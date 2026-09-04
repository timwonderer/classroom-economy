"""Ledger-owned fee commands."""

from decimal import Decimal

from app.feats.ledger_resolution_feat import (
    apply_resolved_ledger_plan,
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
)
from app.services.class_configuration_query_service import get_current_economic_engine


def apply_overdraft_fee_if_needed(
    seat,
    *,
    force: bool = False,
    idempotency_key: str | None = None,
):
    """Execute the Ledger overdraft command; the caller owns the FEAT transaction."""
    intended_plan = build_intended_ledger_plan(
        seat_id=seat.id,
        class_id=seat.class_id,
        user_id=seat.user_id,
        debit_amount=Decimal("0.00"),
        description="Overdraft fee",
    )
    economic_engine = get_current_economic_engine(seat.class_id)
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        economic_engine=economic_engine,
        idempotency_key=idempotency_key,
        force_overdraft_fee=force,
        allow_recovery_transfer=False,
    )
    result = apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        economic_engine=economic_engine,
        idempotency_key=idempotency_key,
    )
    return result.get("accepted", False), resolved_plan.overdraft_fee_amount


__all__ = ["apply_overdraft_fee_if_needed"]
