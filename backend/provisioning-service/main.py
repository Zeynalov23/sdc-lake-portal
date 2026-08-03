"""
Provisioning service — main entry point.
Runs as a long-lived pod in EKS.
Polls SQS, dispatches to the right processor, deletes message on success.
Failed messages stay in SQS for retry (up to 3 times), then go to DLQ.
"""
import json
import logging
import os
import time

import boto3

from src.processors import space, access, notification
from src.utils import dynamo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_SQS_QUEUE_URL  = os.environ["SQS_QUEUE_URL"]
_POLL_WAIT_SECS = int(os.environ.get("POLL_WAIT_SECONDS", "20"))  # long polling
_sqs = boto3.client("sqs")

PROCESSORS = {
    "CREATE_SPACE":        space.process,
    "CREATE_ACCESS":       access.process,
    "CREATE_NOTIFICATION": notification.process,
}


def _process_message(message: dict) -> None:
    body = json.loads(message["Body"])

    # DynamoDB Streams via EventBridge Pipes wraps the record
    # Extract the actual DynamoDB new image
    record     = body.get("dynamodb", {})
    new_image  = record.get("NewImage", {})
    event_type = new_image.get("eventType", {}).get("S", "")

    logger.info("Processing event type: %s", event_type)

    processor = PROCESSORS.get(event_type)
    if not processor:
        logger.warning("No processor for event type: %s — skipping", event_type)
        return

    processor(new_image)


def _deserialize_dynamo_item(item: dict) -> dict:
    """Convert DynamoDB typed JSON to plain Python dict."""
    deserializer = boto3.dynamodb.types.TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def run():
    logger.info("Provisioning service started. Polling SQS: %s", _SQS_QUEUE_URL)

    while True:
        try:
            response = _sqs.receive_message(
                QueueUrl            = _SQS_QUEUE_URL,
                MaxNumberOfMessages = 5,
                WaitTimeSeconds     = _POLL_WAIT_SECS,  # long polling
                VisibilityTimeout   = 300,               # 5 min to process
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                try:
                    body       = json.loads(message["Body"])
                    new_image  = body.get("dynamodb", {}).get("NewImage", {})
                    item       = _deserialize_dynamo_item(new_image)
                    event_type = item.get("eventType", "")

                    logger.info(
                        "Processing message — eventType=%s requestId=%s",
                        event_type,
                        item.get("requestId", "unknown"),
                    )

                    processor = PROCESSORS.get(event_type)
                    if not processor:
                        logger.warning("No processor for event type: %s", event_type)
                        _delete_message(receipt_handle)
                        continue

                    processor(item)

                    # Success — delete from queue
                    _delete_message(receipt_handle)
                    logger.info("Message processed successfully")

                except Exception:
                    logger.exception(
                        "Failed to process message — leaving in queue for retry"
                    )
                    # Don't delete — SQS will redeliver after visibility timeout
                    # After maxReceiveCount (3) it goes to DLQ

        except Exception:
            logger.exception("SQS polling error — retrying in 5s")
            time.sleep(5)


def _delete_message(receipt_handle: str) -> None:
    _sqs.delete_message(
        QueueUrl      = _SQS_QUEUE_URL,
        ReceiptHandle = receipt_handle,
    )


if __name__ == "__main__":
    run()
