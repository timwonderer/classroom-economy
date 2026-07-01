from datetime import datetime, timezone

import pytest

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import (
    Admin,
    ClassEconomy,
    IdentityProfile,
    Issue,
    IssueCategory,
    PayrollSettings,
    Seat,
    StoreItem,
    Student,
    StudentTeacher,
    User,
    UserRole,
)
from tests.helpers.class_scope import create_class_scope


def _bind_canonical_teacher(admin: Admin) -> User:
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id
    return user


def _login_admin(client, admin_id, *, user_id: int | None = None, class_id: str | None = None, seat_id: int | None = None):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        if user_id is not None:
            sess["user_id"] = user_id
        if class_id is not None:
            sess["current_class_id"] = class_id
        if seat_id is not None:
            sess["current_seat_id"] = seat_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_set_current_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("gate_admin_a", "secret-a")
    admin_b = make_admin("gate_admin_b", "secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    create_class_scope(
        teacher=admin_b,
        join_code="GATE001",
        teacher_block_teacher=admin_a,
        teacher_block_claimed=False,
    )
    db.session.commit()

    user_a = _bind_canonical_teacher(admin_a)
    db.session.commit()

    _login_admin(client, admin_a.id, user_id=user_a.id)
    class_row = ClassEconomy.query.filter_by(join_code="GATE001").first()
    response = client.post("/admin/current-class", json={"class_id": class_row.class_id})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_delete_join_code_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("delete_gate_a", "secret-a")
    admin_b = make_admin("delete_gate_b", "secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    create_class_scope(
        teacher=admin_b,
        join_code="DELG001",
        teacher_block_teacher=admin_a,
        teacher_block_claimed=False,
    )
    db.session.commit()

    user_a = _bind_canonical_teacher(admin_a)
    db.session.commit()

    _login_admin(client, admin_a.id, user_id=user_a.id)
    response = client.post("/admin/join-code/delete", json={"join_code": "DELG001"})
    assert response.status_code == 403
    assert ClassEconomy.query.filter_by(join_code="DELG001").first() is not None


