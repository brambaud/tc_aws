# coding: utf-8

# Copyright (c) 2015, thumbor-community
# Use of this source code is governed by the MIT license that can be
# found in the LICENSE file.

from datetime import datetime, timezone, timedelta

from thumbor.utils import logger


_REFRESH_THRESHOLD = timedelta(minutes=5)


class AssumeRoleCredentialProvider:
    """Provides temporary credentials via STS assume role with caching."""

    def __init__(self, session, role_arn, role_session_name, external_id=None,
                 duration_seconds=None, region=None, sts_endpoint=None):
        self._session = session
        self._role_arn = role_arn
        self._role_session_name = role_session_name
        self._external_id = external_id
        self._duration_seconds = duration_seconds  # None means let AWS use its default
        self._region = region
        self._sts_endpoint = sts_endpoint
        self._credentials = None
        self._expiration = None

    def needs_refresh(self):
        if self._credentials is None or self._expiration is None:
            return True
        now = datetime.now(timezone.utc)
        return (self._expiration - now) < _REFRESH_THRESHOLD

    async def get_credentials(self):
        if self.needs_refresh():
            await self._refresh()
        return self._credentials

    async def _refresh(self):
        logger.debug('Refreshing STS credentials for role %s', self._role_arn)
        async with self._session.create_client(
            'sts',
            region_name=self._region,
            endpoint_url=self._sts_endpoint,
        ) as sts:
            kwargs = dict(
                RoleArn=self._role_arn,
                RoleSessionName=self._role_session_name,
            )
            if self._duration_seconds is not None:
                kwargs['DurationSeconds'] = self._duration_seconds
            if self._external_id:
                kwargs['ExternalId'] = self._external_id

            try:
                response = await sts.assume_role(**kwargs)
            except Exception:
                logger.exception('STS assume_role failed for %s', self._role_arn)
                raise

        self._credentials = response['Credentials']
        self._expiration = response['Credentials']['Expiration']
        if self._expiration.tzinfo is None:
            self._expiration = self._expiration.replace(tzinfo=timezone.utc)
