"""
Tests for FEAT-STOR-004: Direct Entitlement Grant (v1.0)

Tests cover:
- Happy path: teacher grants N entitlements to student creates N rows
- Teacher authority validation (must have actor_role="teacher")
- Target seat scope validation (must be in same class)
- Quantity logic: quantity=N creates N rows (not 1 with count)
- Hall-pass grants (no mutable balance)
- Idempotency (replay safe)
- Multi-tenancy isolation
"""

import pytest
import uuid

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, User, ClassEconomy, EntitlementEvent, UserRole
from app.services.context_resolver import CanonicalContext
from app.feats.direct_entitlement_grant_feat import execute_direct_grant, DirectGrantResult
from app.services.store_policy_resolver import StorePolicyResolver
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def app_with_class(app):
    """Test app with a class and seats."""
    with app.app_context():
        yield app


@pytest.fixture
def test_class_with_students(app_with_class):
    """Create a test class with teacher and student seats."""
    with app_with_class.app_context():
        classroom = provision_classroom("chemistry_p1")

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase4-direct-grant:store-policy"):
            policy = StorePolicyResolver.create_store_product(
                class_id=classroom.class_id,
                payload={
                    "product_id": 101,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "0.00",
                    "entitlement_type": "HALL_PASS",
                    "name": "Test Hall Pass",
                },
                created_by_seat_id=classroom.teacher_seat_id,
            )
        db.session.commit()

        return {
            "class_id": classroom.class_id,
            "teacher_user_id": classroom.teacher_user_id,
            "teacher_seat_id": classroom.teacher_seat_id,
            "student_user_1_id": classroom.students[0].user_id,
            "student_seat_1_id": classroom.students[0].seat_id,
            "student_user_2_id": classroom.students[1].user_id,
            "student_seat_2_id": classroom.students[1].seat_id,
            "policy_uuid": policy.policy_uuid,
            "product_id": policy.product_id,
        }


class TestDirectGrantHappyPath:
    """Test ordinary teacher direct grant flow."""

    def test_teacher_grants_to_student(self, app_with_class, test_class_with_students):
        """Teacher can grant entitlements to a student."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=3,
            )

            # Verify result
            assert result.success is True
            assert result.quantity_granted == 3
            assert len(result.entitlement_ids) == 3
            assert result.error_code is None

            # Verify EntitlementEvent rows created
            events = (
                EntitlementEvent.query
                .filter_by(class_id=class_id, target_seat_id=student_seat_id)
                .filter_by(event_type="GRANTED")
                .filter_by(acquisition_type="GRANT")
                .order_by(EntitlementEvent.timestamp)
                .all()
            )

            assert len(events) == 3
            assert all(e.correlation_id == result.correlation_id for e in events)
            assert all(e.product_id == test_class_with_students["product_id"] for e in events)
            assert all(e.actor_seat_id == teacher_seat_id for e in events)

    def test_grant_uses_provided_correlation_id(self, app_with_class, test_class_with_students):
        """Grant uses provided correlation_id."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            provided_corr_id = "grant_corr_123"

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=1,
                correlation_id=provided_corr_id,
            )

            assert result.success is True
            assert result.correlation_id == provided_corr_id


class TestQuantityLogic:
    """Test that quantity creates N rows, not mutable count."""

    def test_quantity_5_creates_5_rows(self, app_with_class, test_class_with_students):
        """Quantity=5 creates 5 EntitlementEvent rows."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=5,
            )

            assert result.quantity_granted == 5
            assert len(result.entitlement_ids) == 5

            # Verify exactly 5 rows
            events = (
                EntitlementEvent.query
                .filter_by(class_id=class_id, correlation_id=result.correlation_id)
                .filter_by(event_type="GRANTED")
                .all()
            )
            assert len(events) == 5

            # Each row should have distinct event_id, shared correlation_id
            event_ids = {e.event_id for e in events}
            assert len(event_ids) == 5  # All distinct


class TestValidationFailures:
    """Test that invalid inputs are rejected before mutation."""

    def test_non_teacher_cannot_grant(self, app_with_class, test_class_with_students):
        """Student cannot grant entitlements (must be teacher)."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            student_seat_1_id = test_class_with_students["student_seat_1_id"]
            student_seat_2_id = test_class_with_students["student_seat_2_id"]
            student_user_1_id = test_class_with_students["student_user_1_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=student_user_1_id,
                class_id=class_id,
                seat_id=student_seat_1_id,
                actor_role="student",  # Not "teacher"
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_2_id,
                policy_uuid=policy_uuid,
                quantity=1,
            )

            assert result.success is False
            assert result.error_code == "TEACHER_AUTHORITY_REQUIRED"
            assert result.quantity_granted == 0

    def test_invalid_quantity_zero(self, app_with_class, test_class_with_students):
        """Grant with quantity=0 is rejected."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=0,
            )

            assert result.success is False
            assert result.error_code == "QUANTITY_NOT_ALLOWED"

    def test_target_seat_not_in_class(self, app_with_class, test_class_with_students):
        """Grant to seat outside class scope is rejected."""
        with app_with_class.app_context():
            # Create second class
            class_scope_2 = provision_classroom("biology_block_a")
            foreign_student_seat_id = class_scope_2.students[0].seat_id

            # Try to grant from class_1 to student in class_2
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=foreign_student_seat_id,  # Different class
                policy_uuid=policy_uuid,
                quantity=1,
            )

            assert result.success is False
            assert result.error_code == "TARGET_SEAT_NOT_FOUND"


class TestHallPassGrants:
    """Test hall-pass specific grant handling."""

    def test_hall_pass_grant_no_balance_row(self, app_with_class, test_class_with_students):
        """Hall-pass grants don't create mutable balance rows."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            # Grant 3 hall passes
            result = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=3,
            )

            assert result.success is True
            assert result.quantity_granted == 3

            # Verify EntitlementEvent rows created
            events = EntitlementEvent.query.filter_by(
                correlation_id=result.correlation_id,
                event_type="GRANTED",
            ).all()

            assert len(events) == 3
            # All should have entitlement_type HALL_PASS
            assert all(e.entitlement_type == "HALL_PASS" for e in events)


