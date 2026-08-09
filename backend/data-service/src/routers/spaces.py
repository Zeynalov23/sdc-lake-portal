"""
Spaces router.
GET   /spaces                    - list all spaces the user can access
GET   /spaces/:id                - get metadata for a specific space
PATCH /spaces/:id/versioning     - toggle versioning on/off
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.utils.auth import get_current_user
from src.utils.authz import SpacePermission, require_space_permission
from src.utils import dynamo, s3 as s3_util

logger = logging.getLogger(__name__)
router = APIRouter()


class VersioningUpdate(BaseModel):
    enabled: bool


@router.get("")
def list_spaces(user: Annotated[dict, Depends(get_current_user)]):
    """Return all spaces for which the user has an active space membership."""
    items = dynamo.get_user_access(user["userId"])

    memberships = [
        item
        for item in items
        if item.get("SK", "").startswith("MEMBER#")
        and item.get("status", "ACTIVE") == "ACTIVE"
    ]

    spaces = []
    for membership in memberships:
        space_id = membership["spaceId"]
        metadata = dynamo.get_space_metadata(space_id)
        if not metadata or metadata.get("status") != "READY":
            continue

        spaces.append({
            "spaceId": space_id,
            "role": membership.get("role"),
            "bucketName": metadata.get("bucketName"),
            "status": metadata.get("status"),
            "tier": metadata.get("tier"),
            "owner": metadata.get("owner"),
            "createdAt": metadata.get("createdAt"),
        })

    return {"spaces": spaces}


@router.get("/{space_id}")
def get_space(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Get space metadata. Any active space role with READ access may view it."""
    membership = require_space_permission(
        user["userId"], space_id, SpacePermission.READ
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    versioning = s3_util.get_bucket_versioning(metadata["bucketName"])

    return {
        "spaceId": space_id,
        "bucketName": metadata["bucketName"],
        "status": metadata["status"],
        "tier": metadata["tier"],
        "owner": metadata["owner"],
        "createdAt": metadata["createdAt"],
        "versioning": versioning,
        "role": membership.get("role"),
    }


@router.patch("/{space_id}/versioning")
def update_versioning(
    space_id: str,
    body: VersioningUpdate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Toggle versioning. Only OWNER and DEPUTY have CONFIGURE permission."""
    require_space_permission(
        user["userId"], space_id, SpacePermission.CONFIGURE
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    s3_util.set_bucket_versioning(metadata["bucketName"], body.enabled)

    return {
        "spaceId": space_id,
        "versioning": "Enabled" if body.enabled else "Suspended",
    }
