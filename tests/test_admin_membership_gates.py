from datetime import datetime, timezone

import pytest

from tests.helpers.v2_fixtures import make_teacher as make_admin
from app.extensions import db
from app.models import (
    ClassEconomy,
    IdentityProfile,
    Issue,
    IssueCategory,
    PayrollSettings,
    Seat,
    StoreItem,
    User,
    UserRole,
)
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


def _bind_canonical_teacher(admin):
    """No-op shim: admin is already a User in V2."""
    return admin


def _login_admin(client, admin_or_id, *, user_id: int | None = None, class_id: str | None = None, seat_id: int | None = None):
    # admin_or_id may be a User object or int (legacy)
    if isinstance(admin_or_id, int):
        admin = db.session.get(User, admin_or_id)
    else:
        admin = admin_or_id
    if admin is None:
        return
    resolved_class_id = class_id
    resolved_seat_id = seat_id
    if resolved_class_id is None:
        owned_classes = ClassEconomy.query.filter_by(user_id=admin.id).order_by(ClassEconomy.class_id.asc()).all()
        if len(owned_classes) == 1:
            resolved_class_id = owned_classes[0].class_id
            teacher_seat = Seat.query.filter_by(class_id=resolved_class_id, role="teacher", user_id=admin.id).first()
            if teacher_seat is not None:
                resolved_seat_id = teacher_seat.id
    login_teacher(client, admin, class_id=resolved_class_id, seat_id=resolved_seat_id)


def test_set_current_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("gate_admin_a", "secret-a")
    admin_b = make_admin("gate_admin_b", "secret-b")
    db.session.flush()

    owned_class = create_class_scope(
        teacher_user=admin_a, join_code="OWNG001")

    create_class_scope(
        teacher_user=admin_b,
        join_code="GATE001"
    )
    db.session.commit()

    user_a = _bind_canonical_teacher(admin_a)
    db.session.commit()

    _login_admin(client, admin_a.id, user_id=user_a.id, class_id=owned_class.class_id, seat_id=Seat.query.filter_by(class_id=owned_class.class_id, role="teacher").first().id)
    class_row = ClassEconomy.query.filter_by(join_code="GATE001").first()
    response = client.post("/admin/current-class", json={"class_id": class_row.class_id})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_delete_join_code_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("delete_gate_a", "secret-a")
    admin_b = make_admin("delete_gate_b", "secret-b")
    db.session.flush()

    owned_class = create_class_scope(
        teacher_user=admin_a, join_code="OWND001")

    create_class_scope(
        teacher_user=admin_b,
        join_code="DELG001"
    )
    db.session.commit()

    user_a = _bind_canonical_teacher(admin_a)
    db.session.commit()

    _login_admin(client, admin_a.id, user_id=user_a.id, class_id=owned_class.class_id, seat_id=Seat.query.filter_by(class_id=owned_class.class_id, role="teacher").first().id)
    response = client.post("/admin/join-code/delete", json={"join_code": "DELG001"})
    assert response.status_code == 403
    assert ClassEconomy.query.filter_by(join_code="DELG001").first() is not None


