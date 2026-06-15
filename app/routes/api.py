"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import re
import pytz
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import func, or_
import sqlalchemy as sa
from sqlalchemy.orm import aliased
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models import (
    Admin, Student, StoreItem, StudentItem, Transaction, TransactionStatus, TapEvent,
    TapEventReasonCode, HallPassLog, HallPassSettings, InsuranceClaim, BankingSettings,
    StudentTeacher, StudentBlock, StoreItemBlock,
    RedemptionAuditLog, RedemptionAuditAction, RedemptionAuditSource, _quantize_currency,
    ClassEconomy, ClassMembership, Seat, SeatAttendanceState,
)
from app.auth import (
    login_required,
    admin_required,
    get_current_seat,
    get_logged_in_student,
    get_current_admin,
    get_current_system_admin,
    get_current_user,
    get_current_class_id,
    SESSION_TIMEOUT_MINUTES,
)
from app.access import AccessScopeDenied, resolve_scope
from app.feats.base import feat_shell
from app.feats.attendance import (
    apply_standard_tap_mutations as feat_apply_standard_tap_mutations,
    approve_hall_pass as feat_approve_hall_pass,
    cancel_hall_pass as feat_cancel_hall_pass,
    check_hall_pass_request_policy as feat_check_hall_pass_request_policy,
    check_start_work_daily_limit as feat_check_start_work_daily_limit,
    checkin_hall_pass as feat_checkin_hall_pass,
    checkout_hall_pass as feat_checkout_hall_pass,
    enforce_daily_limits as feat_enforce_daily_limits,
    get_or_create_student_block as feat_get_or_create_student_block,
    leave_hall_pass as feat_leave_hall_pass,
    reject_hall_pass as feat_reject_hall_pass,
    request_hall_pass as feat_request_hall_pass,
    rotate_teacher_hall_pass_verify_token as feat_rotate_teacher_hall_pass_verify_token,
    save_hall_pass_setup_config as feat_save_hall_pass_setup_config,
    set_student_block_tap_enabled as feat_set_student_block_tap_enabled,
    soft_delete_tap_entry as feat_soft_delete_tap_entry,
    update_hall_pass_queue_settings as feat_update_hall_pass_queue_settings,
    return_hall_pass as feat_return_hall_pass,
)
from app.routes.student import (
    get_feature_settings_for_student,
    get_rent_settings_for_context,
    _calculate_rent_coverage_due_date,
    _is_student_coverage_period_paid,
    _ensure_rent_hall_pass_top_off,
)
from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
from app.feats.store_purchase_feat import execute_rent_perk_purchase, execute_store_purchase
from app.feats.redemption_disposition_feat import (
    RedemptionDispositionError,
    execute_redemption_approval,
    execute_redemption_rejection,
)
from app.services import store_service
from app.utils.economy_policy import resolve_class_scope, resolve_feature_class, resolve_feature_class_for_class
from app.utils.overdraft import charge_overdraft_fee_if_needed
from app.utils.seat_scope import get_seat_id_for_class
from app.utils.transaction_idempotency import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    get_idempotent_transaction,
    purchase_transaction_key,
    student_item_refund_key,
)
from app.utils.time import (
    utc_now,
    ensure_utc,
    normalize_for_db,
    get_timezone,
    local_date_bounds_utc,
    UTC_MIN,
    class_date,
    day_bounds_utc,
    get_class_now,
    get_class_today_range,
)

