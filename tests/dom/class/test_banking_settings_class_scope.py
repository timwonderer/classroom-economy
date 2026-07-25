from app.extensions import db
from app.models import BankingSettings
from tests.helpers.banking_domain import update_banking_settings
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__banking_settings_update_persists_class_scoped_row(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature_name="banking")

    response = update_banking_settings(
        client,
        rate_input_mode="apy",
        savings_apy="4.5",
        savings_monthly_rate="0.0",
        interest_calculation_type="simple",
        compound_frequency="monthly",
        interest_schedule_type="monthly",
        interest_schedule_cycle_days="30",
        overdraft_fee_type="flat",
        overdraft_fee_flat_amount="15.00",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/banking")

    saved = BankingSettings.query.filter_by(class_id=classroom.class_id).first()
    assert saved is not None
    assert float(saved.savings_apy) == 4.5
    assert saved.class_id == classroom.class_id
