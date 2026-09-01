"""Slice 8.2b-3 — Q3 obligation-outcome compute vertical.

Two layers of evidence:

1. **DB-free primitive logic** (``classify_outcome``, ``decompose_coverage``):
   proves the four disjoint §8.4 outcome categories are assigned deterministically
   (partial payment, mixed payment+waiver, unsatisfied-at-window-end, and the
   degenerate zero-assessed guard), and that amount coverage splits assessed
   dollars into student-paid / waived / unmet summing back to assessed — with
   student-paid counting only student-originated payment dollars (§8.5), never
   inferring where a seat's balance was funded from.

2. **DB-backed compute** over real ``assessment_events``: a mixed window of RENT
   outcomes plus an ``NSF_FEE`` obligation proves NSF enters Q3 *only* because an
   ``NSF_FEE`` ASSESSMENT event exists (§8.6, observationally boring), that a
   teacher-mechanism payment satisfies the obligation by count yet contributes no
   student-paid *dollars* (watch-point on funds attribution), and that all three
   candidates carry the per-obligation-type subject (§8.4) — Q3-C1 as
   ``category_fractions_by_type``, Q3-C2 as ``coverage_by_type``, Q3-C3 as
   per-``(type, kind)`` counts — so a reader can inspect outcomes with and without
   NSF. The full payload still fails materialization only for incomplete coverage
   (7 missing).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ObligationAssessment, RentSettings
from app.services.ledger_service import create_pending_transaction
from app.services.interpretation.obligation_observation import compute_q3
from app.services.interpretation.obligation_outcome import (
    OUTCOME_MIXED,
    OUTCOME_PAYMENT_ONLY,
    OUTCOME_UNSATISFIED,
    OUTCOME_WAIVED,
    classify_outcome,
    decompose_coverage,
)
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_V1,
    validate_for_materialization,
    validate_payload_structure,
)
from app.services.interpretation.compute import compute_partial_payload
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


# --------------------------------------------------------------------------- #
# 1. DB-free primitive logic                                                  #
# --------------------------------------------------------------------------- #


def test_classify_outcome_payment_only_when_fully_paid_no_waiver():
    assert classify_outcome(
        has_payment=True, has_waiver=False, paid_total_cents=1000, assessed_cents=1000
    ) == OUTCOME_PAYMENT_ONLY


def test_classify_outcome_waived_when_only_waiver():
    assert classify_outcome(
        has_payment=False, has_waiver=True, paid_total_cents=0, assessed_cents=1000
    ) == OUTCOME_WAIVED


def test_classify_outcome_mixed_when_partial_payment_plus_waiver():
    assert classify_outcome(
        has_payment=True, has_waiver=True, paid_total_cents=400, assessed_cents=1000
    ) == OUTCOME_MIXED


def test_classify_outcome_unsatisfied_when_underpaid_and_unwaived():
    assert classify_outcome(
        has_payment=True, has_waiver=False, paid_total_cents=400, assessed_cents=1000
    ) == OUTCOME_UNSATISFIED


def test_classify_outcome_zero_assessed_with_no_event_is_unsatisfied():
    # An unresolvable (zero) assessed amount with no satisfaction event must NOT
    # be treated as vacuously satisfied — it requires a real PAYMENT or WAIVED.
    assert classify_outcome(
        has_payment=False, has_waiver=False, paid_total_cents=0, assessed_cents=0
    ) == OUTCOME_UNSATISFIED


def test_classify_outcome_zero_assessed_with_settling_payment_is_payment_only():
    # An NSF/immediate obligation whose amount does not resolve, but which carries
    # a settling PAYMENT event, is satisfied by that payment.
    assert classify_outcome(
        has_payment=True, has_waiver=False, paid_total_cents=200, assessed_cents=0
    ) == OUTCOME_PAYMENT_ONLY


def test_decompose_coverage_full_student_payment():
    assert decompose_coverage(
        assessed_cents=1000, paid_student_cents=1000, has_waiver=False
    ) == (1000, 0, 0)


def test_decompose_coverage_mixed_waiver_covers_remainder():
    assert decompose_coverage(
        assessed_cents=1000, paid_student_cents=400, has_waiver=True
    ) == (400, 600, 0)


def test_decompose_coverage_teacher_funded_payment_is_not_student_paid():
    # paid_student_cents is 0 because the payment's ledger row was not
    # student-originated; with no waiver the whole assessed amount is unmet.
    assert decompose_coverage(
        assessed_cents=1000, paid_student_cents=0, has_waiver=False
    ) == (0, 0, 1000)


def test_decompose_coverage_components_sum_to_assessed():
    paid, waived, unmet = decompose_coverage(
        assessed_cents=1000, paid_student_cents=400, has_waiver=False
    )
    assert paid + waived + unmet == 1000


def test_decompose_coverage_zero_assessed_contributes_nothing():
    assert decompose_coverage(
        assessed_cents=0, paid_student_cents=500, has_waiver=True
    ) == (0, 0, 0)


# --------------------------------------------------------------------------- #
# 2. DB-backed Q3 compute                                                     #
# --------------------------------------------------------------------------- #


def _seed_rent_policy(cid) -> str:
    """Ensure the class RentSettings resolves RENT assessments to 10.00 assessed.

    The classroom initializer already provisions a class RentSettings (unique per
    class_id), so this reuses it — setting a known ``rent_amount`` — rather than
    inserting a second row.
    """
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="q3:rent:policy"):
        rs = RentSettings.query.filter_by(class_id=cid).first()
        if rs is None:
            rs = RentSettings(class_id=cid, rent_amount=Decimal("10.00"))
            db.session.add(rs)
        else:
            rs.rent_amount = Decimal("10.00")
        db.session.flush()
        return rs.policy_uuid


def _seed_q3_window(classroom):
    """Seed a mixed six-obligation window (five RENT + one NSF_FEE).

    RENT assessed = 1000 cents each. Layout:
      #1 RENT  paid-only (student-originated full payment)
      #2 RENT  waived
      #3 RENT  mixed (student 400 + waiver covers remaining 600)
      #4 RENT  unsatisfied (no satisfaction event)
      #5 RENT  teacher-mechanism payment: satisfied by count, 0 student dollars
      NSF      NSF_FEE, settling student payment, amount unresolvable (0 assessed)
    """
    cid = classroom.class_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    policy_uuid = _seed_rent_policy(cid)

    def _assess(corr, seat, otype, ts, policy=None):
        db.session.add(ObligationAssessment(
            correlation_id=corr, seat_id=seat.seat_id, class_id=cid,
            obligation_type=otype, event_type="ASSESSMENT",
            internal_ref=f"itr:{corr}", policy_uuid=policy, timestamp=ts,
        ))
        db.session.flush()

    def _waive(corr, seat, otype, ts):
        db.session.add(ObligationAssessment(
            correlation_id=corr, seat_id=seat.seat_id, class_id=cid,
            obligation_type=otype, event_type="WAIVED",
            internal_ref=f"itr:{corr}", timestamp=ts,
        ))
        db.session.flush()

    def _pay(corr, seat, otype, amount, ts, mechanism="self", feat="FEAT-OBL-001"):
        with FEATContext(feat, correlation_id=f"q3:{corr}:pay", idempotency_key=f"q3:{corr}:pay"):
            txn = create_pending_transaction(
                seat_id=seat.seat_id, class_id=cid, target_seat_id=seat.seat_id,
                actor_seat_id=seat.seat_id, mechanism=mechanism,
                amount=Decimal(amount), account_type="checking",
                type="rent_payment", description="q3 pay",
            )
            db.session.add(ObligationAssessment(
                correlation_id=corr, seat_id=seat.seat_id, class_id=cid,
                obligation_type=otype, event_type="PAYMENT",
                internal_ref=f"itr:{corr}", ledger_transaction_id=txn.id,
                timestamp=ts,
            ))
            db.session.flush()

    pay_ts = now + timedelta(minutes=5)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="q3:assess"):
        _assess("rent1", sA, "RENT", now, policy=policy_uuid)
        _assess("rent2", sB, "RENT", now, policy=policy_uuid)
        _assess("rent3", sC, "RENT", now, policy=policy_uuid)
        _assess("rent4", sD, "RENT", now, policy=policy_uuid)
        _assess("rent5", sA, "RENT", now, policy=policy_uuid)
        _assess("nsf1", sB, "NSF_FEE", now)
        # #2 waived, #3 waived (mixed) — waivers may share the assess context.
        _waive("rent2", sB, "RENT", pay_ts)
        _waive("rent3", sC, "RENT", pay_ts)

    # Payment ledger rows (each in its own FEAT correlation).
    _pay("rent1", sA, "RENT", "-10.00", pay_ts)                       # student full
    _pay("rent3", sC, "RENT", "-4.00", pay_ts)                        # student partial
    _pay("rent5", sA, "RENT", "-10.00", pay_ts, mechanism="teacher")  # teacher-funded
    _pay("nsf1", sB, "NSF_FEE", "-2.00", pay_ts)                      # settles NSF

    return cid, window_start, window_end


def _by_id(entries):
    return {e["candidate_id"]: e for e in entries}


def test_q3_c1_count_based_satisfaction_is_per_obligation_type(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q3_window(classroom)

    entries = _by_id(compute_q3(cid, start, end))
    entry = entries["Q3-C1"]
    assert entry["subject"] == "class_id, per obligation type"
    q3_c1 = entry["value"]
    assert q3_c1["kind"] == "category_fractions_by_type"
    by_type = q3_c1["obligation_types"]
    assert set(by_type) == {"RENT", "NSF_FEE"}          # NSF distinct

    # RENT: rent1/rent5 payment-only, rent2 waived, rent3 mixed, rent4 unsatisfied.
    rent = {c["category"]: c for c in by_type["RENT"]["categories"]}
    rent_labels = [c["category"] for c in by_type["RENT"]["categories"]]
    assert rent_labels == sorted(rent_labels)           # §15.9 nested sort
    assert all(c["denominator"] == 5 for c in by_type["RENT"]["categories"])
    assert rent[OUTCOME_PAYMENT_ONLY]["numerator"] == 2
    assert rent[OUTCOME_PAYMENT_ONLY]["value"] == "0.4000"
    assert rent[OUTCOME_WAIVED]["numerator"] == 1
    assert rent[OUTCOME_MIXED]["numerator"] == 1
    assert rent[OUTCOME_UNSATISFIED]["numerator"] == 1

    # NSF_FEE: a single payment-only obligation (settled by its fee debit).
    nsf = {c["category"]: c for c in by_type["NSF_FEE"]["categories"]}
    assert all(c["denominator"] == 1 for c in by_type["NSF_FEE"]["categories"])
    assert nsf[OUTCOME_PAYMENT_ONLY]["numerator"] == 1
    assert nsf[OUTCOME_PAYMENT_ONLY]["value"] == "1.0000"


def test_q3_c2_amount_coverage_is_per_type_and_partitions_assessed(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q3_window(classroom)

    entries = _by_id(compute_q3(cid, start, end))
    entry = entries["Q3-C2"]
    assert entry["subject"] == "class_id, per obligation type"
    q3_c2 = entry["value"]
    assert q3_c2["kind"] == "coverage_by_type"
    by_type = q3_c2["obligation_types"]
    assert set(by_type) == {"RENT", "NSF_FEE"}

    rent = by_type["RENT"]
    assert rent["assessed_cents"] == 5000            # five RENT × 1000
    # paid: rent1 1000 + rent3 400 (rent5 teacher-funded contributes 0) = 1400
    assert rent["student_paid_cents"] == 1400
    # waived: rent2 1000 + rent3 remainder 600 = 1600
    assert rent["waived_cents"] == 1600
    # unmet: rent4 1000 + rent5 1000 (teacher-funded, not student-paid) = 2000
    assert rent["unmet_cents"] == 2000
    # The three numerators partition the assessed denominator exactly.
    assert (rent["student_paid_cents"] + rent["waived_cents"]
            + rent["unmet_cents"]) == rent["assessed_cents"]

    # NSF fee: amount unresolvable → all components zero (contributes nothing to
    # amount coverage, an honest consequence of the missing amount).
    nsf = by_type["NSF_FEE"]
    assert nsf == {"assessed_cents": 0, "student_paid_cents": 0,
                   "waived_cents": 0, "unmet_cents": 0}


def test_q3_c3_counts_are_per_obligation_type_with_nsf_distinct(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q3_window(classroom)

    entries = _by_id(compute_q3(cid, start, end))
    q3_c3 = entries["Q3-C3"]["value"]
    assert q3_c3["kind"] == "counts"
    labels = [it["label"] for it in q3_c3["items"]]
    assert labels == sorted(labels)                      # §15.9
    counts = {it["label"]: it["count"] for it in q3_c3["items"]}

    # NSF is identified distinctly, solely because an NSF_FEE ASSESSMENT exists.
    assert counts["NSF_FEE:assessment"] == 1
    assert counts["NSF_FEE:payment"] == 1
    assert counts["RENT:assessment"] == 5
    assert counts["RENT:payment"] == 3     # rent1 + rent3 + rent5
    assert counts["RENT:waived"] == 2      # rent2 + rent3
    assert counts["RENT:unsatisfied"] == 1  # rent4
    assert q3_c3["total"] == sum(counts.values())


def test_q3_empty_window_reports_lawful_zero_baseline(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    now = utc_now()

    entries = _by_id(compute_q3(cid, now - timedelta(hours=1), now + timedelta(hours=1)))
    # All three candidates are computed (not not_applicable) with zero-bearing
    # values. The per-type maps are lawfully empty (no obligations observed);
    # counts stays non-empty via the global event-kind baseline.
    q3_c3 = entries["Q3-C3"]["value"]
    assert q3_c3["items"]                       # non-empty
    assert q3_c3["total"] == 0
    assert entries["Q3-C1"]["value"]["obligation_types"] == {}
    assert entries["Q3-C2"]["value"]["obligation_types"] == {}


# --------------------------------------------------------------------------- #
# 3. Coverage: the full payload over the obligation window is materializable     #
# --------------------------------------------------------------------------- #


def test_full_payload_over_obligation_window_is_materializable(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_q3_window(classroom)

    payload = compute_partial_payload(cid, start, end)
    assert payload["coverage"]["complete"] is True

    result = validate_payload_structure(payload)
    assert result.complete is True
    assert result.present_ids == REQUIRED_SET_V1
    assert result.missing_ids == frozenset()
    assert result.errors == ()

    validate_for_materialization(payload)
