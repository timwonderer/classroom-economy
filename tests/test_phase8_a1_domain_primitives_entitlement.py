"""
Phase 8.a.1: Domain Primitive Tests for EntitlementEvent Query Layer (DOM-STORE-001)

Tests verify:
1. get_entitlement_balance() — derive available balance from event history
2. get_purchase_count() — count PURCHASE acquisition events
3. get_active_rent_grant() — get active PERK (rent grant) without terminal event
4. is_entitlement_exercisable() — check if entitlement has no terminal event
5. get_entitlement_lineage_terminal_event() — get terminal event for lineage

These are canonical query functions that derive state from EntitlementEvent rows.
No mutable counters are tested; all state is derived.
"""

import pytest
from datetime import datetime, timedelta
import uuid

from app.extensions import db
from app.models import ClassEconomy, EntitlementEvent
from app.services.entitlement_read_service import (
    get_entitlement_balance,
    get_purchase_count,
    get_active_rent_grant,
    is_entitlement_exercisable,
    get_entitlement_lineage_terminal_event,
    get_entitlement_history,
    list_entitlements_for_seat,
)
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize


_created_events = []  # Track events for batch commit


def _add_entitlement_event_for_test(
    event_id: str,
    entitlement_id: str,
    target_seat_id: int,
    class_id: str,
    entitlement_type: str,
    event_type: str,
    acquisition_type: str,
    product_id: int,
    correlation_id: str,
    actor_seat_id: int | None = None,
    timestamp: datetime | None = None,
) -> EntitlementEvent:
    """Queue an EntitlementEvent for testing (will be committed later).

    Events are added to db.session but not committed until _flush_test_events()
    is called within a FEAT context.
    """
    event = EntitlementEvent(
        event_id=event_id,
        entitlement_id=entitlement_id,
        target_seat_id=target_seat_id,
        class_id=class_id,
        entitlement_type=entitlement_type,
        event_type=event_type,
        acquisition_type=acquisition_type,
        product_id=product_id,
        correlation_id=correlation_id,
        actor_seat_id=actor_seat_id,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.session.add(event)
    _created_events.append(event)
    return event


def _flush_test_events():
    """Commit all queued test events within a FEAT context.

    This must be called to persist test data after all _add_entitlement_event_for_test() calls.
    """
    if not _created_events:
        return

    idempotency_key = f"test_entitlement_events:{uuid.uuid4()}"
    with FEATContext("FEAT-STOR-001", idempotency_key=idempotency_key):
        # Events are already in session; just commit
        db.session.flush()

    _created_events.clear()


class TestGetEntitlementBalance:
    """Test get_entitlement_balance() balance derivation."""

    def test_balance_with_granted_events_only(self, app):
        """Balance of 3 GRANTED events = 3."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create 3 GRANTED events
            for i in range(3):
                _add_entitlement_event_for_test(
                    event_id=str(uuid.uuid4()),
                    entitlement_id=f"ent-{i}",
                    target_seat_id=seat_id,
                    class_id=class_id,
                    entitlement_type="HALL_PASS",
                    event_type="GRANTED",
                    acquisition_type="PURCHASE",
                    product_id=101,
                    correlation_id=str(uuid.uuid4()),
                    actor_seat_id=teacher_seat_id,
                )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check balance
            balance = get_entitlement_balance(
                seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                product_id=101,
            )

            assert balance == 3

    def test_balance_with_granted_and_consumed(self, app):
        """Balance of 5 GRANTED - 2 CONSUMED = 3."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create 5 GRANTED events
            entitlement_ids = []
            for i in range(5):
                ent_id = f"ent-{i}"
                entitlement_ids.append(ent_id)
                _add_entitlement_event_for_test(
                    event_id=str(uuid.uuid4()),
                    entitlement_id=ent_id,
                    target_seat_id=seat_id,
                    class_id=class_id,
                    entitlement_type="HALL_PASS",
                    event_type="GRANTED",
                    acquisition_type="PURCHASE",
                    product_id=101,
                    timestamp=datetime.utcnow(),
                    actor_seat_id=teacher_seat_id,
                    correlation_id=str(uuid.uuid4()),
                )

            # Create 2 CONSUMED events
            for i in range(2):
                _add_entitlement_event_for_test(
                    event_id=str(uuid.uuid4()),
                    entitlement_id=entitlement_ids[i],  # Terminal event for first 2
                    target_seat_id=seat_id,
                    class_id=class_id,
                    entitlement_type="HALL_PASS",
                    event_type="CONSUMED",
                    acquisition_type="PURCHASE",
                    product_id=101,
                    timestamp=datetime.utcnow() + timedelta(seconds=1),
                    actor_seat_id=teacher_seat_id,
                    correlation_id=str(uuid.uuid4()),
                )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check balance
            balance = get_entitlement_balance(
                seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                product_id=101,
            )

            assert balance == 3

    def test_balance_scoped_by_class_id(self, app):
        """Balance is scoped by class_id — different classes don't interfere."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create second class (wrap in FEAT context)
            with FEATContext("FEAT-IDEN-001", idempotency_key=f"test_class2:{uuid.uuid4()}"):
                class2 = ClassEconomy(join_code="CLASS2")
                db.session.add(class2)
                db.session.flush()
                class2_id = class2.class_id

            # Create events in class 1
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id="ent-class1",
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Create event in class 2 (same seat, different class)
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id="ent-class2",
                target_seat_id=seat_id,
                class_id=class2_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check balance in class 1
            balance_class1 = get_entitlement_balance(
                seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                product_id=101,
            )

            # Check balance in class 2
            balance_class2 = get_entitlement_balance(
                seat_id=seat_id,
                class_id=class2_id,
                entitlement_type="HALL_PASS",
                product_id=101,
            )

            assert balance_class1 == 1
            assert balance_class2 == 1


class TestGetPurchaseCount:
    """Test get_purchase_count() for PURCHASE acquisition events."""

    def test_purchase_count_zero(self, app):
        """No purchases returns 0."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id

            count = get_purchase_count(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert count == 0

    def test_purchase_count_multiple(self, app):
        """Counts only PURCHASE acquisition type."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create 3 PURCHASE events
            for i in range(3):
                _add_entitlement_event_for_test(
                    event_id=str(uuid.uuid4()),
                    entitlement_id=f"ent-purchase-{i}",
                    target_seat_id=seat_id,
                    class_id=class_id,
                    entitlement_type="HALL_PASS",
                    event_type="GRANTED",
                    acquisition_type="PURCHASE",
                    product_id=101,
                    timestamp=datetime.utcnow(),
                    actor_seat_id=teacher_seat_id,
                    correlation_id=str(uuid.uuid4()),
                )

            # Create 1 GRANT event (should NOT be counted)
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id="ent-grant",
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="GRANT",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check count — should be 3 (only PURCHASE events)
            count = get_purchase_count(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert count == 3

    def test_purchase_count_scoped_by_product(self, app):
        """Purchase count is scoped by product_id."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create 2 purchases of product 101
            for i in range(2):
                _add_entitlement_event_for_test(
                    event_id=str(uuid.uuid4()),
                    entitlement_id=f"ent-prod101-{i}",
                    target_seat_id=seat_id,
                    class_id=class_id,
                    entitlement_type="HALL_PASS",
                    event_type="GRANTED",
                    acquisition_type="PURCHASE",
                    product_id=101,
                    timestamp=datetime.utcnow(),
                    actor_seat_id=teacher_seat_id,
                    correlation_id=str(uuid.uuid4()),
                )

            # Create 1 purchase of product 102
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id="ent-prod102",
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=102,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check count for product 101
            count_101 = get_purchase_count(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            # Check count for product 102
            count_102 = get_purchase_count(
                seat_id=seat_id,
                class_id=class_id,
                product_id=102,
            )

            assert count_101 == 2
            assert count_102 == 1


class TestGetActiveRentGrant:
    """Test get_active_rent_grant() for PERK acquisition type."""

    def test_active_rent_grant_none(self, app):
        """No PERK events returns None."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id

            grant = get_active_rent_grant(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert grant is None

    def test_active_rent_grant_without_terminal_event(self, app):
        """PERK event without terminal event is active."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create PERK event
            ent_id = "ent-perk-active"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PERK",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check active grant
            grant = get_active_rent_grant(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert grant is not None
            assert grant.entitlement_id == ent_id
            assert grant.acquisition_type == "PERK"

    def test_active_rent_grant_with_terminal_event_returns_none(self, app):
        """PERK event with CONSUMED terminal event is not active."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create PERK event
            ent_id = "ent-perk-consumed"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PERK",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Add CONSUMED terminal event
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="CONSUMED",
                acquisition_type="PERK",
                product_id=101,
                timestamp=datetime.utcnow() + timedelta(seconds=1),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check active grant — should be None
            grant = get_active_rent_grant(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert grant is None

    def test_active_rent_grant_returns_most_recent(self, app):
        """Returns the most recent active PERK event."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            seat_id = classroom.students[0].seat.id
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create first PERK event
            ent_id_1 = "ent-perk-1"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id_1,
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PERK",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Create second PERK event (more recent)
            ent_id_2 = "ent-perk-2"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id_2,
                target_seat_id=seat_id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PERK",
                product_id=101,
                timestamp=datetime.utcnow() + timedelta(seconds=1),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check active grant — should be the more recent one
            grant = get_active_rent_grant(
                seat_id=seat_id,
                class_id=class_id,
                product_id=101,
            )

            assert grant is not None
            assert grant.entitlement_id == ent_id_2  # Most recent


class TestIsEntitlementExercisable:
    """Test is_entitlement_exercisable() terminal event checks."""

    def test_exercisable_without_terminal_event(self, app):
        """Entitlement without terminal event is exercisable."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create GRANTED event
            ent_id = "ent-exercisable"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check exercisable
            is_exercisable = is_entitlement_exercisable(
                entitlement_id=ent_id,
                class_id=class_id,
            )

            assert is_exercisable is True

    def test_not_exercisable_with_consumed_event(self, app):
        """Entitlement with CONSUMED terminal event is not exercisable."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create GRANTED event
            ent_id = "ent-consumed"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Add CONSUMED terminal event
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="CONSUMED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow() + timedelta(seconds=1),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check exercisable — should be False
            is_exercisable = is_entitlement_exercisable(
                entitlement_id=ent_id,
                class_id=class_id,
            )

            assert is_exercisable is False


class TestGetEntitlementLineageTerminalEvent:
    """Test get_entitlement_lineage_terminal_event() for terminal event retrieval."""

    def test_terminal_event_none_when_no_events(self, app):
        """No terminal event returns None."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            class_id = classroom.class_id

            terminal = get_entitlement_lineage_terminal_event(
                entitlement_id="ent-nonexistent",
                class_id=class_id,
            )

            assert terminal is None

    def test_terminal_event_none_when_no_terminal(self, app):
        """GRANTED event without terminal returns None."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create GRANTED event
            ent_id = "ent-no-terminal"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=None,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check terminal — should be None
            terminal = get_entitlement_lineage_terminal_event(
                entitlement_id=ent_id,
                class_id=class_id,
            )

            assert terminal is None

    def test_terminal_event_returned_when_consumed(self, app):
        """CONSUMED terminal event is returned."""
        with app.app_context():
            classroom = initialize("chemistry_p1", app)
            class_id = classroom.class_id
            teacher_seat_id = classroom.teacher_seat.id

            # Create GRANTED event
            ent_id = "ent-with-terminal"
            _add_entitlement_event_for_test(
                event_id=str(uuid.uuid4()),
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="GRANTED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow(),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Add CONSUMED terminal event
            terminal_event_id = str(uuid.uuid4())
            _add_entitlement_event_for_test(
                event_id=terminal_event_id,
                entitlement_id=ent_id,
                target_seat_id=classroom.students[0].seat.id,
                class_id=class_id,
                entitlement_type="HALL_PASS",
                event_type="CONSUMED",
                acquisition_type="PURCHASE",
                product_id=101,
                timestamp=datetime.utcnow() + timedelta(seconds=1),
                actor_seat_id=teacher_seat_id,
                correlation_id=str(uuid.uuid4()),
            )

            # Commit test data within FEAT context
            _flush_test_events()

            # Check terminal — should return the CONSUMED event
            result = get_entitlement_lineage_terminal_event(
                entitlement_id=ent_id,
                class_id=class_id,
            )

            assert result is not None
            assert result.event_type == "CONSUMED"
            assert result.event_id == terminal_event_id
