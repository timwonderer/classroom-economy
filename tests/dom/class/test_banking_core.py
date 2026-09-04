
from decimal import Decimal
import importlib.util
from pathlib import Path
import pytest
from app.feats.base import FEATContext
from app.models import LedgerBalanceSnapshot as BalanceCache, Transaction, TransactionStatus
from app.extensions import db
from app.services.ledger_settlement_service import settle_balances, settle_pending_transaction_contexts
from app.services.ledger_balance_query_service import get_available_balances
from tests.helpers.classroom_initializer import initialize


def test_DOM_CLASS_001__ledger_flow_posts_pending_transaction(client, app):
    """Test full flow: Create PENDING -> Settle -> Verify Cache."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="banking-core:test-ledger-flow"):
        classroom = initialize("chemistry_p1", app)
        economy = classroom.economy
        seat = classroom.students[0].seat
        student_user = classroom.students[0].user
        class_id, seat_id = classroom.class_id, seat.id

        tx = Transaction(
            user_id=student_user.id,
            class_id=class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=Decimal("10.50"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="Initial deposit",
        )
        db.session.add(tx)
        db.session.flush()

        assert tx.status == TransactionStatus.PENDING
        assert tx.posted_at is None

        bal_checking, _ = get_available_balances(seat_id, class_id)
        assert bal_checking == Decimal("10.50")

        settle_balances(seat_id, class_id)
        db.session.flush()

        db.session.expire_all()
        tx = db.session.get(Transaction, tx.id)
        assert tx.status == TransactionStatus.POSTED
        assert tx.posted_at is not None
        assert tx.posting_sequence is not None

        cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id, account_type="checking").first()
        assert cache is not None
        assert cache.posted_balance_cents == 1050
        assert cache.reconciled_through_posting_sequence == tx.posting_sequence
        assert cache.last_settlement_at is not None


def test_DOM_LED_001__posting_sequence_is_class_scoped_across_seats(client, app):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="banking-core:class-sequence"):
        classroom = initialize("chemistry_p1", app)
        first = classroom.students[0].seat
        second = classroom.students[1].seat

        for seat, amount in ((first, Decimal("3.00")), (second, Decimal("4.00"))):
            tx = Transaction(
                user_id=seat.user_id,
                class_id=classroom.class_id,
                seat_id=seat.id,
                target_seat_id=seat.id,
                actor_seat_id=seat.id,
                mechanism="self",
                amount=amount,
                account_type="checking",
                status=TransactionStatus.PENDING,
                description="class sequence test",
            )
            db.session.add(tx)
            db.session.flush()
            settle_balances(seat.id, classroom.class_id)

        posted = (
            Transaction.query
            .filter_by(class_id=classroom.class_id, status=TransactionStatus.POSTED)
            .order_by(Transaction.posting_sequence.asc())
            .all()
        )
        sequences = [tx.posting_sequence for tx in posted if tx.posting_sequence is not None]
        assert len(sequences) >= 2
        assert sequences == sorted(set(sequences))

def test_DOM_CLASS_001__void_pending_transaction_does_not_create_reversal(client, app):
    """Test voiding a PENDING transaction (no reversal)."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="banking-core:test-void-pending"):
        classroom = initialize("chemistry_p1", app)
        economy = classroom.economy
        seat = classroom.students[0].seat
        student_user = classroom.students[0].user
        class_id, seat_id = classroom.class_id, seat.id

        tx = Transaction(
            user_id=student_user.id,
            class_id=class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=Decimal("50.00"),
            status=TransactionStatus.PENDING,
        )
        db.session.add(tx)
        db.session.flush()

        tx.is_void = True
        db.session.flush()

        bal, _ = get_available_balances(seat_id, class_id)
        assert bal == Decimal("0.00")

        settle_balances(seat_id, class_id)
        db.session.flush()

        reversals = Transaction.query.filter_by(original_transaction_id=tx.id).all()
        assert len(reversals) == 0

        db.session.expire_all()
        tx = db.session.get(Transaction, tx.id)
        assert tx.status == TransactionStatus.VOID
        assert tx.voided_at is not None

        cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id, account_type="checking").first()
        if cache:
            assert cache.posted_balance_cents == 0

