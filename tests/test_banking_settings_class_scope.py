from app.extensions import db
from app.feats.base import FEATContext
from app.models import BankingSettings
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_feature
from tests.helpers.admin_context import login_teacher


def test_banking_settings_update_persists_class_scoped_row(client):
    teacher = seed_canonical_admin("bank_scope_admin").user

    with FEATContext("FEAT-IDEN-001", idempotency_key="banking_scope:create_class"):
        class_row = create_class_scope(teacher_user=teacher, join_code="BANKSET1", section="B")
        seed_class_feature(class_id=class_row.class_id, feature_name="banking")

    login_teacher(client, teacher, class_id=class_row.class_id)

    response = client.post(
        "/admin/banking/settings",
        data={
            "rate_input_mode": "apy",
            "savings_apy": "4.5",
            "savings_monthly_rate": "0.0",
            "interest_calculation_type": "simple",
            "compound_frequency": "monthly",
            "interest_schedule_type": "monthly",
            "interest_schedule_cycle_days": "30",
            "overdraft_fee_type": "flat",
            "overdraft_fee_flat_amount": "15.00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/banking")

    saved = BankingSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is not None
    assert float(saved.savings_apy) == 4.5
    assert saved.class_id == class_row.class_id
    assert saved.block == "B"
