from app.extensions import db
from app.models import RentSettings
from tests.helpers.class_domain import update_rent_settings
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.v2_fixtures import seed_class_feature


def test_DOM_CLASS_001__rent_settings_update_persists_class_scoped_row(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seed_class_feature(class_id=classroom.class_id, feature_name="rent")

    response = update_rent_settings(
        client,
        is_enabled="on",
        rent_amount="75.00",
        frequency_type="weekly",
        due_day_of_month="1",
        grace_period_days="3",
        late_penalty_amount="10.00",
        late_penalty_type="once",
        bill_preview_days="7",
    )

    assert response.status_code == 302

    saved = RentSettings.query.filter_by(class_id=classroom.class_id).first()
    assert saved is not None
    assert float(saved.rent_amount) == 75.0
    assert saved.class_id == classroom.class_id
