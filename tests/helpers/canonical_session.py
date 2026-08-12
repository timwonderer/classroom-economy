"""
STOP! READ SPEC-TEST-001 AND SPEC-TEST-002 BEFORE USING THIS HELPER.

Test helper that sets up canonical session context the same way production does.

Production login (student.py claim flow) writes:
  - session["user_id"]
  - session["current_session_nonce"]  — validated by validate_canonical_session_nonce()
  - user.current_session_nonce        — DB-side nonce mirror
  - user.last_active_class_id         — canonical class pointer
  - user.last_active_seat_id          — canonical seat pointer

resolve_canonical_context() reads session["user_id"] then resolves
class/seat from the two DB columns. validate_canonical_session_nonce()
(before_request) clears the session if the nonce doesn't match, which
would make resolve_canonical_context() fail — so we must write the nonce too.
"""

import secrets
from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, User


def set_canonical_context(
    sess,
    *,
    user_id: int,
    class_id: str,
    seat_id: int,
    role: str,          # kept for call-site compatibility; not written anywhere
    nonce: str | None = None,
) -> str:
    """Set up session + DB state so resolve_canonical_context() returns a valid context.

    Mirrors production login exactly:
      - session["user_id"] + session["current_session_nonce"] (nonce validated before_request)
      - session["login_time"] + session["last_activity"] (read by dashboard and timeout checks)
      - user.current_session_nonce / last_active_class_id / last_active_seat_id in DB

    Returns the nonce that was written, so callers can use it consistently.
    """
    resolved_nonce = nonce or secrets.token_urlsafe(32)
    now_iso = datetime.now(timezone.utc).isoformat()
    sess["user_id"] = user_id
    sess["current_session_nonce"] = resolved_nonce
    sess["login_time"] = now_iso
    sess["last_activity"] = now_iso

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"canonical-session:{user_id}:{class_id}:{seat_id}"):
        user = db.session.get(User, user_id)
        if user is not None:
            user.current_session_nonce = resolved_nonce
            user.last_active_class_id = class_id
            seat = db.session.get(Seat, seat_id)
            if seat is not None:
                user.last_active_seat_id = seat_id
            db.session.flush()

    return resolved_nonce
