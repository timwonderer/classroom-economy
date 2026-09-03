from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.extensions import db
from app.models import Seat, EconomicEngine
from app.services import ledger_service
from app.models import _quantize_currency
from decimal import InvalidOperation
import logging

logger = logging.getLogger(__name__)


@dataclass
class IntendedLedgerPlan:
    seat_id: int
    class_id: str
    user_id: int | None
    debit_amount: Decimal
    description: str
    source_account: str = "checking"
    target_account: str | None = None


@dataclass
class ResolvedLedgerPlan:
    outcome: str
    intended_plan: IntendedLedgerPlan
    shortfall: Decimal = Decimal("0.00")
    recovery_transfer_amount: Decimal = Decimal("0.00")
    overdraft_fee_amount: Decimal = Decimal("0.00")
    notes: list[str] = field(default_factory=list)


def build_intended_ledger_plan(
    *,
    seat_id: int,
    class_id: str,
    user_id: int | None,
    debit_amount,
    description: str,
    source_account: str = "checking",
    target_account: str | None = None,
) -> IntendedLedgerPlan:
    return IntendedLedgerPlan(
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        debit_amount=_quantize_currency(debit_amount),
        description=description,
        source_account=source_account,
        target_account=target_account,
    )


def resolve_intended_ledger_plan(
    *,
    plan: IntendedLedgerPlan,
    economic_engine: EconomicEngine | None,
    idempotency_key: str | None = None,
    force_overdraft_fee: bool = False,
    allow_recovery_transfer: bool = True,
) -> ResolvedLedgerPlan:
    """Ledger DOMAIN query: resolve an intended plan to ACCEPT/TRANSFORM/DENY.

    Pure and side-effect free (INV-ARC-006 — it mutates nothing). A business FEAT
    composes this query and the ``apply_resolved_ledger_plan`` command within its
    own single FEAT context; this is NOT a FEAT executor (no nested FEAT).
    """
    seat = db.session.get(Seat, plan.seat_id)
    if not seat or seat.class_id != plan.class_id:
        return ResolvedLedgerPlan(
            outcome="DENY",
            intended_plan=plan,
            notes=["invalid seat/class scope"],
        )

    checking_balance, savings_balance = _get_available_balances(seat)
    try:
        debit_amount = _quantize_currency(plan.debit_amount)
    except (TypeError, InvalidOperation):
        return ResolvedLedgerPlan(
            outcome="DENY",
            intended_plan=plan,
            notes=["invalid debit amount"],
        )

    if debit_amount <= Decimal("0.00"):
        if economic_engine and force_overdraft_fee:
            fee_amount = _calculate_overdraft_fee_amount(
                seat=seat,
                economic_engine=economic_engine,
                force=True,
            )
            if fee_amount > 0:
                return ResolvedLedgerPlan(
                    outcome="TRANSFORM",
                    intended_plan=plan,
                    overdraft_fee_amount=fee_amount,
                    notes=["forced overdraft fee"],
                )
        return ResolvedLedgerPlan(
            outcome="ACCEPT",
            intended_plan=plan,
            notes=[f"checking={checking_balance} savings={savings_balance}"],
        )

    if checking_balance >= debit_amount:
        return ResolvedLedgerPlan(
            outcome="ACCEPT",
            intended_plan=plan,
            notes=[f"checking={checking_balance} savings={savings_balance}"],
        )

    shortfall = debit_amount - checking_balance
    if allow_recovery_transfer and economic_engine is not None and economic_engine.overdraft_protection_enabled is True and shortfall > 0:
        if savings_balance >= shortfall:
            return ResolvedLedgerPlan(
                outcome="TRANSFORM",
                intended_plan=plan,
                shortfall=_quantize_currency(shortfall),
                recovery_transfer_amount=_quantize_currency(shortfall),
                notes=["savings recovery transfer"],
            )

    if economic_engine and (force_overdraft_fee or shortfall > 0 or checking_balance < 0):
        fee_amount = _calculate_overdraft_fee_amount(
            seat=seat,
            economic_engine=economic_engine,
            force=force_overdraft_fee or shortfall > 0 or checking_balance < 0,
        )
        if fee_amount > 0:
            return ResolvedLedgerPlan(
                outcome="TRANSFORM",
                intended_plan=plan,
                shortfall=_quantize_currency(shortfall),
                overdraft_fee_amount=fee_amount,
                notes=["overdraft fee"],
            )

    return ResolvedLedgerPlan(
        outcome="DENY",
        intended_plan=plan,
        shortfall=_quantize_currency(shortfall),
        notes=["insufficient funds"],
    )


def _get_available_balances(seat: Seat) -> tuple[Decimal, Decimal]:
    return ledger_service.get_available_balances(seat.id, seat.class_id)


