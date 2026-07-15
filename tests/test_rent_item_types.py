"""Canonical v2 tests for rent-linked store item synchronization and scope."""

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import RentItem, RentSettings, Seat, StoreItem, StorePurchase, StoreItemVisibility
from app.routes.admin import _sync_rent_items_to_store
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.v2_fixtures import make_teacher, seed_class_feature


pytestmark = [pytest.mark.critical, pytest.mark.regression]


@pytest.fixture
def teacher_user(client):
    teacher = make_teacher("teacher_rent")
    db.session.commit()
    return teacher


@pytest.fixture
def class_scope(client, teacher_user):
    scope = create_class_scope(teacher_user=teacher_user, join_code="JOINCODE123", section="A")
    seed_class_feature(class_id=scope.class_id, feature_name="rent")
    seed_class_feature(class_id=scope.class_id, feature_name="store")
    db.session.commit()
    return scope


@pytest.fixture
def student_seat(client, class_scope):
    seat = make_student_identity(class_id=class_scope.class_id, first_name="Test", last_name="S", claimed=True)
    db.session.commit()
    return seat


def test_store_item_schema_is_class_scoped():
    assert hasattr(StoreItem, "class_id")
    assert not hasattr(StoreItem, "join_code")
    assert hasattr(StoreItem, "is_rent_linked")


def test_rent_sync_marks_rent_linked_items(client, teacher_user, class_scope):
    with FEATContext("FEAT-TEST-001", idempotency_key=f"rent-item-types:sync-store:{class_scope.class_id}"):
        settings = RentSettings(class_id=class_scope.class_id)
        db.session.add(settings)
        db.session.flush()

        privilege_store = StoreItem(
            user_id=teacher_user.id,
            class_id=class_scope.class_id,
            name="Privilege",
            price=Decimal("10.00"),
            item_type="delayed",
            is_active=True,
        )
        per_use_store = StoreItem(
            user_id=teacher_user.id,
            class_id=class_scope.class_id,
            name="Consumable",
            price=Decimal("2.00"),
            item_type="delayed",
            is_active=True,
        )
        db.session.add_all([privilege_store, per_use_store])
        db.session.flush()

        db.session.add_all(
            [
                RentItem(
                    rent_setting_id=settings.id,
                    name="Privilege",
                    rent_item_type="privilege",
                    is_available_in_store=True,
                    store_price=Decimal("10.00"),
                    purchase_duration="per_period",
                    store_item_id=privilege_store.id,
                ),
                RentItem(
                    rent_setting_id=settings.id,
                    name="Consumable",
                    rent_item_type="per_use",
                    is_available_in_store=True,
                    store_price=Decimal("2.00"),
                    purchase_duration="per_use",
                    use_limit=1,
                    store_item_id=per_use_store.id,
                ),
                RentItem(
                    rent_setting_id=settings.id,
                    name="HP",
                    rent_item_type="hall_pass",
                    hall_pass_count=1,
                ),
            ]
        )
        db.session.flush()

    with FEATContext("FEAT-TEST-001", idempotency_key=f"rent-item-types:sync-rent:{class_scope.class_id}"):
        _sync_rent_items_to_store(settings, teacher_user.id, class_scope.class_id)

    db.session.refresh(privilege_store)
    db.session.refresh(per_use_store)
    assert privilege_store.is_rent_linked is True
    assert privilege_store.limit_per_student == 1
    assert per_use_store.is_rent_linked is True

    hall_pass_store = StoreItem.query.filter_by(name="HP", class_id=class_scope.class_id).first()
    assert hall_pass_store is None


def test_store_purchase_schema_uses_seat_and_class_scope(client, teacher_user, class_scope, student_seat):
    seat = student_seat
    with FEATContext("FEAT-STOR-002", idempotency_key=f"rent-item-types:purchase:{seat.id}"):
        store_item = StoreItem(
            user_id=teacher_user.id,
            class_id=class_scope.class_id,
            name="Multi-Use Snack",
            price=Decimal("5.00"),
            is_active=True,
            item_type="delayed",
        )
        db.session.add(store_item)
        db.session.flush()

        purchase = StorePurchase(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            store_item_id=store_item.id,
            quantity=1,
            price_at_purchase=Decimal("5.00"),
            total_price=Decimal("5.00"),
            status="purchased",
            uses_remaining=3,
            idempotency_key=f"rent-item-types:{seat.id}",
        )
        db.session.add(purchase)
        db.session.flush()

    db.session.refresh(purchase)
    assert purchase.seat_id == seat.id
    assert purchase.class_id == class_scope.class_id
    assert purchase.uses_remaining == 3
    assert StorePurchase.query.filter_by(seat_id=seat.id, class_id=class_scope.class_id).count() == 1


def test_store_item_visibility_is_seat_scoped(client, teacher_user, class_scope, student_seat):
    with FEATContext("FEAT-STOR-001", idempotency_key=f"rent-item-types:visibility:{student_seat.id}"):
        store_item = StoreItem(
            user_id=teacher_user.id,
            class_id=class_scope.class_id,
            name="Visibility Check",
            price=Decimal("3.00"),
            is_active=True,
            item_type="delayed",
        )
        db.session.add(store_item)
        db.session.flush()

        # The canonical v2 contract scopes visibility per seat, not by block/join code.
        db.session.add(StoreItemVisibility(store_item_id=store_item.id, seat_id=student_seat.id))
        db.session.flush()

    grants = StoreItemVisibility.query.filter_by(store_item_id=store_item.id).all()
    assert len(grants) == 1
    assert grants[0].seat_id == student_seat.id
    assert store_item.visibility_grants.count() == 1
