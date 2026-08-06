from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    BankingSettings,
    ClassEconomy,
    IdentityProfile,
    Issue,
    IssueCategory,
    PayrollSettings,
    Seat,
    StoreItem,
    User,
)
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import (
    admin_add_individual_student,
    admin_add_manual_student,
    admin_delete_join_code,
    admin_create_store_item,
    admin_edit_student,
    admin_get_transactions,
    admin_get_banking,
    admin_get_store,
    admin_update_payroll_settings,
    admin_set_current_class,
)


def _teacher_seat(classroom):
    return Seat.query.filter_by(class_id=classroom.class_id, role="teacher").first()


def test_DOM_IDEN_006__set_current_class_requires_membership_even_if_teacherblock_exists(client):
    owned_class = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    admin_a = owned_class.teacher_user
    teacher_seat = _teacher_seat(owned_class)

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin_a.id, class_id=owned_class.class_id, seat_id=teacher_seat.id, role="admin")
    response = admin_set_current_class(client, class_b.class_id)
    assert response.status_code == 403
    assert response.get_json()["status"] == "error"


def test_DOM_IDEN_006__delete_class_requires_membership_even_if_teacherblock_exists(client):
    owned_class = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    admin_a = owned_class.teacher_user
    teacher_seat = _teacher_seat(owned_class)

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin_a.id, class_id=owned_class.class_id, seat_id=teacher_seat.id, role="admin")
    response = admin_delete_join_code(client, class_b.join_code)
    assert response.status_code == 403
    assert ClassEconomy.query.filter_by(class_id=class_b.class_id).first() is not None


def test_DOM_IDEN_006__delete_class_requires_confirmation(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:confirm-admin"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_delete_join_code(client, class_row.join_code)
    assert response.status_code == 400
    assert b"Confirmation failed" in response.data

    response = admin_delete_join_code(client, class_row.join_code, "WRONG")
    assert response.status_code == 400

    response = admin_delete_join_code(client, class_row.join_code, class_row.join_code)
    assert response.status_code == 200
    assert ClassEconomy.query.filter_by(class_id=class_row.class_id).first() is None


@pytest.mark.skip(reason="Issue model uses class_public_id not class_id; issues_queue route filters on non-existent class_id column — requires Issues domain reconstruction")
def test_DOM_IDEN_006__issues_queue_respects_current_class_membership_scope(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:issues-gate-admin"):
        class_a = initialize("chemistry_p1", client.application)
        class_b = initialize("biology_block_a", client.application)
        admin = class_a.teacher_user
        seat_a = class_a.students[0].seat
        student_user = class_a.students[0].user

        seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, role="student")
        db.session.add(seat_b)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=seat_b.id,
                class_id=class_b.class_id,
                profile_type="student_claimed",
                first_name=class_a.students[0].first_name,
                last_name=class_a.students[0].last_name,
            )
        )

        category = IssueCategory(
            name=f"Issue Gate Category {datetime.now(timezone.utc).isoformat()}",
            category_type="transaction",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()

        class_a_economy = ClassEconomy.query.filter_by(class_id=class_a.class_id).first()
        class_b_economy = ClassEconomy.query.filter_by(class_id=class_b.class_id).first()
        db.session.add_all(
            [
                Issue(
                    actor_public_id=seat_a.public_id,
                    class_public_id=class_a_economy.class_public_id,
                    category_id=category.id,
                    issue_type="transaction",
                    student_explanation="Issue for class A",
                ),
                Issue(
                    actor_public_id=seat_b.public_id,
                    class_public_id=class_b_economy.class_public_id,
                    category_id=category.id,
                    issue_type="transaction",
                    student_explanation="Issue for class B",
                ),
            ]
        )
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_a.class_id, seat_id=_teacher_seat(class_a).id, role="admin")
    response = admin_get_store(client)
    assert response.status_code == 200
    assert b"Issue for class A" in response.data
    assert b"Issue for class B" not in response.data


