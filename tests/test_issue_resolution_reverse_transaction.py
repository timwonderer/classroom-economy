from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
from app.feats.base import FEATContext
from app.extensions import db
from app.models import User, UserRole, ClassEconomy, IdentityProfile, Issue, IssueCategory, Seat, Transaction, TransactionStatus
from tests.helpers.admin_context import login_teacher
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, user_id):
    teacher = db.session.get(User, user_id)
    assert teacher is not None
    class_row = ClassEconomy.query.filter_by(user_id=user_id).order_by(ClassEconomy.class_id.asc()).first()
    assert class_row is not None
    login_teacher(client, teacher, class_id=class_row.class_id)


def _build_issue_context():
    teacher = seed_canonical_admin("teacher_issue_reverse").user
    db.session.flush()

    with FEATContext("FEAT-IDEN-001", idempotency_key="issue_reverse:create_classes"):
        class_a = create_class_scope(teacher_user=teacher, join_code="ISSUEA1", display_name="Issue A")
        class_b = create_class_scope(teacher_user=teacher, join_code="ISSUEB1", display_name="Issue B")
        db.session.flush()

        student_user = User(
            user_role=UserRole.STUDENT,
            username_hash="student-issue-hash",
            username_lookup_hash="student-issue-lookup",
        )
        db.session.add(student_user)
        db.session.flush()

        seat = Seat(
            user_id=student_user.id,
            class_id=class_a.class_id,
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(seat)
        db.session.flush()

        profile = IdentityProfile(profile_type="student", first_name="Ivy", last_name="R")
        profile.seat_id = seat.id
        db.session.add(profile)

        category = IssueCategory(
            name=f"Issue Reverse Category {datetime.now(timezone.utc).isoformat()}",
            category_type="transaction",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()
    db.session.commit()
    return teacher, student_user, seat, category, class_a, class_b


def test_issue_reverse_transaction_creates_reversal_for_posted_tx(client):
    teacher, student_user, seat, category, class_a, _class_b = _build_issue_context()

    with FEATContext("FEAT-LED-001", idempotency_key="issue_reverse:posted_tx"):
        tx = Transaction(
            user_id=student_user.id,
            class_id=class_a.class_id,
            amount=Decimal("30.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="deposit",
            description="Posted deposit",
        )
        db.session.add(tx)
        db.session.flush()

        issue = Issue(
            user_id=student_user.id,
            actor_public_id=seat.public_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            join_code="ISSUEA1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Please reverse this.",
            related_transaction_id=tx.id,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()

    _login_admin(client, teacher.id)
    response = client.post(
        f"/admin/issues/{issue.id}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Valid request"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db.session.refresh(tx)
    assert tx.is_void is True
    assert tx.status == TransactionStatus.POSTED
    assert tx.reversal_transaction_id is not None

    reversal = db.session.get(Transaction, tx.reversal_transaction_id)
    assert reversal is not None
    assert reversal.original_transaction_id == tx.id
    assert reversal.status == TransactionStatus.PENDING
    assert reversal.class_id == class_a.class_id
    assert reversal.amount == Decimal("-30.00")


def test_issue_reverse_transaction_rejects_scope_mismatch(client):
    teacher, student_user, seat, category, class_a, class_b = _build_issue_context()

    with FEATContext("FEAT-LED-001", idempotency_key="issue_reverse:scope_mismatch"):
        mismatch_seat = Seat(
            user_id=student_user.id,
            class_id=class_b.class_id,
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(mismatch_seat)
        db.session.flush()

        tx = Transaction(
            user_id=student_user.id,
            class_id=class_b.class_id,
            seat_id=mismatch_seat.id,
            amount=Decimal("20.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="deposit",
            description="Wrong-scope deposit",
        )
        db.session.add(tx)
        db.session.flush()

        issue = Issue(
            user_id=student_user.id,
            actor_public_id=seat.public_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            join_code="ISSUEA1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Please reverse this.",
            related_transaction_id=tx.id,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()

    _login_admin(client, teacher.id)
    response = client.post(
        f"/admin/issues/{issue.id}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Attempt mismatch"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/admin/issues/{issue.id}" in response.location

    db.session.refresh(tx)
    assert tx.is_void is False
    assert tx.reversal_transaction_id is None
