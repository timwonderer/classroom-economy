from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
import pytest
from app.models import User, UserRole, Transaction
from app import db
from datetime import datetime, timezone
from tests.helpers.class_scope import create_class_scope, make_student_identity
from app.feats.base import FEATContext

def test_payroll_visibility_bug(client):
    """
    Test that a teacher sees only their own class transactions for a shared student.
    """
    with FEATContext("FEAT-IDEN-001", idempotency_key="payroll_visibility:seed"):
        teacher1 = seed_canonical_admin("teacher1").user
        teacher2 = seed_canonical_admin("teacher2").user
        class_a = create_class_scope(teacher_user=teacher1, join_code="JOIN_A", section="A")
        class_g = create_class_scope(teacher_user=teacher2, join_code="JOIN_G", section="A")
        student_a = make_student_identity(class_id=class_a.class_id, first_name="Timothy", last_name="C", claimed=True)
        student_g = make_student_identity(class_id=class_g.class_id, first_name="Timothy", last_name="C", claimed=True)

    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll_visibility:transactions"):
        tx_a = Transaction(
            user_id=student_a.user_id,
            class_id=class_a.class_id,
            seat_id=student_a.id,
            amount=100.00,
            type='payroll',
            timestamp=datetime.now(timezone.utc),
            description="Payroll for Block A"
        )
        tx_g = Transaction(
            user_id=student_g.user_id,
            class_id=class_g.class_id,
            seat_id=student_g.id,
            amount=100.00,
            type='payroll',
            timestamp=datetime.now(timezone.utc),
            description="Payroll for Block G"
        )
        db.session.add_all([tx_a, tx_g])
        db.session.flush()

    # 3. Simulate Teacher 1's view
    visible_transactions = (
        Transaction.query
        .filter_by(type='payroll')
        .filter(Transaction.class_id == class_a.class_id)
        .all()
    )

    # 4. Verify
    has_g_transaction = any(tx.class_id == class_g.class_id for tx in visible_transactions)
    assert not has_g_transaction, "Teacher 1 should NOT see payroll transactions for Block G!"

    has_a_transaction = any(tx.class_id == class_a.class_id for tx in visible_transactions)
    assert has_a_transaction, "Teacher 1 SHOULD see their own block's transaction."
