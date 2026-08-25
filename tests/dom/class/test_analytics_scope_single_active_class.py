"""Same-teacher/two-class isolation for the analytics class-scope resolver.

Guards ``analytics.resolve_current_class_context``. It previously enumerated
EVERY class owned by the acting teacher and returned them as ``available_classes``
options — an illegal in-feature class switcher (INV-ARC-004 V.1/V.3). The
analytics dashboard must bind to exactly the single active canonical class; the
only legal class switcher is the nav-bar context switcher (INV-ARC-010).

``chemistry_p1`` and ``ap_csp_p3`` are both owned by ``teacher_alice``, so
provisioning both yields one teacher owning two classes — the boundary a
class-isolation violation would leak across.
"""

from app.routes.analytics import resolve_current_class_context
from tests.helpers.classroom_initializer import initialize


def test_DOM_CLASS_001__analytics_available_classes_bind_to_active_only(client):
    """available_classes contains only the active class, never the sibling."""
    active = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    assert active.teacher_user.id == sibling.teacher_user.id
    assert active.class_id != sibling.class_id

    selected, available_classes = resolve_current_class_context(
        active.teacher_user.id, active.class_id
    )

    assert selected is not None
    assert selected["class_id"] == active.class_id
    class_ids = {opt["class_id"] for opt in available_classes}
    assert class_ids == {active.class_id}
    assert sibling.class_id not in class_ids
    assert len(available_classes) == 1


def test_DOM_CLASS_001__analytics_rejects_class_not_owned(client):
    """A class_id the teacher does not own resolves to nothing — never a fallback
    to some other class the teacher happens to own."""
    active = initialize("chemistry_p1", client.application)
    other_teacher = initialize("biology_block_a", client.application)
    assert active.teacher_user.id != other_teacher.teacher_user.id

    # Active teacher asks for a class owned by a DIFFERENT teacher.
    selected, available_classes = resolve_current_class_context(
        active.teacher_user.id, other_teacher.class_id
    )
    assert selected is None
    assert available_classes == []
