"""
Provisioning service.

Long-lived pod. Polls SQS, dispatches to a processor, deletes the message on
success. A failed message is left on the queue: SQS redelivers it after the
visibility timeout, and after maxReceiveCount it lands in the DLQ.

Liveness: there is no readiness probe here on purpose. Readiness controls
whether a pod is in a Service's endpoint list, and this pod has no Service
and takes no inbound traffic, so there is nothing for readiness to gate.

Liveness does matter, but "the process is running" is the useless version of
it. The failure that actually hurts is a worker still running while its poll
loop is wedged - stuck on a socket with no timeout, or spinning on one
message. So the loop touches a heartbeat file on every cycle and the probe
checks its age. Note the heartbeat is written on empty receives too: an idle
queue is healthy, and only marking it on processed messages would restart
the pod in a loop whenever there is no work.
"""
import json
import logging
import os
import time

import boto3
import boto3.dynamodb.types

from src.processors import space

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
_POLL_WAIT_SECS = int(os.environ.get("POLL_WAIT_SECONDS", "20"))
_HEARTBEAT_FILE = os.environ.get("HEARTBEAT_FILE", "/tmp/heartbeat")

_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
_deserializer = boto3.dynamodb.types.TypeDeserializer()

PROCESSORS = {
    "CREATE_SPACE": space.process,
}


def _touch_heartbeat() -> None:
    with open(_HEARTBEAT_FILE, "w") as f:
        f.write(str(time.time()))


def _deserialize(image: dict) -> dict:
    """DynamoDB stream images are typed JSON ({"S": "x"}); flatten them."""
    return {k: _deserializer.deserialize(v) for k, v in image.items()}


def _handle(message: dict) -> None:
    body = json.loads(message["Body"])
    new_image = body.get("dynamodb", {}).get("NewImage", {})
    if not new_image:
        logger.warning("Message has no NewImage - skipping")
        return

    item = _deserialize(new_image)
    event_type = item.get("eventType", "")

    processor = PROCESSORS.get(event_type)
    if not processor:
        # Expected and fine: every insert reaches this queue, including the
        # member rows written alongside a space. Only some carry an
        # eventType. Delete rather than retry something we will never handle.
        logger.debug("No processor for eventType=%r - discarding", event_type)
        return

    logger.info("Processing %s for space %s", event_type, item.get("spaceId"))
    processor(item)


def run() -> None:
    logger.info("Provisioning service started, polling %s", _SQS_QUEUE_URL)
    _touch_heartbeat()

    while True:
        try:
            response = _sqs.receive_message(
                QueueUrl=_SQS_QUEUE_URL,
                MaxNumberOfMessages=5,
                WaitTimeSeconds=_POLL_WAIT_SECS,
                VisibilityTimeout=300,
            )

            # Written before any message handling, so a poison message that
            # crashes every attempt still shows a healthy loop - the DLQ is
            # what deals with that, not a restart.
            _touch_heartbeat()

            for message in response.get("Messages", []):
                try:
                    _handle(message)
                    _sqs.delete_message(
                        QueueUrl=_SQS_QUEUE_URL,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                except Exception:
                    logger.exception(
                        "Failed to process message - leaving it queued for retry"
                    )

        except Exception:
            logger.exception("SQS polling error - retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    run()
