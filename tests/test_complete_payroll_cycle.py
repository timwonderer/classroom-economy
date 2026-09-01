"""Slice 8.3d — FEAT-PROD-004 Complete Payroll Cycle orchestration.

Individual business behavior is certified underneath (8.2b/8.2c/8.3b/8.3c/substrate),
so this suite is mostly about transactional atomicity and the replay seam:

* normal run → PROD events + one ITR record + CLASS activation + one completion
  anchor, all sharing the cycle identity;
* replay after commit → same payroll_cycle_id AND zero downstream work (spied);
* failure at every step → nothing persists, the completion anchor never survives;
* commit failure → no completed-run state subsequently resolves;
* no pending CLASS transition → success, activation is a lawful no-op.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
import app.feats.complete_payroll_cycle as orch
from app.feats.complete_payroll_cycle import complete_payroll_cycle
from app.models import (
    AttendanceSession,
    InterpretationCycleRecord,
    PayrollEvent,
    PolicyTransition,
    PolicyVersion,
)
from app.services.context_resolver import CanonicalContext
from app.services.payroll.cycle_completion import resolve_completed_run
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize

_DOWNSTREAM = [
    "allocate_payroll_cycle_id",
    "settle_class_payroll_cycle",
    "compute_partial_payload",
    "materialize_interpretation_cycle",
    "apply_next_boundary_transition",
    "record_run_completion",
]


def _raiser(msg):
    def _fn(*args, **kwargs):
        raise RuntimeError(msg)
    return _fn


def _ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user_id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id, actor_role="teacher",
    )


def _seed_run(classroom, *, pending=True):
    """Seed an active payroll policy (v1), attendance, and optionally a pending
    next_payroll transition (target v2). Returns (cid, start, end, v1_id, v2_id)."""
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    start, end = now - timedelta(hours=1), now + timedelta(hours=1)
    v2_id = None

    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{cid}"):
        v1 = PolicyVersion(class_id=cid, domain="payroll", version_number=1,
                           policy_payload_json="{}", activated_at=now, is_active=True)
        db.session.add(v1)
        db.session.flush()
        v1_id = v1.id
        if pending:
            v2 = PolicyVersion(class_id=cid, domain="payroll", version_number=2,
                               policy_payload_json="{}", activated_at=None, is_active=False)
            db.session.add(v2)
            db.session.flush()
            v2_id = v2.id
            db.session.add(PolicyTransition(
                class_id=cid, domain="payroll", source_policy_version_id=v1.id,
                target_policy_version_id=v2.id, activation_mode="next_payroll",
                status="pending", created_at=now,
            ))
            db.session.flush()

    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        for seat in (sA, sB):
            db.session.add(AttendanceSession(
                target_seat_id=seat.seat_id, class_id=cid, target_user_id=seat.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work",
                timestamp=now - timedelta(minutes=30),
            ))
        db.session.flush()

    return cid, start, end, v1_id, v2_id


def _run(classroom, key, start, end):
    with FEATContext("FEAT-PROD-004", idempotency_key=key):
        return complete_payroll_cycle(
            ctx=_ctx(classroom), idempotency_key=key,
            cycle_started_at=start, cycle_completed_at=end,
        )


def _expect_rollback(classroom, key, start, end):
    with pytest.raises(RuntimeError):
        _run(classroom, key, start, end)


def _assert_nothing_persisted(cid, key):
    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 0
    assert resolve_completed_run(cid, key) is None


# --------------------------------------------------------------------------- #
# Normal run                                                                  #
# --------------------------------------------------------------------------- #


def test_normal_run_completes_the_economic_cycle(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, v1_id, v2_id = _seed_run(classroom)
    key = f"run:{uuid4()}"

    result = _run(classroom, key, start, end)
    cycle = result.payroll_cycle_id

    assert result.created is True
    # PROD: payroll events for the two attended seats, all stamped with the cycle.
    events = PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle, payroll_event_type="payroll"
    ).all()
    assert len(events) == len(result.settled_seat_ids) == 2

    # ITR: exactly one immutable, complete record bound to the cycle.
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle).one()
    assert record.id == result.interpretation_record_id
    assert record.observations_json["coverage"]["complete"] is True

    # CLASS: the pending next-cycle policy activated (P17 -> P18).
    assert result.activation_applied is True
    assert db.session.get(PolicyVersion, v2_id).is_active is True
    assert db.session.get(PolicyVersion, v1_id).is_active is False

    # Completion anchor written last — the run is now resolvable.
    assert result.completion_created is True
    assert resolve_completed_run(cid, key) == cycle


def test_no_pending_transition_still_completes_activation_is_noop(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, v1_id, _ = _seed_run(classroom, pending=False)
    key = f"run:{uuid4()}"

    result = _run(classroom, key, start, end)

    assert result.created is True
    assert result.activation_applied is False           # lawful no-op
    assert db.session.get(PolicyVersion, v1_id).is_active is True
    assert InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=result.payroll_cycle_id
    ).count() == 1
    assert resolve_completed_run(cid, key) == result.payroll_cycle_id


# --------------------------------------------------------------------------- #
# Replay: same id, zero downstream work                                       #
# --------------------------------------------------------------------------- #


def test_replay_returns_same_id_and_does_zero_downstream_work(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, v1_id, v2_id = _seed_run(classroom)
    key = f"run:{uuid4()}"

    first = _run(classroom, key, start, end)

    # Spy on every downstream operation; a replay must call none of them.
    spies = {}
    for name in _DOWNSTREAM:
        spy = MagicMock(name=name)
        monkeypatch.setattr(orch, name, spy)
        spies[name] = spy

    replay = _run(classroom, key, start, end)

    assert replay.payroll_cycle_id == first.payroll_cycle_id
    assert replay.created is False
    for name, spy in spies.items():
        spy.assert_not_called()

    # And no duplicate rows appeared.
    assert PayrollEvent.query.filter_by(class_id=cid, payroll_cycle_id=first.payroll_cycle_id).count() == 2
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1


# --------------------------------------------------------------------------- #
# Failure injection at every step → nothing persists                         #
# --------------------------------------------------------------------------- #


def test_prod_failure_persists_nothing(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "settle_class_payroll_cycle", _raiser("PROD fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_itr_compute_failure_rolls_back_payroll(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    # Real PROD settlement flushes events, then compute fails → must roll back.
    monkeypatch.setattr(orch, "compute_partial_payload", _raiser("ITR compute fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_itr_materialization_failure_rolls_back(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "materialize_interpretation_cycle", _raiser("ITR materialize fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_class_activation_failure_rolls_back_everything(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, v1_id, v2_id = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "apply_next_boundary_transition", _raiser("CLASS fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)
    # Policy lineage untouched: v1 still active, v2 still pending.
    assert db.session.get(PolicyVersion, v1_id).is_active is True
    assert db.session.get(PolicyVersion, v2_id).is_active is False


def test_completion_anchor_failure_rolls_back_everything(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, v1_id, v2_id = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "record_run_completion", _raiser("completion fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)
    # CLASS activation that ran before the completion step is also rolled back.
    assert db.session.get(PolicyVersion, v1_id).is_active is True
    assert db.session.get(PolicyVersion, v2_id).is_active is False


def test_commit_failure_leaves_no_resolvable_completed_run(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"

    # The full pipeline succeeds, then the caller's transaction aborts before
    # commit (simulating a commit-time failure): nothing may survive.
    with pytest.raises(RuntimeError):
        with FEATContext("FEAT-PROD-004", idempotency_key=key):
            complete_payroll_cycle(
                ctx=_ctx(classroom), idempotency_key=key,
                cycle_started_at=start, cycle_completed_at=end,
            )
            raise RuntimeError("commit fails")

    _assert_nothing_persisted(cid, key)
