import pytest
from flask import session
from unittest.mock import patch
from app.services.context_resolver import (
    resolve_canonical_context,
    CanonicalContext,
    ContextNotEstablished,
    ContextForbidden,
    ContextMismatch,
    ContextInvariantViolation,
)
from app.models import Seat, User, UserRole

def test_resolve_canonical_context_rejects_sysadmin(app):
    with app.test_request_context():
        session["is_system_admin"] = True
        with pytest.raises(ContextForbidden, match="System administrators cannot possess Class Context."):
            resolve_canonical_context()

def test_resolve_canonical_context_missing_keys(app):
    with app.test_request_context():
        session["user_id"] = 1
        with pytest.raises(ContextInvariantViolation, match="Missing canonical class_id or seat_id in session."):
            resolve_canonical_context()

def test_resolve_canonical_context_missing_scope_fails_closed(app):
    with app.test_request_context():
        session["user_id"] = 1
        with pytest.raises(ContextInvariantViolation, match="Missing canonical class_id or seat_id in session."):
            resolve_canonical_context()

def test_resolve_canonical_context_invalid_format(app):
    with app.test_request_context():
        session["user_id"] = "not-an-int"
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = "not-an-int"
        with pytest.raises(ContextNotEstablished, match="Invalid format for user_id or seat_id."):
            resolve_canonical_context()

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_seat_not_found(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = 999
        mock_get.return_value = None
        with pytest.raises(ContextNotEstablished, match="Seat not found."):
            resolve_canonical_context()

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_seat_unclaimed(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = 1
        mock_seat = Seat(id=1, user_id=1, class_id="some-uuid", role="student", claimed_at=None)
        mock_get.return_value = mock_seat
        with pytest.raises(ContextNotEstablished, match="Seat is not claimed."):
            resolve_canonical_context()

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_class_mismatch(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = 1
        mock_seat = Seat(id=1, user_id=1, class_id="different-uuid", claimed_at="2023-01-01")
        mock_get.return_value = mock_seat
        with pytest.raises(ContextMismatch, match="Seat 1 does not belong to class some-uuid."):
            resolve_canonical_context()

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_user_mismatch(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = 1
        mock_seat = Seat(id=1, user_id=2, class_id="some-uuid", claimed_at="2023-01-01")
        mock_get.return_value = mock_seat
        with pytest.raises(ContextMismatch, match="User 1 does not own seat 1."):
            resolve_canonical_context()

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_success(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        session["current_class_id"] = "some-uuid"
        session["current_seat_id"] = 1
        mock_seat = Seat(id=1, user_id=1, class_id="some-uuid", claimed_at="2023-01-01", role="student")
        mock_get.return_value = mock_seat
        context = resolve_canonical_context()
        assert context.user_id == 1
        assert context.class_id == "some-uuid"
        assert context.seat_id == 1
        assert context.actor_role == "student"

@patch("app.extensions.db.session.get")
def test_resolve_canonical_context_teacher_exception_returns_none(mock_get, app):
    with app.test_request_context("/admin/onboarding", method="GET"):
        session["user_id"] = 1
        session["current_class_id"] = None
        session["current_seat_id"] = None
        mock_get.return_value = type("UserStub", (), {"user_role": UserRole.TEACHER})()
        assert resolve_canonical_context() is None

def test_canonical_context_guards():
    context = CanonicalContext(user_id=1, class_id="uuid", seat_id=1, actor_role="student")
    
    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access join_code"):
        _ = context.join_code
        
    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access teacher_id"):
        _ = context.teacher_id
        
    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access student_id"):
        _ = context.student_id
