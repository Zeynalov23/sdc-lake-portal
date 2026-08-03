"""
DynamoDB helpers for the provisioning service.
Used to update status and write back provisioned resource ARNs.
"""
import os
from datetime import datetime, timezone

import boto3

_TABLE_NAME = os.environ["DYNAMODB_TABLE"]
_dynamodb   = boto3.resource("dynamodb")
_table      = _dynamodb.Table(_TABLE_NAME)


def update_status(pk: str, sk: str, status: str, extra: dict = None) -> None:
    """Update the status of a record and optionally add extra attributes."""
    now = datetime.now(timezone.utc).isoformat()

    update_expr   = "SET #s = :s, updatedAt = :u"
    expr_names    = {"#s": "status"}
    expr_values   = {":s": status, ":u": now}

    if extra:
        for i, (key, value) in enumerate(extra.items()):
            placeholder = f":extra{i}"
            update_expr += f", {key} = {placeholder}"
            expr_values[placeholder] = value

    _table.update_item(
        Key                       = {"PK": pk, "SK": sk},
        UpdateExpression          = update_expr,
        ExpressionAttributeNames  = expr_names,
        ExpressionAttributeValues = expr_values,
    )


def put_item(item: dict) -> None:
    _table.put_item(Item=item)
