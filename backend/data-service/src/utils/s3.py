"""
S3 helpers for the data service.
All operations go through S3 access points, never directly to buckets.
Pod Identity provides the IAM credentials automatically.
"""
import os

import boto3
from botocore.config import Config

_REGION     = os.environ.get("AWS_REGION", "eu-west-1")
_ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID", "")

_s3 = boto3.client(
    "s3",
    region_name=_REGION,
    config=Config(signature_version="s3v4"),
)

_PRESIGNED_URL_EXPIRY = 3600  # 1 hour


def list_objects(access_point_arn: str, prefix: str = "") -> list[dict]:
    """
    List objects in a bucket via an access point.
    Returns simplified file metadata.
    """
    paginator = _s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(
        Bucket=access_point_arn,
        Prefix=prefix,
    )

    objects = []
    for page in pages:
        for obj in page.get("Contents", []):
            objects.append({
                "key":          obj["Key"],
                "size":         obj["Size"],
                "lastModified": obj["LastModified"].isoformat(),
                "etag":         obj["ETag"].strip('"'),
            })

    return objects


def generate_presigned_download_url(
    access_point_arn: str, key: str
) -> str:
    """Generate a presigned GET URL for downloading a file."""
    return _s3.generate_presigned_url(
        ClientMethod = "get_object",
        Params       = {"Bucket": access_point_arn, "Key": key},
        ExpiresIn    = _PRESIGNED_URL_EXPIRY,
    )


def generate_presigned_upload_url(
    access_point_arn: str, key: str, content_type: str = "application/octet-stream"
) -> str:
    """Generate a presigned PUT URL for uploading a file."""
    return _s3.generate_presigned_url(
        ClientMethod = "put_object",
        Params       = {
            "Bucket":      access_point_arn,
            "Key":         key,
            "ContentType": content_type,
        },
        ExpiresIn = _PRESIGNED_URL_EXPIRY,
    )


def get_bucket_versioning(bucket_name: str) -> str:
    """Returns 'Enabled', 'Suspended', or 'Disabled'."""
    response = _s3.get_bucket_versioning(Bucket=bucket_name)
    return response.get("Status", "Disabled")


def set_bucket_versioning(bucket_name: str, enabled: bool) -> None:
    _s3.put_bucket_versioning(
        Bucket                  = bucket_name,
        VersioningConfiguration = {
            "Status": "Enabled" if enabled else "Suspended"
        },
    )
