"""Obligation-outcome interpretation primitive (SPEC-ITR-001 §8).

The single canonical read primitive behind all three Q3 candidates. It consumes
the authoritative ``assessment_events`` surface (DOM-OBL-001, via
``obligations_service.get_obligation_events_for_window``) and returns the *final
interpreted state per obligation* — one record per ``ASSESSMENT`` correlation in
the window. Every Q3 candidate is then a pure aggregation over these records, so
the hard parts (partial payments, mixed payment+waiver, unsatisfied-at-window-end,
NSF-fee as an ordinary obligation type, student-originated coverage attribution)
are decided in exactly one place.

Two constitutional constraints govern this module:

* **NSF is observationally boring (§8.6).** An NSF fee participates in Q3 solely
  because an ``NSF_FEE`` ``ASSESSMENT`` event exists in ``assessment_events``. This
  module treats ``obligation_type`` as opaque data — it never special-cases a
  string called "NSF", never falls back to a Ledger ``type`` (INV-ITR-015), and
  never synthesizes a missing obligation (§8.6 scope boundary).
* **Coverage attribution never infers funds lineage (§8.5).** The paid *dollars*
  of Q3-C2 count only ``PAYMENT`` events whose referenced Ledger row is
  student-originated per the §6.3 classifier (asked of the Ledger domain). Where a
  teacher-injected credit funded the seat's balance before the payment, this
  module does **not** attribute that funding — the persisted provenance cannot
  support it, so such coverage is simply not claimed as student-paid.
"""

from __future__ import annotations

from typing import NamedTuple

from app.services.ledger_service import get_student_originated_transaction_ids
from app.services.obligations_service import get_obligation_events_for_window

# --- Final outcome categories (SPEC-ITR-001 §8.4 Q3-C1) --------------------
# Numeric-prefixed so §15.9 ascending sort is stable and meaningful.
OUTCOME_PAYMENT_ONLY = "1_satisfied_payment_only"
OUTCOME_WAIVED = "2_satisfied_waived"
OUTCOME_MIXED = "3_satisfied_mixed"
OUTCOME_UNSATISFIED = "4_unsatisfied"
OUTCOME_CATEGORIES: tuple[str, ...] = (
    OUTCOME_PAYMENT_ONLY,
    OUTCOME_WAIVED,
    OUTCOME_MIXED,
    OUTCOME_UNSATISFIED,
)

# Amount coverage (SPEC-ITR-001 §8.4 Q3-C2) is carried per obligation type by the
# ``coverage_by_type`` value's integer fields (assessed / student_paid / waived /
# unmet cents), not as category labels — see ``InterpretedObligation`` below.

# --- Event-kind labels for the counts fallback (SPEC-ITR-001 §8.4 Q3-C3) ---
EVENT_KINDS: tuple[str, ...] = ("assessment", "payment", "unsatisfied", "waived")


class InterpretedObligation(NamedTuple):
    """The final interpreted state of one obligation at window end (§8.4)."""

    correlation_id: str
    obligation_type: str
    outcome: str  # one of OUTCOME_CATEGORIES
    assessed_cents: int
    paid_student_cents: int  # student-originated coverage, capped at assessed
    waived_cents: int
    unmet_cents: int
    n_payment_events: int
    n_waived_events: int


def classify_outcome(
    *, has_payment: bool, has_waiver: bool, paid_total_cents: int, assessed_cents: int
) -> str:
    """Classify an obligation into one of the four §8.4 outcome categories.

    Satisfaction requires a real satisfaction *event*: a WAIVED event, or a
    PAYMENT whose accumulated magnitude meets the assessed amount. This guards
    the degenerate ``assessed == 0`` case (e.g. an amount that does not resolve
    from an upstream policy): a zero-amount obligation with no satisfaction event
    is ``UNSATISFIED``, not vacuously satisfied. When an NSF/immediate obligation
    carries a settling PAYMENT, that payment satisfies it (payment-only).
    """
    satisfied_by_payment = has_payment and paid_total_cents >= assessed_cents
    if not (has_waiver or satisfied_by_payment):
        return OUTCOME_UNSATISFIED
    if has_payment and has_waiver:
        return OUTCOME_MIXED
    if has_waiver:
        return OUTCOME_WAIVED
    return OUTCOME_PAYMENT_ONLY


