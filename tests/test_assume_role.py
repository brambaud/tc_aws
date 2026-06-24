# coding: utf-8

# Copyright (c) 2015, thumbor-community
# Use of this source code is governed by the MIT license that can be
# found in the LICENSE file.

import json
from datetime import datetime, timezone, timedelta

import botocore.exceptions
import botocore.session
from derpconf.config import Config
from thumbor.context import Context
from tornado.testing import gen_test

from tests import S3MockedAsyncTestCase
from tests.fixtures.storage_fixture import s3_bucket, IMAGE_BYTES, IMAGE_URL, get_server
from tc_aws.aws.bucket import Bucket
from tc_aws.aws.credentials import AssumeRoleCredentialProvider
from tc_aws.loaders import s3_loader
from tc_aws.storages.s3_storage import Storage
from tc_aws.result_storages.s3_storage import Storage as ResultStorage


_ROLE_NAME = 'thumbor-test-role'
_ROLE_ARN = 'arn:aws:iam::123456789012:role/thumbor-test-role'
_MOCK_ENDPOINT = 'http://localhost:5000'
_REGION = 'us-east-1'


def _create_iam_role():
    # Sync botocore is intentional: setUp() is a synchronous method so async
    # clients are not available here. Moto shares state between the sync and
    # async paths, so resources created here are visible to the async tests.
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
        with self.assertRaises(botocore.exceptions.ParamValidationError):
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


class PerServiceAssumeRoleTestCase(S3MockedAsyncTestCase):
    """
    Tests that per-service role config is read and applied correctly by each
    Thumbor extension point (loader, storage, result_storage).
    """

    def setUp(self):
        super().setUp()
        _create_iam_role()

    def tearDown(self):
        super().tearDown()
        Bucket._instances = {}

    def _seed_s3(self, key, body=IMAGE_BYTES):
        """Upload an object via the sync botocore client (no aiobotocore needed)."""
        client = botocore.session.get_session().create_client(
            's3', endpoint_url=_MOCK_ENDPOINT
        )
        client.put_object(Bucket=s3_bucket, Key=key, Body=body, ContentType='image/jpeg')

    @gen_test
    async def test_loader_with_role(self):
        self._seed_s3('loader-role-test.jpg')

        conf = Config(
            TC_AWS_LOADER_BUCKET=s3_bucket,
            TC_AWS_LOADER_ROOT_PATH='',
            TC_AWS_REGION=_REGION,
            TC_AWS_ENDPOINT=_MOCK_ENDPOINT,
            TC_AWS_LOADER_ROLE_ARN=_ROLE_ARN,
            TC_AWS_LOADER_ROLE_SESSION_NAME='thumbor-session',
            TC_AWS_LOADER_STS_ENDPOINT=_MOCK_ENDPOINT,
        )
        result = await s3_loader.load(Context(config=conf), 'loader-role-test.jpg')
        self.assertTrue(result.successful)
        self.assertEqual(result.buffer, IMAGE_BYTES)

    @gen_test
    async def test_storage_with_role(self):
        conf = Config(
            TC_AWS_STORAGE_BUCKET=s3_bucket,
            TC_AWS_REGION=_REGION,
            TC_AWS_ENDPOINT=_MOCK_ENDPOINT,
            TC_AWS_STORAGE_ROLE_ARN=_ROLE_ARN,
            TC_AWS_STORAGE_ROLE_SESSION_NAME='thumbor-session',
            TC_AWS_STORAGE_STS_ENDPOINT=_MOCK_ENDPOINT,
        )
        storage = Storage(Context(config=conf, server=get_server('ACME-SEC')))
        await storage.put(IMAGE_URL % 'role-test', IMAGE_BYTES)
        result = await storage.get(IMAGE_URL % 'role-test')
        self.assertEqual(result, IMAGE_BYTES)

    @gen_test
    async def test_result_storage_with_role(self):
        conf = Config(
            TC_AWS_RESULT_STORAGE_BUCKET=s3_bucket,
            TC_AWS_REGION=_REGION,
            TC_AWS_ENDPOINT=_MOCK_ENDPOINT,
            TC_AWS_RESULT_STORAGE_ROLE_ARN=_ROLE_ARN,
            TC_AWS_RESULT_STORAGE_ROLE_SESSION_NAME='thumbor-session',
            TC_AWS_RESULT_STORAGE_STS_ENDPOINT=_MOCK_ENDPOINT,
        )

        class Request:
            url = IMAGE_URL % 'rs-role-test'

        ctx = Context(config=conf, server=get_server('ACME-SEC'))
        ctx.request = Request
        storage = ResultStorage(ctx)
        await storage.put(IMAGE_BYTES)
        result = await storage.get()
        self.assertEqual(result.buffer, IMAGE_BYTES)

    @gen_test
    async def test_no_role_configured(self):
        conf = Config(
            TC_AWS_STORAGE_BUCKET=s3_bucket,
            TC_AWS_LOADER_BUCKET=s3_bucket,
            TC_AWS_RESULT_STORAGE_BUCKET=s3_bucket,
            TC_AWS_REGION=_REGION,
            TC_AWS_ENDPOINT=_MOCK_ENDPOINT,
        )
        ctx = Context(config=conf, server=get_server('ACME-SEC'))
        # No role params set: the Bucket created by storage must have no credential provider.
        bucket = Storage(ctx).storage
        self.assertIsNone(bucket._credential_provider)

    @gen_test
    async def test_mixed_config(self):
        conf = Config(
            TC_AWS_LOADER_BUCKET=s3_bucket,
            TC_AWS_STORAGE_BUCKET=s3_bucket,
            TC_AWS_RESULT_STORAGE_BUCKET=s3_bucket,
            TC_AWS_REGION=_REGION,
            TC_AWS_ENDPOINT=_MOCK_ENDPOINT,
            # Only loader gets a role; storage and result_storage use ambient creds.
            TC_AWS_LOADER_ROLE_ARN=_ROLE_ARN,
            TC_AWS_LOADER_ROLE_SESSION_NAME='thumbor-session',
            TC_AWS_LOADER_STS_ENDPOINT=_MOCK_ENDPOINT,
        )

        class Request:
            url = IMAGE_URL % 'mixed-test'

        ctx = Context(config=conf, server=get_server('ACME-SEC'))
        ctx.request = Request

        storage_bucket = Storage(ctx).storage
        result_storage_bucket = ResultStorage(ctx).storage

        self.assertIsNone(storage_bucket._credential_provider)
        self.assertIsNone(result_storage_bucket._credential_provider)

        self._seed_s3('mixed-test.jpg')
        result = await s3_loader.load(Context(config=conf), 'mixed-test.jpg')
        self.assertTrue(result.successful)

    @gen_test
    async def test_singleton_isolation_per_service(self):
        storage_role_arn = 'arn:aws:iam::123456789012:role/storage-role'

        loader_bucket = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT, role_arn=_ROLE_ARN)
        storage_bucket = Bucket(s3_bucket, _REGION, _MOCK_ENDPOINT, role_arn=storage_role_arn)

        self.assertIsNot(loader_bucket, storage_bucket)
        self.assertNotEqual(
            loader_bucket._credential_provider._role_arn,
            storage_bucket._credential_provider._role_arn,
        )
