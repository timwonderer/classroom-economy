from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, ClassEconomy, IdentityProfile, Issue, IssueCategory, Student, StudentTeacher, Transaction, TransactionStatus


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _build_issue_context():
    teacher = make_admin("teacher_issue_reverse", "secret")
    db.session.add(teacher)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Ivy", last_name="R")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.add_all([
        ClassEconomy(join_code="ISSUEA1", teacher_id=teacher.id, status="active", created_by_admin_id=teacher.id),
        ClassEconomy(join_code="ISSUEB1", teacher_id=teacher.id, status="active", created_by_admin_id=teacher.id),
    ])
    category = IssueCategory(
        name=f"Issue Reverse Category {datetime.now(timezone.utc).isoformat()}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.commit()
    return teacher, student, category


def test_issue_reverse_transaction_creates_reversal_for_posted_tx(client):
    teacher, student, category = _build_issue_context()

    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="ISSUEA1",
        amount=Decimal("30.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="deposit",
        description="Posted deposit",
    )
    db.session.add(tx)
    db.session.flush()

    issue = Issue(
        student_id=student.id,
        actor_public_id="seat-public-issue-1",
        teacher_id=teacher.id,
        join_code="ISSUEA1",
        category_id=category.id,
        issue_type="transaction",
        student_explanation="Please reverse this.",
        related_transaction_id=tx.id,
    )
    db.session.add(issue)
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
    assert reversal.join_code == "ISSUEA1"
    assert reversal.amount == Decimal("-30.00")


def test_issue_reverse_transaction_rejects_scope_mismatch(client):
    teacher, student, category = _build_issue_context()

    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="ISSUEB1",
        amount=Decimal("20.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="deposit",
        description="Wrong-scope deposit",
    )
    db.session.add(tx)
    db.session.flush()

    issue = Issue(
        student_id=student.id,
        actor_public_id="seat-public-issue-2",
        teacher_id=teacher.id,
        join_code="ISSUEA1",
        category_id=category.id,
        issue_type="transaction",
        student_explanation="Please reverse this.",
        related_transaction_id=tx.id,
    )
    db.session.add(issue)
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