def test_DOM_CLASS_001__void_posted_transaction_creates_reversal(client, app):
    """Test voiding a POSTED transaction (creates reversal)."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="banking-core:test-void-posted"):
        classroom = initialize("chemistry_p1", app)
        economy = classroom.economy
        seat = classroom.students[0].seat
        student_user = classroom.students[0].user
        class_id, seat_id = classroom.class_id, seat.id

        tx = Transaction(
            user_id=student_user.id,
            class_id=class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=Decimal("100.00"),
            status=TransactionStatus.PENDING,
        )
        db.session.add(tx)
        db.session.flush()

        settle_balances(seat_id, class_id)
        db.session.flush()

        db.session.expire_all()
        tx = db.session.get(Transaction, tx.id)
        assert tx.status == TransactionStatus.POSTED

        tx.is_void = True

        reversal = Transaction(
            user_id=student_user.id,
            class_id=class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=-tx.amount,
            status=TransactionStatus.PENDING,
            original_transaction_id=tx.id,
        )
        db.session.add(reversal)
        db.session.flush()

        bal_after_void, _ = get_available_balances(seat_id, class_id)
        assert bal_after_void == Decimal("0.00")

        settle_balances(seat_id, class_id)
        db.session.flush()

        db.session.expire_all()
        reversal = db.session.get(Transaction, reversal.id)
        assert reversal.status == TransactionStatus.POSTED

        cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id, account_type="checking").first()
        assert cache.posted_balance_cents == 0


def test_DOM_CLASS_001__settlement_sweep_processes_each_pending_context_once(client, app):
    """The settlement sweep is scheduled automation run standalone (see
    scripts/settle_pending_transactions.py) with NO ambient FEAT context.

    It must therefore establish its own FEAT-LED-003 boundary per seat/class
    context so the settlement is durably committed. This test mirrors production:
    pending activity is created/committed through a FEAT, then the sweep is
    invoked OUTSIDE any FEAT context. Evidence proves: two eligible contexts
    settle exactly once, a second sweep does not re-settle them, and class
    boundaries stay intact.
    """
    # --- Arrange: create pending activity through a FEAT (as production does) ---
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="banking-core:test-settlement-sweep"):
        student_one_class = initialize("chemistry_p1", app)
        student_two_class = initialize("biology_block_a", app)
        student_one_seat_id = student_one_class.students[0].seat.id
        student_one_user_id = student_one_class.students[0].user.id
        student_two_seat_id = student_two_class.students[0].seat.id
        student_two_user_id = student_two_class.students[0].user.id
        class_id_one = student_one_class.class_id
        class_id_two = student_two_class.class_id

        db.session.add_all([
            Transaction(
                user_id=student_one_user_id,
                class_id=class_id_one,
                seat_id=student_one_seat_id,
                target_seat_id=student_one_seat_id,
                actor_seat_id=student_one_seat_id,
                mechanism="self",
                amount=Decimal("12.34"),
                account_type="checking",
                status=TransactionStatus.PENDING,
                type="deposit",
                description="Pending A",
            ),
            Transaction(
                user_id=student_one_user_id,
                class_id=class_id_one,
                seat_id=student_one_seat_id,
                target_seat_id=student_one_seat_id,
                actor_seat_id=student_one_seat_id,
                mechanism="self",
                amount=Decimal("1.66"),
                account_type="savings",
                status=TransactionStatus.PENDING,
                type="deposit",
                description="Pending A savings",
            ),
            Transaction(
                user_id=student_two_user_id,
                class_id=class_id_two,
                seat_id=student_two_seat_id,
                target_seat_id=student_two_seat_id,
                actor_seat_id=student_two_seat_id,
                mechanism="self",
                amount=Decimal("9.99"),
                account_type="checking",
                status=TransactionStatus.PENDING,
                type="deposit",
                description="Pending B",
            ),
        ])
        db.session.flush()

    # --- Act: run the sweep standalone, exactly like the scheduled cron script ---
    summary = settle_pending_transaction_contexts()

    # Two distinct seat/class contexts settle exactly once each; none fail.
    assert summary == {"settled_contexts": 2, "failed_contexts": 0}

    # --- Assert: settlement is durably persisted (survives beyond the sweep) ---
    db.session.expire_all()
    posted_statuses = {
        (tx.user_id, tx.class_id, tx.account_type): tx.status
        for tx in Transaction.query.all()
    }
    assert posted_statuses[(student_one_user_id, class_id_one, "checking")] == TransactionStatus.POSTED
    assert posted_statuses[(student_one_user_id, class_id_one, "savings")] == TransactionStatus.POSTED
    assert posted_statuses[(student_two_user_id, class_id_two, "checking")] == TransactionStatus.POSTED

    # Each context's balance cache reflects its own transactions only (class isolation).
    cache_one = {
        row.account_type: row.posted_balance_cents
        for row in BalanceCache.query.filter_by(seat_id=student_one_seat_id, class_id=class_id_one).all()
    }
    assert cache_one == {"checking": 1234, "savings": 166}

    cache_two = {
        row.account_type: row.posted_balance_cents
        for row in BalanceCache.query.filter_by(seat_id=student_two_seat_id, class_id=class_id_two).all()
    }
    assert cache_two == {"checking": 999}

    # --- Idempotency: a second sweep finds no eligible contexts and settles nothing ---
    summary_again = settle_pending_transaction_contexts()
    assert summary_again == {"settled_contexts": 0, "failed_contexts": 0}

    db.session.expire_all()
    assert BalanceCache.query.filter_by(
        seat_id=student_one_seat_id, class_id=class_id_one, account_type="checking"
    ).one().posted_balance_cents == 1234
    assert BalanceCache.query.filter_by(
        seat_id=student_two_seat_id, class_id=class_id_two, account_type="checking"
    ).one().posted_balance_cents == 999
    for tx in Transaction.query.all():
        assert tx.status == TransactionStatus.POSTED


def test_DOM_CLASS_001__settlement_script_returns_nonzero_when_failures(monkeypatch):
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "settle_pending_transactions.py"
    spec = importlib.util.spec_from_file_location("settle_pending_transactions_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class DummyAppContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyApp:
        def app_context(self):
            return DummyAppContext()

    monkeypatch.setattr(module, "create_app", lambda: DummyApp())
    monkeypatch.setattr(
        module,
        "settle_pending_transaction_contexts",
        lambda limit=None: {"settled_contexts": 1, "failed_contexts": 2},
    )
    monkeypatch.setattr(module, "parse_args", lambda: type("Args", (), {"limit": None})())

    assert module.main() == 1
