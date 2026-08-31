"""Slice 8.2b-2 — Q2/Q5 compliant compute vertical.

Two layers of evidence:

1. **DB-free classifier precedence** (``classify_income_origin``): proves the six
   §10.2 origin categories are assigned by a deterministic precedence order so the
   same inflow cannot land in two categories, that labor is corroborated against
   the authoritative PayrollEvent correlation set rather than a payroll-ish
   ``feat_code`` (INV-ITR-016), that structural reversals win first (INV-LED-003),
   and that "other / unclassified" is only ever the final floor (§10.2 category 6,
   §10.4 weak-surface note for interest).

2. **DB-backed compute** over real source-domain facts: Q2 frequency/volume from
   the §6.3 student-originated Ledger surface, and Q5 income composition / labor
   share over a controlled six-category inbound mix (labor corroborated by a real
   ``PayrollEvent``). The full payload still fails materialization **only** because
   10 of the 17 required candidates remain absent (SPEC-ITR-001 §15.8).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollEvent, PolicyVersion
from app.services.interpretation.compute import compute_partial_payload
from app.services.interpretation.economic_activity import compute_q2
from app.services.interpretation.income_composition import compute_q5
from app.services.interpretation.income_origin import (
    CATEGORY_LABOR,
    CATEGORY_INTEREST,
    CATEGORY_TEACHER_ADMIN,
    CATEGORY_SYSTEM_NON_LABOR,
    CATEGORY_REVERSAL,
    CATEGORY_OTHER,
    INCOME_ORIGIN_CATEGORIES,
    aggregate_income_by_category,
    classify_income_origin,
)
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_V1,
    ObservationContractError,
    validate_for_materialization,
    validate_payload_structure,
)
from app.services.ledger_service import InboundLedgerRow, create_pending_transaction
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


IMPLEMENTED_CANDIDATES = frozenset(
    {"Q1a-C1", "Q1a-C2", "Q1b-C1", "Q2-C1", "Q2-C2", "Q5-C1", "Q5-C2"}
)


def _inbound_row(
    *,
    amount_cents=100,
    feat_code=None,
    correlation_id=None,
    original_transaction_id=None,
    mechanism="self",
    account_type="checking",
):
    return InboundLedgerRow(
        transaction_id=1,
        seat_id=1,
        amount_cents=amount_cents,
        feat_code=feat_code,
        correlation_id=correlation_id,
        original_transaction_id=original_transaction_id,
        mechanism=mechanism,
        account_type=account_type,
    )


# --------------------------------------------------------------------------- #
# 1. DB-free classifier precedence (the provenance watchpoints)               #
# --------------------------------------------------------------------------- #


def test_reversal_wins_over_labor_correlation():
    """A row with original_transaction_id is a reversal even if its correlation is
    in the labor set — structural reversal detection wins first (INV-LED-003)."""
    row = _inbound_row(original_transaction_id=42, correlation_id="c-labor")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset({"c-labor"}),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_REVERSAL


def test_labor_is_corroborated_by_payroll_correlation_not_feat_code():
    """Labor is established by the PayrollEvent correlation set, regardless of a
    non-payroll feat_code on the ledger row (INV-ITR-016 source-domain precedence)."""
    row = _inbound_row(
        correlation_id="c-labor", feat_code="FEAT-STOR-001", mechanism="system"
    )
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset({"c-labor"}),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_LABOR


def test_payroll_ish_feat_without_corroboration_is_not_labor():
    """A payroll-looking feat_code with NO corroborating PayrollEvent correlation
    must NOT be classified as labor — it falls to system-originated non-labor.

    This is the core anti-spoofing guarantee: the Ledger row cannot self-declare
    labor provenance; only the authoritative PayrollEvent surface can (§10.2 cat 1)."""
    row = _inbound_row(correlation_id="c-x", feat_code="FEAT-PROD-003", mechanism="system")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),  # not corroborated
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_SYSTEM_NON_LABOR


def test_manual_credit_correlation_is_teacher_admin_not_labor():
    """A manual_credit correlation lands in teacher/admin (cat 3), never labor."""
    row = _inbound_row(correlation_id="c-manual", mechanism="teacher")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),
        manual_credit_correlation_ids=frozenset({"c-manual"}),
    )
    assert category == CATEGORY_TEACHER_ADMIN


def test_teacher_mechanism_admin_feat_is_teacher_admin():
    """A direct teacher-mechanism admin-adjustment FEAT is teacher/admin (cat 3)."""
    row = _inbound_row(feat_code="FEAT-ADMN-001", mechanism="teacher")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_TEACHER_ADMIN


def test_interest_self_savings_falls_to_other_today():
    """§10.4 honest weak-surface outcome: with no canonical interest FEAT, a
    self-mechanism savings interest credit is NOT category-2 interest; it falls to
    other/unclassified rather than being force-fit into interest."""
    row = _inbound_row(mechanism="self", account_type="savings", feat_code="FEAT-LED-000")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_OTHER


def test_system_savings_non_interest_is_system_non_labor():
    """A system-mechanism savings credit whose feat is not the interest FEAT is
    system-originated non-labor (cat 4) — category 2 is dormant (§10.4)."""
    row = _inbound_row(mechanism="system", account_type="savings", feat_code="FEAT-LED-003")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_SYSTEM_NON_LABOR


def test_unmatched_self_inflow_is_other():
    """A plain student self-mechanism inflow with no canonical provenance signal is
    the lawful floor: other/unclassified (cat 6)."""
    row = _inbound_row(mechanism="self", feat_code="FEAT-STOR-001")
    category = classify_income_origin(
        row,
        labor_correlation_ids=frozenset(),
        manual_credit_correlation_ids=frozenset(),
    )
    assert category == CATEGORY_OTHER


def test_aggregate_covers_all_categories_without_double_counting():
    """aggregate_income_by_category emits every category exactly once and sums each
    inflow into exactly one bucket (totals equal the input sum)."""
    rows = [
        _inbound_row(amount_cents=2000, correlation_id="c-labor", mechanism="system"),
        _inbound_row(amount_cents=500, correlation_id="c-manual", mechanism="teacher"),
        _inbound_row(amount_cents=300, original_transaction_id=9, mechanism="system"),
        _inbound_row(amount_cents=200, mechanism="system", feat_code="FEAT-LED-003"),
        _inbound_row(amount_cents=100, mechanism="self", feat_code="FEAT-STOR-001"),
    ]
    totals = aggregate_income_by_category(
        rows,
        labor_correlation_ids=frozenset({"c-labor"}),
        manual_credit_correlation_ids=frozenset({"c-manual"}),
    )
    assert set(totals) == set(INCOME_ORIGIN_CATEGORIES)  # every category present
    assert totals[CATEGORY_LABOR] == 2000
    assert totals[CATEGORY_TEACHER_ADMIN] == 500
    assert totals[CATEGORY_REVERSAL] == 300
    assert totals[CATEGORY_SYSTEM_NON_LABOR] == 200
    assert totals[CATEGORY_OTHER] == 100
    assert totals[CATEGORY_INTEREST] == 0
    assert sum(totals.values()) == 3100  # no inflow lost or double-counted


# --------------------------------------------------------------------------- #
# 2. DB-backed Q2 compute                                                     #
# --------------------------------------------------------------------------- #


def _seed_q2_window(classroom):
    """Seed a 2-day window with student-originated and excluded ledger rows.

    Active student-originated seats: A (2 acts) and B (1 act) → 3 acts / 2 seats.
    Excluded: a system-FEAT payroll row (seat C) and a teacher-mechanism row
    (seat D) — neither is student-originated per §6.3, so both are absent from
    Q2's frequency numerator and monetary volume.
    """
    cid = classroom.class_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    window_start = now - timedelta(days=2)
    window_end = now + timedelta(hours=1)

    def _tx(feat, corr, seat, amount, mechanism="self"):
        with FEATContext(feat, correlation_id=corr, idempotency_key=corr):
            create_pending_transaction(
                seat_id=seat.seat_id, class_id=cid, target_seat_id=seat.seat_id,
                actor_seat_id=seat.seat_id, mechanism=mechanism,
                amount=Decimal(amount), account_type="checking",
                type="act", description="q2",
            )

    # seat A: two student-originated acts (outbound purchase + transfer).
    _tx("FEAT-STOR-001", "q2:A1", sA, "-5.00")
    _tx("FEAT-STOR-001", "q2:A2", sA, "-3.00")
    # seat B: one student-originated act.
    _tx("FEAT-STOR-001", "q2:B1", sB, "-2.00")
    # seat C: system-FEAT payroll row → excluded by §6.3 classifier.
    _tx("FEAT-LED-004", "q2:C1", sC, "10.00")
    # seat D: teacher-mechanism row → excluded (not SELF).
    _tx("FEAT-ADMN-001", "q2:D1", sD, "5.00", mechanism="teacher")

    return cid, window_start, window_end


def test_q2_frequency_and_volume_reflect_student_originated_rows(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q2_window(classroom)

    entries = {e["candidate_id"]: e for e in compute_q2(cid, start, end)}

    # Q2-C1: 3 student-initiated acts / (2 active seats × 2 days) = 0.75.
    q2_c1 = entries["Q2-C1"]["value"]
    assert q2_c1["kind"] == "rate"
    assert q2_c1["numerator"] == 3
    assert q2_c1["denominator"] == 4  # 2 active seats × 2 days
    assert q2_c1["unit"] == "transactions_per_active_seat_per_day"
    assert q2_c1["value"] == "0.7500"

    # Q2-C2: sum of |amounts| of the three student-originated rows = 5+3+2 = 10.00.
    q2_c2 = entries["Q2-C2"]["value"]
    assert q2_c2["kind"] == "amount"
    assert q2_c2["unit"] == "tokens"
    assert q2_c2["value"] == "10.00"
    assert entries["Q2-C2"]["normalization_dependency"] is None


# --------------------------------------------------------------------------- #
# 3. DB-backed Q5 compute (labor corroborated by a real PayrollEvent)         #
# --------------------------------------------------------------------------- #


def _seed_payroll_policy(cid):
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"q5:policy:{cid}"):
        policy = PolicyVersion(
            class_id=cid, domain="payroll", version_number=1,
            policy_payload_json='{"source":"test"}',
            activated_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()
    return policy


def _seed_q5_window(classroom):
    """Seed a six-category inbound mix (cents): labor 2000, teacher/admin 500,
    reversal 300, system-non-labor 200, other 500 (interest 100 + peer 400),
    interest-as-category-2 0. Total inbound = 3500 cents."""
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    policy = _seed_payroll_policy(cid)

    def _tx(feat, corr, seat, amount, mechanism="self", account_type="checking",
            original_transaction_id=None):
        with FEATContext(feat, correlation_id=corr, idempotency_key=corr):
            return create_pending_transaction(
                seat_id=seat.seat_id, class_id=cid, target_seat_id=seat.seat_id,
                actor_seat_id=seat.seat_id, mechanism=mechanism,
                amount=Decimal(amount), account_type=account_type,
                type="act", description="q5",
                original_transaction_id=original_transaction_id,
            )

    # cat 1 — labor: inbound ledger row corroborated by a payroll PayrollEvent.
    # NOTE: FEATContext normalizes correlation ids to the ``corr_`` prefix
    # (app/feats/base.py §Format Discipline), so the Ledger row this block writes
    # carries ``corr_q5:labor``. The PayrollEvent must share that *normalized* id
    # for corroboration to succeed — exactly as a real payroll FEAT would, since
    # both writes occur under the same context.
    with FEATContext("FEAT-PROD-003", correlation_id="q5:labor", idempotency_key="q5:labor"):
        db.session.add(PayrollEvent(
            class_id=cid, target_seat_id=sA.seat_id, target_user_id=sA.user.id,
            actor_seat_id=teacher_seat_id, correlation_id="corr_q5:labor",
            idempotency_key="q5:labor:evt", policy_version_id=policy.id,
            policy_uuid=policy.policy_uuid, mechanism="TEACHER",
            payroll_event_type="payroll", recorded_at=now,
        ))
        create_pending_transaction(
            seat_id=sA.seat_id, class_id=cid, target_seat_id=sA.seat_id,
            actor_seat_id=teacher_seat_id, mechanism="system",
            amount=Decimal("20.00"), account_type="checking",
            type="payroll", description="labor",
        )

    # cat 3 — teacher/admin: manual_credit corroborated by a PayrollEvent.
    with FEATContext("FEAT-PROD-003", correlation_id="q5:manual", idempotency_key="q5:manual"):
        db.session.add(PayrollEvent(
            class_id=cid, target_seat_id=sB.seat_id, target_user_id=sB.user.id,
            actor_seat_id=teacher_seat_id, correlation_id="corr_q5:manual",
            idempotency_key="q5:manual:evt", policy_version_id=policy.id,
            policy_uuid=policy.policy_uuid, mechanism="TEACHER",
            payroll_event_type="manual_credit", recorded_at=now,
        ))
        create_pending_transaction(
            seat_id=sB.seat_id, class_id=cid, target_seat_id=sB.seat_id,
            actor_seat_id=teacher_seat_id, mechanism="teacher",
            amount=Decimal("5.00"), account_type="checking",
            type="manual_payment", description="manual credit",
        )

    # cat 5 — reversal: outbound base (excluded), inbound refund linked by orig id.
    base = _tx("FEAT-STOR-001", "q5:base", sC, "-3.00")
    _tx("FEAT-LED-002", "q5:rev", sC, "3.00", mechanism="system",
        original_transaction_id=base.id)

    # cat 4 — system non-labor: system-mechanism credit, no payroll corroboration.
    _tx("FEAT-LED-003", "q5:sys", sD, "2.00", mechanism="system")

    # cat 6 — other: interest (self/savings, dormant §10.4) + peer self-transfer.
    _tx("FEAT-LED-000", "q5:int", sA, "1.00", mechanism="self", account_type="savings")
    _tx("FEAT-STOR-001", "q5:peer", sB, "4.00", mechanism="self")

    return cid, window_start, window_end


def test_q5_composition_and_labor_share_reflect_origin_categories(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q5_window(classroom)

    entries = {e["candidate_id"]: e for e in compute_q5(cid, start, end)}

    # Q5-C1: six categories, sorted, sharing total inbound = 3500 cents.
    q5_c1 = entries["Q5-C1"]["value"]
    assert q5_c1["kind"] == "category_fractions"
    cats = {c["category"]: c for c in q5_c1["categories"]}
    labels = [c["category"] for c in q5_c1["categories"]]
    assert labels == sorted(labels)                 # §15.9 sorted
    assert set(cats) == set(INCOME_ORIGIN_CATEGORIES)  # all six present
    assert all(c["denominator"] == 3500 for c in q5_c1["categories"])

    assert cats[CATEGORY_LABOR]["numerator"] == 2000
    assert cats[CATEGORY_LABOR]["value"] == "0.5714"
    assert cats[CATEGORY_TEACHER_ADMIN]["numerator"] == 500
    assert cats[CATEGORY_TEACHER_ADMIN]["value"] == "0.1429"
    assert cats[CATEGORY_REVERSAL]["numerator"] == 300
    assert cats[CATEGORY_SYSTEM_NON_LABOR]["numerator"] == 200
    assert cats[CATEGORY_OTHER]["numerator"] == 500       # interest 100 + peer 400
    assert cats[CATEGORY_INTEREST]["numerator"] == 0      # dormant (§10.4)

    # Q5-C2: labor share = 2000 / 3500.
    q5_c2 = entries["Q5-C2"]["value"]
    assert q5_c2["kind"] == "ratio"
    assert q5_c2["antecedent"] == 2000
    assert q5_c2["consequent"] == 3500
    assert q5_c2["value"] == "0.5714"


# --------------------------------------------------------------------------- #
# 4. Coverage: the full payload still fails materialization (10 missing)       #
# --------------------------------------------------------------------------- #


def test_partial_payload_still_fails_only_for_incomplete_coverage(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q5_window(classroom)

    payload = compute_partial_payload(cid, start, end)
    assert payload["coverage"]["complete"] is False

    result = validate_payload_structure(payload)
    assert result.complete is False
    assert result.present_ids == IMPLEMENTED_CANDIDATES
    assert result.missing_ids == REQUIRED_SET_V1 - IMPLEMENTED_CANDIDATES
    assert len(result.missing_ids) == 10
    assert result.extra_ids == frozenset()
    assert result.duplicate_ids == frozenset()

    # The ONLY failure is incomplete coverage — the seven computed entries carry
    # no structural defect.
    assert len(result.errors) == 1
    assert "missing required candidate" in result.errors[0]

    with pytest.raises(ObservationContractError):
        validate_for_materialization(payload)
