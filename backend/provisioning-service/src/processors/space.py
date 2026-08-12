"""
CREATE_SPACE processor.

Creates one S3 bucket per space and marks the space READY.

This used to also create two IAM roles, two S3 access points and a set of
Cognito identity-pool role mappings per space. All of that is gone:
authorisation is now decided by the data service and enforced by presigned
URLs signed with the pod's own identity, so the per-space AWS principals had
nothing reading them. Removing them also removes the identity pool's hard
limit of 25 role-mapping rules, which capped the platform at ~12 spaces.
"""
import logging
import os

from botocore.exceptions import ClientError

from src.utils import dynamo
from src.utils.aws_clients import PREFIX, REGION, s3

logger = logging.getLogger(__name__)

_CORS_ALLOWED_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")


def bucket_name_for(space_id: str) -> str:
    return f"{PREFIX}-space-{space_id}"


def process(item: dict) -> None:
    space_id = item["spaceId"]
    region = item.get("region", REGION)
    bucket_name = bucket_name_for(space_id)

    logger.info("Provisioning space %s -> bucket %s", space_id, bucket_name)

    try:
        _create_bucket(bucket_name, region)

        dynamo.update_status(
            pk=f"SPACE#{space_id}",
            sk="METADATA",
            status="READY",
            extra={
                "bucketName": bucket_name,
                "bucketArn": f"arn:aws:s3:::{bucket_name}",
            },
        )
        logger.info("Space %s is READY", space_id)

    except Exception as e:
        logger.exception("Failed to provision space %s", space_id)
        # Record why it failed so the UI can show something useful, then
        # re-raise: the message stays on the queue and is retried, and ends
        # up in the DLQ after maxReceiveCount.
        dynamo.update_status(
            pk=f"SPACE#{space_id}",
            sk="METADATA",
            status="FAILED",
            extra={"errorMessage": str(e)},
        )
        raise


def _create_bucket(bucket_name: str, region: str) -> None:
    kwargs = {"Bucket": bucket_name}
    if region != "us-east-1":
        # us-east-1 is the one region that rejects an explicit location
        # constraint, because it is the API's default.
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        s3.create_bucket(**kwargs)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "BucketAlreadyOwnedByYou":
            # A retried message must not fail the whole space. Every call
            # below is idempotent, so carrying on is safe.
            logger.warning("Bucket %s already exists - continuing", bucket_name)
        else:
            raise

    s3.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    s3.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"},
    )

    s3.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
            }]
        },
    )

    # The browser uploads straight to S3 with a presigned URL. Without CORS
    # the request is blocked by the browser before S3 ever sees it.
    s3.put_bucket_cors(
        Bucket=bucket_name,
        CORSConfiguration={
            "CORSRules": [{
                "AllowedOrigins": [_CORS_ALLOWED_ORIGIN],
                "AllowedMethods": ["GET", "PUT", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3000,
            }]
        },
    )
