"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import re
import secrets
import pytz
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from flask import Blueprint, request, jsonify, session, current_app, g
from sqlalchemy import func, or_
import sqlalchemy as sa
from sqlalchemy.orm import aliased
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models import (
    StoreItem, Transaction, TransactionStatus, AttendanceSession,
    AttendanceReasonCode, HallPassLog, HallPassSettings, BankingSettings,
    # Legacy tap models are unauthorized; use attendance_sessions (DOM-PROD-001).
    # StoreItemBlock removed — store_item_blocks unauthorized; use store_item_visibility (DOM-STORE-001)
    StoreItemVisibility, User,
    _quantize_currency,
    ClassEconomy, Seat, IdentityProfile, PayrollEvent,
)
from app.auth import (
    login_required,
    admin_required,
    get_current_seat,

    get_current_user,
    get_current_class_id,
    SESSION_TIMEOUT_MINUTES,
)
from app.access import AccessScopeDenied, resolve_scope
from app.services.context_resolver import ContextResolutionError, resolve_canonical_context
from app.feats.base import feat_shell
from app.feats.attendance import (
    rotate_teacher_hall_pass_verify_token as feat_rotate_teacher_hall_pass_verify_token,
    save_hall_pass_setup_config as feat_save_hall_pass_setup_config,
    update_hall_pass_queue_settings as feat_update_hall_pass_queue_settings,
    _get_or_create_hall_pass_settings as feat_get_or_create_hall_pass_settings,
)
from app.feats.prod import record_attendance_session, record_hall_pass_log
from app.routes.student import (
    get_feature_settings_for_student,
    get_rent_settings_for_context,
    _calculate_rent_coverage_due_date,
    _is_student_coverage_period_paid,
    _ensure_rent_hall_pass_top_off,
)
from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
# TODO (Phase 4): get_active_rent_grant, get_purchase_count commented out (deleted service functions)
# from app.services.store_service import get_active_rent_grant, get_purchase_count
# TODO (Phase 4): store_entitlement_service deleted; use EntitlementEvent queries
# from app.services.store_entitlement_service import consume_entitlement, list_entitlement_history, derive_display_status
# TODO (Phase 4): redemption_disposition_feat deleted; use FEAT-STOR-002 instead
# from app.feats.redemption_disposition_feat import (
#     RedemptionDispositionError,
#     execute_redemption_approval,
#     execute_redemption_rejection,
#     record_live_redemption_event,
# )
from app.services import store_service
from app.services.entitlement_read_service import get_purchase_count, get_active_rent_grant
from app.services.entitlement_service import get_hall_pass_balance, grant_hall_passes
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    clear_pending_hall_pass_requests_for_seat,
    enqueue_hall_pass_request,
    get_pending_hall_pass_request,
    pop_pending_hall_pass_request,
)
from app.utils.economy_policy import resolve_class_scope, resolve_feature_class, resolve_feature_class_for_class
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
from app.utils.join_code import get_display_join_code
from app.utils.transaction_idempotency import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    get_idempotent_transaction,
    purchase_transaction_key,
)
from app.utils.time import (
    utc_now,
    ensure_utc,
    get_timezone,
    UTC_MIN,
)

# Import external modules
from app.services.attendance_service import calculate_unpaid_attendance_seconds, get_class_attendance_status
from app.services.ledger_service import (
    create_pending_transaction,
    create_pending_transaction_idempotent,
    get_available_balances,
    get_last_payroll_time,
)
from app.payroll import get_pay_rate_for_block

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


def _log_api_client_error(route_name, exc, *, extra=None):
    current_app.logger.info(
        "API client error on %s: %s%s",
        route_name,
        exc.__class__.__name__,
        f" ({extra})" if extra else "",
    )


def _safe_exception_prefix_message(exc, default_message, *, allowed_prefixes=None):
    message = str(exc)
    if allowed_prefixes:
        for allowed_prefix in allowed_prefixes:
            if message.startswith(allowed_prefix):
                return allowed_prefix
    return default_message

@api_bp.errorhandler(ContextResolutionError)
def handle_api_context_resolution_error(e):
    from app.services.context_resolver import ContextForbidden, ContextMismatch
    if isinstance(e, (ContextForbidden, ContextMismatch)):
        return jsonify({"status": "error", "message": "Not Found", "error": "Not Found"}), 404
    return jsonify({"status": "error", "message": "Class context required", "error": "Class context required"}), 401



# -------------------- Rent Helpers --------------------




def _get_period_delta(rent_setting):
    """Return the timedelta/relativedelta for a rent setting."""
    if rent_setting.frequency_type == 'daily':
        return timedelta(days=1)
    if rent_setting.frequency_type == 'weekly':
        return timedelta(weeks=1)
    if rent_setting.frequency_type == 'monthly':
        return relativedelta(months=1)
    if rent_setting.frequency_type == 'custom':
        unit = rent_setting.custom_frequency_unit or 'days'
        value = rent_setting.custom_frequency_value or 1
        if unit == 'days':
            return timedelta(days=value)
        if unit == 'weeks':
            return timedelta(weeks=value)
        if unit == 'months':
            return relativedelta(months=value)
    return timedelta(days=30)


def _add_period(dt, delta):
    """Add a timedelta or relativedelta to dt."""
    return dt + delta


def _calculate_due_dates(rent_setting, now):
    """
    Calculate the current and next due dates for a rent setting based on the provided time.
    Returns (current_due, next_due). If first due date is not set, returns (None, None).
    """
    first_due = ensure_utc(rent_setting.first_rent_due_date)
    if not first_due:
        return (None, None)

    delta = _get_period_delta(rent_setting)

    # If before the first due date, the first due date is both current and next marker
    if now < first_due:
        return (first_due, _add_period(first_due, delta))

    current_due = first_due
    next_due = _add_period(first_due, delta)

    # Advance until next_due is after now
    while next_due and next_due <= now:
        current_due = next_due
        next_due = _add_period(next_due, delta)

    return (current_due, next_due)


def _resolve_class_display_label(class_id, fallback_block=None):
    """
    Resolve a stable class display label snapshot for audit logging.
    """
    if class_id:
        class_economy = ClassEconomy.query.filter_by(class_id=class_id).first()
        if class_economy:
            return class_economy.display_name or get_display_join_code(class_id)

    return fallback_block or "Unknown Class"


