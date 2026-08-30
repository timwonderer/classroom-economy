"""Rent itemization "Available in Store" controls are gated on the store feature.

A rent item can only be surfaced in the class store when the store feature is
enabled for that class. The rent-settings page must reflect this: when store is
off, the store-availability affordance is disabled and an explanatory banner is
shown; when store is on, the affordance is live and the banner is absent.
"""

import pytest

from app.models import StoreItem
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.class_domain import enable_class_feature, update_rent_settings

pytestmark = [pytest.mark.regression]

BANNER_TEXT = "Store feature is turned off for this class."


def test_store_gate_disabled_when_store_feature_off(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="rent")

    resp = client.get("/admin/rent-settings")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert BANNER_TEXT in body
    assert "const STORE_ENABLED = false;" in body


def test_store_gate_live_when_store_feature_on(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    enable_class_feature(class_id=classroom.class_id, feature="store")

    resp = client.get("/admin/rent-settings")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert BANNER_TEXT not in body
    assert "const STORE_ENABLED = true;" in body


def test_per_use_rent_item_not_added_to_store_when_store_off(client):
    """Backend hard gate: a per-use rent item (normally 'always available in
    store') must NOT be surfaced in the store while store is disabled."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    # store deliberately NOT enabled

    resp = update_rent_settings(
        client,
        is_enabled="on",
        rent_amount="50.00",
        frequency_type="monthly",
        due_day_of_month="1",
        grace_period_days="3",
        late_penalty_amount="10.00",
        late_penalty_type="once",
        rent_item_name_0="Pencil",
        rent_item_type_0="per_use",
        rent_item_store_price_0="2.00",
    )
    assert resp.status_code == 302

    rent_linked = StoreItem.query.filter(
        StoreItem.class_id == classroom.class_id,
        StoreItem.is_rent_linked.is_(True),
    ).all()
    # Nothing rent-linked may be active or purchasable in the store.
    assert all(not si.is_active for si in rent_linked)
    assert all(not si.is_available_in_store for si in rent_linked)
