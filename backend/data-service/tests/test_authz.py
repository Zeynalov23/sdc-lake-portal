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


def _mock_product_grants(user_id: str, space_id: str):
    if space_id != SPACE_ID:
        return []
    return [
        grant
        for (uid, _dp), grant in DATA_PRODUCT_CONSUMERS.items()
        if uid == user_id
    ]


@pytest.fixture(autouse=True)
def mock_dynamo(monkeypatch):
    monkeypatch.setattr(authz.dynamo, "get_membership", _mock_membership)
    monkeypatch.setattr(authz.dynamo, "get_data_product_consumer", _mock_dp_consumer)
    monkeypatch.setattr(authz.dynamo, "list_user_product_grants", _mock_product_grants)


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
    assert membership["role"] == "PRODUCER"


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


# The old require_data_product_* helpers took a product id and were never
# called by any router. They are replaced by key-scoped guards, so these
# tests now go through the same path the routers actually use.
def test_data_product_consumer_can_read_assigned_product_only():
    access = authz.authorize_read("emma", SPACE_ID, f"{DATA_PRODUCT_ID}/q1.csv")
    assert access.scope == "DATA_PRODUCT"
    assert access.record["dataProductId"] == DATA_PRODUCT_ID


def test_data_product_consumer_cannot_read_other_product():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_read("emma", SPACE_ID, "hr/q1.csv")
    assert exc.value.status_code == 404


def test_data_product_consumer_cannot_write_to_assigned_product():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_write("emma", SPACE_ID, f"{DATA_PRODUCT_ID}/q1.csv")
    assert exc.value.status_code == 403


def test_space_member_can_read_data_product_without_explicit_dp_grant():
    access = authz.authorize_read("david", SPACE_ID, f"{DATA_PRODUCT_ID}/q1.csv")
    assert access.scope == "SPACE"


def test_unknown_user_is_denied_space_access():
    assert_forbidden(
        lambda: authz.require_space_permission(
            "mallory", SPACE_ID, authz.SpacePermission.READ
        )
    )


# ---------------------------------------------------------------
# Prefix confinement — the rule that makes product-level access safe.
# These are the cases that would leak the whole space if the guards
# ever stopped intersecting the caller's request with their grants.
# ---------------------------------------------------------------
def test_product_consumer_cannot_read_outside_their_product():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_read("emma", SPACE_ID, "hr/salaries.csv")
    assert exc.value.status_code == 404


def test_product_consumer_can_read_inside_their_product():
    access = authz.authorize_read("emma", SPACE_ID, "sales/q1.csv")
    assert access.scope == "DATA_PRODUCT"
    assert access.prefixes == ("sales/",)


def test_product_consumer_listing_root_is_narrowed_to_their_products():
    prefixes = authz.authorize_list("emma", SPACE_ID, "")
    assert prefixes == ["sales/"]


def test_product_consumer_cannot_list_another_product():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_list("emma", SPACE_ID, "hr/")
    assert exc.value.status_code == 404


def test_product_consumer_cannot_write():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_write("emma", SPACE_ID, "sales/q1.csv")
    assert exc.value.status_code == 403


def test_product_consumer_cannot_configure_space():
    with pytest.raises(HTTPException) as exc:
        authz.require_space_permission(
            "emma", SPACE_ID, authz.SpacePermission.CONFIGURE
        )
    assert exc.value.status_code == 403


def test_space_member_listing_is_unrestricted():
    assert authz.authorize_list("david", SPACE_ID, "") == [""]


def test_producer_can_write_anywhere_in_space():
    access = authz.authorize_write("charlie", SPACE_ID, "hr/x.csv")
    assert access.scope == "SPACE"


def test_consumer_cannot_write():
    with pytest.raises(HTTPException) as exc:
        authz.authorize_write("david", SPACE_ID, "sales/q1.csv")
    assert exc.value.status_code == 403


def test_stranger_gets_403():
    with pytest.raises(HTTPException) as exc:
        authz.resolve("mallory", SPACE_ID)
    assert exc.value.status_code == 403
