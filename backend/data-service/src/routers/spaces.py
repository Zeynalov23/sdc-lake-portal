"""
Spaces router.
GET /spaces         — list all spaces the user has access to
GET /spaces/:id     — get metadata for a specific space
PATCH /spaces/:id   — toggle versioning on/off
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.utils.auth   import get_current_user
from src.utils        import dynamo, s3 as s3_util

logger = APIRouter()
router = APIRouter()


class VersioningUpdate(BaseModel):
    enabled: bool


@router.get("")
def list_spaces(user: Annotated[dict, Depends(get_current_user)]):
    """
    Returns all spaces the user has access to, grouped by their source role.
    Frontend uses this to populate the space picker.
    """
    user_id = user["userId"]

    items = dynamo.get_user_spaces(user_id)

    # userId-index returns both membership rows (PK=USER#...) and space
    # metadata rows that also carry userId=ownerId (PK=SPACE#...). DynamoDB
    # always projects base-table PK/SK into GSI results, so this filter is
    # safe and keeps metadata rows from being treated as memberships.
    relevant = [
        m for m in items
        if m.get("PK", "").startswith("USER#")
        and m.get("status") == "READY"
    ]

    spaces = []
    for membership in relevant:
        space_id = membership["spaceId"]
        metadata = dynamo.get_space_metadata(space_id)
        if not metadata:
            continue

        spaces.append({
            "spaceId":        space_id,
            "type":           membership.get("type", "OWNER"),
            "role":           membership.get("role", "writer"),
            "accessPointArn": membership.get("accessPointArn"),
            "bucketName":     metadata.get("bucketName"),
            "status":         metadata.get("status"),
            "tier":           metadata.get("tier"),
            "createdAt":      metadata.get("createdAt"),
        })

    return {"spaces": spaces}


@router.get("/{space_id}")
def get_space(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Get metadata for a specific space including versioning status."""
    user_id = user["userId"]

    # Verify user has access to this space
    membership = dynamo.get_membership(user_id, space_id)
    if not membership or membership.get("status") != "READY":
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    versioning = s3_util.get_bucket_versioning(metadata["bucketName"])

    return {
        "spaceId":        space_id,
        "bucketName":     metadata["bucketName"],
        "status":         metadata["status"],
        "tier":           metadata["tier"],
        "owner":          metadata["owner"],
        "createdAt":      metadata["createdAt"],
        "versioning":     versioning,
        "role":           membership.get("role"),
        "type":           membership.get("type"),
        "accessPointArn": membership.get("accessPointArn"),
    }


@router.patch("/{space_id}/versioning")
def update_versioning(
    space_id: str,
    body: VersioningUpdate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Toggle versioning on/off. Writers only."""
    user_id = user["userId"]

    membership = dynamo.get_membership(user_id, space_id)
    if not membership or membership.get("status") != "READY":
        raise HTTPException(status_code=403, detail="Access denied")

    if membership.get("role") != "writer":
        raise HTTPException(status_code=403, detail="Only writers can change versioning")

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    s3_util.set_bucket_versioning(metadata["bucketName"], body.enabled)

    return {
        "spaceId":    space_id,
        "versioning": "Enabled" if body.enabled else "Suspended",
    }
