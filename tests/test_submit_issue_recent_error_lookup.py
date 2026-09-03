"""Regression: the student "Report an Issue" page must not 500.

The support page calls ``has_recent_error_for_actor`` to decide whether to
offer the "attach my recent error" option. That helper (and the ticket
correlation pack) used to query the tamper-evident ``audit_events`` chain ORM
model (``AuditEvent``), which has no ``actor_public_id``/``created_at``
correlation columns — so ``GET /student/help-support/submit-issue`` raised
``AttributeError: type object 'AuditEvent' has no attribute 'actor_public_id'``
and returned a 500.

The correlation surface reads from the ``error_events`` log via guarded raw
SQL and degrades to "no recent error" when that table is absent (it was dropped
by migration 7c3d4e5f6a7b pending operational_events). This must never touch the
audit chain.
"""

from __future__ import annotations

from app.services.tlcp import (
    create_ticket_correlation_pack,
    has_recent_error_for_actor,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize_as_student


def test_submit_issue_page_renders_without_audit_chain_error(client, app):
    """GET the general-issue page: 200, never a 500 from the error lookup."""
    initialize_as_student("chemistry_p1", client, app)

    resp = client.get("/student/help-support/submit-issue", follow_redirects=False)
    assert resp.status_code == 200


def test_has_recent_error_degrades_to_false_when_table_absent(client, app):
    """With error_events absent, the recent-error probe returns False, not raise."""
    with app.app_context():
        assert has_recent_error_for_actor("student", "seat_public_abc123") is False


def test_correlation_pack_yields_empty_errors_when_table_absent(client, app):
    """The correlation pack still builds; error refs degrade to [] cleanly."""
    with app.app_context():
        pack = create_ticket_correlation_pack(
            issue_id=1,
            actor_type="student",
            actor_public_id="seat_public_abc123",
            class_id=None,
            ticket_created_at=utc_now(),
            include_recent_error=True,
        )
        assert pack["error_refs_json"] == []
        assert pack["correlation_version"] == 1
