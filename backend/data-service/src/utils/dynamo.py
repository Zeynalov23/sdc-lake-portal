"""
DynamoDB helpers for the data service.
All reads — no writes except status polling.
"""
import os

import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ["DYNAMODB_TABLE"]
_dynamodb   = boto3.resource("dynamodb")
_table      = _dynamodb.Table(_TABLE_NAME)


def get_user_spaces(user_id: str) -> list[dict]:
    """
    Returns all spaces a user has access to.
    Includes owned spaces and guest spaces.
    """
    response = _table.query(
        IndexName              = "userId-index",
        KeyConditionExpression = Key("userId").eq(user_id),
    )
    return response.get("Items", [])


def get_space_metadata(space_id: str) -> dict | None:
    response = _table.get_item(
        Key={"PK": f"SPACE#{space_id}", "SK": "METADATA"}
    )
    return response.get("Item")


def get_membership(user_id: str, space_id: str) -> dict | None:
    """
    Get a specific membership record to retrieve the access point ARN.
    SK is keyed by role ("writer"/"reader"), so this can't be a direct
    get_item without knowing the role — query by userId and filter, same
    as get_user_spaces. Assumes one membership row per (user, space).
    """
    response = _table.query(
        IndexName              = "userId-index",
        KeyConditionExpression = Key("userId").eq(user_id),
    )
    for item in response.get("Items", []):
        if item.get("spaceId") == space_id:
            return item
    return None
