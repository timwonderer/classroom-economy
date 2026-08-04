"""
Canonical Classroom Initializer 
docs/SPEC/SPEC-TEST-001_CANONICAL_TEST_INITIALIZER.md
docs/SPEC/SPEC-TEST-002_CANONICAL_TEST_IDENTITIES.md

The single entry point for any test that requires class scope, teacher identity,
or student identity. No test may construct identity, scope, or context through
any other path.

Initialization order:
  1. provision_classroom() — calls production code to build teacher + class + students
  2. DB self-test         — re-queries every entity from the DB and verifies all
                            constitutional invariants hold
  3. (optional) session   — login_teacher() or login_student() sets Flask session
  4. Context self-test    — resolve_canonical_context() is called inside a real
                            request context and its output is verified against
                            the provisioned state

If any self-test assertion fails the test is aborted immediately via pytest.fail().
A test with an invalid identity, scope, or context must never run.

Usage:

    def test_something(client, app):
        classroom = initialize_as_teacher("chemistry_p1", client, app)
        # teacher session is live, context is verified

    def test_student(client, app):
        classroom, student = initialize_as_student("chemistry_p1", client, app)
        # student[0] session is live, context is verified

    def test_db_only(app):
        classroom = initialize("chemistry_p1", app)
        # no session; DB state verified
"""

from __future__ import annotations

import pytest
from flask import Flask, session as flask_session