# Import external modules
from app.services.attendance_service import calculate_unpaid_attendance_seconds, get_all_block_statuses
from app.services.ledger_service import (
    apply_overdraft_fee_if_needed as apply_ledger_overdraft_fee,
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


def _safe_exception_message(exc, default_message, *, allowed_messages=None):
    message = str(exc)
    if allowed_messages and message in allowed_messages:
        return message
    return default_message


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


def _resolve_class_display_label(teacher_id, class_id, join_code=None, fallback_block=None):
    """
    Resolve a stable class display label snapshot for audit logging.
    """
    if class_id:
        class_economy = ClassEconomy.query.filter_by(class_id=class_id).first()
        if class_economy:
            return class_economy.display_name or class_economy.join_code
    
    if join_code:
        # Fallback for UI-driven requests
        class_economy = ClassEconomy.query.filter_by(join_code=join_code).first()
        if class_economy:
            return class_economy.display_name or class_economy.join_code

    return fallback_block or "Unknown Class"


def _append_redemption_audit_log(*, student_item, student, teacher_id, action, notes, guard_state, fallback_block=None):
    """
    Append exactly one live redemption audit log row for this request path.

    Must be called before redemption state mutations.
    """
    if guard_state.get('inserted'):
        raise RuntimeError("Duplicate redemption audit insertion attempt in single request path")

    action_map = {
        'request': RedemptionAuditAction.REQUEST,
        'approved': RedemptionAuditAction.APPROVED,
        'rejected': RedemptionAuditAction.REJECTED,
    }
    if action not in action_map:
        raise ValueError(f"Unsupported redemption audit action: {action}")

    student_name = student.full_name if student else "Unknown Student"
    class_id = getattr(student_item, 'class_id', None)
    join_code = getattr(student_item, 'join_code', None)
    class_label = _resolve_class_display_label(teacher_id, class_id, join_code=join_code, fallback_block=fallback_block)

    db.session.add(RedemptionAuditLog(
        student_item_id=student_item.id if student_item else None,
        student_display_name=student_name,
        class_display_label=class_label,
        action=action_map[action],
        notes=notes if notes else None,
        teacher_id=teacher_id,
        class_id=class_id,
        timestamp=utc_now(),
        source=RedemptionAuditSource.LIVE,
    ))
    guard_state['inserted'] = True


def _get_request_join_code(payload=None):
    """Resolve explicit class scope from request data or session."""
    join_code = request.args.get("join_code", "").strip()
    if not join_code and payload:
        raw_join_code = payload.get("join_code")
        if raw_join_code is not None:
            join_code = str(raw_join_code).strip()
    if not join_code:
        join_code = (session.get("current_join_code") or "").strip()
    return join_code or None


def _get_hall_pass_settings_scope(teacher_id, join_code):
    """Resolve canonical class scope for hall pass settings."""
    return resolve_class_scope(teacher_id, join_code=join_code)


def _get_or_create_hall_pass_settings(class_id):
    """Return the hall pass settings row for a specific class, creating it if needed."""
    if not class_id:
        return None

    settings = HallPassSettings.query.filter_by(class_id=class_id).first()
    if settings:
        return settings

    settings = HallPassSettings(
        class_id=class_id,
        queue_enabled=True,
        queue_limit=10,
    )
    db.session.add(settings)
    return settings


def _get_teacher_class_scope(admin_id):
    """Return (class_id_scope_subquery, has_class_scope) for a teacher admin."""
    class_id_scope = (
        db.session.query(ClassMembership.class_id)
        .filter(
            ClassMembership.admin_id == admin_id,
            ClassMembership.role == 'admin',
            ClassMembership.class_id.isnot(None),
        )
        .distinct()
        .subquery()
    )
    has_class_scope = db.session.query(
        sa.exists().where(
            sa.and_(
                ClassMembership.admin_id == admin_id,
                ClassMembership.role == 'admin',
                ClassMembership.class_id.isnot(None),
            )
        )
    ).scalar()
    return class_id_scope, has_class_scope


def _admin_has_class_scope(admin_id, class_id):
    """Return True when admin owns the class_id via active admin membership."""
    if not admin_id or not class_id:
        return False

    return db.session.query(
        sa.exists().where(
            sa.and_(
                ClassMembership.admin_id == admin_id,
                ClassMembership.class_id == class_id,
                ClassMembership.role == 'admin',
            )
        )
    ).scalar()


def _apply_admin_class_scope(query, model, admin_id, accessible_student_ids_query=None):
    """Apply class_id tenant scoping. In V2, class_id is the primary anchor."""
    class_id_scope, has_class_scope = _get_teacher_class_scope(admin_id)
    if has_class_scope:
        return query.filter(
            model.class_id.isnot(None),
            model.class_id.in_(sa.select(class_id_scope)),
        )
    if accessible_student_ids_query is not None:
        return query.filter(model.student_id.in_(accessible_student_ids_query))
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

def _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id, join_code, force=False):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.

    Args:
        student: Student object
        banking_settings: BankingSettings object
        teacher_id: Teacher ID for multi-tenancy isolation
        join_code: Join code for multi-tenancy isolation
        force: Charge fee even if balance is non-negative (declined transaction).
    """
    return apply_ledger_overdraft_fee(
        student,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code,
        force=force
    )


@api_bp.route('/purchase-item', methods=['POST'])
@login_required
@feat_shell("FEAT-STOR-002")
def purchase_item():
    from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

    student = get_logged_in_student()
    try:
        scope = resolve_scope(
            actor=student,
            selected_join_code=session.get("current_join_code"),
        )
    except AccessScopeDenied as exc:
        return jsonify({"status": "error", "message": exc.message}), 403
    data = request.get_json(silent=True) or {}
    item_id = data.get('item_id')
    passphrase = data.get('passphrase')
    try:
        quantity = int(data.get('quantity', 1))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Quantity must be a whole number."}), 400
    client_purchase_id = str(data.get('client_purchase_id') or '').strip()

    if not all([item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1."}), 400

    if len(client_purchase_id) > MAX_IDEMPOTENCY_KEY_LENGTH:
        return jsonify({"status": "error", "message": "Purchase request ID is too long."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # CRITICAL FIX v2: Get full class context (class_id is source of truth)
    context = resolve_canonical_context()
    if not context:
        return jsonify({"status": "error", "message": "No class context available."}), 400

    class_id = context.class_id
    join_code = get_display_join_code(context.class_id)
    teacher_id = context['teacher_id']
    current_block = context.get('block', '').strip().upper()
    seat_id = get_seat_id_for_class(student.id, class_id)
    if not seat_id:
         return jsonify({"status": "error", "message": "No seat assigned in this class."}), 403
    
    # Authoritative seat object
    from app.models import Seat
    seat = db.session.get(Seat, seat_id)

    purchase_idempotency_key = None
    if client_purchase_id:
        purchase_idempotency_key = purchase_transaction_key(
            seat.id,
            class_id,
            item_id,
            client_purchase_id,
        )
        if len(purchase_idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            return jsonify({"status": "error", "message": "Purchase request ID is too long."}), 400

    item_filters = [
        StoreItem.id == item_id,
        StoreItem.class_id == class_id,
    ]
    if current_block:
        item_filters.append(
            or_(
                StoreItem.visible_blocks.any(func.upper(StoreItemBlock.block) == current_block),
                ~StoreItem.visible_blocks.any(),
            )
        )
    item = (
        StoreItem.query
        .filter(*item_filters)
        .first()
    )

    # 2. Validate item and purchase conditions
    if not item or not item.is_active:
        return jsonify({"status": "error", "message": "This item is not available."}), 404

    # Check if a collective goal has passed its expiration deadline.
    if item.item_type == 'collective' and item.collective_goal_expires_at:
        if ensure_utc(item.collective_goal_expires_at) <= utc_now():
            return jsonify({"status": "error", "message": "This collective goal has expired and is no longer available."}), 400

    # For collective items with whole_class goal, enforce one purchase per student per class
    if item.item_type == 'collective' and item.collective_goal_type == 'whole_class':
        existing_purchase = StudentItem.query.filter(
            StudentItem.seat_id == seat.id,
            StudentItem.store_item_id == item.id,
            StudentItem.class_id == class_id,
            StudentItem.status.notin_(['voided', 'rejected'])
        ).first()
        if existing_purchase:
            return jsonify({"status": "error", "message": "You have already purchased this whole class goal item."}), 400

    # Check rent late restrictions
    from app.models import RentSettings, RentItem
    from datetime import timedelta

    rent_settings = get_rent_settings_for_context(context)
    now = utc_now()
    has_paid_rent = False
    per_use_rent_item = None
    has_privilege_link = False
    has_per_use_link = False

    if rent_settings and rent_settings.is_enabled:
        coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
        if coverage_due_date:
            has_paid_rent = _is_student_coverage_period_paid(
                rent_settings,
                seat.id,
                class_id,
                coverage_due_date,
            )

        rent_item_links = RentItem.query.filter(
            RentItem.rent_setting_id == rent_settings.id,
            RentItem.store_item_id == item.id
        ).all()
        has_per_use_link = any(
            ri.rent_item_type == 'per_use' or (ri.rent_item_type == 'privilege' and ri.purchase_duration == 'per_use')
            for ri in rent_item_links
        )
        has_privilege_link = any(
            ri.rent_item_type == 'privilege' and ri.purchase_duration != 'per_use'
            for ri in rent_item_links
        )
        per_use_rent_item = next(
            (ri for ri in rent_item_links
             if ri.rent_item_type == 'per_use' or (ri.rent_item_type == 'privilege' and ri.purchase_duration == 'per_use')),
            None
        )

        # Fallback for legacy/stale linkage where StoreItem.is_rent_linked is True but mapping row is missing.
        if not per_use_rent_item and item.is_rent_linked:
            has_per_use_link = True

    # Privilege-only rent items are already included when rent is paid and
    # should not be purchasable.
    if has_paid_rent and has_privilege_link and not has_per_use_link:
        return jsonify({
            "status": "error",
            "message": "This item is already included in your rent for this period."
        }), 400

    if rent_settings and rent_settings.is_enabled and rent_settings.prevent_purchase_when_late:
        # Check if student is late on rent
        coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)

        if coverage_due_date:
            grace_end_date = coverage_due_date + timedelta(days=rent_settings.grace_period_days)

            # Pre-paid system: use the most recently passed due date
            # as the coverage period so we match payments that COVER this cycle.
            coverage_month = coverage_due_date.month
            coverage_year = coverage_due_date.year

            # Check if past grace period
            if now > grace_end_date:
                is_paid_for_coverage = _is_student_coverage_period_paid(
                    rent_settings,
                    seat.id,
                    class_id,
                    coverage_due_date,
                )

                # Student is late if they haven't fully settled the coverage period
                if not is_paid_for_coverage:
                    # Check if itemization is enabled
                    rent_items = RentItem.query.filter_by(rent_setting_id=rent_settings.id).all()

                    if rent_items:
                        # Itemization is enabled: check if this item is a rent item
                        rent_item_store_ids = [ri.store_item_id for ri in rent_items if ri.store_item_id]

                        if item.id not in rent_item_store_ids:
                            # This item is NOT part of rent - block purchase
                            return jsonify({
                                "status": "error",
                                "message": "You are late on rent. You can only purchase items covered by rent until you pay your rent."
                            }), 403
                        # If item IS part of rent, allow purchase (they can buy à la carte)
                    else:
                        # No itemization: block ALL purchases
                        return jsonify({
                            "status": "error",
                            "message": "You cannot make purchases while late on rent. Please pay your rent first."
                        }), 403

    # Check if student has free uses remaining from rent (per-use rent items).
    if (
        quantity == 1
        and item.item_type != 'hall_pass'
        and (item.is_rent_linked or per_use_rent_item)
    ):
        # Look for an active StudentItem with uses_remaining for this store item
        rent_item_query = StudentItem.query.filter(
            StudentItem.seat_id == seat.id,
            StudentItem.class_id == class_id,
            StudentItem.store_item_id == item.id,
            db.or_(
                StudentItem.uses_remaining > 0,
                StudentItem.uses_remaining == -1
            ),
            db.or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > now
            )
        )

        active_rent_item = rent_item_query.first()
        needs_rent_grant = (
            not active_rent_item
            and has_paid_rent
            and (per_use_rent_item or item.is_rent_linked)
        )

        if active_rent_item or needs_rent_grant:
            result = execute_rent_perk_purchase(
                scope=scope,
                seat=seat,
                teacher_id=teacher_id,
                item=item,
                active_rent_item=active_rent_item,
                ensure_active_grant=needs_rent_grant,
                rent_grant_use_limit=per_use_rent_item.use_limit if per_use_rent_item else None,
                banking_settings=None,
                purchase_idempotency_key=purchase_idempotency_key,
            )
            # No manual commit here; feat_shell owns it
            remaining = result.rent_uses_remaining
            if remaining == -1:
                return jsonify({"status": "success", "message": f"{result.success_message} Unlimited free purchases remaining this period."})
            if remaining > 0:
                return jsonify({"status": "success", "message": f"{result.success_message} {remaining} free purchase(s) remaining this period."})
            return jsonify({"status": "success", "message": f"{result.success_message} No free purchases remaining this period."})

    # Calculate price (with bulk discount if applicable)
    unit_price = item.price
    if (item.bulk_discount_enabled and
        item.bulk_discount_quantity is not None and
        item.bulk_discount_percentage is not None and
        quantity >= item.bulk_discount_quantity):
        discount_multiplier = Decimal('1') - (Decimal(str(item.bulk_discount_percentage)) / 100)
        unit_price = item.price * discount_multiplier

    # Align balance checks and persisted purchase amount with 2dp currency semantics.
    total_price = _quantize_currency(unit_price * quantity)

    # Get banking settings for overdraft handling
    banking_settings = BankingSettings.query.filter_by(class_id=class_id).first()
    checking_balance, savings_balance = get_available_balances(seat.id, class_id)

    # Check if student has sufficient funds
    if checking_balance < total_price:
        shortfall = total_price - checking_balance
        # Check if overdraft protection is enabled (savings can cover the difference)
        if (banking_settings and banking_settings.overdraft_protection_enabled and
                savings_balance >= shortfall):
            # Allow transaction - overdraft protection will transfer from savings
            pass
        else:
            fee_charged, fee_amount = apply_ledger_overdraft_fee(
                seat,
                banking_settings,
                force=True
            )

            if banking_settings and banking_settings.overdraft_protection_enabled:
                message = (f"Insufficient funds in both checking and savings. You need "
                           f"${total_price:.2f} total but have "
                           f"${checking_balance + savings_balance:.2f}.")
            else:
                message = (f"Insufficient funds. You need ${total_price:.2f} but have "
                           f"${checking_balance:.2f}.")

            if fee_charged:
                message += f" Overdraft fee of ${fee_amount:.2f} charged."

            return jsonify({"status": "error", "message": message}), 400

    if item.inventory is not None and item.inventory < quantity:
        return jsonify({"status": "error", "message": f"Insufficient stock. Only {item.inventory} available."}), 400

    if item.limit_per_student is not None:
        if item.item_type == 'hall_pass':
            # For hall passes, check transaction history and sum quantities
            transactions = Transaction.query.filter(
                Transaction.seat_id == seat.id,
                Transaction.class_id == class_id,
                Transaction.type == 'purchase',
                Transaction.description.like(f"Purchase: {item.name}%")
            ).all()

            # Parse quantities from transaction descriptions
            total_purchased = 0
            for txn in transactions:
                match = re.search(r'\(x(\d+)\)', txn.description)
                total_purchased += int(match.group(1)) if match else 1

            purchase_count = total_purchased
        else:
            purchase_count = StudentItem.query.filter(
                StudentItem.seat_id == seat.id,
                StudentItem.class_id == class_id,
                StudentItem.store_item_id == item.id,
                StudentItem.status.notin_(['voided', 'rejected'])
            ).count()
        if purchase_count + quantity > item.limit_per_student:
            return jsonify({"status": "error", "message": f"You can only purchase {item.limit_per_student - purchase_count} more of this item."}), 400

    # 3. Process the transaction
    try:
        purchase_description = f"Purchase: {item.name}"
        if quantity > 1:
            purchase_description += f" (x{quantity})"
        if item.bulk_discount_enabled and quantity >= item.bulk_discount_quantity:
            purchase_description += f" [{item.bulk_discount_percentage}% bulk discount]"
        expiry_date = None
        from app.models import RentItem, RentSettings
        rent_item = RentItem.query.filter_by(store_item_id=item.id).first()
        uses_remaining = None

        if rent_item:
            if rent_item.rent_item_type == 'privilege':
                rent_setting = db.session.get(RentSettings, rent_item.rent_setting_id)
                if rent_setting and rent_setting.is_enabled:
                    now = utc_now()
                    if rent_setting.first_rent_due_date:
                        current_due, next_due = _calculate_due_dates(rent_setting, now)
                        if current_due and next_due:
                            expiry_date = next_due
                    else:
                        delta = _get_period_delta(rent_setting)
                        expiry_date = _add_period(now, delta)

        # Fall back to standard auto_expiry for delayed items
        if expiry_date is None and item.item_type == 'delayed' and item.auto_expiry_days:
            expiry_date = utc_now() + timedelta(days=item.auto_expiry_days)

        student_item_status = 'purchased'
        if item.item_type == 'immediate':
            student_item_status = 'redeemed'
        elif item.item_type == 'collective':
            student_item_status = 'pending'
        else: # delayed
            student_item_status = 'purchased'
        
        result = execute_store_purchase(
            scope=scope,
            seat=seat,
            teacher_id=teacher_id,
            item=item,
            quantity=quantity,
            total_price=total_price,
            purchase_description=purchase_description,
            banking_settings=banking_settings,
            purchase_idempotency_key=purchase_idempotency_key,
            expiry_date=expiry_date,
            uses_remaining=uses_remaining,
            student_item_status=student_item_status,
        )
        # No manual commit here; feat_shell owns it

        if item.item_type == 'hall_pass':
            return jsonify({
                "status": "success",
                "message": f"You purchased {quantity} Hall Pass(es)! Your new balance is {result.hall_pass_balance}.",
            })

        return jsonify({"status": "success", "message": result.success_message})

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Purchase failed for seat {seat.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred during purchase. Please try again."}), 500


@api_bp.route('/use-item', methods=['POST'])
@login_required
@feat_shell("FEAT-STOR-005")
def use_item():
    student = get_logged_in_student()
    data = request.get_json()
    student_item_id = data.get('student_item_id')
    passphrase = data.get('passphrase')
    details = data.get('redemption_details', data.get('details', ''))  # optional notes from student

    if not all([student_item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 2. Get the student's item
    student_item = db.session.get(StudentItem, student_item_id)

    if not student_item or student_item.student_id != student.id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Special handling for hall_pass items in inventory (legacy or bundle)
    if student_item.store_item.item_type == 'hall_pass':
        # Grant balance immediately
        qty = student_item.quantity_purchased or 1
        student.hall_passes = (student.hall_passes or 0) + qty
        student_item.status = 'redeemed'
        student_item.redemption_date = utc_now()
        student_item.redemption_details = f"Hall pass grant processed immediately ({qty} pass(es) added)."
        db.session.flush()
        return jsonify({"status": "success", "message": f"Added {qty} hall pass(es) to your balance!"})

    # Validate the item can be used
    if student_item.is_from_bundle:
        # For bundle items, check bundle_remaining
        if student_item.bundle_remaining is None or student_item.bundle_remaining <= 0:
            return jsonify({"status": "error", "message": "All uses from this bundle have been consumed."}), 400
    else:
        # For regular items, check status
        if student_item.status not in ['purchased', 'pending']:
            return jsonify({"status": "error", "message": "This item has already been used or is not available."}), 400

    # Check expiry
    if student_item.expiry_date and utc_now() > student_item.expiry_date:
        student_item.status = 'expired'
        db.session.flush()
        return jsonify({"status": "error", "message": "This item has expired."}), 400

    # Get context up front for audit snapshots and transaction scoping.
    context = resolve_canonical_context()
    teacher_id_for_audit = (
        context['teacher_id'] if context else
        (student_item.store_item.teacher_id if student_item.store_item else None)
    )
    fallback_block = context.get('block') if context else student.block


    # Request action happens when item transitions into admin approval workflow.
    will_create_request = (
        not student_item.is_from_bundle and (
            student_item.uses_remaining is None or
            (student_item.uses_remaining != -1 and student_item.uses_remaining <= 1)
        )
    )

    # 3. Mark as processing and create redemption transaction
    try:
        audit_guard = {'inserted': False}
        if will_create_request:
            _append_redemption_audit_log(
                student_item=student_item,
                student=student,
                teacher_id=teacher_id_for_audit,
                action='request',
                notes=details,
                guard_state=audit_guard,
                fallback_block=fallback_block,
            )

        # Handle bundle items differently
        if student_item.is_from_bundle:
            # Decrement bundle_remaining
            student_item.bundle_remaining -= 1
            if student_item.bundle_remaining == 0:
                student_item.status = 'redeemed'  # All uses consumed
            student_item.redemption_date = utc_now()
            if student_item.redemption_details:
                student_item.redemption_details += f"\n---\n{details}"
            else:
                student_item.redemption_details = details
        elif student_item.uses_remaining is not None:
            # Multi-use item (Rent Per-Use with limit > 1) or unlimited (-1)
            # Don't decrement if unlimited
            if student_item.uses_remaining != -1:
                student_item.uses_remaining -= 1
                if student_item.uses_remaining <= 0:
                    # Last use - mark as processing (if requires approval) or completed/redeemed
                    # Assuming rent per-use items are 'delayed' type (request redemption)
                    student_item.status = 'processing'
                else:
                    # Still has uses remaining - keep status as 'purchased' so it remains in "My Items"
                    pass

            student_item.redemption_date = utc_now()
            if student_item.uses_remaining == -1:
                uses_msg = "unlimited uses remaining"
            else:
                uses_msg = f"{student_item.uses_remaining} uses remaining"
            
            if student_item.redemption_details:
                student_item.redemption_details += f"\n---\n{details} ({uses_msg})"
            else:
                student_item.redemption_details = f"{details} ({uses_msg})"
        else:
            # Regular item - mark as processing
            student_item.status = 'processing'
            student_item.redemption_date = utc_now()
            student_item.redemption_details = details

        # Log the redemption event through Ledger without changing monetary balance.
        if student_item.class_id:
            create_pending_transaction(
                seat_id=student_item.seat_id,
                class_id=student_item.class_id,
                teacher_id=teacher_id_for_audit,
                amount=Decimal('0.00'),
                account_type='checking',
                type='redemption',
                description=f"Used: {student_item.store_item.name}" + (f" (bundle: {student_item.bundle_remaining} remaining)" if student_item.is_from_bundle else "")
            )
        # FEAT wrapper owns commit/rollback boundaries; keep mutations in the open transaction.
        db.session.flush()

        if student_item.is_from_bundle:
            return jsonify({"status": "success", "message": f"You have used 1 from your bundle of {student_item.store_item.name}. {student_item.bundle_remaining} uses remaining."})
        elif student_item.uses_remaining is not None:
            if student_item.uses_remaining == -1:
                return jsonify({"status": "success", "message": f"You have used {student_item.store_item.name}. Unlimited uses remaining."})
            elif student_item.uses_remaining > 0:
                return jsonify({"status": "success", "message": f"You have used {student_item.store_item.name}. {student_item.uses_remaining} uses remaining."})
            else:
                return jsonify({"status": "success", "message": f"You have requested to use {student_item.store_item.name}. Awaiting admin approval."})
        else:
            return jsonify({"status": "success", "message": f"You have requested to use {student_item.store_item.name}. Awaiting admin approval."})

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.session.rollback()
        current_app.logger.error(f"Item use failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred. Please try again."}), 500


@api_bp.route('/approve-redemption', methods=['POST'])
@admin_required
@feat_shell("FEAT-STOR-006")
def approve_redemption():
    """
    Approve a pending redemption request.

    Validation and scope checks run as pure reads in the route body; the actual
    state mutation is delegated to FEAT-STOR-006. The FEAT shell owns the
    transaction boundary — any exception raised below this point (other than
    the explicitly caught RedemptionDispositionError business error) will
    trigger a rollback at the shell. Infrastructure errors are NOT swallowed
    here; they propagate to Flask's error handler.
    """
    data = request.get_json(silent=True) or {}
    student_item_id = data.get('student_item_id')

    if not student_item_id:
        return jsonify({"status": "error", "message": "Missing student item ID."}), 400

    student_item = db.session.get(StudentItem, student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    has_membership = _admin_has_class_scope(current_admin.id, student_item.class_id)
    if not has_membership:
        return jsonify({"status": "error", "message": "You do not have access to this class."}), 403

    if not student_item.store_item.class_id or student_item.store_item.class_id != student_item.class_id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    if not _admin_has_class_scope(current_admin.id, student_item.store_item.class_id):
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        result = execute_redemption_approval(
            student_item=student_item,
            actor_teacher_id=current_admin.id,
            notes=student_item.redemption_details,
        )
    except RedemptionDispositionError as e:
        # Business-rule failure (e.g., concurrent state change). Map to 409.
        current_app.logger.info(
            "Redemption approval rejected by FEAT for student_item %s: %s",
            student_item_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": "Redemption request is no longer pending and cannot be approved.",
        }), 409

    return jsonify({"status": "success", "message": result.message})


@api_bp.route('/reject-redemption', methods=['POST'])
@admin_required
@feat_shell("FEAT-STOR-006")
def reject_redemption():
    """
    Reject a pending redemption request and refund the student.

    Validation and scope checks run as pure reads in the route body; the actual
    state mutation (audit log, refund transaction, item status change) is
    delegated to FEAT-STOR-006. The FEAT shell owns the transaction boundary
    and rollback semantics. RedemptionDispositionError is the only exception
    converted into a structured response; infrastructure errors propagate.
    """
    data = request.get_json(silent=True) or {}
    student_item_id = data.get('student_item_id')

    if not student_item_id:
        return jsonify({"status": "error", "message": "Missing student item ID."}), 400

    student_item = db.session.get(StudentItem, student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    # SECURITY: Verify the current admin has class scope for this store item
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    if not student_item.store_item.class_id or student_item.store_item.class_id != student_item.class_id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    if not _admin_has_class_scope(current_admin.id, student_item.store_item.class_id):
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        result = execute_redemption_rejection(
            student_item=student_item,
            actor_teacher_id=current_admin.id,
            notes=student_item.redemption_details,
        )
    except RedemptionDispositionError as e:
        current_app.logger.info(
            "Redemption rejection refused by FEAT for student_item %s: %s",
            student_item_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": "Redemption request could not be rejected in its current state.",
        }), 409

    return jsonify({"status": "success", "message": result.message})


# -------------------- HALL PASS API --------------------

@api_bp.route('/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
@feat_shell("FEAT-ATTN-001")
def handle_hall_pass_action(pass_id, action):
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Pass not found."}), 404
    if not log_entry.class_id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404
    class_scope = ClassEconomy.query.filter_by(class_id=log_entry.class_id).first()
    if not class_scope or class_scope.teacher_id != current_admin.id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404
    now = utc_now()
    try:
        if action == 'approve':
            result = feat_approve_hall_pass(log_entry=log_entry, now_utc=now)
            return jsonify({"status": "success", "message": result.message})
        if action == 'reject':
            result = feat_reject_hall_pass(log_entry=log_entry, now_utc=now)
            return jsonify({"status": "success", "message": result.message})
        if action == 'leave':
            result = feat_leave_hall_pass(log_entry=log_entry, now_utc=now)
            return jsonify({"status": "success", "message": result.message})
        if action == 'return':
            result = feat_return_hall_pass(log_entry=log_entry, now_utc=now)
            return jsonify({"status": "success", "message": result.message})
    except ValueError as exc:
        _log_api_client_error("handle_hall_pass_action", exc, extra=f"action={action}")
        safe_messages = {
            "approve": "Hall pass cannot be approved in its current state.",
            "reject": "Hall pass cannot be rejected in its current state.",
            "leave": "Hall pass cannot be checked out in its current state.",
            "return": "Hall pass cannot be checked in in its current state.",
        }
        return jsonify({"status": "error", "message": safe_messages.get(action, "Invalid action.")}), 400

    return jsonify({"status": "error", "message": "Invalid action."}), 400



def _get_default_timezone():
    """Return the configured default timezone or fall back to Pacific Time."""
    return get_timezone(current_app.config.get('DEFAULT_TIMEZONE'))


def _check_simultaneous_pass_limit(log_entry):
    """Validate destination settings and simultaneous pass limits."""
    from app.models import ClassEconomy
    economy = ClassEconomy.query.filter_by(class_id=log_entry.class_id).first()
    teacher_id = economy.teacher_id if economy else None
    if not teacher_id:
        return None

    settings = _get_or_create_hall_pass_settings(log_entry.class_id)
    if not settings:
        return None

    pass_types = settings.get_pass_types()

    # Find configuration for this destination
    pass_type_config = next((pt for pt in pass_types if pt['name'].lower() == log_entry.reason.lower()), None)

    # Check if pass type is enabled
    if pass_type_config and not pass_type_config.get('enabled', True):
        return jsonify({
            "status": "error",
            "message": f"{log_entry.reason} pass type is currently disabled."
        }), 403

    # Check simultaneous limit
    if pass_type_config and pass_type_config.get('simultaneous_limit') is not None:
        if log_entry.class_id:
            today_start_utc, _ = get_class_today_range(log_entry.class_id, reference_time_utc=utc_now())
        else:
            today_start_utc, _ = day_bounds_utc()
        today_start_db = normalize_for_db(today_start_utc)

        # Count currently out students for THIS destination from today (excluding this student)
        currently_out = HallPassLog.query.filter(
            HallPassLog.status == 'left',
            HallPassLog.reason == log_entry.reason,
            HallPassLog.class_id == log_entry.class_id,
            HallPassLog.left_time >= today_start_db,
            HallPassLog.id != log_entry.id  # Exclude current pass
        ).count()

        simultaneous_limit = pass_type_config['simultaneous_limit']

        # Check if limit is reached
        if currently_out >= simultaneous_limit:
            return jsonify({
                "status": "error",
                "message": (
                    f"{log_entry.reason} limit reached. {currently_out}/{simultaneous_limit} students are "
                    "currently out. Please wait for someone to return."
                )
            }), 403

    return None


def _enforce_hall_pass_student_context(student, log_entry):
    """
    Enforce active student class context for hall-pass state mutations.

    Class context is required and must match the pass class/join scope.
    """
    current_class_id = get_current_class_id()
    if not current_class_id:
        context = resolve_canonical_context()
        current_class_id = context.get("class_id") if context else None

    if not current_class_id:
        # Legacy sessions may only pin join_code; treat that as invalid for mutation context.
        if session.get("current_join_code"):
            return jsonify({
                "status": "error",
                "message": "This pass belongs to a different class context. Switch class and retry.",
            }), 403
        # Canonical fallback for sessions with no class selected:
        # ownership is already enforced by student_id match above, so allow class-scoped pass rows.
        if log_entry.class_id:
            return None
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




@api_bp.route('/hall-pass/cancel/<int:pass_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-ATTN-002")
def cancel_hall_pass(pass_id):
    """Allow students to cancel their pending hall pass request"""
    seat = get_current_seat()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()
    log_entry = db.get_or_404(HallPassLog, pass_id)

    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error

    try:
        result = feat_cancel_hall_pass(log_entry=log_entry, now_utc=utc_now())
        return jsonify({"status": "success", "message": result.message})
    except ValueError as exc:
        _log_api_client_error("cancel_hall_pass", exc, extra=f"pass_id={pass_id}")
        return jsonify({
            "status": "error",
            "message": _safe_exception_message(
                exc,
                "Hall pass cannot be cancelled in its current state.",
                allowed_messages={"Only pending passes can be cancelled."},
            ),
        }), 400


@api_bp.route('/hall-pass/checkout', methods=['POST'])
@login_required
@feat_shell("FEAT-ATTN-002")
def checkout_hall_pass():
    """Allow student to check out with their approved hall pass (replaces terminal use)"""
    seat = get_current_seat()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKOUT_DEBUG: student_id=%s pass_id=%s pass_student_id=%s pass_seat_id=%s pass_class_id=%s pass_join_code=%s session_class_id=%s session_join_code=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.student_id,
        log_entry.seat_id,
        log_entry.class_id,
        log_entry.join_code,
        session.get("current_class_id"),
        session.get("current_join_code"),
    )
    
    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error

    limit_response = _check_simultaneous_pass_limit(log_entry)
    if limit_response:
        return limit_response
    now = utc_now()
    try:
        result = feat_checkout_hall_pass(student=student, log_entry=log_entry, now_utc=now)
        return jsonify({
            "status": "success",
            "message": result.message,
            "destination": result.destination,
            "left_time": result.left_time_iso,
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKOUT_IDENTITY_MISSING: student_id=%s pass_id=%s message=%s",
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
@feat_shell("FEAT-ATTN-002")
def checkin_hall_pass():
    """Allow student to check in from their hall pass (replaces terminal return)"""
    seat = get_current_seat()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKIN_DEBUG: student_id=%s pass_id=%s pass_student_id=%s pass_seat_id=%s pass_class_id=%s pass_join_code=%s session_class_id=%s session_join_code=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.student_id,
        log_entry.seat_id,
        log_entry.class_id,
        log_entry.join_code,
        session.get("current_class_id"),
        session.get("current_join_code"),
    )
    
    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error
    
    now = utc_now()
    try:
        result = feat_checkin_hall_pass(student=student, log_entry=log_entry, now_utc=now)
        return jsonify({
            "status": "success",
            "message": result.message,
            "return_time": result.return_time_iso,
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKIN_IDENTITY_MISSING: student_id=%s pass_id=%s message=%s",
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
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401

    join_code = (session.get("current_join_code") or "").strip()
    class_id = (session.get("current_class_id") or "").strip()
    if not join_code or not class_id:
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
@feat_shell("FEAT-ATTN-001")
def update_hall_pass_settings():
    """Update hall pass queue settings (admin only)."""
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401
    scoped_admin_id = current_admin.id

    join_code = (session.get("current_join_code") or "").strip()
    class_id = (session.get("current_class_id") or "").strip()
    if not join_code or not class_id:
        return jsonify({"status": "error", "message": "Class context is required"}), 400

    data = request.get_json() or {}
    try:
        settings = feat_update_hall_pass_queue_settings(
            teacher_id=scoped_admin_id,
            class_id=class_id,
            join_code=join_code,
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

        # Get filter parameters
        period = request.args.get('period', '').strip()
        pass_type = request.args.get('type', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        # Get student IDs that the current admin can access (tenant-scoped)
        # Includes both primary ownership and shared students
        student_ids_subquery = (
            get_admin_student_query(include_unassigned=False)
            .with_entities(Student.id)
            .subquery()
        )
        # Build query with tenant scoping
        current_admin = get_current_admin()
        if not current_admin:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        scoped_admin_id = current_admin.id
        query = _apply_admin_class_scope(
            HallPassLog.query,
            HallPassLog,
            scoped_admin_id,
            sa.select(student_ids_subquery),
        )

        # Enforce single-class context for admin history views.
        current_class_id = (session.get("current_class_id") or "").strip()
        if current_class_id:
            query = query.filter(HallPassLog.class_id == current_class_id)

        # Apply filters
        if period:
            query = query.filter(HallPassLog.period == period)

        if pass_type:
            query = query.filter(HallPassLog.reason == pass_type)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_datetime, _ = local_date_bounds_utc(start_day)
                query = query.filter(HallPassLog.request_time >= start_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                next_day = end_day + timedelta(days=1)
                next_day_start_utc, _ = local_date_bounds_utc(next_day)
                query = query.filter(HallPassLog.request_time < next_day_start_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Order by most recent first
        query = query.order_by(HallPassLog.request_time.desc())

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
            records_data.append({
                "id": record.id,
                "student_name": record.student.full_name if record.student else "Unknown",
                "period": record.period,
                "reason": record.reason,
                "status": record.status,
                "request_time": format_timestamp(record.request_time),
                "decision_time": format_timestamp(record.decision_time),
                "left_time": format_timestamp(record.left_time),
                "return_time": format_timestamp(record.return_time)
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
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401
    teacher_id = current_admin.id
    current_class_id = get_current_class_id()
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400
    class_row = ClassEconomy.query.filter_by(class_id=current_class_id).first()
    join_code = class_row.join_code if class_row else None
    if not join_code:
        return jsonify({"status": "error", "message": "Class scope not found"}), 404

    scope = _get_hall_pass_settings_scope(teacher_id, join_code)
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
@feat_shell("FEAT-ATTN-001")
def save_hall_pass_setup():
    """Save teacher's hall pass configuration"""
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401
    scoped_admin_id = current_admin.id
    data = request.get_json() or {}
    current_class_id = get_current_class_id()
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400
    class_row = ClassEconomy.query.filter_by(class_id=current_class_id).first()
    join_code = class_row.join_code if class_row else None
    if not join_code:
        return jsonify({"status": "error", "message": "Class scope not found"}), 404

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
        scope = _get_hall_pass_settings_scope(scoped_admin_id, join_code)
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
            teacher_id=scoped_admin_id,
            class_id=scope["class_id"],
            join_code=scope["join_code"],
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
@feat_shell("FEAT-ATTN-001")
def rotate_hall_pass_verify_token():
    """
    Rotate the teacher's hall pass public verification token.

    Generates a new 256-bit random token and overwrites the old one.
    The old token is immediately invalid. Use after a lost pass, suspicious
    traffic, or student screenshot concern.
    """
    current_admin = get_current_admin()
    if not current_admin:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401
    teacher_id = current_admin.id

    try:
        token = feat_rotate_teacher_hall_pass_verify_token(teacher_id=teacher_id)
    except LookupError as exc:
        _log_api_client_error("rotate_hall_pass_verify_token", exc, extra=f"teacher_id={teacher_id}")
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
    if request.args.get('teacher_public_id'):
        return jsonify({
            "status": "error",
            "message": "teacher_public_id is not supported"
        }), 400

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
    """Return active/recent hall passes for one class-scoped teacher seat."""
    actor_public_id = (request.args.get('actor') or '').strip()
    class_id = (request.args.get('class_id') or '').strip()
    if not actor_public_id or not class_id:
        return jsonify({"status": "error", "message": "actor and class_id are required"}), 400

    teacher_seat = Seat.query.filter_by(
        public_id=actor_public_id,
        class_id=class_id,
        role="teacher",
    ).first()
    if not teacher_seat:
        return jsonify({"status": "error", "message": "Teacher seat not found"}), 404

    passes = (
        HallPassLog.query
        .filter(HallPassLog.class_id == class_id)
        .order_by(HallPassLog.request_time.desc())
        .all()
    )

    return jsonify({
        "status": "success",
        "passes": [
            {
                "id": log.id,
                "student_id": log.student_id,
                "destination": log.reason,
                "status": log.status,
                "join_code": log.join_code,
            }
            for log in passes
        ],
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
        period = request.args.get('period', '').strip()
        block = request.args.get('block', '').strip()
        status = request.args.get('status', '').strip()  # 'active' or 'inactive'
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        current_admin = get_current_admin()
        if current_admin is None:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        scoped_admin_id = current_admin.id

        # Get student IDs that the current admin can access (tenant-scoped)
        accessible_student_ids_query = get_admin_student_query(include_unassigned=False).with_entities(Student.id)
        # Build query scoped to admin's students and exclude deleted records
        query = _apply_admin_class_scope(
            TapEvent.query.filter(TapEvent.is_deleted.is_(False)),
            TapEvent,
            scoped_admin_id,
            accessible_student_ids_query,
        )
        current_class_id = (session.get("current_class_id") or "").strip()
        if current_class_id:
            query = query.filter(TapEvent.class_id == current_class_id)

        # Suppress duplicate auto tap-outs from known race conditions.
        # Keep only the earliest row when daily-limit inactive events are otherwise identical.
        duplicate_tap = aliased(TapEvent)
        query = query.filter(~sa.and_(
            TapEvent.status == 'inactive',
            or_(
                TapEvent.reason_code == TapEventReasonCode.DAILY_LIMIT,
                sa.and_(
                    TapEvent.reason_code.is_(None),
                    TapEvent.reason.like('Daily limit%')
                )
            ),
            sa.exists(
                sa.select(1).where(
                    sa.and_(
                        duplicate_tap.seat_id == TapEvent.seat_id,
                        duplicate_tap.class_id == TapEvent.class_id,
                        duplicate_tap.period == TapEvent.period,
                        duplicate_tap.status == TapEvent.status,
                        duplicate_tap.reason == TapEvent.reason,
                        duplicate_tap.timestamp == TapEvent.timestamp,
                        duplicate_tap.is_deleted.is_(False),
                        duplicate_tap.id < TapEvent.id
                    )
                )
            )
        ))

        # Apply filters
        if period:
            query = query.filter(TapEvent.period == period)

        if status:
            query = query.filter(TapEvent.status == status)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_datetime, _ = local_date_bounds_utc(start_day, timezone_name='UTC')
                query = query.filter(TapEvent.timestamp >= normalize_for_db(start_datetime))
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                _, end_datetime = local_date_bounds_utc(end_day, timezone_name='UTC')
                query = query.filter(TapEvent.timestamp <= normalize_for_db(end_datetime))
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        from app.models import Seat
        # Filter by block (need to join with Seat)
        if block:
            query = query.join(Seat, TapEvent.seat_id == Seat.id)
            query = query.filter(TapEvent.period == block)

        # Order by most recent first
        query = query.order_by(TapEvent.timestamp.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Build seat lookup for names and blocks without loading full Seat entities.
        seat_ids = [r.seat_id for r in records if r.seat_id]
        seats = {}
        if seat_ids:
            seat_rows = db.session.query(Seat.id, Seat.student_id, Seat.block).filter(Seat.id.in_(seat_ids)).all()
            student_ids = list({row.student_id for row in seat_rows if row.student_id})
            students_by_id = {}
            if student_ids:
                student_rows = Student.query.filter(Student.id.in_(student_ids)).all()
                students_by_id = {student.id: student for student in student_rows}

            period_by_seat_id = {}
            for record in records:
                if record.seat_id and record.seat_id not in period_by_seat_id:
                    period_by_seat_id[record.seat_id] = record.period

            for row in seat_rows:
                student = students_by_id.get(row.student_id)
                student_name = student.full_name if student else "Unknown"
                student_block = period_by_seat_id.get(row.id) or row.block or "Unknown"
                seats[row.id] = {"name": student_name, "block": student_block}

        # Get class labels for blocks
        blocks_in_records = set(seats[sid]['block'] for sid in seats if seats[sid]['block'])
        class_labels = {}
        if blocks_in_records:
            classes = ClassEconomy.query.filter(
                ClassEconomy.teacher_id == scoped_admin_id
            ).all()
            for c in classes:
                block_name = (c.display_name or '').strip().upper()
                class_labels[block_name] = c.display_name or c.join_code

        # Format records for response
        records_data = []
        for record in records:
            seat_info = seats.get(record.seat_id, {'name': 'Unknown', 'block': 'Unknown'})
            student_block = seat_info['block']
            student_class_label = class_labels.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown'

            # Format timestamp as UTC with 'Z' suffix
            timestamp_str = None
            if record.timestamp:
                timestamp_str = ensure_utc(record.timestamp).isoformat().replace('+00:00', 'Z')

            records_data.append({
                "id": record.id,
                "seat_id": record.seat_id,
                "student_name": seat_info['name'],
                "student_block": student_block,
                "student_class_label": student_class_label,
                "period": record.period,
                "status": record.status,
                "reason": record.reason if record.reason else None,
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
@feat_shell("FEAT-ATTN-002")
def handle_tap():
    data = request.get_json()
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    current_app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    seat = get_current_seat()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()

    if not student:
        current_app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not check_password_hash(student.pin_hash or '', pin):
        current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student.id}")
        return jsonify({"error": "Invalid PIN"}), 403


    student_blocks_raw = [b.strip() for b in student.block.split(',') if b.strip()] if student and isinstance(student.block, str) else []
    block_lookup = {b.upper(): b for b in student_blocks_raw}
    valid_periods = list(block_lookup.keys())
    period = data.get("period", "").upper()
    action = data.get("action")

    current_app.logger.info(f"TAP DEBUG: valid_periods={valid_periods}, period={period}, action={action}")

    # Support both old and new action names
    action_map = {
        "tap_in": "start_work",
        "tap_out": "stop_work",
        "start_work": "start_work",
        "stop_work": "stop_work"
    }

    if period not in valid_periods or action not in action_map:
        current_app.logger.warning(f"TAP ERROR: Invalid period or action: period={period}, valid_periods={valid_periods}, action={action}")
        return jsonify({"error": "Invalid period or action"}), 400

    # Normalize action to new terminology
    normalized_action = action_map[action]

    context = resolve_canonical_context()
    class_id = context.get("class_id") if context else get_current_class_id()
    if not class_id:
        current_app.logger.warning("TAP ERROR: Missing class_id context for student_id=%s", student.id)
        return jsonify({"error": "Unable to resolve class context for this period."}), 400

    seat_id = seat.id if seat and seat.class_id == class_id else get_seat_id_for_class(student.id, class_id)
    if not seat_id:
        return jsonify({"error": "No seat assigned in this class."}), 403

    seat_row = db.session.get(Seat, seat_id)
    if seat_row and (seat_row.block_identifier or seat_row.block):
        seat_period = (seat_row.block_identifier or seat_row.block or "").upper()
        if seat_period and period != seat_period:
            return jsonify({"error": "Invalid period or action"}), 400

    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    join_code = economy.join_code if economy else None

    now = utc_now()

    if not seat_id or not class_id:
        return jsonify({"error": "No seat assigned in this class."}), 403

    # --- Check if tap is enabled for this student in this period ---
    student_block = feat_get_or_create_student_block(
        student_id=student.id,
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        tap_enabled=True,
    )

    # Check if tap is disabled for this period
    if not student_block.tap_enabled:
        return jsonify({"error": "Start Work / Break is currently disabled for this period."}), 403

    # --- Check "done for the day" lock ---
    if normalized_action == "start_work":
        today_local = get_class_now(class_id, reference_time_utc=now).date()
        att_state = SeatAttendanceState.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            period=period,
        ).first()
        done_date = att_state.done_for_day_date if att_state else None
        if done_date is not None and done_date < today_local:
            if att_state:
                att_state.done_for_day_date = None
            db.session.flush()
            done_date = None
        if done_date == today_local:
            return jsonify({"error": "You are done for the day. You cannot Start Work again until tomorrow."}), 403


    # --- Hall Pass Logic for Stop Work ---
    if normalized_action == 'stop_work':
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "A reason is required for a hall pass."}), 400

        # Special case for "Done for the day" - this is the old "tap out" behavior
        if reason.lower() in ['done', 'done for the day']:
            # Fall through to the standard TapEvent creation logic below
            pass
        else:
            policy_guard = feat_check_hall_pass_request_policy(
                student=student,
                class_id=class_id,
                join_code=join_code,
                period=period,
                reason=reason,
                now_utc=now,
            )
            if not policy_guard.allowed:
                return jsonify({"error": policy_guard.message}), policy_guard.status_code
            teacher_id = policy_guard.teacher_id
            if not teacher_id:
                return jsonify({"error": "Unable to resolve class context."}), 400
            should_require_pass = policy_guard.should_require_pass

            # Keep hall-pass rent grants in sync for the active rent coverage period.
            # This applies the monthly top-off model even if the student paid rent earlier.
            context = {'join_code': join_code, 'block': period, 'teacher_id': teacher_id}
            if should_require_pass and context:
                _, _, hall_pass_reconciled = _ensure_rent_hall_pass_top_off(student, context)
                if hall_pass_reconciled:
                    db.session.flush()

            if should_require_pass and student.hall_passes <= 0:
                return jsonify({"error": "Insufficient hall passes."}), 400

            hall_pass_log = feat_request_hall_pass(
                student=student,
                seat_id=seat_id,
                class_id=class_id,
                join_code=join_code,
                period=period,
                reason=reason,
                now_utc=now,
            )

            # Since the student is just requesting, they are still 'active'.
            # We need to return the current state to the UI.
            is_active = True
            last_payroll_time = get_last_payroll_time(seat_id=seat_id, class_id=class_id)
            duration = calculate_unpaid_attendance_seconds(seat_id, class_id, period, last_payroll_time)
            rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period), class_id=class_id)
            projected_pay = duration * rate_per_second

            db.session.flush() # FEAT-AUTHORIZED-SHELL
            return jsonify({
                "status": "ok",
                "message": "Hall pass requested.",
                "active": is_active,
                "duration": duration,
                "projected_pay": float(projected_pay),
                "hall_pass": {
                    "id": hall_pass_log.id,
                    "status": hall_pass_log.status,
                    "reason": hall_pass_log.reason
                }
            })

    # --- Standard Start/Stop Work Logic ---
    try:
        status = "active" if normalized_action == "start_work" else "inactive"
        reason = data.get("reason") if normalized_action == "stop_work" else None

        # Prevent duplicate tap-in or tap-out
        latest_state = SeatAttendanceState.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            period=period,
        ).first()
        if latest_state and ((latest_state.is_active and status == "active") or (not latest_state.is_active and status == "inactive")):
            current_app.logger.info(f"Duplicate {action} ignored for seat {seat_id} in period {period}")
            last_payroll_time = get_last_payroll_time(seat_id=seat_id, class_id=class_id)
            duration = calculate_unpaid_attendance_seconds(seat_id, class_id, period, last_payroll_time)
            db.session.flush() # FEAT-AUTHORIZED-SHELL
            return jsonify({
                "status": "ok",
                "active": latest_state.is_active,
                "duration": duration
            })

        if normalized_action == "start_work":
            daily_limit_guard = feat_check_start_work_daily_limit(
                student_id=student.id,
                seat_id=seat_id,
                class_id=class_id,
                period=period,
                now_utc=now,
                logger=current_app.logger,
            )
            if not daily_limit_guard.allowed:
                return jsonify({"error": daily_limit_guard.message}), daily_limit_guard.status_code

        feat_apply_standard_tap_mutations(
            student=student,
            student_block=student_block,
            seat_id=seat_id,
            class_id=class_id,
            join_code=join_code,
            period=period,
            normalized_action=normalized_action,
            reason=reason,
            valid_periods=valid_periods,
            now_utc=now,
            logger=current_app.logger,
        )
        current_app.logger.info(f"TAP success - seat {seat_id} {period} {action}")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for seat {seat_id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    # Fetch latest status and unpaid duration for the tapped period
    latest_state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
    ).first()
    is_active = latest_state.is_active if latest_state else False
    last_payroll_time = get_last_payroll_time(seat_id=seat_id, class_id=class_id)
    duration = calculate_unpaid_attendance_seconds(seat_id, class_id, period, last_payroll_time)

    rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period), class_id=class_id)
    projected_pay = duration * rate_per_second

    db.session.flush()
    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": float(projected_pay)
    })


