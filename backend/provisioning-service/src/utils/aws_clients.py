"""
Shared AWS clients.
Using module-level singletons so they're reused across processor calls.
"""
import os
import boto3

REGION     = os.environ.get("AWS_REGION", "eu-west-1")
ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID", "")
PREFIX     = os.environ.get("RESOURCE_PREFIX", "sdc-lake-dev")

s3         = boto3.client("s3",           region_name=REGION)
s3control  = boto3.client("s3control",    region_name=REGION)
iam        = boto3.client("iam")
sns        = boto3.client("sns",          region_name=REGION)
cognito    = boto3.client("cognito-identity", region_name=REGION)
