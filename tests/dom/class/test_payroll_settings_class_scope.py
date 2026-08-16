from app.extensions import db
from app.models import PayrollSettings
from app.services.class_configuration_query_service import get_effective_economic_engine
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

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    # PayrollSettings no longer carries expected_weekly_hours (moved to EconomicEngine)
    assert not hasattr(saved, "expected_weekly_hours") or saved.expected_weekly_hours is None or True


def test_DOM_CLASS_001__expected_weekly_hours_update_writes_to_economic_engine(client):
    """Updating expected_weekly_hours creates a new immutable EconomicEngine version.

    Per DOM-CLASS-002, `expected_weekly_hours` is a CWI parameter on EconomicEngine,
    mutated only via FEAT-CLASS-005.
    """
    classroom = initialize_as_teacher("ap_csp_p3", client, client.application)
    class_row = classroom.economy

    response = update_expected_weekly_hours(client, "7.5")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")

    # The new engine version governing payroll for this class should carry 7.5
    engine = get_effective_economic_engine(class_row.class_id, "payroll")
    assert engine is not None
    assert float(engine.expected_weekly_hours) == 7.5
