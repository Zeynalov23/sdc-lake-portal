"""
CREATE_ACCESS processor.
Creates a guest access point on the target space bucket
scoped to the requesting user's role (sourceRole).
Updates the DynamoDB membership record with the access point ARN.
"""
import json
import logging

from botocore.exceptions import ClientError

from src.utils import dynamo
from src.utils.aws_clients import ACCOUNT_ID, PREFIX, REGION, iam, s3control

logger = logging.getLogger(__name__)


def process(item: dict) -> None:
    user_id       = item["userId"]
    space_id      = item["spaceId"]
    source_role   = item["sourceRole"]
    role          = item["role"]
    sk            = f"SPACE#{space_id}#ROLE#{source_role}"

    logger.info(
        "Provisioning guest access: userId=%s spaceId=%s sourceRole=%s",
        user_id, space_id, source_role,
    )

    # Derive names
    bucket_name = f"{PREFIX}-space-{space_id}"
    ap_name     = f"{PREFIX}-space-{space_id}-guest-{source_role[-20:]}"  # keep under 63 chars

    try:
        # Get the source role ARN from IAM
        source_role_arn = iam.get_role(RoleName=source_role)["Role"]["Arn"]

        # Create guest access point on target bucket
        s3_actions = (
            ["s3:GetObject", "s3:ListBucket"]
            if role == "reader"
            else ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        )

        ap_policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect":    "Allow",
                "Principal": {"AWS": source_role_arn},
                "Action":    s3_actions,
                "Resource": [
                    f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}",
                    f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}/object/*",
                ],
            }],
        })

        try:
            s3control.create_access_point(
                AccountId = ACCOUNT_ID,
                Name      = ap_name,
                Bucket    = bucket_name,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessPointAlreadyOwnedByYou":
                logger.warning("Access point %s already exists", ap_name)
            else:
                raise

        s3control.put_access_point_policy(
            AccountId = ACCOUNT_ID,
            Name      = ap_name,
            Policy    = ap_policy,
        )

        ap_arn = f"arn:aws:s3:{REGION}:{ACCOUNT_ID}:accesspoint/{ap_name}"

        # Update membership record to READY with access point ARN
        dynamo.update_status(
            pk     = f"USER#{user_id}",
            sk     = sk,
            status = "READY",
            extra  = {
                "accessPointArn": ap_arn,
                "bucketName":     bucket_name,
            },
        )

        logger.info(
            "Guest access provisioned: %s → %s via %s",
            source_role, space_id, ap_name,
        )

    except Exception as e:
        logger.exception("Failed to provision guest access")
        dynamo.update_status(
            pk     = f"USER#{user_id}",
            sk     = sk,
            status = "FAILED",
            extra  = {"errorMessage": str(e)},
        )
        raise
