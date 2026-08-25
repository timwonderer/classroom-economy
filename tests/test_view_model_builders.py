"""Tests for Phase 5 Store/Entitlements view model builders."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, IdentityProfile
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver
from app.services.view_model_builders import (
    build_entitlement_list_view,
    build_policy_list_view,
    build_purchase_history_view,
    build_identity_profile_view,
)
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import create_ledger_pending_transaction


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
        # Fund the purchasing student through the canonical ledger write path so the
        # priced DELAYED_USE purchase (4.50 x up-to-2 = 9.00) is accepted by the
        # Ledger instead of being denied INSUFFICIENT_FUNDS. A pending credit is
        # sufficient: available balance = posted + pending delta, so the store
        # purchase FEAT sees funds without a separate settlement pass. We use the
        # lowest-level canonical producer (ledger_service.create_pending_transaction)
        # rather than hand-constructing balance rows.
        student = classroom.students[0]
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase5-view-models:fund-student"):
            create_ledger_pending_transaction(
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                user_id=student.user_id,
                amount=Decimal("100.00"),
                account_type="checking",
                type="payroll",
                description="Test funding for store purchase",
            )
        # Persist the canonical producer's output durably. create_store_product
        # only flushes inside the FEAT-TEST-SETUP transaction boundary; without a
        # real commit the StoreProduct rows are rolled back when this fixture's
        # app_context pops, leaving the read paths (which run in a fresh
        # app_context/session) unable to see any policy. This mirrors the sibling
        # store fixtures (e.g. test_feat_stor_001_purchase.py).
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


def test_build_policy_list_view_returns_canonical_policies_in_presentation_order(app, classroom):
    with app.app_context():
        classroom_obj, purchase_policy, grant_policy = classroom

        views = build_policy_list_view(classroom_obj.class_id)

        assert [view.policy_uuid for view in views] == [
            purchase_policy.policy_uuid,
            grant_policy.policy_uuid,
        ]
        assert [view.product_id for view in views] == [701, 702]
        assert [view.name for view in views] == ["Notebook", "Hall Pass"]
        assert all(view.class_id == classroom_obj.class_id for view in views)
        assert all(view.is_purchasable for view in views)
        assert all(view.supports_direct_grants for view in views)


def test_build_identity_profile_view_happy_path(app, classroom):
    """Test building identity profile view for a student seat."""
    with app.app_context():
        classroom_obj, _, _ = classroom
        student = classroom_obj.students[0]

        view = build_identity_profile_view(student.seat_id, classroom_obj.class_id)

        assert view is not None
        assert view.seat_id == student.seat_id
        assert view.class_id == classroom_obj.class_id
        assert view.profile_type == "student"
        # Verify view model contains identity profile data
        profile = IdentityProfile.query.filter_by(seat_id=student.seat_id).first()
        assert profile is not None
        assert view.first_name == profile.first_name
        assert view.last_name == profile.last_name
        assert view.notes == profile.notes


def test_build_identity_profile_view_computes_display_properties(app, classroom):
    """Test that view model computes full_name and last_initial correctly."""
    with app.app_context():
        classroom_obj, _, _ = classroom
        student = classroom_obj.students[0]

        view = build_identity_profile_view(student.seat_id, classroom_obj.class_id)

        assert view is not None
        profile = IdentityProfile.query.filter_by(seat_id=student.seat_id).first()
        assert view.full_name == f"{profile.first_name} {profile.last_name}"
        assert view.last_initial == profile.last_name[0]


def test_build_identity_profile_view_returns_none_when_not_found(app, classroom):
    """Test that builder returns None when profile doesn't exist."""
    with app.app_context():
        classroom_obj, _, _ = classroom

        view = build_identity_profile_view(999999, classroom_obj.class_id)

        assert view is None


def test_build_identity_profile_view_scoped_by_class_id(app, classroom):
    """Test that view model respects multi-tenancy scoping by class_id."""
    with app.app_context():
        classroom_obj, _, _ = classroom
        student = classroom_obj.students[0]

        # Query with correct class_id - should find the profile
        view = build_identity_profile_view(student.seat_id, classroom_obj.class_id)
        assert view is not None

        # Query with wrong class_id - should not find the profile
        view_wrong_class = build_identity_profile_view(student.seat_id, "wrong-class-id")
        assert view_wrong_class is None


def test_build_identity_profile_view_is_frozen(app, classroom):
    """Test that view model dataclass is frozen and immutable."""
    with app.app_context():
        classroom_obj, _, _ = classroom
        student = classroom_obj.students[0]

        view = build_identity_profile_view(student.seat_id, classroom_obj.class_id)

        assert view is not None

        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises((AttributeError, TypeError)):
            view.first_name = "Modified"
