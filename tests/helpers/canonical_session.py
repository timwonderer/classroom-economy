from datetime import datetime, timezone


def set_canonical_context(
    sess,
    *,
    user_id: int,
    class_id: str,
    seat_id: int,
    role: str,
    join_code: str | None = None,
) -> None:
    from app.extensions import db
    from app.models import Seat, User

    sess["user_id"] = user_id
    sess["current_class_id"] = class_id
    sess["current_seat_id"] = seat_id
    sess["current_session_nonce"] = sess.get("current_session_nonce") or "test-session-nonce"
    sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    if join_code is not None:
        sess["current_join_code"] = join_code

    user = db.session.get(User, user_id)
    if user is not None:
        user.last_active_class_id = class_id
        if db.session.get(Seat, seat_id) is not None:
            user.last_active_seat_id = seat_id
        user.current_session_nonce = sess["current_session_nonce"]
        db.session.flush()
