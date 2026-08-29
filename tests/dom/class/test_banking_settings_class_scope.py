from app.models import EconomicEngine
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__banking_surface_renders_as_guarded_real_page(client):
    """/admin/banking is a real, feature-guarded page over canonical banking state.

    The legacy BankingSettings table was removed in migration dc3d4e5f6a7b and the
    old redirect-to-economic-engine surface is retired. Banking is now a first-class
    guarded page: transaction logs plus savings/interest settings sourced from the
    EconomicEngine (DOM-CLASS-003). When banking is enabled and the class scope is
    lawfully resolved, the guard must fail OPEN -- rendering the page (200) and
    emitting NEITHER enforcement header.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="banking")

    response = client.get("/admin/banking")

    # Real page, not a redirect, and no enforcement interception.
    assert response.status_code == 200
    assert response.headers.get("X-Feature-Disabled") is None
    assert response.headers.get("X-Feature-Unresolved") is None

    # Banking policy is owned by the Economic Engine; a version must exist.
    saved = EconomicEngine.query.filter_by(class_id=classroom.class_id).first()
    assert saved is not None
    assert saved.class_id == classroom.class_id
