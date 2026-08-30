"""Regression: the analytics economy-event timeline must not crash.

The `/admin/analytics/events` route previously queried ``AuditEvent`` (the
tamper-evident integrity chain) and rendered those rows through a template that
accessed economy-event fields the audit row does not have (``old_value``,
``new_value``, ``event_type``, ...), raising ``UndefinedError`` → HTTP 500
whenever the class had any audit rows.

The economy-event timeline (rent/wage/inflation "contextual annotations") is a
DOM-ITR-001 capability that is NOT IMPLEMENTED in v2 (§XIII.a). Until an
Interpretation annotation surface is specified, the page presents its graceful
empty state instead of fabricating events from the integrity chain.
"""

from __future__ import annotations

from tests.helpers.classroom_initializer import initialize_as_teacher


def test_events_route_renders_empty_state_without_crashing(client, app):
    """The route must render (200) and show its empty state. Previously it passed
    AuditEvent rows to a template expecting economy-event fields (old_value, ...),
    raising UndefinedError → 500. The fix stops feeding the integrity chain to
    this Interpretation surface, which is NOT IMPLEMENTED (DOM-ITR-001 §XIII.a)."""
    initialize_as_teacher("chemistry_p1", client, app)

    resp = client.get("/admin/analytics/events")

    assert resp.status_code == 200
    assert b"No events recorded yet" in resp.data
