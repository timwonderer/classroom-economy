"""Slice 8.2b-5 — Q9-C1 resilience observation set + contract completeness.

Q9-C1 is a *composition* of already-certified observations (SPEC-ITR-001 §13),
so the tests prove two things above all:

1. **Reuse, not recomputation.** Q9's nested signals are byte-identical to the
   primitives their owning candidates already certified — its ``resource_checking``
   distribution equals Q6-C1's value, and its ``obligation_outcomes`` counts equal
   the Q3 outcome tally. There is exactly one definition of each fact in the domain.

2. **Contract completeness.** With Q9 present the compute core reaches 17/17:
   ``coverage.complete`` is ``True`` and ``validate_for_materialization`` accepts
   the payload. This is the point the core becomes materializable — the writer
   itself remains the separate 8.2c boundary.

Also guarded: the dignity constraint (no seat ids in the serialized output), the
persistence signal as *presence* (currently ``not_applicable`` — no prior cycle
records — never a trend), and per-signal ``not_applicable`` when savings is off.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    LedgerMechanism,
    ObligationAssessment,
    Transaction,
    TransactionStatus,
)
from app.services.interpretation.compute import compute_partial_payload
from app.services.interpretation.obligation_observation import compute_q3
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_V1,
    validate_for_materialization,
    validate_payload_structure,
)
from app.services.interpretation.resilience_observation import compute_q9
from app.services.interpretation.resource_distribution import compute_q6
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.class_domain import disable_class_feature
from tests.helpers.classroom_initializer import initialize


def _signals(entry):
    return {s["signal_id"]: s for s in entry["value"]["signals"]}


def _post(cid, seat, account_type, amount, ts, mechanism=LedgerMechanism.SELF):
    db.session.add(Transaction(
        seat_id=seat.seat_id, target_seat_id=seat.seat_id, actor_seat_id=seat.seat_id,
        class_id=cid, amount=Decimal(amount), account_type=account_type,
        mechanism=mechanism, status=TransactionStatus.POSTED, type="test", timestamp=ts,
    ))


def _seed_q9(classroom):
    """A window exercising every Q9 signal group (savings enabled by default)."""
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    in_window = now - timedelta(minutes=30)

    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"q9:{cid}"):
        # Labor participation: sA and sB attend.
        for seat in (sA, sB):
            db.session.add(AttendanceSession(
                target_seat_id=seat.seat_id, class_id=cid, target_user_id=seat.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work", timestamp=in_window,
            ))
        # Resource balances.
        _post(cid, sA, "checking", "100.00", in_window)
        _post(cid, sB, "checking", "-20.00", in_window)
        _post(cid, sA, "savings", "30.00", in_window)
        # Teacher-support: a teacher-mechanism inbound inflow to sC.
        _post(cid, sC, "checking", "50.00", in_window, LedgerMechanism.TEACHER)
        # Obligations: one unsatisfied, one waived (drives obligation_outcomes and
        # the teacher-support waived count).
        db.session.add(ObligationAssessment(
            correlation_id="q9-rent-unsat", seat_id=sA.seat_id, class_id=cid,
            obligation_type="RENT", event_type="ASSESSMENT",
            internal_ref="itr:q9-rent-unsat", timestamp=now,
        ))
        db.session.add(ObligationAssessment(
            correlation_id="q9-rent-waived", seat_id=sB.seat_id, class_id=cid,
            obligation_type="RENT", event_type="ASSESSMENT",
            internal_ref="itr:q9-rent-waived", timestamp=now,
        ))
        db.session.add(ObligationAssessment(
            correlation_id="q9-rent-waived", seat_id=sB.seat_id, class_id=cid,
            obligation_type="RENT", event_type="WAIVED",
            internal_ref="itr:q9-rent-waived", timestamp=now,
        ))
        db.session.flush()

    return cid, window_start, window_end


# --------------------------------------------------------------------------- #
# 1. Structure + dignity                                                      #
# --------------------------------------------------------------------------- #


def test_q9_is_a_signal_set_of_independent_groups(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    entry = compute_q9(cid, start, end)[0]
    assert entry["candidate_id"] == "Q9-C1"
    assert entry["value"]["kind"] == "signal_set"

    signal_ids = [s["signal_id"] for s in entry["value"]["signals"]]
    assert signal_ids == sorted(signal_ids)          # §15.9
    assert set(signal_ids) == {
        "labor_participation", "obligation_outcomes", "persistence",
        "resource_checking", "resource_savings", "resource_total", "teacher_support",
    }


def test_q9_serialized_output_exposes_no_seat_identifiers(app):
    """Dignity (INV-ITR-009): the value is class-level distributional evidence."""
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)
    sA = classroom.students[0]

    import json
    blob = json.dumps(compute_q9(cid, start, end)[0]["value"])
    assert f'"{sA.seat_id}"' not in blob
    assert "seat_id" not in blob


def test_persistence_signal_is_not_applicable_presence_not_trend(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    persistence = _signals(compute_q9(cid, start, end)[0])["persistence"]
    assert persistence["applicability"] == "not_applicable"
    assert persistence["value"] is None
    assert persistence["not_applicable_reason"] == {
        "input": "prior_completed_cycle_records", "state": "unavailable",
    }


# --------------------------------------------------------------------------- #
# 2. Reuse: Q9 composes the same certified primitives                          #
# --------------------------------------------------------------------------- #


def test_q9_resource_checking_equals_q6_c1_value(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    q9_checking = _signals(compute_q9(cid, start, end)[0])["resource_checking"]["value"]
    q6_c1 = {e["candidate_id"]: e for e in compute_q6(cid, start, end)}["Q6-C1"]["value"]
    # Identical value proves Q9 reuses the Q6 resource primitive, not a second
    # independent read with slightly different rules.
    assert q9_checking == q6_c1


def test_q9_obligation_outcomes_match_the_q3_outcome_tally(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    q9_counts = {
        it["label"]: it["count"]
        for it in _signals(compute_q9(cid, start, end)[0])["obligation_outcomes"]["value"]["items"]
    }
    # Reconstruct the pooled outcome tally from Q3-C1's per-type fractions: both
    # candidates read the same interpret_obligations primitive.
    q3_c1 = {e["candidate_id"]: e for e in compute_q3(cid, start, end)}["Q3-C1"]["value"]
    pooled: dict[str, int] = {}
    for by_type in q3_c1["obligation_types"].values():
        for cat in by_type["categories"]:
            pooled[cat["category"]] = pooled.get(cat["category"], 0) + cat["numerator"]
    # One unsatisfied + one waived obligation.
    assert q9_counts["4_unsatisfied"] == 1
    assert q9_counts["2_satisfied_waived"] == 1
    assert q9_counts == pooled


def test_q9_teacher_support_counts_waivers_and_teacher_inflows(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    counts = {
        it["label"]: it["count"]
        for it in _signals(compute_q9(cid, start, end)[0])["teacher_support"]["value"]["items"]
    }
    assert counts["waived_events"] == 1        # the one WAIVED event
    assert counts["teacher_inflows"] == 1      # sC's teacher-mechanism inflow


# --------------------------------------------------------------------------- #
# 3. Savings disabled: per-signal not_applicable                              #
# --------------------------------------------------------------------------- #


def test_q9_resource_signals_not_applicable_when_savings_disabled(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)
    disable_class_feature(class_id=cid, feature="banking")

    signals = _signals(compute_q9(cid, start, end)[0])
    # Checking is always observable; savings and total are per-signal N/A.
    assert signals["resource_checking"]["applicability"] == "computed"
    for sid in ("resource_savings", "resource_total"):
        assert signals[sid]["applicability"] == "not_applicable"
        assert signals[sid]["value"] is None
        assert signals[sid]["not_applicable_reason"] == {"feature": "savings", "state": "disabled"}


# --------------------------------------------------------------------------- #
# 4. Contract completeness — the compute core becomes materializable           #
# --------------------------------------------------------------------------- #


def test_full_payload_is_complete_and_materializable(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q9(classroom)

    payload = compute_partial_payload(cid, start, end)

    # 17 / 17 → coverage.complete = true → validate_for_materialization = PASS.
    assert payload["coverage"]["complete"] is True

    result = validate_payload_structure(payload)
    assert result.complete is True
    assert result.present_ids == REQUIRED_SET_V1
    assert len(result.present_ids) == 17
    assert result.missing_ids == frozenset()
    assert result.extra_ids == frozenset()
    assert result.duplicate_ids == frozenset()
    assert result.errors == ()

    # The fail-closed materialization gate now accepts the complete payload.
    materialized = validate_for_materialization(payload)
    assert materialized.complete is True
