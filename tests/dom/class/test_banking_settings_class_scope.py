from app.models import EconomicEngine
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__banking_settings_surface_redirects_to_economic_engine(client):
    """The legacy banking-settings surface is retired; banking policy is owned by
    the Economic Engine (DOM-CLASS-003; the BankingSettings table was removed in
    migration dc3d4e5f6a7b). A teacher reaching /admin/banking must be redirected
    to the canonical Economic Engine configuration surface.

    The banking feature must be enabled first: /admin/banking is feature-gated in
    admin.before_request, which renders the feature-disabled page (200) before the
    redirect view runs when banking is off.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="banking")

    response = client.get("/admin/banking")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/economic-engine")

    saved = EconomicEngine.query.filter_by(class_id=classroom.class_id).first()
    assert saved is not None
    assert saved.class_id == classroom.class_id
