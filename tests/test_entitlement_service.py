"""Tests for entitlement_service — grant, remove, consume, expire flows.

Validates DOM-STORE-001 contracts:
- One EntitlementEvent per pass (§VII)
- Lineage via entitlement_id reuse on terminal events
- PERK acquisition_type for rent-granted passes
- Expiration by correlation_id at rent cycle boundary (§VIII.6)
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, Seat
from app.services.entitlement_service import (
    consume_hall_pass,
    expire_rent_hall_passes,
    get_hall_pass_balance,
    grant_hall_passes,
    remove_hall_passes,
)
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def classroom(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        return classroom


def _seat(app, classroom) -> Seat:
    return db.session.get(Seat, classroom.students[0].seat_id)


# ---------------------------------------------------------------------------
# grant_hall_passes
# ---------------------------------------------------------------------------


def test_grant_emits_one_event_per_pass(app, classroom):
    """DOM-STORE-001 §VII: one event per unit."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="grant-5"):
            grant_hall_passes(seat, 5, correlation_id="corr-test-001")

        events = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id,
            class_id=seat.class_id,
            event_type="GRANTED",
        ).all()
        assert len(events) == 5
        assert all(e.correlation_id == "corr-test-001" for e in events)
        assert len({e.entitlement_id for e in events}) == 5


def test_grant_perk_acquisition_type(app, classroom):
    """Rent-granted passes use acquisition_type=PERK."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="grant-perk"):
            grant_hall_passes(seat, 2, acquisition_type="PERK", correlation_id="rent-corr-001")

        events = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id,
            event_type="GRANTED",
        ).all()
        assert len(events) == 2
        assert all(e.acquisition_type == "PERK" for e in events)


def test_grant_with_actor_seat_id(app, classroom):
    """actor_seat_id can differ from target (teacher granting to student)."""
    with app.app_context():
        seat = _seat(app, classroom)
        teacher_seat_id = classroom.teacher_seat_id
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="grant-actor"):
            grant_hall_passes(seat, 1, actor_seat_id=teacher_seat_id)

        event = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id,
            event_type="GRANTED",
        ).first()
        assert event.actor_seat_id == teacher_seat_id
        assert event.target_seat_id == seat.id


def test_grant_balance_reflects_quantity(app, classroom):
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="grant-balance"):
            balance = grant_hall_passes(seat, 3)
        assert balance == 3
        assert get_hall_pass_balance(seat.id, seat.class_id) == 3


# ---------------------------------------------------------------------------
# remove_hall_passes
# ---------------------------------------------------------------------------


def test_remove_reuses_entitlement_id(app, classroom):
    """DOM-STORE-001: REVOKED event must reuse the grant's entitlement_id."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="remove-setup"):
            grant_hall_passes(seat, 2)

        granted_ids = {
            e.entitlement_id
            for e in EntitlementEvent.query.filter_by(
                target_seat_id=seat.id, event_type="GRANTED",
            ).all()
        }

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="remove-exec"):
            remove_hall_passes(seat, 1)

        revoked = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="REVOKED",
        ).first()
        assert revoked.entitlement_id in granted_ids
        assert get_hall_pass_balance(seat.id, seat.class_id) == 1


def test_remove_preserves_acquisition_type(app, classroom):
    """REVOKED event should carry the original grant's acquisition_type."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="remove-perk-setup"):
            grant_hall_passes(seat, 1, acquisition_type="PERK")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="remove-perk-exec"):
            remove_hall_passes(seat, 1)

        revoked = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="REVOKED",
        ).first()
        assert revoked.acquisition_type == "PERK"


# ---------------------------------------------------------------------------
# consume_hall_pass
# ---------------------------------------------------------------------------


def test_consume_reuses_entitlement_id(app, classroom):
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="consume-setup"):
            grant_hall_passes(seat, 1)

        granted = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="GRANTED",
        ).first()

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="consume-exec"):
            event, balance = consume_hall_pass(seat.id, seat.class_id, trigger_id="hp-log-1")

        assert event.entitlement_id == granted.entitlement_id
        assert event.event_type == "CONSUMED"
        assert balance == 0


def test_consume_preserves_correlation_id(app, classroom):
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="consume-corr-setup"):
            grant_hall_passes(seat, 1, correlation_id="orig-corr-123")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="consume-corr-exec"):
            event, _ = consume_hall_pass(seat.id, seat.class_id, trigger_id="hp-log-2")

        assert event.correlation_id == "orig-corr-123"


def test_consume_fails_when_no_passes(app, classroom):
    with app.app_context():
        seat = _seat(app, classroom)
        with pytest.raises(ValueError, match="No available hall-pass"):
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="consume-empty"):
                consume_hall_pass(seat.id, seat.class_id, trigger_id="hp-log-3")


# ---------------------------------------------------------------------------
# expire_rent_hall_passes
# ---------------------------------------------------------------------------


def test_expire_by_correlation_id(app, classroom):
    """DOM-OBL-001 §IX.9: perk passes expire at rent boundary by correlation_id."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-setup"):
            grant_hall_passes(
                seat, 3,
                acquisition_type="PERK",
                correlation_id="rent-cycle-001",
            )

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-exec"):
            expired_count = expire_rent_hall_passes(
                correlation_id="rent-cycle-001",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        assert expired_count == 3
        assert get_hall_pass_balance(seat.id, seat.class_id) == 0

        expired_events = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="EXPIRED",
        ).all()
        assert len(expired_events) == 3
        assert all(e.acquisition_type == "PERK" for e in expired_events)
        assert all(e.correlation_id == "rent-cycle-001" for e in expired_events)


