import pytest
from flask import session
from unittest.mock import patch

from app.models import Seat, User, UserRole
from app.services.context_resolver import (
    CanonicalContext,
    ContextForbidden,
    ContextInvariantViolation,
    ContextMismatch,
    ContextNotEstablished,
    resolve_canonical_context,
)


def _seed_request_session(*, user_id=1, nonce="nonce"):
    session["user_id"] = user_id
    session["current_session_nonce"] = nonce


class _SeatQueryStub:
    def __init__(self, seat):
        self._seat = seat

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._seat


@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_rejects_sysadmin(mock_get, app):
    with app.test_request_context():
        session["is_system_admin"] = True
        with pytest.raises(ContextForbidden, match="System administrators cannot possess Class Context."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_missing_keys(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        with pytest.raises(ContextNotEstablished, match="Missing session nonce."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_missing_scope_fails_closed(mock_get, app):
    with app.test_request_context():
        session["user_id"] = 1
        with pytest.raises(ContextNotEstablished, match="Missing session nonce."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_invalid_format(mock_get, app):
    with app.test_request_context():
        session["user_id"] = "not-an-int"
        session["current_session_nonce"] = "nonce"
        with pytest.raises(ContextNotEstablished, match="Invalid format for user_id."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.query")
@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_seat_not_found(mock_get, mock_query, app):
    with app.test_request_context():
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", last_active_class_id="some-uuid")
            return None
        mock_get.side_effect = fake_get
        mock_query.return_value = _SeatQueryStub(None)
        with pytest.raises(ContextNotEstablished, match="Seat not found."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.query")
@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_seat_unclaimed(mock_get, mock_query, app):
    with app.test_request_context():
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", last_active_class_id="some-uuid")
            if model is Seat:
                return Seat(id=1, user_id=1, class_id="some-uuid", role="student", claimed_at=None)
            return None
        mock_get.side_effect = fake_get
        mock_query.return_value = _SeatQueryStub(Seat(id=1, user_id=1, class_id="some-uuid", role="student", claimed_at=None))
        with pytest.raises(ContextNotEstablished, match="Seat is not claimed."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.query")
@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_class_mismatch(mock_get, mock_query, app):
    with app.test_request_context():
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", last_active_class_id="some-uuid")
            if model is Seat:
                return Seat(id=1, user_id=1, class_id="different-uuid", claimed_at="2023-01-01")
            return None
        mock_get.side_effect = fake_get
        mock_query.return_value = _SeatQueryStub(None)
        with pytest.raises(ContextNotEstablished, match="Seat not found."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.query")
@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_user_mismatch(mock_get, mock_query, app):
    with app.test_request_context():
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", last_active_class_id="some-uuid")
            if model is Seat:
                return Seat(id=1, user_id=2, class_id="some-uuid", claimed_at="2023-01-01")
            return None
        mock_get.side_effect = fake_get
        mock_query.return_value = _SeatQueryStub(None)
        with pytest.raises(ContextNotEstablished, match="Seat not found."):
            resolve_canonical_context()


@patch("app.services.context_resolver.db.session.query")
@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_success(mock_get, mock_query, app):
    with app.test_request_context():
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", last_active_class_id="some-uuid")
            if model is Seat:
                return Seat(id=1, user_id=1, class_id="some-uuid", claimed_at="2023-01-01", role="student")
            return None
        mock_get.side_effect = fake_get
        mock_query.return_value = _SeatQueryStub(Seat(id=1, user_id=1, class_id="some-uuid", claimed_at="2023-01-01", role="student"))
        context = resolve_canonical_context()
        assert context.user_id == 1
        assert context.class_id == "some-uuid"
        assert context.seat_id == 1
        assert context.actor_role == "student"


@patch("app.services.context_resolver.db.session.get")
def test_resolve_canonical_context_teacher_exception_returns_none(mock_get, app):
    with app.test_request_context("/admin/onboarding", method="GET"):
        _seed_request_session()
        def fake_get(model, ident):
            if model is User:
                return User(id=1, current_session_nonce="nonce", user_role=UserRole.TEACHER, last_active_class_id=None)
            return None
        mock_get.side_effect = fake_get
        assert resolve_canonical_context() is None


def test_canonical_context_guards():
    context = CanonicalContext(user_id=1, class_id="uuid", seat_id=1, actor_role="student")

    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access join_code"):
        _ = context.join_code

    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access teacher_id"):
        _ = context.teacher_id

    with pytest.raises(AttributeError, match="Strict context invariant violation: cannot access student_id"):
        _ = context.student_id
