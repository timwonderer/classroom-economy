"""Record an NSF (non-sufficient funds) fee as an immediate fine obligation.

An NSF/overdraft fee is a FINE (SPEC-ECON-003), and per DOM-OBL-001 §II.C an
immediately-collected charge is still an obligation ("settled immediately does
not remove it from this domain"). Its Economic Context is owned by the
Obligations domain — DOM-LED-001 §II keeps the Ledger domain-blind.

Ledger (``apply_resolved_ledger_plan``) posts the fee debit and returns its
``ledger_transaction_id``. The ORIGINATING BUSINESS FEAT then calls this
orchestrator, from within its own FEAT context, to record the fine as an
obligation: an ASSESSMENT plus a PAYMENT settled by that very fee debit. Keeping
this out of the ledger primitive preserves the domain boundary and avoids
Ledger orchestrating an Obligations write.

Identity-blind lineage (INV-ARC-019 — anchored on class_id + seat_id):
  internal_ref   = "nsf-fee:{class_id}:{seat_id}"
  correlation_id = "nsf-fee:{class_id}:{seat_id}:txn:{fee_transaction_id}"

Idempotent: the assessment dedupes by correlation_id and the payment dedupes by
ledger_transaction_id, so re-recording the same fee is a no-op.
"""

from __future__ import annotations

from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_payment


def record_nsf_fee_obligation(*, class_id: str, seat_id: int, fee_transaction_id: int) -> str:
    """Record the NSF fine for a posted fee debit. Returns its correlation_id.

    MUST be called within the originating business FEAT's context (which owns the
    commit); the assessment/payment run as that FEAT's cross-domain orchestration.
    """
    internal_ref = f"nsf-fee:{class_id}:{seat_id}"
    correlation_id = f"nsf-fee:{class_id}:{seat_id}:txn:{fee_transaction_id}"
    # correlation_id passed positionally: requires_feat_context inspects
    # kwargs["correlation_id"] and would reject a distinct obligation-level
    # correlation as an illegal nested context.
    execute_assess_obligation(
        seat_id,
        class_id,
        internal_ref,
        correlation_id,
        "NSF_FEE",
    )
    execute_satisfy_obligation_payment(
        correlation_id,
        class_id,
        seat_id,
        fee_transaction_id,
    )
    return correlation_id
