from datetime import datetime, timezone

import pytest

from tests.helpers.v2_fixtures import seed_canonical_admin, seed_student_identity
from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    ClassEconomy,
    Issue,
    IssueCategory,
    PayrollSettings,
    Seat,
    StoreItem,
    User,
)
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


def _login_admin(client, admin: User, *, class_id: str | None = None, seat_id: int | None = None):
    if class_id is None:
        raise ValueError("admin membership gate tests require an explicit canonical class scope")
    login_teacher(client, admin, class_id=class_id, seat_id=seat_id)


def test_set_current_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = seed_canonical_admin("gate_admin_a", "secret-a").user
    admin_b = seed_canonical_admin("gate_admin_b", "secret-b").user

    owned_class = create_class_scope(
        teacher_user=admin_a, join_code="OWNG001")

    class_b = create_class_scope(
        teacher_user=admin_b,
        join_code="GATE001"
    )
    _login_admin(client, admin_a, class_id=owned_class.class_id, seat_id=Seat.query.filter_by(class_id=owned_class.class_id, role="teacher").first().id)
    response = client.post("/admin/current-class", json={"class_id": class_b.class_id})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_delete_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = seed_canonical_admin("delete_gate_a", "secret-a").user
    admin_b = seed_canonical_admin("delete_gate_b", "secret-b").user

    owned_class = create_class_scope(
        teacher_user=admin_a, join_code="OWND001")

    class_b = create_class_scope(
        teacher_user=admin_b,
        join_code="DELG001"
    )
    _login_admin(client, admin_a, class_id=owned_class.class_id, seat_id=Seat.query.filter_by(class_id=owned_class.class_id, role="teacher").first().id)
    response = client.post("/admin/join-code/delete", json={"join_code": "DELG001"})
    assert response.status_code == 403
    assert ClassEconomy.query.filter_by(class_id=class_b.class_id).first() is not None


def test_delete_class_requires_confirmation(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:confirm-admin"):
        admin = seed_canonical_admin("confirm_admin", "secret").user
        class_row = create_class_scope(
            teacher_user=admin, join_code="CONF001")

    _login_admin(client, admin, class_id=class_row.class_id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row.class_id,
            seat_id=Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first().id,
            role="teacher",
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
    assert ClassEconomy.query.filter_by(class_id=class_row.class_id).first() is None


def test_issues_queue_respects_current_class_membership_scope(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:issues-gate-admin"):
        admin = seed_canonical_admin("issues_gate_admin", "secret").user

        class_a = create_class_scope(
            teacher_user=admin, join_code="ISSGA1")
        class_b = create_class_scope(
            teacher_user=admin, join_code="ISSGB1")
        seat_a = make_student_identity(
            class_id=class_a.class_id,
            first_name="Gate",
            last_name="Stone",
            username="gate_student",
        )
        student_user = db.session.get(User, seat_a.user_id)
        assert student_user is not None
        seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, role="student")
        db.session.add(seat_b)
        db.session.flush()
        from app.models import IdentityProfile
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
                    user_id=student_user.id,
                    actor_public_id="seat-public-issue-gate-a",
                    class_id=class_a.class_id,
                    seat_id=seat_a.id,
                    join_code=class_a.join_code,
                    category_id=category.id,
                    issue_type="transaction",
                    student_explanation="Issue for class A",
                ),
                Issue(
                    user_id=student_user.id,
                    actor_public_id="seat-public-issue-gate-b",
                    class_id=class_b.class_id,
                    seat_id=seat_b.id,
                    join_code=class_b.join_code,
                    category_id=category.id,
                    issue_type="transaction",
                    student_explanation="Issue for class B",
                ),
        ])
        db.session.flush()

    _login_admin(client, admin, class_id=class_a.class_id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_a.class_id,
            seat_id=Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first().id,
            role="teacher",
        )

    response = client.get("/admin/issues")
    assert response.status_code == 200
    assert b"Issue for class A" in response.data
    assert b"Issue for class B" not in response.data


