from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.extensions import db
from app.models import LedgerMechanism, Transaction, TransactionStatus, _quantize_currency
from app.utils.canonical_temporal_resolver import ensure_utc


def _non_void_filter():
    return Transaction.is_void.isnot(True)


# --- Ledger provenance classifier (SPEC-ITR-001 §6.3) ----------------------
#
# The Interpretation domain classifies ledger rows by origin without ever
# consulting ``Transaction.type`` (INV-ITR-015). A row is *student-originated*
# iff it is a self-mechanism, non-reversal, non-void row whose ``feat_code`` is
# NOT one of the system-originated FEATs enumerated below. SPEC-ITR-001 §6.6
# defers the concrete enumeration to the implementing surface; the Ledger domain
# owns the provenance of its own rows, so the set lives here.
#
# Categories (SPEC-ITR-001 §6.3): payroll accrual, interest accrual, obligation
# assessment, admin adjustment, ledger resolution. Student-agency FEATs
# (FEAT-STOR-001 purchase, FEAT-OBL-001 rent self-payment, transfers) are
# deliberately excluded so those acts remain student-originated.
SYSTEM_ORIGINATED_FEAT_CODES: frozenset[str] = frozenset(
    {
        # payroll accrual
        "FEAT-LED-004",   # Payroll Execution
        "FEAT-PROD-003",  # Record Payroll Event
        # interest accrual / ledger resolution (Ledger authority posts these)
        "FEAT-LED-000",   # Canonical Monetary Resolution
        "FEAT-LED-003",   # Settlement Sweep
        # system-imposed fees
        "FEAT-LED-001",   # Overdraft/NSF Fee Application
        # obligation assessment (scheduled cycles, not self-payment)
        "FEAT-OBL-002",   # Scheduled Rent Cycle
        "FEAT-OBL-003",   # Scheduled Insurance Cycle
        # admin adjustment
        "FEAT-ADMN-001",  # Bulk administration
    }
)


def _student_originated_filter():
    """SQLAlchemy predicate for the §6.3 student-originated ledger classifier."""
    return db.and_(
        Transaction.mechanism == LedgerMechanism.SELF,
        Transaction.original_transaction_id.is_(None),
        Transaction.is_void.isnot(True),
        db.or_(
            Transaction.feat_code.is_(None),
            Transaction.feat_code.notin_(SYSTEM_ORIGINATED_FEAT_CODES),
        ),
    )


def get_seat_ids_with_student_originated_activity(
    class_id: str, window_start, window_end
) -> set[int]:
    """Return seat ids with ≥1 student-originated ledger row in ``[start, end)``.

    Read-only Ledger surface consumed by the Interpretation domain
    (SPEC-ITR-001 §6.2 first source, §6.3 classifier). Scoped by ``class_id``
    (multi-tenancy) and the half-open completed-cycle window. Uses the canonical
    ledger anchor (``Transaction.seat_id``) as the acting seat. Never consults
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return set()
    rows = (
        Transaction.query
        .with_entities(Transaction.seat_id)
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            _student_originated_filter(),
        )
        .distinct()
        .all()
    )
    return {row.seat_id for row in rows if row.seat_id is not None}


# --- Interpretation read projections (SPEC-ITR-001 §7, §10) -----------------
#
# Lightweight, read-only row projections consumed by the Interpretation compute
# layer. They carry only the fields Interpretation is permitted to classify on;
# ``Transaction.type`` is deliberately excluded (INV-ITR-015). These surfaces are
# pure reads (INV-ARC-007) exposed by the Ledger domain, which owns the
# provenance of its own rows (INV-ARC-009, INV-ITR-016).


class StudentOriginatedRow(NamedTuple):
    """One student-originated ledger row (§6.3), projected for Q2 aggregation."""

    seat_id: int | None
    amount_cents: int


class InboundLedgerRow(NamedTuple):
    """One inbound-to-seat ledger row, projected for Q5 income-origin classification.

    ``mechanism`` is normalized to its lowercase string value (``self`` /
    ``teacher`` / ``system``) so the interpretation classifier operates on plain
    data rather than an ORM enum.
    """

    transaction_id: int
    seat_id: int | None
    amount_cents: int
    feat_code: str | None
    correlation_id: str | None
    original_transaction_id: int | None
    mechanism: str | None
    account_type: str | None
def _mechanism_value(mechanism) -> str | None:
    """Normalize a stored mechanism (enum member or string) to its lowercase value."""
    if mechanism is None:
        return None
    value = getattr(mechanism, "value", mechanism)
    return str(value).lower()


def get_student_originated_rows(
    class_id: str, window_start, window_end
) -> list[StudentOriginatedRow]:
    """Return student-originated ledger rows (§6.3) in ``[start, end)``.

    Read-only Ledger surface for Q2 (SPEC-ITR-001 §7.3). Applies the same §6.3
    student-originated classifier as :func:`get_seat_ids_with_student_originated_activity`,
    but projects the per-row ``amount_cents`` so Q2-C1 (frequency) and Q2-C2
    (monetary volume) can be computed from a single scoped read. Never consults
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return []
    rows = (
        Transaction.query
        .with_entities(Transaction.seat_id, Transaction.amount_cents)
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            _student_originated_filter(),
        )
        .all()
    )
    return [
        StudentOriginatedRow(seat_id=row.seat_id, amount_cents=int(row.amount_cents or 0))
        for row in rows
    ]


