import secrets
from tests.helpers.canonical_session import set_canonical_context


def login_admin(
    client,
    admin_id: int,
    join_code: str | None = None,
    *,
    user_id: int | None = None,
    class_id: str | None = None,
    seat_id: int | None = None,
) -> None:
    from app.extensions import db
    from app.models import Admin, ClassEconomy, Seat, User, UserRole

    # Resolve the canonical teacher user if the caller only knows the legacy admin row.
    if user_id is None:
        admin = db.session.get(Admin, admin_id)
        if admin and admin.username_lookup_hash:
            user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
            if user is None:
                user = User(
                    username_hash=admin.username_hash or admin.username_lookup_hash,
                    username_lookup_hash=admin.username_lookup_hash,
                    user_role=UserRole.TEACHER,
                    has_completed_setup=True,
                )
                db.session.add(user)
                db.session.flush()
            user_id = user.id

    if class_id is None and join_code is not None:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if class_row is not None:
            class_id = class_row.class_id
            seat = None
            if user_id is not None:
                seat = Seat.query.filter(
                    Seat.class_id == class_row.class_id,
                    Seat.user_id == user_id,
                ).order_by(Seat.id.asc()).first()
            if seat is None:
                seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").order_by(Seat.id.asc()).first()
            if seat is not None:
                seat_id = seat.id
                user_id = seat.user_id

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        if user_id is not None:
            sess["user_id"] = user_id
            sess["current_session_nonce"] = secrets.token_urlsafe(32)
            user = db.session.get(User, user_id)
            if user:
                user.current_session_nonce = sess["current_session_nonce"]
                db.session.commit()
        if class_id is not None and seat_id is not None and user_id is not None:
            set_canonical_context(
                sess,
                user_id=user_id,
                class_id=class_id,
                seat_id=seat_id,
                role="teacher",
                join_code=join_code,
            )
            sess["user_id"] = user_id
            # Persist canonical pointers on the User model so context_resolver
            # can establish CanonicalContext from DB state.
            from app.extensions import db
            from app.models import User
            user = db.session.get(User, user_id)
            if user:
                user.last_active_class_id = class_id
                user.last_active_seat_id = seat_id
                db.session.commit()
        elif join_code is not None:
            sess["current_join_code"] = join_code

    if user_id is None:
        admin = db.session.get(Admin, admin_id)
        if admin and admin.username_lookup_hash:
            user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
            if user is not None:
                nonce = secrets.token_urlsafe(32)
                with client.session_transaction() as sess:
                    sess["user_id"] = user.id
                    sess["current_session_nonce"] = nonce
                user.current_session_nonce = nonce
                db.session.commit()
