"""Regression pin for blocker B10 — snapshot identity is per ACCOUNT.

DOM-LED-001 §2 scopes a balance snapshot to ``(class_id, seat_id, account_type)``:
one row per account, not one row per seat carrying both. Before this fix
``app/models.py`` still declared the pre-split shape (a single row with
``posted_checking_balance_cents`` / ``posted_savings_balance_cents``) that
migration ``e6f7a8b9c0d1`` had already dropped. Two things followed:

1. Reads of those columns hit SQL that no longer existed, so ``get_posted_balance``
   RAISED instead of degrading to its own INV-LED-006 fallback; and
2. ``_get_balance_cache`` looked a snapshot up without naming the account, so even
   with the columns present it would hand back an arbitrary account's row and
   report it as both balances.

These assertions fail against the pre-fix commit and are the ship gate for B10.
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus
from app.services.ledger_balance_query_service import get_posted_balance
from app.utils.banking import settle_balances
from tests.helpers.classroom_initializer import initialize


def _snapshots(seat_id, class_id):
    return {
        row.account_type: row
        for row in LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat_id, class_id=class_id
        ).all()
    }


def _pending(seat, amount, account_type, description):
    return Transaction(
        user_id=seat.user_id,
        class_id=seat.class_id,
        seat_id=seat.id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        amount=Decimal(amount),
        account_type=account_type,
        status=TransactionStatus.PENDING,
        type="deposit",
        description=description,
    )


def test_DOM_LED_001__settlement_writes_one_snapshot_row_per_account(client, app):
    """Checking and savings settle into SEPARATE rows holding their own balance."""
    classroom = initialize("chemistry_p1", app)
    seat = classroom.students[0].seat
    class_id, seat_id = classroom.class_id, seat.id

    with FEATContext("FEAT-LED-001", idempotency_key="b10:per-account-rows"):
        db.session.add_all([
            _pending(seat, "40.00", "checking", "Checking deposit"),
            _pending(seat, "25.00", "savings", "Savings deposit"),
        ])
        db.session.flush()

        settle_balances(seat_id, class_id)
        db.session.flush()

    rows = _snapshots(seat_id, class_id)

    # Two distinct rows — the pre-split shape could only ever produce one.
    assert set(rows) == {"checking", "savings"}
    assert rows["checking"].posted_balance_cents == 4000
    assert rows["savings"].posted_balance_cents == 2500

    # And the accounts are genuinely independent, not one row reported twice.
    assert get_posted_balance(seat_id, class_id, "checking") == Decimal("40.00")
    assert get_posted_balance(seat_id, class_id, "savings") == Decimal("25.00")


def test_DOM_LED_001__posted_balance_reads_are_account_scoped(client, app):
    """A seat funded in ONE account must not leak that balance into the other.

    This is the sharp edge of the missing ``account_type`` predicate: with only
    a savings row present, an account-blind lookup returns it for both reads.
    """
    classroom = initialize("chemistry_p1", app)
    seat = classroom.students[0].seat
    class_id, seat_id = classroom.class_id, seat.id

    with FEATContext("FEAT-LED-001", idempotency_key="b10:savings-only"):
        db.session.add(_pending(seat, "80.00", "savings", "Savings only"))
        db.session.flush()

        settle_balances(seat_id, class_id)
        db.session.flush()

    assert get_posted_balance(seat_id, class_id, "savings") == Decimal("80.00")
    assert get_posted_balance(seat_id, class_id, "checking") == Decimal("0.00")


def test_DOM_LED_001__missing_snapshot_recomputes_instead_of_raising(client, app):
    """INV-LED-006: the snapshot is a projection, so a missing row is normal.

    Deleting the row must degrade to a recompute from ledger history. Pre-fix
    this path raised, because the read touched dropped columns before it could
    ever reach the fallback.
    """
    classroom = initialize("chemistry_p1", app)
    seat = classroom.students[0].seat
    class_id, seat_id = classroom.class_id, seat.id

    with FEATContext("FEAT-LED-001", idempotency_key="b10:fallback"):
        db.session.add(_pending(seat, "12.50", "checking", "Checking deposit"))
        db.session.flush()

        settle_balances(seat_id, class_id)
        db.session.flush()

    assert get_posted_balance(seat_id, class_id, "checking") == Decimal("12.50")

    with FEATContext("FEAT-LED-001", idempotency_key="b10:fallback-drop"):
        LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat_id, class_id=class_id, account_type="checking"
        ).delete()
        db.session.flush()

    assert _snapshots(seat_id, class_id).get("checking") is None
    # Rebuilt from history rather than raising or reporting zero.
    assert get_posted_balance(seat_id, class_id, "checking") == Decimal("12.50")


def test_DOM_LED_001__snapshot_scope_is_unique_per_account(client, app):
    """uq_balance_snapshot_scope enforces (class_id, seat_id, account_type)."""
    classroom = initialize("chemistry_p1", app)
    seat = classroom.students[0].seat
    class_id, seat_id = classroom.class_id, seat.id

    with FEATContext("FEAT-LED-001", idempotency_key="b10:scope-uniqueness"):
        db.session.add(
            LedgerBalanceSnapshot(
                seat_id=seat_id, class_id=class_id,
                account_type="checking", posted_balance_cents=100,
            )
        )
        db.session.flush()

        # A second row for the SAME account is a duplicate...
        db.session.add(
            LedgerBalanceSnapshot(
                seat_id=seat_id, class_id=class_id,
                account_type="checking", posted_balance_cents=200,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()

    # ...but the other account is a legitimately distinct scope.
    with FEATContext("FEAT-LED-001", idempotency_key="b10:scope-uniqueness-savings"):
        db.session.add(
            LedgerBalanceSnapshot(
                seat_id=seat_id, class_id=class_id,
                account_type="checking", posted_balance_cents=100,
            )
        )
        db.session.add(
            LedgerBalanceSnapshot(
                seat_id=seat_id, class_id=class_id,
                account_type="savings", posted_balance_cents=200,
            )
        )
        db.session.flush()

    rows = _snapshots(seat_id, class_id)
    assert rows["checking"].posted_balance_cents == 100
    assert rows["savings"].posted_balance_cents == 200
