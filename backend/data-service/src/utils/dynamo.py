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
_dynamodb = boto3.resource("dynamodb")
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
