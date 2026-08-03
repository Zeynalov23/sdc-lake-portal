"""
CREATE_SPACE processor.
Creates per space:
  - S3 bucket with encryption, versioning, public access block
  - Writer IAM role (space-{name}-gw) + reader IAM role (space-{name}-gr)
  - Writer S3 access point + reader S3 access point
  - Identity Pool role mapping rules for gw and gr roles
  - Updates DynamoDB owner membership to READY
  - Updates DynamoDB space metadata to READY
"""
import json
import logging
import os
import time

from botocore.exceptions import ClientError

from src.utils import dynamo
from src.utils.aws_clients import (
    ACCOUNT_ID, PREFIX, REGION,
    cognito, iam, s3, s3control,
)

logger = logging.getLogger(__name__)

_IDENTITY_POOL_ID       = os.environ["COGNITO_IDENTITY_POOL_ID"]
_USER_POOL_ID           = os.environ["COGNITO_USER_POOL_ID"]
_USER_POOL_CLIENT_ID    = os.environ["COGNITO_USER_POOL_CLIENT_ID"]
_CORS_ALLOWED_ORIGIN    = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")


def process(item: dict) -> None:
    space_id  = item["spaceId"]
    owner_id  = item["ownerId"]
    region    = item.get("region", REGION)

    logger.info("Provisioning space: %s", space_id)

    bucket_name  = f"{PREFIX}-space-{space_id}"
    gw_role_name = f"{PREFIX}-space-{space_id}-gw"
    gr_role_name = f"{PREFIX}-space-{space_id}-gr"
    gw_ap_name   = f"{PREFIX}-space-{space_id}-gw-ap"
    gr_ap_name   = f"{PREFIX}-space-{space_id}-gr-ap"

    try:
        # 1. Create S3 bucket
        _create_bucket(bucket_name, region)
        logger.info("Created bucket: %s", bucket_name)

        # 2. Create IAM roles
        gw_role_arn = _create_space_role(gw_role_name, bucket_name, "writer")
        gr_role_arn = _create_space_role(gr_role_name, bucket_name, "reader")
        logger.info("Created IAM roles: %s, %s", gw_role_name, gr_role_name)

        # 3. Create S3 access points
        gw_ap_arn = _create_access_point(gw_ap_name, bucket_name, gw_role_arn, "writer")
        gr_ap_arn = _create_access_point(gr_ap_name, bucket_name, gr_role_arn, "reader")
        logger.info("Created access points: %s, %s", gw_ap_name, gr_ap_name)

        # 4. Update Identity Pool role mappings
        _update_identity_pool_mappings(
            space_id, gw_role_arn, gr_role_arn,
        )
        logger.info("Updated Identity Pool role mappings")

        # 5. Update DynamoDB space metadata to READY
        dynamo.update_status(
            pk     = f"SPACE#{space_id}",
            sk     = "METADATA",
            status = "READY",
            extra  = {
                "bucketName": bucket_name,
                "bucketArn":  f"arn:aws:s3:::{bucket_name}",
                "gwRoleArn":  gw_role_arn,
                "grRoleArn":  gr_role_arn,
                "gwApArn":    gw_ap_arn,
                "grApArn":    gr_ap_arn,
            },
        )

        # 6. Update owner membership record to READY
        dynamo.update_status(
            pk     = f"USER#{owner_id}",
            sk     = f"SPACE#{space_id}#ROLE#writer",
            status = "READY",
            extra  = {
                "accessPointArn": gw_ap_arn,
                "bucketName":     bucket_name,
            },
        )

        logger.info("Space %s provisioned successfully", space_id)

    except Exception as e:
        logger.exception("Failed to provision space %s", space_id)
        dynamo.update_status(
            pk     = f"SPACE#{space_id}",
            sk     = "METADATA",
            status = "FAILED",
            extra  = {"errorMessage": str(e)},
        )
        raise


