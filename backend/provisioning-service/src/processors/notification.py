"""
CREATE_NOTIFICATION processor.
Creates an SNS topic for the space (if needed) and
wires up S3 event notifications to the target ARN.
"""
import json
import logging

from src.utils import dynamo
from src.utils.aws_clients import ACCOUNT_ID, PREFIX, REGION, s3, sns

logger = logging.getLogger(__name__)


def process(item: dict) -> None:
    space_id        = item["spaceId"]
    notification_id = item["notificationId"]
    events          = item["events"]
    target_arn      = item["targetArn"]
    prefix          = item.get("prefix", "")
    user_id         = item["userId"]

    pk = f"SPACE#{space_id}"
    sk = f"NOTIFICATION#{notification_id}"

    logger.info("Provisioning notification: spaceId=%s id=%s", space_id, notification_id)

    bucket_name = f"{PREFIX}-space-{space_id}"

    try:
        # Get existing notification config
        existing = s3.get_bucket_notification_configuration(Bucket=bucket_name)
        topic_configs = existing.get("TopicConfigurations", [])

        # Build new notification config
        new_config = {
            "Id":       notification_id,
            "TopicArn": target_arn,
            "Events":   events,
        }

        if prefix:
            new_config["Filter"] = {
                "Key": {
                    "FilterRules": [{"Name": "prefix", "Value": prefix}]
                }
            }

        topic_configs.append(new_config)

        # Put updated notification config
        s3.put_bucket_notification_configuration(
            Bucket                    = bucket_name,
            NotificationConfiguration = {
                "TopicConfigurations": topic_configs,
            },
        )

        dynamo.update_status(
            pk     = pk,
            sk     = sk,
            status = "READY",
            extra  = {"targetArn": target_arn},
        )

        logger.info("Notification %s provisioned on bucket %s", notification_id, bucket_name)

    except Exception as e:
        logger.exception("Failed to provision notification %s", notification_id)
        dynamo.update_status(
            pk     = pk,
            sk     = sk,
            status = "FAILED",
            extra  = {"errorMessage": str(e)},
        )
        raise
