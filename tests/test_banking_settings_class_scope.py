from datetime import datetime, timezone

from app.extensions import db
from app.models import BankingSettings, ClassFeature, Seat, User
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import make_teacher
from tests.helpers.admin_context import login_teacher


def test_banking_settings_update_persists_class_scoped_row(client):
    teacher = make_teacher("bank_scope_admin")
    db.session.flush()

    class_row = create_class_scope(teacher_user=teacher, join_code="BANK001")
    db.session.add(ClassFeature(class_id=class_row.class_id, feature_name="banking"))
    db.session.commit()

    login_teacher(client, teacher, join_code="BANK001", class_id=class_row.class_id)

    response = client.post(
        "/admin/banking/settings",
        data={
            "settings_block": "B",
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
    assert response.headers["Location"].endswith("/admin/banking?settings_block=B")

    saved = BankingSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is not None
    assert float(saved.savings_apy) == 4.5
    assert saved.class_id == class_row.class_id
    assert saved.block == "B"
