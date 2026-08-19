from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import ClassEconomy, Seat
from app.services import ledger_service
from app.models import _quantize_currency
from decimal import InvalidOperation


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


@requires_feat_context("FEAT-LED-000")
def resolve_intended_ledger_plan(
    *,
    plan: IntendedLedgerPlan,
    banking_settings=None,
    idempotency_key: str | None = None,
    force_overdraft_fee: bool = False,
    allow_recovery_transfer: bool = True,
) -> ResolvedLedgerPlan:
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
        if banking_settings and banking_settings.overdraft_fee_enabled and force_overdraft_fee:
            fee_amount = _calculate_overdraft_fee_amount(
                seat=seat,
                banking_settings=banking_settings,
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
    allowed = bool(
        banking_settings
        and banking_settings.overdraft_protection_enabled
        and savings_balance >= shortfall
    )

    if allowed:
        return ResolvedLedgerPlan(
            outcome="ACCEPT",
            intended_plan=plan,
            notes=[f"checking={checking_balance} savings={savings_balance}"],
        )

    if banking_settings and banking_settings.overdraft_protection_enabled and allow_recovery_transfer and shortfall > 0:
        if savings_balance >= shortfall:
            return ResolvedLedgerPlan(
                outcome="TRANSFORM",
                intended_plan=plan,
                shortfall=_quantize_currency(shortfall),
                recovery_transfer_amount=_quantize_currency(shortfall),
                notes=["savings recovery transfer"],
            )

    if banking_settings and banking_settings.overdraft_fee_enabled and (force_overdraft_fee or shortfall > 0 or checking_balance < 0):
        fee_amount = _calculate_overdraft_fee_amount(
            seat=seat,
            banking_settings=banking_settings,
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


def _calculate_overdraft_fee_amount(*, seat, banking_settings, force: bool = False) -> Decimal:
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return Decimal("0.00")

    current_balance = _quantize_currency(
        ledger_service.get_available_balance(seat.id, seat.class_id, "checking")
    )

    if abs(current_balance) < Decimal("0.01"):
        current_balance = Decimal("0.00")

    if not force and current_balance >= Decimal("0.00"):
        return Decimal("0.00")

    if banking_settings.overdraft_fee_type == "flat":
        return _quantize_currency(banking_settings.overdraft_fee_flat_amount)

    if banking_settings.overdraft_fee_type == "progressive":
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

        if overdraft_fee_count == 0:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_1 or 0)
        elif overdraft_fee_count == 1:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_2 or 0)
        else:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_3 or 0)

        if banking_settings.overdraft_fee_progressive_cap:
            from sqlalchemy import func
            from app.models import Transaction

            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.seat_id == seat.id,
                Transaction.class_id == seat.class_id,
                Transaction.type == "overdraft_fee",
                Transaction.timestamp >= month_start_utc,
            ).scalar()
            total_fees_this_month = _quantize_currency(total_fees_this_month) if total_fees_this_month else Decimal("0.00")
            cap = _quantize_currency(banking_settings.overdraft_fee_progressive_cap)
            if abs(total_fees_this_month) + fee_amount > cap:
                fee_amount = max(Decimal("0.00"), cap - abs(total_fees_this_month))
        return fee_amount

    return Decimal("0.00")


@requires_feat_context("FEAT-LED-000")
def apply_resolved_ledger_plan(
    *,
    resolved_plan: ResolvedLedgerPlan,
    banking_settings=None,
    idempotency_key: str | None = None,
):
    seat = db.session.get(Seat, resolved_plan.intended_plan.seat_id)
    if not seat or seat.class_id != resolved_plan.intended_plan.class_id:
        return {"accepted": False, "reason": "invalid_scope"}

    if resolved_plan.outcome == "DENY":
        return {"accepted": False, "reason": "denied"}

    if resolved_plan.recovery_transfer_amount > 0:
        class_economy = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        user_id = class_economy.user_id if class_economy else resolved_plan.intended_plan.user_id
        if not user_id:
            return {"accepted": False, "reason": "missing_user"}
        ledger_service.create_transfer_pair(
            seat_id=seat.id,
            class_id=seat.class_id,
            user_id=user_id,
            amount=resolved_plan.recovery_transfer_amount,
            from_account="savings",
            to_account="checking",
            withdraw_description="Overdraft protection transfer to checking",
            deposit_description="Overdraft protection transfer from savings",
        )
        db.session.flush()

    if resolved_plan.overdraft_fee_amount > 0:
        fee_idempotency_key = idempotency_key or f"overdraft:{seat.id}:{resolved_plan.intended_plan.class_id}"
        class_economy = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        user_id = class_economy.user_id if class_economy else resolved_plan.intended_plan.user_id
        if not user_id:
            return {"accepted": False, "reason": "missing_user"}
        fee_transaction, _created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=fee_idempotency_key,
            seat_id=seat.id,
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=ledger_service.resolve_class_authority_seat_id(seat.class_id),
            mechanism="system",
            user_id=user_id,
            amount=-resolved_plan.overdraft_fee_amount,
            account_type="checking",
            type="overdraft_fee",
            description="Overdraft fee",
        )
        return {"accepted": True, "reason": resolved_plan.outcome, "ledger_transaction_id": fee_transaction.id}

    return {"accepted": True, "reason": resolved_plan.outcome}
