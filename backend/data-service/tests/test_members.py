"""
Membership invariants, against a mocked DynamoDB.

The interesting cases are the ones a naive implementation gets wrong under
concurrency: two people made deputy, or the owner demoted out of their own
space. Those are enforced by conditional writes, so they are worth testing
against something that actually evaluates conditions rather than a stub.
"""
import os

import boto3
import pytest
from moto import mock_aws

TABLE = os.environ.setdefault("DYNAMODB_TABLE", "sdc-lake-test-resources")


@pytest.fixture
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="eu-west-1")
        ddb.create_table(
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
        dynamo.create_space("finance", "alice", "alice@x.com", "standard")
        yield


def test_deputy_can_be_assigned(table):
    from src.utils import dynamo
    dynamo.assign_deputy("finance", "bob", "bob@x.com", "Bob")
    meta = dynamo.get_space_metadata("finance")
    assert meta["deputyOid"] == "bob"
    assert dynamo.get_membership("bob", "finance")["role"] == "DEPUTY"


def test_second_deputy_is_rejected(table):
    from src.utils import dynamo
    dynamo.assign_deputy("finance", "bob", "bob@x.com", "Bob")
    with pytest.raises(dynamo.DeputyAlreadyAssigned):
        dynamo.assign_deputy("finance", "carol", "carol@x.com", "Carol")
    assert dynamo.get_space_metadata("finance")["deputyOid"] == "bob"


def test_deputy_can_be_replaced_after_removal(table):
    from src.utils import dynamo
    dynamo.assign_deputy("finance", "bob", "bob@x.com", "Bob")
    dynamo.remove_deputy("finance", "bob")
    assert "deputyOid" not in dynamo.get_space_metadata("finance")
    assert dynamo.get_membership("bob", "finance") is None

    dynamo.assign_deputy("finance", "carol", "carol@x.com", "Carol")
    assert dynamo.get_space_metadata("finance")["deputyOid"] == "carol"


def test_removing_a_stale_deputy_does_not_clear_the_current_one(table):
    """A retried request must not remove whoever holds the role now."""
    from src.utils import dynamo
    from botocore.exceptions import ClientError

    dynamo.assign_deputy("finance", "bob", "bob@x.com", "Bob")
    with pytest.raises(ClientError):
        dynamo.remove_deputy("finance", "carol")   # carol was never deputy
    assert dynamo.get_space_metadata("finance")["deputyOid"] == "bob"


def test_members_are_listed_with_the_owner(table):
    from src.utils import dynamo
    dynamo.put_member("finance", "dave", "dave@x.com", "Dave", "CONSUMER")
    roles = {m["userId"]: m["role"] for m in dynamo.list_space_members("finance")}
    assert roles == {"alice": "OWNER", "dave": "CONSUMER"}


def test_deleting_a_member_removes_their_access(table):
    from src.utils import dynamo
    dynamo.put_member("finance", "dave", "dave@x.com", "Dave", "PRODUCER")
    dynamo.delete_member("finance", "dave")
    assert dynamo.get_membership("dave", "finance") is None
