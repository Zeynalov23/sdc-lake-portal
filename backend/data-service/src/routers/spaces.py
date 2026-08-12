"""
Spaces router.

POST   /spaces                     — request a new space
GET    /spaces                     — spaces the caller can see
GET    /spaces/{id}                — one space
PATCH  /spaces/{id}/versioning     — toggle bucket versioning

Creating a space is asynchronous. This endpoint only writes the request to
DynamoDB with status PENDING; the stream carries it to the provisioning
service, which creates the bucket and flips the status to READY. The API
stays fast and the slow AWS calls happen where they can be retried.
"""
from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.utils import authz, dynamo
from src.utils import s3 as s3_util
from src.utils.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# The space id becomes part of an S3 bucket name, so it has to satisfy the
# stricter of the two rule sets: lowercase letters, digits and hyphens only.
_SPACE_ID_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{1,38})[a-z0-9]$")
_TIERS = {"standard", "premium"}


class SpaceCreate(BaseModel):
    space_id: str = Field(alias="spaceId")
    tier: str = "standard"

    model_config = {"populate_by_name": True}


class VersioningUpdate(BaseModel):
    enabled: bool


def _validate_space_id(space_id: str) -> str:
    if not _SPACE_ID_PATTERN.match(space_id):
        raise HTTPException(
            status_code=400,
            detail=(
                "Space id must be 3-40 characters, lowercase letters, digits "
                "and hyphens, and may not start or end with a hyphen"
            ),
        )
    return space_id


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_space(
    body: SpaceCreate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Request a new space. The caller becomes its owner.

    The metadata item and the owner's member row are written in a single
    transaction, so a space can never exist without an owner. The condition
    on the metadata item makes a duplicate space id fail at the database
    rather than in a check-then-write race.
    """
    space_id = _validate_space_id(body.space_id)

    if body.tier not in _TIERS:
        raise HTTPException(
            status_code=400, detail=f"Tier must be one of: {', '.join(sorted(_TIERS))}"
        )

    try:
        dynamo.create_space(
            space_id=space_id,
            owner_id=user["userId"],
            owner_email=user.get("email"),
            tier=body.tier,
        )
    except dynamo.SpaceAlreadyExists:
        raise HTTPException(
            status_code=409, detail=f"Space '{space_id}' already exists"
        )

    logger.info("Space %s requested by %s", space_id, user["userId"])

    # 202, not 201: the space does not exist in AWS yet. The client polls
    # GET /spaces/{id} until status is READY.
    return {
        "spaceId": space_id,
        "status": "PENDING",
        "message": "Space creation requested",
    }


@router.get("")
def list_spaces(user: Annotated[dict, Depends(get_current_user)]):
    """
    Every space the caller can see, whether through space membership or a
    data-product grant. Used to populate the space picker.
    """
    user_id = user["userId"]
    spaces = []

    for record in dynamo.get_user_access(user_id):
        if record.get("status", "ACTIVE") != "ACTIVE":
            continue

        space_id = _space_id_from_record(record)
        if not space_id:
            continue

        metadata = dynamo.get_space_metadata(space_id)
        if not metadata:
            # Grant rows can outlive a deleted space; skip rather than fail
            # the whole listing.
            continue

        is_product_grant = "#CONSUMER#" in str(record.get("SK", ""))

        spaces.append({
            "spaceId": space_id,
            "scope": "DATA_PRODUCT" if is_product_grant else "SPACE",
            "role": str(record.get("role", "")).upper(),
            "dataProductId": record.get("dataProductId"),
            "status": metadata.get("status"),
            "tier": metadata.get("tier"),
            "owner": metadata.get("ownerEmail"),
            "createdAt": metadata.get("createdAt"),
        })

    return {"spaces": spaces}


@router.get("/{space_id}")
def get_space(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """One space, with the caller's effective access to it."""
    access = authz.resolve(user["userId"], space_id)

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    response = {
        "spaceId": space_id,
        "status": metadata.get("status"),
        "tier": metadata.get("tier"),
        "owner": metadata.get("ownerEmail"),
        "createdAt": metadata.get("createdAt"),
        "scope": access.scope,
        "role": access.role,
        "prefixes": list(access.prefixes),
    }

    # Versioning is an admin detail and needs an extra S3 call, so only look
    # it up for someone who could actually change it.
    if authz.has_permission(access, authz.SpacePermission.CONFIGURE):
        bucket_name = metadata.get("bucketName")
        if bucket_name:
            response["versioning"] = s3_util.get_bucket_versioning(bucket_name)

    return response


@router.patch("/{space_id}/versioning")
def update_versioning(
    space_id: str,
    body: VersioningUpdate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Toggle bucket versioning. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.CONFIGURE
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata or metadata.get("status") != "READY":
        raise HTTPException(status_code=409, detail="Space is not ready yet")

    bucket_name = metadata.get("bucketName")
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Space bucket is not configured")

    s3_util.set_bucket_versioning(bucket_name, body.enabled)

    return {
        "spaceId": space_id,
        "versioning": "Enabled" if body.enabled else "Suspended",
    }


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _space_id_from_record(record: dict) -> str | None:
    """
    Grant rows carry spaceId, but fall back to parsing the partition key so a
    row written without that attribute still resolves instead of vanishing
    silently from the listing.
    """
    if record.get("spaceId"):
        return str(record["spaceId"])

    pk = str(record.get("PK", ""))
    return pk[len("SPACE#"):] if pk.startswith("SPACE#") else None
