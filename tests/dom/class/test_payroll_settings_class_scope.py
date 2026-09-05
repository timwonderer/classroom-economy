from app.extensions import db
from app.services.class_configuration_query_service import (
    get_effective_economic_engine,
    get_payroll_settings,
)
from app.services.payroll.builders import build_payroll_settings_display
from tests.helpers.class_domain import update_expected_weekly_hours, update_payroll_settings
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__payroll_settings_update_persists_class_scoped_row(client):
    """Payroll settings POST persists a class-scoped PayrollSettings row.

    `expected_weekly_hours` is no longer accepted on this route — it lives on
    EconomicEngine per DOM-CLASS-002 — so the form should still succeed and the
    row should carry the pay rate scoped to class_id.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_row = classroom.economy

    response = update_payroll_settings(
        client,
        settings_mode="simple",
        simple_pay_rate="15.0",
        simple_frequency="biweekly",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")

    # The submission supersedes its predecessor rather than editing it, so read
    # the policy currently governing the class rather than any row for it.
    saved = get_payroll_settings(class_row.class_id)
    assert saved is not None
    assert saved.class_id == class_row.class_id
    assert build_payroll_settings_display(saved)["display_hourly_rate_value"] == "15.00"


def test_DOM_CLASS_001__simple_hourly_rate_round_trips_without_precision_loss(client):
    """An hourly rate remains exact after per-minute database storage."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)

    response = update_payroll_settings(
        client,
        settings_mode="simple",
        simple_pay_rate="80.00",
        simple_frequency="biweekly",
    )

    assert response.status_code == 302
    db.session.expire_all()
    saved = get_payroll_settings(classroom.class_id)
    display = build_payroll_settings_display(saved)

    assert display["display_hourly_rate_value"] == "80.00"


def test_DOM_CLASS_001__expected_weekly_hours_update_writes_to_economic_engine(client):
    """Updating expected_weekly_hours creates a new immutable EconomicEngine version.

    Per DOM-CLASS-002, `expected_weekly_hours` is a CWI parameter on EconomicEngine,
    mutated only via FEAT-CLASS-005.
    """
    classroom = initialize_as_teacher("ap_csp_p3", client, client.application)
    class_row = classroom.economy

    response = update_expected_weekly_hours(client, "7.5")

    assert response.status_code == 302
    # expected_weekly_hours lives on the Economic Engine (DOM-CLASS-002), so the
    # route redirects back to the economic-engine surface, not payroll.
    assert response.headers["Location"].endswith("/admin/economic-engine")

    # The new engine version governing payroll for this class should carry 7.5
    engine = get_effective_economic_engine(class_row.class_id, "payroll")
    assert engine is not None
    assert float(engine.expected_weekly_hours) == 7.5
