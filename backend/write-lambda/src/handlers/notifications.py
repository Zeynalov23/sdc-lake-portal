"""
POST /notifications handler
Creates an S3 event notification on a space bucket.
Provisioning service wires up the SNS topic and S3 config.

Expected body:
{
    "spaceId":    "analytics-eu",
    "requesterId": "entra-object-id",
    "events":     ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],
    "targetArn":  "arn:aws:sqs:eu-west-1:123:my-queue"  (SQS or SNS ARN)
    "prefix":     "raw/"   (optional — only notify on this prefix)
}
"""
import uuid
from datetime import datetime, timezone

from src.utils import dynamo, validation
from src.utils.response import created, bad_request


def handle_create(body: dict) -> dict:
    validation.require_fields(body, [
        "spaceId",
        "requesterId",
        "events",
        "targetArn",
    ])
    validation.validate_events(body["events"])

    space_id     = body["spaceId"]
    requester_id = body["requesterId"]
    events       = body["events"]
    target_arn   = body["targetArn"]
    prefix       = body.get("prefix", "")

    # Verify space exists and is ready
    space = dynamo.get_item(f"SPACE#{space_id}", "METADATA")
    if not space:
        return bad_request(f"Space '{space_id}' does not exist")
    if space.get("status") != "READY":
        return bad_request(f"Space '{space_id}' is not yet ready")

    # Verify requester has write access to this space
    membership = dynamo.get_item(
        f"USER#{requester_id}",
        f"SPACE#{space_id}#ROLE#writer",
    )
    if not membership or membership.get("role") != "writer":
        return bad_request("Only space writers can create notifications")

    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    dynamo.put_item({
        "PK":             f"SPACE#{space_id}",
        "SK":             f"NOTIFICATION#{notification_id}",
        "spaceId":        space_id,
        "notificationId": notification_id,
        "requesterId":    requester_id,
        "events":         events,
        "targetArn":      target_arn,
        "prefix":         prefix,
        "status":         "PENDING",
        "eventType":      "CREATE_NOTIFICATION",
        "requestId":      notification_id,
        "createdAt":      now,
        "updatedAt":      now,
        "userId":         requester_id,
    })

    return created({
        "message":        "Notification creation requested",
        "notificationId": notification_id,
        "spaceId":        space_id,
        "status":         "PENDING",
    })
