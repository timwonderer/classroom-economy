"""Tests for Phase 5 Store/Entitlements view model builders."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver
from app.services.view_model_builders import (
    build_entitlement_list_view,
    build_purchase_history_view,
)
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def classroom(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase5-view-models:policy-purchase"):
            purchase_policy = StorePolicyResolver.create_store_product(
                class_id=classroom.class_id,
                payload={
                    "product_id": 701,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "4.50",
                    "entitlement_type": "DELAYED_USE",
                    "name": "Notebook",
                },
                created_by_seat_id=classroom.teacher_seat_id,
            )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase5-view-models:policy-grant"):
            grant_policy = StorePolicyResolver.create_store_product(
                class_id=classroom.class_id,
                payload={
                    "product_id": 702,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "0.00",
                    "entitlement_type": "HALL_PASS",
                    "name": "Hall Pass",
                },
                created_by_seat_id=classroom.teacher_seat_id,
            )
        db.session.commit()
        return classroom, purchase_policy, grant_policy


def test_build_entitlement_list_view_uses_policy_name_and_status(app, classroom):
    with app.app_context():
        classroom_obj, purchase_policy, grant_policy = classroom
        student = classroom_obj.students[0]
        teacher_ctx = CanonicalContext(
            user_id=classroom_obj.teacher_user_id,
            class_id=classroom_obj.class_id,
            seat_id=classroom_obj.teacher_seat_id,
            actor_role="teacher",
        )

        execute_store_purchase(
            canonical_context=CanonicalContext(
                user_id=student.user_id,
                class_id=classroom_obj.class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
            policy_uuid=purchase_policy.policy_uuid,
            quantity=1,
        )
        execute_direct_grant(
            canonical_context=teacher_ctx,
            target_seat_id=student.seat_id,
            policy_uuid=grant_policy.policy_uuid,
            quantity=1,
        )
        db.session.commit()

        views = build_entitlement_list_view(student.seat_id, classroom_obj.class_id)
        assert len(views) == 2
        assert {view.product_name for view in views} == {"Notebook", "Hall Pass"}
        assert all(view.status == "GRANTED" for view in views)
        assert sorted(view.granted_by_seat_id for view in views) == sorted(
            [student.seat_id, classroom_obj.teacher_seat_id]
        )


def test_build_purchase_history_view_groups_by_correlation(app, classroom):
    with app.app_context():
        classroom_obj, purchase_policy, _ = classroom
        student = classroom_obj.students[0]

        result = execute_store_purchase(
            canonical_context=CanonicalContext(
                user_id=student.user_id,
                class_id=classroom_obj.class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
            policy_uuid=purchase_policy.policy_uuid,
            quantity=2,
        )
        db.session.commit()

        views = build_purchase_history_view(student.seat_id, classroom_obj.class_id)
        assert len(views) == 1
        view = views[0]
        assert view.policy_uuid == purchase_policy.policy_uuid
        assert view.product_name == "Notebook"
        assert view.quantity == 2
        assert view.price_per_unit == Decimal("4.50")
        assert view.total_price == Decimal("9.00")
        assert view.correlation_id == result.correlation_id
