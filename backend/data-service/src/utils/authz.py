"""
Central authorization rules for spaces and data products.

Two levels of access exist:

  * space level    — a member row, covers the whole space
  * product level  — a consumer grant on one staged root-level folder

The rule that makes product-level access safe is that every S3 operation is
scoped to an allowed key prefix. Space members get the prefix "" (everything);
a product consumer gets "{product}/" and nothing else. Callers must go through
`authorize_read`, `authorize_write` or `authorize_list` — those return the
prefixes, and the router applies them to S3.

Since AWS no longer enforces the boundary for us (the pod signs every URL with
its own identity), a bug in this file is a security hole. It is kept small and
explicit for that reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException

from src.utils import dynamo

_ACTIVE = "ACTIVE"


class SpacePermission(str, Enum):
    READ = "read_space"
    WRITE = "write_space"
    CONFIGURE = "configure_space"
    MANAGE_MEMBERS = "manage_members"
    CREATE_DATA_PRODUCT = "create_data_product"
    MANAGE_DATA_PRODUCT_CONSUMERS = "manage_data_product_consumers"


class SpaceRole(str, Enum):
    OWNER = "OWNER"
    DEPUTY = "DEPUTY"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


_ADMIN_PERMISSIONS = {
    SpacePermission.READ,
    SpacePermission.WRITE,
    SpacePermission.CONFIGURE,
    SpacePermission.MANAGE_MEMBERS,
    SpacePermission.CREATE_DATA_PRODUCT,
    SpacePermission.MANAGE_DATA_PRODUCT_CONSUMERS,
}

# Deputy is deliberately the same object as owner rather than a copy of the
# same six permissions. A deputy exists so the space is not blocked while the
# owner is away, so the two must never drift apart.
SPACE_ROLE_PERMISSIONS: dict[str, set[SpacePermission]] = {
    SpaceRole.OWNER.value: _ADMIN_PERMISSIONS,
    SpaceRole.DEPUTY.value: _ADMIN_PERMISSIONS,
    SpaceRole.PRODUCER.value: {
        SpacePermission.READ,
        SpacePermission.WRITE,
    },
    SpaceRole.CONSUMER.value: {
        SpacePermission.READ,
    },
}


@dataclass(frozen=True)
class Access:
    """What the caller may do in one space, and where."""

    scope: str                    # "SPACE" or "DATA_PRODUCT"
    role: str
    prefixes: tuple[str, ...]     # ("",) = whole space
    record: dict                  # the membership or consumer grant

    def covers(self, key: str) -> bool:
        return any(key.startswith(p) for p in self.prefixes)


# ---------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------
def _space_membership(user_id: str, space_id: str) -> dict | None:
    membership = dynamo.get_membership(user_id, space_id)
    if not membership or membership.get("status", _ACTIVE) != _ACTIVE:
        return None

    role = str(membership.get("role", "")).upper()
    if role not in SPACE_ROLE_PERMISSIONS:
        # Unknown role in the data: refuse rather than guess at intent.
        return None

    return membership


def _product_prefixes(user_id: str, space_id: str) -> tuple[dict, ...]:
    grants = dynamo.list_user_product_grants(user_id, space_id)
    return tuple(g for g in grants if g.get("status", _ACTIVE) == _ACTIVE)


def resolve(user_id: str, space_id: str) -> Access:
    """
    Work out the caller's access to a space. Raises 403 if they have none.

    Order matters: a space membership is strictly wider than any product
    grant, so it wins and we do not even look at product grants.
    """
    membership = _space_membership(user_id, space_id)
    if membership:
        return Access(
            scope="SPACE",
            role=str(membership["role"]).upper(),
            prefixes=("",),
            record=membership,
        )

    grants = _product_prefixes(user_id, space_id)
    if grants:
        prefixes = tuple(
            f"{g['dataProductId']}/" for g in grants if g.get("dataProductId")
        )
        if prefixes:
            return Access(
                scope="DATA_PRODUCT",
                role=SpaceRole.CONSUMER.value,
                prefixes=prefixes,
                record=grants[0],
            )

    raise HTTPException(status_code=403, detail="Access denied")


def has_permission(access: Access, permission: SpacePermission) -> bool:
    if access.scope == "DATA_PRODUCT":
        # Product grants are read-only by design, whatever the role says.
        return permission is SpacePermission.READ
    return permission in SPACE_ROLE_PERMISSIONS.get(access.role, set())


# ---------------------------------------------------------------
# Guards — routers use these, never the internals above
# ---------------------------------------------------------------
def require_space_permission(
    user_id: str,
    space_id: str,
    permission: SpacePermission,
) -> dict:
    """
    For space-wide operations that are not tied to one object key:
    versioning, notifications, staging a product, managing members.
    Product-level consumers can never satisfy these.
    """
    access = resolve(user_id, space_id)
    if access.scope != "SPACE" or not has_permission(access, permission):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return access.record


def authorize_read(user_id: str, space_id: str, key: str) -> Access:
    access = resolve(user_id, space_id)
    if not has_permission(access, SpacePermission.READ) or not access.covers(key):
        # 404 rather than 403: confirming that a forbidden path exists tells
        # the caller about data they were never meant to know about.
        raise HTTPException(status_code=404, detail="Not found")
    return access


def authorize_write(user_id: str, space_id: str, key: str) -> Access:
    access = resolve(user_id, space_id)
    if not has_permission(access, SpacePermission.WRITE):
        raise HTTPException(status_code=403, detail="Read-only access")
    if not access.covers(key):
        raise HTTPException(status_code=404, detail="Not found")
    return access


def authorize_list(user_id: str, space_id: str, requested_prefix: str) -> list[str]:
    """
    Which prefixes to actually list, given what the client asked for.

    This is the easiest place to leak data: passing the client's prefix
    straight to S3 lets a product consumer ask for "" and see the whole
    space. So the request is intersected with what the caller is allowed.
    """
    access = resolve(user_id, space_id)
    if not has_permission(access, SpacePermission.READ):
        raise HTTPException(status_code=403, detail="Access denied")

    if access.prefixes == ("",):
        return [requested_prefix]

    if not requested_prefix:
        # Nothing specific asked for: show each product they may read.
        return list(access.prefixes)

    if access.covers(requested_prefix):
        return [requested_prefix]

    raise HTTPException(status_code=404, detail="Not found")


def data_product_of(key: str) -> str | None:
    """
    The root-level folder a key sits in, or None for a file at the root.
    Data products are always root-level folders, so this is the first segment.
    """
    head, sep, _ = key.partition("/")
    return head if sep else None
