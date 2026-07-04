"""Helpers for strict seat-scoped queries."""

import sqlalchemy as sa


def transaction_scope_filter(TransactionModel, seat_id: int, seat_ids: list[int] | None = None):
    """Return a strict seat-scoped filter."""
    if seat_ids is not None:
        if seat_ids:
            return sa.and_(TransactionModel.seat_id.in_(seat_ids), TransactionModel.seat_id.is_not(None))
        return sa.false()
    return sa.and_(TransactionModel.seat_id == seat_id, TransactionModel.seat_id.is_not(None))


def seat_scoped_filter(Model, seat_id: int, seat_field: str = "seat_id"):
    """Return a strict seat-scoped filter for models that carry seat references."""
    seat_col = getattr(Model, seat_field)
    return sa.and_(seat_col == seat_id, seat_col.is_not(None))
