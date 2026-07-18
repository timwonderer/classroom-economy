from __future__ import annotations

from decimal import Decimal

from flask import Flask

from app.models import Transaction
from app.services import ledger_service
from app.utils.banking import settle_balances
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.classroom_initializer import (
    initialize as _initialize_classroom,
    initialize_as_student as _initialize_as_student,
    initialize_as_teacher as _initialize_as_teacher,
)


def provision_ledger_classroom(classroom_key: str, app: Flask):
    return _initialize_classroom(classroom_key, app)


def provision_ledger_teacher(classroom_key: str, client, app: Flask):
    return _initialize_as_teacher(classroom_key, client, app)


def provision_ledger_student(classroom_key: str, client, app: Flask, student_index: int = 0):
    return _initialize_as_student(classroom_key, client, app, student_index=student_index)


def create_ledger_idempotent_transaction(
    *,
    idempotency_key: str,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    account_type: str,
    type: str,
    description: str,
    target_seat_id: int | None = None,
    actor_seat_id: int,
    mechanism: str = "self",
    original_transaction_id: int | None = None,
    policy_id: int | None = None,
):
    return create_idempotent_transaction(
        idempotency_key=idempotency_key,
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=target_seat_id or seat_id,
        actor_seat_id=actor_seat_id or seat_id,
        mechanism=mechanism,
        user_id=user_id,
        amount=amount,
        account_type=account_type,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )


def create_ledger_pending_transaction(
    *,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    account_type: str,
    type: str,
    description: str,
    target_seat_id: int | None = None,
    actor_seat_id: int,
    mechanism: str = "self",
    original_transaction_id: int | None = None,
    policy_id: int | None = None,
):
    return ledger_service.create_pending_transaction(
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=target_seat_id or seat_id,
        actor_seat_id=actor_seat_id or seat_id,
        mechanism=mechanism,
        user_id=user_id,
        amount=amount,
        account_type=account_type,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )


def create_ledger_transfer_pair(
    *,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    from_account: str,
    to_account: str,
    withdraw_description: str,
    deposit_description: str,
):
    return ledger_service.create_transfer_pair(
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=amount,
        from_account=from_account,
        to_account=to_account,
        withdraw_description=withdraw_description,
        deposit_description=deposit_description,
    )


def compensate_ledger_posted_transaction(
    transaction: Transaction,
    *,
    description: str,
    compensation_type: str = "refund",
    idempotency_key: str | None = None,
):
    return ledger_service.compensate_posted_transaction(
        transaction,
        description=description,
        compensation_type=compensation_type,
        idempotency_key=idempotency_key,
    )


def apply_ledger_monthly_savings_interest(seat, *, annual_rate: Decimal = Decimal("0.045")):
    return ledger_service.apply_monthly_savings_interest(seat, annual_rate=annual_rate)


def apply_ledger_overdraft_fee_if_needed(seat, banking_settings, *, force: bool = False, idempotency_key: str | None = None):
    return ledger_service.apply_overdraft_fee_if_needed(
        seat,
        banking_settings,
        force=force,
        idempotency_key=idempotency_key,
    )


def settle_ledger_balances(seat_id: int, class_id: str) -> None:
    settle_balances(seat_id, class_id)
