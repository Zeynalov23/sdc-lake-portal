"""
POST /spaces handler.
Creates a new space request in DynamoDB with PENDING status.
Provisioning service picks it up via DynamoDB Streams -> SQS.

Expected body:
{
    "spaceId": "analytics-eu",
    "owner":   "jan@siemens.com",
    "ownerId": "entra-object-id",
    "tier":    "standard" | "premium",
    "region":  "eu-west-1"   (optional, defaults to eu-west-1)
}
"""
import os
import uuid
from datetime import datetime, timezone

from src.utils import dynamo, validation
from src.utils.response import created, bad_request


_REGION = os.environ.get("AWS_REGION", "eu-west-1")


def handle_create(body: dict) -> dict:
    validation.require_fields(body, ["spaceId", "owner", "ownerId", "tier"])
    validation.validate_space_name(body["spaceId"])
    validation.validate_tier(body["tier"])

    space_id = body["spaceId"]
    owner_id = body["ownerId"]
    region = body.get("region", _REGION)

    existing = dynamo.get_item(f"SPACE#{space_id}", "METADATA")
    if existing:
        return bad_request(f"Space '{space_id}' already exists")

    now = datetime.now(timezone.utc).isoformat()

    dynamo.put_item({
        "PK": f"SPACE#{space_id}",
        "SK": "METADATA",
        "spaceId": space_id,
        "owner": body["owner"],
        "ownerId": owner_id,
        "tier": body["tier"],
        "region": region,
        "status": "PENDING",
        "eventType": "CREATE_SPACE",
        "requestId": str(uuid.uuid4()),
        "createdAt": now,
        "updatedAt": now,
    })

    # Authorization is modeled under the space partition. The owner gets a
    # regular membership record with the OWNER role instead of a special
    # writer IAM role / Cognito mapping.
    dynamo.put_item({
        "PK": f"SPACE#{space_id}",
        "SK": f"MEMBER#{owner_id}",
        "userId": owner_id,
        "spaceId": space_id,
        "role": "OWNER",
        "status": "PENDING",
        "createdBy": owner_id,
        "createdAt": now,
        "updatedAt": now,
    })

    return created({
        "message": f"Space '{space_id}' creation requested",
        "spaceId": space_id,
        "status": "PENDING",
    })
