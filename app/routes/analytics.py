"""Interpretation page route (DOM-ITR-001, SPEC-ITR-001).

Governing authority: DOM-ITR-001 (Interpretation Domain). As of the 8.4 tranche
this module renders **only** the teacher Interpretation page, fed by the DOM-ITR
read/presentation layer over immutable ``interpretation_cycle_record`` history.
The retired V1 analytics engine — on-demand recompute, local thresholds, generated
alerts, a prescriptive action field, and the per-student drill-down — is gone
(slice 8.4d) and is not imported here.
"""

from flask import Blueprint, request, flash, redirect, url_for, abort

from app.auth import admin_required
from app.services.class_configuration_query_service import (
    get_class_economy,
    verify_teacher_owns_class,
)
from app.services.interpretation.page_view import build_interpretation_page_view
from app.utils.join_code import get_display_join_code
from app.utils.helpers import render_template_with_fallback as render_template

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/admin/interpretation')


def _active_class_option(user_id: int, class_id: str | None):
    """Build the option dict for the single active class, or None.

    Class isolation (INV-ARC-004 V.1): the Interpretation page operates on the one
    active canonical class. Ownership is verified, but the class acted upon comes
    from the request context — never from enumerating the teacher's classes.
    Block/section is display-only (V.2) and is not a scope key.
    """
    if not user_id:
        return None
    resolved_class_id = (class_id or '').strip()
    if not resolved_class_id:
        return None
    class_row = verify_teacher_owns_class(resolved_class_id, user_id)
    if not class_row:
        return None
    return {
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
        'block': (class_row.display_name or '').strip().upper(),
        'label': class_row.display_name or class_row.join_code,
    }


def resolve_current_class_context(user_id: int, class_id: str | None):
    """Resolve the active class context using explicit class_id authority.

    Returns ``(selected, available_classes)`` where ``available_classes`` is capped
    at the single active class. There is no per-feature class switcher: the sole
    legal class switcher is the nav-bar context switcher (INV-ARC-010).
    """
    selected = _active_class_option(user_id, class_id)
    available_classes = [selected] if selected else []
    return selected, available_classes


@analytics_bp.route('/')
@admin_required
def dashboard():
    """Teacher Interpretation page.

    A pure GET (INV-ARC-007): it composes a class-scoped page view model from the
    DOM-ITR read service over immutable cycle records and renders it. It never
    recomputes Interpretation, never reads the retired analytics engine, and
    writes nothing.
    Cycle drill-down (``?cycle=``) is resolved under the active class_id
    (INV-CORE-000) and fails closed for a cycle not belonging to the class.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
        context = resolve_canonical_context()
        user_id = context.user_id
        class_id = context.class_id

        # Resolve the active class directly from canonical class authority.
        class_row = get_class_economy(class_id)
        if not class_row:
            raise ContextResolutionError("Class not found")
        join_code = get_display_join_code(class_row.class_id)
        selected_class, available_classes = resolve_current_class_context(user_id, class_id)
        if not selected_class:
            raise ContextResolutionError("No class context available")
    except Exception:
        flash('You need to set up class periods before viewing Interpretation.', 'warning')
        return redirect(url_for('admin.students'))

    selected_cycle_id = request.args.get('cycle') or None
    page_view = build_interpretation_page_view(class_id, selected_cycle_id=selected_cycle_id)
    if selected_cycle_id and page_view.latest_cycle is None:
        abort(404)

    return render_template(
        'admin_analytics_dashboard.html',
        view=page_view,
        join_code=join_code,
        available_classes=available_classes,
        current_class_label=selected_class['label'],
        current_page='interpretation',
    )
