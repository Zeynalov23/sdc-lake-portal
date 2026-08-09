import pytest
from fastapi import HTTPException

from src.utils import authz
from tests.fixtures import DATA_PRODUCT_CONSUMERS, DATA_PRODUCT_ID, SPACE_ID, SPACE_MEMBERSHIPS


def _mock_membership(user_id: str, space_id: str):
    if space_id != SPACE_ID:
        return None
    return SPACE_MEMBERSHIPS.get(user_id)


def _mock_dp_consumer(user_id: str, space_id: str, data_product_id: str):
    if space_id != SPACE_ID:
        return None
    return DATA_PRODUCT_CONSUMERS.get((user_id, data_product_id))


@pytest.fixture(autouse=True)
def mock_dynamo(monkeypatch):
    monkeypatch.setattr(authz.dynamo, "get_membership", _mock_membership)
    monkeypatch.setattr(authz.dynamo, "get_data_product_consumer", _mock_dp_consumer)


def assert_forbidden(callable_):
    with pytest.raises(HTTPException) as exc:
        callable_()
    assert exc.value.status_code == 403


def test_owner_can_configure_space():
    membership = authz.require_space_permission(
        "alice", SPACE_ID, authz.SpacePermission.CONFIGURE
    )
    assert membership["role"] == "OWNER"


def test_deputy_can_manage_members():
    membership = authz.require_space_permission(
        "bob", SPACE_ID, authz.SpacePermission.MANAGE_MEMBERS
    )
    assert membership["role"] == "DEPUTY"


def test_developer_can_upload_to_space():
    membership = authz.require_space_permission(
        "charlie", SPACE_ID, authz.SpacePermission.WRITE
    )
    assert membership["role"] == "DEVELOPER"


def test_developer_cannot_manage_members():
    assert_forbidden(
        lambda: authz.require_space_permission(
            "charlie", SPACE_ID, authz.SpacePermission.MANAGE_MEMBERS
        )
    )


def test_space_consumer_can_read():
    membership = authz.require_space_permission(
        "david", SPACE_ID, authz.SpacePermission.READ
    )
    assert membership["role"] == "CONSUMER"


def test_space_consumer_cannot_upload():
    assert_forbidden(
        lambda: authz.require_space_permission(
            "david", SPACE_ID, authz.SpacePermission.WRITE
        )
    )


def test_data_product_consumer_can_read_assigned_product_only():
    result = authz.require_data_product_read("emma", SPACE_ID, DATA_PRODUCT_ID)
    assert result["scope"] == "DATA_PRODUCT"
    assert result["membership"]["dataProductId"] == DATA_PRODUCT_ID


def test_data_product_consumer_cannot_read_other_product():
    assert_forbidden(
        lambda: authz.require_data_product_read("emma", SPACE_ID, "hr")
    )


def test_data_product_consumer_cannot_write_to_assigned_product():
    assert_forbidden(
        lambda: authz.require_data_product_write("emma", SPACE_ID)
    )


def test_space_member_can_read_data_product_without_explicit_dp_grant():
    result = authz.require_data_product_read("david", SPACE_ID, DATA_PRODUCT_ID)
    assert result["scope"] == "SPACE"


def test_unknown_user_is_denied_space_access():
    assert_forbidden(
        lambda: authz.require_space_permission(
            "mallory", SPACE_ID, authz.SpacePermission.READ
        )
    )
