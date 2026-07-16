from collections import defaultdict
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, tuple_
from app.extensions import db
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus

def _quantize_currency(value):
    """
    Convert a value to Decimal and quantize to 2 decimal places for currency.
    """
    if value is None:
        return Decimal('0.00')
    try:
        if isinstance(value, Decimal):
            if not value.is_finite():
                return Decimal('0.00')
            return value.quantize(Decimal('0.01'))
        else:
            quantized = Decimal(str(value)).quantize(Decimal('0.01'))
            if not quantized.is_finite():
                return Decimal('0.00')
            return quantized
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')


def _empty_balance_dict():
    return {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}


def get_batch_balances_by_class_seat(class_seat_pairs):
    """
    Fetch balances keyed by canonical scope tuple (class_id, seat_id).

    Args:
        class_seat_pairs (iterable): Iterable of (class_id, seat_id) tuples.

    Returns:
        defaultdict: Mapping of (class_id, seat_id) ->
            {'checking_cents': int, 'savings_cents': int, 'earnings': Decimal}
    """
    raw_balances = defaultdict(_empty_balance_dict)

    normalized_pairs = {
        (str(class_id), int(seat_id))
        for class_id, seat_id in (class_seat_pairs or [])
        if class_id and seat_id
    }
    if not normalized_pairs:
        return raw_balances

    class_ids = sorted({class_id for class_id, _ in normalized_pairs})
    seat_ids = sorted({seat_id for _, seat_id in normalized_pairs})
    scope_tuple = tuple_(LedgerBalanceSnapshot.class_id, LedgerBalanceSnapshot.seat_id)
    tx_scope_tuple = tuple_(Transaction.class_id, Transaction.seat_id)

    cache_records = db.session.query(
        LedgerBalanceSnapshot.class_id,
        LedgerBalanceSnapshot.seat_id,
        LedgerBalanceSnapshot.posted_checking_balance_cents,
        LedgerBalanceSnapshot.posted_savings_balance_cents
    ).filter(
        LedgerBalanceSnapshot.class_id.in_(class_ids),
        LedgerBalanceSnapshot.seat_id.in_(seat_ids),
        scope_tuple.in_(list(normalized_pairs)),
    ).all()

    for rec in cache_records:
        key = (str(rec.class_id), int(rec.seat_id))
        raw_balances[key]['checking_cents'] = rec.posted_checking_balance_cents
        raw_balances[key]['savings_cents'] = rec.posted_savings_balance_cents

    pending_sums = db.session.query(
        Transaction.class_id,
        Transaction.seat_id,
        Transaction.account_type,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.class_id.in_(class_ids),
        Transaction.seat_id.in_(seat_ids),
        tx_scope_tuple.in_(list(normalized_pairs)),
        Transaction.status == TransactionStatus.PENDING,
        Transaction.is_void == False
    ).group_by(
        Transaction.class_id,
        Transaction.seat_id,
        Transaction.account_type
    ).all()

    for rec in pending_sums:
        key = (str(rec.class_id), int(rec.seat_id))
        amount_cents = int(_quantize_currency(rec[3]) * 100)
        acct_type = str(rec.account_type).lower()

        if acct_type == 'checking':
            raw_balances[key]['checking_cents'] += amount_cents
        elif acct_type == 'savings':
            raw_balances[key]['savings_cents'] += amount_cents

    earnings_sums = db.session.query(
        Transaction.class_id,
        Transaction.seat_id,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.class_id.in_(class_ids),
        Transaction.seat_id.in_(seat_ids),
        tx_scope_tuple.in_(list(normalized_pairs)),
        Transaction.amount > 0,
        Transaction.is_void == False,
        ~Transaction.description.ilike('Transfer%')
    ).group_by(
        Transaction.class_id,
        Transaction.seat_id
    ).all()

    for rec in earnings_sums:
        key = (str(rec.class_id), int(rec.seat_id))
        raw_balances[key]['earnings'] = _quantize_currency(rec[2])

    return raw_balances


