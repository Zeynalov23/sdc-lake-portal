"""
Space membership.

GET    /spaces/{id}/members            — who has access
POST   /spaces/{id}/members            — add a producer or consumer by email
DELETE /spaces/{id}/members/{user_id}  — remove a member
PUT    /spaces/{id}/deputy             — assign the deputy
DELETE /spaces/{id}/deputy             — clear the deputy

Access is granted by email because that is what an owner knows, but stored
by Entra object id, which never changes. The directory lookup happens here,
once, at grant time - so a later email change cannot silently break access.

Owner and deputy are fields on the space item rather than membership rows.
An attribute holds one value, so "one owner, one deputy" is true by the shape
of the data and does not depend on a check that a concurrent request could
also pass.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.utils import authz, dynamo, graph
from src.utils.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Roles that can be granted through this endpoint. Owner is set at creation
# and deputy has its own endpoint, because both need stronger guarantees than
# a plain put_item.
_GRANTABLE_ROLES = {authz.SpaceRole.PRODUCER.value, authz.SpaceRole.CONSUMER.value}


class MemberCreate(BaseModel):
    email: EmailStr
    role: str


class DeputyAssign(BaseModel):
    email: EmailStr


def _resolve_directory_user(email: str) -> dict:
    """
    Email -> Entra object id. Raises 404 if the person is not in the tenant.

    Deliberately strict: granting access to an address that does not resolve
    would create a row nobody can ever use, and it would look like it worked.
    """
    return graph.find_user_by_email(email)


@router.get("/{space_id}/members")
def list_members(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Everyone with access to the space.

    Any member may see this. Knowing who else is in a space you already
    belong to is not sensitive, and hiding it makes the UI useless.
    """
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.READ
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    members = []
    for row in dynamo.list_space_members(space_id):
        if row.get("status", "ACTIVE") != "ACTIVE":
            continue
        members.append({
            "userId": row.get("userId"),
            "email": row.get("email"),
            "name": row.get("name"),
            "role": str(row.get("role", "")).upper(),
            "createdAt": row.get("createdAt"),
        })

    return {
        "spaceId": space_id,
        "ownerId": metadata.get("ownerOid"),
        "deputyId": metadata.get("deputyOid"),
        "members": members,
    }


@router.post("/{space_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    space_id: str,
    body: MemberCreate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Add a producer or consumer. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.MANAGE_MEMBERS
    )

    role = body.role.upper()
    if role not in _GRANTABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Role must be PRODUCER or CONSUMER. The owner is set when the "
                "space is created, and the deputy has its own endpoint."
            ),
        )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    directory_user = _resolve_directory_user(body.email)
    target_id = directory_user["oid"]

    # Demoting the owner or deputy through this endpoint would leave the
    # metadata field pointing at someone who now holds a lesser role.
    if target_id in (metadata.get("ownerOid"), metadata.get("deputyOid")):
        raise HTTPException(
            status_code=409,
            detail="That user is the owner or deputy; remove that role first",
        )

    dynamo.put_member(
        space_id=space_id,
        user_id=target_id,
        email=directory_user["email"],
        name=directory_user["name"],
        role=role,
    )

    logger.info(
        "Granted %s on %s to %s (by %s)", role, space_id, target_id, user["userId"]
    )

    return {
        "spaceId": space_id,
        "userId": target_id,
        "email": directory_user["email"],
        "role": role,
    }


@router.delete("/{space_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    space_id: str,
    member_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Remove a producer or consumer. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.MANAGE_MEMBERS
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    if member_id == metadata.get("ownerOid"):
        # A space with no owner has nobody who can ever administer it again.
        raise HTTPException(status_code=409, detail="The owner cannot be removed")

    if member_id == metadata.get("deputyOid"):
        raise HTTPException(
            status_code=409,
            detail="That user is the deputy; clear the deputy role first",
        )

    dynamo.delete_member(space_id, member_id)
    logger.info("Removed %s from %s (by %s)", member_id, space_id, user["userId"])


@router.put("/{space_id}/deputy")
def assign_deputy(
    space_id: str,
    body: DeputyAssign,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Assign the deputy. Owner and deputy only.

    A space has at most one deputy, enforced by a conditional write rather
    than by reading first and hoping nothing changed in between.
    """
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.MANAGE_MEMBERS
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    directory_user = _resolve_directory_user(body.email)
    target_id = directory_user["oid"]

    if target_id == metadata.get("ownerOid"):
        raise HTTPException(
            status_code=409, detail="The owner cannot also be the deputy"
        )

    try:
        dynamo.assign_deputy(
            space_id=space_id,
            user_id=target_id,
            email=directory_user["email"],
            name=directory_user["name"],
        )
    except dynamo.DeputyAlreadyAssigned:
        raise HTTPException(
            status_code=409,
            detail="This space already has a deputy; clear the existing one first",
        )

    logger.info(
        "Assigned deputy %s on %s (by %s)", target_id, space_id, user["userId"]
    )

    return {
        "spaceId": space_id,
        "deputyId": target_id,
        "email": directory_user["email"],
    }


@router.delete("/{space_id}/deputy", status_code=status.HTTP_204_NO_CONTENT)
def clear_deputy(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Clear the deputy. Owner and deputy only - a deputy may step down."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.MANAGE_MEMBERS
    )

    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")

    current = metadata.get("deputyOid")
    if not current:
        raise HTTPException(status_code=404, detail="This space has no deputy")

    dynamo.remove_deputy(space_id, current)
    logger.info("Cleared deputy on %s (by %s)", space_id, user["userId"])