def test_expire_does_not_affect_non_perk_passes(app, classroom):
    """Only PERK passes expire; GRANT passes are untouched."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-mixed-setup"):
            grant_hall_passes(seat, 2, acquisition_type="GRANT", correlation_id="teacher-grant")
            grant_hall_passes(seat, 3, acquisition_type="PERK", correlation_id="rent-cycle-002")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-mixed-exec"):
            expired_count = expire_rent_hall_passes(
                correlation_id="rent-cycle-002",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        assert expired_count == 3
        assert get_hall_pass_balance(seat.id, seat.class_id) == 2


def test_expire_skips_already_consumed(app, classroom):
    """Already consumed passes should not be expired again."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-consumed-setup"):
            grant_hall_passes(seat, 2, acquisition_type="PERK", correlation_id="rent-cycle-003")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-consumed-use"):
            consume_hall_pass(seat.id, seat.class_id, trigger_id="hp-used")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-consumed-exec"):
            expired_count = expire_rent_hall_passes(
                correlation_id="rent-cycle-003",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        assert expired_count == 1
        assert get_hall_pass_balance(seat.id, seat.class_id) == 0


def test_expire_different_correlation_ids_isolated(app, classroom):
    """Passes from different rent cycles are isolated by correlation_id."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-iso-setup"):
            grant_hall_passes(seat, 2, acquisition_type="PERK", correlation_id="cycle-A")
            grant_hall_passes(seat, 3, acquisition_type="PERK", correlation_id="cycle-B")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-iso-exec"):
            expired_count = expire_rent_hall_passes(
                correlation_id="cycle-A",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        assert expired_count == 2
        assert get_hall_pass_balance(seat.id, seat.class_id) == 3


def test_expire_entitlement_id_lineage(app, classroom):
    """EXPIRED events must reuse the grant's entitlement_id for lineage."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-lineage-setup"):
            grant_hall_passes(seat, 1, acquisition_type="PERK", correlation_id="rent-cycle-lin")

        granted = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="GRANTED",
        ).first()

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="expire-lineage-exec"):
            expire_rent_hall_passes(
                correlation_id="rent-cycle-lin",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        expired = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="EXPIRED",
        ).first()
        assert expired.entitlement_id == granted.entitlement_id


def test_double_expire_produces_single_expired_event(app, classroom):
    """Calling expire twice must not create duplicate EXPIRED events."""
    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="double-expire-setup"):
            grant_hall_passes(seat, 2, acquisition_type="PERK", correlation_id="rent-double")

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="double-expire-1"):
            count1 = expire_rent_hall_passes(
                correlation_id="rent-double",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="double-expire-2"):
            count2 = expire_rent_hall_passes(
                correlation_id="rent-double",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        assert count1 == 2
        assert count2 == 0

        expired_events = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id,
            event_type="EXPIRED",
            correlation_id="rent-double",
        ).all()
        assert len(expired_events) == 2


def test_unique_index_rejects_duplicate_terminal_events(app, classroom):
    """DB unique partial index prevents duplicate terminal events per lineage.

    The ix_entitlement_events_one_terminal_per_lineage index enforces at most
    one terminal event (CONSUMED/EXPIRED/REVOKED) per (entitlement_id, class_id).
    This is the last line of defense if FOR UPDATE serialization fails.
    """
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    with app.app_context():
        seat = _seat(app, classroom)
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="dup-terminal-setup"):
            grant_hall_passes(seat, 1, acquisition_type="PERK", correlation_id="rent-dup")

        granted = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id, event_type="GRANTED",
        ).first()
        assert granted is not None

        # First EXPIRED event succeeds.
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="dup-terminal-1"):
            expire_rent_hall_passes(
                correlation_id="rent-dup",
                class_id=seat.class_id,
                actor_seat_id=classroom.teacher_seat_id,
            )

        # Manually inserting a second terminal event for the same lineage
        # must be rejected by the unique partial index.
        with pytest.raises(SAIntegrityError):
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="dup-terminal-2"):
                duplicate = EntitlementEvent(
                    class_id=seat.class_id,
                    target_seat_id=seat.id,
                    actor_seat_id=classroom.teacher_seat_id,
                    entitlement_id=granted.entitlement_id,
                    entitlement_type="HALL_PASS",
                    acquisition_type="PERK",
                    event_type="EXPIRED",
                    correlation_id="rent-dup",
                )
                db.session.add(duplicate)
                db.session.flush()

        # Verify only the original EXPIRED event exists.
        expired_events = EntitlementEvent.query.filter_by(
            target_seat_id=seat.id,
            event_type="EXPIRED",
            correlation_id="rent-dup",
        ).all()
        assert len(expired_events) == 1
