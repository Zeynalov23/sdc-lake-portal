"""Integration-ish tests for the space lifecycle against a mocked DynamoDB."""
import os
import boto3
import pytest
from moto import mock_aws

TABLE = os.environ.setdefault("DYNAMODB_TABLE", "sdc-lake-test-resources")


@pytest.fixture
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="eu-west-1")
        t = ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                       {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "userId-index",
                "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        import importlib
        from src.utils import dynamo
        importlib.reload(dynamo)
        yield t


def test_create_space_writes_both_items(table):
    from src.utils import dynamo
    dynamo.create_space("finance", "alice", "alice@x.com", "standard")
    meta = dynamo.get_space_metadata("finance")
    member = dynamo.get_membership("alice", "finance")
    assert meta["status"] == "PENDING" and meta["ownerOid"] == "alice"
    assert member["role"] == "OWNER"


def test_duplicate_space_id_is_rejected(table):
    from src.utils import dynamo
    dynamo.create_space("finance", "alice", "a@x.com", "standard")
    with pytest.raises(dynamo.SpaceAlreadyExists):
        dynamo.create_space("finance", "bob", "b@x.com", "standard")


def test_owner_appears_in_user_access(table):
    from src.utils import dynamo
    dynamo.create_space("finance", "alice", "a@x.com", "standard")
    rows = dynamo.get_user_access("alice")
    assert any(r["SK"] == "MEMBER#alice" for r in rows)