from app.extensions import db
from app.models import ClassEconomy, IdentityProfile, Seat, User, UserRole
from app.services.context_resolver import CanonicalContext, resolve_canonical_context
from tests.helpers.canonical_classroom import (
    ProvisionedClassroom,
    ProvisionedStudent,
    login_student,
    login_teacher,
    provision_classroom,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize(classroom_key: str, app: Flask) -> ProvisionedClassroom:
    """Provision a classroom and run the DB self-test.

    Use when a test needs DB state but no active session
    (e.g. unit tests on services or models).
    """
    classroom = provision_classroom(classroom_key)
    _assert_db_invariants(classroom)
    return classroom


def initialize_as_teacher(
    classroom_key: str,
    client,
    app: Flask,
) -> ProvisionedClassroom:
    """Provision, DB self-test, establish teacher session, context self-test."""
    classroom = provision_classroom(classroom_key)
    _assert_db_invariants(classroom)
    login_teacher(client, classroom)
    _assert_nonce_integrity(client, classroom.teacher_user)
    _assert_canonical_context(
        app,
        client,
        expected_user_id=classroom.teacher_user.id,
        expected_class_id=classroom.class_id,
        expected_seat_id=classroom.teacher_seat.id,
        expected_role="teacher",
    )
    return classroom


def initialize_as_student(
    classroom_key: str,
    client,
    app: Flask,
    student_index: int = 0,
) -> tuple[ProvisionedClassroom, ProvisionedStudent]:
    """Provision, DB self-test, establish student[student_index] session, context self-test."""
    classroom = provision_classroom(classroom_key)
    _assert_db_invariants(classroom)
    student = classroom.students[student_index]
    login_student(client, student)
    _assert_nonce_integrity(client, student.user)
    _assert_canonical_context(
        app,
        client,
        expected_user_id=student.user.id,
        expected_class_id=classroom.class_id,
        expected_seat_id=student.seat.id,
        expected_role="student",
    )
    return classroom, student


# ---------------------------------------------------------------------------
# DB self-test
# ---------------------------------------------------------------------------

def _assert_db_invariants(classroom: ProvisionedClassroom) -> None:
    """Re-query every entity from the DB and verify all constitutional invariants.

    Fails the test immediately if any invariant is violated.
    """
    _check(classroom.class_id, "ClassEconomy.class_id is not set")
    _check(classroom.join_code, "ClassEconomy.join_code is not set")

    # Re-query economy
    economy = db.session.get(ClassEconomy, classroom.class_id)
    _check(economy is not None, f"ClassEconomy not found in DB for class_id={classroom.class_id}")
    _check(
        economy.user_id == classroom.teacher_user.id,
        f"ClassEconomy.user_id {economy.user_id} != teacher user_id {classroom.teacher_user.id}",
    )

    # Re-query teacher user
    teacher = db.session.get(User, classroom.teacher_user.id)
    _check(teacher is not None, f"Teacher User not found in DB for id={classroom.teacher_user.id}")
    _check(
        teacher.user_role == UserRole.TEACHER,
        f"Teacher User.user_role is {teacher.user_role}, expected TEACHER",
    )
    _check(teacher.username_hash is not None, "Teacher User.username_hash is None")
    _check(
        teacher.last_active_class_id == classroom.class_id,
        f"Teacher last_active_class_id {teacher.last_active_class_id} != {classroom.class_id}",
    )
    _check(
        teacher.last_active_seat_id == classroom.teacher_seat.id,
        f"Teacher last_active_seat_id {teacher.last_active_seat_id} != teacher_seat.id {classroom.teacher_seat.id}",
    )

    # Re-query teacher seat
    teacher_seat = db.session.get(Seat, classroom.teacher_seat.id)
    _check(teacher_seat is not None, f"Teacher Seat not found in DB for id={classroom.teacher_seat.id}")
    _check(teacher_seat.role == "teacher", f"Teacher Seat.role is {teacher_seat.role!r}, expected 'teacher'")
    _check(
        teacher_seat.user_id == classroom.teacher_user.id,
        f"Teacher Seat.user_id {teacher_seat.user_id} != teacher user_id {classroom.teacher_user.id}",
    )
    _check(
        teacher_seat.class_id == classroom.class_id,
        f"Teacher Seat.class_id {teacher_seat.class_id} != {classroom.class_id}",
    )

    # Re-query each student
    for i, student in enumerate(classroom.students):
        prefix = f"Student[{i}] ({student.first_name} {student.last_name})"

        user = db.session.get(User, student.user.id)
        _check(user is not None, f"{prefix} User not found in DB")
        _check(
            user.user_role == UserRole.STUDENT,
            f"{prefix} User.user_role is {user.user_role}, expected STUDENT",
        )
        _check(user.username_hash is not None, f"{prefix} User.username_hash is None")
        _check(user.pin_hash is not None, f"{prefix} User.pin_hash is None")
        _check(user.passphrase_hash is not None, f"{prefix} User.passphrase_hash is None")
        _check(
            user.last_active_class_id == classroom.class_id,
            f"{prefix} User.last_active_class_id {user.last_active_class_id} != {classroom.class_id}",
        )
        _check(
            user.last_active_seat_id == student.seat.id,
            f"{prefix} User.last_active_seat_id {user.last_active_seat_id} != seat.id {student.seat.id}",
        )

        seat = db.session.get(Seat, student.seat.id)
        _check(seat is not None, f"{prefix} Seat not found in DB")
        _check(seat.role == "student", f"{prefix} Seat.role is {seat.role!r}, expected 'student'")
        _check(
            seat.user_id == student.user.id,
            f"{prefix} Seat.user_id {seat.user_id} != user.id {student.user.id}",
        )
        _check(
            seat.class_id == classroom.class_id,
            f"{prefix} Seat.class_id {seat.class_id} != {classroom.class_id}",
        )
        _check(seat.claimed_at is not None, f"{prefix} Seat.claimed_at is None — seat is unclaimed")
        _check(seat.claim_first_name_hash is not None, f"{prefix} Seat.claim_first_name_hash is None")
        _check(seat.claim_last_name_hash is not None, f"{prefix} Seat.claim_last_name_hash is None")
        _check(seat.roster_fingerprint is not None, f"{prefix} Seat.roster_fingerprint is None")

        profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
        _check(profile is not None, f"{prefix} IdentityProfile not found for seat_id={seat.id}")
        _check(
            profile.class_id == classroom.class_id,
            f"{prefix} IdentityProfile.class_id {profile.class_id} != {classroom.class_id}",
        )
        _check(
            profile.first_name == student.first_name,
            f"{prefix} IdentityProfile.first_name {profile.first_name!r} != {student.first_name!r}",
        )
        _check(
            profile.last_name == student.last_name,
            f"{prefix} IdentityProfile.last_name {profile.last_name!r} != {student.last_name!r}",
        )


# ---------------------------------------------------------------------------
# Session + context self-test
# ---------------------------------------------------------------------------

def _assert_nonce_integrity(client, user: User) -> None:
    """Verify the session nonce matches the DB nonce.

    This is the same gate that validate_canonical_session_nonce() enforces on
    every request. If these don't match, the before_request hook clears the
    session and resolve_canonical_context() will raise ContextNotEstablished.
    """
    with client.session_transaction() as sess:
        session_nonce = sess.get("current_session_nonce")

    _check(session_nonce is not None, "session['current_session_nonce'] is not set after login")

    fresh_user = db.session.get(User, user.id)
    _check(fresh_user is not None, f"User id={user.id} not found when checking nonce")
    _check(
        fresh_user.current_session_nonce == session_nonce,
        f"Nonce mismatch: session has {session_nonce!r}, "
        f"DB has {fresh_user.current_session_nonce!r}. "
        "The before_request hook would clear this session.",
    )


def _assert_canonical_context(
    app: Flask,
    client,
    *,
    expected_user_id: int,
    expected_class_id: str,
    expected_seat_id: int,
    expected_role: str,
) -> None:
    """Call resolve_canonical_context() inside a real request context and verify its output.

    Uses the session keys written by login_teacher() / login_student() so the
    check is identical to what production resolves on every authenticated request.
    """
    with client.session_transaction() as sess:
        session_snapshot = dict(sess)

    with app.test_request_context("/"):
        for key, value in session_snapshot.items():
            flask_session[key] = value

        try:
            ctx = resolve_canonical_context()
        except Exception as exc:
            pytest.fail(
                f"[Initializer] resolve_canonical_context() raised {type(exc).__name__}: {exc}\n"
                f"Session keys present: {list(session_snapshot.keys())}"
            )

        _check(
            isinstance(ctx, CanonicalContext),
            f"Expected CanonicalContext, got {type(ctx).__name__}. "
            "Actor may lack a class scope (BoundaryContext returned instead).",
        )
        _check(
            ctx.user_id == expected_user_id,
            f"context.user_id={ctx.user_id} != expected {expected_user_id}",
        )
        _check(
            ctx.class_id == expected_class_id,
            f"context.class_id={ctx.class_id!r} != expected {expected_class_id!r}",
        )
        _check(
            ctx.seat_id == expected_seat_id,
            f"context.seat_id={ctx.seat_id} != expected {expected_seat_id}",
        )
        _check(
            ctx.actor_role == expected_role,
            f"context.actor_role={ctx.actor_role!r} != expected {expected_role!r}",
        )


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _check(condition: bool, message: str) -> None:
    """Fail the current test immediately if condition is False.

    Uses pytest.fail() so the failure is reported as a test failure (not an
    error), and the message clearly identifies it as an initializer violation.
    """
    if not condition:
        pytest.fail(f"[Initializer self-test failed] {message}")
