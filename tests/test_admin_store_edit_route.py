"""Regression guard for rendering the admin store item edit form.

``edit_store_item`` lost its ``render_template`` template-name positional
argument in bad800fa, so every GET raised TypeError -> 500. The POST path
redirects on success and never renders, which is why the break went unnoticed.
"""

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import StoreItem
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher

pytestmark = [pytest.mark.regression]


def _make_store_item(classroom, name="Homework Pass"):
    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"admin_store_edit_route:item:{classroom.class_id}:{name}",
    ):
        item = StoreItem(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            name=name,
            description="Skip one homework assignment",
            price=25,
            item_type="immediate",
            is_active=True,
        )
        db.session.add(item)
        db.session.flush()
    return item


def test_admin_store_edit_get_renders_form(client):
    """GET on the store item edit route renders the edit form for its teacher."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    item = _make_store_item(classroom)

    response = client.get(f"/admin/store/edit/{item.id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Homework Pass" in body
    assert f"/admin/store/edit/{item.id}" in body


def test_admin_store_edit_get_rejects_foreign_class_item(client):
    """An item belonging to another class is not editable from the active scope."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    other = initialize_as_teacher("ap_csp_p3", client, client.application)
    foreign_item = _make_store_item(other, name="Foreign Item")

    # Re-establish the first teacher's session; the second initialize logged it out.
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get(f"/admin/store/edit/{foreign_item.id}")

    assert response.status_code == 404
