"""
Data product staging and grants.

The case that matters most is the cascade on unstage: authz turns a consumer
grant into an allowed key prefix and does not re-check that the product is
still staged, so a grant left behind would keep working while the UI showed
the folder as no longer shared.
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
        dynamo.put_data_product("finance", "sales", "Q1 numbers", "alice")
        yield


def test_staged_products_exclude_consumer_rows(table):
    from src.utils import dynamo
    dynamo.put_data_product_consumer("finance", "sales", "emma", "e@x.com", "Emma")
    products = dynamo.list_data_products("finance")
    assert [p["dataProductId"] for p in products] == ["sales"]


def test_consumer_grant_is_found_through_the_index(table):
    from src.utils import dynamo
    dynamo.put_data_product_consumer("finance", "sales", "emma", "e@x.com", "Emma")
    grants = dynamo.list_user_product_grants("emma", "finance")
    assert len(grants) == 1
    assert grants[0]["dataProductId"] == "sales"


def test_unstaging_revokes_every_grant(table):
    from src.utils import dynamo
    dynamo.put_data_product_consumer("finance", "sales", "emma", "e@x.com", "Emma")
    dynamo.put_data_product_consumer("finance", "sales", "frank", "f@x.com", "Frank")

    revoked = dynamo.delete_data_product("finance", "sales")

    assert revoked == 2
    assert dynamo.get_data_product("finance", "sales") is None
    assert dynamo.list_user_product_grants("emma", "finance") == []
    assert dynamo.list_user_product_grants("frank", "finance") == []


def test_unstaging_one_product_leaves_another_alone(table):
    from src.utils import dynamo
    dynamo.put_data_product("finance", "hr", None, "alice")
    dynamo.put_data_product_consumer("finance", "sales", "emma", "e@x.com", "Emma")
    dynamo.put_data_product_consumer("finance", "hr", "frank", "f@x.com", "Frank")

    dynamo.delete_data_product("finance", "sales")

    assert dynamo.get_data_product("finance", "hr") is not None
    assert len(dynamo.list_user_product_grants("frank", "finance")) == 1


def test_revoking_one_consumer_leaves_the_others(table):
    from src.utils import dynamo
    dynamo.put_data_product_consumer("finance", "sales", "emma", "e@x.com", "Emma")
    dynamo.put_data_product_consumer("finance", "sales", "frank", "f@x.com", "Frank")

    dynamo.delete_data_product_consumer("finance", "sales", "emma")

    remaining = dynamo.list_data_product_consumers("finance", "sales")
    assert [c["userId"] for c in remaining] == ["frank"]