def _append_redemption_audit_log(*, entitlement, student, user_id, action, notes, guard_state, fallback_block=None):
    """Append exactly one live redemption event row for this request path."""
    if guard_state.get('inserted'):
        raise RuntimeError("Duplicate redemption audit insertion attempt in single request path")

    action_map = {
        'REQUEST': RedemptionEventAction.REQUEST,
        'APPROVED': RedemptionEventAction.APPROVED,
        'REJECTED': RedemptionEventAction.REJECTED,
    }
    if action not in action_map:
        raise ValueError(f"Unsupported redemption audit action: {action}")

    class_id = entitlement.class_id
    class_label = _resolve_class_display_label(class_id, fallback_block=fallback_block)

    # Derive student display name from IdentityProfile (v2 canonical).
    from app.models import IdentityProfile
    seat_id_val = entitlement.target_seat_id
    identity = IdentityProfile.query.filter_by(seat_id=seat_id_val).first() if seat_id_val else None
    if identity:
        try:
            first = identity.first_name or ''
            last = identity.last_name or ''
            student_display_name = f"{first} {last}".strip() or 'Unknown'
        except Exception:
            student_display_name = 'Unknown'
    else:
        student_display_name = 'Unknown'

    record_live_redemption_event(
        entitlement_id=entitlement.entitlement_id,
        seat_id=entitlement.target_seat_id,
        class_id=class_id,
        action=action_map[action],
        initiated_by_user_id=user_id,
        seat_display_name=student_display_name,
        class_display_label=class_label,
        notes=notes if notes else None,
    )
    guard_state['inserted'] = True


def _get_hall_pass_settings_scope(class_id):
    """Resolve canonical class scope for hall pass settings."""
    return resolve_class_scope(None, class_id=class_id)


def _get_or_create_hall_pass_settings(class_id):
    """Return the hall pass settings row for a specific class, creating it if needed."""
    return feat_get_or_create_hall_pass_settings(class_id=class_id)


def _get_teacher_class_scope(canonical_context):
    """Return (class_id_scope_subquery, has_class_scope) for a canonical teacher context."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return None, False

    user_id = canonical_context.user_id
    class_id_scope = (
        db.session.query(Seat.class_id)
        .filter(
            Seat.user_id == user_id,
            Seat.role == 'teacher',
            Seat.class_id.isnot(None),
        )
        .distinct()
        .subquery()
    )
    has_class_scope = db.session.query(
        sa.exists().where(
            sa.and_(
                Seat.user_id == user_id,
                Seat.role == 'teacher',
                Seat.class_id.isnot(None),
            )
        )
    ).scalar()
    return class_id_scope, has_class_scope


def _admin_has_class_scope(canonical_context, class_id):
    """Return True when admin owns the class_id via active admin membership."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not class_id:
        return False

    user_id = canonical_context.user_id
    return db.session.query(
        sa.exists().where(
            sa.and_(
                Seat.user_id == user_id,
                Seat.class_id == class_id,
                Seat.role == 'teacher',
            )
        )
    ).scalar()


def _apply_admin_class_scope(query, model, canonical_context):
    """Apply class_id tenant scoping. In V2, class_id is the primary anchor."""
    class_id_scope, has_class_scope = _get_teacher_class_scope(canonical_context)
    if has_class_scope:
        return query.filter(
            model.class_id.isnot(None),
            model.class_id.in_(sa.select(class_id_scope)),
        )
    return query


# -------------------- TIPS API --------------------

@api_bp.route('/tips/<user_type>')
@limiter.exempt
def get_tips(user_type):
    """
    Return tips for login loading screens as JSON.

    Endpoint: GET /api/tips/<user_type>
    User types: 'student' or 'teacher'

    Exempt from rate limiting because it's called on every login page load.
    """
    if user_type == 'student':
        tips = [
            "You don't have to stay logged in after starting work. You'll continue to earn minutes even when you're away from the page.",
            "Check your balance regularly to track your earnings and plan your spending wisely.",
            "Your teacher can award bonus tokens for exceptional work or good behavior.",
            "Remember to log your attendance every day to earn your payroll minutes.",
            "The shop refreshes with new items regularly - check back often for deals!",
            "Save up for big purchases by setting financial goals for yourself.",
            "Hall passes deduct from your balance - plan your breaks wisely.",
            "Insurance can protect your balance from unexpected classroom events.",
            "Ask your teacher about bonus opportunities to earn extra tokens.",
            "Keep track of your transaction history to understand your spending habits."
        ]
    elif user_type == 'teacher':
        tips = [
            "Students don't have to stay logged in after starting work. They'll continue to earn minutes even when away from the page.",
            "Use the bulk transaction feature to quickly award or deduct tokens from multiple students.",
            "Set up automated payroll to save time on manual attendance tracking.",
            "The analytics dashboard shows spending trends to help you understand student behavior.",
            "Create custom store items to incentivize specific behaviors or achievements.",
            "Use insurance policies to teach students about risk management and financial protection.",
            "Rent settings can simulate monthly expenses to teach budgeting skills.",
            "Check the transaction log regularly to monitor unusual spending patterns.",
            "Bonus tokens are a great way to reward exceptional effort or good citizenship.",
            "Export your class data regularly for backup and analysis purposes."
        ]
    else:
        return jsonify({"error": "Invalid user type. Use 'student' or 'teacher'."}), 400

    return jsonify({"tips": tips})


# -------------------- STORE API --------------------

