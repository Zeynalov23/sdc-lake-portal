"""
DynamoDB read helpers for the data service.
The table uses a single-table model with deterministic PK/SK access paths.
"""
import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ["DYNAMODB_TABLE"]

# region_name is passed explicitly rather than left to the environment.
# botocore's implicit lookup reads AWS_DEFAULT_REGION, not AWS_REGION, which
# is an easy way to get NoRegionError in a container that looks correctly
# configured. Being explicit removes the ambiguity everywhere this runs.
_REGION = os.environ.get("AWS_REGION", "eu-west-1")
_dynamodb = boto3.resource("dynamodb", region_name=_REGION)
_table = _dynamodb.Table(_TABLE_NAME)


def get_user_access(user_id: str) -> list[dict]:
    """Return all space and data-product access records for a user."""
    response = _table.query(
        IndexName="userId-index",
        KeyConditionExpression=Key("userId").eq(user_id),
    )
    return response.get("Items", [])


def get_user_spaces(user_id: str) -> list[dict]:
    """Backward-compatible alias used by the current spaces router."""
    return get_user_access(user_id)


def get_space_metadata(space_id: str) -> Optional[dict]:
    response = _table.get_item(
        Key={"PK": f"SPACE#{space_id}", "SK": "METADATA"}
    )
    return response.get("Item")


def get_membership(user_id: str, space_id: str) -> Optional[dict]:
    """Return one exact space membership using a strongly bounded key lookup."""
    response = _table.get_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"MEMBER#{user_id}",
        }
    )
    return response.get("Item")


def get_data_product(space_id: str, data_product_id: str) -> Optional[dict]:
    response = _table.get_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}",
        }
    )
    return response.get("Item")


def get_data_product_consumer(
    user_id: str,
    space_id: str,
    data_product_id: str,
) -> Optional[dict]:
    """Return exact consumer access for one root-level data product."""
    response = _table.get_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}#CONSUMER#{user_id}",
        }
    )
    return response.get("Item")


def list_user_product_grants(user_id: str, space_id: str) -> list:
    """
    Every active data-product consumer grant a user holds inside one space.

    The consumer SK is DATAPRODUCT#{id}#CONSUMER#{user}, so it cannot be
    filtered by user with begins_with. We go through the userId GSI instead
    and narrow in code. Fine at this scale: a user holds few grants. If that
    stops being true, add a sort key to the GSI rather than scanning more.
    """
    response = _table.query(
        IndexName="userId-index",
        KeyConditionExpression=Key("userId").eq(user_id),
    )
    wanted_pk = f"SPACE#{space_id}"
    return [
        item
        for item in response.get("Items", [])
        if item.get("PK") == wanted_pk
        and "#CONSUMER#" in str(item.get("SK", ""))
    ]


