"""V2 canonical admin session helpers.

Teacher auth works entirely through the canonical User (role=TEACHER) +
context_resolver. No authority bridge objects.
"""
import secrets
from app.extensions import db
from app.feats.base import FEATContext
from app.models import User
from tests.helpers.canonical_session import set_canonical_context


def login_teacher(
    client,
    teacher_user: User,
    *,
    class_id: str | None = None,
    seat_id: int | None = None,
) -> None:
    """Set up a teacher session on the test client."""

    nonce = secrets.token_urlsafe(32)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"login_teacher:{teacher_user.id}:{class_id}:{seat_id}:{nonce}"):
        with client.session_transaction() as sess:
            sess["user_id"] = teacher_user.id
            sess["current_session_nonce"] = nonce
            sess["last_activity"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            if class_id is not None and seat_id is not None:
                set_canonical_context(
                    sess,
                    user_id=teacher_user.id,
                    class_id=class_id,
                    seat_id=seat_id,
                    role="teacher",
                )
        teacher_user.current_session_nonce = nonce
        db.session.flush()


# Keep old name as alias for migration convenience
login_admin = login_teacher
