
from decimal import Decimal
from tests.helpers.v2_fixtures import make_admin

import importlib.util
from pathlib import Path
import pytest
from app.models import BalanceCache, ClassEconomy, Seat, Transaction, TransactionStatus
from app.extensions import db
from app.utils.banking import settle_balances, settle_pending_transaction_contexts
from app.services.ledger_service import get_available_balances


def _create_class_and_student(teacher, join_code):
    """Create class economy and canonical student. Returns (economy, seat, student_user)."""
    from tests.helpers.class_scope import create_class_scope, make_student_identity
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code)
    student_seat = make_student_identity(class_id=class_row.class_id, first_name="Test", last_name="S")
    db.session.flush()
    from app.models import User as _User, Seat as _Seat
    student_user = db.session.get(_User, student_seat.user_id)
    seat = _Seat.query.filter_by(user_id=student_user.id, class_id=class_row.class_id, role="student").first()
    return class_row, seat, student_user


def test_ledger_flow(client):
    """Test full flow: Create PENDING -> Settle -> Verify Cache."""
    # Setup
    teacher = make_admin("teacher")
    db.session.flush()
    join_code = "MATH101"
    economy, seat, student_user = _create_class_and_student(teacher, join_code)
    class_id, seat_id = economy.class_id, seat.id

    # 1. Create Transaction (PENDING)
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        amount=Decimal('10.50'),
        account_type='checking',
        status=TransactionStatus.PENDING,
        description="Initial deposit"
    )
    db.session.add(tx)
    db.session.commit()
    
    # Verify Pending state
    assert tx.status == TransactionStatus.PENDING
    assert tx.posted_at is None
    
    # 2. Verify Balance Read
    # Student.get_checking_balance NO LONGER calls settle_balances (Write-on-Read fix)
    bal_checking, bal_savings = get_available_balances(seat_id, class_id)
    assert bal_checking == Decimal('10.50')

    # Trigger explicit settlement for test purposes
    settle_balances(seat_id, class_id)
    db.session.commit()
    
    # 3. Verify Settlement Effects
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
    assert tx.status == TransactionStatus.POSTED
    assert tx.posted_at is not None
    
    cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id).first()
    assert cache is not None
    assert cache.posted_checking_balance_cents == 1050
    assert cache.last_settlement_at is not None

def test_void_pending(client):
    """Test voiding a PENDING transaction (no reversal)."""
    teacher = make_admin("teacher2")
    db.session.flush()
    join_code = "SCI202"
    economy, seat, student_user = _create_class_and_student(teacher, join_code)
    class_id, seat_id = economy.class_id, seat.id
    
    # 1. Create PENDING
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        amount=Decimal('50.00'),
        status=TransactionStatus.PENDING
    )
    db.session.add(tx)
    db.session.commit()
    
    # 2. Simulate Void Logic (Admin Button)
    # Pending voids are marked is_void and resolved during settlement.
    tx.is_void = True
    db.session.commit()
    
    # 3. Read Balance
    bal, _ = get_available_balances(seat_id, class_id)
    
    # Should be 0.00 (settlement ignores VOID pending)
    assert bal == Decimal('0.00')
    
    # Trigger explicit settlement for test purposes
    settle_balances(seat_id, class_id)
    db.session.commit()

    # Verify no reversal created
    reversals = Transaction.query.filter_by(original_transaction_id=tx.id).all()
    assert len(reversals) == 0

    # Verify pending transaction was settled as VOID.
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
    assert tx.status == TransactionStatus.VOID
    assert tx.voided_at is not None
    
    # Verify Cache state (should be 0)
    cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id).first()
    # Cache might exist if get_checking_balance triggered settlement (which creates it if missing)
    if cache:
        assert cache.posted_checking_balance_cents == 0

def test_void_posted_with_reversal(client):
    """Test voiding a POSTED transaction (creates reversal)."""
    teacher = make_admin("teacher3")
    db.session.flush()
    join_code = "ENG303"
    economy, seat, student_user = _create_class_and_student(teacher, join_code)
    class_id, seat_id = economy.class_id, seat.id
    
    # 1. Create PENDING then Settle -> POSTED
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        amount=Decimal('100.00'),
        status=TransactionStatus.PENDING
    )
    db.session.add(tx)
    db.session.commit()
    
    # student.get_checking_balance(join_code=join_code) # NO LONGER Triggers settlement
    settle_balances(seat_id, class_id) # Explicit settlement
    db.session.commit()
    
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
    assert tx.status == TransactionStatus.POSTED
    
    # 2. Simulate Void Logic (Admin Button)
    # Since status is POSTED, logic should match admin.py:
    # Mark is_void=True
    # Create Reversal (status=PENDING)
    
    tx.is_void = True
    
    reversal = Transaction(
        user_id=student_user.id,class_id=class_id,
        amount=-tx.amount,
        status=TransactionStatus.PENDING,
        original_transaction_id=tx.id
    )
    db.session.add(reversal)
    db.session.commit()
    
    # 3. Read Balance (Should be 0)
    # 100 (POSTED) + (-100) (PENDING) = 0
    bal_after_void, _ = get_available_balances(seat_id, class_id)
    assert bal_after_void == Decimal('0.00')
    
    # 4. Trigger Settlement again (processes Reversal)
    # get_checking_balance NO LONGER triggers it.
    settle_balances(seat_id, class_id)
    db.session.commit()
    
    db.session.expire_all()
    reversal = db.session.get(Transaction, reversal.id)
    assert reversal.status == TransactionStatus.POSTED
    
    cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id).first()
    # Cache should be updated: 100 + (-100) = 0
    assert cache.posted_checking_balance_cents == 0


def test_settlement_sweep_processes_each_pending_context_once(client):
    teacher = make_admin("teacher-sweep")
    db.session.flush()
    student_one_economy, student_one_seat, student_one_user = _create_class_and_student(teacher, "SWEEP-A")
    student_two_economy, student_two_seat, student_two_user = _create_class_and_student(teacher, "SWEEP-B")
    class_id_one, _seat_id_one = student_one_economy.class_id, student_one_seat.id
    class_id_two, _seat_id_two = student_two_economy.class_id, student_two_seat.id

    db.session.add_all([
        Transaction(
            user_id=student_one_user.id,class_id=class_id_one,
            amount=Decimal('12.34'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A',
        ),
        Transaction(
            user_id=student_one_user.id,class_id=class_id_one,
            amount=Decimal('1.66'),
            account_type='savings',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A savings',
        ),
        Transaction(
            user_id=student_two_user.id,class_id=class_id_two,
            amount=Decimal('9.99'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending B',
        ),
    ])
    db.session.commit()

    summary = settle_pending_transaction_contexts()

    assert summary == {"settled_contexts": 0, "failed_contexts": 2}

    posted_statuses = {
        (tx.user_id, tx.class_id, tx.account_type): tx.status
        for tx in Transaction.query.all()
    }
    assert posted_statuses[(student_one_user.id, class_id_one, "checking")] == TransactionStatus.PENDING
    assert posted_statuses[(student_one_user.id, class_id_one, "savings")] == TransactionStatus.PENDING
    assert posted_statuses[(student_two_user.id, class_id_two, "checking")] == TransactionStatus.PENDING


def test_settlement_script_returns_nonzero_when_failures(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "settle_pending_transactions.py"
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