class SpaceAlreadyExists(Exception):
    """Raised when a space id is taken. Surfaced by the router as a 409."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_space(
    space_id: str,
    owner_id: str,
    owner_email: Optional[str],
    tier: str,
) -> None:
    """
    Write the space request and its owner membership in one transaction.

    Two invariants come from the database rather than from application code:

      * attribute_not_exists(PK) on the metadata item means a duplicate space
        id fails atomically, with no check-then-write race between requests
      * both items are written or neither is, so a space can never exist
        without an owner, and an orphan member row can never point at a space
        that was not created

    ownerOid is stored on the metadata item as well as on the member row.
    That is deliberate duplication: an attribute holds exactly one value, so
    "one owner" is enforced by the shape of the data, while the member row
    keeps permission lookups and member listing uniform. The transaction is
    what keeps the two copies honest.
    """
    now = _now()
    client = _table.meta.client

    try:
        client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": _TABLE_NAME,
                        "Item": {
                            "PK": f"SPACE#{space_id}",
                            "SK": "METADATA",
                            "spaceId": space_id,
                            "ownerOid": owner_id,
                            "ownerEmail": owner_email,
                            "tier": tier,
                            "status": "PENDING",
                            "eventType": "CREATE_SPACE",
                            "createdAt": now,
                            "updatedAt": now,
                        },
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
                {
                    "Put": {
                        "TableName": _TABLE_NAME,
                        "Item": {
                            "PK": f"SPACE#{space_id}",
                            "SK": f"MEMBER#{owner_id}",
                            "spaceId": space_id,
                            "userId": owner_id,
                            "email": owner_email,
                            "role": "OWNER",
                            "status": "ACTIVE",
                            "createdAt": now,
                            "updatedAt": now,
                        },
                    }
                },
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            reasons = e.response.get("CancellationReasons", [])
            if any(r.get("Code") == "ConditionalCheckFailed" for r in reasons):
                raise SpaceAlreadyExists(space_id) from e
        raise


class DeputyAlreadyAssigned(Exception):
    """Raised when a space already has a deputy. Surfaced as a 409."""


def list_space_members(space_id: str) -> list:
    """
    Every membership row for a space. Does not include the owner and deputy
    fields on the metadata item, which the router merges in - they are the
    source of truth for who holds those two roles.
    """
    response = _table.query(
        KeyConditionExpression=Key("PK").eq(f"SPACE#{space_id}")
        & Key("SK").begins_with("MEMBER#"),
    )
    return response.get("Items", [])


def put_member(
    space_id: str,
    user_id: str,
    email: Optional[str],
    name: Optional[str],
    role: str,
) -> None:
    """
    Add or update a producer/consumer membership.

    Owner and deputy are not written through here: they live on the metadata
    item so that "exactly one of each" is enforced by the shape of the data.
    """
    now = _now()
    _table.put_item(
        Item={
            "PK": f"SPACE#{space_id}",
            "SK": f"MEMBER#{user_id}",
            "spaceId": space_id,
            "userId": user_id,
            "email": email,
            "name": name,
            "role": role,
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
    )


def delete_member(space_id: str, user_id: str) -> None:
    _table.delete_item(
        Key={"PK": f"SPACE#{space_id}", "SK": f"MEMBER#{user_id}"}
    )


def assign_deputy(
    space_id: str,
    user_id: str,
    email: Optional[str],
    name: Optional[str],
) -> None:
    """
    Make a user the deputy of a space.

    Two writes in one transaction: deputyOid on the metadata item, and the
    membership row that keeps permission lookups and member listing uniform.

    The condition attribute_not_exists(deputyOid) is what enforces "at most
    one deputy". Two concurrent requests cannot both succeed, because the
    second one fails the condition at the database rather than after a read
    that was already stale by the time it was used.
    """
    now = _now()
    client = _table.meta.client

    try:
        client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": _TABLE_NAME,
                        "Key": {"PK": f"SPACE#{space_id}", "SK": "METADATA"},
                        "UpdateExpression": "SET deputyOid = :oid, updatedAt = :now",
                        "ConditionExpression": "attribute_not_exists(deputyOid)",
                        "ExpressionAttributeValues": {":oid": user_id, ":now": now},
                    }
                },
                {
                    "Put": {
                        "TableName": _TABLE_NAME,
                        "Item": {
                            "PK": f"SPACE#{space_id}",
                            "SK": f"MEMBER#{user_id}",
                            "spaceId": space_id,
                            "userId": user_id,
                            "email": email,
                            "name": name,
                            "role": "DEPUTY",
                            "status": "ACTIVE",
                            "createdAt": now,
                            "updatedAt": now,
                        },
                    }
                },
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            reasons = e.response.get("CancellationReasons", [])
            if any(r.get("Code") == "ConditionalCheckFailed" for r in reasons):
                raise DeputyAlreadyAssigned(space_id) from e
        raise


def remove_deputy(space_id: str, user_id: str) -> None:
    """
    Clear the deputy. Both writes again, so the field and the membership row
    can never disagree about who holds the role.
    """
    now = _now()
    client = _table.meta.client

    client.transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": _TABLE_NAME,
                    "Key": {"PK": f"SPACE#{space_id}", "SK": "METADATA"},
                    "UpdateExpression": "REMOVE deputyOid SET updatedAt = :now",
                    # Only clear the deputy we were asked to clear: without
                    # this, a stale request could remove a different person
                    # who was assigned in the meantime.
                    "ConditionExpression": "deputyOid = :oid",
                    "ExpressionAttributeValues": {":oid": user_id, ":now": now},
                }
            },
            {
                "Delete": {
                    "TableName": _TABLE_NAME,
                    "Key": {"PK": f"SPACE#{space_id}", "SK": f"MEMBER#{user_id}"},
                }
            },
        ]
    )


# ---------------------------------------------------------------
# Data products
#
# A data product is a root-level folder an owner has deliberately staged for
# sharing. Not every folder is one: staging is the act that makes a folder
# grantable to people who have no access to the rest of the space.
# ---------------------------------------------------------------
def put_data_product(
    space_id: str,
    data_product_id: str,
    description: Optional[str],
    created_by: str,
) -> None:
    now = _now()
    _table.put_item(
        Item={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}",
            "spaceId": space_id,
            "dataProductId": data_product_id,
            "description": description,
            "createdBy": created_by,
            "createdAt": now,
            "updatedAt": now,
        }
    )


def list_data_products(space_id: str) -> list:
    """
    Staged products only - the SK prefix excludes consumer grants, whose keys
    continue past the product id with #CONSUMER#.
    """
    response = _table.query(
        KeyConditionExpression=Key("PK").eq(f"SPACE#{space_id}")
        & Key("SK").begins_with("DATAPRODUCT#"),
    )
    return [
        item for item in response.get("Items", [])
        if "#CONSUMER#" not in str(item.get("SK", ""))
    ]


def list_data_product_consumers(space_id: str, data_product_id: str) -> list:
    response = _table.query(
        KeyConditionExpression=Key("PK").eq(f"SPACE#{space_id}")
        & Key("SK").begins_with(f"DATAPRODUCT#{data_product_id}#CONSUMER#"),
    )
    return response.get("Items", [])


def put_data_product_consumer(
    space_id: str,
    data_product_id: str,
    user_id: str,
    email: Optional[str],
    name: Optional[str],
) -> None:
    """
    Grant one user read access to one staged folder.

    userId is set because the GSI keys on it: that is how a consumer's grants
    are found when they list a space they are otherwise not a member of.
    """
    now = _now()
    _table.put_item(
        Item={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}#CONSUMER#{user_id}",
            "spaceId": space_id,
            "dataProductId": data_product_id,
            "userId": user_id,
            "email": email,
            "name": name,
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
    )


def delete_data_product_consumer(
    space_id: str,
    data_product_id: str,
    user_id: str,
) -> None:
    _table.delete_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}#CONSUMER#{user_id}",
        }
    )


def delete_data_product(space_id: str, data_product_id: str) -> int:
    """
    Unstage a folder and revoke every grant on it. Returns how many grants
    were revoked.

    The cascade is the security-relevant part. Consumer grants are what
    authz turns into an allowed key prefix, and it does not re-check that the
    product is still staged - so a grant left behind after unstaging would
    keep working. Deleting the product row alone would silently leave access
    in place while the UI showed the folder as no longer shared.
    """
    consumers = list_data_product_consumers(space_id, data_product_id)

    with _table.batch_writer() as batch:
        for consumer in consumers:
            batch.delete_item(Key={"PK": consumer["PK"], "SK": consumer["SK"]})
        batch.delete_item(
            Key={
                "PK": f"SPACE#{space_id}",
                "SK": f"DATAPRODUCT#{data_product_id}",
            }
        )

    return len(consumers)