@api_bp.route('/admin/tap-entries/<int:student_id>', methods=['GET'])
def get_tap_entries(student_id):
    """
    Get all tap entries for a student with pairing validation.
    Returns entries grouped by period with pairing status.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import TapEvent
    from app.auth import get_student_for_admin, get_admin_student_query

    # SECURITY FIX: Use scoped helper to verify admin owns this student
    student = get_student_for_admin(student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    active_class_id = get_current_class_id()
    if not active_class_id:
        return jsonify({"error": "Class context unavailable"}), 404

    has_class_scope = _admin_has_class_scope(admin.id, active_class_id)
    if not has_class_scope:
        return jsonify({"error": "Student not found or access denied"}), 404

    has_student_membership = db.session.query(
        sa.exists().where(
            sa.and_(
                ClassMembership.class_id == active_class_id,
                ClassMembership.student_id == student_id,
                ClassMembership.role == 'student',
            )
        )
    ).scalar()
    if not has_student_membership:
        return jsonify({"error": "Student not found or access denied"}), 404

    accessible_student_ids_query = get_admin_student_query(include_unassigned=False).with_entities(Student.id)

    # Get all tap events for this student in active class scope.
    query = TapEvent.query
    query = query.filter(TapEvent.student_id == student_id, TapEvent.class_id == active_class_id)

    events = (
        _apply_admin_class_scope(
            query,
            TapEvent,
            admin.id,
            accessible_student_ids_query,
        )
        .order_by(TapEvent.period, TapEvent.timestamp.asc())
        .all()
    )

    # Group by period and validate pairing
    periods = {}
    for event in events:
        if event.period not in periods:
            periods[event.period] = []
        periods[event.period].append({
            'id': event.id,
            'status': event.status,
            'timestamp': event.timestamp.isoformat() if event.timestamp else None,
            'reason': event.reason,
            'is_deleted': event.is_deleted,
            'deleted_at': event.deleted_at.isoformat() if event.deleted_at else None
        })

    # Validate pairing for each period
    period_data = {}
    for period, events_list in periods.items():
        # Filter out deleted events for pairing validation
        active_events = [e for e in events_list if not e['is_deleted']]

        # Check for unpaired entries
        unpaired = []
        expected_status = 'active'
        for event in active_events:
            if event['status'] == expected_status:
                expected_status = 'inactive' if expected_status == 'active' else 'active'
            else:
                unpaired.append(event['id'])

        # If we end on 'active', the last event is unpaired (student still tapped in)
        if active_events and active_events[-1]['status'] == 'active':
            # This is actually valid (student is currently working), remove from unpaired
            if active_events[-1]['id'] in unpaired:
                unpaired.remove(active_events[-1]['id'])

        period_data[period] = {
            'events': events_list,
            'unpaired_event_ids': unpaired,
            'is_valid': len(unpaired) == 0
        }

    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'periods': period_data
    })


@api_bp.route('/admin/tap-entries/<int:event_id>', methods=['DELETE'])
@feat_shell("FEAT-ATTN-001")
def delete_tap_entry(event_id):
    """
    Soft-delete a tap entry by marking it as deleted.
    Only allows deletion of unpaired or invalid entries.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import TapEvent
    from app.auth import get_student_for_admin, get_admin_student_query

    event = TapEvent.query.filter(TapEvent.id == event_id).first()
    if not event:
        return jsonify({"error": "Tap entry not found"}), 404

    active_class_id = get_current_class_id()
    if not active_class_id:
        return jsonify({"error": "Class context unavailable"}), 404

    if not event.class_id:
        return jsonify({"error": "Tap entry not found"}), 404
    if event.class_id != active_class_id:
        return jsonify({"error": "Access denied"}), 403

    if not _admin_has_class_scope(admin.id, event.class_id):
        return jsonify({"error": "Tap entry not found"}), 404

    # SECURITY FIX: Use scoped helper to verify admin owns this student
    student = get_student_for_admin(event.student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    feat_soft_delete_tap_entry(event=event, admin_id=admin.id, deleted_at=utc_now())

    current_app.logger.info(f"Admin {admin.id} deleted tap entry {event_id} for student {event.student_id}")

    return jsonify({
        "status": "ok",
        "message": "Tap entry deleted successfully"
    })


@api_bp.route('/admin/student-block-settings', methods=['POST'])
@feat_shell("FEAT-ATTN-001")
def update_student_block_settings():
    """
    Update StudentBlock settings (tap_enabled toggle) for a student-period combination.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    student_id = data.get('student_id')
    period = data.get('period', '').upper()
    tap_enabled = data.get('tap_enabled')

    if not student_id or not period or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400

    from app.auth import get_student_for_admin

    # SECURITY FIX: Use scoped helper AND removed deprecated teacher_id check
    student = get_student_for_admin(student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    # Resolve seat_id and class_id for V2 identity
    seat = Seat.query.join(ClassEconomy, Seat.class_id == ClassEconomy.class_id).filter(
        ClassEconomy.teacher_id == admin.id,
        Seat.student_id == student_id,
        Seat.claimed_at.isnot(None),
        func.upper(Seat.block) == period,
    ).first()

    if not seat or not seat.class_id:
        return jsonify({"error": "Student block not found or access denied"}), 403

    class_id = seat.class_id
    seat_id = seat.id

    try:
        feat_set_student_block_tap_enabled(
            student_id=student_id,
            seat_id=seat_id,
            class_id=class_id,
            period=period,
            tap_enabled=tap_enabled,
        )
    except PermissionError:
        return jsonify({"error": "Student block not found or access denied"}), 403

    current_app.logger.info(f"Admin {admin.id} set tap_enabled={tap_enabled} for student {student_id} period {period}")

    return jsonify({
        "status": "ok",
        "tap_enabled": tap_enabled
    })


def check_and_auto_tapout_if_limit_reached(student, commit=True):
    """
    Checks if an active student has reached their daily limit and auto-taps them out.
    This function should be called periodically (e.g., during status checks).
    Daily limits reset at midnight in the effective class timezone.
    
    Args:
        student: Student model instance
        commit: Whether to commit the transaction immediately (default: True).
                Set to False if calling in a loop to batch commits.
    """
    try:
        feat_enforce_daily_limits(
            student=student,
            commit=commit,
            logger=current_app.logger,
        )
    except Exception as e:
        if commit:
            db.session.rollback()
        current_app.logger.error(f"Failed to auto-tap-out student {student.id}: {e}")
        if not commit:
            raise


@api_bp.route('/student-status', methods=['GET'])
@login_required
def student_status():
    from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

    student = get_logged_in_student()

    context = resolve_canonical_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    class_id = context.get("class_id")
    if not class_id:
        return jsonify({"status": "error", "message": "Class context unavailable."}), 400

    period_states = get_all_block_statuses(student, class_id=class_id)

    # Convert Decimal values to float for JSON serialization
    for state in period_states.values():
        if 'projected_pay' in state and state['projected_pay'] is not None:
            state['projected_pay'] = float(state['projected_pay'])

    return jsonify({
        "status": "ok",
        "periods": period_states
    })


@api_bp.route('/student-status/reconcile', methods=['POST'])
@login_required
@feat_shell("FEAT-ATTN-002")
def reconcile_student_status():
    """Apply attendance-side mutations (daily-limit auto tap-out) explicitly via POST."""
    from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

    student = get_logged_in_student()
    if not student:
        return jsonify({"status": "error", "message": "Student not found."}), 404

    context = resolve_canonical_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    check_and_auto_tapout_if_limit_reached(student, commit=True)
    return jsonify({"status": "ok"})


# -------------------- UTILITY API --------------------

@api_bp.route('/set-timezone', methods=['POST'])
def set_timezone():
    """Store user's timezone in session for datetime formatting"""
    # Allow access if user is logged in as student OR admin
    is_authenticated = False
    now = utc_now()

    # Check Admin Session
    if get_current_admin() is not None:
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if (now - last_activity_dt) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass # Invalid date format, treat as unauthenticated
        else:
             # If no last_activity but is_admin is set, treat as active for now
             # (matches admin_required logic which would set it if missing)
             is_authenticated = True
             session['last_activity'] = now.isoformat()

    # Check System Admin Session (if not already authenticated)
    if not is_authenticated and get_current_system_admin() is not None:
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if (now - last_activity_dt) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass
        else:
            # If no last_activity but sysadmin_id is set, treat as active
            is_authenticated = True
            session['last_activity'] = now.isoformat()

    # Check Student Session (if not already authenticated as admin or sysadmin)
    if not is_authenticated and get_logged_in_student() is not None:
        login_time_str = session.get('login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                if (now - login_time) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass

    if not is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

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


@api_bp.route('/admin/block-tap-settings', methods=['GET'])
@admin_required
def get_block_tap_settings():
    """
    Get tap_enabled settings for all students in a specific block.
    Returns true if any student has tap enabled, false if all are disabled.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    block = request.args.get('block', '').strip().upper()
    if not block:
        return jsonify({"error": "Block parameter is required"}), 400
    
    from app.models import Student, StudentBlock
    from app.auth import get_admin_student_query
    
    # Resolve class_id for this admin and block
    class_row = ClassEconomy.query.filter(
        ClassEconomy.teacher_id == admin.id,
        func.upper(ClassEconomy.display_name) == block,
    ).first()
    
    if not class_row:
        return jsonify({"tap_enabled": True})
        
    class_id = class_row.class_id

    # Get all claimed seats for this admin, block, and class
    seats = Seat.query.filter(
        Seat.class_id == class_id,
        func.upper(Seat.block) == block,
        Seat.claimed_at.isnot(None)
    ).all()

    if not seats:
        # No claimed seats in this block, default to enabled
        return jsonify({"tap_enabled": True})
    
    # Check if tap is enabled for any seat in this block
    any_enabled = False
    for seat in seats:
        student_block = StudentBlock.query.filter_by(
            seat_id=seat.id,
            class_id=class_id,
            period=block,
        ).first()
        
        if student_block:
            if student_block.tap_enabled:
                any_enabled = True
                break
        else:
            # No StudentBlock record means tap is enabled by default
            any_enabled = True
            break
    
    return jsonify({"tap_enabled": any_enabled})


@api_bp.route('/admin/block-tap-settings', methods=['POST'])
@admin_required
@feat_shell("FEAT-ATTN-001")
def update_block_tap_settings():
    """
    Update tap_enabled settings for all students in a specific block/period.
    This sets the tap_enabled flag for all students in the specified block.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    block = data.get('block', '').strip().upper()
    tap_enabled = data.get('tap_enabled')
    
    if not block or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    from app.models import Student
    
    try:
        # Resolve class_id for this admin and block
        class_row = ClassEconomy.query.filter(
            ClassEconomy.teacher_id == admin.id,
            func.upper(ClassEconomy.display_name) == block,
        ).first()
        
        if not class_row:
            return jsonify({"status": "error", "message": "Class not found"}), 404
            
        class_id = class_row.class_id

        # Get all claimed seats for this admin, block, and class
        seats = Seat.query.filter(
            Seat.class_id == class_id,
            func.upper(Seat.block) == block,
            Seat.claimed_at.isnot(None)
        ).all()

        updated_count = 0
        for seat in seats:
            # Strict v2 scope: seat_id + class_id + period must match.
            feat_set_student_block_tap_enabled(
                student_id=seat.student_id,
                seat_id=seat.id,
                class_id=class_id,
                period=block,
                tap_enabled=tap_enabled,
            )
            updated_count += 1

        current_app.logger.info(
            f"Admin {admin.id} set tap_enabled={tap_enabled} for {updated_count} students in block {block}"
        )
        
        return jsonify({
            "status": "ok",
            "tap_enabled": tap_enabled,
            "updated_count": updated_count
        })
    
    except PermissionError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Class not found"}), 404
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating block tap settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to update tap settings"}), 500


@api_bp.route('/admin/view-as-student-status', methods=['GET'])
@admin_required
def view_as_student_status():
    """Get the current view-as-student mode status"""
    return jsonify({
        "status": "success",
        "view_as_student": session.get('view_as_student', False)
    })
