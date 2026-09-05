from __future__ import annotations

from app.extensions import db
from app.models import ClassEconomy, Issue


def create_support_ticket(*, actor_public_id: str, class_public_id: str, category_id: int, scoped_description: str, expected_behavior: str | None, page_url: str | None) -> Issue:
    """Create and flush a canonical support ticket row."""
    # Freeze the class display name at submission time (DOM-SUP-001 §VI). The
    # label is context, not a live pointer: renaming or destroying the class
    # afterwards must not rewrite or erase the context of an existing ticket.
    class_row = ClassEconomy.query.filter_by(class_public_id=class_public_id).first()

    report = Issue(
        actor_public_id=actor_public_id,
        class_public_id=class_public_id,
        class_label=class_row.display_name if class_row else None,
        category_id=category_id,
        issue_type='general',
        student_explanation=scoped_description,
        student_expected_outcome=expected_behavior if expected_behavior else None,
        page_url=page_url if page_url else None,
        status=Issue.STATUS_OPEN,
    )
    db.session.add(report)
    db.session.flush()
    return report
