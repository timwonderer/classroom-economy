"""
Canonical Classroom Setup Helper

Single authoritative path for setting up teacher + class + students in tests.
Implements TEST-IDEN-001: Canonical Test Identities.

Every operation here is a direct call to production code in app/services/ or app/auth.py.
No identity object is constructed by this helper — all artifacts are produced by the
same code paths that production uses.

Usage:

    classroom = provision_classroom("chemistry_p1")
    # DB state is fully set; no session yet.

    login_teacher(client, classroom)
    # Teacher session is live; resolve_canonical_context() will return a valid context.

    login_student(client, classroom.students[0])
    # Student session is live.

All other helpers that construct identity or context (v2_fixtures, class_scope,
admin_context) are superseded by this module for any test that requires canonical
identity setup.
"""

from dataclasses import dataclass, field

from app.extensions import db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import ClassEconomy, IdentityProfile, Seat, User
from app.services.classroom_setup import (
    create_class,
    create_student_user_for_seat,
    create_teacher,
)
from app.utils.join_code import generate_join_code
from app.utils.username_generation import build_username
from tests.helpers.canonical_identities import CLASSROOMS, TEACHERS
from tests.helpers.canonical_session import set_canonical_context


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class ProvisionedStudent:
    user: User
    seat: Seat
    profile: IdentityProfile
    user_id: int
    seat_id: int
    first_name: str
    last_name: str
    chosen_word: str
    username: str       # plaintext; stored here for test login use
    pin: str
    passphrase: str


@dataclass
class ProvisionedClassroom:
    economy: ClassEconomy
    class_id: str
    teacher_user: User
    teacher_seat: Seat
    teacher_user_id: int
    teacher_seat_id: int
    students: list[ProvisionedStudent] = field(default_factory=list)

    @property
    def join_code(self) -> str:
        return self.economy.join_code


# ---------------------------------------------------------------------------
# Core provision
# ---------------------------------------------------------------------------

def provision_classroom(classroom_key: str) -> ProvisionedClassroom:
    """Provision a canonical classroom entirely through production code.

    Creates:
      - Teacher User (role=TEACHER)
      - ClassEconomy (join_code generated, display_name + section from spec)
      - Teacher Seat (role='teacher', bound to class_id)
      - Teacher last_active_class_id / last_active_seat_id set
      - One unclaimed Seat + IdentityProfile per roster row
        (claim_first_name_hash, claim_last_name_hash, roster_fingerprint set)
      - Username built via production build_username(chosen_word, roster_fingerprint)
      - One User (role=STUDENT) per roster row with preset credentials, bound to seat
      - Student last_active_class_id / last_active_seat_id set

    Flushes but does NOT commit. Callers own the transaction boundary
    (the pytest conftest session-scoped transaction rollback handles cleanup).

    Does not touch the Flask session. Call login_teacher() or login_student()
    to establish request context.
    """
    classroom_def = CLASSROOMS[classroom_key]
    teacher_def = TEACHERS[classroom_def["teacher"]]

    join_code = generate_join_code()
    idempotency_key = f"canonical-classroom:provision:{classroom_key}:{join_code}"

    with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):

        # --- Teacher account ---
        teacher_user = create_teacher(teacher_def["username"])

        # --- Class (creates teacher Seat + sets last_active pointers) ---
        economy = create_class(
            teacher_user.id,
            join_code=join_code,
            display_name=classroom_def["display_name"],
            section=classroom_def.get("section"),
        )

        teacher_seat = Seat.query.filter_by(
            user_id=teacher_user.id,
            class_id=economy.class_id,
            role="teacher",
        ).first()

        # --- Roster: unclaimed seats → username generation → credentials ---
        provisioned_students = []
        for row in classroom_def["roster"]:
            seat = _provision_roster_seat(economy.class_id, row)

            # Username is built the same way the create_username route does it:
            # production build_username(chosen_word, roster_fingerprint)
            username = build_username(row["chosen_word"], seat.roster_fingerprint or "")

            student_user = create_student_user_for_seat(
                seat,
                username=username,
                pin=row["pin"],
                passphrase=row["passphrase"],
            )
            profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
            provisioned_students.append(ProvisionedStudent(
                user=student_user,
                seat=seat,
                profile=profile,
                user_id=student_user.id,
                seat_id=seat.id,
                first_name=row["first_name"],
                last_name=row["last_name"],
                chosen_word=row["chosen_word"],
                username=username,
                pin=row["pin"],
                passphrase=row["passphrase"],
            ))

    return ProvisionedClassroom(
        economy=economy,
        class_id=economy.class_id,
        teacher_user=teacher_user,
        teacher_seat=teacher_seat,
        teacher_user_id=teacher_user.id,
        teacher_seat_id=teacher_seat.id,
        students=provisioned_students,
    )


