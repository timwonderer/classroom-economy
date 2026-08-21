from app.extensions import db
from app.models import EconomicEngine
from tests.helpers.banking_domain import update_banking_settings
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__banking_settings_surface_redirects_to_economic_engine(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    response = client.get("/admin/banking")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/banking")

    saved = EconomicEngine.query.filter_by(class_id=classroom.class_id).first()
    assert saved is not None
    assert saved.class_id == classroom.class_id
