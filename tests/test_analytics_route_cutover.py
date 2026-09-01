"""Slice 8.4b — Interpretation page authority cutover (route → DOM-ITR).

8.4b answers only "who owns the data feeding this page?": the dashboard route now
composes ITR read/presentation models over immutable cycle records and no longer
touches AnalyticsEngine. No visual redesign (the legacy template renders confused
but 200 until 8.4c). Acceptance:

* a class with history → latest frozen cycle + ordered history (page view);
* a class without history → first-class empty state, renders 200;
* a cycle requested from another class → fails closed (404);
* GET is pure — viewing materializes/recomputes nothing (INV-ARC-007);
* the dashboard route invokes no AnalyticsEngine / snapshot / alert generation.
"""

from __future__ import annotations

import ast
import inspect
from datetime import timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import InterpretationCycleRecord
from app.services.interpretation.page_view import (
    STATE_AWAITING_FIRST_CYCLE,
    STATE_HAS_HISTORY,
    build_interpretation_page_view,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

_REF = {"schema_version": 1, "economic_engine": {}, "policy": {}}


def _put_record(cid, cycle_id, *, completed_at=None):
    now = utc_now()
    with FEATContext("FEAT-PROD-004", idempotency_key=f"rec:{cid}:{cycle_id}"):
        db.session.add(InterpretationCycleRecord(
            class_id=cid, payroll_cycle_id=cycle_id,
            cycle_started_at=now - timedelta(hours=1),
            cycle_completed_at=completed_at or now, computed_at=now,
            reference_configuration=_REF,
            observations_json={"schema_version": 1, "observations": []},
        ))
        db.session.flush()


# --------------------------------------------------------------------------- #
# Page view composition (class-scoped, empty-state, drill-down)               #
# --------------------------------------------------------------------------- #


def test_page_view_has_latest_and_ordered_history(app):
    cid = initialize("chemistry_p1", app).class_id
    now = utc_now()
    _put_record(cid, "old", completed_at=now - timedelta(days=2))
    _put_record(cid, "new", completed_at=now)

    view = build_interpretation_page_view(cid)
    assert view.state == STATE_HAS_HISTORY
    assert view.latest_cycle.cycle.payroll_cycle_id == "new"
    assert [s.payroll_cycle_id for s in view.history] == ["new", "old"]
    assert view.selected_cycle_id == "new"


def test_page_view_empty_history_is_first_class_state(app):
    cid = initialize("chemistry_p1", app).class_id
    view = build_interpretation_page_view(cid)
    assert view.state == STATE_AWAITING_FIRST_CYCLE
    assert view.latest_cycle is None
    assert view.history == ()
    assert view.selected_cycle_id is None


def test_page_view_cycle_selection_is_class_scoped(app):
    class_a = initialize("chemistry_p1", app).class_id
    class_b = initialize("chemistry_p1", app).class_id
    _put_record(class_a, "a-cycle")

    # Selecting class A's cycle under class B resolves to nothing (fail-closed).
    view = build_interpretation_page_view(class_b, selected_cycle_id="a-cycle")
    assert view.latest_cycle is None


# --------------------------------------------------------------------------- #
# HTTP route behavior                                                         #
# --------------------------------------------------------------------------- #


def test_dashboard_renders_with_history(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    _put_record(classroom.class_id, "cycle-1")

    response = client.get("/admin/interpretation/")
    assert response.status_code == 200


def test_dashboard_renders_empty_state(client):
    app = client.application
    initialize_as_teacher("chemistry_p1", client, app)  # no cycle records
    response = client.get("/admin/interpretation/")
    assert response.status_code == 200


def test_dashboard_unknown_cycle_fails_closed(client):
    # A cycle id not present under the active class (which is exactly how another
    # class's cycle looks from this class's scope) fails closed. True cross-class
    # isolation is covered by test_page_view_cycle_selection_is_class_scoped.
    app = client.application
    initialize_as_teacher("chemistry_p1", client, app)

    assert client.get("/admin/interpretation/?cycle=not-in-this-class").status_code == 404
    # The class's own (absent) selection still renders the empty state.
    assert client.get("/admin/interpretation/").status_code == 200


def test_dashboard_get_is_pure_no_writes(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = classroom.class_id

    before = InterpretationCycleRecord.query.filter_by(class_id=cid).count()
    assert client.get("/admin/interpretation/").status_code == 200
    after = InterpretationCycleRecord.query.filter_by(class_id=cid).count()
    assert after == before == 0  # viewing materializes nothing


# --------------------------------------------------------------------------- #
# Authority: the dashboard route no longer invokes AnalyticsEngine            #
# --------------------------------------------------------------------------- #


def test_dashboard_route_invokes_no_analytics_engine():
    import app.routes.analytics as analytics_module

    source = inspect.getsource(analytics_module)
    tree = ast.parse(source)
    dashboard_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "dashboard"
    )
    # Collect actual code identifiers referenced in the function (names +
    # attribute accesses) — comments/docstrings are not in the AST, so prose
    # mentioning these terms never triggers a false positive.
    referenced: set[str] = set()
    for node in ast.walk(dashboard_fn):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    for forbidden in (
        "AnalyticsEngine", "get_or_create_snapshot", "create_snapshot",
        "get_snapshot_read_only", "generate_alerts", "build_analytics_dashboard_view",
    ):
        assert forbidden not in referenced, forbidden
