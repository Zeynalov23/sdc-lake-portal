"""
DynamoDB read helpers for the data service.
The table uses a single-table model with deterministic PK/SK access paths.
"""
import os

import boto3
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


def get_space_metadata(space_id: str) -> dict | None:
    response = _table.get_item(
        Key={"PK": f"SPACE#{space_id}", "SK": "METADATA"}
    )
    return response.get("Item")


def get_membership(user_id: str, space_id: str) -> dict | None:
    """Return one exact space membership using a strongly bounded key lookup."""
    response = _table.get_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"MEMBER#{user_id}",
        }
    )
    return response.get("Item")


def get_data_product(space_id: str, data_product_id: str) -> dict | None:
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
) -> dict | None:
    """Return exact consumer access for one root-level data product."""
    response = _table.get_item(
        Key={
            "PK": f"SPACE#{space_id}",
            "SK": f"DATAPRODUCT#{data_product_id}#CONSUMER#{user_id}",
        }
    )
    return response.get("Item")
