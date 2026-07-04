"""canonicalContextFactory — canonical v2 test fixture builder.

Builds the full v2 identity chain: User → Seat → IdentityProfile.
Seat ownership stays canonical; compatibility helpers resolve through Seat.

Usage:
    ctx = canonicalContextFactory(db).build()
    # ctx.teacher_user    — User instance (v2 canonical principal)
    # ctx.class_id        — UUID string
    # ctx.join_code       — public alias
    # ctx.economy         — ClassEconomy instance
    # ctx.teacher_seat    — teacher Seat (user_id → teacher_user)
    # ctx.teacher_profile — teacher IdentityProfile

    student = ctx.add_student("Alice", "Anderson")
    # student.user        — User instance
    # student.seat        — Seat instance
    # student.profile     — IdentityProfile instance

    # Or bulk:
    ctx = canonicalContextFactory(db).with_students(3).build()
    ctx.students[0].seat  # first student's seat

    # Login helpers (set correct session keys for current auth):
    ctx.login_teacher(client)
    ctx.students[0].login(client)
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class StudentContext:
    """A student fully wired into a class context (v2 canonical)."""
    user: object       # User model instance (v2 principal)
    seat: object       # Seat model instance
    profile: object    # IdentityProfile model instance
    join_code: str = ""
    class_id: str = ""
    @property
    def seat_id(self):
        return self.seat.id

    @property
    def user_id(self):
        return self.user.id

    def login(self, client):
        """Log this student into the test client session."""
        with client.session_transaction() as sess:
            from tests.helpers.canonical_session import set_canonical_context
            set_canonical_context(
                sess,
                user_id=self.user.id,
                class_id=self.class_id,
                seat_id=self.seat.id,
                role="student",
                join_code=self.join_code,
            )


@dataclass
class ClassroomContext:
    """Fully wired v2 class context with all invariants satisfied."""
    db: object
    teacher_user: object     # User instance (v2 canonical principal)
    economy: object          # ClassEconomy instance
    teacher_seat: object     # Seat instance (user_id → teacher_user)
    teacher_profile: object  # IdentityProfile instance
    students: List[StudentContext] = field(default_factory=list)
    @property
    def class_id(self):
        return self.economy.class_id

    @property
    def join_code(self):
        return self.economy.join_code

    @property
    def teacher_id(self):
        return None

    def add_student(self, first_name="Test", last_name="Student", **kwargs):
        """Add a student to this class with full v2 wiring.

        Returns a StudentContext with .user, .seat, .profile attributes.
        """
        from app.models import User, Seat, IdentityProfile, UserRole
        from app.utils.auth_username import build_hashed_username_fields

        idx = len(self.students) + 1
        username = kwargs.pop("username", f"student_{self.join_code}_{idx}")

        # 1. User (v2 canonical principal)
        u_salt, u_hash, u_lookup = build_hashed_username_fields(username)
        user = User(
            user_role=UserRole.STUDENT,
            username_hash=u_hash,
            username_lookup_hash=u_lookup,
        )
        self.db.session.add(user)
        self.db.session.flush()

        # 2. Seat
        seat = Seat(
            user_id=user.id,
            class_id=self.class_id,
            join_code=self.join_code,
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        self.db.session.add(seat)
        self.db.session.flush()

        # 3. IdentityProfile
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=self.class_id,
            profile_type="student",
            first_name=first_name,
            last_name=last_name,
        )
        self.db.session.add(profile)
        self.db.session.flush()

        sc = StudentContext(
            user=user,
            seat=seat,
            profile=profile,
            join_code=self.join_code,
            class_id=self.class_id,
        )
        self.students.append(sc)
        return sc

    def login_teacher(self, client):
        """Log the teacher into the test client session for this class."""
        with client.session_transaction() as sess:
            from tests.helpers.canonical_session import set_canonical_context
            set_canonical_context(
                sess,
                user_id=self.teacher_user.id,
                class_id=self.class_id,
                seat_id=self.teacher_seat.id,
                role="teacher",
                join_code=self.join_code,
            )

    def commit(self):
        """Commit the current session."""
        from app.feats.base import FEATBypass
        with FEATBypass():
            self.db.session.commit()


class ClassroomContextFactory:
    """Builder for ClassroomContext.

    Usage:
        ctx = ClassroomContextFactory(db).build()
        ctx = ClassroomContextFactory(db).with_students(3).build()
    """

    def __init__(self, db, *, join_code=None, class_id=None,
                 teacher_display_name=None):
        self._db = db
        self._join_code = join_code
        self._class_id = class_id
        self._teacher_display_name = teacher_display_name
        self._student_count = 0
        self._student_specs = []  # list of (first_name, last_name, kwargs)

    def with_students(self, count=1):
        """Add N students with default names."""
        self._student_count = count
        return self

    def with_student(self, first_name="Test", last_name="Student", **kwargs):
        """Add a specifically-named student."""
        self._student_specs.append((first_name, last_name, kwargs))
        return self

    def build(self) -> ClassroomContext:
        """Build the full context, flush to DB (but don't commit)."""
        from app.models import (
            Admin, User, ClassEconomy, Seat, IdentityProfile, UserRole,
        )
        from app.utils.auth_username import build_hashed_username_fields

        uname = f"teacher_{uuid.uuid4().hex[:8]}"

        # 1. User (v2 canonical principal for teacher)
        u_salt, u_hash, u_lookup = build_hashed_username_fields(uname)
        teacher_user = User(
            user_role=UserRole.TEACHER,
            username_hash=u_hash,
            username_lookup_hash=u_lookup,
        )
        self._db.session.add(teacher_user)
        self._db.session.flush()

        # 2. ClassEconomy
        class_id = self._class_id or str(uuid.uuid4())
        join_code = self._join_code or f"CTX-{uuid.uuid4().hex[:6].upper()}"

        economy = ClassEconomy(
            class_id=class_id,
            join_code=join_code,
            user_id=teacher_user.id,
            created_by_user_id=teacher_user.id,
            display_name=f"Test Class {join_code}",
        )
        self._db.session.add(economy)
        self._db.session.flush()

        # 3. Teacher Seat (user_id → User)
        teacher_seat = Seat(
            user_id=teacher_user.id,
            class_id=class_id,
            join_code=join_code,
            role="teacher",
        )
        self._db.session.add(teacher_seat)
        self._db.session.flush()

        # 4. Teacher IdentityProfile
        display = self._teacher_display_name or "Test Teacher"
        parts = display.split(" ", 1)
        t_first = parts[0]
        t_last = parts[1] if len(parts) > 1 else ""

        teacher_profile = IdentityProfile(
            seat_id=teacher_seat.id,
            class_id=class_id,
            profile_type="teacher",
            first_name=t_first,
            last_name=t_last,
        )
        self._db.session.add(teacher_profile)
        self._db.session.flush()

        ctx = ClassroomContext(
            db=self._db,
            teacher_user=teacher_user,
            economy=economy,
            teacher_seat=teacher_seat,
            teacher_profile=teacher_profile,
        )

        # 5. Named students
        for first, last, kwargs in self._student_specs:
            ctx.add_student(first, last, **kwargs)

        # 6. Default-named students
        _default_names = [
            ("Alice", "A"), ("Bob", "B"), ("Charlie", "C"), ("Diana", "D"),
            ("Eve", "E"), ("Frank", "F"), ("Grace", "G"), ("Henry", "H"),
            ("Iris", "I"), ("Jack", "J"),
        ]
        for i in range(self._student_count):
            fn, ln = _default_names[i % len(_default_names)]
            if i >= len(_default_names):
                fn = f"{fn}{i // len(_default_names) + 1}"
            ctx.add_student(fn, ln)

        self._db.session.flush()
        return ctx


canonicalContextFactory = ClassroomContextFactory
