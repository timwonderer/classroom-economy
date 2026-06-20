"""Backfill canonical identity principals and seat bindings.

Revision ID: b7e4c1d9a2f6
Revises: a6d9c2e4f1b7
Create Date: 2026-06-04

This migration treats legacy principal tables as migration input only. It does
not make them runtime authority, and it fails closed on ambiguous bindings.
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e4c1d9a2f6"
down_revision = "a6d9c2e4f1b7"
branch_labels = None
depends_on = None


def _rows(query, **params):
    return op.get_bind().execute(sa.text(query), params).mappings().all()


def _scalar(query, **params):
    return op.get_bind().execute(sa.text(query), params).scalar_one_or_none()


def _execute(query, **params):
    return op.get_bind().execute(sa.text(query), params)


def _assert_no_cross_principal_username_collisions():
    collisions = _rows(
        """
        SELECT username_lookup_hash, COUNT(*) AS principal_count
        FROM (
            SELECT username_lookup_hash FROM teachers WHERE username_lookup_hash IS NOT NULL
            UNION ALL
            SELECT username_lookup_hash FROM students WHERE username_lookup_hash IS NOT NULL
            UNION ALL
            SELECT username_lookup_hash FROM system_admins WHERE username_lookup_hash IS NOT NULL
        ) principals
        GROUP BY username_lookup_hash
        HAVING COUNT(*) > 1
        """
    )
    if collisions:
        raise RuntimeError(
            "Canonical identity backfill found duplicate username lookup hashes "
            "across legacy principal tables. Resolve the collisions before upgrading."
        )


def _assert_unambiguous_student_bindings():
    ambiguous = _rows(
        """
        SELECT student_id, COUNT(DISTINCT user_id) AS user_count
        FROM seats
        WHERE student_id IS NOT NULL AND user_id IS NOT NULL
        GROUP BY student_id
        HAVING COUNT(DISTINCT user_id) > 1
        """
    )
    if ambiguous:
        raise RuntimeError(
            "Canonical identity backfill found students already bound to multiple "
            "users. Resolve the seat bindings before upgrading."
        )


def _assert_unambiguous_user_roles():
    ambiguous = _rows(
        """
        SELECT user_id, COUNT(DISTINCT role) AS role_count
        FROM seats
        WHERE user_id IS NOT NULL
        GROUP BY user_id
        HAVING COUNT(DISTINCT role) > 1
        """
    )
    if ambiguous:
        raise RuntimeError(
            "Canonical identity backfill found users with mixed seat roles. "
            "Resolve the role ambiguity before upgrading."
        )


def _ensure_user_for_principal(principal, role, *, totp_secret=None, pin_hash=None, passphrase_hash=None):
    lookup_hash = principal["username_lookup_hash"]
    user = _rows(
        """
        SELECT id, user_role
        FROM users
        WHERE username_lookup_hash = :lookup_hash
        """,
        lookup_hash=lookup_hash,
    )
    if len(user) > 1:
        raise RuntimeError("Canonical identity backfill found duplicate users for one username lookup hash.")

    if user:
        user_id = user[0]["id"]
        existing_role = user[0]["user_role"]
        if existing_role not in (None, role):
            raise RuntimeError(
                f"Canonical identity backfill cannot change user {user_id} role "
                f"from {existing_role} to {role}."
            )
    else:
        user_id = _scalar(
            """
            INSERT INTO users (
                user_role,
                username_hash,
                username_lookup_hash,
                password_hash,
                totp_secret_encrypted,
                pin_hash,
                passphrase_hash,
                has_completed_setup,
                created_at,
                updated_at
            )
            VALUES (
                :role,
                :username_hash,
                :lookup_hash,
                NULL,
                :totp_secret,
                :pin_hash,
                :passphrase_hash,
                :has_completed_setup,
                COALESCE(:created_at, NOW()),
                NOW()
            )
            RETURNING id
            """,
            role=role,
            username_hash=principal["username_hash"],
            lookup_hash=lookup_hash,
            totp_secret=totp_secret,
            pin_hash=pin_hash,
            passphrase_hash=passphrase_hash,
            has_completed_setup=bool(principal.get("has_completed_setup", True)),
            created_at=principal.get("created_at"),
        )

    _execute(
        """
        UPDATE users
        SET user_role = COALESCE(user_role, :role),
            username_hash = COALESCE(username_hash, :username_hash),
            username_lookup_hash = COALESCE(username_lookup_hash, :lookup_hash),
            totp_secret_encrypted = COALESCE(totp_secret_encrypted, :totp_secret),
            pin_hash = COALESCE(pin_hash, :pin_hash),
            passphrase_hash = COALESCE(passphrase_hash, :passphrase_hash),
            has_completed_setup = has_completed_setup OR :has_completed_setup,
            updated_at = NOW()
        WHERE id = :user_id
        """,
        user_id=user_id,
        role=role,
        username_hash=principal["username_hash"],
        lookup_hash=lookup_hash,
        totp_secret=totp_secret,
        pin_hash=pin_hash,
        passphrase_hash=passphrase_hash,
        has_completed_setup=bool(principal.get("has_completed_setup", True)),
    )
    return user_id


def _normalize_existing_seat_users():
    _execute(
        """
        UPDATE users AS u
        SET user_role = role_source.role::user_role_enum,
            updated_at = NOW()
        FROM (
            SELECT user_id, MIN(role) AS role
            FROM seats
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        ) AS role_source
        WHERE u.id = role_source.user_id
          AND u.user_role IS NULL
        """
    )
    _execute(
        """
        UPDATE seats
        SET claimed_at = COALESCE(claimed_at, created_at, NOW())
        WHERE user_id IS NOT NULL
          AND claimed_at IS NULL
        """
    )


def _backfill_students():
    students = _rows(
        """
        SELECT id, username_hash, username_lookup_hash, pin_hash, passphrase_hash,
               money_action_cooldown_until, has_completed_setup, identity_id
        FROM students
        WHERE username_hash IS NOT NULL
          AND username_lookup_hash IS NOT NULL
        ORDER BY id
        """
    )
    for student in students:
        bound_user_id = _scalar(
            """
            SELECT MIN(user_id)
            FROM seats
            WHERE student_id = :student_id
              AND user_id IS NOT NULL
            """,
            student_id=student["id"],
        )
        if bound_user_id:
            user_id = bound_user_id
            collision_user_id = _scalar(
                "SELECT id FROM users WHERE username_lookup_hash = :lookup_hash",
                lookup_hash=student["username_lookup_hash"],
            )
            if collision_user_id not in (None, user_id):
                raise RuntimeError(
                    f"Student {student['id']} username is already owned by another user."
                )
            _execute(
                """
                UPDATE users
                SET user_role = COALESCE(user_role, 'student'::user_role_enum),
                    username_hash = :username_hash,
                    username_lookup_hash = :lookup_hash,
                    pin_hash = COALESCE(pin_hash, :pin_hash),
                    passphrase_hash = COALESCE(passphrase_hash, :passphrase_hash),
                    money_action_cooldown_until = COALESCE(
                        money_action_cooldown_until,
                        :money_action_cooldown_until
                    ),
                    has_completed_setup = has_completed_setup OR :has_completed_setup,
                    updated_at = NOW()
                WHERE id = :user_id
                  AND (user_role IS NULL OR user_role = 'student'::user_role_enum)
                """,
                user_id=user_id,
                username_hash=student["username_hash"],
                lookup_hash=student["username_lookup_hash"],
                pin_hash=student["pin_hash"],
                passphrase_hash=student["passphrase_hash"],
                money_action_cooldown_until=student["money_action_cooldown_until"],
                has_completed_setup=bool(student["has_completed_setup"]),
            )
        else:
            user_id = _ensure_user_for_principal(
                student,
                "student",
                pin_hash=student["pin_hash"],
                passphrase_hash=student["passphrase_hash"],
            )

        conflicting_seat = _scalar(
            """
            SELECT id
            FROM seats
            WHERE student_id = :student_id
              AND user_id IS NOT NULL
              AND user_id <> :user_id
            LIMIT 1
            """,
            student_id=student["id"],
            user_id=user_id,
        )
        if conflicting_seat:
            raise RuntimeError(
                f"Student {student['id']} has a seat bound to another user."
            )
        _execute(
            """
            UPDATE seats
            SET user_id = :user_id,
                claimed_at = COALESCE(claimed_at, created_at, NOW())
            WHERE student_id = :student_id
              AND user_id IS NULL
            """,
            student_id=student["id"],
            user_id=user_id,
        )


def _backfill_teachers():
    teachers = _rows(
        """
        SELECT id, username_hash, username_lookup_hash, totp_secret, created_at
        FROM teachers
        WHERE username_hash IS NOT NULL
          AND username_lookup_hash IS NOT NULL
        ORDER BY id
        """
    )
    for teacher in teachers:
        user_id = _ensure_user_for_principal(
            teacher,
            "teacher",
            totp_secret=teacher["totp_secret"],
        )
        classes = _rows(
            """
            SELECT class_id, join_code, created_at
            FROM classes
            WHERE teacher_id = :teacher_id
            ORDER BY class_id
            """,
            teacher_id=teacher["id"],
        )
        for class_row in classes:
            teacher_seats = _rows(
                """
                SELECT id, user_id
                FROM seats
                WHERE class_id = :class_id
                  AND role = 'teacher'
                ORDER BY id
                """,
                class_id=class_row["class_id"],
            )
            if len(teacher_seats) > 1:
                raise RuntimeError(
                    f"Class {class_row['class_id']} has multiple teacher seats."
                )
            existing_user_id = teacher_seats[0]["user_id"] if teacher_seats else None
            if existing_user_id not in (None, user_id):
                raise RuntimeError(
                    f"Class {class_row['class_id']} already has a teacher seat owned by another user."
                )
            if teacher_seats:
                _execute(
                    """
                    UPDATE seats
                    SET user_id = :user_id,
                        claimed_at = COALESCE(claimed_at, created_at, NOW())
                    WHERE id = :seat_id
                    """,
                    user_id=user_id,
                    seat_id=teacher_seats[0]["id"],
                )
            else:
                _execute(
                    """
                    INSERT INTO seats (
                        public_id,
                        user_id,
                        class_id,
                        role,
                        join_code,
                        claimed_at,
                        created_at,
                        updated_at
                    )
                    SELECT
                        gen_random_uuid()::text,
                        :user_id,
                        :class_id,
                        'teacher',
                        :join_code,
                        COALESCE(:created_at, NOW()),
                        COALESCE(:created_at, NOW()),
                        NOW()
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM seats
                        WHERE class_id = :class_id
                          AND role = 'teacher'
                    )
                    """,
                    user_id=user_id,
                    class_id=class_row["class_id"],
                    join_code=class_row["join_code"],
                    created_at=class_row["created_at"],
                )


def _backfill_system_admins():
    admins = _rows(
        """
        SELECT id, username_hash, username_lookup_hash, totp_secret
        FROM system_admins
        WHERE username_hash IS NOT NULL
          AND username_lookup_hash IS NOT NULL
        ORDER BY id
        """
    )
    for admin in admins:
        _ensure_user_for_principal(
            admin,
            "sysadmin",
            totp_secret=admin["totp_secret"],
        )


def _backfill_student_profiles():
    seats = _rows(
        """
        SELECT s.id AS seat_id, st.identity_id
        FROM seats AS s
        JOIN students AS st ON st.id = s.student_id
        LEFT JOIN identity_profiles AS existing ON existing.seat_id = s.id
        WHERE existing.id IS NULL
        ORDER BY s.id
        """
    )
    for seat in seats:
        source = _rows(
            """
            SELECT id, seat_id, profile_type, first_name, last_initial, created_at, updated_at
            FROM identity_profiles
            WHERE id = :identity_id
            """,
            identity_id=seat["identity_id"],
        )
        if not source:
            raise RuntimeError(
                f"Seat {seat['seat_id']} cannot be bound to a display profile."
            )
        profile = source[0]
        if profile["seat_id"] is None:
            _execute(
                "UPDATE identity_profiles SET seat_id = :seat_id WHERE id = :profile_id",
                seat_id=seat["seat_id"],
                profile_id=profile["id"],
            )
        else:
            _execute(
                """
                INSERT INTO identity_profiles (
                    seat_id,
                    profile_type,
                    first_name,
                    last_initial,
                    created_at,
                    updated_at
                )
                VALUES (
                    :seat_id,
                    :profile_type,
                    :first_name,
                    :last_initial,
                    :created_at,
                    :updated_at
                )
                """,
                seat_id=seat["seat_id"],
                profile_type=profile["profile_type"],
                first_name=profile["first_name"],
                last_initial=profile["last_initial"],
                created_at=profile["created_at"],
                updated_at=profile["updated_at"],
            )


def upgrade():
    # Guard: if seats.student_id has already been dropped by the identity-repoint
    # migration, the backfill queries will fail.  On a clean v2 DB there is nothing
    # to backfill anyway, so skip gracefully.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    seat_cols = [c['name'] for c in inspector.get_columns('seats')]
    if 'student_id' not in seat_cols:
        return

    _assert_no_cross_principal_username_collisions()
    _assert_unambiguous_student_bindings()
    _assert_unambiguous_user_roles()
    _normalize_existing_seat_users()
    _backfill_students()
    _backfill_teachers()
    _backfill_system_admins()
    _backfill_student_profiles()


def downgrade():
    # Identity bindings are intentionally irreversible. Removing migrated users or
    # seats would destroy canonical authority and could orphan domain records.
    pass
