import pytest

from app.extensions import db
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.class_domain import update_rent_settings
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.class_domain import enable_class_feature

pytestmark = [pytest.mark.critical, pytest.mark.regression]


def test_DOM_CLASS_001__rent_settings_update_persists_class_scoped_row(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="rent")

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

    # The POST supersedes rather than edits, so read the current policy through
    # the canonical reader (append-only: DOM-POL-001 §VI.1).
    saved = get_rent_settings(classroom.class_id)
    assert saved is not None
    assert float(saved.rent_amount) == 75.0
    assert saved.class_id == classroom.class_id
