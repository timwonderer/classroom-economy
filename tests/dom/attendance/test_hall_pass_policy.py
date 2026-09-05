"""Hall-pass policy definitions are immutable and append-only (DOM-POL-001 §VI).

Regression coverage for the ``HallPassSettings`` half of blocker **B2**.

This writer already inserted a new row per save, so the append-only half looked
done. What was missing was supersession: nothing retired the predecessor, so a
class accumulated several rows all claiming to be current and the reader picked
one by sort order.

A second gap sat in ``_get_or_create_hall_pass_settings``, which inserted a
default policy as a side effect of being *asked* which policy applied. That is
not an INV-ARC-007 GET-write — its only live caller was the queue-settings
write command — but it did mint a governing contract nobody submitted, and it
left that conjured row unretired alongside the submission that followed it.
"""

import pytest

from app.extensions import db
from app.feats.attendance import save_hall_pass_setup_config, update_hall_pass_queue_settings
from app.feats.base import FEATContext
from app.models import HallPassSettings
from app.services.class_configuration_query_service import get_hall_pass_settings
from tests.helpers.classroom_initializer import initialize


_PAYLOAD = [{"pass_name": "Break", "max_queue": 2, "consume_pass": False}]


def _save(classroom, *, max_queue_limit, key, payload=None):
    return save_hall_pass_setup_config(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        hall_pass_enabled=True,
        pass_type_payload=payload or _PAYLOAD,
        max_queue_limit=max_queue_limit,
        correlation_id=f"corr_{key}",
        idempotency_key=f"test:hall-pass:{key}",
    )


def _in_use_rows(class_id):
    return HallPassSettings.query.filter_by(
        class_id=class_id, availability_state="IN_USE"
    ).all()


def test_hall_pass_policy_submission_is_append_only(client):
    classroom = initialize("chemistry_p1", client.application)
    first = _save(classroom, max_queue_limit=10, key="append:1")
    second = _save(classroom, max_queue_limit=4, key="append:2")

    assert first.policy_uuid != second.policy_uuid
    assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() >= 3
    assert second.effective_queue_limit == 2


def test_hall_pass_submission_retires_the_predecessor(client):
    """Exactly one row may be current, and it is the one just submitted."""
    classroom = initialize("chemistry_p1", client.application)
    first = _save(classroom, max_queue_limit=10, key="retire:1")
    second = _save(classroom, max_queue_limit=4, key="retire:2")

    db.session.refresh(first)
    assert first.availability_state == "RETIRED"
    assert second.availability_state == "IN_USE"

    in_use = _in_use_rows(classroom.class_id)
    assert len(in_use) == 1
    assert in_use[0].policy_uuid == second.policy_uuid
    assert get_hall_pass_settings(classroom.class_id).policy_uuid == second.policy_uuid


def test_superseded_hall_pass_policy_keeps_its_terms(client):
    """DOM-POL-001 §VII: a retired policy stays readable and unchanged."""
    classroom = initialize("chemistry_p1", client.application)
    first = _save(classroom, max_queue_limit=10, key="keep:1")
    first_uuid = first.policy_uuid

    _save(classroom, max_queue_limit=4, key="keep:2")

    frozen = HallPassSettings.query.filter_by(policy_uuid=first_uuid).first()
    assert frozen is not None
    assert frozen.max_queue_limit == 10


def test_in_place_hall_pass_payload_edit_is_rejected(client):
    """A write path that skipped the command must raise, not silently rewrite."""
    classroom = initialize("chemistry_p1", client.application)
    settings = _save(classroom, max_queue_limit=10, key="illegal:1")

    with pytest.raises(ValueError, match="immutable"):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="hall-pass:illegal"):
            settings.max_queue_limit = 4
            db.session.flush()

    db.session.rollback()


def test_queue_settings_update_executes_as_a_single_feat(client):
    """The queue-limit command must run, not raise ``FEATContextError``.

    ``update_hall_pass_queue_settings`` carried ``@requires_feat_context`` and
    then called ``save_hall_pass_setup_config``, which carries it too. That
    decorator opens a context unconditionally, so a FEAT composed a FEAT and
    every call raised — making the queue-limit API endpoint
    (``app/routes/api.py``) an unconditional 500. Found by this suite, not by
    the endpoint's own coverage, which is why the pin lives here.
    """
    classroom = initialize("chemistry_p1", client.application)

    saved = update_hall_pass_queue_settings(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        max_queue_limit=7,
        correlation_id="corr_queue",
        idempotency_key="test:hall-pass:queue",
    )

    assert saved.max_queue_limit == 7
    in_use = _in_use_rows(classroom.class_id)
    assert len(in_use) == 1
    assert in_use[0].policy_uuid == saved.policy_uuid


def test_reading_hall_pass_settings_never_mints_a_policy(client):
    """Guard, not a regression pin: the query-service reader was already pure.

    It passes against the pre-fix tree too. It is here so that the impure
    ``_get_or_create`` shape cannot quietly return on this side of the boundary.
    """
    classroom = initialize("chemistry_p1", client.application)
    before = HallPassSettings.query.filter_by(class_id=classroom.class_id).count()

    for _ in range(3):
        get_hall_pass_settings(classroom.class_id)

    assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() == before
