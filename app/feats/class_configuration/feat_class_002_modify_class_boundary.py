"""
FEAT-CLASS-002: Modify Class Boundary (v1.0)

Handles the destruction/modification of the class boundary itself.
Modifications to the roster (seats and identity profiles) have been moved to FEAT-IDEN-002.
"""

from __future__ import annotations
from app.feats.base import requires_feat_context
from app.services.context_resolver import CanonicalContext

@requires_feat_context("FEAT-CLASS-002")
def execute_delete_class_boundary(
    class_id: int, 
    canonical_context: CanonicalContext, 
    correlation_id: str | None = None, 
    idempotency_key: str | None = None
) -> bool:
    """
    Hard-delete a class economy and all records scoped to the class.
    """
    from app.routes.admin import _hard_delete_class_scope
    from app.models import Seat
    from app.extensions import db

    _hard_delete_class_scope(class_id, canonical_context)

    # Clean up pending students left hanging
    Seat.query.filter(
        Seat.class_id == class_id,
        Seat.claimed_at.is_(None),
    ).delete(synchronize_session=False)
    
    return True
