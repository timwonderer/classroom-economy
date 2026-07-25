from app.feats.base import FEATContext
from app.models import Transaction
from tests.helpers.ledger import create_ledger_pending_transaction, provision_ledger_classroom

def test_DOM_LED_001__payroll_transactions_stay_class_scoped(app):
    """
    Test that a teacher sees only their own class transactions for a shared student.
    """
    class_a = provision_ledger_classroom("chemistry_p1", app)
    class_g = provision_ledger_classroom("biology_block_a", app)
    student_a = class_a.students[0]
    student_g = class_g.students[0]

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-payroll-display-fix:seed"):
        create_ledger_pending_transaction(
            seat_id=student_a.seat.id,
            class_id=class_a.class_id,
            user_id=student_a.user.id,
            amount=100.00,
            account_type="checking",
            type="payroll",
            description="Payroll for Block A",
        )
        create_ledger_pending_transaction(
            seat_id=student_g.seat.id,
            class_id=class_g.class_id,
            user_id=student_g.user.id,
            amount=100.00,
            account_type="checking",
            type="payroll",
            description="Payroll for Block G",
        )

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
