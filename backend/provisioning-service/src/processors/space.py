"""CREATE_SPACE processor.

Creates one S3 bucket per space and activates the space metadata and owner
membership records in DynamoDB. Authorization is handled by the data service
using DynamoDB membership records; no per-space IAM roles, Cognito role
mappings, or S3 Access Points are required.
"""
import logging
import os

from botocore.exceptions import ClientError

from src.utils import dynamo
from src.utils.aws_clients import PREFIX, REGION, s3

logger = logging.getLogger(__name__)

_CORS_ALLOWED_ORIGIN = os.environ.get(
    "CORS_ALLOWED_ORIGIN", "http://localhost:3000"
)


def process(item: dict) -> None:
    space_id = item["spaceId"]
    owner_id = item["ownerId"]
    region = item.get("region", REGION)
    bucket_name = f"{PREFIX}-space-{space_id}"

    logger.info("Provisioning space: %s", space_id)

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

        dynamo.update_status(
            pk=f"SPACE#{space_id}",
            sk=f"MEMBER#{owner_id}",
            status="ACTIVE",
        )

        logger.info("Space %s provisioned successfully", space_id)

    except Exception as exc:
        logger.exception("Failed to provision space %s", space_id)
        dynamo.update_status(
            pk=f"SPACE#{space_id}",
            sk="METADATA",
            status="FAILED",
            extra={"errorMessage": str(exc)},
        )
        raise


def _create_bucket(bucket_name: str, region: str) -> None:
    kwargs = {"Bucket": bucket_name}
    if region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        s3.create_bucket(**kwargs)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
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
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        },
    )

    s3.put_bucket_cors(
        Bucket=bucket_name,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": [_CORS_ALLOWED_ORIGIN],
                    "AllowedMethods": ["GET", "PUT", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3000,
                }
            ]
        },
    )
