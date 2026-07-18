"""V2 canonical admin session helpers.

Teacher auth works entirely through the canonical User (role=TEACHER) +
context_resolver. No authority bridge objects.
"""
import secrets
from datetime import datetime, timezone
from app.extensions import db
from app.feats.base import FEATContext
from app.models import User


def login_teacher(
    client,
    teacher_user: User,
    *,
    class_id: str | None = None,
    seat_id: int | None = None,
) -> None:
    """Set up a teacher session on the test client.

    Mirrors the production teacher login path (select_class_context):
      - session: user_id + nonce + last_activity
      - DB: user.current_session_nonce + user.last_active_class_id

    Does NOT write last_active_seat_id. Production never does either —
    resolve_canonical_context() uses the DOM-IDEN-006 §VIII step-7 seat
    fallback (query by user_id + class_id) when last_active_seat_id is null.

    seat_id is accepted for call-site compatibility but ignored — the resolver
    handles seat resolution from the DB.
    """
    nonce = secrets.token_urlsafe(32)
    now_iso = datetime.now(timezone.utc).isoformat()
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"login_teacher:{teacher_user.id}:{class_id}:{nonce}"):
        with client.session_transaction() as sess:
            sess["user_id"] = teacher_user.id
            sess["current_session_nonce"] = nonce
            sess["login_time"] = now_iso
            sess["last_activity"] = now_iso
        teacher_user.current_session_nonce = nonce
        if class_id is not None:
            teacher_user.last_active_class_id = class_id
        db.session.flush()


# Keep old name as alias for migration convenience
login_admin = login_teacher
