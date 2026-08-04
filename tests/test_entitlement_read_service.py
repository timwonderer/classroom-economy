"""Tests for the Phase 5 entitlement read service."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent
from app.services.entitlement_read_service import get_hall_pass_balance
from app.services.store_policy_resolver import StorePolicyResolver
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from app.services.context_resolver import CanonicalContext
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def classroom(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase5-read-service:policy"):
            policy = StorePolicyResolver.create_store_product(
                class_id=classroom.class_id,
                payload={
                    "product_id": 501,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "0.00",
                    "entitlement_type": "HALL_PASS",
                    "name": "Hall Pass",
                },
                created_by_seat_id=classroom.teacher_seat_id,
            )
        db.session.commit()
        return classroom, policy


def test_get_hall_pass_balance_derives_from_events(app, classroom):
    with app.app_context():
        classroom_obj, policy = classroom
        ctx = CanonicalContext(
            user_id=classroom_obj.teacher_user_id,
            class_id=classroom_obj.class_id,
            seat_id=classroom_obj.teacher_seat_id,
            actor_role="teacher",
        )

        execute_direct_grant(
            canonical_context=ctx,
            target_seat_id=classroom_obj.students[0].seat_id,
            policy_uuid=policy.policy_uuid,
            quantity=2,
        )
        db.session.commit()

        assert get_hall_pass_balance(classroom_obj.students[0].seat_id, classroom_obj.class_id) == 2

        # Consume one entitlement and ensure the derived balance updates.
        granted = (
            EntitlementEvent.query
            .filter_by(
                class_id=classroom_obj.class_id,
                target_seat_id=classroom_obj.students[0].seat_id,
                event_type="GRANTED",
                acquisition_type="GRANT",
            )
            .order_by(EntitlementEvent.timestamp.asc())
            .first()
        )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase5-read-service:consume"):
            consumed = EntitlementEvent(
                class_id=classroom_obj.class_id,
                entitlement_id=granted.entitlement_id,
                target_seat_id=classroom_obj.students[0].seat_id,
                actor_seat_id=classroom_obj.teacher_seat_id,
                product_id=granted.product_id,
                entitlement_type=granted.entitlement_type,
                acquisition_type=granted.acquisition_type,
                event_type="CONSUMED",
                correlation_id=granted.correlation_id,
                payload={"reason": "test"},
            )
            db.session.add(consumed)
            db.session.flush()

        assert get_hall_pass_balance(classroom_obj.students[0].seat_id, classroom_obj.class_id) == 1
