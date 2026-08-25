"""Same-teacher/two-class isolation regression test for class-scope destruction.

Guards ``_hard_delete_class_scope``: destroying one class must tear down ONLY
that class's records. A sibling class owned by the same teacher must survive
intact. This specifically pins the store-catalog cleanup, which was previously
gated on the teacher's block/section labels (display-only metadata) — a bug that
could leak a sectionless class's store items past destruction, and (had the
label matched two classes) risked reaching across classes.

``chemistry_p1`` and ``ap_csp_p3`` are both owned by ``teacher_alice``.
"""

from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, StoreItem
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize


def _add_store_item(class_id: str, user_id: int, name: str) -> int:
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"store-item:{class_id}:{name}",
    ):
        item = StoreItem(
            user_id=user_id,
            class_id=class_id,
            name=name,
            price=Decimal("5.00"),
            item_type="immediate",
            is_active=True,
        )
        db.session.add(item)
        db.session.flush()
        item_id = item.id
    return item_id


def test_DOM_CLASS_001__hard_delete_class_scope_spares_sibling_class(client):
    """Destroying class A leaves class B (same teacher) fully intact."""
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("ap_csp_p3", client.application)
    assert class_a.teacher_user.id == class_b.teacher_user.id
    assert class_a.class_id != class_b.class_id

    teacher_id = class_a.teacher_user.id
    item_a = _add_store_item(class_a.class_id, teacher_id, "Widget A")
    item_b = _add_store_item(class_b.class_id, teacher_id, "Widget B")

    ctx = CanonicalContext(
        user_id=teacher_id,
        class_id=class_a.class_id,
        seat_id=class_a.teacher_seat.id,
        actor_role="teacher",
    )

    # _hard_delete_class_scope is decorated with @requires_feat_context, so it
    # opens its own FEAT-CLASS-001 context; call it directly (no outer wrapper).
    from app.feats.base import generate_correlation_id
    from app.routes.admin import _hard_delete_class_scope

    _hard_delete_class_scope(
        class_id=class_a.class_id,
        canonical_context=ctx,
        correlation_id=generate_correlation_id(),
        idempotency_key=f"class:destroy:{class_a.class_id}",
    )

    db.session.expire_all()

    # Class A is destroyed.
    assert db.session.get(ClassEconomy, class_a.class_id) is None
    assert db.session.get(StoreItem, item_a) is None
    assert Seat.query.filter_by(class_id=class_a.class_id).count() == 0

    # Class B is fully intact — no cross-class fan-out.
    assert db.session.get(ClassEconomy, class_b.class_id) is not None
    assert db.session.get(StoreItem, item_b) is not None
    assert Seat.query.filter_by(class_id=class_b.class_id).count() > 0