@api_bp.route('/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    """
    Purchase an item from the store.

    Wired to FEAT-STOR-001 (Store Purchase and Entitlement Grant).
    Creates EntitlementEvent(s) for purchased quantity.
    """
    # 1. Resolve context and verify actor
    try:
        context = resolve_canonical_context()
    except ContextResolutionError:
        return jsonify({"status": "error", "message": "No class context available."}), 400

    if not context or not context.seat_id:
        return jsonify({"status": "error", "message": "No seat assigned in this class."}), 403

    user = db.session.get(User, context.user_id)
    if not user:
        return jsonify({"status": "error", "message": "Actor not found."}), 403

    # 2. Parse and validate input
    data = request.get_json(silent=True) or {}
    policy_uuid = data.get('policy_uuid')
    passphrase = data.get('passphrase')

    try:
        quantity = int(data.get('quantity', 1))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Quantity must be a whole number."}), 400

    if not policy_uuid or not passphrase:
        return jsonify({"status": "error", "message": "Missing policy UUID or passphrase."}), 400

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1."}), 400

    # 3. Verify passphrase
    if not check_password_hash(user.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 4. Call FEAT-STOR-001: Create entitlement grants via purchase
    result = execute_store_purchase(
        canonical_context=context,
        policy_uuid=policy_uuid,
        quantity=quantity,
        instant_use=False,  # TODO: Read from product policy
    )

    if not result.success:
        error_msg = result.error_message or f"Purchase failed: {result.error_code}"
        return jsonify({"status": "error", "message": error_msg}), 400

    return jsonify({
        "status": "success",
        "message": f"Purchase successful! Quantity: {quantity}",
        "correlation_id": result.correlation_id,
    })


@api_bp.route('/use-item', methods=['POST'])
@login_required
@feat_shell("FEAT-STOR-002")
def use_item():
    context = getattr(g, "canonical_context", None)
    if not context:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    user = db.session.get(User, context.user_id)
    student = db.session.get(Seat, context.seat_id)
    student_id = student.id if student else None
    
    if not user or not student:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json()
    entitlement_id = data.get('entitlement_id')
    passphrase = data.get('passphrase')
    details = data.get('redemption_details', data.get('details', ''))  # optional notes from student

    if not all([entitlement_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing entitlement ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(user.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 2. Get the entitlement
    entitlement = Entitlement.query.filter_by(entitlement_id=entitlement_id).first()

    if not entitlement or entitlement.target_seat_id != student.id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Check availability via canonical display status
    display_status = derive_display_status(entitlement.entitlement_id)
    if display_status not in ('purchased', 'processing'):
        return jsonify({"status": "error", "message": "This item is not available for redemption."}), 400

    store_item = db.session.get(StoreItem, entitlement.entitlement_item_id)
    if not store_item:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Special handling for hall_pass items in inventory (bundle or standalone)
    if store_item.item_type == 'hall_pass':
        qty = 1
        # Try to get quantity from the bridge StorePurchase if it exists
        bridge_purchase = StorePurchase.query.filter_by(
            seat_id=entitlement.target_seat_id,
            store_item_id=entitlement.entitlement_item_id,
            class_id=entitlement.class_id,
        ).first()
        if bridge_purchase and bridge_purchase.quantity:
            qty = bridge_purchase.quantity
        grant_hall_passes(student, qty, trigger_id=f"inventory_redeem_{entitlement.entitlement_id}")
        consume_entitlement(
            entitlement_id=entitlement.entitlement_id,
            class_id=entitlement.class_id,
            target_seat_id=student.id,
            actor_seat_id=student.id,
            correlation_id=f"inventory_redeem_{entitlement.entitlement_id}",
        )
        return jsonify({"status": "success", "message": f"Added {qty} hall pass(es) to your balance!"})

    # Delayed items remain request-based in the canonical model.
    if display_status not in ('purchased',):
        return jsonify({"status": "error", "message": "This item is not available for redemption."}), 400

    # Get context up front for audit snapshots and transaction scoping.
    try:
        context = resolve_canonical_context()
    except ContextResolutionError:
        context = None
    # Resolve class owner (teacher) user_id from class_id via canonical ClassEconomy lookup
    _class_id_for_audit = context.class_id if context else entitlement.class_id
    _ce = ClassEconomy.query.filter_by(class_id=_class_id_for_audit).first() if _class_id_for_audit else None
    user_id_for_audit = _ce.user_id if _ce else None
    fallback_block = None


    # 3. Record the redemption request and create the audit transaction.
    try:
        audit_guard = {'inserted': False}
        _append_redemption_audit_log(
            entitlement=entitlement,
            student=student,
            user_id=user_id_for_audit,
            action='REQUEST',
            notes=details,
            guard_state=audit_guard,
            fallback_block=fallback_block,
        )

        # FEAT wrapper owns commit/rollback boundaries; keep mutations in the open transaction.
        return jsonify({"status": "success", "message": f"You have requested to use {store_item.name}. Awaiting admin approval."})

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.session.rollback()
        current_app.logger.error(f"Item use failed for student {student_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred. Please try again."}), 500


@api_bp.route('/approve-redemption', methods=['POST'])
@admin_required
@feat_shell("FEAT-STOR-002")
def approve_redemption():
    """
    Approve a pending redemption request.

    Validation and scope checks run as pure reads in the route body; the actual
    state mutation is delegated to FEAT-STOR-002. The FEAT shell owns the
    transaction boundary — any exception raised below this point (other than
    the explicitly caught RedemptionDispositionError business error) will
    trigger a rollback at the shell. Infrastructure errors are NOT swallowed
    here; they propagate to Flask's error handler.
    """
    data = request.get_json(silent=True) or {}
    entitlement_id = data.get('entitlement_id')

    if not entitlement_id:
        return jsonify({"status": "error", "message": "Missing entitlement ID."}), 400

    entitlement = Entitlement.query.filter_by(entitlement_id=entitlement_id).first()
    if not entitlement:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Verify an unresolved REQUEST exists (no APPROVED/REJECTED follow-up)
    display_status = derive_display_status(entitlement.entitlement_id)
    if display_status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    user_id = g.canonical_context.user_id

    has_membership = _admin_has_class_scope(g.canonical_context, entitlement.class_id)
    if not has_membership:
        return jsonify({"status": "error", "message": "You do not have access to this class."}), 403

    store_item = db.session.get(StoreItem, entitlement.entitlement_item_id)
    if not store_item or not store_item.class_id or store_item.class_id != entitlement.class_id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    if not _admin_has_class_scope(g.canonical_context, store_item.class_id):
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        result = execute_redemption_approval(
            entitlement=entitlement,
            actor_user_id=user_id,
            notes=None,
        )
    except RedemptionDispositionError as e:
        current_app.logger.info(
            "Redemption approval rejected by FEAT for entitlement %s: %s",
            entitlement_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": "Redemption request is no longer pending and cannot be approved.",
        }), 409

    return jsonify({"status": "success", "message": result.message})


@api_bp.route('/reject-redemption', methods=['POST'])
@admin_required
@feat_shell("FEAT-STOR-002")
def reject_redemption():
    """Reject a pending redemption request without terminating the entitlement."""
    data = request.get_json(silent=True) or {}
    entitlement_id = data.get('entitlement_id')

    if not entitlement_id:
        return jsonify({"status": "error", "message": "Missing entitlement ID."}), 400

    entitlement = Entitlement.query.filter_by(entitlement_id=entitlement_id).first()
    if not entitlement:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Verify an unresolved REQUEST exists
    display_status = derive_display_status(entitlement.entitlement_id)
    if display_status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    # SECURITY: Verify the current admin has class scope for this store item
    user_id = g.canonical_context.user_id
    store_item = db.session.get(StoreItem, entitlement.entitlement_item_id)
    if not store_item or not store_item.class_id or store_item.class_id != entitlement.class_id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    if not _admin_has_class_scope(g.canonical_context, store_item.class_id):
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        result = execute_redemption_rejection(
            entitlement=entitlement,
            actor_user_id=user_id,
            notes=None,
        )
    except RedemptionDispositionError as e:
        current_app.logger.info(
            "Redemption rejection refused by FEAT for entitlement %s: %s",
            entitlement_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": "Redemption request could not be rejected in its current state.",
        }), 409

    return jsonify({"status": "success", "message": result.message})


# -------------------- HALL PASS API --------------------

@api_bp.route('/hall-pass/request', methods=['POST'])
@login_required
def request_hall_pass():
    """Create an ephemeral hall-pass request for teacher approval."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    if not context or not student or student.class_id != context.class_id:
        return jsonify({"status": "error", "message": "Student class context is required."}), 403

    data = request.get_json(silent=True) or {}
    destination = (data.get("destination") or data.get("reason") or "Bathroom").strip()
    if not destination:
        return jsonify({"status": "error", "message": "Destination is required."}), 400

    if get_hall_pass_balance(student.id, context.class_id) <= 0:
        return jsonify({"status": "error", "message": "No hall passes available."}), 403

    latest_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=student.id,
            class_id=context.class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    if not latest_event or latest_event.status != "active":
        return jsonify({"status": "error", "message": "Start work before requesting a hall pass."}), 400

    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="current_time",
    )
    request_id = secrets.token_urlsafe(18)
    clear_pending_hall_pass_requests_for_seat(
        class_id=context.class_id,
        seat_id=student.id,
    )
    pending_request = enqueue_hall_pass_request(
        PendingHallPassRequest(
            request_id=request_id,
            class_id=context.class_id,
            requested_by_seat_id=student.id,
            destination=destination,
            requested_at_utc=evaluation.canonical_now_utc,
        )
    )
    return jsonify({
        "status": "success",
        "message": "Hall pass request sent.",
        "hall_pass": {
            "id": pending_request.request_id,
            "status": "pending",
            "reason": pending_request.destination,
        },
    })


