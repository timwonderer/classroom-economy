"""Slice 8.4a — ITR-owned read/presentation models over interpretation_cycle_record.

Proves:
* every curated guiding question satisfies the non-prescriptive contract, and the
  validator rejects prescriptive/evaluative phrasing;
* each stored value-kind renders to a plain, teacher-readable presentation value;
* the read service consumes the FROZEN stored record and never recomputes;
* not_applicable is humanized (no value); the checking-only qualifier surfaces;
* cycle history is class-scoped and ordered.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import InterpretationCycleRecord
from app.services.interpretation.presentation import (
    _CANDIDATES,
    _SECTIONS,
    validate_guiding_question,
)
from app.services.interpretation.read_service import (
    get_cycle_view,
    get_latest_cycle_view,
    list_cycle_summaries,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize

_REF_CONFIG = {"schema_version": 1, "economic_engine": {}, "policy": {}}


def _entry(candidate_id, value=None, *, applicability="computed", reason=None, qualifiers=None):
    return {
        "candidate_id": candidate_id, "applicability": applicability,
        "not_applicable_reason": reason, "qualifiers": qualifiers, "value": value,
    }


def _put_record(cid, cycle_id, observations, *, completed_at=None):
    now = utc_now()
    with FEATContext("FEAT-PROD-004", idempotency_key=f"rec:{cycle_id}"):
        record = InterpretationCycleRecord(
            class_id=cid, payroll_cycle_id=cycle_id,
            cycle_started_at=now - timedelta(hours=1),
            cycle_completed_at=completed_at or now, computed_at=now,
            reference_configuration=_REF_CONFIG,
            observations_json={"schema_version": 1, "observations": observations},
        )
        db.session.add(record)
        db.session.flush()
    return record


# --------------------------------------------------------------------------- #
# Guiding-question contract                                                   #
# --------------------------------------------------------------------------- #


def test_all_curated_guiding_questions_are_non_prescriptive():
    for *_prefix, questions in _SECTIONS:
        for q in questions:
            validate_guiding_question(q)  # must not raise
    for meta in _CANDIDATES.values():
        for q in meta.guiding_questions:
            validate_guiding_question(q)


@pytest.mark.parametrize("bad", [
    "You should increase wages?",
    "Is participation too low?",
    "How can you improve savings?",
    "This looks concerning, agreed?",
    "What might explain this pattern.",  # not a question
])
def test_validator_rejects_prescriptive_or_non_questions(bad):
    with pytest.raises(ValueError):
        validate_guiding_question(bad)


# --------------------------------------------------------------------------- #
# Value formatting + frozen-record read                                       #
# --------------------------------------------------------------------------- #


def _representative_observations():
    return [
        _entry("Q1a-C1", {"kind": "fraction", "numerator": 99, "denominator": 100, "value": "0.9900"}),
        _entry("Q1a-C2", {"kind": "distribution", "count": 4, "p10": "0.00", "p25": "1.00",
                          "p50": "2.00", "p75": "3.00", "p90": "4.00", "iqr": "2.00", "mean": "2.00"}),
        _entry("Q2-C1", {"kind": "rate", "numerator": 3, "denominator": 4,
                         "unit": "transactions_per_active_seat_per_day", "value": "0.7500"}),
        _entry("Q2-C2", {"kind": "amount", "value": "10.00", "unit": "tokens"}),
        _entry("Q3-C1", {"kind": "category_fractions_by_type", "obligation_types": {
            "RENT": {"kind": "category_fractions", "categories": [
                {"category": "1_satisfied_payment_only", "numerator": 2, "denominator": 5, "value": "0.4000"}]}}}),
        _entry("Q3-C2", {"kind": "coverage_by_type", "obligation_types": {
            "RENT": {"assessed_cents": 5000, "student_paid_cents": 1400,
                     "waived_cents": 1600, "unmet_cents": 2000}}}),
        _entry("Q3-C3", {"kind": "counts", "items": [{"label": "RENT:payment", "count": 3}], "total": 3}),
        _entry("Q4-C1", applicability="not_applicable", reason={"feature": "savings", "state": "disabled"}),
        _entry("Q5-C1", {"kind": "category_fractions", "categories": [
            {"category": "1_labor", "numerator": 2000, "denominator": 3500, "value": "0.5714"}]}),
        _entry("Q6-C3", {"kind": "distribution", "count": 4, "p10": "0.00", "p25": "0.00",
                         "p50": "35.00", "p75": "70.00", "p90": "130.00", "iqr": "70.00",
                         "n_at_or_below_zero": 2},
               qualifiers={"basis_note": {"code": "checking_only_savings_disabled",
                                          "excluded_component": "savings"}}),
        _entry("Q9-C1", {"kind": "signal_set", "signals": [
            {"signal_id": "labor_participation", "applicability": "computed",
             "value": {"kind": "distribution", "count": 4, "p10": "0", "p25": "0", "p50": "1",
                       "p75": "1", "p90": "1", "iqr": "1"}},
            {"signal_id": "persistence", "applicability": "not_applicable", "value": None}]}),
    ]


def test_frozen_record_renders_stored_values_without_recompute(app):
    classroom = initialize("chemistry_p1", app)  # a 4-student class
    cid = classroom.class_id
    _put_record(cid, "cycle-fmt", _representative_observations())

    view = get_cycle_view(cid, "cycle-fmt")
    assert view is not None
    obs = {o.candidate_id: o for section in view.sections for o in section.observations}

    # Q1a-C1 says 99 of 100 — impossible for a 4-student class, so this can only
    # come from the stored record, proving no recompute.
    assert obs["Q1a-C1"].value.display == "99 of 100 students (99.00%)"
    # Distribution reads in plain language, not percentile jargon.
    assert obs["Q1a-C2"].value.display == "About 2 attendance records per student on average"
    # Rate leads with the graspable count and gives the per-day figure as context.
    assert obs["Q2-C1"].value.display == "3 student-started transactions this cycle"
    assert obs["Q2-C2"].value.display == "$10.00"
    # Income sources use friendly labels + money framing.
    assert "attendance-based work: 57.14% ($20.00 of $35.00 received)" in obs["Q5-C1"].value.supporting
    assert obs["Q3-C3"].value.display == "3 obligation events recorded"
    assert any("$50.00 owed" in line for line in obs["Q3-C2"].value.supporting)
    assert obs["Q3-C1"].value.display == "For each obligation, how it was resolved:"

    # Q4-C1 not_applicable: no value, humanized reason.
    assert obs["Q4-C1"].applicability == "not_applicable"
    assert obs["Q4-C1"].value is None
    assert obs["Q4-C1"].not_applicable_reason == "Savings is disabled for this class this cycle."

    # Q6-C3 checking-only qualifier surfaces as supporting context.
    assert "Reported on a checking-only basis (savings excluded)." in obs["Q6-C3"].supporting_context

    # Q9-C1 signal_set: each independent signal is named and explained on its own line.
    assert obs["Q9-C1"].value.display == "2 independent signals, each shown separately:"
    assert any("Persistence across cycles: not available yet" in line
               for line in obs["Q9-C1"].value.supporting)
    assert any(line.startswith("Attendance per student:") for line in obs["Q9-C1"].value.supporting)


def test_sections_group_candidates_thematically(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    _put_record(cid, "cycle-sec", _representative_observations())

    view = get_cycle_view(cid, "cycle-sec")
    section_keys = [s.key for s in view.sections]
    # Only sections with present observations appear, in the fixed order.
    assert section_keys == ["participation", "activity", "obligations",
                            "savings", "income", "resources", "resilience"]
    for section in view.sections:
        assert section.guiding_questions  # each section carries guiding questions


# --------------------------------------------------------------------------- #
# History read: class-scoped and ordered                                      #
# --------------------------------------------------------------------------- #


def test_presents_a_real_materialized_cycle_record(app):
    """End-to-end: a cycle materialized by the payroll pipeline presents cleanly."""
    from app.feats.complete_payroll_cycle import complete_payroll_cycle
    from app.models import AttendanceSession, PolicyVersion
    from app.services.context_resolver import CanonicalContext

    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    now = utc_now()
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"pol:{cid}"):
        db.session.add(PolicyVersion(class_id=cid, domain="payroll", version_number=1,
                                     policy_payload_json="{}", activated_at=now, is_active=True))
        db.session.flush()
    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        student = classroom.students[0]
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid, target_user_id=student.user.id,
            actor_seat_id=classroom.teacher_seat_id, reason_code="start_work",
            timestamp=now - timedelta(minutes=30)))
        db.session.flush()

    ctx = CanonicalContext(user_id=classroom.teacher_user_id, class_id=cid,
                           seat_id=classroom.teacher_seat_id, actor_role="teacher")
    key = "run:present"
    with FEATContext("FEAT-PROD-004", idempotency_key=key):
        complete_payroll_cycle(ctx=ctx, idempotency_key=key,
                               cycle_started_at=now - timedelta(hours=1), cycle_completed_at=now)

    view = get_latest_cycle_view(cid)
    assert view is not None
    assert {s.key for s in view.sections} == {
        "participation", "activity", "obligations", "savings", "income", "resources", "resilience"}
    total = sum(len(s.observations) for s in view.sections)
    assert total == 17  # all candidates present in the frozen record


def test_cycle_history_is_class_scoped_and_ordered(app):
    class_a = initialize("chemistry_p1", app).class_id
    class_b = initialize("chemistry_p1", app).class_id
    now = utc_now()
    _put_record(class_a, "a-old", [], completed_at=now - timedelta(days=2))
    _put_record(class_a, "a-new", [], completed_at=now)
    _put_record(class_b, "b-1", [], completed_at=now)

    summaries_a = list_cycle_summaries(class_a)
    assert [s.payroll_cycle_id for s in summaries_a] == ["a-new", "a-old"]  # newest first
    assert [s.payroll_cycle_id for s in list_cycle_summaries(class_b)] == ["b-1"]

    assert get_latest_cycle_view(class_a).cycle.payroll_cycle_id == "a-new"
    assert get_cycle_view(class_a, "does-not-exist") is None
