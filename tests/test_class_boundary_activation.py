"""Slice 8.3c — CLASS next-boundary policy activation.

Certifies the narrow policy-lineage command that applies a class's authoritative
pending ``next_boundary`` transition exactly once at a lawful payroll boundary.
Acceptance set:

* pending next_boundary applies (target active, prior deactivated, transition
  applied, applied_at recorded);
* no pending transition → lawful no-op;
* already-applied same transition → idempotent no-op (state unchanged);
* multiple authoritative pending transitions → fail closed;
* pending ``manual`` / ``immediate`` → untouched;
* target/source class-scope mismatch → fail closed;
* failure/rollback leaves the existing active version unchanged (no internal commit).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import PolicyTransition, PolicyVersion
from app.services.class_boundary_activation import (
    BoundaryActivationConflict,
    BoundaryActivationError,
    apply_next_boundary_transition,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize

_DOMAIN = "payroll"


def _version(cid, version_number, *, active, domain=_DOMAIN):
    v = PolicyVersion(
        class_id=cid, domain=domain, version_number=version_number,
        policy_payload_json="{}", activated_at=(utc_now() if active else None),
        is_active=active,
    )
    db.session.add(v)
    db.session.flush()
    return v


def _transition(cid, source, target, *, mode="next_payroll", domain=_DOMAIN):
    t = PolicyTransition(
        class_id=cid, domain=domain,
        source_policy_version_id=source.id if source else None,
        target_policy_version_id=target.id,
        activation_mode=mode, status="pending", created_at=utc_now(),
    )
    db.session.add(t)
    db.session.flush()
    return t


def _seed_pending(cid, *, mode="next_payroll"):
    """Seed an active source (v1) + pending target (v2) + a transition."""
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{cid}"):
        source = _version(cid, 1, active=True)
        target = _version(cid, 2, active=False)
        transition = _transition(cid, source, target, mode=mode)
        return transition.id, source.id, target.id


def _apply(cid, boundary_at):
    with FEATContext("FEAT-CLASS-005", idempotency_key=f"boundary:{cid}"):
        return apply_next_boundary_transition(class_id=cid, boundary_at=boundary_at)


def test_pending_next_boundary_applies(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    tid, source_id, target_id = _seed_pending(cid)
    boundary = utc_now()

    result = _apply(cid, boundary)

    assert result.applied is True
    assert result.transition.id == tid
    assert db.session.get(PolicyVersion, target_id).is_active is True
    assert db.session.get(PolicyVersion, source_id).is_active is False
    transition = db.session.get(PolicyTransition, tid)
    assert transition.status == "applied"
    assert transition.applied_at is not None
    assert db.session.get(PolicyVersion, target_id).activated_at is not None


def test_no_pending_transition_is_noop(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{cid}"):
        _version(cid, 1, active=True)  # active version, but no transition

    result = _apply(cid, utc_now())
    assert result.applied is False
    assert result.transition is None


def test_already_applied_is_idempotent_noop(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    tid, source_id, target_id = _seed_pending(cid)

    first = _apply(cid, utc_now())
    applied_at = db.session.get(PolicyTransition, tid).applied_at
    second = _apply(cid, utc_now() + timedelta(minutes=5))

    assert first.applied is True
    assert second.applied is False           # nothing pending remains
    # State unchanged by the replay — same applied_at, same active version.
    assert db.session.get(PolicyTransition, tid).applied_at == applied_at
    assert db.session.get(PolicyVersion, target_id).is_active is True
    assert db.session.get(PolicyVersion, source_id).is_active is False


def test_multiple_authoritative_pending_fails_closed(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{cid}"):
        source = _version(cid, 1, active=True)
        t1 = _transition(cid, source, _version(cid, 2, active=False))
        t2 = _transition(cid, source, _version(cid, 3, active=False))

    with pytest.raises(BoundaryActivationConflict):
        _apply(cid, utc_now())

    # Neither applied; both still pending; the active version is unchanged.
    assert db.session.get(PolicyTransition, t1.id).status == "pending"
    assert db.session.get(PolicyTransition, t2.id).status == "pending"
    assert db.session.get(PolicyVersion, source.id).is_active is True


@pytest.mark.parametrize("mode", ["manual", "immediate", "next_renewal"])
def test_non_boundary_modes_are_untouched(app, mode):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    tid, source_id, target_id = _seed_pending(cid, mode=mode)

    result = _apply(cid, utc_now())

    assert result.applied is False           # not authoritative at a payroll boundary
    assert db.session.get(PolicyTransition, tid).status == "pending"   # untouched
    assert db.session.get(PolicyVersion, target_id).is_active is False
    assert db.session.get(PolicyVersion, source_id).is_active is True


def test_target_scope_mismatch_fails_closed(app):
    class_a = initialize("chemistry_p1", app).class_id
    class_b = initialize("chemistry_p1", app).class_id
    assert class_a != class_b

    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{class_a}"):
        source_a = _version(class_a, 1, active=True)
        # Corruption: transition in class A points at a class B target version.
        target_b = _version(class_b, 1, active=False)
        bad = _transition(class_a, source_a, target_b)

    with pytest.raises(BoundaryActivationError):
        _apply(class_a, utc_now())

    # Nothing changed.
    assert db.session.get(PolicyTransition, bad.id).status == "pending"
    assert db.session.get(PolicyVersion, source_a.id).is_active is True
    assert db.session.get(PolicyVersion, target_b.id).is_active is False


def test_rollback_leaves_active_version_unchanged_no_commit(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    tid, source_id, target_id = _seed_pending(cid)

    # Apply then raise inside the same FEAT transaction: the command does not
    # commit, so the whole activation must roll back.
    with pytest.raises(RuntimeError):
        with FEATContext("FEAT-CLASS-005", idempotency_key=f"boundary:{cid}"):
            apply_next_boundary_transition(class_id=cid, boundary_at=utc_now())
            raise RuntimeError("caller aborts after activation")

    assert db.session.get(PolicyVersion, source_id).is_active is True   # prior active restored
    assert db.session.get(PolicyVersion, target_id).is_active is False  # target not activated
    assert db.session.get(PolicyTransition, tid).status == "pending"    # transition not applied
