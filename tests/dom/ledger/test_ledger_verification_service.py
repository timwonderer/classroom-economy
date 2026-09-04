from unittest.mock import patch

from app.services.ledger_balance_query_service import LedgerProofResult, TransferProofResult
from app.services.ledger_verification_service import verify_class_ledger


def test_class_verification_requires_authorized_work_item():
    result = verify_class_ledger(class_id="", balance_scopes=())
    assert result.state == "UNKNOWN"
    assert result.checks == ()


def test_class_verification_aggregates_ledger_proofs_without_scope_output():
    transfer = TransferProofResult("PASS", 2, True, True, True, True, True)
    with patch("app.services.ledger_verification_service.verify_posted_balance",
               return_value=LedgerProofResult("PASS", 100, 3)), \
         patch("app.services.ledger_verification_service.verify_available_balance",
               return_value=LedgerProofResult("PASS", 100, 3)), \
         patch("app.services.ledger_verification_service.verify_transfer",
               return_value=transfer):
        result = verify_class_ledger(
            class_id="class-internal", balance_scopes=((7, "checking"),),
            transfer_correlations=("corr_transfer",),
        )

    assert result.state == "AVAILABLE"
    assert [check.check for check in result.checks] == [
        "posted_balance_reconciliation", "available_balance_constraint",
        "internal_transfer_zero_sum",
    ]
    assert all(not hasattr(check, "class_id") for check in result.checks)


def test_class_verification_maps_unavailable_proof_to_unknown():
    with patch("app.services.ledger_verification_service.verify_posted_balance",
               return_value=LedgerProofResult("UNAVAILABLE", complete=False, code="missing_snapshot")), \
         patch("app.services.ledger_verification_service.verify_available_balance",
               return_value=LedgerProofResult("PASS", 100, 3)):
        result = verify_class_ledger(
            class_id="class-internal", balance_scopes=((7, "checking"),),
        )
    assert result.state == "UNKNOWN"