def _calculate_overdraft_fee_amount(*, seat, economic_engine, force: bool = False) -> Decimal:
    if not economic_engine:
        return Decimal("0.00")

    current_balance = _quantize_currency(
        ledger_service.get_available_balance(seat.id, seat.class_id, "checking")
    )

    if abs(current_balance) < Decimal("0.01"):
        current_balance = Decimal("0.00")

    if not force and current_balance >= Decimal("0.00"):
        return Decimal("0.00")

    if economic_engine.flat_overdraft_fee is not None:
        return _quantize_currency(economic_engine.flat_overdraft_fee)

    if economic_engine.progressive_overdraft_fee is not None:
        from types import SimpleNamespace
        from app.utils.canonical_temporal_resolver import (
            canonical_temporal_resolver, CLASS_LEVEL_EVALUATION,
        )
        ctx = SimpleNamespace(class_id=seat.class_id)
        month_eval = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="evaluation_period_boundaries",
            period="month",
        )
        month_start_utc = month_eval.boundary_start_utc

        from app.models import Transaction

        fee_filters = [
            Transaction.seat_id == seat.id,
            Transaction.class_id == seat.class_id,
            Transaction.type == "overdraft_fee",
            Transaction.timestamp >= month_start_utc,
        ]

        overdraft_fee_count = Transaction.query.filter(*fee_filters).count()

        tier = "tier_1" if overdraft_fee_count == 0 else "tier_2" if overdraft_fee_count == 1 else "tier_3"
        schedule = economic_engine.progressive_overdraft_fee
        if not isinstance(schedule, dict):
            logger.error("Malformed progressive_overdraft_fee for class %s", seat.class_id)
            return Decimal("0.00")
        raw_rate = schedule.get(tier)
        if raw_rate is None:
            return Decimal("0.00")
        try:
            rate = Decimal(str(raw_rate).strip().rstrip("%")) / Decimal("100")
        except (InvalidOperation, ValueError):
            logger.error("Unparseable progressive_overdraft_fee rate %r for class %s", raw_rate, seat.class_id)
            return Decimal("0.00")
        if rate < 0:
            return Decimal("0.00")
        from app.services.class_configuration_query_service import calculate_cwi
        cwi = calculate_cwi(seat.class_id)
        if cwi is None:
            return Decimal("0.00")
        return _quantize_currency(Decimal(str(cwi)) * rate)

    return Decimal("0.00")


def apply_resolved_ledger_plan(
    *,
    resolved_plan: ResolvedLedgerPlan,
    economic_engine: EconomicEngine | None,
    idempotency_key: str | None = None,
):
    """Ledger DOMAIN command: apply a resolved plan (posts the debit / recovery /
    overdraft-fee transactions). Runs within the CALLING FEAT's single context —
    it is NOT a FEAT executor and opens no FEAT boundary of its own (INV-ARC-006,
    INV-ARC-021 §V.2). The caller owns the transaction; the flush guard is
    satisfied by the caller's active FEAT context.

    economic_engine is the snapshot paired with resolve, accepted to keep
    resolve/apply signatures symmetric and to make the caller's policy snapshot
    explicit at the transaction boundary.
    """
    seat = db.session.get(Seat, resolved_plan.intended_plan.seat_id)
    if not seat or seat.class_id != resolved_plan.intended_plan.class_id:
        return {"accepted": False, "reason": "invalid_scope"}

    if resolved_plan.outcome == "DENY":
        return {"accepted": False, "reason": "denied"}

    if resolved_plan.recovery_transfer_amount > 0:
        # Internal economic action: anchor on class_id + seat_id only (INV-ARC-019).
        # A savings->checking overdraft-protection transfer moves the SEAT'S OWN
        # money between its own accounts; it is not a user-scoped act, so it carries
        # no user_id (the ledger row is anchored by target/actor seat).
        ledger_service.create_transfer_pair(
            seat_id=seat.id,
            class_id=seat.class_id,
            amount=resolved_plan.recovery_transfer_amount,
            from_account="savings",
            to_account="checking",
            withdraw_description="Overdraft protection transfer to checking",
            deposit_description="Overdraft protection transfer from savings",
        )
        db.session.flush()

    if resolved_plan.overdraft_fee_amount > 0:
        fee_idempotency_key = idempotency_key or f"overdraft:{seat.id}:{resolved_plan.intended_plan.class_id}"
        # Anchor on class_id + seat_id (INV-ARC-019): the fine is charged to the
        # student's seat, with the class authority seat as actor. No user_id.
        fee_transaction, _created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=fee_idempotency_key,
            seat_id=seat.id,
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=ledger_service.resolve_class_authority_seat_id(seat.class_id),
            mechanism="system",
            amount=-resolved_plan.overdraft_fee_amount,
            account_type="checking",
            type="overdraft_fee",
            description="Non-sufficient funds fee",
        )

        # NOTE: the NSF fee is a FINE and must ALSO be recorded as an obligation
        # (SPEC-ECON-003; DOM-OBL-001 §II.C immediate charge). That Economic-Context
        # write is NOT done here — DOM-LED-001 §II keeps Ledger domain-blind, so the
        # originating business FEAT records the NSF_FEE obligation from this result's
        # ledger_transaction_id as part of its own cross-domain orchestration.
        return {"accepted": True, "reason": resolved_plan.outcome, "ledger_transaction_id": fee_transaction.id}

    return {"accepted": True, "reason": resolved_plan.outcome}