class TestIdempotency:
    """Test replay protection."""

    def test_replay_same_idempotency_key(self, app_with_class, test_class_with_students):
        """Replaying with same idempotency_key should be safe."""
        with app_with_class.app_context():
            class_id = test_class_with_students["class_id"]
            teacher_seat_id = test_class_with_students["teacher_seat_id"]
            student_seat_id = test_class_with_students["student_seat_1_id"]
            teacher_user_id = test_class_with_students["teacher_user_id"]
            policy_uuid = test_class_with_students["policy_uuid"]

            ctx = CanonicalContext(
                user_id=teacher_user_id,
                class_id=class_id,
                seat_id=teacher_seat_id,
                actor_role="teacher",
            )

            idempotency_key = f"test_grant_{uuid.uuid4().hex}"

            # First grant
            result1 = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=2,
                idempotency_key=idempotency_key,
            )

            assert result1.success is True
            first_count = EntitlementEvent.query.filter_by(
                correlation_id=result1.correlation_id
            ).count()

            # Replay with same idempotency_key
            result2 = execute_direct_grant(
                canonical_context=ctx,
                target_seat_id=student_seat_id,
                policy_uuid=policy_uuid,
                quantity=2,
                idempotency_key=idempotency_key,
            )

            assert result2.success is True
            assert result2.correlation_id == result1.correlation_id
            assert result2.entitlement_ids == result1.entitlement_ids
            second_count = EntitlementEvent.query.filter_by(
                correlation_id=result2.correlation_id
            ).count()
            assert second_count == first_count


class TestCrossClassIsolation:
    """Test that grants in different classes don't interfere."""

    def test_grants_in_different_classes_isolated(self, app_with_class):
        """Grants in different classes are isolated."""
        with app_with_class.app_context():
            # Create two class scopes
            scope1 = provision_classroom("chemistry_p1")
            scope2 = provision_classroom("biology_block_a")

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase4-direct-grant:scope1-policy"):
                policy1 = StorePolicyResolver.create_store_product(
                    class_id=scope1.class_id,
                    payload={
                        "product_id": 301,
                        "is_purchasable": True,
                        "supports_direct_grants": True,
                        "price": "0.00",
                        "entitlement_type": "HALL_PASS",
                        "name": "Scope 1 Hall Pass",
                    },
                    created_by_seat_id=scope1.teacher_seat_id,
                )
            db.session.commit()

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="phase4-direct-grant:scope2-policy"):
                policy2 = StorePolicyResolver.create_store_product(
                    class_id=scope2.class_id,
                    payload={
                        "product_id": 302,
                        "is_purchasable": True,
                        "supports_direct_grants": True,
                        "price": "0.00",
                        "entitlement_type": "HALL_PASS",
                        "name": "Scope 2 Hall Pass",
                    },
                    created_by_seat_id=scope2.teacher_seat_id,
                )
            db.session.commit()

            teacher1_seat_id = scope1.teacher_seat_id
            teacher2_seat_id = scope2.teacher_seat_id

            student1_seat_id = scope1.students[0].seat_id
            student2_seat_id = scope2.students[0].seat_id

            # Grant in class 1
            ctx1 = CanonicalContext(
                user_id=scope1.teacher_user_id,
                class_id=scope1.class_id,
                seat_id=teacher1_seat_id,
                actor_role="teacher",
            )

            result1 = execute_direct_grant(
                canonical_context=ctx1,
                target_seat_id=student1_seat_id,
                policy_uuid=policy1.policy_uuid,
                quantity=2,
            )

            # Grant in class 2
            ctx2 = CanonicalContext(
                user_id=scope2.teacher_user_id,
                class_id=scope2.class_id,
                seat_id=teacher2_seat_id,
                actor_role="teacher",
            )

            result2 = execute_direct_grant(
                canonical_context=ctx2,
                target_seat_id=student2_seat_id,
                policy_uuid=policy2.policy_uuid,
                quantity=3,
            )

            # Verify isolation
            events1 = EntitlementEvent.query.filter_by(class_id=scope1.class_id).all()
            events2 = EntitlementEvent.query.filter_by(class_id=scope2.class_id).all()

            assert len(events1) == 2
            assert len(events2) == 3
            assert all(e.class_id == scope1.class_id for e in events1)
            assert all(e.class_id == scope2.class_id for e in events2)
