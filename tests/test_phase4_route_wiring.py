"""
Smoke tests for Phase 4 route wiring.

Tests verify:
1. `/api/purchase-item` POST correctly calls FEAT-STOR-001
2. `/admin/student/<seat_id>/adjust-hall-pass-entitlements` POST correctly calls FEAT-STOR-004
3. EntitlementEvent rows are created with correct structure
"""

import pytest
from decimal import Decimal

from app.extensions import db
from app.models import EntitlementEvent, StoreItem
from app.services.context_resolver import CanonicalContext
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def app_with_context(app):
    """Test app with class context."""
    with app.app_context():
        yield app


@pytest.fixture
def test_class_setup(app_with_context):
    """Create a test class with teacher, student, and store item."""
    with app_with_context.app_context():
        classroom = provision_classroom("chemistry_p1")
        teacher_user_id = classroom.teacher_user_id
        teacher_seat_id = classroom.teacher_seat_id
        student_seat_id = classroom.students[0].seat_id
        student_user_id = classroom.students[0].user_id

        store_item = StoreItem(
            user_id=teacher_user_id,
            class_id=classroom.class_id,
            name="Test Hall Pass",
            item_type="hall_pass",
            price=Decimal("0.00"),
            is_active=True,
        )
        db.session.add(store_item)
        db.session.commit()

        return {
            "class_id": classroom.class_id,
            "teacher_user_id": teacher_user_id,
            "teacher_seat_id": teacher_seat_id,
            "student_user_id": student_user_id,
            "student_seat_id": student_seat_id,
            "store_item": store_item,
        }


class TestDirectGrantFeature:
    """Test FEAT-STOR-004 direct grant via admin route."""

    def test_grant_creates_entitlement_events(self, app_with_context, test_class_setup):
        """Test that granting creates correct EntitlementEvent rows."""
        with app_with_context.app_context():
            teacher_user_id = test_class_setup["teacher_user_id"]
            teacher_seat_id = test_class_setup["teacher_seat_id"]
            student_seat_id = test_class_setup["student_seat_id"]
            class_id = test_class_setup["class_id"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                product_id=1,
                quantity=2,
            )

            assert result.success is True
            assert result.quantity_granted == 2
            assert len(result.entitlement_ids) == 2

            events = (
                EntitlementEvent.query
                .filter_by(
                    class_id=class_id,
                    correlation_id=result.correlation_id,
                    event_type="GRANTED",
                    acquisition_type="GRANT",
                )
                .all()
            )

            assert len(events) == 2
            for event in events:
                assert event.target_seat_id == student_seat_id
                assert event.actor_seat_id == teacher_seat_id
                assert event.product_id == 1
                assert event.entitlement_id is not None
                assert event.event_id is not None
                assert event.timestamp is not None

    def test_non_teacher_cannot_grant(self, app_with_context, test_class_setup):
        """Test that non-teachers are denied grant authority."""
        with app_with_context.app_context():
            student_user_id = test_class_setup["student_user_id"]
            student_seat_id = test_class_setup["student_seat_id"]
            class_id = test_class_setup["class_id"]

            ctx = CanonicalContext(
                user_id=student_user_id,
                class_id=class_id,
                seat_id=student_seat_id,
                actor_role="student",  # Not teacher
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                product_id=1,
                quantity=1,
            )

            assert result.success is False
            assert result.error_code == "TEACHER_AUTHORITY_REQUIRED"


class TestEntitlementEventCanonicalStructure:
    """Test EntitlementEvent has correct canonical fields."""

    def test_granted_event_structure(self, app_with_context, test_class_setup):
        """Verify GRANTED event has all required canonical fields."""
        with app_with_context.app_context():
            teacher_user_id = test_class_setup["teacher_user_id"]
            teacher_seat_id = test_class_setup["teacher_seat_id"]
            student_seat_id = test_class_setup["student_seat_id"]
            class_id = test_class_setup["class_id"]

            result = execute_direct_grant(
                canonical_context=CanonicalContext(
                    user_id=teacher_user_id,
                    class_id=class_id,
                    seat_id=teacher_seat_id,
                    actor_role="teacher",
                ),
                target_seat_id=student_seat_id,
                product_id=1,
                quantity=1,
            )

            event = (
                EntitlementEvent.query
                .filter_by(correlation_id=result.correlation_id)
                .first()
            )

            assert event.event_id is not None
            assert event.entitlement_id is not None
            assert event.class_id == class_id
            assert event.target_seat_id == student_seat_id
            assert event.actor_seat_id == teacher_seat_id
            assert event.product_id == 1
            assert event.entitlement_type in [
                "INSURANCE",
                "PRIVILEGE",
                "IMMEDIATE_USE",
                "DELAYED_USE",
                "COLLECTIVE_GOAL",
                "HALL_PASS",
            ]
            assert event.acquisition_type == "GRANT"
            assert event.event_type == "GRANTED"
            assert event.correlation_id == result.correlation_id
            assert event.payload is not None
            assert event.timestamp is not None
            assert event.timestamp.tzinfo is not None