def test_delete_join_code_requires_confirmation(client):
    admin = make_admin("confirm_admin", "secret")
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_row = create_class_scope(
        teacher_user=admin, join_code="CONF001")
    db.session.commit()

    _login_admin(client, admin.id, user_id=user.id, class_id=class_row.class_id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_row.class_id,
            seat_id=Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first().id,
            role="teacher",
            join_code="CONF001",
        )

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
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_a = create_class_scope(
        teacher_user=admin, join_code="ISSGA1")
    class_b = create_class_scope(
        teacher_user=admin, join_code="ISSGB1")
    profile = IdentityProfile(profile_type="student", first_name="Gate", last_name="Stone")
    db.session.add(profile)
    student_user = User(username_hash="gate_student_hash", username_lookup_hash="gate_student_lookup", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat_a = Seat(user_id=student_user.id, class_id=class_a.class_id, role="student")
    db.session.add(seat_a)
    db.session.flush()
    profile.seat_id = seat_a.id
    seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, role="student")
    db.session.add(seat_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type="student_claimed", first_name="Gate", last_name="Stone"))

    category = IssueCategory(
        name=f"Issue Gate Category {datetime.now(timezone.utc).isoformat()}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    db.session.add_all([
        Issue(
            student_first_name="Gate",
            student_last_initial="S",
            user_id=student_user.id,
            actor_public_id="seat-public-issue-gate-a",
            class_id=class_a.class_id,
            seat_id=seat_a.id,
            join_code="ISSGA1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Issue for class A",
        ),
        Issue(
            student_first_name="Gate",
            student_last_initial="S",
            user_id=student_user.id,
            actor_public_id="seat-public-issue-gate-b",
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
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_a.class_id,
            seat_id=Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first().id,
            role="teacher",
            join_code="ISSGA1",
        )

    response = client.get("/admin/issues")
    assert response.status_code == 200
    assert b"Issue for class A" in response.data
    assert b"Issue for class B" not in response.data


def test_add_individual_student_requires_current_class_context(client):
    admin = make_admin("student_guard_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin, join_code="STUG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
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
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1


def test_add_individual_student_creates_single_student_seat_for_new_student(client):
    admin = make_admin("student_single_tb_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin,
        join_code="SING001"
    )
    db.session.commit()

    _login_admin(client, admin.id)
    class_row_sing = ClassEconomy.query.filter_by(join_code="SING001").first()
    teacher_seat_sing = Seat.query.filter_by(class_id=class_row_sing.class_id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_sing.class_id,
            seat_id=teacher_seat_sing.id,
            role="teacher",
            join_code="SING001",
        )

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    class_row = ClassEconomy.query.filter_by(join_code="SING001").first()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count()

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
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1
    assert db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    linked_seats = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert ClassEconomy.query.filter_by(class_id=linked_seats[0].class_id).first().join_code == "SING001"
    assert linked_seats[0].dedupe_code is not None


def test_add_manual_student_creates_single_student_seat_for_new_student(client):
    admin = make_admin("manual_single_tb_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin,
        join_code="MANU001"
    )
    db.session.commit()

    _login_admin(client, admin.id)
    class_row_manu = ClassEconomy.query.filter_by(join_code="MANU001").first()
    teacher_seat_manu = Seat.query.filter_by(class_id=class_row_manu.class_id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_manu.class_id,
            seat_id=teacher_seat_manu.id,
            role="teacher",
            join_code="MANU001",
        )

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    class_row = ClassEconomy.query.filter_by(join_code="MANU001").first()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count()

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
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1
    assert db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    linked_seats = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert linked_seats[0].dedupe_code is not None


def test_add_individual_student_uses_selected_class_join_code_when_block_has_other_scope(client):
    admin = make_admin("student_scope_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin,
        join_code="OLDA001"
    )
    create_class_scope(
        teacher_user=admin,
        join_code="NEWA001"
    )
    db.session.commit()

    _login_admin(client, admin.id)
    class_row_new = ClassEconomy.query.filter_by(join_code="NEWA001").first()
    teacher_seat_new = Seat.query.filter_by(class_id=class_row_new.class_id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_new.class_id,
            seat_id=teacher_seat_new.id,
            role="teacher",
            join_code="NEWA001",
        )

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
        .filter_by(class_id=class_row.class_id, role="student")
        .order_by(Seat.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert ClassEconomy.query.filter_by(class_id=linked_seat.class_id).first().join_code == "NEWA001"

def test_store_create_requires_current_class_context(client):
    admin = make_admin("store_guard_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin, join_code="STOG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_store_item_count = db.session.query(StoreItem).count()
    response = client.post(
        "/admin/store",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert db.session.query(StoreItem).count() == initial_store_item_count


def test_payroll_settings_requires_current_class_context(client):
    admin = make_admin("payroll_guard_admin", "secret")
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    create_class_scope(
        teacher_user=admin, join_code="PAYG001")
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
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    profile = IdentityProfile(profile_type="student", first_name="Scope", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student_user = User(username_hash="scope_student_hash", username_lookup_hash="scope_student_lookup", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()

    class_row = create_class_scope(
        teacher_user=admin,
        join_code="PAYS002"
    )
    student_seat = Seat(user_id=student_user.id, class_id=class_row.class_id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(student_seat)
    db.session.flush()
    profile.seat_id = student_seat.id
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
    assert saved is None


def test_class_scoped_write_rejects_stale_session_join_code(client):
    admin = make_admin("stale_guard_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin, join_code="LIVE001")
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STALE999"

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
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
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1


def test_store_query_scope_does_not_implicitly_switch_session_context(client):
    admin = make_admin("query_scope_admin", "secret")
    db.session.flush()

    create_class_scope(
        teacher_user=admin, join_code="STOREA1")
    create_class_scope(
        teacher_user=admin, join_code="STOREB2")
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STOREA1"

    response = client.get("/admin/store?join_code=STOREB2")
    assert response.status_code == 200


def test_class_scoped_post_rejects_request_join_code_mismatch(client):
    admin = make_admin("mismatch_guard_admin", "secret")
    db.session.flush()
    user = _bind_canonical_teacher(admin)

    class_a = create_class_scope(
        teacher_user=admin, join_code="PAYA01")
    create_class_scope(
        teacher_user=admin, join_code="PAYB02")
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
