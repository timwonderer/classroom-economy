"""Regression: the Store admin surface must not mount the rent recommendation panel.

The Store "Add New Item" (and "Edit Item") forms previously mounted the generic
economy-balance ``displayCWIInfo()`` renderer on an ``#cwi-info`` container. That
renderer is rent-specific: it hardcodes the word "rent", a "per month" cadence,
and a rent CWI band (SPEC-ECON-003 §4.6 is a *rent* surface). Rendering it on the
Store form produced a nonsensical rent pricing recommendation on a store item.

Store pricing guidance is expressed exclusively through the tier recommendation
(``#tier-recommendation``, SPEC-ECON-003 §4.8 store tiers). There is no canonical
Store CWI band -- ``get_price_recommendation_context`` builds only the rent band --
so the fix is to REMOVE the rent panel from the composition source, not invent a
Store recommendation.

This test asserts:
  * the Store surface does not mount the ``#cwi-info`` rent panel container, and
  * the store item form script does not invoke ``displayCWIInfo`` (composition source),
  * while the legitimate ``#tier-recommendation`` store guidance is preserved.
"""

from __future__ import annotations

from pathlib import Path

from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__store_surface_does_not_mount_rent_cwi_panel(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")

    response = client.get("/admin/store")
    assert response.status_code == 200
    body = response.data

    # The rent recommendation container must NOT be mounted on the Store form.
    assert b'id="cwi-info"' not in body
    # The legitimate store-tier guidance container IS preserved.
    assert b'id="tier-recommendation"' in body


def test_DOM_CLASS_001__store_item_form_script_does_not_invoke_rent_renderer():
    """Composition-source guard: the store item form script must not call the
    rent-specific ``displayCWIInfo()`` renderer. Removing the mount only from the
    template would let the defect return via any future container named #cwi-info."""
    repo_root = Path(__file__).resolve().parents[3]
    script = (repo_root / "static" / "js" / "item-form-economy.js").read_text()

    assert "displayCWIInfo" not in script, (
        "item-form-economy.js must not invoke the rent-specific displayCWIInfo() "
        "renderer on the Store surface"
    )
    # The store-tier recommendation wiring must remain.
    assert "tier-recommendation" in script


def test_DOM_CLASS_001__store_edit_surface_does_not_mount_rent_cwi_panel(client):
    """The Edit Item surface shares the same form partial and must also be clean."""
    repo_root = Path(__file__).resolve().parents[3]
    edit_template = (repo_root / "templates" / "admin_edit_item.html").read_text()

    assert 'id="cwi-info"' not in edit_template
    assert 'id="tier-recommendation"' in edit_template
