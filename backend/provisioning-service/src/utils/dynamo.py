"""
DynamoDB helpers for the provisioning service.
Used to update status and write back provisioned resource ARNs.
"""
import os
from datetime import datetime, timezone

import boto3

_TABLE_NAME = os.environ["DYNAMODB_TABLE"]

# Explicit region: botocore's implicit lookup reads AWS_DEFAULT_REGION rather
# than AWS_REGION, so leaving it out fails in containers that look fine.
_REGION     = os.environ.get("AWS_REGION", "eu-west-1")
_dynamodb   = boto3.resource("dynamodb", region_name=_REGION)
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
