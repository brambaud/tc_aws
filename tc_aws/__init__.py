# coding: utf-8

# Copyright (c) 2015, thumbor-community
# Use of this source code is governed by the MIT license that can be
# found in the LICENSE file.

from thumbor.config import Config

Config.define('TC_AWS_REGION', 'eu-west-1', 'S3 region', 'S3')
Config.define('TC_AWS_STORAGE_BUCKET', None, 'S3 bucket for Storage', 'S3')
Config.define('TC_AWS_STORAGE_ROOT_PATH', '', 'S3 path prefix for Storage bucket', 'S3')
Config.define('TC_AWS_LOADER_BUCKET', None, 'S3 bucket for loader', 'S3')
Config.define('TC_AWS_LOADER_ROOT_PATH', '', 'S3 path prefix for Loader bucket', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_BUCKET', None, 'S3 bucket for result Storage', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_ROOT_PATH', '', 'S3 path prefix for Result storage bucket', 'S3')
Config.define('TC_AWS_STORAGE_SSE', False, 'S3 encryption', 'S3')
Config.define('TC_AWS_STORAGE_RRS', False, 'S3 redundancy', 'S3')
Config.define('TC_AWS_ENABLE_HTTP_LOADER', False, 'Enable HTTP Loader as well?', 'S3')
Config.define('TC_AWS_ALLOWED_BUCKETS', False, 'List of allowed buckets to be requested', 'S3')
Config.define('TC_AWS_STORE_METADATA', False, 'S3 store result with metadata', 'S3')
Config.define('TC_AWS_ENDPOINT', None, 'Custom AWS API endpoint', 'S3')
Config.define('TC_AWS_MAX_RETRY', 0, 'Max retries for get image from S3 bucket', 'S3')
Config.define('TC_AWS_RANDOMIZE_KEYS', False, 'Should S3 keys be randomized? Defaults to False for BC, for performance, should be set to True', 'S3')
Config.define('TC_AWS_ROOT_IMAGE_NAME', '', 'When resizing a URL that ends in a slash, what should the corresponding cache key be?', 'S3')
Config.define('TC_AWS_LOADER_ROLE_ARN', '', 'IAM role ARN to assume for loader S3 access (enables STS assume role when set)', 'S3')
Config.define('TC_AWS_LOADER_ROLE_SESSION_NAME', 'thumbor-session', 'Session name for loader STS assume role', 'S3')
Config.define('TC_AWS_LOADER_ROLE_EXTERNAL_ID', '', 'External ID for loader STS assume role (optional, for cross-account access)', 'S3')
Config.define('TC_AWS_LOADER_ASSUME_ROLE_DURATION_SECONDS', None, 'Duration in seconds for loader assumed role credentials (None lets AWS use its default of 3600)', 'S3')
Config.define('TC_AWS_LOADER_STS_ENDPOINT', None, 'Custom STS endpoint URL for loader (defaults to the AWS global STS endpoint)', 'S3')
Config.define('TC_AWS_STORAGE_ROLE_ARN', '', 'IAM role ARN to assume for storage S3 access (enables STS assume role when set)', 'S3')
Config.define('TC_AWS_STORAGE_ROLE_SESSION_NAME', 'thumbor-session', 'Session name for storage STS assume role', 'S3')
Config.define('TC_AWS_STORAGE_ROLE_EXTERNAL_ID', '', 'External ID for storage STS assume role (optional, for cross-account access)', 'S3')
Config.define('TC_AWS_STORAGE_ASSUME_ROLE_DURATION_SECONDS', None, 'Duration in seconds for storage assumed role credentials (None lets AWS use its default of 3600)', 'S3')
Config.define('TC_AWS_STORAGE_STS_ENDPOINT', None, 'Custom STS endpoint URL for storage (defaults to the AWS global STS endpoint)', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_ROLE_ARN', '', 'IAM role ARN to assume for result storage S3 access (enables STS assume role when set)', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_ROLE_SESSION_NAME', 'thumbor-session', 'Session name for result storage STS assume role', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_ROLE_EXTERNAL_ID', '', 'External ID for result storage STS assume role (optional, for cross-account access)', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_ASSUME_ROLE_DURATION_SECONDS', None, 'Duration in seconds for result storage assumed role credentials (None lets AWS use its default of 3600)', 'S3')
Config.define('TC_AWS_RESULT_STORAGE_STS_ENDPOINT', None, 'Custom STS endpoint URL for result storage (defaults to the AWS global STS endpoint)', 'S3')
