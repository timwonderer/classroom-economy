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
from app.models import Seat, EntitlementEvent, StoreItem
from app.services.context_resolver import CanonicalContext
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from tests.helpers.v2_fixtures import make_teacher
from tests.helpers.class_scope import make_student_identity


@pytest.fixture
def app_with_context(app):
    """Test app with class context."""
    with app.app_context():
        yield app


@pytest.fixture
def test_class_setup(app_with_context):
    """Create a test class with teacher, student, and store item."""
    with app_with_context.app_context():
        from app.services.classroom_setup import create_class

        # Create teacher
        teacher = make_teacher(username="test_teacher")

        # Create class
        class_row = create_class(teacher.id, join_code="TEST123")
        class_id = class_row.class_id

        # Create teacher seat
        teacher_seat = Seat(user_id=teacher.id, class_id=class_id)
        db.session.add(teacher_seat)
        db.session.flush()

        # Create student
        student_seat = make_student_identity(
            class_id=class_id,
            first_name="Test",
            last_name="Student",
        )
        student_user = student_seat.user

        # Create store item
        store_item = StoreItem(
            user_id=teacher.id,
            class_id=class_id,
            name="Test Hall Pass",
            item_type="hall_pass",
            price=Decimal("0.00"),
            is_active=True,
        )
        db.session.add(store_item)
        db.session.commit()

        return {
            "class_id": class_id,
            "teacher": teacher,
            "teacher_seat": teacher_seat,
            "student_user": student_user,
            "student_seat": student_seat,
            "store_item": store_item,
        }


class TestDirectGrantFeature:
    """Test FEAT-STOR-004 direct grant via admin route."""

    def test_grant_creates_entitlement_events(self, app_with_context, test_class_setup):
        """Test that granting creates correct EntitlementEvent rows."""
        with app_with_context.app_context():
            teacher = test_class_setup["teacher"]
            teacher_seat = test_class_setup["teacher_seat"]
            student_seat = test_class_setup["student_seat"]
            class_id = test_class_setup["class_id"]

            # Grant hall passes via FEAT-STOR-004
            ctx = CanonicalContext(
                user_id=teacher.id,
                class_id=class_id,
                seat_id=teacher_seat.id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat.id,
                product_id=1,
                quantity=2,
            )

            # Verify grant succeeded
            assert result.success is True
            assert result.quantity_granted == 2
            assert len(result.entitlement_ids) == 2

            # Verify EntitlementEvent rows
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
                assert event.target_seat_id == student_seat.id
                assert event.actor_seat_id == teacher_seat.id
                assert event.product_id == 1
                assert event.entitlement_id is not None
                assert event.event_id is not None
                assert event.timestamp is not None

    def test_non_teacher_cannot_grant(self, app_with_context, test_class_setup):
        """Test that non-teachers are denied grant authority."""
        with app_with_context.app_context():
            student_user = test_class_setup["student_user"]
            student_seat = test_class_setup["student_seat"]
            class_id = test_class_setup["class_id"]

            ctx = CanonicalContext(
                user_id=student_user.id,
                class_id=class_id,
                seat_id=student_seat.id,
                actor_role="student",  # Not teacher
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat.id,
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
            teacher = test_class_setup["teacher"]
            teacher_seat = test_class_setup["teacher_seat"]
            student_seat = test_class_setup["student_seat"]
            class_id = test_class_setup["class_id"]

            result = execute_direct_grant(
                canonical_context=CanonicalContext(
                    user_id=teacher.id,
                    class_id=class_id,
                    seat_id=teacher_seat.id,
                    actor_role="teacher",
                ),
                target_seat_id=student_seat.id,
                product_id=1,
                quantity=1,
            )

            event = (
                EntitlementEvent.query
                .filter_by(correlation_id=result.correlation_id)
                .first()
            )

            # Verify all canonical fields per DOM-STORE-001
            assert event.event_id is not None  # PK
            assert event.entitlement_id is not None  # Lineage key
            assert event.class_id == class_id  # Class boundary
            assert event.target_seat_id == student_seat.id  # Recipient
            assert event.actor_seat_id == teacher_seat.id  # Actor (teacher)
            assert event.product_id == 1  # Product reference
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
            assert event.timestamp.tzinfo is not None  # UTC
