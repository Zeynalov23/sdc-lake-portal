"""Central authorization rules for spaces and data products."""
from enum import StrEnum

from fastapi import HTTPException

from src.utils import dynamo


class SpacePermission(StrEnum):
    READ = "read_space"
    WRITE = "write_space"
    CONFIGURE = "configure_space"
    MANAGE_MEMBERS = "manage_members"
    CREATE_DATA_PRODUCT = "create_data_product"
    MANAGE_DATA_PRODUCT_CONSUMERS = "manage_data_product_consumers"


SPACE_ROLE_PERMISSIONS: dict[str, set[SpacePermission]] = {
    "OWNER": {
        SpacePermission.READ,
        SpacePermission.WRITE,
        SpacePermission.CONFIGURE,
        SpacePermission.MANAGE_MEMBERS,
        SpacePermission.CREATE_DATA_PRODUCT,
        SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
    },
    "DEPUTY": {
        SpacePermission.READ,
        SpacePermission.WRITE,
        SpacePermission.CONFIGURE,
        SpacePermission.MANAGE_MEMBERS,
        SpacePermission.CREATE_DATA_PRODUCT,
        SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
    },
    "DEVELOPER": {
        SpacePermission.READ,
        SpacePermission.WRITE,
        SpacePermission.CREATE_DATA_PRODUCT,
    },
    "CONSUMER": {
        SpacePermission.READ,
    },
}


def require_space_permission(
    user_id: str,
    space_id: str,
    permission: SpacePermission,
) -> dict:
    """Return the membership if the user has the requested space permission."""
    membership = dynamo.get_membership(user_id, space_id)
    if not membership or membership.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(status_code=403, detail="Access denied")

    role = str(membership.get("role", "")).upper()
    if permission not in SPACE_ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return membership


def require_data_product_read(
    user_id: str,
    space_id: str,
    data_product_id: str,
) -> dict:
    """
    Allow data-product reads through either space-wide READ permission or an
    exact consumer grant for the requested root-level data product.
    """
    membership = dynamo.get_membership(user_id, space_id)
    if membership and membership.get("status", "ACTIVE") == "ACTIVE":
        role = str(membership.get("role", "")).upper()
        if SpacePermission.READ in SPACE_ROLE_PERMISSIONS.get(role, set()):
            return {"scope": "SPACE", "membership": membership}

    consumer = dynamo.get_data_product_consumer(
        user_id=user_id,
        space_id=space_id,
        data_product_id=data_product_id,
    )
    if consumer and consumer.get("status", "ACTIVE") == "ACTIVE":
        return {"scope": "DATA_PRODUCT", "membership": consumer}

    raise HTTPException(status_code=403, detail="Access denied")


def require_data_product_write(
    user_id: str,
    space_id: str,
) -> dict:
    """Writing into a data product always requires space-level write access."""
    return require_space_permission(
        user_id=user_id,
        space_id=space_id,
        permission=SpacePermission.WRITE,
    )
