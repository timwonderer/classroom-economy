"""V2 canonical admin session helpers.

Teacher auth works entirely through the canonical User (role=TEACHER) +
context_resolver. No Admin objects.
"""
import secrets
from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, User


def login_teacher(
    client,
    teacher_user: User,
    *,
    class_id: str | None = None,
    join_code: str | None = None,
    seat_id: int | None = None,
) -> None:
    """Set up a teacher session on the test client.

    If class_id / join_code is provided, establishes a full CanonicalContext
    (teacher sees their class). If omitted, establishes a BoundaryContext
    (teacher is logged in but has no active class — valid for onboarding routes).
    """
    resolved_class_id = class_id
    resolved_seat_id = seat_id

    if resolved_class_id is None and join_code is not None:
        row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if row:
            resolved_class_id = row.class_id

    if resolved_seat_id is None and resolved_class_id is not None:
        seat = Seat.query.filter_by(
            user_id=teacher_user.id,
            class_id=resolved_class_id,
        ).first()
        if seat:
            resolved_seat_id = seat.id

    nonce = secrets.token_urlsafe(32)

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"login_teacher:{teacher_user.id}:{nonce}"):
        with client.session_transaction() as sess:
            sess["user_id"] = teacher_user.id
            sess["current_session_nonce"] = nonce
            sess["last_activity"] = __import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat()

            if resolved_class_id and resolved_seat_id:
                sess["current_class_id"] = resolved_class_id
                sess["current_seat_id"] = resolved_seat_id
                if join_code:
                    sess["current_join_code"] = join_code

        teacher_user.current_session_nonce = nonce
        if resolved_class_id:
            teacher_user.last_active_class_id = resolved_class_id
        if resolved_seat_id:
            teacher_user.last_active_seat_id = resolved_seat_id
        db.session.flush()


# Keep old name as alias for migration convenience
login_admin = login_teacher
