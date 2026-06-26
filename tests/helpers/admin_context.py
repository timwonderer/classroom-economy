from datetime import datetime, timezone
import secrets


def login_admin(
    client,
    admin_id: int,
    join_code: str | None = None,
    *,
    user_id: int | None = None,
    class_id: str | None = None,
    seat_id: int | None = None,
) -> None:
    # Ensure a User exists for this admin (required by get_current_admin() → get_current_user())
    if user_id is None:
        from app.extensions import db
        from app.models import Admin, User, UserRole
        admin = db.session.get(Admin, admin_id)
        if admin and admin.username_lookup_hash:
            user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
            if not user:
                user = User(
                    username_hash=admin.username_lookup_hash,
                    username_lookup_hash=admin.username_lookup_hash,
                    user_role=UserRole.TEACHER,
                )
                db.session.add(user)
                db.session.commit()
            user_id = user.id

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        if user_id is not None:
            sess["user_id"] = user_id
            sess["current_session_nonce"] = secrets.token_urlsafe(32)
            from app.extensions import db
            from app.models import User
            user = db.session.get(User, user_id)
            if user:
                user.current_session_nonce = sess["current_session_nonce"]
                db.session.commit()
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
        if join_code is not None:
            sess["current_join_code"] = join_code
        if class_id is not None:
            sess["current_class_id"] = class_id
        if seat_id is not None:
            sess["current_seat_id"] = seat_id
