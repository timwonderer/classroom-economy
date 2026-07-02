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
    sess["user_id"] = user_id
    sess["current_class_id"] = class_id
    sess["current_seat_id"] = seat_id
    sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    if join_code is not None:
        sess["current_join_code"] = join_code
    if role == "teacher":
        sess["is_admin"] = True
