"""Schema tests for the ``interpretation_cycle_record`` table (DOM-ITR-001 §IX).

Covers the durable, immutable per-cycle materialization record. These exercise
the DB integrity backstops directly — they do NOT test FEAT-PROD-004 / FEAT-ITR-001
materialization wiring (later build slices §8.2 / §8.4).

Verified:
* a valid row persists and the JSONB projections round-trip as structured data;
* the ``(class_id, payroll_cycle_id)`` uniqueness guard rejects a second record
  for the same cycle (one record per completed cycle, §IX Immutability);
* NOT NULL is enforced on ``reference_configuration``.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import InterpretationCycleRecord
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _base(class_id, **overrides):
    started = utc_now()
    common = dict(
        class_id=class_id,
        payroll_cycle_id=str(uuid4()),
        cycle_started_at=started,
        cycle_completed_at=started,
        computed_at=started,
        reference_configuration={
            "schema_version": 1,
            "economic_engine": {"cwi": "1.00", "expected_weekly_hours": "5", "hourly_pay_rate": "12.00"},
            "policy": {"policy_uuid": str(uuid4()), "version": "1"},
        },
        observations_json={"descriptive": [], "interpretive": []},
    )
    common.update(overrides)
    return common


def _insert(class_id, **overrides):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"itr:{uuid4().hex}"):
        row = InterpretationCycleRecord(**_base(class_id, **overrides))
        db.session.add(row)
        db.session.flush()
    return row


def test_valid_row_persists_and_jsonb_round_trips(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _insert(classroom.class_id)
        fetched = db.session.get(InterpretationCycleRecord, row.id)
        assert fetched is not None
        assert fetched.class_id == classroom.class_id
        assert fetched.reference_configuration["schema_version"] == 1
        assert fetched.reference_configuration["economic_engine"]["cwi"] == "1.00"
        assert fetched.observations_json == {"descriptive": [], "interpretive": []}


def test_duplicate_cycle_rejected(app):
    """One record per (class_id, payroll_cycle_id) — the second insert is rejected."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cycle_id = str(uuid4())
        _insert(classroom.class_id, payroll_cycle_id=cycle_id)
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, payroll_cycle_id=cycle_id)
        db.session.rollback()


def test_reference_configuration_not_null(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, reference_configuration=None)
        db.session.rollback()
