from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pyotp

from app.extensions import db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import IdentityProfile, Issue, IssueCategory, Seat, Transaction, TransactionStatus
from app.models import User
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher


def teacher_issue_lifecycle(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with FEATContext("FEAT-ADMN-001", idempotency_key="issue_lifecycle:seed"):
        category = IssueCategory(
            name="Lifecycle Category",
            category_type="general",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()
        issue = Issue(
            user_id=classroom.students[0].user.id,
            actor_public_id=classroom.students[0].seat.public_id,
            class_id=classroom.class_id,
            seat_id=classroom.students[0].seat.id,
            class_label="Block A",
            category_id=category.id,
            issue_type="general",
            student_explanation="Balance looked incorrect after store purchase.",
            status=Issue.STATUS_TEACHER_REVIEW,
        )
        db.session.add(issue)
        db.session.flush()
    return classroom, issue


def payroll_visibility_state(client, app):
    classroom_a, student_a = initialize_as_student("chemistry_p1", client, app)
    classroom_g = initialize("biology_block_a", app)
    student_g = classroom_g.students[0]

    tx_a = Transaction(
        user_id=student_a.user.id,
        class_id=classroom_a.class_id,
        seat_id=student_a.seat.id,
        target_seat_id=student_a.seat.id,
        actor_seat_id=student_a.seat.id,
        mechanism="self",
        amount=100.00,
        type="payroll",
        timestamp=datetime.now(timezone.utc),
        description="Payroll for Block A",
    )
    tx_g = Transaction(
        user_id=student_g.user.id,
        class_id=classroom_g.class_id,
        seat_id=student_g.seat.id,
        target_seat_id=student_g.seat.id,
        actor_seat_id=student_g.seat.id,
        mechanism="self",
        amount=100.00,
        type="payroll",
        timestamp=datetime.now(timezone.utc),
        description="Payroll for Block G",
    )
    db.session.add_all([tx_a, tx_g])
    db.session.flush()
    return classroom_a, classroom_g


def issue_reverse_state(client, app):
    classroom_a = initialize_as_teacher("chemistry_p1", client, app)
    classroom_b = initialize("ap_csp_p3", app)
    student = classroom_a.students[0]
    mismatch_seat = Seat(
        user_id=student.user.id,
        class_id=classroom_b.class_id,
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(mismatch_seat)
    db.session.flush()
    db.session.add(
        IdentityProfile(
            seat_id=mismatch_seat.id,
            class_id=classroom_b.class_id,
            profile_type="student_claimed",
            first_name=student.first_name,
            last_name=student.last_name,
        )
    )
    category = IssueCategory(
        name=f"Issue Reverse Category {datetime.now(timezone.utc).isoformat()}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    with FEATContext("FEAT-LED-001", idempotency_key="issue_reverse:posted_tx"):
        tx = Transaction(
            user_id=student.user.id,
            class_id=classroom_a.class_id,
            seat_id=student.seat.id,
            target_seat_id=student.seat.id,
            actor_seat_id=student.seat.id,
            mechanism="self",
            amount=Decimal("30.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="deposit",
            description="Posted deposit",
        )
        db.session.add(tx)
        db.session.flush()
        issue = Issue(
            user_id=student.user.id,
            actor_public_id=student.seat.public_id,
            class_id=student.seat.class_id,
            seat_id=student.seat.id,
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Please reverse this.",
            related_transaction_id=tx.id,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()
    return classroom_a, classroom_b, student, issue, tx


def sysadmin_reward_issue_state(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    category = IssueCategory(
        name="Bug Report Category",
        category_type="general",
        is_active=True,
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key="sysadmin_issue_reward:category"):
        db.session.add(category)
        db.session.flush()
    with FEATContext("FEAT-TEST-001", idempotency_key="sysadmin_issue_reward:issue"):
        issue = Issue(
            user_id=student.user.id,
            actor_public_id=student.seat.public_id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            class_label="Block A",
            category_id=category.id,
            issue_type="general",
            student_explanation="Found a reproducible bug in the app.",
            student_expected_outcome="Expected behavior should work.",
            status=Issue.STATUS_ESCALATED_TO_DEV,
            eligible_for_reward=True,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()
    return classroom, student, issue


def create_sysadmin_via_cli(app, username: str = "sysadmin"):
    result = app.test_cli_runner().invoke(args=["create-sysadmin"], input=f"{username}\n")
    if result.exit_code != 0:
        raise RuntimeError(result.output)
    secret = ""
    lines = result.output.splitlines()
    for idx, line in enumerate(lines):
        if "TOTP SECRET" in line:
            for candidate in lines[idx + 1 :]:
                stripped = candidate.strip()
                if stripped and not stripped.startswith("=") and "IMPORTANT:" not in stripped and "Manual entry URI" not in stripped:
                    secret = stripped
                    break
            break
    if not secret:
        raise RuntimeError(result.output)
    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    if user is None:
        raise RuntimeError(result.output)
    return user, secret


def login_sysadmin(client, username: str, totp_secret: str):
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(totp_secret).now()},
        follow_redirects=True,
    )
