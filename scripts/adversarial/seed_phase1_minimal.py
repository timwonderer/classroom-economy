#!/usr/bin/env python3
"""Phase 1 minimal adversarial seed.

Seeds only the minimum graph needed for:
- auth/user principals
- teachers/classes/seats
- session-context boundaries
- feature toggle differentials
- same-name cross-class collision
- seat lifecycle variants (claimed/unclaimed/deleted)

All mutations run inside explicit FEAT contexts (FEAT-IDEN-001 / FEAT-ADMN-001).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    Admin,
    BalanceCache,
    ClassEconomy,
    ClassFeature,
    ClassMembership,
    IdentityProfile,
    Seat,
    Student,
    StudentTeacher,
    TeacherBlock,
    User,
)
from app.utils.encryption import encrypt_totp


@dataclass(frozen=True)
class ClassDef:
    key: str
    join_code: str
    display_name: str
    teacher_key: str
    block: str


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_salt() -> bytes:
    return secrets.token_bytes(16)


def ensure_teacher(public_label: str) -> Admin:
    lookup = h(f"teacher:{public_label}")
    teacher = Admin.query.filter_by(username_lookup_hash=lookup).first()
    if teacher:
        return teacher

    teacher = Admin(
        username_hash=h(f"teacher-hash:{public_label}"),
        username_lookup_hash=lookup,
        teacher_public_id=public_label,
        display_name=public_label,
        totp_secret=encrypt_totp("JBSWY3DPEHPK3PXP"),
        has_assigned_students=True,
        created_at=now_utc(),
    )
    db.session.add(teacher)
    db.session.flush()
    return teacher


def ensure_class(cdef: ClassDef, teacher: Admin) -> ClassEconomy:
    row = ClassEconomy.query.filter_by(join_code=cdef.join_code).first()
    if row:
        return row
    row = ClassEconomy(
        join_code=cdef.join_code,
        user_id=teacher.id,
        created_by_admin_id=teacher.id,
        display_name=cdef.display_name,
        class_timezone="UTC",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.session.add(row)
    db.session.flush()
    return row


def ensure_admin_membership(class_row: ClassEconomy, teacher: Admin) -> None:
    existing = ClassMembership.query.filter_by(class_id=class_row.class_id, admin_id=teacher.id, role="admin").first()
    if existing:
        return
    db.session.add(
        ClassMembership(
            class_id=class_row.class_id,
            join_code=class_row.join_code,
            admin_id=teacher.id,
            role="admin",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
    )


def ensure_user(username: str) -> User:
    user = User.query.filter_by(username=username).first()
    if user:
        return user
    user = User(
        username=username,
        password_hash=generate_password_hash(f"{username}-pw"),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.session.add(user)
    db.session.flush()
    return user


def ensure_identity(first_name: str, last_initial: str) -> IdentityProfile:
    row = (
        IdentityProfile.query.filter_by(profile_type="student")
        .filter(IdentityProfile.last_name == last_initial)
        .all()
    )
    for cand in row:
        if (cand.first_name or "") == first_name:
            return cand

    ident = IdentityProfile(
        profile_type="student",
        first_name=first_name,
        last_name=last_initial,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.session.add(ident)
    db.session.flush()
    return ident


def ensure_student(first_name: str, last_initial: str, block: str, class_row: ClassEconomy, teacher: Admin, unique_tag: str) -> Student:
    lookup = h(f"student:{first_name}:{last_initial}:{unique_tag}")
    row = Student.query.filter_by(username_lookup_hash=lookup).first()
    if row:
        return row

    ident = ensure_identity(first_name, last_initial)
    row = Student(
        identity_profile=ident,
        block=block,
        join_code=class_row.join_code,
        class_id=class_row.class_id,
        salt=make_salt(),
        first_half_hash=h(f"fh:{first_name[0]}:{unique_tag}"),
        username_hash=h(f"student-user-hash:{unique_tag}"),
        username_lookup_hash=lookup,
        pin_hash=generate_password_hash(f"{first_name[0]}1234"),
        has_completed_setup=True,
        hall_passes=3,
    )
    db.session.add(row)
    db.session.flush()

    # Teacher ownership link
    if not StudentTeacher.query.filter_by(student_id=row.id, teacher_id=teacher.id).first():
        db.session.add(
            StudentTeacher(
                student_id=row.id,
                teacher_id=teacher.id,
                class_id=class_row.class_id,
                join_code=class_row.join_code,
                created_at=now_utc(),
            )
        )

    # Student membership
    if not ClassMembership.query.filter_by(class_id=class_row.class_id, student_id=row.id, role="student").first():
        db.session.add(
            ClassMembership(
                class_id=class_row.class_id,
                join_code=class_row.join_code,
                student_id=row.id,
                role="student",
                created_at=now_utc(),
                updated_at=now_utc(),
            )
        )

    return row


def ensure_teacher_block(student: Student, teacher: Admin, class_row: ClassEconomy, block: str, claimed: bool) -> TeacherBlock:
    row = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        join_code=class_row.join_code,
        identity_id=student.identity_id,
        block=block,
    ).first()
    if row:
        return row

    row = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        class_label=class_row.display_name,
        first_name=student.display_first_name,
        last_initial=student.display_last_initial,
        identity_id=student.identity_id,
        last_name_hash_by_part=[h(f"ln:{student.id}")],
        dob_sum_hash=h(f"dobsum:{student.id}"),
        salt=make_salt(),
        first_half_hash=h(f"tb:{student.id}:{class_row.join_code}"),
        join_code=class_row.join_code,
        class_id=class_row.class_id,
        student_id=student.id if claimed else None,
        is_claimed=claimed,
        claimed_at=now_utc() if claimed else None,
        created_at=now_utc(),
    )
    db.session.add(row)
    db.session.flush()
    return row


def ensure_seat(user: User, student: Student, class_row: ClassEconomy, block: str, claimed: bool) -> Seat:
    row = Seat.query.filter_by(user_id=user.id, class_id=class_row.class_id).first()
    if row:
        return row
    row = Seat(
        user_id=user.id,
        student_id=student.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        role="student",
        block=block,
        block_identifier=block,
        claimed_at=now_utc() if claimed else None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.session.add(row)
    db.session.flush()
    return row


def set_feature_differential(class_a1: ClassEconomy, class_a2: ClassEconomy) -> None:
    feature = "hall_pass"
    # A2 enabled
    if not ClassFeature.query.filter_by(class_id=class_a2.class_id, feature_name=feature).first():
        db.session.add(ClassFeature(class_id=class_a2.class_id, feature_name=feature, created_at=now_utc()))
    # A1 disabled (absence == disabled)
    row = ClassFeature.query.filter_by(class_id=class_a1.class_id, feature_name=feature).first()
    if row:
        db.session.delete(row)


def normalize_balance_cache_scope_for_seeded_classes(class_ids: set[str]) -> dict[str, int]:
    """
    Repair stale balance_cache rows whose class_id no longer matches the seat's class.

    This keeps the adversarial seeded baseline deterministic by removing drift left behind
    from prior synthetic-injection runs.
    """
    if not class_ids:
        return {"mismatched_rows_found": 0, "rows_rehomed": 0, "rows_merged_deleted": 0}

    mismatched_rows = (
        db.session.query(BalanceCache, Seat)
        .join(Seat, Seat.id == BalanceCache.seat_id)
        .filter(
            Seat.class_id.in_(class_ids),
            BalanceCache.class_id != Seat.class_id,
        )
        .all()
    )

    rows_rehomed = 0
    rows_merged_deleted = 0
    for cache, seat in mismatched_rows:
        canonical = (
            BalanceCache.query
            .filter_by(seat_id=seat.id, class_id=seat.class_id)
            .first()
        )
        if canonical and canonical.id != cache.id:
            canonical.posted_checking_balance_cents += cache.posted_checking_balance_cents or 0
            canonical.posted_savings_balance_cents += cache.posted_savings_balance_cents or 0
            if not canonical.join_code and seat.join_code:
                canonical.join_code = seat.join_code
            db.session.delete(cache)
            rows_merged_deleted += 1
            continue

        cache.class_id = seat.class_id
        cache.join_code = seat.join_code
        rows_rehomed += 1

    return {
        "mismatched_rows_found": len(mismatched_rows),
        "rows_rehomed": rows_rehomed,
        "rows_merged_deleted": rows_merged_deleted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed minimal Phase 1 adversarial topology")
    parser.add_argument("--env-file", default=".env.redteam.local")
    args = parser.parse_args()

    load_dotenv(args.env_file, override=True)

    app = create_app()
    with app.app_context():
        teachers: dict[str, Admin] = {}
        classes: dict[str, ClassEconomy] = {}

        class_defs = [
            ClassDef("A1", "ADVA1", "Class A1", "teacher_a", "A1"),
            ClassDef("A2", "ADVA2", "Class A2", "teacher_a", "A2"),
            ClassDef("B1", "ADVB1", "Class B1", "teacher_b", "B1"),
        ]

        with FEATContext("FEAT-IDEN-001", idempotency_key="feat:adv:seed:teachers-classes"):
            teachers["teacher_a"] = ensure_teacher("Teacher A")
            teachers["teacher_b"] = ensure_teacher("Teacher B")

            for cdef in class_defs:
                cls = ensure_class(cdef, teachers[cdef.teacher_key])
                classes[cdef.key] = cls
                ensure_admin_membership(cls, teachers[cdef.teacher_key])

        students_plan = [
            # normal students
            ("Alice", "A", "A1", "alice_a1", True),
            ("Bob", "B", "A2", "bob_a2", True),
            ("Carlos", "C", "B1", "carlos_b1", True),
            # same-name collision across classes
            ("Maria", "G", "A1", "maria_garcia_a1", True),
            ("Maria", "G", "B1", "maria_garcia_b1", True),
        ]

        created_seats: dict[str, Seat] = {}

        with FEATContext("FEAT-IDEN-001", idempotency_key="feat:adv:seed:students-seats"):
            for first, li, ckey, tag, claimed in students_plan:
                cls = classes[ckey]
                teacher = teachers["teacher_a"] if ckey in {"A1", "A2"} else teachers["teacher_b"]
                user = ensure_user(f"adv_{tag}")
                student = ensure_student(first, li, cdef_block(ckey), cls, teacher, tag)
                ensure_teacher_block(student, teacher, cls, cdef_block(ckey), claimed=claimed)
                seat = ensure_seat(user, student, cls, cdef_block(ckey), claimed=claimed)
                created_seats[tag] = seat

            # Unclaimed seat state: teacher block exists but seat has no claimed_at
            user_unclaimed = ensure_user("adv_unclaimed_a2")
            student_unclaimed = ensure_student("Una", "U", "A2", classes["A2"], teachers["teacher_a"], "unclaimed_a2")
            ensure_teacher_block(student_unclaimed, teachers["teacher_a"], classes["A2"], "A2", claimed=False)
            created_seats["unclaimed_a2"] = ensure_seat(user_unclaimed, student_unclaimed, classes["A2"], "A2", claimed=False)

        # Deleted seat lifecycle state (created lawfully, then removed lawfully)
        with FEATContext("FEAT-IDEN-001", idempotency_key="feat:adv:seed:deleted-seat"):
            user_deleted = ensure_user("adv_deleted_b1")
            student_deleted = ensure_student("Delia", "D", "B1", classes["B1"], teachers["teacher_b"], "deleted_b1")
            ensure_teacher_block(student_deleted, teachers["teacher_b"], classes["B1"], "B1", claimed=True)
            doomed = ensure_seat(user_deleted, student_deleted, classes["B1"], "B1", claimed=True)
            doomed_public_id = doomed.public_id
            db.session.delete(doomed)

        with FEATContext("FEAT-ADMN-001", idempotency_key="feat:adv:seed:features"):
            set_feature_differential(classes["A1"], classes["A2"])

        with FEATContext("FEAT-ADMN-001", idempotency_key="feat:adv:seed:normalize-balance-cache-scope"):
            normalization_summary = normalize_balance_cache_scope_for_seeded_classes(
                {cls.class_id for cls in classes.values() if cls.class_id}
            )

        # Commit is orchestrator-owned by FEAT contexts; at this point all done.
        summary = {
            "teachers": {"teacher_a_id": teachers["teacher_a"].id, "teacher_b_id": teachers["teacher_b"].id},
            "classes": {k: v.class_id for k, v in classes.items()},
            "seat_counts": {
                "active_claimed": Seat.query.filter(Seat.claimed_at.isnot(None)).count(),
                "active_unclaimed": Seat.query.filter(Seat.claimed_at.is_(None)).count(),
            },
            "notes": {
                "deleted_seat_created_and_removed": True,
                "feature_diff": "hall_pass disabled in A1 (absent), enabled in A2 (present)",
                "balance_cache_scope_normalization": normalization_summary,
            },
        }
        print(summary)
    return 0


def cdef_block(class_key: str) -> str:
    return class_key


if __name__ == "__main__":
    raise SystemExit(main())
