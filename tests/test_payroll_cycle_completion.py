"""Slice 8.3 substrate — payroll-cycle completion replay-identity API.

Certifies the persistent anchor that makes the payroll cycle boundary replay-safe,
independently of any orchestrator (FEAT-PROD-004 is not built yet). The property
that matters: after a run's completion is recorded, the run can be *resolved* back
to its **original** ``payroll_cycle_id`` — so a replay recovers that id rather than
allocating a new one or recapturing advanced configuration.

Covered:
* an unknown run resolves to ``None``;
* recording a completion makes it resolvable by ``(class_id, idempotency_key)``;
* ``allocate_payroll_cycle_id`` yields fresh distinct ids;
* re-recording the same run/content is idempotent (no second row);
* re-recording the same run with a different cycle id fails closed — no update;
* completions are scoped by ``(class_id, idempotency_key)`` — the same key in two
  classes is two independent runs;
* the DB uniqueness guard rejects a duplicate ``(class_id, idempotency_key)``;
* the full resolve → record → resolve replay handshake returns the same id.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollCycleCompletion
from app.services.payroll.cycle_completion import (
    PayrollCycleCompletionConflict,
    allocate_payroll_cycle_id,
    record_run_completion,
    resolve_completed_run,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _record(cid, key, cycle_id):
    with FEATContext("FEAT-PROD-004", idempotency_key=key):
        return record_run_completion(cid, key, cycle_id)


def test_unknown_run_resolves_to_none(app):
    classroom = initialize("chemistry_p1", app)
    assert resolve_completed_run(classroom.class_id, "cycle:run:never") is None


def test_allocate_yields_fresh_distinct_ids(app):
    initialize("chemistry_p1", app)
    a, b = allocate_payroll_cycle_id(), allocate_payroll_cycle_id()
    assert a != b
    assert len(a) == 36  # uuid4


def test_recorded_run_is_resolvable(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    key = "cycle:run:1"
    cycle_id = allocate_payroll_cycle_id()

    result = _record(cid, key, cycle_id)
    assert result.created is True
    assert result.payroll_cycle_id == cycle_id
    assert resolve_completed_run(cid, key) == cycle_id


def test_replay_handshake_returns_original_cycle_id(app):
    """The seam: resolve-before is None; after recording, resolve-after returns the
    same id — a replay recovers it instead of allocating a new one."""
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    key = "cycle:run:handshake"

    assert resolve_completed_run(cid, key) is None       # first execution path
    original = allocate_payroll_cycle_id()
    _record(cid, key, original)

    # Replay: the guard resolves the completed run before any domain work.
    resolved = resolve_completed_run(cid, key)
    assert resolved == original


def test_idempotent_record_same_content_no_second_row(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    key = "cycle:run:idem"
    cycle_id = allocate_payroll_cycle_id()

    first = _record(cid, key, cycle_id)
    second = _record(cid, key, cycle_id)

    assert first.created is True
    assert second.created is False
    assert second.payroll_cycle_id == cycle_id
    assert PayrollCycleCompletion.query.filter_by(class_id=cid, idempotency_key=key).count() == 1


def test_conflict_on_different_cycle_id_fails_closed_no_update(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    key = "cycle:run:conflict"
    original = allocate_payroll_cycle_id()
    _record(cid, key, original)

    with pytest.raises(PayrollCycleCompletionConflict):
        _record(cid, key, allocate_payroll_cycle_id())  # a different cycle id

    row = PayrollCycleCompletion.query.filter_by(class_id=cid, idempotency_key=key).one()
    assert row.payroll_cycle_id == original  # unchanged — no update path
    assert PayrollCycleCompletion.query.filter_by(class_id=cid, idempotency_key=key).count() == 1


def test_completions_scoped_by_class(app):
    class_a = initialize("chemistry_p1", app).class_id
    class_b = initialize("chemistry_p1", app).class_id
    assert class_a != class_b
    key = "cycle:run:shared-key"  # same class-level key string in both classes

    cycle_a = allocate_payroll_cycle_id()
    cycle_b = allocate_payroll_cycle_id()
    _record(class_a, key, cycle_a)
    _record(class_b, key, cycle_b)

    assert resolve_completed_run(class_a, key) == cycle_a
    assert resolve_completed_run(class_b, key) == cycle_b
    assert cycle_a != cycle_b


def test_db_uniqueness_guard_rejects_duplicate_class_key(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    with pytest.raises(IntegrityError):
        with FEATContext("FEAT-PROD-004", idempotency_key="cycle:run:dup"):
            db.session.add_all([
                PayrollCycleCompletion(
                    class_id=cid, idempotency_key="cycle:run:dup",
                    payroll_cycle_id=allocate_payroll_cycle_id(), completed_at=utc_now(),
                ),
                PayrollCycleCompletion(
                    class_id=cid, idempotency_key="cycle:run:dup",
                    payroll_cycle_id=allocate_payroll_cycle_id(), completed_at=utc_now(),
                ),
            ])
            db.session.flush()