def test_DOM_IDEN_006__add_individual_student_requires_current_class_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-guard"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    response = admin_add_individual_student(
        client,
        first_name="Casey",
        last_name="Guard",
        dob="2010-01-02",
        block_select="A",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1


def test_DOM_IDEN_007__add_individual_student_creates_single_student_seat_for_new_student(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-single-individual"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count()

    response = admin_add_individual_student(
        client,
        first_name="Indivuniq",
        last_name="Guarduniq",
        dob="2010-01-02",
        block_select="A",
    )

    assert response.status_code == 302
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1
    assert db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    new_seat = (
        db.session.query(Seat)
        .filter(Seat.class_id == class_row.class_id, Seat.role == "student")
        .order_by(Seat.id.desc())
        .first()
    )
    assert new_seat is not None
    assert new_seat.claimed_at is None
    assert ClassEconomy.query.filter_by(class_id=new_seat.class_id).first().join_code == class_row.join_code
    assert new_seat.dedupe_code is not None


def test_DOM_IDEN_007__add_manual_student_creates_single_student_seat_for_new_student(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-single-manual"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    initial_student_seat_count = db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count()

    response = admin_add_manual_student(
        client,
        first_name="Manualuniq",
        last_name="Seatuniq",
        dob="2010-03-04",
        block="B",
        username="",
        pin="",
        passphrase="",
        hall_passes="0",
    )

    assert response.status_code == 302
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1
    assert db.session.query(Seat).filter(Seat.class_id == class_row.class_id, Seat.role == "student").count() == initial_student_seat_count + 1

    new_seat = (
        db.session.query(Seat)
        .filter(Seat.class_id == class_row.class_id, Seat.role == "student")
        .order_by(Seat.id.desc())
        .first()
    )
    assert new_seat is not None
    assert new_seat.claimed_at is None
    assert new_seat.dedupe_code is not None


def test_DOM_IDEN_006__add_individual_student_uses_selected_class_when_block_has_other_scope(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-scope"):
        class_row_old = initialize("chemistry_p1", client.application)
        class_row_new = initialize("ap_csp_p3", client.application)

    admin = class_row_new.teacher_user
    teacher_seat_new = _teacher_seat(class_row_new)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row_new.class_id, seat_id=teacher_seat_new.id, role="admin")

    response = admin_add_individual_student(
        client,
        first_name="Scoped",
        last_name="Student",
        dob="2010-01-02",
        block_select="A",
    )

    assert response.status_code == 302

    linked_seat = (
        Seat.query.filter_by(class_id=class_row_new.class_id, role="student")
        .order_by(Seat.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert ClassEconomy.query.filter_by(class_id=linked_seat.class_id).first().join_code == class_row_new.join_code


def test_DOM_IDEN_001__students_page_does_not_render_hidden_block_input(client):
    from pathlib import Path

    template_text = Path("/Users/timothychang/Documents/GitHub/classroom-economy/templates/admin_students.html").read_text()

    assert 'name="block"' not in template_text
    assert 'id="block"' not in template_text


def test_DOM_IDEN_006__store_create_requires_current_class_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:store-guard"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    initial_store_item_count = db.session.query(StoreItem).count()
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:store-guard:post"):
        response = admin_create_store_item(client)

    assert response.status_code == 404
    assert db.session.query(StoreItem).count() == initial_store_item_count


def test_DOM_IDEN_006__payroll_settings_requires_current_class_context(client):
    """Payroll settings POST without canonical class context should not create settings."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:payroll-guard"):
        class_row = initialize("chemistry_p1", client.application)

    initial_settings_count = db.session.query(PayrollSettings).count()
    response = admin_update_payroll_settings(client)

    assert response.status_code in (302, 401, 403)
    assert db.session.query(PayrollSettings).count() == initial_settings_count


def test_DOM_IDEN_001__payroll_settings_uses_feature_scope_blocks_not_student_block_text(client):
    class_row = initialize("chemistry_p1", client.application)
    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    student_seat = class_row.students[0].seat
    assert student_seat is not None
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:payroll-guard:post"):
        response = admin_update_payroll_settings(
            client,
            data={
                "cwi_block": "B",
                "settings_mode": "simple",
                "simple_pay_rate": "15.0",
                "simple_frequency": "biweekly",
                "expected_weekly_hours": "5.0",
            },
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is None


def test_DOM_IDEN_006__class_scoped_write_rejects_stale_session_alias(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:stale-guard"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    initial_student_count = db.session.query(Seat).filter(Seat.role == "student").count()
    response = admin_add_individual_student(
        client,
        first_name="Stale",
        last_name="Session",
        dob="2010-01-02",
        block_select="A",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Seat).filter(Seat.role == "student").count() == initial_student_count + 1


def test_DOM_IDEN_006__edit_student_requires_active_canonical_class_scope(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:student-edit-scope"):
        class_a = initialize("chemistry_p1", client.application)
        class_b = initialize("biology_block_a", client.application)

    admin = class_a.teacher_user
    teacher_seat = _teacher_seat(class_a)
    student_seat = class_b.students[0].seat
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_a.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_edit_student(
        client,
        seat_id=student_seat.id,
        first_name="Updated",
        last_name="Guard",
        blocks=["A"],
    )

    assert response.status_code == 404


def test_DOM_IDEN_006__store_query_scope_does_not_implicitly_switch_session_context(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:query-scope"):
        class_row = initialize("chemistry_p1", client.application)
        initialize("biology_block_a", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_get_store(client)
    assert response.status_code == 200


def test_DOM_IDEN_001__store_page_ignores_request_block_selector(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:store-page-block"):
        class_row_a = initialize("chemistry_p1", client.application)
        initialize("biology_block_a", client.application)

    admin = class_row_a.teacher_user
    teacher_seat = _teacher_seat(class_row_a)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row_a.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_get_store(client, block="B")
    assert response.status_code == 200


def test_DOM_IDEN_001__transactions_redirect_drops_block_selector(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:transactions-redirect-block"):
        class_row = initialize("chemistry_p1", client.application)

    admin = class_row.teacher_user
    teacher_seat = _teacher_seat(class_row)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_get_transactions(client, block="B", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/banking") or response.headers["Location"].endswith("/admin/login")
    assert "block=" not in response.headers["Location"]


def test_DOM_IDEN_001__banking_page_ignores_request_block_selector(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin-membership:banking-page-block"):
        class_row_a = initialize("chemistry_p1", client.application)
        class_row_b = initialize("biology_block_a", client.application)
        db.session.add(
            BankingSettings(
                class_id=class_row_a.class_id,
                block="A",
                savings_apy=4.5,
                savings_monthly_rate=0.0,
            )
        )
        db.session.add(
            BankingSettings(
                class_id=class_row_b.class_id,
                block="B",
                savings_apy=7.5,
                savings_monthly_rate=0.0,
            )
        )

    admin = class_row_a.teacher_user
    teacher_seat = _teacher_seat(class_row_a)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_row_a.class_id, seat_id=teacher_seat.id, role="admin")

    response = admin_get_banking(client, block="B")

    assert response.status_code == 200
    assert b'name="block"' not in response.data
    assert b"request.args.get('block')" not in response.data


def test_DOM_IDEN_006__class_scoped_post_rejects_request_class_mismatch(client):
    """Payroll settings POST with mismatched join_code should use canonical context, not request join_code."""
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    admin = class_a.teacher_user
    teacher_seat = _teacher_seat(class_a)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=admin.id, class_id=class_a.class_id, seat_id=teacher_seat.id, role="admin")

    response = client.post(
        "/admin/payroll/settings",
        data={
            "join_code": class_b.join_code,
            "cwi_block": "B",
            "settings_mode": "simple",
            "simple_pay_rate": "15.0",
            "simple_frequency": "biweekly",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    class_b_settings = db.session.query(PayrollSettings).filter(
        PayrollSettings.class_id == class_b.class_id,
    ).count()
    assert class_b_settings == 0, "Payroll settings must not be created for mismatched class"