@api_bp.route('/hall-pass/request/<request_id>/cancel', methods=['POST'])
@login_required
def cancel_pending_hall_pass_request(request_id):
    """Cancel the current student's ephemeral pending hall-pass request."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    pending_request = get_pending_hall_pass_request(request_id)
    if (
        not context
        or not student
        or not pending_request
        or pending_request.class_id != context.class_id
        or pending_request.requested_by_seat_id != student.id
    ):
        return jsonify({"status": "error", "message": "Pending request not found."}), 404

    pop_pending_hall_pass_request(request_id)
    return jsonify({"status": "success", "message": "Hall pass request cancelled."})


@api_bp.route('/hall-pass/request/<request_id>/<string:action>', methods=['POST'])
@admin_required
def handle_pending_hall_pass_request(request_id, action):
    """Approve or reject an ephemeral hall-pass request."""
    ctx = g.canonical_context
    pending_request = get_pending_hall_pass_request(request_id)
    if not pending_request or pending_request.class_id != ctx.class_id:
        return jsonify({"status": "error", "message": "Pending request not found."}), 404

    if action == "reject":
        pop_pending_hall_pass_request(request_id)
        return jsonify({"status": "success", "message": "Hall pass request rejected."})

    if action != "approve":
        return jsonify({"status": "error", "message": "Unsupported hall pass action."}), 400

    requested_seat = db.session.get(Seat, pending_request.requested_by_seat_id)
    if not requested_seat or requested_seat.class_id != ctx.class_id:
        return jsonify({"status": "error", "message": "Pending request not found."}), 404

    try:
        record_hall_pass_log(
            ctx=ctx,
            requested_by_seat_id=requested_seat.id,
            approved_by_seat_id=ctx.seat_id,
            destination=pending_request.destination,
            reason="teacher_approved",
            idempotency_key=f"hall_pass_approve:{ctx.class_id}:{request_id}",
        )
        db.session.commit()
        pop_pending_hall_pass_request(request_id)
        return jsonify({"status": "success", "message": "Hall pass issued."})
    except ValueError as exc:
        db.session.rollback()
        _log_api_client_error("handle_pending_hall_pass_request", exc, extra=f"request_id={request_id}")
        return jsonify({"status": "error", "message": "Hall pass request cannot be approved."}), 400
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Hall pass approval failed: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
def handle_hall_pass_action(pass_id, action):
    log_entry = db.get_or_404(HallPassLog, pass_id)
    ctx = g.canonical_context
    if not log_entry.class_id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404
    if ctx.class_id != log_entry.class_id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404

    try:
        if action == 'leave':
            latest_event = (
                AttendanceSession.query.filter_by(
                    target_seat_id=log_entry.requested_by_seat_id,
                    class_id=log_entry.class_id,
                )
                .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
                .first()
            )
            if latest_event and latest_event.status == "inactive" and latest_event.reason_code == AttendanceReasonCode.HALL_PASS.value:
                return jsonify({"status": "success", "message": "Student is already marked out."})
            record_attendance_session(
                ctx=ctx,
                target_seat_id=log_entry.requested_by_seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="inactive",
                reason=log_entry.destination,
                reason_code=AttendanceReasonCode.HALL_PASS,
                hall_pass_id=log_entry.hall_pass_id,
                idempotency_key=f"hall_pass_leave:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
            )
            return jsonify({"status": "success", "message": "Student has left the class."})
        if action == 'return':
            latest_event = (
                AttendanceSession.query.filter_by(
                    target_seat_id=log_entry.requested_by_seat_id,
                    class_id=log_entry.class_id,
                )
                .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
                .first()
            )
            if latest_event and latest_event.status == "active":
                return jsonify({"status": "success", "message": "Student is already marked returned."})
            record_attendance_session(
                ctx=ctx,
                target_seat_id=log_entry.requested_by_seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="active",
                reason="Return from hall pass",
                hall_pass_id=log_entry.hall_pass_id,
                idempotency_key=f"hall_pass_return:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
            )
            return jsonify({"status": "success", "message": "Student has returned."})
    except ValueError as exc:
        _log_api_client_error("handle_hall_pass_action", exc, extra=f"action={action}")
        safe_messages = {
            "leave": "Hall pass cannot be checked out in its current state.",
            "return": "Hall pass cannot be checked in in its current state.",
        }
        return jsonify({"status": "error", "message": safe_messages.get(action, "Invalid action.")}), 400

    return jsonify({"status": "error", "message": "Invalid action."}), 400



def _get_default_timezone():
    """Return the configured default timezone or fall back to Pacific Time."""
    return get_timezone(current_app.config.get('DEFAULT_TIMEZONE'))


def _enforce_hall_pass_student_context(student, log_entry):
    """
    Enforce active student class context for hall-pass state mutations.

    Class context is required and must match the pass class/join scope.
    """
    context = resolve_canonical_context()
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({
            "status": "error",
            "message": "This pass belongs to a different class context. Switch class and retry.",
        }), 403

    if current_class_id and log_entry.class_id and log_entry.class_id != current_class_id:
        return jsonify({
            "status": "error",
            "message": "This pass belongs to a different class context. Switch class and retry.",
        }), 403

    return None




@api_bp.route('/hall-pass/checkout', methods=['POST'])
@login_required
def checkout_hall_pass():
    """Append an inactive attendance row for an issued hall pass."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKOUT_DEBUG: seat_id=%s pass_id=%s pass_requested_by_seat_id=%s pass_class_id=%s session_class_id=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.requested_by_seat_id,
        log_entry.class_id,
        getattr(getattr(g, "canonical_context", None), "class_id", None),
    )
    
    if not student or log_entry.requested_by_seat_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error

    try:
        latest_event = (
            AttendanceSession.query.filter_by(
                target_seat_id=student.id,
                class_id=log_entry.class_id,
            )
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        if latest_event and latest_event.status == "inactive" and latest_event.reason_code == AttendanceReasonCode.HALL_PASS.value:
            return jsonify({
                "status": "success",
                "message": "You are already checked out.",
                "destination": log_entry.destination,
            })

        record_attendance_session(
            ctx=context,
            target_seat_id=student.id,
            actor_seat_id=context.seat_id,
            mechanism="self",
            status="inactive",
            reason=log_entry.destination,
            reason_code=AttendanceReasonCode.HALL_PASS,
            hall_pass_id=log_entry.hall_pass_id,
            idempotency_key=f"student_hall_pass_checkout:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
        )
        return jsonify({
            "status": "success",
            "message": "Hall pass checked out.",
            "destination": log_entry.destination,
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKOUT_IDENTITY_MISSING: seat_id=%s pass_id=%s message=%s",
            getattr(student, "id", None),
            pass_id,
            str(exc),
        )
        return jsonify({"status": "error", "message": "Student session is missing required class context."}), 401
    except ValueError as exc:
        _log_api_client_error("checkout_hall_pass", exc, extra=f"pass_id={pass_id}")
        return jsonify({
            "status": "error",
            "message": _safe_exception_prefix_message(
                exc,
                "Hall pass cannot be checked out in its current state.",
                allowed_prefixes={"Pass is not approved."},
            ),
        }), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkout failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/checkin', methods=['POST'])
@login_required
def checkin_hall_pass():
    """Append an active attendance row when the student returns from hall pass."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKIN_DEBUG: seat_id=%s pass_id=%s pass_requested_by_seat_id=%s pass_class_id=%s session_class_id=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.requested_by_seat_id,
        log_entry.class_id,
        getattr(getattr(g, "canonical_context", None), "class_id", None),
    )
    
    if not student or log_entry.requested_by_seat_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error
    
    try:
        latest_event = (
            AttendanceSession.query.filter_by(
                target_seat_id=student.id,
                class_id=log_entry.class_id,
            )
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        if latest_event and latest_event.status == "active":
            return jsonify({"status": "success", "message": "You are already checked in."})

        record_attendance_session(
            ctx=context,
            target_seat_id=student.id,
            actor_seat_id=context.seat_id,
            mechanism="self",
            status="active",
            reason="Return from hall pass",
            hall_pass_id=log_entry.hall_pass_id,
            idempotency_key=f"student_hall_pass_checkin:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
        )
        return jsonify({
            "status": "success",
            "message": "Hall pass checked in.",
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKIN_IDENTITY_MISSING: seat_id=%s pass_id=%s message=%s",
            getattr(student, "id", None),
            pass_id,
            str(exc),
        )
        return jsonify({"status": "error", "message": "Student session is missing required class context."}), 401
    except ValueError as exc:
        _log_api_client_error("checkin_hall_pass", exc, extra=f"pass_id={pass_id}")
        return jsonify({
            "status": "error",
            "message": _safe_exception_prefix_message(
                exc,
                "Hall pass cannot be checked in in its current state.",
                allowed_prefixes={"You are not currently checked out."},
            ),
        }), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkin failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500




@api_bp.route('/hall-pass/settings', methods=['GET'])
@admin_required
def hall_pass_settings():
    """Get hall pass queue settings (admin only)"""
    context = getattr(g, "canonical_context", None)
    class_id = context.class_id if context else None
    if not class_id:
        return jsonify({"status": "error", "message": "Class context is required"}), 400

    settings = HallPassSettings.query.filter_by(class_id=class_id).first()

    return jsonify({
        "status": "success",
        "settings": {
            "queue_enabled": settings.queue_enabled if settings else True,
            "queue_limit": settings.queue_limit if settings else 10
        }
    })


@api_bp.route('/hall-pass/settings', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def update_hall_pass_settings():
    """Update hall pass queue settings (admin only)."""
    context = getattr(g, "canonical_context", None)
    class_id = context.class_id if context else None
    if not class_id:
        return jsonify({"status": "error", "message": "Class context is required"}), 400

    data = request.get_json() or {}
    try:
        settings = feat_update_hall_pass_queue_settings(
            user_id=context.user_id if context else None,
            class_id=class_id,
            join_code=None,
            queue_enabled=data.get("queue_enabled") if "queue_enabled" in data else None,
            queue_limit=data.get("queue_limit") if "queue_limit" in data else None,
            updated_at=utc_now(),
        )
    except ValueError as exc:
        _log_api_client_error("update_hall_pass_settings", exc, extra=f"class_id={class_id}")
        return jsonify({"status": "error", "message": "Hall pass settings are invalid."}), 400

    return jsonify({
        "status": "success",
        "message": "Settings updated successfully",
        "settings": {
            "queue_enabled": settings.queue_enabled,
            "queue_limit": settings.queue_limit,
        }
    })


@api_bp.route('/hall-pass/history', methods=['GET'])
@admin_required
def hall_pass_history():
    """Get paginated hall pass history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 25)), 100)  # Max 100 per page

        # Get filter parameters (no client-supplied period per C2 canonical scoping)
        pass_type = request.args.get('type', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        context = getattr(g, "canonical_context", None)
        current_class_id = (getattr(context, "class_id", None) or "").strip()
        if not current_class_id:
            return jsonify({"status": "error", "message": "Class context required"}), 400

        # Enforce single-class context for admin history views (v2 canonical scoping).
        query = HallPassLog.query.filter(HallPassLog.class_id == current_class_id)

        # Apply filters

        if pass_type:
            query = query.filter(HallPassLog.destination == pass_type)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=start_day,
                )
                query = query.filter(HallPassLog.timestamp >= start_bounds.boundary_start_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                end_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=end_day,
                )
                query = query.filter(HallPassLog.timestamp < end_bounds.boundary_end_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Order by most recent first
        query = query.order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Helper function to format timestamp as UTC with 'Z' suffix
        def format_timestamp(dt):
            if not dt:
                return None
            return ensure_utc(dt).isoformat().replace('+00:00', 'Z')
        
        # Format records for response
        records_data = []
        for record in records:
            seat = record.requested_by_seat
            profile = IdentityProfile.query.filter_by(
                seat_id=record.requested_by_seat_id,
                class_id=record.class_id,
            ).first()
            student_name = (
                " ".join(part for part in [
                    getattr(profile, "first_name", None),
                    getattr(profile, "last_name", None),
                ] if part).strip()
                or "Unknown"
            )
            class_row = ClassEconomy.query.filter_by(class_id=record.class_id).first()
            attendance_rows = (
                AttendanceSession.query.filter_by(
                    class_id=record.class_id,
                    target_seat_id=record.requested_by_seat_id,
                    hall_pass_id=record.hall_pass_id,
                )
                .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
                .all()
            )
            left_row = next(
                (
                    row for row in attendance_rows
                    if row.status == "inactive"
                    and row.reason_code == AttendanceReasonCode.HALL_PASS.value
                ),
                None,
            )
            return_row = next(
                (
                    row for row in attendance_rows
                    if left_row is not None
                    and row.status == "active"
                    and row.timestamp >= left_row.timestamp
                ),
                None,
            )
            if return_row is not None:
                status = "returned"
            elif left_row is not None:
                status = "left"
            else:
                status = "approved"
            records_data.append({
                "id": record.id,
                "student_name": student_name,
                "period": class_row.section if class_row else "",
                "reason": record.destination,
                "status": status,
                "request_time": format_timestamp(record.timestamp),
                "decision_time": None,
                "left_time": format_timestamp(left_row.timestamp if left_row else None),
                "return_time": format_timestamp(return_row.timestamp if return_row else None),
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching hall pass history: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch history"}), 500


@api_bp.route('/hall-pass/setup', methods=['GET'])
@admin_required
def get_hall_pass_setup():
    """Get teacher's hall pass configuration"""
    _ = get_current_user()
    context = getattr(g, "canonical_context", None)
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400

    scope = _get_hall_pass_settings_scope(current_class_id)
    if not scope:
        return jsonify({"status": "error", "message": "Class scope not found"}), 404

    feature_scope = resolve_feature_class_for_class(scope["class_id"], 'hall_pass')
    if feature_scope and not feature_scope["enabled"]:
        return jsonify({"status": "error", "message": "Hall pass is disabled for this class"}), 403

    settings = HallPassSettings.query.filter_by(class_id=scope["class_id"]).first()

    if not settings:
        # Return default configuration
        return jsonify({
            "status": "success",
            "hall_pass_enabled": True,
            "pass_types": HallPassSettings.get_default_pass_types()
        })

    # Return configured pass types with fallback to defaults
    return jsonify({
        "status": "success",
        "hall_pass_enabled": settings.queue_enabled,
        "pass_types": settings.get_pass_types()
    })


@api_bp.route('/hall-pass/setup', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def save_hall_pass_setup():
    """Save teacher's hall pass configuration"""
    user_id = g.canonical_context.user_id
    data = request.get_json() or {}
    context = getattr(g, "canonical_context", None)
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400

    pass_types = data.get('pass_types', [])
    hall_pass_enabled = data.get('hall_pass_enabled', True)

    # Validate hall_pass_enabled
    if not isinstance(hall_pass_enabled, bool):
        return jsonify({"status": "error", "message": "hall_pass_enabled must be a boolean"}), 400

    # Validate pass_types format
    if not isinstance(pass_types, list):
        return jsonify({"status": "error", "message": "pass_types must be a list"}), 400

    for pt in pass_types:
        if not isinstance(pt, dict):
            return jsonify({"status": "error", "message": "Each pass type must be an object"}), 400
        if 'name' not in pt:
            return jsonify({"status": "error", "message": "Each pass type must have a name"}), 400
        if not pt['name'].strip():
            return jsonify({"status": "error", "message": "Pass type name cannot be empty"}), 400

        # Validate enabled (defaults to True if not provided)
        if 'enabled' not in pt:
            pt['enabled'] = True
        if not isinstance(pt['enabled'], bool):
            return jsonify({"status": "error", "message": "enabled must be a boolean"}), 400

        # Validate queue_limit and simultaneous_limit (can be None or positive integer)
        for field in ['queue_limit', 'simultaneous_limit']:
            if field in pt and pt[field] is not None:
                try:
                    val = int(pt[field])
                    if val < 0:
                        return jsonify({"status": "error", "message": f"{field} must be non-negative"}), 400
                    pt[field] = val
                except (ValueError, TypeError):
                    return jsonify({"status": "error", "message": f"{field} must be a number or blank"}), 400

    try:
        scope = _get_hall_pass_settings_scope(current_class_id)
        if not scope:
            return jsonify({"status": "error", "message": "Class scope not found"}), 404
        settings = HallPassSettings.query.filter_by(class_id=scope["class_id"]).first()
        if not settings:
            settings = _get_or_create_hall_pass_settings(scope["class_id"])
        if not settings:
            return jsonify({"status": "error", "message": "Class scope not found"}), 404

        feature_scope = resolve_feature_class_for_class(scope["class_id"], 'hall_pass')
        if feature_scope and not feature_scope["enabled"]:
            return jsonify({"status": "error", "message": "Hall pass is disabled for this class"}), 403

        settings = feat_save_hall_pass_setup_config(
            user_id=user_id,
            class_id=scope["class_id"],
            hall_pass_enabled=hall_pass_enabled,
            pass_types=pass_types,
            updated_at=utc_now(),
        )

        return jsonify({
            "status": "success",
            "message": "Hall pass configuration saved successfully",
            "hall_pass_enabled": settings.queue_enabled,
            "pass_types": settings.get_pass_types()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving hall pass setup: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to save configuration"}), 500


@api_bp.route('/hall-pass/verify-token/rotate', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def rotate_hall_pass_verify_token():
    """
    Rotate the teacher's hall pass public verification token.

    Generates a new 256-bit random token and overwrites the old one.
    The old token is immediately invalid. Use after a lost pass, suspicious
    traffic, or student screenshot concern.
    """
    user_id = g.canonical_context.user_id

    try:
        token = feat_rotate_teacher_hall_pass_verify_token(user_id=user_id)
    except LookupError as exc:
        _log_api_client_error("rotate_hall_pass_verify_token", exc, extra=f"user_id={user_id}")
        return jsonify({"status": "error", "message": "Hall pass verification settings were not found."}), 404
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Failed to rotate hall pass verify token", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to rotate token."}), 500

    return jsonify({
        "status": "success",
        "token": token
    })


@api_bp.route('/hall-pass/available-types', methods=['GET'])
@login_required
def get_available_hall_pass_types():
    """Get available pass types for the current class.

    Authority: class_id is canonical and required.
    """
    requested_class_id = (request.args.get('class_id') or '').strip() or None

    resolved_class_id = None
    context = resolve_canonical_context()

    if context:
        # Session class context is authoritative for logged-in student/admin flows.
        resolved_class_id = context.class_id
        if requested_class_id and requested_class_id != resolved_class_id:
            return jsonify({"status": "error", "message": "class_id is out of scope for this session"}), 403
    elif requested_class_id:
        class_row = ClassEconomy.query.filter_by(class_id=requested_class_id).first()
        if class_row:
            resolved_class_id = class_row.class_id

    if not resolved_class_id:
        return jsonify({
            "status": "error",
            "message": "class_id is required"
        }), 400

    settings = None
    if resolved_class_id:
        settings = HallPassSettings.query.filter_by(class_id=resolved_class_id).first()
    feature_scope = resolve_feature_class_for_class(resolved_class_id, 'hall_pass')
    if not feature_scope or not feature_scope.get("enabled"):
        return jsonify({
            "status": "error",
            "message": "Hall pass is disabled for this class",
        }), 403

    if not settings:
        # Return defaults if not configured
        return jsonify({
            "status": "success",
            "pass_types": HallPassSettings.get_default_pass_types()
        })

    # Return just the names for enabled pass types
    pass_types = settings.get_pass_types()
    enabled_pass_types = [{"name": pt["name"]} for pt in pass_types if pt.get("enabled", True)]

    return jsonify({
        "status": "success",
        "pass_types": enabled_pass_types
    })


@api_bp.route('/hall-pass/verification/active', methods=['GET'])
def hall_pass_verification_active():
    """Return current-day hall passes for the teacher resolved by public token."""
    from types import SimpleNamespace

    token = (request.args.get('token') or '').strip()
    if not token:
        return jsonify({"status": "error", "message": "token is required"}), 400

    teacher_user = User.query.filter_by(hall_pass_verify_token=token).first()
    if not teacher_user:
        return jsonify({"status": "error", "message": "Verification page not available."}), 404

    class_rows = ClassEconomy.query.filter_by(user_id=teacher_user.id).all()
    class_ids = [row.class_id for row in class_rows]
    class_by_id = {row.class_id: row for row in class_rows}
    passes = []
    for class_id in class_ids:
        public_temporal_context = SimpleNamespace(class_id=class_id)
        day_bounds = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=public_temporal_context,
            primitive="evaluation_day_boundaries",
        )
        passes.extend(
            HallPassLog.query
            .filter(
                HallPassLog.class_id == class_id,
                HallPassLog.timestamp >= day_bounds.boundary_start_utc,
                HallPassLog.timestamp < day_bounds.boundary_end_utc,
            )
            .order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc())
            .all()
        )
    passes.sort(key=lambda log: (log.timestamp, log.id), reverse=True)
    passes = passes[:10]

    def _hall_pass_state(log):
        rows = (
            AttendanceSession.query.filter_by(
                class_id=log.class_id,
                target_seat_id=log.requested_by_seat_id,
                hall_pass_id=log.hall_pass_id,
            )
            .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
            .all()
        )
        left_row = None
        return_row = None
        left_row = next(
            (
                row for row in rows
                if row.status == "inactive"
                and row.reason_code == AttendanceReasonCode.HALL_PASS.value
            ),
            None,
        )
        return_row = next(
            (
                row for row in rows
                if left_row is not None
                and row.status == "active"
                and row.timestamp >= left_row.timestamp
            ),
            None,
        )
        status = "returned" if return_row is not None else "left" if left_row is not None else "approved"
        return status, left_row, return_row

    def _profile_for(log):
        return IdentityProfile.query.filter_by(
            seat_id=log.requested_by_seat_id,
            class_id=log.class_id,
        ).first()

    def _iso_timestamp(row):
        if row is None or row.timestamp is None:
            return None
        return row.timestamp.isoformat().replace("+00:00", "Z")

    pass_rows = []
    for log in passes:
        profile = _profile_for(log)
        status, left_row, return_row = _hall_pass_state(log)
        class_row = class_by_id.get(log.class_id)
        student_name = ""
        if profile is not None:
            student_name = " ".join(
                part for part in (
                    profile.first_name,
                    f"{profile.last_initial}." if profile.last_initial else None,
                )
                if part
            ).strip()
        pass_rows.append({
            "id": log.id,
            "seat_id": log.requested_by_seat_id,
            "student_name": student_name,
            "destination": log.destination,
            "status": status,
            "left_time": _iso_timestamp(left_row),
            "return_time": _iso_timestamp(return_row),
            "period": (class_row.section if class_row else None) or "",
            "class_id": log.class_id,
            "class_label": (
                class_row.display_name
                or class_row.section
                or log.class_id
            ) if class_row else log.class_id,
        })

    return jsonify({
        "status": "success",
        "passes": pass_rows,
    })


@api_bp.route('/attendance/history', methods=['GET'])
@admin_required
def attendance_history():
    """Get paginated attendance history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)  # Max 100 per page

        # Get filter parameters
        status = request.args.get('status', '').strip()  # 'active' or 'inactive'
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        context = getattr(g, "canonical_context", None)
        current_class_id = (getattr(context, "class_id", None) or "").strip()
        if not current_class_id:
            return jsonify({"status": "error", "message": "Class context required"}), 400

        query = AttendanceSession.query.filter(
            AttendanceSession.class_id == current_class_id
        )

        if status:
            if status not in {'active', 'inactive'}:
                return jsonify({"status": "error", "message": "Invalid status filter"}), 400
            query = query.filter(AttendanceSession.status == status)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=start_day,
                )
                query = query.filter(AttendanceSession.timestamp >= start_bounds.boundary_start_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                end_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=end_day,
                )
                query = query.filter(AttendanceSession.timestamp < end_bounds.boundary_end_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        query = query.order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        seat_ids = [r.target_seat_id for r in records if r.target_seat_id]
        seats = {}
        if seat_ids:
            seat_rows = (
                db.session.query(
                    Seat.id,
                    Seat.class_id,
                    ClassEconomy.section,
                    ClassEconomy.display_name,
                    ClassEconomy.join_code,
                    IdentityProfile.first_name,
                    IdentityProfile.last_name,
                )
                .outerjoin(IdentityProfile, IdentityProfile.seat_id == Seat.id)
                .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                .filter(Seat.id.in_(seat_ids))
                .all()
            )
        else:
            seat_rows = []

        for row in seat_rows:
            student_name = " ".join(part for part in [row.first_name, row.last_name] if part).strip() or "Unknown"
            seats[row.id] = {
                "name": student_name,
                "class_id": row.class_id,
                "period": row.section or "",
                "class_label": row.display_name or row.join_code or row.class_id,
            }

        records_data = []
        for record in records:
            seat_info = seats.get(record.target_seat_id, {
                'name': 'Unknown',
                'class_id': record.class_id,
                'period': '',
                'class_label': record.class_id,
            })
            student_class_id = seat_info['class_id']
            student_class_label = seat_info['class_label'] or student_class_id or 'Unknown'

            timestamp_str = None
            if record.timestamp:
                timestamp_str = ensure_utc(record.timestamp).isoformat().replace('+00:00', 'Z')

            records_data.append({
                "id": record.id,
                "seat_id": record.target_seat_id,
                "student_name": seat_info['name'],
                "student_block": student_class_label,
                "student_class_label": student_class_label,
                "period": seat_info['period'],
                "status": record.status,
                "reason": record.reason_code,
                "timestamp": timestamp_str
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching attendance history: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to fetch attendance history"}), 500


# -------------------- ATTENDANCE API --------------------

@api_bp.route('/tap', methods=['POST'])
@limiter.limit("100 per minute")
def handle_tap():
    data = request.get_json(silent=True) or {}
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    current_app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    context = getattr(g, "canonical_context", None)
    student_seat = db.session.get(Seat, context.seat_id) if context else None
    student_user = db.session.get(User, context.user_id) if context else None

    if not student_seat or not student_user:
        current_app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not check_password_hash(student_user.pin_hash or '', pin):
        current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student_user.id}")
        return jsonify({"error": "Invalid PIN"}), 403

    context = resolve_canonical_context()
    class_id = context.class_id if context else None
    if not class_id:
        current_app.logger.warning("ATTENDANCE ERROR: Missing class_id context for user_id=%s", student_user.id)
        return jsonify({"error": "Unable to resolve class context for this period."}), 400

    action = data.get("action")

    current_app.logger.info("TAP DEBUG: class_id=%s action=%s", class_id, action)

    # Support both old and new action names
    action_map = {
        "tap_in": "start_work",
        "tap_out": "stop_work",
        "start_work": "start_work",
        "stop_work": "stop_work"
    }

    if action not in action_map:
        current_app.logger.warning("TAP ERROR: Invalid action: action=%s", action)
        return jsonify({"error": "Invalid action"}), 400

    normalized_action = action_map[action]

    seat_id = student_seat.id if student_seat and student_seat.class_id == class_id else None
    if not seat_id:
        return jsonify({"error": "No seat assigned in this class."}), 403

    latest_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    currently_active = bool(latest_event and latest_event.status == "active")

    if normalized_action == "start_work" and currently_active:
        return jsonify({"status": "ok", "active": True, "duration": 0})

    if normalized_action == "stop_work" and not currently_active:
        return jsonify({"status": "ok", "active": False, "duration": 0})

    reason = data.get("reason") if normalized_action == "stop_work" else None
    reason_code = None
    if normalized_action == "stop_work":
        if not reason:
            return jsonify({"error": "A reason is required."}), 400
        if reason.lower() in ['done', 'done for the day']:
            reason_code = AttendanceReasonCode.DONE_FOR_DAY
        else:
            return jsonify({"error": "Hall-pass requests are handled by the hall-pass command surface."}), 400

    try:
        status = "active" if normalized_action == "start_work" else "inactive"
        record_attendance_session(
            ctx=context,
            status=status,
            reason=reason,
            reason_code=reason_code,
            idempotency_key=f"prod_attendance:{class_id}:{seat_id}:{normalized_action}:{secrets.token_hex(12)}",
        )
        current_app.logger.info("TAP success - seat %s class_id=%s action=%s", seat_id, class_id, action)
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for seat {seat_id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    refreshed_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    is_active = bool(refreshed_event and refreshed_event.status == "active")
    last_payroll = (
        PayrollEvent.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
            payroll_event_type="payroll",
        )
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .first()
    )
    duration = calculate_unpaid_attendance_seconds(
        seat_id,
        class_id,
        last_payroll.recorded_at if last_payroll else None,
        ctx=context,
    )

    class_row = db.session.get(ClassEconomy, class_id)
    settings_section = class_row.section if class_row and class_row.section else None
    rate_per_second = get_pay_rate_for_block(settings_section, class_id=class_id)
    projected_pay = duration * rate_per_second

    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": float(projected_pay)
    })


@api_bp.route('/student-status', methods=['GET'])
@login_required
def student_status():
    from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

    context = resolve_canonical_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    student = db.session.get(Seat, context.seat_id)

    class_id = context.class_id
    if not class_id:
        return jsonify({"status": "error", "message": "Class context unavailable."}), 400

    attendance_state = get_class_attendance_status(student, class_id=class_id, ctx=context)
    if 'projected_pay' in attendance_state and attendance_state['projected_pay'] is not None:
        attendance_state['projected_pay'] = float(attendance_state['projected_pay'])

    return jsonify({
        "status": "ok",
        "attendance_state": attendance_state
    })


# -------------------- UTILITY API --------------------

@api_bp.route('/set-timezone', methods=['POST'])
def set_timezone():
    """Store user's timezone in session for datetime formatting"""
    now = utc_now()

    # Check via V2 Canonical Context
    context = getattr(g, "canonical_context", None)
    if not context:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    session['last_activity'] = now.isoformat()

    data = request.get_json()
    timezone_name = data.get('timezone')

    if not timezone_name:
        return jsonify({"status": "error", "message": "Timezone is required."}), 400

    # Validate Timezone
    if timezone_name not in pytz.all_timezones:
         return jsonify({"status": "error", "message": "Invalid timezone."}), 400

    # Store in session
    session['timezone'] = timezone_name
    current_app.logger.info(f"Timezone set to {timezone_name} for session")

    return jsonify({"status": "success", "message": f"Timezone set to {timezone_name}."})


    # view_as_student_status endpoint — REMOVED (prohibited feature)
