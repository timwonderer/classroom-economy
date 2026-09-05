"""Operations-facing coordination over Ledger-owned proof surfaces.

The coordinator receives an already-authorized, class-bound work item.  It
does not enumerate classes, issue Ledger SQL, or expose tenant detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.ledger_balance_query_service import (
    LedgerProofResult,
    TransferProofResult,
    verify_available_balance,
    verify_posted_balance,
    verify_transfer,
)


@dataclass(frozen=True)
class LedgerVerificationCheck:
    check: str
    outcome: str
    failure_count: int
    checked_at: datetime
    code: str | None = None


@dataclass(frozen=True)
class LedgerVerificationAggregate:
    state: str
    checks: tuple[LedgerVerificationCheck, ...]
    checked_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _balance_check(name: str, result: LedgerProofResult, checked_at: datetime) -> LedgerVerificationCheck:
    return LedgerVerificationCheck(
        check=name, outcome=result.outcome,
        failure_count=1 if result.outcome == "FAIL" else 0,
        checked_at=checked_at, code=result.code,
    )


def _transfer_check(result: TransferProofResult, checked_at: datetime) -> LedgerVerificationCheck:
    return LedgerVerificationCheck(
        check="internal_transfer_zero_sum", outcome=result.outcome,
        failure_count=1 if result.outcome == "FAIL" else 0,
        checked_at=checked_at, code=result.code,
    )


def verify_class_ledger(
    *, class_id: str, balance_scopes: tuple[tuple[int, str], ...],
    transfer_correlations: tuple[str, ...] = (),
) -> LedgerVerificationAggregate:
    """Run one authorized class-bound Ledger verification execution.

    Scope work items are supplied by the coordinator authority.  An empty
    work item is explicitly unknown rather than an implicit healthy result.
    Individual proof failures are isolated so one malformed scope cannot hide
    the remaining evidence.
    """
    checked_at = _now()
    checks: list[LedgerVerificationCheck] = []
    if not class_id or not balance_scopes:
        return LedgerVerificationAggregate("UNKNOWN", tuple(checks), checked_at)

    for seat_id, account_type in balance_scopes:
        try:
            checks.append(_balance_check(
                "posted_balance_reconciliation",
                verify_posted_balance(class_id, seat_id, account_type), checked_at,
            ))
            checks.append(_balance_check(
                "available_balance_constraint",
                verify_available_balance(class_id, seat_id, account_type), checked_at,
            ))
        except Exception:
            checks.append(LedgerVerificationCheck(
                check="ledger_balance_verification", outcome="UNKNOWN",
                failure_count=0, checked_at=checked_at, code="proof_execution_unavailable",
            ))

    for correlation_id in transfer_correlations:
        try:
            checks.append(_transfer_check(verify_transfer(class_id, correlation_id), checked_at))
        except Exception:
            checks.append(LedgerVerificationCheck(
                check="internal_transfer_zero_sum", outcome="UNKNOWN",
                failure_count=0, checked_at=checked_at, code="proof_execution_unavailable",
            ))

    if any(check.outcome == "FAIL" for check in checks):
        state = "DEGRADED"
    elif any(check.outcome == "UNAVAILABLE" for check in checks):
        state = "UNKNOWN"
    elif any(check.outcome == "UNKNOWN" for check in checks):
        state = "UNKNOWN"
    else:
        state = "AVAILABLE"
    return LedgerVerificationAggregate(state, tuple(checks), checked_at)


__all__ = ["LedgerVerificationCheck", "LedgerVerificationAggregate", "verify_class_ledger"]
