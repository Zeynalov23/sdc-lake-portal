"""
Shared AWS clients.

Module-level singletons: boto3 clients are thread-safe and cheap to reuse,
but expensive to construct repeatedly.

Only S3 remains. The IAM, s3control and cognito-identity clients went away
with the per-space roles and access points.
"""
import os

import boto3

REGION = os.environ.get("AWS_REGION", "eu-west-1")
PREFIX = os.environ.get("RESOURCE_PREFIX", "sdc-lake-dev")

s3 = boto3.client("s3", region_name=REGION)
