"""Same-teacher/two-class isolation for admin feature-scope resolution.

Guards the P0 class-isolation invariant on the admin feature-scope helpers
(``get_admin_feature_join_code_options`` / ``resolve_admin_feature_join_code`` /
``require_admin_feature_scope``). These previously enumerated EVERY class owned
by the acting teacher and returned them as per-feature "class selector" options —
an illegal in-feature class switcher (INV-ARC-004 V.1/V.3). The sole legal class
switcher is the nav-bar context switcher (INV-ARC-010); every feature surface
must bind to exactly the single active canonical class.

``chemistry_p1`` and ``ap_csp_p3`` are both owned by ``teacher_alice``, so
provisioning both yields one teacher owning two classes — the boundary a
class-isolation violation would leak across.
"""

import pytest

from app.routes.admin import (
    get_admin_feature_join_code_options,
    resolve_admin_feature_join_code,
    require_admin_feature_scope,
)
from app.services.context_resolver import CanonicalContext
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize


def _ctx(classroom, active_class_id):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=active_class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def test_DOM_CLASS_001__feature_options_never_include_sibling_class(client):
    """Options list contains only the active class even when the sibling has the
    same feature enabled — no teacher-wide fan-out."""
    active = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    assert active.teacher_user.id == sibling.teacher_user.id
    assert active.class_id != sibling.class_id

    # Enable 'store' on BOTH classes: a fan-out bug would surface the sibling.
    enable_class_feature(class_id=active.class_id, feature="store")
    enable_class_feature(class_id=sibling.class_id, feature="store")

    ctx = _ctx(active, active.class_id)
    options = get_admin_feature_join_code_options("store", canonical_context=ctx)

    class_ids = {opt["class_id"] for opt in options}
    assert class_ids == {active.class_id}
    assert sibling.class_id not in class_ids
    assert len(options) == 1


def test_DOM_CLASS_001__resolve_join_code_binds_to_active_class(client):
    """resolve_admin_feature_join_code returns the active class's join code, never
    the sibling's, regardless of which class was provisioned last."""
    active = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    enable_class_feature(class_id=active.class_id, feature="store")
    enable_class_feature(class_id=sibling.class_id, feature="store")

    ctx = _ctx(active, active.class_id)
    resolved = resolve_admin_feature_join_code("store", canonical_context=ctx)
    assert resolved == active.join_code
    assert resolved != sibling.join_code


def test_DOM_CLASS_001__require_scope_ignores_requested_block(client):
    """A block/section label may never resolve or switch classes (INV-ARC-004 V.2).
    require_admin_feature_scope always binds to the active class regardless of a
    requested_block argument."""
    active = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    enable_class_feature(class_id=active.class_id, feature="store")
    enable_class_feature(class_id=sibling.class_id, feature="store")

    ctx = _ctx(active, active.class_id)
    # Even if the sibling's section label is passed, scope stays on the active class.
    scope = require_admin_feature_scope(
        "store",
        canonical_context=ctx,
        requested_block=(sibling.economy.section or "ZZZ"),
    )
    assert scope["class_id"] == active.class_id
    assert scope["class_id"] != sibling.class_id


def test_DOM_CLASS_001__require_scope_404s_when_no_active_class(client):
    """With no active class in context, there is no scope to act on — 404, never a
    fallback to some class the teacher happens to own."""
    from werkzeug.exceptions import NotFound

    active = initialize("chemistry_p1", client.application)
    initialize("ap_csp_p3", client.application)
    enable_class_feature(class_id=active.class_id, feature="store")

    ctx = _ctx(active, active_class_id=None)
    with pytest.raises(NotFound):
        require_admin_feature_scope("store", canonical_context=ctx)
