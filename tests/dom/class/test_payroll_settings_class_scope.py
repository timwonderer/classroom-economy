from app.extensions import db
from app.models import PayrollSettings, Seat, User
from tests.helpers.class_domain import update_expected_weekly_hours, update_payroll_settings
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__payroll_settings_update_persists_class_scoped_row(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_row = classroom.economy

    response = update_payroll_settings(
        client,
        cwi_block=classroom.economy.section,
        settings_mode="simple",
        simple_pay_rate="15.0",
        simple_frequency="biweekly",
        expected_weekly_hours="5.0",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 5.0


def test_DOM_CLASS_001__expected_weekly_hours_update_creates_class_scoped_row(client):
    classroom = initialize_as_teacher("ap_csp_p3", client, client.application)
    class_row = classroom.economy

    response = update_expected_weekly_hours(
        client,
        "7.5",
        apply_to_all=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    assert "cwi_block" not in response.headers["Location"]

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 7.5
