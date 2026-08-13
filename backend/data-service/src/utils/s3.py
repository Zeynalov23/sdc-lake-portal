"""
S3 helpers for the data service.

One bucket per space. Authorisation is decided in authz.py and enforced by
signing a URL for one specific object key, so callers must never pass a key
here that has not been through a guard.

Credentials come from the environment: a local session token in development,
Pod Identity in the cluster. The code does not care which.
"""
import os

import boto3
from botocore.config import Config

_REGION = os.environ.get("AWS_REGION", "eu-west-1")

# addressing_style="virtual" is required, not cosmetic. Without it, presigned
# URLs are built against the global host (my-bucket.s3.amazonaws.com) while
# the signature is scoped to the real region. S3 answers those with a 307
# TemporaryRedirect, and since curl and most HTTP clients will not replay a
# PUT body across a redirect, every upload fails. Setting it explicitly makes
# the host and the signature agree: my-bucket.s3.eu-west-1.amazonaws.com
_s3 = boto3.client(
    "s3",
    region_name=_REGION,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)

_PRESIGNED_URL_EXPIRY = 3600  # 1 hour


def list_objects(
    bucket_name: str,
    prefix: str,
    continuation_token: str | None = None,
    max_keys: int = 100,
) -> dict:
    """List one page of object metadata from a space prefix."""
    params = {
        "Bucket": bucket_name,
        "Prefix": prefix,
        "MaxKeys": max_keys,
    }
    if continuation_token:
        params["ContinuationToken"] = continuation_token

    response = _s3.list_objects_v2(**params)

    objects = [
        {
            "key": obj["Key"],
            "size": obj["Size"],
            "lastModified": obj["LastModified"].isoformat(),
            "etag": obj["ETag"].strip('"'),
        }
        for obj in response.get("Contents", [])
    ]

    return {
        "objects": objects,
        "nextToken": response.get("NextContinuationToken"),
        "isTruncated": response.get("IsTruncated", False),
    }


def generate_presigned_download_url(bucket_name: str, key: str) -> str:
    """Generate a presigned GET URL for downloading one object."""
    return _s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=_PRESIGNED_URL_EXPIRY,
    )


def generate_presigned_upload_url(
    bucket_name: str,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Generate a presigned PUT URL for uploading one object."""
    return _s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=_PRESIGNED_URL_EXPIRY,
    )


def get_bucket_versioning(bucket_name: str) -> str:
    """Returns 'Enabled', 'Suspended', or 'Disabled'."""
    response = _s3.get_bucket_versioning(Bucket=bucket_name)
    return response.get("Status", "Disabled")


def set_bucket_versioning(bucket_name: str, enabled: bool) -> None:
    _s3.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={
            "Status": "Enabled" if enabled else "Suspended"
        },
    )