# ---------------------------------------------------------------------------
# Session setup
# ---------------------------------------------------------------------------

def login_teacher(client, classroom: ProvisionedClassroom) -> None:
    """Establish a canonical teacher session identical to production admin login.

    Mirrors app/routes/admin.py login():
      - session["user_id"], session["role"] = "admin"
      - session["current_session_nonce"] (validated by before_request)
      - session["login_time"], session["last_activity"]
      - session["admin_auth_username"]
      - user.current_session_nonce, user.last_active_class_id, user.last_active_seat_id (DB)
    """
    teacher_def = TEACHERS[_teacher_key_for(classroom)]
    user = classroom.teacher_user
    seat = classroom.teacher_seat

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=classroom.class_id,
            seat_id=seat.id,
            role="teacher",
        )
        sess["role"] = "admin"
        sess["admin_auth_username"] = teacher_def["username"]


def login_student(client, student: ProvisionedStudent) -> None:
    """Establish a canonical student session identical to production student login.

    Mirrors app/routes/student.py login():
      - session["user_id"], session["role"] = "student"
      - session["current_session_nonce"] (validated by before_request)
      - session["login_time"], session["last_activity"]
      - user.current_session_nonce, user.last_active_class_id, user.last_active_seat_id (DB)
    """
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user.id,
            class_id=student.seat.class_id,
            seat_id=student.seat.id,
            role="student",
        )
        sess["role"] = "student"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _provision_roster_seat(class_id: str, row: dict) -> Seat:
    """Create one unclaimed roster seat with claim hashes and roster_fingerprint set.

    Mirrors the production upload_students route:
      - claim_first_name_hash / claim_last_name_hash enable name-based seat matching
      - roster_fingerprint is used by build_username() to derive the fingerprint_suffix
    """
    first_name = row["first_name"]
    last_name = row["last_name"]

    seat = Seat(
        class_id=class_id,
        role="student",
        claimed_at=None,
        claim_first_name_hash=hash_username_lookup(first_name.lower()),
        claim_last_name_hash=hash_username_lookup(last_name.lower()),
        roster_fingerprint=hash_username_lookup(
            f"{class_id}|{first_name.lower()}|{last_name.lower()}"
        ),
        dedupe_code=row.get("dedupe_code"),
    )
    db.session.add(seat)
    db.session.flush()

    profile = IdentityProfile(
        seat_id=seat.id,
        class_id=class_id,
        profile_type="student",
        first_name=first_name,
        last_name=last_name,
        notes=row.get("teacher_note"),
    )
    db.session.add(profile)
    db.session.flush()

    return seat


def _teacher_key_for(classroom: ProvisionedClassroom) -> str:
    """Resolve the TEACHERS key for a provisioned classroom by matching username_lookup_hash."""
    from app.utils.auth_username import build_hashed_username_fields
    for key, teacher_def in TEACHERS.items():
        _, _, lookup_hash = build_hashed_username_fields(teacher_def["username"])
        if classroom.teacher_user.username_lookup_hash == lookup_hash:
            return key
    raise ValueError(f"Could not resolve teacher key for user_id={classroom.teacher_user.id}")
