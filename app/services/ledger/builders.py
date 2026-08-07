"""
Ledger Domain View Model Builders — Phase 1 Remediation

Converts raw account balances and transaction records into immutable,
presentation-ready view models per SPEC-UI-001 and INV-ARC-022.

All numeric formatting (currency display, percentage) is pre-computed here.
All dates are pre-formatted. Templates receive only display-ready strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import Transaction, Seat, ClassEconomy


@dataclass(frozen=True)
class TransactionListItemView:
    """Pre-computed, formatted transaction record for display."""
    transaction_id: int
    display_amount: str  # Pre-formatted as "+$X.XX" or "-$X.XX"
    display_timestamp: str  # Pre-formatted (e.g., "Aug 04" or ISO)
    display_description: str
    icon_class: str | None  # CSS class for icon selection, if any
    account_type: str  # 'checking' or 'savings'
    transaction_type: str  # Type of transaction
    status: str  # 'posted', 'pending', 'void'


@dataclass(frozen=True)
class AccountBalanceView:
    """
    Pre-computed and formatted account balance snapshot.

    Eliminates all Jinja filters and numeric formatting from templates.
    """
    display_checking_balance: str  # Pre-formatted as "$X.XX"
    display_savings_balance: str  # Pre-formatted as "$X.XX"
    display_total_balance: str  # Pre-formatted as "$X.XX"
    checking_balance_raw: Decimal  # Raw for calculations
    savings_balance_raw: Decimal  # Raw for calculations
    total_balance_raw: Decimal  # Raw for calculations


def build_account_balance_view(
    checking_balance: Decimal | float | int,
    savings_balance: Decimal | float | int,
) -> AccountBalanceView:
    """
    Build pre-computed account balance view with formatted display strings.

    Eliminates template-level Jinja filters (audit violations: student_dashboard.html
    lines 262, 288, 291; student_rent.html lines 108, 114; etc.).

    Args:
        checking_balance: Raw checking account balance
        savings_balance: Raw savings account balance

    Returns:
        Frozen AccountBalanceView with pre-formatted display strings
    """
    # Convert to Decimal for precision
    checking = Decimal(str(checking_balance))
    savings = Decimal(str(savings_balance))
    total = checking + savings

    # Pre-format all display strings (no filters in template)
    display_checking = f"${checking:.2f}"
    display_savings = f"${savings:.2f}"
    display_total = f"${total:.2f}"

    return AccountBalanceView(
        display_checking_balance=display_checking,
        display_savings_balance=display_savings,
        display_total_balance=display_total,
        checking_balance_raw=checking,
        savings_balance_raw=savings,
        total_balance_raw=total,
    )


def build_transaction_list_view(
    transactions: list[Transaction],
    class_id: str,
) -> list[TransactionListItemView]:
    """
    Build pre-computed transaction list with formatted display values.

    Eliminates all date formatting and ORM iteration from template
    (audit violations: student_dashboard.html lines 321-349, 335, 336).

    Args:
        transactions: List of Transaction models sorted as desired
        class_id: Class scope for multi-tenancy

    Returns:
        List of frozen TransactionListItemView ready for template rendering
    """
    views = []

    for txn in transactions:
        # Pre-format amount display with sign
        amount = Decimal(str(txn.amount))
        if amount >= 0:
            display_amount = f"+${amount:.2f}"
        else:
            display_amount = f"-${abs(amount):.2f}"

        # Pre-format timestamp (eliminate strftime from template)
        # Use "Aug 04" format for conciseness in transaction lists
        display_timestamp = (
            txn.timestamp.strftime("%b %d")
            if txn.timestamp
            else "Unknown"
        )

        # Pre-format description
        display_description = txn.description or f"{txn.type} transaction"

        # Derive icon class from transaction type (presentation only)
        icon_class = _get_icon_class_for_transaction_type(txn.type)

        views.append(
            TransactionListItemView(
                transaction_id=txn.id,
                display_amount=display_amount,
                display_timestamp=display_timestamp,
                display_description=display_description,
                icon_class=icon_class,
                account_type=txn.account_type or "checking",
                transaction_type=txn.type or "transfer",
                status=txn.status.value if txn.status else "unknown",
            )
        )

    return views


def _get_icon_class_for_transaction_type(transaction_type: str | None) -> str | None:
    """
    Map transaction type to a Material Symbols icon class.

    This is presentation-only logic and does not affect domain truth.

    Args:
        transaction_type: The transaction type string

    Returns:
        CSS class for Material Symbols icon, or None if unknown type
    """
    icon_map = {
        "payroll": "payment",
        "transfer": "send",
        "deposit": "add_circle",
        "withdrawal": "remove_circle",
        "interest": "trending_up",
        "fee": "trending_down",
        "rent": "home",
        "hall_pass": "exit_to_app",
        "refund": "undo",
    }

    if not transaction_type:
        return None

    # Try exact match first
    if transaction_type in icon_map:
        return icon_map[transaction_type]

    # Try substring matching for common patterns
    txn_lower = transaction_type.lower()
    for key, icon in icon_map.items():
        if key in txn_lower:
            return icon

    return None


def build_transaction_summary_view(
    transactions: list[Transaction],
    class_id: str,
) -> dict[str, Any]:
    """
    Build a summary view of transactions (total count, date range, etc.).

    Supports dashboard summaries and analytics pages.

    Args:
        transactions: List of Transaction models
        class_id: Class scope

    Returns:
        Dict with pre-computed summary statistics
    """
    if not transactions:
        return {
            "total_count": 0,
            "earliest_date": None,
            "latest_date": None,
            "total_inflow": "$0.00",
            "total_outflow": "$0.00",
            "net_activity": "$0.00",
        }

    # Pre-compute summary
    total_inflow = Decimal("0.00")
    total_outflow = Decimal("0.00")
    earliest = None
    latest = None

    for txn in transactions:
        if txn.status.value == "void":
            continue

        amount = Decimal(str(txn.amount))
        if amount > 0:
            total_inflow += amount
        else:
            total_outflow += abs(amount)

        if txn.timestamp:
            if earliest is None or txn.timestamp < earliest:
                earliest = txn.timestamp
            if latest is None or txn.timestamp > latest:
                latest = txn.timestamp

    net_activity = total_inflow - total_outflow

    return {
        "total_count": len([t for t in transactions if t.status.value != "void"]),
        "earliest_date": earliest.strftime("%b %d, %Y") if earliest else None,
        "latest_date": latest.strftime("%b %d, %Y") if latest else None,
        "total_inflow": f"${total_inflow:.2f}",
        "total_outflow": f"${total_outflow:.2f}",
        "net_activity": f"${net_activity:+.2f}" if net_activity != 0 else "$0.00",
    }