def decompose_coverage(
    *, assessed_cents: int, paid_student_cents: int, has_waiver: bool
) -> tuple[int, int, int]:
    """Split assessed dollars into (paid, waived, unmet) cents summing to assessed.

    ``paid`` counts only student-originated payment dollars (§8.5), capped at the
    assessed amount. A waiver covers whatever assessed amount the student did not
    pay. Whatever remains after student payment and waiver is unmet. When the
    assessed amount is unresolvable (``0``), all three components are ``0`` — the
    obligation contributes nothing to the amount-based coverage denominator, an
    honest consequence of the missing amount rather than a fabricated figure.
    """
    assessed = max(int(assessed_cents), 0)
    paid_cov = min(max(int(paid_student_cents), 0), assessed)
    waived_cov = (assessed - paid_cov) if has_waiver else 0
    unmet_cov = assessed - paid_cov - waived_cov
    return paid_cov, waived_cov, unmet_cov


def interpret_obligations(
    class_id: str, window_start, window_end
) -> list[InterpretedObligation]:
    """Return the final interpreted state of every obligation assessed in-window.

    One record per ``ASSESSMENT`` correlation in ``[window_start, window_end)``.
    The referenced-Ledger provenance of each ``PAYMENT`` is resolved once, in a
    single batched call to the Ledger §6.3 classifier, so coverage attribution is
    consistent across all obligations.
    """
    rows = get_obligation_events_for_window(class_id, window_start, window_end)
    if not rows:
        return []

    payment_txn_ids = [
        r.ledger_transaction_id
        for r in rows
        if r.event_type == "PAYMENT" and r.ledger_transaction_id is not None
    ]
    student_txn_ids = get_student_originated_transaction_ids(class_id, payment_txn_ids)

    # Group events by obligation correlation.
    by_correlation: dict[str, dict] = {}
    for r in rows:
        agg = by_correlation.setdefault(
            r.correlation_id,
            {
                "obligation_type": r.obligation_type,
                "assessed_cents": 0,
                "paid_total_cents": 0,
                "paid_student_cents": 0,
                "n_payment": 0,
                "n_waived": 0,
            },
        )
        if r.event_type == "ASSESSMENT":
            if r.assessed_amount_cents is not None:
                agg["assessed_cents"] = int(r.assessed_amount_cents)
        elif r.event_type == "PAYMENT":
            agg["n_payment"] += 1
            magnitude = int(r.ledger_amount_cents or 0)
            agg["paid_total_cents"] += magnitude
            if r.ledger_transaction_id in student_txn_ids:
                agg["paid_student_cents"] += magnitude
        elif r.event_type == "WAIVED":
            agg["n_waived"] += 1

    interpreted: list[InterpretedObligation] = []
    for correlation_id, agg in by_correlation.items():
        has_payment = agg["n_payment"] > 0
        has_waiver = agg["n_waived"] > 0
        outcome = classify_outcome(
            has_payment=has_payment,
            has_waiver=has_waiver,
            paid_total_cents=agg["paid_total_cents"],
            assessed_cents=agg["assessed_cents"],
        )
        paid_cov, waived_cov, unmet_cov = decompose_coverage(
            assessed_cents=agg["assessed_cents"],
            paid_student_cents=agg["paid_student_cents"],
            has_waiver=has_waiver,
        )
        interpreted.append(
            InterpretedObligation(
                correlation_id=correlation_id,
                obligation_type=agg["obligation_type"],
                outcome=outcome,
                assessed_cents=agg["assessed_cents"],
                paid_student_cents=paid_cov,
                waived_cents=waived_cov,
                unmet_cents=unmet_cov,
                n_payment_events=agg["n_payment"],
                n_waived_events=agg["n_waived"],
            )
        )
    return interpreted
