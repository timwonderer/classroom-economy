
from decimal import Decimal
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import importlib.util
from pathlib import Path
import pytest
from app.models import BalanceCache, User, UserRole, Admin, ClassEconomy, Seat, IdentityProfile, Transaction, TransactionStatus
from app.extensions import db
from app.utils.banking import settle_balances, settle_pending_transaction_contexts


def _attach_seat(student, teacher, join_code, block="A"):
    economy = ClassEconomy(join_code=join_code, user_id=teacher.id, created_by_admin_id=teacher.id)
    db.session.add(economy)
    db.session.flush()
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=economy.class_id, join_code=join_code, block=block, role="student")
    db.session.add(seat)
    db.session.commit()
    return seat


def _scope_for_student(student, join_code):
    seat = Seat.query.filter_by(user_id=student_user.id, join_code=join_code).first()
    assert seat is not None
    assert seat.class_id is not None
    return seat.class_id, seat.id

def test_ledger_flow(client):
    """Test full flow: Create PENDING -> Settle -> Verify Cache."""
    # Setup
    student = make_student_identity(block="A", first_name="Test", last_name="S")
    teacher = make_admin("teacher", "secret")
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "MATH101"
    _attach_seat(student, teacher, join_code)
    class_id, seat_id = _scope_for_student(student, join_code)

    # 1. Create Transaction (PENDING)
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        join_code=join_code,
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
    bal = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
    assert bal == Decimal('10.50')

    # Trigger explicit settlement for test purposes
    settle_balances(student.id, join_code)
    db.session.commit()
    
    # 3. Verify Settlement Effects
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
    assert tx.status == TransactionStatus.POSTED
    assert tx.posted_at is not None
    
    cache = BalanceCache.query.filter_by(user_id=student_user.id, join_code=join_code).first()
    assert cache is not None
    assert cache.posted_checking_balance_cents == 1050
    assert cache.last_settlement_at is not None

def test_void_pending(client):
    """Test voiding a PENDING transaction (no reversal)."""
    student = make_student_identity(block="B", first_name="Test2", last_name="B")
    teacher = make_admin("teacher2", "secret")
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "SCI202"
    _attach_seat(student, teacher, join_code, block="B")
    class_id, seat_id = _scope_for_student(student, join_code)
    
    # 1. Create PENDING
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        join_code=join_code,
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
    bal = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
    
    # Should be 0.00 (settlement ignores VOID pending)
    assert bal == Decimal('0.00')
    
    # Trigger explicit settlement for test purposes
    settle_balances(student.id, join_code)
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
    cache = BalanceCache.query.filter_by(user_id=student_user.id, join_code=join_code).first()
    # Cache might exist if get_checking_balance triggered settlement (which creates it if missing)
    if cache:
        assert cache.posted_checking_balance_cents == 0

def test_void_posted_with_reversal(client):
    """Test voiding a POSTED transaction (creates reversal)."""
    student = make_student_identity(block="C", first_name="Test3", last_name="C")
    teacher = make_admin("teacher3", "secret")
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "ENG303"
    _attach_seat(student, teacher, join_code, block="C")
    class_id, seat_id = _scope_for_student(student, join_code)
    
    # 1. Create PENDING then Settle -> POSTED
    tx = Transaction(
        user_id=student_user.id,class_id=class_id,
        join_code=join_code,
        amount=Decimal('100.00'),
        status=TransactionStatus.PENDING
    )
    db.session.add(tx)
    db.session.commit()
    
    # student.get_checking_balance(join_code=join_code) # NO LONGER Triggers settlement
    settle_balances(student.id, join_code) # Explicit settlement
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
        join_code=join_code,
        amount=-tx.amount,
        status=TransactionStatus.PENDING,
        original_transaction_id=tx.id
    )
    db.session.add(reversal)
    db.session.commit()
    
    # 3. Read Balance (Should be 0)
    # 100 (POSTED) + (-100) (PENDING) = 0
    bal_after_void = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
    assert bal_after_void == Decimal('0.00')
    
    # 4. Trigger Settlement again (processes Reversal)
    # get_checking_balance NO LONGER triggers it.
    settle_balances(student.id, join_code)
    db.session.commit()
    
    db.session.expire_all()
    reversal = db.session.get(Transaction, reversal.id)
    assert reversal.status == TransactionStatus.POSTED
    
    cache = BalanceCache.query.filter_by(user_id=student_user.id, join_code=join_code).first()
    # Cache should be updated: 100 + (-100) = 0
    assert cache.posted_checking_balance_cents == 0


def test_settlement_sweep_processes_each_pending_context_once(client):
    teacher = make_admin("teacher-sweep", "secret")
    student_one = make_student_identity(block="A", first_name="Sweep", last_name="A")
    student_two = make_student_identity(block="B", first_name="Sweep", last_name="B")
    db.session.add(teacher)
    db.session.commit()
    _attach_seat(student_one, teacher, "SWEEP-A", block="A")
    _attach_seat(student_two, teacher, "SWEEP-B", block="B")
    class_id_one, _seat_id_one = _scope_for_student(student_one, "SWEEP-A")
    class_id_two, _seat_id_two = _scope_for_student(student_two, "SWEEP-B")

    db.session.add_all([
        Transaction(
            user_id=student_one_user.id,class_id=class_id_one,
            join_code="SWEEP-A",
            amount=Decimal('12.34'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A',
        ),
        Transaction(
            user_id=student_one_user.id,class_id=class_id_one,
            join_code="SWEEP-A",
            amount=Decimal('1.66'),
            account_type='savings',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A savings',
        ),
        Transaction(
            user_id=student_two_user.id,class_id=class_id_two,
            join_code="SWEEP-B",
            amount=Decimal('9.99'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending B',
        ),
    ])
    db.session.commit()

    summary = settle_pending_transaction_contexts()

    assert summary == {"settled_contexts": 2, "failed_contexts": 0}

    posted_statuses = {
        (tx.student_id, tx.join_code, tx.account_type): tx.status
        for tx in Transaction.query.all()
    }
    assert posted_statuses[(student_one.id, "SWEEP-A", "checking")] == TransactionStatus.POSTED
    assert posted_statuses[(student_one.id, "SWEEP-A", "savings")] == TransactionStatus.POSTED
    assert posted_statuses[(student_two.id, "SWEEP-B", "checking")] == TransactionStatus.POSTED

    cache_one = BalanceCache.query.filter_by(user_id=student_one_user.id, join_code="SWEEP-A").first()
    cache_two = BalanceCache.query.filter_by(user_id=student_two_user.id, join_code="SWEEP-B").first()
    assert cache_one.posted_checking_balance_cents == 1234
    assert cache_one.posted_savings_balance_cents == 166
    assert cache_two.posted_checking_balance_cents == 999


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
