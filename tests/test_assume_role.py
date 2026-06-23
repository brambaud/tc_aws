# coding: utf-8

# Copyright (c) 2015, thumbor-community
# Use of this source code is governed by the MIT license that can be
# found in the LICENSE file.

import json
from datetime import datetime, timezone, timedelta

import botocore.session
from tornado.testing import gen_test

from tests import S3MockedAsyncTestCase
from tests.fixtures.storage_fixture import s3_bucket
from tc_aws.aws.bucket import Bucket
from tc_aws.aws.credentials import AssumeRoleCredentialProvider


_ROLE_NAME = 'thumbor-test-role'
_ROLE_ARN = 'arn:aws:iam::123456789012:role/thumbor-test-role'
_MOCK_ENDPOINT = 'http://localhost:5000'
_REGION = 'us-east-1'


def _create_iam_role():
    """Create an IAM role via moto using botocore."""
    client = botocore.session.get_session().create_client(
        'iam',
        region_name=_REGION,
        endpoint_url=_MOCK_ENDPOINT,
    )
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "Resource": "*",
        }]
    }
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }]
    }
    client.create_role(
        RoleName=_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(assume_role_policy),
    )
    client.put_role_policy(
        RoleName=_ROLE_NAME,
        PolicyName='s3-access',
        PolicyDocument=json.dumps(policy),
    )
    return _ROLE_ARN


class AssumeRoleBucketTestCase(S3MockedAsyncTestCase):

    def setUp(self):
        super().setUp()
        _create_iam_role()

    def tearDown(self):
        super().tearDown()
        Bucket._instances = {}

    @gen_test
    async def test_assume_role_loads_object(self):
        direct = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT)
        await direct.put('test-key.jpg', b'hello world')

        role_bucket = Bucket(
            s3_bucket, _REGION, _MOCK_ENDPOINT,
            role_arn=_ROLE_ARN, role_session_name='thumbor-session', sts_endpoint=_MOCK_ENDPOINT,
        )
        response = await role_bucket.get('test-key.jpg')
        async with response['Body'] as stream:
            data = await stream.read()
        self.assertEqual(data, b'hello world')

    @gen_test
    async def test_credentials_are_cached(self):
        role_bucket = Bucket(
            s3_bucket, _REGION, _MOCK_ENDPOINT,
            role_arn=_ROLE_ARN, role_session_name='thumbor-session', sts_endpoint=_MOCK_ENDPOINT,
        )
        provider = role_bucket._credential_provider

        creds1 = await provider.get_credentials()
        creds2 = await provider.get_credentials()

        self.assertIs(creds1, creds2)

    @gen_test
    async def test_credentials_refresh_on_expiry(self):
        role_bucket = Bucket(
            s3_bucket, _REGION, _MOCK_ENDPOINT,
            role_arn=_ROLE_ARN, role_session_name='thumbor-session', sts_endpoint=_MOCK_ENDPOINT,
        )
        provider = role_bucket._credential_provider

        await provider.get_credentials()
        first_token = provider._credentials['SessionToken']

        # Simulate near-expiry by moving the expiration back
        provider._expiration = datetime.now(timezone.utc) + timedelta(seconds=60)

        await provider.get_credentials()
        second_token = provider._credentials['SessionToken']

        # moto returns a new token on each assume_role call
        self.assertNotEqual(first_token, second_token)

    @gen_test
    async def test_no_role_arn_uses_default_credentials(self):
        bucket = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT)
        self.assertIsNone(bucket._credential_provider)

        await bucket.put('ambient-test.jpg', b'ambient data')
        response = await bucket.get('ambient-test.jpg')
        async with response['Body'] as stream:
            data = await stream.read()
        self.assertEqual(data, b'ambient data')

    @gen_test
    async def test_invalid_role_arn_raises(self):
        bucket = Bucket(
            s3_bucket, _REGION, _MOCK_ENDPOINT,
            role_arn='not-a-valid-arn',
            role_session_name='thumbor-session',
            sts_endpoint=_MOCK_ENDPOINT,
        )
        with self.assertRaises(Exception):
            await bucket._get_client()

    @gen_test
    async def test_singleton_isolation(self):
        bucket_a = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT, role_arn=_ROLE_ARN)
        bucket_b = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT, role_arn='arn:aws:iam::123456789012:role/other-role')
        bucket_no_role = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT)

        self.assertIsNot(bucket_a, bucket_b)
        self.assertIsNot(bucket_a, bucket_no_role)
        self.assertIsNot(bucket_b, bucket_no_role)

        # Same role ARN returns same instance
        bucket_a2 = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT, role_arn=_ROLE_ARN)
        self.assertIs(bucket_a, bucket_a2)