def get_inbound_ledger_rows(
    class_id: str, window_start, window_end
) -> list[InboundLedgerRow]:
    """Return inbound-to-seat (positive-amount), POSTED, non-void ledger rows in ``[start, end)``.

    Read-only Ledger surface for Q5 income composition (SPEC-ITR-001 §10.3). An
    inbound row is a credit to the canonical anchor seat (``amount_cents > 0``;
    the model documents positive amounts as inbound). Classification into the six
    §10.2 origin categories is performed by the Interpretation domain
    (``income_origin``) using the projected provenance fields — never
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return []
    rows = (
        Transaction.query
        .with_entities(
            Transaction.id,
            Transaction.seat_id,
            Transaction.amount_cents,
            Transaction.feat_code,
            Transaction.correlation_id,
            Transaction.original_transaction_id,
            Transaction.mechanism,
            Transaction.account_type,
        )
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            Transaction.amount_cents > 0,
            Transaction.status == TransactionStatus.POSTED,
            Transaction.is_void.isnot(True),
        )
        .all()
    )
    return [
        InboundLedgerRow(
            transaction_id=row.id,
            seat_id=row.seat_id,
            amount_cents=int(row.amount_cents or 0),
            feat_code=row.feat_code,
            correlation_id=row.correlation_id,
            original_transaction_id=row.original_transaction_id,
            mechanism=_mechanism_value(row.mechanism),
            account_type=row.account_type,
        )
        for row in rows
    ]


def get_student_originated_transaction_ids(
    class_id: str, transaction_ids
) -> set[int]:
    """Return the subset of ``transaction_ids`` that are student-originated (§6.3).

    Read-only Ledger surface consumed by the Interpretation domain to decide,
    for obligation ``PAYMENT`` events, whether the *referenced* Ledger row is
    student-originated (SPEC-ITR-001 §8.4/§8.5, Q3-C2). The Ledger domain owns
    the provenance of its own rows (INV-ARC-009, INV-ITR-016): the caller passes
    the ledger ids a PAYMENT event settled and receives back only those that pass
    the §6.3 classifier. This never infers where a seat's *balance* originally
    came from — it classifies the payment row itself, nothing more (§8.5).
    Scoped by ``class_id``; ``Transaction.type`` is never consulted (INV-ITR-015).
    """
    if not class_id or not transaction_ids:
        return set()
    ids = [int(tid) for tid in transaction_ids if tid is not None]
    if not ids:
        return set()
    rows = (
        Transaction.query
        .with_entities(Transaction.id)
        .filter(
            Transaction.class_id == class_id,
            Transaction.id.in_(ids),
            _student_originated_filter(),
        )
        .all()
    )
    return {row.id for row in rows}


def get_posted_balances_as_of(
    class_id: str, as_of, account_type: str
) -> dict[int, Decimal]:
    """Return per-seat POSTED balances for ``account_type`` **as of** ``as_of``.

    Historically-correct end-of-cycle balance surface for the Interpretation
    domain (SPEC-ITR-001 §11.4, §9.4). The balance of a seat at the cycle
    boundary is the sum of its settled (``POSTED``), non-void ledger amounts with
    ``timestamp < as_of`` — the half-open cycle boundary. Restricting to
    ``timestamp < as_of`` is what prevents a later transaction from leaking into
    an earlier cycle's materialized interpretation (INV-ITR-003 reproducibility):
    this is a point-in-time read, never the current cached balance.

    Returns a ``{seat_id: Decimal}`` map for seats that have at least one such
    row; the caller supplies ``0`` for enrolled seats absent from the map.
    Scoped by ``class_id`` (multi-tenancy).
    """
    if not class_id or as_of is None:
        return {}
    rows = (
        db.session.query(
            Transaction.seat_id,
            db.func.sum(Transaction.amount),
        )
        .filter(
            Transaction.class_id == class_id,
            Transaction.account_type == account_type,
            Transaction.timestamp < ensure_utc(as_of),
            Transaction.status == TransactionStatus.POSTED,
            _non_void_filter(),
        )
        .group_by(Transaction.seat_id)
        .all()
    )
    return {
        seat_id: _quantize_currency(total or Decimal("0.00"))
        for seat_id, total in rows
        if seat_id is not None
    }


def get_student_savings_contribution_rows(
    class_id: str, window_start, window_end
) -> list[StudentOriginatedRow]:
    """Return student-originated savings *contribution* rows in ``[start, end)``.

    Read-only Ledger surface for Q4-C2/Q4-C3 (SPEC-ITR-001 §9.4). A savings
    contribution is the *deposit side* of a student-initiated transfer into
    savings: a student-originated (§6.3) row with ``account_type='savings'`` and a
    positive amount (inbound to the savings account, ``DOM-LED-001`` INV-LED-007).
    Both legs of a transfer pair carry ``original_transaction_id IS NULL``, so the
    §6.3 classifier applies to the savings-credit leg directly. Projects
    ``seat_id`` and ``amount_cents``; ``Transaction.type`` is never consulted
    (INV-ITR-015). Scoped by ``class_id`` and the half-open completed-cycle window.
    """
    if not class_id or window_start is None or window_end is None:
        return []
    rows = (
        Transaction.query
        .with_entities(Transaction.seat_id, Transaction.amount_cents)
        .filter(
            Transaction.class_id == class_id,
            Transaction.account_type == "savings",
            Transaction.amount_cents > 0,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            _student_originated_filter(),
        )
        .all()
    )
    return [
        StudentOriginatedRow(seat_id=row.seat_id, amount_cents=int(row.amount_cents or 0))
        for row in rows
    ]



__all__ = ["SYSTEM_ORIGINATED_FEAT_CODES", "get_seat_ids_with_student_originated_activity", "get_student_originated_rows", "get_inbound_ledger_rows", "get_student_originated_transaction_ids", "get_posted_balances_as_of", "get_student_savings_contribution_rows"]
