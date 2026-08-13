"""
Data products.

A data product is a root-level folder that an owner has deliberately staged
for sharing. Not every folder is one - staging is the act that makes a folder
grantable to people who have no access to the rest of the space.

GET    /spaces/{id}/products                          — staged folders
POST   /spaces/{id}/products                          — stage a folder
DELETE /spaces/{id}/products/{name}                   — unstage and revoke
GET    /spaces/{id}/products/{name}/consumers         — who may read it
POST   /spaces/{id}/products/{name}/consumers         — grant read by email
DELETE /spaces/{id}/products/{name}/consumers/{uid}   — revoke

Consumers granted here are read-only, and confined to that one folder by
authz. They are typically people with no other access to the space at all.
"""
from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from src.utils import authz, dynamo, graph
from src.utils import s3 as s3_util
from src.utils.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# A product name is one path segment: it becomes a key prefix, so a slash
# would let it point at a nested folder and break the "root-level only" rule
# that the prefix check in authz depends on.
_PRODUCT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


class ProductCreate(BaseModel):
    name: str
    description: str | None = Field(default=None, max_length=500)


class ConsumerCreate(BaseModel):
    email: EmailStr


def _validate_product_name(name: str) -> str:
    if not _PRODUCT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail=(
                "A data product name is a single root-level folder: letters, "
                "digits, dot, dash or underscore, no slashes"
            ),
        )
    return name


def _load_product_or_404(space_id: str, name: str) -> dict:
    product = dynamo.get_data_product(space_id, name)
    if not product:
        raise HTTPException(
            status_code=404, detail=f"'{name}' is not a staged data product"
        )
    return product


def _bucket_or_409(space_id: str) -> str:
    metadata = dynamo.get_space_metadata(space_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Space not found")
    if metadata.get("status") != "READY":
        raise HTTPException(status_code=409, detail="Space is not ready yet")
    bucket = metadata.get("bucketName")
    if not bucket:
        raise HTTPException(status_code=500, detail="Space bucket is not configured")
    return bucket


@router.get("/{space_id}/products")
def list_products(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Staged products in this space.

    A product-level consumer sees only the products they hold a grant on -
    listing the rest would tell them what else exists in a space they are not
    a member of.
    """
    access = authz.resolve(user["userId"], space_id)
    products = dynamo.list_data_products(space_id)

    if access.scope == "DATA_PRODUCT":
        visible = {p.rstrip("/") for p in access.prefixes}
        products = [p for p in products if p.get("dataProductId") in visible]

    return {
        "spaceId": space_id,
        "products": [
            {
                "name": p.get("dataProductId"),
                "description": p.get("description"),
                "createdBy": p.get("createdBy"),
                "createdAt": p.get("createdAt"),
            }
            for p in products
        ],
    }


@router.post("/{space_id}/products", status_code=status.HTTP_201_CREATED)
def stage_product(
    space_id: str,
    body: ProductCreate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Stage a root-level folder as a data product. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.CREATE_DATA_PRODUCT
    )

    name = _validate_product_name(body.name)
    bucket = _bucket_or_409(space_id)

    if dynamo.get_data_product(space_id, name):
        raise HTTPException(
            status_code=409, detail=f"'{name}' is already a data product"
        )

    # Staging a folder that does not exist would produce a product nobody can
    # read, and the owner would have no clue why. One object under the prefix
    # is enough - S3 has no real directories.
    listing = s3_util.list_objects(bucket_name=bucket, prefix=f"{name}/", max_keys=1)
    if not listing["objects"]:
        raise HTTPException(
            status_code=404,
            detail=f"No folder '{name}/' exists in this space yet",
        )

    dynamo.put_data_product(
        space_id=space_id,
        data_product_id=name,
        description=body.description,
        created_by=user["userId"],
    )

    logger.info("Staged data product %s in %s by %s", name, space_id, user["userId"])

    return {"spaceId": space_id, "name": name, "description": body.description}


@router.delete("/{space_id}/products/{name}", status_code=status.HTTP_200_OK)
def unstage_product(
    space_id: str,
    name: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Unstage a folder and revoke every grant on it. Owner and deputy only.

    The files are untouched - this removes sharing, not data.
    """
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.CREATE_DATA_PRODUCT
    )
    _load_product_or_404(space_id, name)

    revoked = dynamo.delete_data_product(space_id, name)

    logger.info(
        "Unstaged %s in %s, revoked %d grants (by %s)",
        name, space_id, revoked, user["userId"],
    )

    return {"spaceId": space_id, "name": name, "revokedGrants": revoked}


@router.get("/{space_id}/products/{name}/consumers")
def list_consumers(
    space_id: str,
    name: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Who may read this product. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"],
        space_id,
        authz.SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
    )
    _load_product_or_404(space_id, name)

    return {
        "spaceId": space_id,
        "name": name,
        "consumers": [
            {
                "userId": c.get("userId"),
                "email": c.get("email"),
                "name": c.get("name"),
                "createdAt": c.get("createdAt"),
            }
            for c in dynamo.list_data_product_consumers(space_id, name)
            if c.get("status", "ACTIVE") == "ACTIVE"
        ],
    }


@router.post(
    "/{space_id}/products/{name}/consumers",
    status_code=status.HTTP_201_CREATED,
)
def add_consumer(
    space_id: str,
    name: str,
    body: ConsumerCreate,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Grant one person read access to one staged folder. Owner and deputy only.

    This is the point of staging: the grantee usually has no access to the
    space at all, and gains exactly this prefix and nothing else.
    """
    authz.require_space_permission(
        user["userId"],
        space_id,
        authz.SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
    )
    _load_product_or_404(space_id, name)

    directory_user = graph.find_user_by_email(body.email)
    target_id = directory_user["oid"]

    # A space member already reads the whole space, so a product grant would
    # be dead data that implies a restriction that is not real.
    existing = dynamo.get_membership(target_id, space_id)
    metadata = dynamo.get_space_metadata(space_id) or {}
    if existing or target_id in (metadata.get("ownerOid"), metadata.get("deputyOid")):
        raise HTTPException(
            status_code=409,
            detail="That user is already a member of the space",
        )

    dynamo.put_data_product_consumer(
        space_id=space_id,
        data_product_id=name,
        user_id=target_id,
        email=directory_user["email"],
        name=directory_user["name"],
    )

    logger.info(
        "Granted %s/%s to %s (by %s)", space_id, name, target_id, user["userId"]
    )

    return {
        "spaceId": space_id,
        "name": name,
        "userId": target_id,
        "email": directory_user["email"],
    }


@router.delete(
    "/{space_id}/products/{name}/consumers/{consumer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_consumer(
    space_id: str,
    name: str,
    consumer_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Revoke one grant. Owner and deputy only."""
    authz.require_space_permission(
        user["userId"],
        space_id,
        authz.SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
    )
    _load_product_or_404(space_id, name)

    dynamo.delete_data_product_consumer(space_id, name, consumer_id)
    logger.info(
        "Revoked %s/%s from %s (by %s)", space_id, name, consumer_id, user["userId"]
    )
