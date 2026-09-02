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

# Obligations DOMAIN commands (plain functions), invoked within the originating
# business FEAT's single context — never the execute_* FEAT wrappers
# (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2, INV-ARC-006).
from app.feats.assess_obligation_feat import assess_obligation, AssessmentRequest
from app.feats.satisfy_obligation_feat import satisfy_obligation, SatisfyObligationRequest


def record_nsf_fee_obligation(*, class_id: str, seat_id: int, fee_transaction_id: int) -> str:
    """Record the NSF fine for a posted fee debit. Returns its correlation_id.

    MUST be called within the originating business FEAT's context (which owns the
    commit); the assessment/payment run as that FEAT's cross-domain orchestration,
    via Obligations domain commands (not FEAT executors).
    """
    internal_ref = f"nsf-fee:{class_id}:{seat_id}"
    correlation_id = f"nsf-fee:{class_id}:{seat_id}:txn:{fee_transaction_id}"
    assess_obligation(
        AssessmentRequest(
            seat_id=seat_id,
            class_id=class_id,
            internal_ref=internal_ref,
            correlation_id=correlation_id,
            obligation_type="NSF_FEE",
        ),
        context=None,
    )
    satisfy_obligation(
        SatisfyObligationRequest(
            correlation_id=correlation_id,
            class_id=class_id,
            seat_id=seat_id,
            method="PAYMENT",
            ledger_transaction_id=fee_transaction_id,
        ),
        context=None,
    )
    return correlation_id