def test_add_individual_student_requires_current_class_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-guard"):
        admin = seed_canonical_admin("student_guard_admin", "secret").user

        class_row = create_class_scope(
            teacher_user=admin, join_code="STUG001")

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-guard:post"):
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
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-single-individual"):
        admin = seed_canonical_admin("student_single_tb_admin", "secret").user

        class_row_sing = create_class_scope(
            teacher_user=admin,
            join_code="SING001"
        )

    teacher_seat_sing = Seat.query.filter_by(class_id=class_row_sing.class_id, role="teacher").first()
    assert teacher_seat_sing is not None
    _login_admin(client, admin, class_id=class_row_sing.class_id, seat_id=teacher_seat_sing.id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_sing.class_id,
            seat_id=teacher_seat_sing.id,
            role="teacher",
        )

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row_sing.class_id, Seat.role == "student").count()

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
    assert db.session.query(Seat).filter(Seat.class_id == class_row_sing.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    linked_seats = db.session.query(Seat).filter(Seat.class_id == class_row_sing.class_id, Seat.role == "student").all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert ClassEconomy.query.filter_by(class_id=linked_seats[0].class_id).first().join_code == "SING001"
    assert linked_seats[0].dedupe_code is not None


def test_add_manual_student_creates_single_student_seat_for_new_student(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-single-manual"):
        admin = seed_canonical_admin("manual_single_tb_admin", "secret").user

        class_row_manu = create_class_scope(
            teacher_user=admin,
            join_code="MANU001",
        )

    teacher_seat_manu = Seat.query.filter_by(class_id=class_row_manu.class_id, role="teacher").first()
    assert teacher_seat_manu is not None
    _login_admin(client, admin, class_id=class_row_manu.class_id, seat_id=teacher_seat_manu.id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_manu.class_id,
            seat_id=teacher_seat_manu.id,
            role="teacher",
        )

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row_manu.class_id, Seat.role == "student").count()

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
    assert db.session.query(Seat).filter(Seat.class_id == class_row_manu.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    linked_seats = db.session.query(Seat).filter(Seat.class_id == class_row_manu.class_id, Seat.role == "student").all()
    assert len(linked_seats) == 1
    assert linked_seats[0].claimed_at is None
    assert linked_seats[0].dedupe_code is not None


def test_add_individual_student_uses_selected_class_when_block_has_other_scope(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-scope"):
        admin = seed_canonical_admin("student_scope_admin", "secret").user

        class_row_old = create_class_scope(
            teacher_user=admin,
            join_code="OLDA001"
        )
        class_row_new = create_class_scope(
            teacher_user=admin,
            join_code="NEWA001"
        )

    teacher_seat_new = Seat.query.filter_by(class_id=class_row_new.class_id, role="teacher").first()
    assert teacher_seat_new is not None
    _login_admin(client, admin, class_id=class_row_new.class_id, seat_id=teacher_seat_new.id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row_new.class_id,
            seat_id=teacher_seat_new.id,
            role="teacher",
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

    linked_seat = (
        Seat.query
        .filter_by(class_id=class_row_new.class_id, role="student")
        .order_by(Seat.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert ClassEconomy.query.filter_by(class_id=linked_seat.class_id).first().join_code == "NEWA001"

def test_store_create_requires_current_class_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:store-guard"):
        admin = seed_canonical_admin("store_guard_admin", "secret").user

        class_row = create_class_scope(
            teacher_user=admin, join_code="STOG001")

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

    initial_store_item_count = db.session.query(StoreItem).count()
    response = client.post(
        "/admin/store",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert db.session.query(StoreItem).count() == initial_store_item_count


def test_payroll_settings_requires_current_class_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:payroll-guard"):
        admin = seed_canonical_admin("payroll_guard_admin", "secret").user

        class_row = create_class_scope(
            teacher_user=admin, join_code="PAYG001")

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

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
    admin = seed_canonical_admin("payroll_scope_admin", "secret").user
    class_row = create_class_scope(teacher_user=admin, join_code="PAYS002")
    student_seat = seed_student_identity(
        class_id=class_row.class_id,
        first_name="Scope",
        last_name="S",
        username="scope_student",
    ).seat

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

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


def test_class_scoped_write_rejects_stale_session_alias(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:stale-guard"):
        admin = seed_canonical_admin("stale_guard_admin", "secret").user

        class_row = create_class_scope(
            teacher_user=admin, join_code="LIVE001")

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:stale-guard:post"):
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
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:query-scope"):
        admin = seed_canonical_admin("query_scope_admin", "secret").user

        class_row = create_class_scope(
            teacher_user=admin, join_code="STOREA1")
        create_class_scope(
            teacher_user=admin, join_code="STOREB2")

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_row.class_id, seat_id=teacher_seat.id)

    response = client.get("/admin/store?join_code=STOREB2")
    assert response.status_code == 200


def test_class_scoped_post_rejects_request_class_mismatch(client):
    admin = seed_canonical_admin("mismatch_guard_admin", "secret").user

    class_a = create_class_scope(
        teacher_user=admin, join_code="PAYA01")
    create_class_scope(
        teacher_user=admin, join_code="PAYB02")

    teacher_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    assert teacher_seat is not None
    _login_admin(client, admin, class_id=class_a.class_id, seat_id=teacher_seat.id)

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
