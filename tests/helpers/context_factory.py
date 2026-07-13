"""ClassroomContextFactory — thin wrapper around production classroom_setup service.

Tests use the same production path as routes. If the service changes, tests
automatically get the updated behavior.

Usage:
    ctx = ClassroomContextFactory(db).build()
    ctx = ClassroomContextFactory(db, join_code="MATH-01").with_students(3).build()

    ctx.teacher_user    — User instance (role=TEACHER)
    ctx.economy         — ClassEconomy instance
    ctx.class_id        — UUID string
    ctx.join_code       — display/ingress alias
    ctx.teacher_seat    — teacher Seat

    student = ctx.add_student("Alice", "Anderson")
    student.user        — User instance
    student.seat        — Seat instance
    student.profile     — IdentityProfile instance
    student.login(client)

    ctx.login_teacher(client)
    ctx.commit()
"""

import uuid
from dataclasses import dataclass, field
from typing import List

from app.feats.base import FEATContext


@dataclass
class StudentContext:
    """A student fully wired into a class context."""
    user: object
    seat: object
    profile: object
    join_code: str = ""
    class_id: str = ""

    @property
    def seat_id(self):
        return self.seat.id

    @property
    def user_id(self):
        return self.user.id

    def login(self, client):
        with client.session_transaction() as sess:
            from tests.helpers.canonical_session import set_canonical_context
            set_canonical_context(
                sess,
                user_id=self.user.id,
                class_id=self.class_id,
                seat_id=self.seat.id,
                role="student",
            )


@dataclass
class ClassroomContext:
    """Fully wired v2 class context — all invariants satisfied."""
    db: object
    teacher_user: object
    economy: object
    teacher_seat: object
    students: List[StudentContext] = field(default_factory=list)

    @property
    def class_id(self):
        return self.economy.class_id

    @property
    def join_code(self):
        return self.economy.join_code

    def add_student(self, first_name="Test", last_name="Student", **kwargs) -> StudentContext:
        """Add a student via the canonical production service."""
        from app.services.classroom_setup import create_student
        user, seat, profile = create_student(
            self.class_id,
            first_name=first_name,
            last_name=last_name,
            **kwargs,
        )
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
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"classroom_context_login:{self.teacher_user.id}:{self.class_id}"):
            with client.session_transaction() as sess:
                from tests.helpers.canonical_session import set_canonical_context
                set_canonical_context(
                    sess,
                    user_id=self.teacher_user.id,
                    class_id=self.class_id,
                    seat_id=self.teacher_seat.id,
                    role="teacher",
                )

    def commit(self):
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"classroom_context_commit:{self.class_id}"):
            self.db.session.commit()


class ClassroomContextFactory:
    """Builder that calls production services to create a classroom context.

    All DB operations go through app/services/classroom_setup.py — the same
    path production routes use. Tests and routes stay in sync automatically.
    """

    def __init__(self, db, *, join_code=None, class_id=None,
                 display_name=None, section=None, teacher_username=None,
                 feature_names=None):
        self._db = db
        self._join_code = join_code
        self._class_id = class_id
        self._display_name = display_name
        self._section = section
        self._teacher_username = teacher_username
        self._feature_names = list(feature_names or [])
        self._student_count = 0
        self._student_specs = []  # list of (first_name, last_name, kwargs)

    def with_students(self, count=1):
        self._student_count = count
        return self

    def with_student(self, first_name="Test", last_name="Student", **kwargs):
        self._student_specs.append((first_name, last_name, kwargs))
        return self

    def build(self) -> ClassroomContext:
        from app.services.classroom_setup import create_teacher, create_class

        username = self._teacher_username or f"teacher_{uuid.uuid4().hex[:8]}"
        join_code = self._join_code or f"CTX-{uuid.uuid4().hex[:6].upper()}"

        with FEATContext("FEAT-IDEN-001", idempotency_key=f"classroom_context_build:{join_code}"):
            teacher_user = create_teacher(username)

            economy = create_class(
                teacher_user.id,
                join_code=join_code,
                display_name=self._display_name or f"Test Class {join_code}",
                section=self._section,
            )

            if self._feature_names:
                from app.models import ClassFeature
                for feature_name in self._feature_names:
                    if not ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).first():
                        self._db.session.add(ClassFeature(class_id=economy.class_id, feature_name=feature_name))

            # Teacher seat is created inside create_class; retrieve it.
            from app.models import Seat
            teacher_seat = self._db.session.query(Seat).filter_by(
                user_id=teacher_user.id,
                class_id=economy.class_id,
                role="teacher",
            ).first()

            ctx = ClassroomContext(
                db=self._db,
                teacher_user=teacher_user,
                economy=economy,
                teacher_seat=teacher_seat,
            )

            for first, last, kwargs in self._student_specs:
                ctx.add_student(first, last, **kwargs)

            _default_names = [
                ("Alice", "A"), ("Bob", "B"), ("Charlie", "C"), ("Diana", "D"),
                ("Eve", "E"), ("Frank", "F"), ("Grace", "G"), ("Henry", "H"),
                ("Iris", "I"), ("Jack", "J"),
            ]
            for i in range(self._student_count):
                fn, ln = _default_names[i % len(_default_names)]
                ctx.add_student(fn, ln)

            self._db.session.flush()
            return ctx