def _create_bucket(bucket_name: str, region: str) -> None:
    kwargs = {"Bucket": bucket_name}
    if region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        s3.create_bucket(**kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            logger.warning("Bucket %s already exists — continuing", bucket_name)
        else:
            raise

    # Block all public access
    s3.put_public_access_block(
        Bucket                          = bucket_name,
        PublicAccessBlockConfiguration  = {
            "BlockPublicAcls":       True,
            "IgnorePublicAcls":      True,
            "BlockPublicPolicy":     True,
            "RestrictPublicBuckets": True,
        },
    )

    # Enable versioning
    s3.put_bucket_versioning(
        Bucket                  = bucket_name,
        VersioningConfiguration = {"Status": "Enabled"},
    )

    # Enable server-side encryption
    s3.put_bucket_encryption(
        Bucket                            = bucket_name,
        ServerSideEncryptionConfiguration = {
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        },
    )

    # Allow the frontend to PUT/GET directly against presigned URLs —
    # without this, browsers block the cross-origin request entirely
    # before it ever reaches S3.
    s3.put_bucket_cors(
        Bucket             = bucket_name,
        CORSConfiguration  = {
            "CORSRules": [{
                "AllowedOrigins": [_CORS_ALLOWED_ORIGIN],
                "AllowedMethods": ["GET", "PUT", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders":  ["ETag"],
                "MaxAgeSeconds":  3000,
            }]
        },
    )


def _create_space_role(role_name: str, bucket_name: str, access_type: str) -> str:
    """Create an IAM role for a space. Returns the role ARN."""
    trust_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect":    "Allow",
            "Principal": {"Federated": "cognito-identity.amazonaws.com"},
            "Action":    ["sts:AssumeRoleWithWebIdentity", "sts:TagSession"],
            "Condition": {
                "StringEquals": {
                    "cognito-identity.amazonaws.com:aud": _IDENTITY_POOL_ID,
                },
                "ForAnyValue:StringLike": {
                    "cognito-identity.amazonaws.com:amr": "authenticated",
                },
            },
        }],
    })

    try:
        response = iam.create_role(
            RoleName                 = role_name,
            AssumeRolePolicyDocument = trust_policy,
            Tags                     = [
                {"Key": "Project",     "Value": "sdc-lake-portal"},
                {"Key": "SpaceBucket", "Value": bucket_name},
                {"Key": "AccessType",  "Value": access_type},
            ],
        )
        role_arn = response["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            logger.warning("Role %s already exists", role_name)
            role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        else:
            raise

    # Attach inline policy
    s3_actions = (
        ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        if access_type == "writer"
        else ["s3:GetObject", "s3:ListBucket"]
    )

    iam.put_role_policy(
        RoleName       = role_name,
        PolicyName     = "space-access-policy",
        PolicyDocument = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect":   "Allow",
                "Action":   s3_actions,
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            }],
        }),
    )

    return role_arn


def _create_access_point(
    ap_name: str, bucket_name: str, role_arn: str, access_type: str
) -> str:
    """Create an S3 access point scoped to a specific role. Returns the AP ARN."""
    s3_actions = (
        ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        if access_type == "writer"
        else ["s3:GetObject", "s3:ListBucket"]
    )

    ap_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect":    "Allow",
            "Principal": {"AWS": role_arn},
            "Action":    s3_actions,
            "Resource": [
                f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}",
                f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}/object/*",
            ],
        }],
    })

    try:
        response = s3control.create_access_point(
            AccountId = ACCOUNT_ID,
            Name      = ap_name,
            Bucket    = bucket_name,
        )
        ap_arn = response["AccessPointArn"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessPointAlreadyOwnedByYou":
            logger.warning("Access point %s already exists", ap_name)
            ap_arn = (
                f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}"
            )
        else:
            raise

    # IAM roles take a few seconds to propagate before they're recognized
    # as valid principals elsewhere — retry through that window instead of
    # failing the whole space on a role we just created ourselves.
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            s3control.put_access_point_policy(
                AccountId  = ACCOUNT_ID,
                Name       = ap_name,
                Policy     = ap_policy,
            )
            break
        except ClientError as e:
            is_last = attempt == max_attempts - 1
            if e.response["Error"]["Code"] == "MalformedPolicy" and not is_last:
                delay = 2 * (2 ** attempt)
                logger.warning(
                    "put_access_point_policy for %s failed (IAM role likely not "
                    "yet propagated) — retrying in %ss (attempt %d/%d)",
                    ap_name, delay, attempt + 1, max_attempts,
                )
                time.sleep(delay)
            else:
                raise

    return ap_arn


def _update_identity_pool_mappings(
    space_id: str, gw_role_arn: str, gr_role_arn: str,
) -> None:
    """
    Add role mapping rules to the Cognito Identity Pool for this space.
    Rules map custom:spaceId claim → specific IAM role.
    We read existing rules and append — never overwrite the full list.
    """
    provider = (
        f"cognito-idp.{REGION}.amazonaws.com/"
        f"{_USER_POOL_ID}:"
        f"{_USER_POOL_CLIENT_ID}"
    )

    # Get existing role mappings
    existing = cognito.get_identity_pool_roles(
        IdentityPoolId=_IDENTITY_POOL_ID,
    )
    role_mappings = existing.get("RoleMappings", {})
    existing_rules = (
        role_mappings.get(provider, {})
        .get("RulesConfiguration", {})
        .get("Rules", [])
    )

    # Add new rules for this space
    new_rules = [
        {
            "Claim":     "custom:spaceId",
            "MatchType": "Equals",
            "Value":     f"{space_id}:writer",
            "RoleARN":   gw_role_arn,
        },
        {
            "Claim":     "custom:spaceId",
            "MatchType": "Equals",
            "Value":     f"{space_id}:reader",
            "RoleARN":   gr_role_arn,
        },
    ]

    all_rules = existing_rules + new_rules

    cognito.set_identity_pool_roles(
        IdentityPoolId = _IDENTITY_POOL_ID,
        Roles          = existing.get("Roles", {}),
        RoleMappings   = {
            provider: {
                "Type":                 "Rules",
                "AmbiguousRoleResolution": "Deny",
                "RulesConfiguration":   {"Rules": all_rules},
            }
        },
    )
