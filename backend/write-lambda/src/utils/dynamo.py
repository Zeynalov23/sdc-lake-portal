"""
DynamoDB client and helpers.
Table name comes from environment variable set by Terraform.
"""
import os
import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ["DYNAMODB_TABLE"]
_dynamodb   = boto3.resource("dynamodb")
_table      = _dynamodb.Table(_TABLE_NAME)


def put_item(item: dict) -> None:
    """Write a new item. Raises if PK+SK already exists."""
    _table.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(PK)",
    )


def get_item(pk: str, sk: str) -> dict | None:
    response = _table.get_item(Key={"PK": pk, "SK": sk})
    return response.get("Item")


def query_by_user(user_id: str) -> list[dict]:
    response = _table.query(
        IndexName="userId-index",
        KeyConditionExpression=Key("userId").eq(user_id),
    )
    return response.get("Items", [])


def update_status(pk: str, sk: str, status: str) -> None:
    _table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )
