"""
POST /access handler
Requests guest access to another space.
Creates a PENDING access record — provisioning service
creates the S3 access point on the target bucket.

Expected body:
{
    "requesterId":    "entra-object-id of requesting user",
    "requesterRole":  "space-analytics-eu-gw",
    "targetSpaceId":  "marketing-data",
    "role":           "reader"
}
"""
import uuid
from datetime import datetime, timezone

from src.utils import dynamo, validation
from src.utils.response import created, bad_request


def handle_create(body: dict) -> dict:
    validation.require_fields(body, [
        "requesterId",
        "requesterRole",
        "targetSpaceId",
        "role",
    ])
    validation.validate_role(body["role"])

    requester_id   = body["requesterId"]
    requester_role = body["requesterRole"]
    target_space   = body["targetSpaceId"]
    role           = body["role"]

    # Verify target space exists and is active
    target = dynamo.get_item(f"SPACE#{target_space}", "METADATA")
    if not target:
        return bad_request(f"Space '{target_space}' does not exist")
    if target.get("status") != "READY":
        return bad_request(f"Space '{target_space}' is not yet ready")

    # Check access not already granted
    sk = f"SPACE#{target_space}#ROLE#{requester_role}"
    existing = dynamo.get_item(f"USER#{requester_id}", sk)
    if existing:
        return bad_request(
            f"Access to '{target_space}' already exists or is pending"
        )

    now = datetime.now(timezone.utc).isoformat()

    dynamo.put_item({
        "PK":            f"USER#{requester_id}",
        "SK":            sk,
        "userId":        requester_id,
        "spaceId":       target_space,
        "type":          "GUEST",
        "role":          role,
        "sourceRole":    requester_role,
        "status":        "PENDING",
        "eventType":     "CREATE_ACCESS",
        "requestId":     str(uuid.uuid4()),
        "createdAt":     now,
        "updatedAt":     now,
    })

    return created({
        "message":      f"Access to '{target_space}' requested",
        "targetSpaceId": target_space,
        "role":          role,
        "status":        "PENDING",
    })