def test_delete_join_code_requires_confirmation(client):
    admin = make_admin("confirm_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_row = create_class_scope(teacher=admin, join_code="CONF001")
    db.session.commit()

    _login_admin(client, admin.id, user_id=user.id, class_id=class_row.class_id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "CONF001"

    # 1. Missing confirmation -> 400
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001"})
    assert response.status_code == 400
    assert b"Confirmation failed" in response.data

    # 2. Wrong confirmation -> 400
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001", "confirm_join_code": "WRONG"})
    assert response.status_code == 400

    # 3. Correct confirmation -> 200
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001", "confirm_join_code": "CONF001"})
    assert response.status_code == 200
    assert ClassEconomy.query.filter_by(join_code="CONF001").first() is None


def test_issues_queue_respects_current_join_code_membership_scope(client):
    admin = make_admin("issues_gate_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_a = create_class_scope(teacher=admin, join_code="ISSGA1")
    class_b = create_class_scope(teacher=admin, join_code="ISSGB1")
    profile = IdentityProfile(profile_type="student", first_name="Gate", last_name="Stone")
    student = Student(identity_profile=profile, block="A", class_id=class_a.class_id, join_code="ISSGA1", salt=b"salt")
    db.session.add(student)
    db.session.flush()
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat_a = Seat(user_id=student_user.id, class_id=class_a.class_id, join_code="ISSGA1", block="A", block_identifier="A", role="student")
    db.session.add(seat_a)
    db.session.flush()
    profile.seat_id = seat_a.id
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, join_code="ISSGB1", block="A", block_identifier="A", role="student")
    db.session.add(seat_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type="student_claimed", first_name="Gate", last_name="Stone"))
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=admin.id, class_id=class_a.class_id, join_code="ISSGA1"))

    category = IssueCategory(
        name=f"Issue Gate Category {datetime.now(timezone.utc).isoformat()}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    db.session.add_all([
        Issue(
            user_id=student_user.id,
            actor_public_id="seat-public-issue-gate-a",
            teacher_id=admin.id,
            class_id=class_a.class_id,
            seat_id=seat_a.id,
            join_code="ISSGA1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Issue for class A",
        ),
        Issue(
            user_id=student_user.id,
            actor_public_id="seat-public-issue-gate-b",
            teacher_id=admin.id,
            class_id=class_b.class_id,
            seat_id=seat_b.id,
            join_code="ISSGB1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Issue for class B",
        ),
    ])
    db.session.commit()

    _login_admin(client, admin.id, user_id=user.id, class_id=class_a.class_id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "ISSGA1"

    response = client.get("/admin/issues")
    assert response.status_code == 200
    assert b"Issue for class A" in response.data
    assert b"Issue for class B" not in response.data


def test_add_individual_student_requires_current_class_context(client):
    admin = make_admin("student_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STUG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_student_count = db.session.query(Student).count()
    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Casey",
            "last_name": "Guard",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Student).count() == initial_student_count


@pytest.mark.skip(reason="Legacy add-student seat-counting assertions were tied to TeacherBlock semantics and need canonical rewrite.")
def test_add_individual_student_creates_single_student_seat_for_new_student(client):
    admin = make_admin("student_single_tb_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="SING001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "SING001"

    initial_student_count = Student.query.count()
    initial_link_count = StudentTeacher.query.filter_by(teacher_id=admin.id).count()
    class_row = ClassEconomy.query.filter_by(join_code="SING001").first()
    initial_student_seat_count = Seat.query.filter_by(class_id=class_row.class_id, block="A").filter(Seat.user_id.isnot(None)).count()

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Indivuniq",
            "last_name": "Guarduniq",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert Student.query.count() == initial_student_count + 1
    assert StudentTeacher.query.filter_by(teacher_id=admin.id).count() == initial_link_count + 1
    assert Seat.query.filter_by(class_id=class_row.class_id, block="A").filter(Seat.user_id.isnot(None)).count() == initial_student_seat_count + 1

    linked_seats = Seat.query.filter_by(class_id=class_row.class_id, block="A").filter(Seat.user_id.isnot(None)).all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert linked_seats[0].join_code == "SING001"
    assert linked_seats[0].dedupe_code is not None


@pytest.mark.skip(reason="Legacy add-student seat-counting assertions were tied to TeacherBlock semantics and need canonical rewrite.")
def test_add_manual_student_creates_single_student_seat_for_new_student(client):
    admin = make_admin("manual_single_tb_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="MANU001",
        block="B",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "MANU001"

    initial_student_count = Student.query.count()
    initial_link_count = StudentTeacher.query.filter_by(teacher_id=admin.id).count()
    class_row = ClassEconomy.query.filter_by(join_code="MANU001").first()
    initial_student_seat_count = Seat.query.filter_by(class_id=class_row.class_id, block="B").filter(Seat.user_id.isnot(None)).count()

    response = client.post(
        "/admin/student/add-manual",
        data={
            "first_name": "Manualuniq",
            "last_name": "Seatuniq",
            "dob": "2010-03-04",
            "block": "B",
            "username": "",
            "pin": "",
            "passphrase": "",
            "hall_passes": "3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert Student.query.count() == initial_student_count + 1
    assert StudentTeacher.query.filter_by(teacher_id=admin.id).count() == initial_link_count + 1
    assert Seat.query.filter_by(class_id=class_row.class_id, block="B").filter(Seat.user_id.isnot(None)).count() == initial_student_seat_count + 1

    linked_seats = Seat.query.filter_by(class_id=class_row.class_id, block="B").filter(Seat.user_id.isnot(None)).all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert linked_seats[0].join_code == "MANU001"
    assert linked_seats[0].dedupe_code is not None


@pytest.mark.skip(reason="Legacy add-student join-code assertions were tied to TeacherBlock-derived seat discovery and need canonical rewrite.")
def test_add_individual_student_uses_selected_class_join_code_when_block_has_other_scope(client):
    admin = make_admin("student_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="OLDA001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    create_class_scope(
        teacher=admin,
        join_code="NEWA001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "NEWA001"

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Scoped",
            "last_name": "Student",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    class_row = ClassEconomy.query.filter_by(join_code="NEWA001").first()
    linked_seat = (
        Seat.query
        .filter_by(class_id=class_row.class_id, block="A")
        .filter(Seat.user_id.isnot(None))
        .order_by(Seat.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert linked_seat.join_code == "NEWA001"


@pytest.mark.skip(reason="Legacy new-class student-add assertions were tied to TeacherBlock-derived shadow-seat creation and need canonical rewrite.")
def test_add_individual_student_create_new_class_section_mints_new_join_code(client):
    admin = make_admin("student_new_class_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="CURRA01",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "CURRA01"

    initial_class_count = ClassEconomy.query.count()

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Brand",
            "last_name": "Newclass",
            "dob": "2011-02-03",
            "block_select": "__CREATE_NEW__",
            "block": "B",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert ClassEconomy.query.count() == initial_class_count + 1

    linked_seat = (
        Seat.query
        .filter_by(block="B", join_code=ClassEconomy.query.filter(ClassEconomy.join_code != "CURRA01", ClassEconomy.user_id == admin.id).order_by(ClassEconomy.id.desc()).with_entities(ClassEconomy.join_code).scalar_subquery())
        .filter(Seat.user_id.isnot(None))
        .order_by(Seat.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert linked_seat.join_code != "CURRA01"
    assert ClassEconomy.query.filter_by(join_code=linked_seat.join_code).first() is not None

    teacher_student_seat = Seat.query.filter_by(
        join_code=linked_seat.join_code,
        role="student",
        student_id=None,
    ).first()
    assert teacher_student_seat is not None
    assert teacher_student_seat.block == "B"

    with client.session_transaction() as sess:
        assert sess["current_join_code"] == linked_seat.join_code


def test_admin_students_surfaces_teacher_shadow_claim_dob(client):
    admin = make_admin("teacher_shadow_info_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_row = create_class_scope(
        teacher=admin,
        join_code="SHADOW1",
        block="B",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    from app.routes.admin import _ensure_teacher_student_seat

    _ensure_teacher_student_seat(admin.id, "SHADOW1", "B")
    db.session.commit()

    _login_admin(client, admin.id, user_id=user.id, class_id=class_row.class_id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "SHADOW1"

    response = client.get("/admin/students")
    assert response.status_code == 200
    teacher_shadow = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(
            Seat.class_id == class_row.class_id,
            IdentityProfile.profile_type == "teacher_shadow_student",
        )
        .first()
    )
    assert teacher_shadow is not None
    assert teacher_shadow.join_code == "SHADOW1"
    assert teacher_shadow.block == "B"


def test_store_create_requires_current_class_context(client):
    admin = make_admin("store_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STOG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_store_item_count = db.session.query(StoreItem).count()
    response = client.post(
        "/admin/store",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/store")
    assert db.session.query(StoreItem).count() == initial_store_item_count


def test_payroll_settings_requires_current_class_context(client):
    admin = make_admin("payroll_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    create_class_scope(teacher=admin, join_code="PAYG001")
    db.session.commit()

    _login_admin(client, admin.id, user_id=user.id)

    initial_settings_count = db.session.query(PayrollSettings).count()
    response = client.post(
        "/admin/payroll/settings",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    assert db.session.query(PayrollSettings).count() == initial_settings_count


def test_payroll_settings_uses_feature_scope_blocks_not_student_block_text(client):
    admin = make_admin("payroll_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    profile = IdentityProfile(profile_type="student", first_name="Scope", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    class_row = create_class_scope(
        teacher=admin,
        join_code="PAYS002",
        block="B",
        student=student,
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin.id, user_id=user.id, class_id=class_row.class_id, seat_id=teacher_seat.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = class_row.join_code

    response = client.post(
        "/admin/payroll/settings",
        data={
            "cwi_block": "B",
            "settings_mode": "simple",
            "simple_pay_rate": "15.0",
            "simple_frequency": "biweekly",
            "expected_weekly_hours": "5.0",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is not None


def test_class_scoped_write_rejects_stale_session_join_code(client):
    admin = make_admin("stale_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="LIVE001")
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STALE999"

    initial_student_count = db.session.query(Student).count()
    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Stale",
            "last_name": "Session",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Student).count() == initial_student_count


def test_store_query_scope_does_not_implicitly_switch_session_context(client):
    admin = make_admin("query_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STOREA1", block="A", create_claimed_teacher_block=True)
    create_class_scope(teacher=admin, join_code="STOREB2", block="B", create_claimed_teacher_block=True)
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STOREA1"

    response = client.get("/admin/store?join_code=STOREB2")
    assert response.status_code == 200

    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "STOREA1"


def test_class_scoped_post_rejects_request_join_code_mismatch(client):
    admin = make_admin("mismatch_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_a = create_class_scope(teacher=admin, join_code="PAYA01", block="A", create_claimed_teacher_block=True)
    create_class_scope(teacher=admin, join_code="PAYB02", block="B", create_claimed_teacher_block=True)
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin.id, user_id=user.id, class_id=class_a.class_id, seat_id=teacher_seat.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "PAYA01"

    initial_settings_count = db.session.query(PayrollSettings).count()
    response = client.post(
        "/admin/payroll/settings",
        data={
            "join_code": "PAYB02",
            "cwi_block": "B",
            "settings_mode": "simple",
            "simple_pay_rate": "15.0",
            "simple_frequency": "biweekly",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    assert db.session.query(PayrollSettings).count() == initial_settings_count
