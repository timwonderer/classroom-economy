"""
Admin routes for Classroom Token Hub.

Contains all admin/teacher-facing functionality including dashboard, student management,
store management, insurance, payroll, attendance tracking, and data import/export.
"""

import csv
import io
import json
import os
import re
import base64
import math
import random
import string
import secrets
import threading
import qrcode
import hashlib
from types import SimpleNamespace
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from app.utils.time import (
    utc_now,
    ensure_utc,
    local_date_end_utc,
    local_date_bounds_utc,
    UTC_MIN,
    normalize_for_db,
    claim_period_bounds_utc,
    class_date,
    day_bounds_utc,
    get_class_now,
    get_timezone,
)
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, redirect, url_for, flash, request, session,
    jsonify, Response, send_file, current_app, abort, g
)
from urllib.parse import urljoin, urlparse
from sqlalchemy import desc, text, or_, and_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import sqlalchemy as sa
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import pyotp
import pytz
from werkzeug.exceptions import HTTPException, NotFound

from app.extensions import db, limiter
from app.feats.base import feat_shell, FEATContext, InvariantViolation
from app.access import AccessScopeDenied, resolve_scope
from app.models import (
    Student, Admin, ClassEconomy, StudentTeacher, Transaction, TransactionStatus, TapEvent, StoreItem, StudentItem,
    InsurancePolicy, InsurancePolicyBlock, RentItem, RentPayment, RentSettings, RentWaiver, StoreItemBlock,
    InsuranceEnrollment, StudentInsurance, InsuranceClaim, HallPassLog, HallPassSettings, PayrollSettings, SavedAdjustment,
    BankingSettings,
    UserReport, FeatureSettings, StudentBlock,
    Announcement, RedemptionAuditLog, RedemptionAuditAction,
    RedemptionAuditSource, Issue, IssueStatusHistory, IssueResolutionAction, AnalyticsSnapshot, AnalyticsEvent, Seat,
    BalanceCache, ClassMembership, ClassEconomy, EconomySnapshot, User, UserRole, _quantize_currency,
    SeatAttendanceState, TapEventReasonCode, IdentityProfile,
)
from app.auth import (
    admin_required,
    find_canonical_user_by_auth_username,
    get_admin_student_query,
    get_current_admin,
    get_current_user,
    get_student_for_admin,
    resolve_admin_shadow_for_user,
    set_canonical_user_session,
)
from app.forms import (
    AdminLoginForm, AdminSignupForm, AdminTOTPConfirmForm, AdminRecoveryForm, AdminResetCredentialsForm, StoreItemForm,
    InsurancePolicyForm, AdminClaimProcessForm, PayrollSettingsForm,
    ManualPaymentForm, BankingSettingsForm
)
# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso, generate_anonymous_code, render_template_with_fallback as render_template
from app.utils.store import refund_pending_collective_purchases
from app.utils.join_code import generate_join_code
from app.utils.economy_balance import EconomyBalanceChecker
from app.utils.economy_policy import (
    POLICY_MODES,
    convert_weekly_amount_to_frequency,
    get_class_feature_settings_for_class,
    get_insurance_premium_recommendation,
    get_class_feature_settings,
    get_feature_settings_row_for_class,
    get_price_recommendation_context,
    normalize_policy_mode,
    replace_enabled_class_features,
    resolve_class_scope,
    resolve_feature_class_for_class,
)
from app.utils.economy_rebalance import (
    REBALANCE_ACTIVATION_IMMEDIATE,
    REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL,
    REBALANCE_ACTIVATION_NEXT_RENEWAL,
    activate_due_rebalances,
    apply_rebalance_changes,
    cancel_pending_policy_transitions,
    get_pending_policy_transition_count,
    get_pending_policy_transition_effective_at,
    prepare_scheduled_rebalance_changes,
    queue_scheduled_policy_transitions,
)
from app.utils.claim_credentials import (
    compute_primary_claim_hash,
    match_claim_hash,
    normalize_claim_hash,
)
from app.utils.ip_handler import get_real_ip
from app.utils.turnstile import verify_turnstile_token
from app.utils.name_utils import hash_last_name_parts, verify_last_name_parts
from app.utils.help_content import HELP_ARTICLES
from app.utils.encryption import encrypt_totp, decrypt_totp
from app.utils.overdraft import charge_overdraft_fee_if_needed, evaluate_overdraft_allowance
from app.utils.passwordless_client import (
    create_register_token,
    verify_signin_token,
    get_public_api_key
)
from app.utils.admin_identity import (
    load_teacher_id_words,
    generate_teacher_public_id,
    generate_teacher_public_id_with_suffix,
)
from app.utils.display_name_session import (
    set_admin_display_name_cache,
    clear_admin_display_name_cache,
)
from app.utils.opaque_refs import make_opaque_ref, resolve_opaque_ref
from app.utils.auth_username import (
    normalize_auth_username,
    needs_hashed_username_migration,
    build_hashed_username_fields,
)
from app.utils.student_deletion import (
    hard_delete_student_if_orphaned,
    remove_student_from_teacher_scope,
)
from app.utils.seat_scope import get_seat_id_for_class, get_seat_ids_for_student_join, seat_scoped_filter, transaction_scope_filter
from app.utils.transaction_idempotency import create_idempotent_transaction, void_refund_key
from app.feats.admin_adjustment_feat import execute_admin_adjustments
from app.feats.attendance import student_tap
from app.feats.insurance_claim_feat import execute_insurance_claim_resolution
from app.feats.transaction_void_feat import execute_void_transaction
from app.hash_utils import get_random_salt, hash_hmac, hash_username, hash_username_lookup
from app.payroll import calculate_payroll_breakdown, get_cached_payroll_with_meta
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    get_batch_attendance_events,
    calculate_seconds_in_memory,
)
from app.utils.attendance_helpers import get_join_code_for_student_period
from app.services.balance_service import get_batch_balances_by_class_seat
from app.services import access_policy_service, ledger_service, obligations_service
from app.services import operational_event_service
from app.services.ledger_service import get_available_balances
from app.services.admin_identity_bridge_service import (
    admin_has_passkeys,
    create_admin_credential,
    create_legacy_completed_teacher_onboarding,
    delete_admin_credential,
    delete_admin_credentials_for_teacher,
    delete_teacher_onboarding_for_teacher,
    get_admin_credential,
    get_or_create_teacher_onboarding,
    get_teacher_onboarding,
    list_admin_credentials,
    set_teacher_onboarding_skipped,
    set_teacher_onboarding_widget_dismissed,
    set_teacher_onboarding_widget_task_status,
    touch_admin_credentials_last_used,
)
from app.services.recovery_bridge_service import (
    create_recovery_request_with_students,
    delete_recovery_rows_for_teacher,
    find_recovery_request_by_resume_pin,
    get_active_recovery_request_for_teacher,
    get_recovery_request_by_id,
    invalidate_recovery_codes,
    list_recovery_codes_for_request,
    mark_recovery_request_verified,
    save_recovery_progress,
)
from app.utils.insurance_eligibility import (
    collect_reimbursed_source_tx_ids,
    compute_waiting_end_class_for_enrollment,
    evaluate_claim_transaction_eligibility,
    resolve_claim_type,
    CLAIM_REASON_ALREADY_CLAIMED,
    CLAIM_REASON_DELAY_USE_EXPIRED,
    CLAIM_REASON_DELAY_USE_NOT_USED,
    CLAIM_REASON_HARD_DENY_CATEGORY,
    CLAIM_REASON_INTERNAL_TRANSFER,
    CLAIM_REASON_PREMIUM_NOT_CURRENT,
    CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS,
    CLAIM_REASON_TIME_LIMIT_EXCEEDED,
    CLAIM_REASON_UNCLASSIFIED_TRANSACTION,
    CLAIM_REASON_WAITING_PERIOD,
)
import time

# Join code generation constants
MAX_JOIN_CODE_RETRIES = 10  # Maximum attempts to generate a unique join code
FALLBACK_BLOCK_PREFIX_LENGTH = 1  # Number of characters from block name in fallback code
FALLBACK_CODE_MODULO = 10000  # Modulo for timestamp suffix (produces 4-digit number)


# Insurance form mapping for derived claim period storage
FREQUENCY_TO_CLAIM_PERIOD = {
    'weekly': 'week',
    'monthly': 'month',
    'semester': 'semester',
}
# Placeholder values for legacy class roster entries
LEGACY_PLACEHOLDER_CREDENTIAL = "LEGACY0"  # Placeholder credential for legacy classes
LEGACY_PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"  # Marks legacy placeholder entries
LEGACY_PLACEHOLDER_LAST_INITIAL = "P"  # "P" for Placeholder

# Module-level cache for schema table-name lookups (keyed by DB URL to be app-config safe).
_table_names_cache: dict[str, set[str]] = {}
_table_columns_cache: dict[tuple[str, str], set[str]] = {}
_table_names_cache_lock = threading.Lock()

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

_BANKING_REDIRECT_QUERY_KEYS = {
    "student",
    "block",
    "account",
    "type",
    "start_date",
    "end_date",
    "page",
    "settings_block",
}

_SAFE_VOID_ERROR_MESSAGES = {
    "This purchase transaction cannot be voided automatically.",
    "Transaction is missing class scope (class_id) and cannot be voided safely.",
    "Purchase item record was not found. This transaction cannot be voided.",
    "Immediate-use item purchases are not voidable.",
    "Only delayed-use item purchases are voidable.",
    "No matching student item was found for this purchase.",
    "Unable to map this transaction to purchasable student items.",
    "Delayed-use item has already been used (redemption requested or completed) and cannot be voided.",
}


def _safe_local_redirect_target(target):
    if not target or not is_safe_url(target):
        return None
    parsed = urlparse(urljoin(request.host_url, target))
    safe_target = parsed.path or "/"
    if parsed.query:
        safe_target = f"{safe_target}?{parsed.query}"
    if parsed.fragment:
        safe_target = f"{safe_target}#{parsed.fragment}"
    return safe_target


def _safe_known_message(message, allowed_messages, default_message):
    for allowed_message in allowed_messages:
        if message == allowed_message:
            return allowed_message
    return default_message

ADMIN_FEATURE_ENDPOINTS = {
    "admin.payroll": "payroll",
    "admin.store_management": "store",
    "admin.banking": "banking",
    "admin.rent_settings": "rent",
    "admin.insurance_management": "insurance",
    "admin.hall_pass": "hall_pass",
    "admin.hall_pass_setup": "hall_pass",
}

FEATURE_LABELS = {
    "payroll": "Payroll",
    "store": "Store",
    "banking": "Banking",
    "rent": "Rent",
    "insurance": "Insurance",
    "hall_pass": "Hall Pass",
}

ADMIN_FEATURE_PATH_PREFIXES = {
    '/admin/hall-pass': 'hall_pass',
    '/admin/payroll': 'payroll',
    '/admin/store': 'store',
    '/admin/banking': 'banking',
    '/admin/rent-settings': 'rent',
    '/admin/rent-waiver': 'rent',
    '/admin/insurance': 'insurance',
}

ADMIN_CLASS_CONTEXT_ENDPOINTS = {
    'admin.add_individual_student',
    'admin.add_manual_student',
}

ADMIN_CLASS_CONTEXT_REDIRECTS = {
    'admin.add_individual_student': 'admin.students',
    'admin.add_manual_student': 'admin.students',
}


def _route_matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _get_admin_class_context_redirect_endpoint() -> str:
    redirect_endpoint = ADMIN_CLASS_CONTEXT_REDIRECTS.get(request.endpoint)
    if redirect_endpoint:
        return redirect_endpoint

    for prefix, feature_name in ADMIN_FEATURE_PATH_PREFIXES.items():
        if _route_matches_prefix(request.path, prefix):
            if feature_name == 'store':
                return 'admin.store_management'
            if feature_name == 'payroll':
                return 'admin.payroll'
    return 'admin.dashboard'


def _get_requested_admin_class_id() -> str | None:
    """Resolve request-scoped class_id from explicit class_id, join_code, or block."""
    endpoint = request.endpoint or ''
    # Ignore raw 'block' parameter if it represents student roster assignment rather than class scope selector
    ignore_raw_block = endpoint in {
        'admin.add_individual_student',
        'admin.add_manual_student',
        'admin.edit_student',
        'admin.delete_student',
    }

    if request.method == 'GET':
        class_candidate = request.args.get('class_id')
        jc_candidate = None
        block_candidate = None
    elif request.is_json:
        payload = request.get_json(silent=True) or {}
        class_candidate = payload.get('class_id')
        jc_candidate = payload.get('join_code') or payload.get('jc')
        block_candidate = payload.get('cwi_block') or payload.get('settings_block')
        if not ignore_raw_block:
            block_candidate = block_candidate or payload.get('block')
    else:
        class_candidate = request.form.get('class_id')
        jc_candidate = request.form.get('join_code') or request.form.get('jc')
        block_candidate = request.form.get('cwi_block') or request.form.get('settings_block')
        if not ignore_raw_block:
            block_candidate = block_candidate or request.form.get('block')

    if class_candidate:
        normalized_class_id = (class_candidate or '').strip()
        if normalized_class_id:
            return normalized_class_id

    admin_id = session.get('admin_id')
    if not admin_id:
        return None

    if jc_candidate:
        class_row = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(
            join_code=jc_candidate.strip().upper(),
            teacher_id=admin_id
        ).first()
        if class_row:
            return class_row[0]

    if block_candidate:
        from app.utils.economy_policy import resolve_class_scope
        scope = resolve_class_scope(admin_id, block=block_candidate)
        if scope:
            return scope['class_id']

    return None


def _admin_write_has_join_code_conflict(admin_id: int | None) -> bool:
    if not admin_id or request.method == 'GET':
        return False

    requested_class_id = _get_requested_admin_class_id()
    if not requested_class_id:
        return False

    session_class_id = (session.get('current_class_id') or '').strip()
    if not session_class_id:
        return True

    return requested_class_id != session_class_id


def _admin_request_has_join_code_conflict(admin_id: int | None) -> bool:
    """Return True when request-supplied class selector disagrees with active class context."""
    if not admin_id:
        return False

    requested_class_id = _get_requested_admin_class_id()
    if not requested_class_id:
        return False

    session_class_id = (session.get('current_class_id') or '').strip()
    if not session_class_id:
        return True

    return requested_class_id != session_class_id


def _route_uses_admin_class_context() -> bool:
    endpoint = request.endpoint or ''
    if not endpoint.startswith('admin.'):
        return False
    if endpoint == 'admin.set_current_class':
        return False
    if endpoint in ADMIN_CLASS_CONTEXT_ENDPOINTS:
        return True
    return any(_route_matches_prefix(request.path, prefix) for prefix in ADMIN_FEATURE_PATH_PREFIXES)


def _route_requires_admin_class_context() -> bool:
    if not _route_uses_admin_class_context():
        return False
    return request.method != 'GET'


def _resolve_admin_class_context(admin_id: int | None) -> dict | None:
    if not admin_id:
        return None

    candidate_class_id = (session.get('current_class_id') or '').strip() or None
    class_row = None
    if candidate_class_id:
        class_row = (
            ClassEconomy.query.with_entities(
                ClassEconomy.class_id, ClassEconomy.join_code, ClassEconomy.teacher_id
            )
            .filter(
                ClassEconomy.teacher_id == admin_id,
                ClassEconomy.class_id == candidate_class_id,
            )
            .first()
        )
    else:
        # Fallback for legacy sessions that still carry join_code but not class_id.
        candidate_join_code = (session.get('current_join_code') or '').strip() or None
        if candidate_join_code:
            class_row = (
                ClassEconomy.query.with_entities(
                    ClassEconomy.class_id, ClassEconomy.join_code, ClassEconomy.teacher_id
                )
                .filter(
                    ClassEconomy.teacher_id == admin_id,
                    ClassEconomy.join_code == candidate_join_code,
                )
                .first()
            )
            if class_row:
                session['current_class_id'] = class_row.class_id
                session['current_join_code'] = class_row.join_code
        else:
            return None
    if not class_row or class_row.teacher_id != admin_id:
        return None

    if request.method != 'GET':
        session['current_class_id'] = class_row.class_id
        session['current_join_code'] = class_row.join_code
    return {
        'join_code': class_row.join_code,
        'class_id': class_row.class_id,
    }


def _handle_mismatched_admin_class_context():
    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    current_app.logger.error(
        "Blocked admin write with mismatched class context",
        extra={
            'admin_id': scoped_admin_id,
            'endpoint': request.endpoint,
            'method': request.method,
            'path': request.path,
            'session_join_code': _get_current_admin_join_code(scoped_admin_id),
            'requested_class_id': _get_requested_admin_class_id(),
        },
    )

    message = "Switch to the selected class before making changes."
    if request.is_json:
        return jsonify({'status': 'error', 'message': message}), 400

    flash(message, 'error')
    return redirect(url_for(_get_admin_class_context_redirect_endpoint()))


def _handle_missing_admin_class_context():
    """Block class-scoped writes when the teacher has not selected an active class."""
    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    if not scoped_admin_id:
        return None

    current_join_code = _get_current_admin_join_code(scoped_admin_id)
    if current_join_code:
        return None

    current_app.logger.error(
        "Blocked admin write without class context",
        extra={
            'admin_id': scoped_admin_id,
            'endpoint': request.endpoint,
            'method': request.method,
            'path': request.path,
        },
    )

    message = "Select a class before making changes."
    if request.is_json:
        return jsonify({'status': 'error', 'message': message}), 400

    flash(message, 'error')
    redirect_endpoint = _get_admin_class_context_redirect_endpoint()
    return redirect(url_for(redirect_endpoint))


@admin_bp.before_request
def before_request():
    """
    Set context flags for request safety.

    Mark GET requests as read-only to prevent accidental writes (e.g., balance settlement).
    This interacts with guards in app/utils/banking.py.
    """
    if request.method == 'GET':
        g.read_only = True

    g.admin_class_context = None
    g.admin_join_code = None
    g.admin_class_id = None

    admin_id = session.get('admin_id')
    if admin_id and _route_uses_admin_class_context():
        context = _resolve_admin_class_context(admin_id)
        if context:
            g.admin_class_context = context
            g.admin_join_code = context['join_code']
            g.admin_class_id = context['class_id']

        if _admin_request_has_join_code_conflict(admin_id):
            return _handle_mismatched_admin_class_context()

        if _route_requires_admin_class_context() and _admin_write_has_join_code_conflict(admin_id):
            return _handle_mismatched_admin_class_context()

    if _route_requires_admin_class_context() and g.admin_class_context is None:
        response = _handle_missing_admin_class_context()
        if response is not None:
            return response

    feature_name = ADMIN_FEATURE_ENDPOINTS.get(request.endpoint or "")
    if (
        feature_name
        and request.method == "GET"
        and g.admin_class_context is not None
    ):
        scope = resolve_feature_class_for_class(g.admin_class_id, feature_name)
        if scope and not scope["enabled"]:
            return render_template(
                "admin_feature_disabled.html",
                current_page="feature_disabled",
                feature_name=feature_name,
                feature_label=FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ").title()),
            )

    return None


# -------------------- HELPER FUNCTIONS --------------------

def parse_dob_input(dob_str):
    """
    Parse date of birth input and return the DOB sum (month + day + year).

    Attempts to parse in multiple formats:
    1. YYYY-MM-DD (from date input)
    2. MM/DD/YYYY (fallback format)

    Args:
        dob_str: String representation of date of birth

    Returns:
        int: DOB sum (month + day + year)

    Raises:
        ValueError: If date string cannot be parsed in any supported format
    """
    if not dob_str:
        raise ValueError("Date of birth is required")

    dob_str = dob_str.strip()

    # Try YYYY-MM-DD format first (native date input)
    try:
        dob_input = datetime.strptime(dob_str, "%Y-%m-%d").date()
        return dob_input.month + dob_input.day + dob_input.year
    except ValueError:
        pass

    # Try MM/DD/YYYY format as fallback
    try:
        dob_input = datetime.strptime(dob_str, "%m/%d/%Y").date()
        return dob_input.month + dob_input.day + dob_input.year
    except ValueError:
        pass

    # If both formats fail, raise error
    raise ValueError("Invalid date format. Please use the date picker.")


def _get_admin_feature_name_for_path(path: str) -> str | None:
    for prefix, feature_name in ADMIN_FEATURE_PATH_PREFIXES.items():
        if path == prefix or path.startswith(f"{prefix}/"):
            return feature_name
    return None


def _get_current_admin_join_code(admin_id: int | None) -> str | None:
    if not admin_id:
        return None
    current_class_id = (session.get('current_class_id') or '').strip()
    if not current_class_id:
        return None
    class_row = (
        ClassEconomy.query.with_entities(ClassEconomy.join_code)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.class_id == current_class_id,
        )
        .first()
    )
    if not class_row or not class_row.join_code:
        return None
    if request.method != 'GET':
        session['current_join_code'] = class_row.join_code
    return class_row.join_code


def get_admin_feature_settings_for_join_code(admin_id: int | None, join_code: str | None = None) -> dict:
    if not admin_id:
        return FeatureSettings.get_defaults()

    resolved_join_code = (join_code or _get_current_admin_join_code(admin_id) or '').strip()
    if not resolved_join_code:
        return FeatureSettings.get_defaults()

    class_row = (
        ClassEconomy.query.with_entities(ClassEconomy.class_id)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.join_code == resolved_join_code,
        )
        .first()
    )
    if not class_row or not class_row.class_id:
        return FeatureSettings.get_defaults()

    scoped_features = get_class_feature_settings_for_class(class_row.class_id)
    return scoped_features["features"] if scoped_features else FeatureSettings.get_defaults()


def is_admin_feature_enabled(feature_name: str, admin_id: int | None = None, join_code: str | None = None) -> bool:
    class_id = (getattr(g, "admin_class_id", None) or session.get("current_class_id") or "").strip() or None
    if not class_id and join_code:
        resolved_admin_id = admin_id or session.get('admin_id')
        if resolved_admin_id:
            class_row = (
                ClassEconomy.query.with_entities(ClassEconomy.class_id)
                .filter_by(join_code=join_code, teacher_id=resolved_admin_id)
                .first()
            )
            class_id = class_row.class_id if class_row else None
    scope = resolve_feature_class_for_class(class_id, feature_name) if class_id else None
    return bool(scope["enabled"]) if scope else False


def get_admin_feature_join_code_options(feature_name: str, admin_id: int | None = None) -> list[dict[str, str]]:
    resolved_admin_id = admin_id or session.get('admin_id')
    if not resolved_admin_id:
        return []

    classes = (
        ClassEconomy.query.with_entities(
            ClassEconomy.class_id,
            ClassEconomy.join_code,
            ClassEconomy.section,
            ClassEconomy.display_name,
        )
        .filter(
            ClassEconomy.teacher_id == resolved_admin_id,
            ClassEconomy.join_code.isnot(None),
        )
        .order_by(ClassEconomy.section.asc(), ClassEconomy.created_at.asc())
        .all()
    )
    roster_blocks = {
        seat_class_id: seat_block
        for seat_class_id, seat_block in (
            db.session.query(Seat.class_id, Seat.block)
            .filter(Seat.class_id.in_([class_id for class_id, *_ in classes]))
            .order_by(Seat.id.asc())
            .all()
        )
        if seat_class_id and seat_block
    }

    options: list[dict[str, str]] = []
    seen_join_codes: set[str] = set()
    for class_id, join_code, section, display_name in classes:
        if not join_code or join_code in seen_join_codes:
            continue
        seen_join_codes.add(join_code)
        scope = resolve_feature_class_for_class(class_id, feature_name)
        if not scope or not scope["enabled"]:
            continue
        normalized_block = ((section or roster_blocks.get(class_id) or "")).strip().upper()
        label = display_name or (f"Period {normalized_block}" if normalized_block else scope["join_code"])
        options.append({
            'join_code': scope["join_code"],
            'class_id': scope["class_id"],
            'block': normalized_block,
            'label': label,
        })
    return options


def resolve_admin_feature_join_code(feature_name: str, admin_id: int | None = None) -> str | None:
    resolved_admin_id = admin_id or session.get('admin_id')
    if not resolved_admin_id:
        return None

    options = get_admin_feature_join_code_options(feature_name, admin_id=resolved_admin_id)
    enabled_join_codes = {option['join_code'] for option in options}
    current_join_code = _get_current_admin_join_code(resolved_admin_id)
    if current_join_code and current_join_code in enabled_join_codes:
        return current_join_code

    return options[0]['join_code'] if options else None


def require_admin_feature_scope(
    feature_name: str,
    *,
    admin_id: int | None = None,
    requested_block: str | None = None,
    allow_default: bool = True,
) -> dict:
    resolved_admin_id = admin_id or session.get('admin_id')
    options = get_admin_feature_join_code_options(feature_name, admin_id=resolved_admin_id)
    if not options:
        abort(404)

    options_by_block = {option['block']: option for option in options if option.get('block')}

    normalized_block = (requested_block or '').strip().upper()

    if normalized_block:
        option = options_by_block.get(normalized_block)
        if not option:
            abort(404)
        return option

    if not allow_default:
        abort(404)

    return options[0]


def _parse_dob_date(dob_str):
    """Parse DOB input and return a date object."""
    if not dob_str:
        raise ValueError("Date of birth is required")

    dob_str = dob_str.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(dob_str, fmt).date()
        except ValueError:
            continue

    raise ValueError("Invalid date format. Please use the date picker.")


def _normalize_full_name_for_dedupe(first_name: str, last_name: str) -> str:
    """Return lowercase letters-only full name for dedupe key input."""
    return re.sub(r"[^a-z]", "", f"{first_name}{last_name}".lower())


def _resolve_class_id(teacher_id: int, join_code: str) -> str:
    """Get or create the canonical ClassEconomy row and return class_id."""
    return _ensure_join_code_anchors(teacher_id, join_code)


def _build_teacher_block_dedupe_key(class_id: str, first_name: str, last_name: str) -> str:
    """Build deterministic dedupe key: class_id|normalized_full_name."""
    normalized_full_name = _normalize_full_name_for_dedupe(first_name, last_name)
    dedupe_input = f"{class_id}|{normalized_full_name}".encode()
    return hash_hmac(dedupe_input, b"")


def _find_admin_by_auth_username(username: str):
    """Lookup teacher by hash, with migration-only legacy fallback."""
    normalized = normalize_auth_username(username)
    if not normalized:
        return None

    lookup_hash = hash_username_lookup(normalized)
    return Admin.query.filter_by(username_lookup_hash=lookup_hash).first()


def _auth_username_exists(username: str, *, exclude_admin_id: int | None = None) -> bool:
    normalized = normalize_auth_username(username)
    if not normalized:
        return False
    lookup_hash = hash_username_lookup(normalized)
    user = User.query.filter_by(username_lookup_hash=lookup_hash).first()
    if user:
        if exclude_admin_id is not None:
            excluded_admin = db.session.get(Admin, exclude_admin_id)
            if excluded_admin and excluded_admin.username_lookup_hash == lookup_hash:
                return False
        return True

    admin = _find_admin_by_auth_username(username)
    if not admin:
        return False
    if exclude_admin_id is not None and admin.id == exclude_admin_id:
        return False
    return True


def _admin_requires_username_migration(admin: Admin) -> bool:
    return needs_hashed_username_migration(admin)


def _generate_unique_teacher_public_id() -> str:
    words = load_teacher_id_words()
    for _ in range(100):
        candidate = generate_teacher_public_id(words=words)
        if not Admin.query.filter_by(teacher_public_id=candidate).first():
            return candidate
    while True:
        candidate = generate_teacher_public_id_with_suffix(words=words)
        if not Admin.query.filter_by(teacher_public_id=candidate).first():
            return candidate


def _build_admin_auth_fields(username: str, *, existing_salt: bytes | None = None) -> tuple[bytes, str, str]:
    return build_hashed_username_fields(username, existing_salt=existing_salt)


# -------------------- DASHBOARD & QUICK ACTIONS --------------------


def _scoped_students(include_unassigned=True):
    """Return a query for students the current admin can access."""
    query = get_admin_student_query(include_unassigned=include_unassigned)
    class_id = getattr(g, "admin_class_id", None) or (session.get("current_class_id") or "").strip() or None
    admin_id = session.get("admin_id")
    if not class_id or not admin_id:
        return query

    class_scoped_student_ids = (
        db.session.query(Seat.student_id)
        .filter(
            Seat.class_id == class_id,
            Seat.student_id.isnot(None),
        )
        .subquery()
    )
    return query.filter(Student.id.in_(sa.select(class_scoped_student_ids)))


def _get_teacher_blocks():
    """Get sorted list of blocks from the current teacher's Seat roster."""
    admin_id = session.get("admin_id")
    class_id = getattr(g, "admin_class_id", None) or (session.get("current_class_id") or "").strip() or None
    if not admin_id:
        return []

    # Derive blocks from ClassEconomy (canonical class anchor) for the current teacher.
    query = (
        db.session.query(ClassEconomy.section)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section.isnot(None),
        )
    )
    if class_id:
        query = query.filter(ClassEconomy.class_id == class_id)
    rows = query.all()
    return sorted({(section or "").strip().upper() for (section,) in rows if (section or "").strip()})




def _populate_policy_from_form(policy, form, *, next_tier_category_id=None):
    """Populate insurance policy fields from form data."""
    is_non_monetary = form.claim_type.data == 'non_monetary'
    policy.title = form.title.data
    policy.description = form.description.data
    policy.premium = form.premium.data
    policy.charge_frequency = form.charge_frequency.data
    policy.autopay = form.autopay.data
    policy.waiting_period_days = form.waiting_period_days.data
    policy.max_claims_count = form.max_claims_count.data
    policy.max_claims_period = FREQUENCY_TO_CLAIM_PERIOD.get(form.charge_frequency.data, 'month')
    policy.max_claim_amount = None if is_non_monetary else form.max_claim_amount.data
    policy.max_payout_per_period = None if is_non_monetary else form.max_payout_per_period.data
    policy.bypass_cwi_warnings = form.bypass_cwi_warnings.data
    policy.claim_type = form.claim_type.data
    policy.is_monetary = not is_non_monetary
    policy.no_repurchase_after_cancel = form.no_repurchase_after_cancel.data
    policy.enable_repurchase_cooldown = form.enable_repurchase_cooldown.data
    policy.repurchase_wait_days = form.repurchase_wait_days.data
    policy.auto_cancel_nonpay_days = form.auto_cancel_nonpay_days.data
    policy.claim_time_limit_days = form.claim_time_limit_days.data
    policy.bundle_with_policy_ids = form.bundle_with_policy_ids.data
    policy.bundle_discount_percent = form.bundle_discount_percent.data
    policy.bundle_discount_amount = form.bundle_discount_amount.data
    policy.marketing_badge = form.marketing_badge.data if form.marketing_badge.data else None
    policy.set_blocks(form.blocks.data if form.blocks.data else [])

    if form.tier_category_id.data:
        policy.tier_category_id = form.tier_category_id.data
    elif form.tier_name.data or form.tier_color.data:
        policy.tier_category_id = next_tier_category_id
    else:
        policy.tier_category_id = None

    policy.tier_name = form.tier_name.data or None
    policy.tier_color = form.tier_color.data or None
    policy.tier_level = form.tier_level.data or None
    policy.is_active = form.is_active.data

def _get_class_labels_for_blocks(admin_id, blocks):
    """Return mapping of block -> class display_name for the given admin without N+1 queries."""

    if not blocks:
        return {}

    class_id = getattr(g, "admin_class_id", None) or (session.get("current_class_id") or "").strip() or None
    query = (
        db.session.query(ClassEconomy.section, ClassEconomy.display_name)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section.in_(blocks),
        )
    )
    if class_id:
        query = query.filter(ClassEconomy.class_id == class_id)
    rows = query.all()
    labels = {section: (display_name or section) for section, display_name in rows}

    for block in blocks:
        labels.setdefault(block, block)

    return labels


def _get_join_codes_by_block(admin_id, blocks):
    """Return mapping of block -> join_code for the given admin without N+1 queries."""

    if not blocks:
        return {}

    class_id = getattr(g, "admin_class_id", None) or (session.get("current_class_id") or "").strip() or None
    query = (
        db.session.query(ClassEconomy.section, ClassEconomy.join_code)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section.in_(blocks),
            ClassEconomy.join_code.isnot(None),
        )
    )
    if class_id:
        query = query.filter(ClassEconomy.class_id == class_id)
    rows = query.all()
    return {section: join_code for section, join_code in rows if join_code}


def _build_payroll_preview_state(students, join_codes_by_block):
    """Aggregate payroll preview data from class-scoped payroll anchors."""
    students_by_join_code: dict[str, dict[int, Student]] = defaultdict(dict)

    for student in students:
        for raw_block in (student.block or "").split(","):
            block = raw_block.strip()
            if not block:
                continue
            join_code = join_codes_by_block.get(block)
            if join_code:
                students_by_join_code[join_code][student.id] = student

    summary_by_join_code: dict[str, dict[int, Decimal]] = {}
    anchor_by_join_code: dict[str, datetime | None] = {}
    updated_at_by_join_code: dict[str, datetime] = {}
    total_summary: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for join_code, students_map in students_by_join_code.items():
        class_students = list(students_map.values())

        economy = ClassEconomy.query.filter_by(join_code=join_code).first()
        if not economy:
            continue

        class_id = economy.class_id
        student_ids = [s.id for s in class_students]
        seats = Seat.query.filter(Seat.student_id.in_(student_ids), Seat.class_id == class_id).all()
        seat_ids = [s.id for s in seats]

        # map seat_id to student_id to preserve backward compatibility of the preview payload
        seat_to_student = {s.id: s.student_id for s in seats if s.student_id}

        anchor = None
        if getattr(g, "read_only", False):
            seat_summary = calculate_payroll_breakdown(class_id, seat_ids, anchor)
            updated_at = None
        else:
            seat_summary, updated_at = get_cached_payroll_with_meta(
                class_id,
                seat_ids,
                anchor
            )

        # Remap to student_id to preserve downstream view templates expecting student IDs
        summary = {}
        for s_id, amt in seat_summary.items():
            if s_id in seat_to_student:
                summary[seat_to_student[s_id]] = amt

        anchor_by_join_code[join_code] = anchor
        summary_by_join_code[join_code] = summary
        if updated_at is not None:
            updated_at_by_join_code[join_code] = ensure_utc(updated_at)
        for student_id, amount in summary.items():
            total_summary[student_id] += Decimal(str(amount))

    latest_updated_at = max(updated_at_by_join_code.values()) if updated_at_by_join_code else None
    return {
        "summary_by_join_code": summary_by_join_code,
        "anchor_by_join_code": anchor_by_join_code,
        "updated_at_by_join_code": updated_at_by_join_code,
        "total_summary": dict(total_summary),
        "latest_updated_at": latest_updated_at,
    }


def _student_scope_subquery(include_unassigned=True):
    """Return a subquery of student IDs the current admin can access."""
    return (
        _scoped_students(include_unassigned=include_unassigned)
        .with_entities(Student.id)
        .subquery()
    )


def _student_scope_subquery_for_join_code(join_code: str, *, include_unassigned: bool = False):
    """Return a subquery of student IDs scoped to one class by join_code."""
    admin_id = session.get("admin_id")
    if not admin_id or not join_code:
        return sa.select(Student.id).where(sa.false()).subquery()

    query = (
        db.session.query(Student.id)
        .join(Seat, Seat.student_id == Student.id)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            Seat.join_code == join_code,
            Seat.student_id.isnot(None),
        )
        .distinct()
    )
    if not include_unassigned:
        query = query.filter(Seat.claimed_at.isnot(None))

    return query.subquery()


def _get_claimed_teacher_block_for_join_code(student_id: int, teacher_id: int, join_code: str):
    """Return the claimed Seat for one student in one class scope."""
    if not student_id or not teacher_id or not join_code:
        return None
    return (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.student_id == student_id,
            ClassEconomy.teacher_id == teacher_id,
            Seat.join_code == join_code,
            Seat.claimed_at.isnot(None),
        )
        .first()
    )


def _require_payroll_feature_scope_from_request(
    class_id: str | None = None,
    seat_id: int | None = None,
    *,
    allow_default: bool = True,
) -> dict:
    """Resolve the canonical payroll class scope starting from class_id and seat_id.

    This function implements the V2 authority flow:
    1. Retrieve/resolve class_id and seat_id context.
    2. Load and verify the Seat corresponding to the requested class_id.
    3. Ensure the Seat has teacher role/authority.
    4. Construct the scoped features and options based on the class boundary.
    """
    from flask import request, session
    from app.models import Seat, ClassFeature
    from app.feats.base import InvariantViolation

    # 1. Resolve canonical context variables
    resolved_class_id = class_id or request.values.get('class_id') or session.get('current_class_id')
    resolved_seat_id = seat_id or request.values.get('seat_id') or request.values.get('teacher_seat_id') or session.get('current_seat_id')

    if not resolved_class_id:
        raise InvariantViolation("Missing canonical class_id context.")

    if not resolved_seat_id:
        raise InvariantViolation("Missing canonical seat_id context.")

    # 2. Retrieve Seat first to verify against the class_id before anything else
    teacher_seat = Seat.query.filter_by(id=resolved_seat_id).first()
    if not teacher_seat:
        raise InvariantViolation(
            f"Seat not found for seat_id={resolved_seat_id}. "
            "Canonical context construction failed."
        )

    # Verify the seat.seat_id against the class_id before anything else
    if teacher_seat.class_id != resolved_class_id:
        raise InvariantViolation(
            f"Seat class mismatch: seat.class_id={teacher_seat.class_id} != requested class_id={resolved_class_id}"
        )

    # 3. Ensure the Seat has teacher role/authority
    if teacher_seat.role != 'teacher':
        raise InvariantViolation(
            f"Insufficient authority: Seat {teacher_seat.id} is role='{teacher_seat.role}', not 'teacher'."
        )

    # 4. Resolve available blocks from Seat (class-scoped)
    requested_block = (request.values.get('cwi_block') or request.values.get('block') or '').strip().upper()

    blocks = (
        db.session.query(Seat.block)
        .filter(
            Seat.class_id == resolved_class_id,
            Seat.block.isnot(None),
        )
        .distinct()
        .order_by(Seat.block.asc())
        .all()
    )
    available_blocks = [r[0] for r in blocks if r[0]]

    if requested_block:
        if requested_block not in available_blocks:
            raise InvariantViolation(f"Block '{requested_block}' is not associated with class_id '{resolved_class_id}'.")
        resolved_block = requested_block
    else:
        # Fallback to the first available block, or default
        resolved_block = available_blocks[0] if available_blocks else None
        if not resolved_block and not allow_default:
            raise InvariantViolation("No blocks found and default block is not allowed.")

    # 5. Verify feature is enabled
    enabled = "payroll" in ClassFeature.enabled_names_for_class(resolved_class_id)

    return {
        'join_code': teacher_seat.join_code,
        'class_id': resolved_class_id,
        'block': resolved_block,
        'teacher_seat': teacher_seat,
        'enabled': enabled,
    }



def _join_code_exists(join_code):
    """Return True when a class identified by join_code still exists in ClassEconomy."""
    if not join_code:
        return False
    return ClassEconomy.query.filter_by(join_code=join_code).first() is not None


def _assert_transaction_deletion_allowed(join_code, *, join_code_deletion=False):
    """
    Guardrail: transactions are immutable while class join code exists.

    Hard transaction deletion is only allowed from join-code destruction workflow.
    """
    if not join_code_deletion and _join_code_exists(join_code):
        raise AssertionError(
            f"Refusing to delete transactions for active join code '{join_code}'. "
            "Use student removal or class deletion flows instead."
        )


def _hard_delete_student_if_orphaned(student_id):
    """Compatibility wrapper for internal call sites and tests."""
    return hard_delete_student_if_orphaned(student_id)


def _remove_student_from_teacher_scope(student, teacher_id):
    """
    Remove a student from a teacher's roster.

    If the student is shared with other teachers, only the current teacher
    association is removed. The student record is hard-deleted only when it no
    longer has any StudentTeacher links.
    """
    return remove_student_from_teacher_scope(student.id, teacher_id)


def _delete_transactions_for_join_code(join_code, *, join_code_deletion=False):
    """Hard-delete transactions scoped to join_code (join-code destruction only)."""
    _assert_transaction_deletion_allowed(join_code, join_code_deletion=join_code_deletion)
    return Transaction.query.filter_by(join_code=join_code).delete(synchronize_session=False)


def _hard_delete_class_scope(class_id, teacher_id):
    """
    Permanently remove records scoped to a destroyed class.

    The boundary may enter through join_code, but internal deletion uses the
    canonical class_id anchor only.
    """
    if not class_id:
        current_app.logger.critical("P0 INVARIANT VIOLATION: class deletion invoked without class_id.")
        raise InvariantViolation("class deletion requires canonical class_id")

    class_row = db.session.get(ClassEconomy, class_id)
    if not class_row:
        return

    join_code = class_row.join_code
    invalid_scope_rows = []
    scoped_models = (
        ("ledger_transaction", Transaction),
        ("student_blocks", StudentBlock),
        ("tap_events", TapEvent),
        ("hall_pass_logs", HallPassLog),
        ("student_items", StudentItem),
        ("analytics_events", AnalyticsEvent),
        ("analytics_snapshots", AnalyticsSnapshot),
        ("issues", Issue),
        ("student_insurance", StudentInsurance),
        ("rent_payments", RentPayment),
        ("announcements", Announcement),
    )
    for label, model in scoped_models:
        count = db.session.query(model).filter(
            model.join_code == join_code,
            model.class_id.is_(None),
        ).count()
        if count:
            invalid_scope_rows.append(f"{label}={count}")
    if invalid_scope_rows:
        message = (
            f"class_id NULL rows detected for class_id={class_id} join_code={join_code}: "
            f"{', '.join(invalid_scope_rows)}"
        )
        current_app.logger.critical("P0 INVARIANT VIOLATION: %s", message)
        raise InvariantViolation(message)

    scoped_student_ids = [
        sid for (sid,) in db.session.query(Seat.student_id)
        .filter(
            Seat.class_id == class_id,
            Seat.student_id.isnot(None),
        )
        .distinct()
        .all()
    ]
    student_item_ids_subq = (
        db.session.query(StudentItem.id)
        .filter(StudentItem.class_id == class_id)
        .subquery()
    )
    insurance_ids_subq = (
        db.session.query(StudentInsurance.id)
        .filter(StudentInsurance.class_id == class_id)
        .subquery()
    )
    tx_ids_subq = (
        db.session.query(Transaction.id)
        .filter(Transaction.class_id == class_id)
        .subquery()
    )
    issue_ids_subq = (
        db.session.query(Issue.id)
        .filter(Issue.class_id == class_id)
        .subquery()
    )
    class_blocks = [
        block for (block,) in db.session.query(Seat.block).filter(
            Seat.class_id == class_id,
            Seat.block.isnot(None),
        ).distinct().all()
    ]
    if class_blocks and scoped_student_ids:
        inferred_student_block_nulls = db.session.query(StudentBlock).filter(
            StudentBlock.student_id.in_(scoped_student_ids),
            StudentBlock.period.in_(class_blocks),
            StudentBlock.class_id.is_(None),
        ).count()
        if inferred_student_block_nulls:
            message = (
                f"class_id NULL student_blocks detected for class_id={class_id} "
                f"join_code={join_code}: student_blocks_inferred={inferred_student_block_nulls}"
            )
            current_app.logger.critical("P0 INVARIANT VIOLATION: %s", message)
            raise InvariantViolation(message)

    # Class-scoped records
    RedemptionAuditLog.query.filter(
        RedemptionAuditLog.student_item_id.in_(sa.select(student_item_ids_subq))
    ).delete(synchronize_session=False)
    StudentItem.query.filter(StudentItem.class_id == class_id).delete(synchronize_session=False)
    TapEvent.query.filter(TapEvent.class_id == class_id).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.class_id == class_id).delete(synchronize_session=False)
    RentPayment.query.filter(RentPayment.class_id == class_id).delete(synchronize_session=False)
    StudentBlock.query.filter(StudentBlock.class_id == class_id).delete(synchronize_session=False)
    BalanceCache.query.filter(BalanceCache.class_id == class_id).delete(synchronize_session=False)
    AnalyticsSnapshot.query.filter(AnalyticsSnapshot.class_id == class_id).delete(synchronize_session=False)
    AnalyticsEvent.query.filter(AnalyticsEvent.class_id == class_id).delete(synchronize_session=False)
    Announcement.query.filter(
        Announcement.teacher_id == teacher_id,
        Announcement.class_id == class_id,
    ).delete(synchronize_session=False)

    # Issue data tied to this class
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.class_id == class_id).delete(synchronize_session=False)

    # Insurance data tied to this class or class-scoped transactions
    InsuranceClaim.query.filter(
        sa.or_(
            InsuranceClaim.enrollment_id.in_(sa.select(insurance_ids_subq)),
            InsuranceClaim.transaction_id.in_(sa.select(tx_ids_subq)),
        )
    ).delete(synchronize_session=False)
    StudentInsurance.query.filter(StudentInsurance.class_id == class_id).delete(synchronize_session=False)

    # Financial ledger (only here)
    Transaction.query.filter(Transaction.class_id == class_id).delete(synchronize_session=False)
    PayrollSettings.query.filter(PayrollSettings.class_id == class_id).delete(synchronize_session=False)
    RentSettings.query.filter(RentSettings.class_id == class_id).delete(synchronize_session=False)

    # Remove store items tied only to this class block scope.
    if class_blocks:
        store_item_ids_for_blocks = (
            db.session.query(StoreItemBlock.store_item_id)
            .group_by(StoreItemBlock.store_item_id)
            .having(sa.func.count() > 0)
            .having(sa.func.sum(sa.case((StoreItemBlock.block.in_(class_blocks), 1), else_=0)) == sa.func.count())
            .subquery()
        )
        deletable_store_item_ids = (
            db.session.query(StoreItem.id)
            .filter(
                StoreItem.class_id == class_id,
                StoreItem.id.in_(sa.select(store_item_ids_for_blocks)),
            )
            .subquery()
        )
        class_item_student_ids = (
            db.session.query(StudentItem.id)
            .filter(StudentItem.store_item_id.in_(sa.select(deletable_store_item_ids)))
            .subquery()
        )
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(sa.select(class_item_student_ids))
        ).delete(synchronize_session=False)
        StudentItem.query.filter(
            StudentItem.store_item_id.in_(sa.select(deletable_store_item_ids))
        ).delete(synchronize_session=False)
        StoreItem.query.filter(
            StoreItem.id.in_(sa.select(deletable_store_item_ids))
        ).delete(synchronize_session=False)

    # Clean up orphaned StoreItemBlock entries for the deleted class blocks
    # This handles items that are visible to multiple classes
    if class_blocks:
        deletable_block_entries = (
            db.session.query(StoreItemBlock.store_item_id, StoreItemBlock.block)
            .join(StoreItem, StoreItemBlock.store_item_id == StoreItem.id)
            .filter(
                StoreItem.class_id == class_id,
                StoreItemBlock.block.in_(class_blocks)
            )
            .subquery()
        )
        StoreItemBlock.query.filter(
            sa.tuple_(StoreItemBlock.store_item_id, StoreItemBlock.block).in_(
                sa.select(deletable_block_entries)
            )
        ).delete(synchronize_session=False)

    # Seats/ownership for this class
    ClassMembership.query.filter(ClassMembership.class_id == class_id).delete(synchronize_session=False)
    Seat.query.filter(Seat.class_id == class_id).delete(synchronize_session=False)
    ClassEconomy.query.filter_by(class_id=class_id).delete(synchronize_session=False)

    # Remove students that no longer belong to any class after this class deletion.
    remaining_student_ids_subq = db.session.query(Seat.student_id).filter(
        Seat.student_id.isnot(None),
        Seat.class_id != class_id,
    ).subquery()
    orphan_student_ids = (
        db.session.query(Student.id)
        .filter(Student.id.in_(scoped_student_ids))
        .filter(~Student.id.in_(sa.select(remaining_student_ids_subq)))
        .subquery()
    )
    StudentTeacher.query.filter(
        StudentTeacher.student_id.in_(sa.select(orphan_student_ids))
    ).delete(synchronize_session=False)
    Student.query.filter(
        Student.id.in_(sa.select(orphan_student_ids))
    ).delete(synchronize_session=False)

def _delete_teacher_residual_ownership_rows(teacher_id):
    """Delete teacher-owned link rows not already removed by class-scoped deletion."""
    Seat.query.join(ClassEconomy, ClassEconomy.class_id == Seat.class_id).filter(
        ClassEconomy.teacher_id == teacher_id
    ).delete(synchronize_session=False)
    StudentTeacher.query.filter_by(teacher_id=teacher_id).delete(synchronize_session=False)


def _delete_teacher_settings_activity_and_audit_rows(teacher_id):
    """Delete teacher-scoped settings, activity, and audit rows."""
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_id == teacher_id
    ).subquery()
    BankingSettings.query.filter(
        BankingSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    FeatureSettings.query.filter(
        FeatureSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    HallPassSettings.query.filter(
        HallPassSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    SavedAdjustment.query.filter(
        SavedAdjustment.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    Announcement.query.filter(
        sa.or_(
            Announcement.teacher_id == teacher_id,
            Announcement.target_teacher_id == teacher_id,
        )
    ).delete(synchronize_session=False)
    Transaction.query.filter_by(teacher_id=teacher_id).delete(synchronize_session=False)
    RedemptionAuditLog.query.filter_by(teacher_id=teacher_id).delete(synchronize_session=False)


def _delete_teacher_rent_rows(teacher_id):
    """Delete rent settings and dependent items owned by a teacher."""
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_id == teacher_id
    ).subquery()
    rent_setting_ids_subq = db.session.query(RentSettings.id).filter(
        RentSettings.class_id.in_(sa.select(class_ids_subq))
    ).subquery()
    RentItem.query.filter(
        RentItem.rent_setting_id.in_(sa.select(rent_setting_ids_subq))
    ).delete(synchronize_session=False)
    RentSettings.query.filter(
        RentSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)


def _delete_teacher_insurance_rows(teacher_id):
    """Delete insurance policies and dependent rows scoped to classes owned by the teacher."""
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_id == teacher_id
    ).subquery()
    policy_ids_subq = db.session.query(InsurancePolicy.id).filter(
        InsurancePolicy.class_id.in_(sa.select(class_ids_subq))
    ).subquery()
    InsuranceClaim.query.filter(
        InsuranceClaim.policy_id.in_(sa.select(policy_ids_subq))
    ).delete(synchronize_session=False)
    StudentInsurance.query.filter(
        StudentInsurance.policy_id.in_(sa.select(policy_ids_subq))
    ).delete(synchronize_session=False)
    InsurancePolicyBlock.query.filter(
        InsurancePolicyBlock.policy_id.in_(sa.select(policy_ids_subq))
    ).delete(synchronize_session=False)
    InsurancePolicy.query.filter(
        InsurancePolicy.id.in_(sa.select(policy_ids_subq))
    ).delete(synchronize_session=False)


def _delete_teacher_issue_rows(teacher_id):
    """Delete teacher-owned issue records and their dependent rows."""
    issue_ids_subq = db.session.query(Issue.id).filter(Issue.teacher_id == teacher_id).subquery()
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    IssueStatusHistory.query.filter(
        IssueStatusHistory.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.teacher_id == teacher_id).delete(synchronize_session=False)


def _delete_teacher_recovery_and_credentials_rows(teacher_id):
    """Delete teacher recovery, credential, and onboarding rows."""
    delete_recovery_rows_for_teacher(teacher_id)
    delete_admin_credentials_for_teacher(teacher_id)
    delete_teacher_onboarding_for_teacher(teacher_id)


def _delete_teacher_store_rows(teacher_id):
    """Delete store rows owned by teacher, including dependent student items."""
    store_item_ids_subq = db.session.query(StoreItem.id).filter_by(teacher_id=teacher_id).subquery()
    StudentItem.query.filter(
        StudentItem.store_item_id.in_(sa.select(store_item_ids_subq))
    ).delete(synchronize_session=False)
    StoreItem.query.filter_by(teacher_id=teacher_id).delete(synchronize_session=False)


def _delete_orphan_students(affected_student_ids):
    """Delete students that no longer have any teacher links."""
    if not affected_student_ids:
        return
    linked_student_ids_subq = db.session.query(StudentTeacher.student_id).filter(
        StudentTeacher.student_id.in_(affected_student_ids)
    ).subquery()
    orphan_student_ids_subq = (
        db.session.query(Student.id)
        .filter(Student.id.in_(affected_student_ids))
        .filter(~Student.id.in_(sa.select(linked_student_ids_subq)))
        .subquery()
    )
    Student.query.filter(
        Student.id.in_(sa.select(orphan_student_ids_subq))
    ).delete(synchronize_session=False)


def _hard_delete_teacher_account_scope(teacher_id):
    """Hard-delete a teacher account and all class-scoped data owned by the teacher."""
    if not teacher_id:
        raise ValueError("teacher_id is required for account deletion")

    class_ids = [
        value for (value,) in db.session.query(ClassEconomy.class_id).filter(
            ClassEconomy.teacher_id == teacher_id,
        ).distinct().all()
    ]

    affected_student_ids = {
        sid for (sid,) in db.session.query(Seat.student_id).filter(
            Seat.class_id.in_(class_ids),
            Seat.student_id.isnot(None),
        ).distinct().all()
    }
    affected_student_ids.update(
        sid for (sid,) in db.session.query(StudentTeacher.student_id).filter(
            StudentTeacher.teacher_id == teacher_id
        ).distinct().all()
    )

    # Required ordering: all join-code-scoped data is destroyed before admin account deletion.
    for class_id in class_ids:
        _hard_delete_class_scope(class_id, teacher_id)

    _delete_teacher_residual_ownership_rows(teacher_id)
    _delete_teacher_settings_activity_and_audit_rows(teacher_id)
    _delete_teacher_rent_rows(teacher_id)
    _delete_teacher_insurance_rows(teacher_id)
    _delete_teacher_issue_rows(teacher_id)
    _delete_teacher_recovery_and_credentials_rows(teacher_id)
    _delete_teacher_store_rows(teacher_id)
    _delete_orphan_students(affected_student_ids)


def _sanitize_csv_field(value):
    """Prevent CSV injection by prefixing risky leading characters."""

    if value is None:
        return ""

    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _get_admin_owned_join_codes(admin_id):
    """Return active class economies owned by the current admin via membership."""
    if not admin_id:
        return []

    return [
        join_code
        for (join_code,) in db.session.query(ClassMembership.join_code)
        .filter(
            ClassMembership.admin_id == admin_id,
            ClassMembership.role == 'admin',
        )
        .distinct()
        .all()
        if join_code
    ]


def _admin_owns_join_code(admin_id, join_code):
    """Return True when the admin has an active admin membership for the join_code."""
    if not admin_id or not join_code:
        return False

    return db.session.query(
        sa.exists().where(
            sa.and_(
                ClassMembership.admin_id == admin_id,
                ClassMembership.join_code == join_code,
                ClassMembership.role == 'admin',
            )
        )
    ).scalar()


def _validate_destruction_gate(data, expected_phrase):
    """Require timed in-app gate proof for destructive operations."""
    phrase = str((data or {}).get("gate_phrase", "")).strip().upper()
    if phrase != expected_phrase:
        return jsonify({
            "status": "error",
            "message": "Confirmation failed: confirmation phrase did not match."
        }), 400

    try:
        countdown_seconds = int((data or {}).get("gate_countdown_seconds", 0))
    except (TypeError, ValueError):
        countdown_seconds = 0

    try:
        hold_seconds = float((data or {}).get("gate_hold_seconds", 0))
    except (TypeError, ValueError):
        hold_seconds = 0.0

    if countdown_seconds < 30:
        return jsonify({
            "status": "error",
            "message": "Deletion blocked: 30-second safety countdown is required."
        }), 400

    if hold_seconds < 10:
        return jsonify({
            "status": "error",
            "message": "Deletion blocked: 10-second hold is required."
        }), 400

    return None


def _get_student_or_404(student_id, include_unassigned=True):
    """Fetch a student the current admin can access or 404."""
    student = get_student_for_admin(student_id, include_unassigned=include_unassigned)
    if not student:
        abort(404)
    return student


_STUDENT_DETAIL_NAV_TTL_SECONDS = 300


def _student_detail_nav_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")


def _issue_student_detail_nav_token(*, student_id: int, seat_public_id: str, class_id: str | None = None) -> str:
    payload = {
        "student_id": int(student_id),
        "seat_public_id": str(seat_public_id),
        "class_id": str(class_id) if class_id else None,
        "admin_id": int(session.get("admin_id", 0) or 0),
    }
    return _student_detail_nav_serializer().dumps(payload)


def _read_student_detail_nav_token(token: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None
    try:
        payload = _student_detail_nav_serializer().loads(
            token,
            max_age=_STUDENT_DETAIL_NAV_TTL_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_student_detail_seat(student_id: int, teacher_id: int) -> Seat | None:
    selected_class_id = (session.get("current_class_id") or "").strip()
    selected_join_code = (session.get("current_join_code") or "").strip()

    seat_query = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.student_id == student_id,
            Seat.role == "student",
            Seat.public_id.isnot(None),
            ClassEconomy.teacher_id == teacher_id,
        )
    )
    if selected_class_id:
        return seat_query.filter(Seat.class_id == selected_class_id).first()
    if selected_join_code:
        return seat_query.filter(Seat.join_code == selected_join_code).first()
    return seat_query.order_by(Seat.id.asc()).first()


def _build_student_detail_url(student_id: int, *, teacher_id: int | None = None) -> str | None:
    teacher_id = int(teacher_id or session.get("admin_id") or 0)
    if not teacher_id:
        return None
    seat = _resolve_student_detail_seat(int(student_id), teacher_id)
    if not seat or not seat.public_id:
        return None
    nav_token = _issue_student_detail_nav_token(
        student_id=int(student_id),
        seat_public_id=seat.public_id,
        class_id=seat.class_id,
    )
    return url_for("admin.student_detail_public", student_public_id=seat.public_id, nav=nav_token)


def _redirect_to_student_detail(student_id: int):
    detail_url = _build_student_detail_url(student_id)
    if not detail_url:
        abort(404)
    return redirect(detail_url)


@admin_bp.app_template_global("student_detail_url")
def student_detail_url(student_id: int) -> str:
    detail_url = _build_student_detail_url(student_id)
    return detail_url or url_for("admin.students")


def _ensure_teacher_student_seat(teacher_id, join_code, block):
    """
    Ensure a teacher shadow student seat exists for the given class period.

    Uses profile_type='teacher_shadow_student' as the authoritative machine-readable
    discriminator. Name-based detection is explicitly avoided — the profile_type is the
    only correct authority for identifying this seat.
    """
    if not join_code:
        return

    class_id = _resolve_class_id(teacher_id, join_code)
    if not class_id:
        class_id = _ensure_join_code_anchors(teacher_id, join_code, class_label=block)

    from app.models import Seat, IdentityProfile
    from app.hash_utils import hash_username_lookup

    # Use profile_type as the canonical discriminator — not name strings.
    existing_seat = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(
            Seat.class_id == class_id,
            IdentityProfile.profile_type == 'teacher_shadow_student',
        )
        .first()
    )

    if existing_seat:
        existing_seat.block_identifier = block
        existing_seat.block = block
        existing_seat.join_code = join_code
        return

    first_name = "Teacher"
    last_initial = "S"

    # Roster fingerprint is class-scoped to prevent cross-class correlation (INV-CORE).
    claim_first_name_hash = hash_username_lookup(first_name.lower())
    claim_last_name_hash = hash_username_lookup("student")
    roster_fingerprint = hash_username_lookup(f"{class_id}|{first_name.lower()}|student")

    teacher_seat = Seat(
        class_id=class_id,
        role='student',
        block_identifier=block,
        block=block,
        claim_first_name_hash=claim_first_name_hash,
        claim_last_name_hash=claim_last_name_hash,
        roster_fingerprint=roster_fingerprint,
        join_code=join_code,
        claimed_at=None
    )
    db.session.add(teacher_seat)
    db.session.flush()

    profile = IdentityProfile(
        seat_id=teacher_seat.id,
        profile_type='teacher_shadow_student',
        first_name=first_name,
        last_initial=last_initial
    )
    db.session.add(profile)
    current_app.logger.info(f"Created teacher shadow student seat for teacher {teacher_id}, join_code {join_code}")


def _get_table_names() -> set[str]:
    """Return the set of table names for the current engine, using a module-level cache."""
    db_url = str(db.engine.url)
    with _table_names_cache_lock:
        if db_url not in _table_names_cache:
            # Use the session's own connection rather than acquiring a fresh one from
            # the engine.  Acquiring a separate connection (and returning it) causes
            # SQLAlchemy to issue a ROLLBACK on the shared connection when using
            # StaticPool (e.g. SQLite in-memory during tests), which silently undoes
            # any changes already flushed by the current session.
            conn = db.session.connection()
            inspector = sa.inspect(conn)
            _table_names_cache[db_url] = set(inspector.get_table_names())
        return _table_names_cache[db_url]


def _get_table_columns(table_name: str) -> set[str]:
    """Return the set of column names for a table on the current engine."""
    db_url = str(db.engine.url)
    cache_key = (db_url, table_name)
    with _table_names_cache_lock:
        if cache_key not in _table_columns_cache:
            conn = db.session.connection()
            inspector = sa.inspect(conn)
            _table_columns_cache[cache_key] = {
                column["name"] for column in inspector.get_columns(table_name)
            }
        return _table_columns_cache[cache_key]


def _build_pending_class_timezone_payload(class_row: ClassEconomy) -> dict:
    return {
        "class_id": class_row.class_id,
        "join_code": class_row.join_code,
        "class_identifier": class_row.display_name or class_row.join_code,
        "display_name": class_row.display_name,
        "class_timezone": class_row.class_timezone,
    }


def _class_timezone_needs_confirmation(class_row: ClassEconomy | None) -> bool:
    if class_row is None:
        return False
    timezone_name = (class_row.class_timezone or "").strip()
    return timezone_name in ("", "UTC")


def _queue_pending_class_timezone_confirmation(class_row: ClassEconomy | None):
    if not _class_timezone_needs_confirmation(class_row):
        return

    pending = session.get("pending_class_timezone_confirmations", [])
    if any(item.get("class_id") == class_row.class_id for item in pending):
        return

    pending.append(_build_pending_class_timezone_payload(class_row))
    session["pending_class_timezone_confirmations"] = pending
    session.modified = True


def _consume_pending_class_timezone_confirmations(admin_id: int | None) -> list[dict]:
    pending = session.get("pending_class_timezone_confirmations", [])
    if not pending or not admin_id:
        return []

    class_ids = [item.get("class_id") for item in pending if item.get("class_id")]
    if not class_ids:
        session.pop("pending_class_timezone_confirmations", None)
        return []

    class_rows = {
        row.class_id: row
        for row in ClassEconomy.query.filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.class_id.in_(class_ids),
        ).all()
    }

    refreshed = []
    for item in pending:
        class_row = class_rows.get(item.get("class_id"))
        if not _class_timezone_needs_confirmation(class_row):
            continue
        refreshed.append(_build_pending_class_timezone_payload(class_row))

    if refreshed:
        session["pending_class_timezone_confirmations"] = refreshed
    else:
        session.pop("pending_class_timezone_confirmations", None)
    session.modified = True
    return refreshed


def _remove_pending_class_timezone_confirmation(class_id: str):
    pending = session.get("pending_class_timezone_confirmations", [])
    filtered = [item for item in pending if item.get("class_id") != class_id]
    if filtered:
        session["pending_class_timezone_confirmations"] = filtered
    else:
        session.pop("pending_class_timezone_confirmations", None)
    session.modified = True


def _ensure_join_code_anchors(teacher_id, join_code, class_label=None, return_metadata: bool = False):
    """Ensure the canonical class row and membership exist before child inserts."""
    if not teacher_id or not join_code:
        return (None, False, None) if return_metadata else None

    economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    created = False
    if economy is not None:
        if economy.teacher_id != teacher_id:
            raise ValueError("Join code belongs to a different teacher.")
        if class_label and not economy.display_name:
            economy.display_name = class_label
        if economy.created_by_admin_id is None:
            economy.created_by_admin_id = teacher_id
    else:
        economy = ClassEconomy(
            join_code=join_code,
            teacher_id=teacher_id,
            created_by_admin_id=teacher_id,
            display_name=class_label,
        )
        db.session.add(economy)
        created = True
    if economy.class_id is None:
        db.session.flush()

    admin_membership = ClassMembership.query.filter_by(
        class_id=economy.class_id,
        join_code=join_code,
        admin_id=teacher_id,
    ).first()
    if not admin_membership:
        db.session.add(ClassMembership(
            class_id=economy.class_id,
            join_code=join_code,
            admin_id=teacher_id,
            role="admin",
        ))

    teacher_seat = Seat.query.filter_by(
        class_id=economy.class_id,
        role="teacher",
    ).first()
    if teacher_seat is None:
        db.session.add(Seat(
            class_id=economy.class_id,
            join_code=join_code,
            role="teacher",
        ))

    db.session.flush()
    if return_metadata:
        return economy.class_id, created, economy
    return economy.class_id


def _generate_unique_teacher_join_code(block: str) -> str:
    """Generate a teacher-scoped join code, falling back to a timestamp suffix."""
    for _ in range(MAX_JOIN_CODE_RETRIES):
        candidate = generate_join_code()
        if not ClassEconomy.query.filter_by(join_code=candidate).first():
            return candidate

    block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
    timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
    return f"B{block_initial}{timestamp_suffix:04d}"


def _resolve_student_add_class_context(admin_id: int | None, block: str) -> dict | None:
    """Resolve the target class for add-student flows, creating one when requested."""
    if not admin_id:
        return None

    block_select = (request.form.get('block_select') or '').strip()
    if block_select != '__CREATE_NEW__':
        return _resolve_admin_class_context(admin_id)

    if not block:
        return None

    class_name = (request.form.get('class_name') or '').strip()
    class_label = class_name or block
    join_code = _generate_unique_teacher_join_code(block)
    class_id, class_created, class_row = _ensure_join_code_anchors(
        admin_id,
        join_code,
        class_label=class_label,
        return_metadata=True,
    )
    _ensure_teacher_student_seat(admin_id, join_code, block)
    session['current_join_code'] = join_code
    return {
        'join_code': join_code,
        'class_id': class_id,
        'block': block,
        'class_created': class_created,
        'class_row': class_row,
    }


def _link_student_to_admin(
    student: Student,
    admin_id,
    *,
    join_code: str | None = None,
    class_id: str | None = None,
    class_label: str | None = None,
    block: str | None = None,
):
    """
    Ensure the given admin is associated with the student.
    Creates a StudentTeacher link and a claimed Seat record.
    """
    if not admin_id:
        return

    target_block = (block or student.block or "").strip().upper()

    if not target_block:
        current_app.logger.warning(
            "Selected student has no block assigned, skipping Seat creation"
        )
        return

    # 1. Create StudentTeacher link
    existing_link = StudentTeacher.query.filter_by(student_id=student.id, teacher_id=admin_id).first()
    if not existing_link:
        db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin_id, join_code=join_code))
    elif join_code and not existing_link.join_code:
        existing_link.join_code = join_code

    target_join_code = join_code
    target_class_id = class_id

    if target_join_code:
        if not target_class_id:
            target_class_id = _resolve_class_id(admin_id, target_join_code)
    else:
        # Find or create a join_code for this teacher+block combo via ClassEconomy.
        existing_class = ClassEconomy.query.filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section == target_block,
        ).first()
        if existing_class and existing_class.join_code:
            target_join_code = existing_class.join_code
            target_class_id = existing_class.class_id
        else:
            from app.utils.join_code import generate_join_code as _gen_jc
            target_join_code = _gen_jc()
        if not target_class_id:
            target_class_id = _resolve_class_id(admin_id, target_join_code)

    # 2. Ensure ClassEconomy record exists.
    _ensure_join_code_anchors(admin_id, target_join_code, class_label=class_label)

    # 3. Create or update Seat record.
    existing_seat = Seat.query.filter_by(
        student_id=student.id,
        class_id=target_class_id,
    ).first()

    if not existing_seat:
        from app.hash_utils import hash_username_lookup as _h
        new_seat = Seat(
            class_id=target_class_id,
            student_id=student.id,
            role='student',
            block_identifier=target_block,
            block=target_block,
            join_code=target_join_code,
            claim_first_name_hash=_h(student.first_name.lower()) if student.first_name else None,
            claim_last_name_hash=_h(student.last_initial.lower()) if student.last_initial else None,
            roster_fingerprint=_h(
                f"{target_class_id}|{(student.first_name or '').lower()}|{(student.last_initial or '').lower()}"
            ),
            claimed_at=utc_now(),
        )
        db.session.add(new_seat)
        db.session.flush()
        profile = IdentityProfile(
            seat_id=new_seat.id,
            profile_type='student',
            first_name=student.first_name,
            last_initial=student.last_initial,
        )
        db.session.add(profile)
        current_app.logger.info(
            "Created claimed Seat for student %s, teacher %s, block %s",
            student.id, admin_id, target_block,
        )
    else:
        if not existing_seat.claimed_at:
            existing_seat.claimed_at = utc_now()
        existing_seat.class_id = existing_seat.class_id or target_class_id
        current_app.logger.info(
            "Claimed existing Seat %s for student %s", existing_seat.id, student.id
        )


def _get_feature_settings(teacher_id, block=None):
    """
    Get class-scoped feature settings for a teacher block.

    Args:
        teacher_id: The teacher's admin ID
        block: Optional block/period name (e.g., "A", "B", "1")

    Returns:
        dict: Feature settings with all toggle values
    """
    if not block:
        return FeatureSettings.get_defaults()
    scoped_features = get_class_feature_settings(teacher_id, block=block)
    if scoped_features:
        return scoped_features["features"]
    return FeatureSettings.get_defaults()


def _resolve_join_code_for_block(admin_id, block_name):
    if not block_name:
        return None
    row = (
        ClassEconomy.query
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section == block_name,
            ClassEconomy.join_code.isnot(None),
        )
        .first()
    )
    return row.join_code if row and row.join_code else None


def _build_economy_snapshot_from_analysis(class_id, join_code, checker, analysis):
    recommendations = analysis.recommendations or {}
    rent = recommendations.get('rent') or {}
    insurance = recommendations.get('insurance_premium_weekly') or {}
    store_tiers = recommendations.get('store_tiers') or {}
    return EconomySnapshot(
        class_id=class_id,
        join_code=join_code,
        policy_mode=checker.policy_mode,
        pay_rate=Decimal(str(analysis.cwi.pay_rate_per_minute or 0)),
        expected_hours=Decimal(str((analysis.cwi.expected_weekly_minutes or 0) / 60.0)).quantize(Decimal('0.01')),
        weekly_cwi=Decimal(str(analysis.cwi.cwi or 0)).quantize(Decimal('0.01')),
        rent_min=Decimal(str(rent.get('min', 0))).quantize(Decimal('0.01')),
        rent_recommended=Decimal(str(rent.get('recommended', 0))).quantize(Decimal('0.01')),
        rent_max=Decimal(str(rent.get('max', 0))).quantize(Decimal('0.01')),
        insurance_weekly_min=Decimal(str(insurance.get('min', 0))).quantize(Decimal('0.01')),
        insurance_weekly_recommended=Decimal(str(insurance.get('recommended', 0))).quantize(Decimal('0.01')),
        insurance_weekly_max=Decimal(str(insurance.get('max', 0))).quantize(Decimal('0.01')),
        store_tier_min={
            key: str(_quantize_currency((values or {}).get('min', 0)))
            for key, values in store_tiers.items()
        },
        store_tier_max={
            key: str(_quantize_currency((values or {}).get('max', 0)))
            for key, values in store_tiers.items()
        },
        analysis_payload=_serialize_economy_analysis_payload(analysis),
    )


def _economy_refresh_timezone():
    return pytz.timezone(current_app.config.get('ECONOMY_REFRESH_TIMEZONE', 'America/Los_Angeles'))


def _json_safe_value(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    return value


def _economy_weekly_refresh_bounds(now_utc=None):
    now = ensure_utc(now_utc or utc_now())
    local_now = now.astimezone(_economy_refresh_timezone())
    days_since_sunday = (local_now.weekday() + 1) % 7
    weekly_start_local = (local_now - timedelta(days=days_since_sunday)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    next_weekly_start_local = weekly_start_local + timedelta(days=7)
    return ensure_utc(weekly_start_local), ensure_utc(next_weekly_start_local)


def _economy_monthly_refresh_bounds(now_utc=None):
    now = ensure_utc(now_utc or utc_now())
    local_now = now.astimezone(_economy_refresh_timezone())
    monthly_start_local = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if monthly_start_local.month == 12:
        next_monthly_start_local = monthly_start_local.replace(year=monthly_start_local.year + 1, month=1)
    else:
        next_monthly_start_local = monthly_start_local.replace(month=monthly_start_local.month + 1)
    return ensure_utc(monthly_start_local), ensure_utc(next_monthly_start_local)


def _economy_analysis_schedule(snapshot=None, *, now_utc=None, frozen=True):
    current_time = ensure_utc(now_utc or utc_now())
    weekly_window_start, next_weekly_refresh = _economy_weekly_refresh_bounds(current_time)
    monthly_window_start, next_monthly_refresh = _economy_monthly_refresh_bounds(current_time)
    last_updated = ensure_utc(snapshot.effective_at) if snapshot and snapshot.effective_at else current_time
    return {
        'frozen': frozen,
        'last_updated_at': last_updated.isoformat(),
        'refresh_timezone': _economy_refresh_timezone().zone,
        'weekly_refresh_label': 'Sunday 12:00 AM',
        'monthly_refresh_label': '1st of each month 12:00 AM',
        'weekly_window_start_at': weekly_window_start.isoformat(),
        'monthly_window_start_at': monthly_window_start.isoformat(),
        'next_weekly_refresh_at': next_weekly_refresh.isoformat(),
        'next_monthly_refresh_at': next_monthly_refresh.isoformat(),
    }


def _serialize_economy_analysis_payload(analysis, *, snapshot=None, now_utc=None, frozen=True):
    warnings_by_level = {
        'critical': [],
        'warning': [],
        'info': [],
    }
    warning_items = []

    for warning in analysis.warnings:
        warning_payload = {
            'feature': warning.feature,
            'level': warning.level.value,
            'message': warning.message,
            'current_value': _json_safe_value(warning.current_value),
            'recommended_min': _json_safe_value(warning.recommended_min),
            'recommended_max': _json_safe_value(warning.recommended_max),
            'cwi_ratio': _json_safe_value(warning.cwi_ratio),
        }
        warning_items.append(warning_payload)
        warnings_by_level[warning.level.value].append(warning_payload)

    return {
        'status': 'success',
        'cwi': _json_safe_value(analysis.cwi.cwi),
        'is_balanced': analysis.is_balanced,
        'budget_survival_test_passed': analysis.budget_survival_test_passed,
        'weekly_savings': _json_safe_value(analysis.weekly_savings),
        'warnings': warnings_by_level,
        'warning_items': warning_items,
        'recommendations': _json_safe_value(analysis.recommendations),
        'cwi_breakdown': {
            'pay_rate_per_hour': float(analysis.cwi.pay_rate_per_minute) * 60,
            'pay_rate_per_minute': float(analysis.cwi.pay_rate_per_minute),
            'expected_weekly_hours': float(analysis.cwi.expected_weekly_minutes) / 60.0,
            'expected_weekly_minutes': float(analysis.cwi.expected_weekly_minutes),
            'notes': _json_safe_value(analysis.cwi.notes),
        },
        'analysis_schedule': _economy_analysis_schedule(snapshot, now_utc=now_utc, frozen=frozen),
    }


def _deserialize_economy_analysis_payload(payload):
    if not payload:
        return None

    warnings = []
    for warning in payload.get('warning_items', []):
        warnings.append(SimpleNamespace(
            feature=warning.get('feature'),
            message=warning.get('message'),
            current_value=warning.get('current_value'),
            recommended_min=warning.get('recommended_min'),
            recommended_max=warning.get('recommended_max'),
            cwi_ratio=warning.get('cwi_ratio'),
            level=SimpleNamespace(value=warning.get('level', 'info')),
        ))

    breakdown = payload.get('cwi_breakdown') or {}
    cwi = SimpleNamespace(
        cwi=payload.get('cwi'),
        pay_rate_per_minute=breakdown.get('pay_rate_per_minute'),
        expected_weekly_minutes=breakdown.get('expected_weekly_minutes'),
        notes=breakdown.get('notes') or [],
    )
    return SimpleNamespace(
        cwi=cwi,
        is_balanced=payload.get('is_balanced'),
        budget_survival_test_passed=payload.get('budget_survival_test_passed'),
        weekly_savings=payload.get('weekly_savings'),
        warnings=warnings,
        recommendations=payload.get('recommendations') or {},
        analysis_schedule=payload.get('analysis_schedule') or {},
    )


def _current_economy_snapshot_inputs(checker, payroll_settings, expected_weekly_hours=None):
    pay_rate = Decimal(str(payroll_settings.pay_rate or 0)).quantize(Decimal('0.0001'))
    source_hours = expected_weekly_hours
    if source_hours is None:
        source_hours = payroll_settings.expected_weekly_hours if payroll_settings.expected_weekly_hours is not None else 5.0
    hours = Decimal(str(source_hours)).quantize(Decimal('0.01'))
    return {
        'policy_mode': checker.policy_mode,
        'pay_rate': pay_rate,
        'expected_hours': hours,
    }


def _economy_snapshot_matches_inputs(snapshot, *, expected_inputs):
    if not snapshot:
        return False
    return (
        snapshot.policy_mode == expected_inputs['policy_mode']
        and Decimal(str(snapshot.pay_rate)).quantize(Decimal('0.0001')) == expected_inputs['pay_rate']
        and Decimal(str(snapshot.expected_hours)).quantize(Decimal('0.01')) == expected_inputs['expected_hours']
    )


def _get_frozen_economy_analysis_payload(
    admin_id,
    block,
    checker,
    payroll_settings,
    *,
    rent_settings=None,
    insurance_policies=None,
    fines=None,
    store_items=None,
    expected_weekly_hours=None,
    persist_snapshot=False,
):
    expected_inputs = _current_economy_snapshot_inputs(
        checker,
        payroll_settings,
        expected_weekly_hours=expected_weekly_hours,
    )
    class_id = getattr(payroll_settings, "class_id", None)
    join_code = _resolve_join_code_for_block(admin_id, block)
    weekly_window_start, _next_weekly_refresh = _economy_weekly_refresh_bounds()
    weekly_window_start_db = normalize_for_db(weekly_window_start)
    latest_snapshot = None

    if class_id and expected_weekly_hours is None:
        latest_snapshot = (
            EconomySnapshot.query
            .filter(
                EconomySnapshot.class_id == class_id,
                EconomySnapshot.effective_at >= weekly_window_start_db,
            )
            .order_by(EconomySnapshot.effective_at.desc(), EconomySnapshot.id.desc())
            .first()
        )
        if _economy_snapshot_matches_inputs(latest_snapshot, expected_inputs=expected_inputs) and latest_snapshot.analysis_payload:
            payload = dict(latest_snapshot.analysis_payload)
            payload['analysis_schedule'] = _economy_analysis_schedule(latest_snapshot, frozen=True)
            payload['snapshot_cached'] = True
            return payload, latest_snapshot

    analysis = checker.analyze_economy(
        payroll_settings=payroll_settings,
        rent_settings=rent_settings,
        insurance_policies=insurance_policies,
        fines=fines,
        store_items=store_items,
        expected_weekly_hours=float(expected_inputs['expected_hours']),
    )

    if class_id and expected_weekly_hours is None:
        if persist_snapshot:
            snapshot = _build_economy_snapshot_from_analysis(class_id, join_code, checker, analysis)
            db.session.add(snapshot)
            db.session.flush()
            payload = _serialize_economy_analysis_payload(analysis, snapshot=snapshot, frozen=True)
            payload['snapshot_cached'] = False
            return payload, snapshot

        payload = _serialize_economy_analysis_payload(analysis, frozen=True)
        payload['analysis_schedule'] = _economy_analysis_schedule(None, frozen=False)
        payload['snapshot_cached'] = False
        return payload, None

    payload = _serialize_economy_analysis_payload(analysis, frozen=False)
    payload['snapshot_cached'] = False
    return payload, None


def _resolve_payroll_settings_for_block(admin_id, block_name):
    if not block_name:
        return None
    class_row = ClassEconomy.query.filter(
        ClassEconomy.teacher_id == admin_id,
        ClassEconomy.section == block_name,
        ClassEconomy.class_id.isnot(None),
    ).first()
    class_id = class_row.class_id if class_row else None
    if not class_id:
        return None
    return (
        PayrollSettings.query.filter(
            PayrollSettings.class_id == class_id,
            PayrollSettings.is_active.is_(True),
        )
        .order_by(desc(PayrollSettings.block.isnot(None)))
        .first()
    )


def _resolve_rent_settings_for_block(admin_id, block_name):
    if not block_name:
        return None
    join_code = _resolve_join_code_for_block(admin_id, block_name)
    if not join_code:
        return None
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        return None
    return (
        RentSettings.query.filter(
            RentSettings.class_id == class_row.class_id,
            RentSettings.is_enabled.is_(True),
        )
        .order_by(desc(RentSettings.block.isnot(None)))
        .first()
    )


def _resolve_banking_settings_for_block(admin_id, block_name):
    if not block_name:
        return None
    join_code = _resolve_join_code_for_block(admin_id, block_name)
    if not join_code:
        return None
    class_row = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(
        teacher_id=admin_id,
        join_code=join_code,
    ).first()
    if not class_row or not class_row[0]:
        return None
    return (
        BankingSettings.query.filter(
            BankingSettings.class_id == class_row[0],
            BankingSettings.is_active.is_(True),
        )
        .order_by(desc(BankingSettings.block.isnot(None)))
        .first()
    )


def _format_money(value):
    if value is None:
        return "-"
    return f"${Decimal(str(value)):.2f}"


def _format_frequency_label(frequency, custom_frequency_value=None, custom_frequency_unit=None):
    frequency = (frequency or '').lower()
    if frequency == 'custom':
        unit = (custom_frequency_unit or 'days').lower()
        count = custom_frequency_value or 1
        return f"every {count} {unit}"
    if frequency:
        return frequency
    return "configured cadence"


def _warning_to_alignment(level_value):
    if level_value == 'critical':
        return 'significantly_off'
    if level_value == 'warning':
        return 'slightly_off'
    return 'aligned'


def _max_alignment(statuses):
    rank = {'aligned': 0, 'slightly_off': 1, 'significantly_off': 2}
    return max(statuses, key=lambda item: rank.get(item, 0)) if statuses else 'aligned'


def _warning_feature_prefixes_for_policy(policy):
    title = getattr(policy, 'title', '')
    return {
        f'Insurance: {title}',
        f'Coverage: {title}',
        f'Period Cap: {title}',
        f'Waiting Period: {title}',
    }


def _is_actionable_economy_warning(warning):
    level = getattr(getattr(warning, 'level', None), 'value', None) or getattr(warning, 'level', None)
    return level in {'critical', 'warning'}


def _is_bypassed_economy_warning(warning, rent_settings, insurance_policies, store_items):
    feature = getattr(warning, 'feature', '')
    if feature == 'Rent' and rent_settings and getattr(rent_settings, 'bypass_cwi_warnings', False):
        return True

    for policy in insurance_policies or []:
        if getattr(policy, 'bypass_cwi_warnings', False) and feature in _warning_feature_prefixes_for_policy(policy):
            return True

    for item in store_items or []:
        if getattr(item, 'bypass_cwi_warnings', False) and feature == f'Store Item: {item.name}':
            return True

    return False


def _filter_economy_health_warnings(analysis, rent_settings, insurance_policies, fines, store_items, *, selected_block=None):
    filtered = []
    for warning in analysis.warnings if analysis else []:
        if not _is_actionable_economy_warning(warning):
            continue
        if _is_bypassed_economy_warning(warning, rent_settings, insurance_policies, store_items):
            continue
        filtered.append(warning)

    warnings_by_level = {'critical': [], 'warning': [], 'info': []}
    warnings_by_feature = {}
    for warning in filtered:
        warnings_by_level[warning.level.value].append(warning)
        warnings_by_feature.setdefault(warning.feature, []).append(warning)

    insurance_prefixes = set()
    for policy in insurance_policies or []:
        if getattr(policy, 'bypass_cwi_warnings', False):
            continue
        insurance_prefixes.update(_warning_feature_prefixes_for_policy(policy))

    summary_rows = []

    def add_summary(label, count, link_label, link_href):
        if count <= 0:
            return
        summary_rows.append({
            'label': label,
            'count': count,
            'link_label': link_label,
            'link_href': link_href,
        })

    add_summary(
        'Rent',
        len([w for w in filtered if w.feature == 'Rent']) if rent_settings else 0,
        'Adjust rent',
        url_for('admin.rent_settings', settings_block=selected_block) if rent_settings else None,
    )
    add_summary(
        'Insurance',
        len([w for w in filtered if w.feature in insurance_prefixes]),
        'Review insurance',
        url_for('admin.insurance_management', settings_block=selected_block),
    )
    add_summary(
        'Fees',
        len([w for w in filtered if w.feature.startswith('Fine:')]) if fines else 0,
        'Review payroll fines',
        url_for('admin.payroll', cwi_block=selected_block),
    )
    add_summary(
        'Store',
        len([w for w in filtered if w.feature.startswith('Store Item:')]) if store_items else 0,
        'Update store',
        url_for('admin.store_management'),
    )

    return filtered, warnings_by_level, warnings_by_feature, summary_rows


def _build_policy_summary(class_scope, analysis, rent_settings, insurance_policies, fines, *, warnings=None):
    settings_row = get_feature_settings_row_for_class(class_scope.get('class_id'), create=False)
    policy_mode = normalize_policy_mode(getattr(settings_row, 'economy_policy_mode', 'default'))

    categories = []

    def add_category(key, label, warnings):
        if not warnings:
            return
        severity = _max_alignment([_warning_to_alignment(w.level.value) for w in warnings])
        categories.append({
            'key': key,
            'label': label,
            'status': severity,
            'warning_count': len(warnings),
        })

    warning_items = warnings if warnings is not None else (analysis.warnings if analysis else [])
    add_category('rent', 'Rent', [w for w in warning_items if w.feature == 'Rent'] if rent_settings else [])
    add_category(
        'insurance',
        'Insurance',
        [w for w in warning_items if w.feature.startswith(('Insurance:', 'Coverage:', 'Period Cap:', 'Waiting Period:'))] if insurance_policies else []
    )
    add_category('fine', 'Fees', [w for w in warning_items if w.feature.startswith('Fine:')] if fines else [])
    overall_status = _max_alignment([category['status'] for category in categories])

    return {
        'settings_row': settings_row,
        'mode': policy_mode,
        'profile': POLICY_MODES[policy_mode],
        'categories': categories,
        'overall_status': overall_status,
        'is_aligned': overall_status == 'aligned',
        'updated_at': getattr(settings_row, 'economy_policy_updated_at', None),
        'has_pending_policy_transition': bool(get_pending_policy_transition_count(getattr(settings_row, 'class_id', None))),
    }


def _extract_pending_rebalance_effective_at(policy_summary: dict) -> datetime | None:
    """Return the next known effective timestamp for a pending policy transition."""
    settings_row = policy_summary.get('settings_row')
    class_id = getattr(settings_row, 'class_id', None) if settings_row else None
    return get_pending_policy_transition_effective_at(class_id)


def _build_rebalance_preview(admin_id, selected_block, checker, cwi, rent_settings, insurance_policies):
    preview_items = []
    recommendations = get_price_recommendation_context(checker.policy_mode, cwi) or {}

    if rent_settings and rent_settings.is_enabled:
        recommended_amount = convert_weekly_amount_to_frequency(
            Decimal(str(recommendations['rent_weekly']['recommended'])),
            rent_settings.frequency_type,
            custom_frequency_value=rent_settings.custom_frequency_value,
            custom_frequency_unit=getattr(rent_settings, 'custom_frequency_unit', None),
        )
        current_amount = Decimal(str(rent_settings.rent_amount or 0))
        if current_amount != recommended_amount:
            preview_items.append({
                'key': 'rent',
                'label': 'Rent',
                'current': f"{_format_money(current_amount)} / {_format_frequency_label(rent_settings.frequency_type, rent_settings.custom_frequency_value, getattr(rent_settings, 'custom_frequency_unit', None))}",
                'recommended': f"{_format_money(recommended_amount)} / {_format_frequency_label(rent_settings.frequency_type, rent_settings.custom_frequency_value, getattr(rent_settings, 'custom_frequency_unit', None))}",
                'apply_by_default': True,
                'change': {
                    'type': 'rent',
                    'block': selected_block,
                    'join_code': _resolve_join_code_for_block(admin_id, selected_block),
                    'current_value': str(current_amount),
                    'new_value': str(recommended_amount),
                },
            })

    recommended_insurance_weekly = Decimal(str(recommendations['insurance_premium_weekly']['recommended']))
    for policy in insurance_policies or []:
        if not policy.is_active:
            continue
        current_premium = Decimal(str(policy.premium or 0))
        recommended_premium = convert_weekly_amount_to_frequency(
            recommended_insurance_weekly,
            policy.charge_frequency,
        )
        if current_premium == recommended_premium:
            continue
        preview_items.append({
            'key': f'insurance_{policy.id}',
            'label': f'Insurance Premium: {policy.title}',
            'current': f"{_format_money(current_premium)} / {_format_frequency_label(policy.charge_frequency)}",
            'recommended': f"{_format_money(recommended_premium)} / {_format_frequency_label(policy.charge_frequency)}",
            'apply_by_default': True,
            'change': {
                'type': 'insurance',
                'policy_id': policy.id,
                'current_value': str(current_premium),
                'new_value': str(recommended_premium),
                'title': policy.title,
            },
        })

    return preview_items


def _build_insurance_recommendation_context(admin_id, *, block=None, charge_frequency='weekly'):
    payroll_settings = _resolve_admin_payroll_settings_for_block(admin_id, block)
    if not payroll_settings:
        return None

    checker = EconomyBalanceChecker(admin_id, block, class_id=getattr(payroll_settings, "class_id", None))
    cwi_calc = checker.calculate_cwi(payroll_settings)
    return get_insurance_premium_recommendation(
        checker.policy_mode,
        Decimal(str(cwi_calc.cwi)),
        frequency=charge_frequency,
    )


def _load_economy_rebalance_context(admin_id, selected_block):
    class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=admin_id)
    payroll_query = PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(sa.select(class_ids_query.subquery())),
        PayrollSettings.is_active.is_(True),
    )
    all_payroll_settings = payroll_query.order_by(PayrollSettings.block.asc()).all()
    settings_by_block = {s.block: s for s in all_payroll_settings if s.block}

    payroll_settings = _resolve_payroll_settings_for_block(admin_id, selected_block) if selected_block else None
    effective_block = selected_block

    if not payroll_settings and all_payroll_settings:
        first_class_setting = next((s for s in all_payroll_settings if s.block), None)
        if first_class_setting:
            payroll_settings = first_class_setting
            effective_block = first_class_setting.block

    rent_settings = _resolve_rent_settings_for_block(admin_id, effective_block) if effective_block else None

    class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=admin_id)
    insurance_policies_query = InsurancePolicy.query.filter(
        InsurancePolicy.class_id.in_(sa.select(class_ids_query.subquery())),
        InsurancePolicy.is_active.is_(True),
    )
    if effective_block:
        insurance_policies = [
            policy for policy in insurance_policies_query.all()
            if not policy.blocks_list or effective_block.upper() in [b.upper() for b in policy.blocks_list]
        ]
    else:
        insurance_policies = insurance_policies_query.all()

    return effective_block, payroll_settings, rent_settings, insurance_policies, all_payroll_settings


def _apply_rebalance_plan(admin_id, settings_row, change_plan, activation_mode):
    applied_labels = apply_rebalance_changes(admin_id, settings_row, change_plan, activation_mode)
    current_app.logger.info(
        "Applied economy rebalance for teacher=%s class_id=%s activation=%s changes=%s",
        admin_id,
        settings_row.class_id,
        activation_mode,
        applied_labels,
    )
    return applied_labels


def _get_or_create_onboarding(teacher_id):
    """
    Get or create onboarding record for a teacher.

    Args:
        teacher_id: The teacher's admin ID

    Returns:
        Teacher onboarding record view
    """
    return get_or_create_teacher_onboarding(teacher_id, utc_now())


def _check_onboarding_redirect():
    """
    Check if the current admin needs onboarding and should be redirected.

    NOTE: As of the widget-based onboarding redesign, we no longer force redirect
    teachers to the onboarding wizard. Instead, they see the Getting Started widget
    in the bottom-right corner of the dashboard.

    Returns:
        None - onboarding redirect disabled in favor of floating widget
    """
    admin_id = session.get('admin_id')
    if not admin_id:
        return None

    # Check if teacher has completed or skipped onboarding
    onboarding = get_teacher_onboarding(admin_id)

    # If no onboarding record exists, teacher needs onboarding
    if not onboarding:
        # Check if teacher has any existing students - if so, they're a legacy teacher
        # and we should skip onboarding for them
        admin = db.session.get(Admin, admin_id)
        if admin and admin.has_assigned_students:
            # Legacy teacher - create completed onboarding record
            create_legacy_completed_teacher_onboarding(admin_id, utc_now())
            return None

        # New teacher - no redirect, they'll see the Getting Started widget
        return None

    # No redirect - widget-based onboarding is now used instead
    return None


def _normalize_claim_credentials_for_admin(admin_id: int) -> int:
    """No-op: TeacherBlock-based hash normalization has been removed.

    Kept as a stub to avoid breaking any callers that have not yet been removed.
    Returns 0 always.
    """
    return 0

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics, pending actions, and recent activity."""
    # Check if teacher needs onboarding
    onboarding_redirect = _check_onboarding_redirect()
    if onboarding_redirect:
        return onboarding_redirect
    current_admin_id = session.get('admin_id')

    # Fetch active system announcements for teachers
    now = utc_now()
    system_announcements = Announcement.query.filter(
        Announcement.is_active == True,
        sa.or_(Announcement.expires_at == None, Announcement.expires_at > now),
        Announcement.audience_type.in_(['system_wide', 'all_teachers'])
    ).order_by(Announcement.created_at.desc()).all()

    student_ids_subq = _student_scope_subquery()
    # INV-ARC-007: dashboard GET must remain read-only.
    # Daily-limit auto tap-out is handled by scheduled tasks and explicit POST
    # trigger (`/admin/enforce-daily-limits`).

    # Get all students for calculations
    students = _scoped_students().order_by(Student.first_name).all()
    student_lookup = {s.id: s for s in students}

    # Quick Stats
    total_students = len(students)

    # Optimized balance calculation (scoped to teacher's classes)
    student_ids = [s.id for s in students]
    # Fetch all join codes for this teacher via ClassEconomy (canonical source).
    teacher_join_codes = _get_admin_owned_join_codes(current_admin_id)

    teacher_class_ids = [
        class_id
        for (class_id,) in db.session.query(ClassEconomy.class_id).filter(
            ClassEconomy.join_code.in_(teacher_join_codes)
        ).all()
        if class_id
    ]

    seats = Seat.query.filter(Seat.class_id.in_(teacher_class_ids), Seat.role == 'student').all()
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    batch_balances = get_batch_balances_by_class_seat(class_seat_pairs)

    # Sum up balances
    total_balance_decimal = Decimal('0.00')
    for bal in batch_balances.values():
        total_balance_decimal += Decimal(bal['checking_cents']) / 100
        total_balance_decimal += Decimal(bal['savings_cents']) / 100

    total_balance = float(total_balance_decimal)
    avg_balance = total_balance / total_students if total_students > 0 else 0

    # Pending actions - count all types of pending approvals
    pending_redemptions_count = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StudentItem.status == 'processing')
        .count()
    )
    pending_hall_passes_count = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(HallPassLog.join_code.in_(teacher_join_codes))
        .filter(HallPassLog.status == 'pending')
        .count()
    )
    pending_insurance_claims_count = (
        InsuranceClaim.query
        .join(Seat, InsuranceClaim.seat_id == Seat.id)
        .filter(Seat.student_id.in_(sa.select(student_ids_subq)))
        .filter(InsuranceClaim.status == 'pending')
        .count()
    )
    total_pending_actions = pending_redemptions_count + pending_hall_passes_count + pending_insurance_claims_count

    # Get recent items for each pending type (limited for display)
    recent_redemptions = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StudentItem.status == 'processing')
        .order_by(StudentItem.redemption_date.desc())
        .limit(5)
        .all()
    )
    recent_hall_passes = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(HallPassLog.join_code.in_(teacher_join_codes))
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.desc())
        .limit(5)
        .all()
    )
    recent_insurance_claims = (
        InsuranceClaim.query
        .join(Seat, InsuranceClaim.seat_id == Seat.id)
        .filter(Seat.student_id.in_(sa.select(student_ids_subq)))
        .filter(InsuranceClaim.status == 'pending')
        .order_by(InsuranceClaim.filed_date.desc())
        .limit(5)
        .all()
    )

    # Recent transactions (limited to 5 for display)
    recent_transactions = (
        Transaction.query
        .filter(Transaction.class_id.in_(teacher_class_ids))
        .filter_by(is_void=False)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
    today_start_utc, _ = day_bounds_utc()
    today_start_db = normalize_for_db(today_start_utc)
    total_transactions_today = (
        Transaction.query
        .filter(Transaction.class_id.in_(teacher_class_ids))
        .filter(
            Transaction.timestamp >= today_start_db,
            Transaction.is_void == False,
        )
        .count()
    )

    # Recent attendance logs (limited to 5 for display)
    raw_logs = (
        db.session.query(TapEvent, Student)
        .join(Student, TapEvent.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .order_by(TapEvent.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_logs = []
    for log, student in raw_logs:
        recent_logs.append({
            'student_id': log.student_id,
            'student_name': student.full_name if student else 'Unknown',
            'period': log.period,
            'timestamp': log.timestamp,
            'reason': log.reason,
            'status': log.status
        })

    # --- Payroll Info ---
    dashboard_blocks = sorted({b.strip() for s in students for b in (s.block or "").split(',') if b.strip()})
    dashboard_join_codes_by_block = _get_join_codes_by_block(current_admin_id, dashboard_blocks)
    payroll_preview = _build_payroll_preview_state(students, dashboard_join_codes_by_block)
    payroll_summary = payroll_preview["total_summary"]
    payroll_updated_at = payroll_preview["latest_updated_at"]
    total_payroll_estimate = sum(payroll_summary.values())

    # Calculate next payroll date (keep in UTC for template conversion)
    anchor_candidates = [
        anchor + timedelta(days=14)
        for anchor in payroll_preview["anchor_by_join_code"].values()
        if anchor is not None
    ]
    if anchor_candidates:
        next_payroll_date = min(anchor_candidates)
    else:
        now_utc = utc_now()
        days_until_friday = (4 - now_utc.weekday() + 7) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_payroll_date = now_utc + timedelta(days=days_until_friday)

    # v2: DOB-based recovery setup prompt is disabled.
    show_recovery_setup = False

    # Prompt legacy teachers to upgrade insurance policies to the new tiered design
    show_insurance_tier_prompt = False
    onboarding_record = get_teacher_onboarding(session['admin_id'])
    if onboarding_record and onboarding_record.steps_completed and onboarding_record.steps_completed.get("needs_insurance_tier_upgrade"):
        class_ids_subq = (
            db.session.query(ClassEconomy.class_id)
            .filter(ClassEconomy.teacher_id == session['admin_id'])
            .subquery()
        )
        legacy_policy_exists = (
            db.session.query(InsurancePolicy.id)
            .filter(InsurancePolicy.class_id.in_(sa.select(class_ids_subq)))
            .filter(InsurancePolicy.tier_category_id.is_(None))
            .filter(InsurancePolicy.tier_level.is_(None))
            .first()
            is not None
        )
        show_insurance_tier_prompt = legacy_policy_exists

    return render_template(
        'admin_dashboard.html',
        system_announcements=system_announcements,
        show_recovery_setup=show_recovery_setup,
        # Quick stats
        total_students=total_students,
        total_balance=total_balance,
        avg_balance=avg_balance,
        total_pending_actions=total_pending_actions,
        pending_redemptions_count=pending_redemptions_count,
        pending_hall_passes_count=pending_hall_passes_count,
        pending_insurance_claims_count=pending_insurance_claims_count,
        total_transactions_today=total_transactions_today,
        # Payroll info
        total_payroll_estimate=total_payroll_estimate,
        payroll_updated_at=payroll_updated_at,
        next_payroll_date=next_payroll_date,
        # Limited data for cards
        recent_redemptions=recent_redemptions,
        recent_hall_passes=recent_hall_passes,
        recent_insurance_claims=recent_insurance_claims,
        recent_transactions=recent_transactions,
        recent_logs=recent_logs,
        # Lookup table
        student_lookup=student_lookup,
        show_insurance_tier_prompt=show_insurance_tier_prompt,
        current_page="dashboard"
    )


@admin_bp.route('/bonuses', methods=['POST'])
@admin_required
def give_bonus_all():
    """Give bonus or payroll adjustment to all students."""
    from app.models import _quantize_currency

    title = request.form.get('title')
    amount = _quantize_currency(request.form.get('amount'))
    tx_type = request.form.get('type')

    # Get current admin ID for teacher_id
    current_admin_id = session.get('admin_id')

    class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=current_admin_id).subquery()
    seats = Seat.query.filter(Seat.class_id.in_(sa.select(class_ids_subq)), Seat.role == 'student').all()

    banking_settings = (
        BankingSettings.query
        .filter(BankingSettings.class_id.in_(sa.select(class_ids_subq)))
        .first()
    )
    adjustments = []

    for seat in seats:
        adjustments.append({
            'seat': seat,
            'teacher_id': current_admin_id,
            'amount': amount,
            'type': tx_type,
            'description': title,
            'account_type': 'checking',
        })

    result = execute_admin_adjustments(adjustments=adjustments, banking_settings=banking_settings)
    message = f"Bonus/Payroll posted to {result.applied_count} student(s)!"
    if result.declined_count:
        message += f" {result.declined_count} declined for insufficient funds."
    if result.fee_count:
        message += f" Overdraft fee charged for {result.fee_count}."
    flash(message, "warning" if result.declined_count else "success")
    return redirect(url_for('admin.dashboard'))



# -------------------- AUTHENTICATION --------------------

@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Admin login with TOTP authentication."""
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("user_id", None)
    session.pop("last_activity", None)
    session.pop("force_admin_username_migration", None)
    form = AdminLoginForm()
    if form.validate_on_submit():
        username = normalize_auth_username(form.username.data)
        totp_code = form.totp_code.data.strip()
        user = find_canonical_user_by_auth_username(username, expected_role="teacher")
        if user:
            try:
                decrypted_secret = decrypt_totp(user.totp_secret_encrypted)
            except (TypeError, ValueError):
                current_app.logger.warning("Admin login failed: invalid encrypted TOTP secret for user_id=%s", user.id)
                decrypted_secret = None

            if decrypted_secret:
                try:
                    totp_valid = pyotp.TOTP(decrypted_secret).verify(totp_code, valid_window=1)
                except (TypeError, ValueError):
                    totp_valid = False
                if totp_valid:
                    admin = resolve_admin_shadow_for_user(user)
                    if not admin:
                        current_app.logger.error(
                            "Admin login failed: canonical teacher user_id=%s has no unique legacy route shadow",
                            user.id,
                        )
                        flash("Invalid credentials or TOTP code.", "error")
                        return redirect(url_for("admin.login", next=request.args.get("next")))
                    session["is_admin"] = True
                    session["admin_id"] = admin.id
                    session["user_id"] = user.id
                    session["admin_auth_username"] = username
                    session["last_activity"] = utc_now().isoformat()
                    set_admin_display_name_cache(admin_id=admin.id, display_name=admin.get_display_name())
                    if _admin_requires_username_migration(admin):
                        session["force_admin_username_migration"] = True
                        return redirect(url_for("admin.username_migration"))
                    flash("Admin login successful.")
                    next_url = request.args.get("next")
                    redirect_target = None
                    if next_url:
                        # Normalize backslashes to mitigate browser quirks and parsing issues
                        normalized_next = next_url.replace('\\', '')
                        parsed_next = urlparse(normalized_next)
                        # Only allow relative URLs with no scheme or netloc, and that pass the existing safety check
                        if (not parsed_next.scheme and not parsed_next.netloc and is_safe_url(normalized_next)):
                            redirect_target = normalized_next
                        else:
                            redirect_target = url_for("admin.dashboard")
                    else:
                        redirect_target = url_for("admin.dashboard")
                    return redirect(redirect_target)
        flash("Invalid credentials or TOTP code.", "error")
        return redirect(url_for("admin.login", next=request.args.get("next")))
    return render_template("admin_login.html", form=form)


@admin_bp.route('/username-migration', methods=['GET', 'POST'])
@admin_required
def username_migration():
    """One-time migration screen for legacy plaintext teacher usernames."""
    admin = db.session.get(Admin, session.get("admin_id"))
    if not admin:
        flash("Account not found.", "error")
        return redirect(url_for("admin.login"))

    if not _admin_requires_username_migration(admin):
        session.pop("force_admin_username_migration", None)
        return redirect(url_for("admin.dashboard"))

    legacy_username = session.get("admin_auth_username")
    if not legacy_username:
        flash("Could not determine your current username. Contact support.", "error")
        return redirect(url_for("admin.logout"))

    student_count = admin.get_student_count()
    no_recovery_warning = student_count == 0

    if request.method == "POST":
        action = request.form.get("action", "continue")
        chosen_username = legacy_username

        if action == "update":
            chosen_username = normalize_auth_username(request.form.get("new_username", ""))
            if not chosen_username:
                flash("Please enter a username.", "error")
                return render_template(
                    "admin_username_migration.html",
                    legacy_username=legacy_username,
                    no_recovery_warning=no_recovery_warning,
                    student_count=student_count,
                )
            if _auth_username_exists(chosen_username, exclude_admin_id=admin.id):
                flash("Username already exists. Choose a different username.", "error")
                return render_template(
                    "admin_username_migration.html",
                    legacy_username=legacy_username,
                    no_recovery_warning=no_recovery_warning,
                    student_count=student_count,
                )

        salt, username_hash, username_lookup_hash = _build_admin_auth_fields(
            chosen_username,
            existing_salt=admin.salt,
        )
        admin.salt = salt
        admin.username_hash = username_hash
        admin.username_lookup_hash = username_lookup_hash
        user = find_canonical_user_by_auth_username(legacy_username, expected_role="teacher")
        if user:
            user.username_hash = username_hash
            user.username_lookup_hash = username_lookup_hash
        if not admin.teacher_public_id:
            admin.teacher_public_id = _generate_unique_teacher_public_id()
        if not admin.hall_pass_verify_token:
            admin.hall_pass_verify_token = Admin.generate_verify_token()
        db.session.flush()

        session["admin_auth_username"] = chosen_username
        set_admin_display_name_cache(admin_id=admin.id, display_name=admin.get_display_name())
        session.pop("force_admin_username_migration", None)
        flash("Username migration completed.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin_username_migration.html",
        legacy_username=legacy_username,
        no_recovery_warning=no_recovery_warning,
        student_count=student_count,
    )


@admin_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    TOTP-only admin registration for v2.
    Uses AdminSignupForm for initial signup, AdminTOTPConfirmForm for TOTP confirmation.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Check if this is TOTP confirmation (has totp_code field)
    is_totp_submission = 'totp_code' in request.form

    # Use appropriate form based on submission type
    if is_totp_submission:
        form = AdminTOTPConfirmForm()
    else:
        form = AdminSignupForm()

    # Debug logging
    if request.method == 'POST':
        current_app.logger.info(f"Signup POST request received (TOTP submission: {is_totp_submission})")
        current_app.logger.info(f"   Form data: username={request.form.get('username')}")

    if form.validate_on_submit():
        current_app.logger.info("Form validation passed")

        # Get form data
        if is_totp_submission:
            # TOTP form has all fields as strings
            username = normalize_auth_username(form.username.data)
            totp_code = form.totp_code.data.strip()
        else:
            # Initial signup form
            username = normalize_auth_username(form.username.data)
            totp_code = ""

        # Validate ToS for initial signup
        # Validate ToS for initial signup
        if not is_totp_submission and request.form.get('tos_agreed') != 'true':
            flash("You must agree to the Terms of Service and Privacy Policy.", "error")
            return redirect(url_for('admin.signup'))

        # Step 1: Validate Turnstile for initial signup submit.
        if not is_totp_submission:
            turnstile_token = request.form.get('cf-turnstile-response') or request.form.get('turnstile_token')
            if not verify_turnstile_token(turnstile_token, get_real_ip()):
                msg = "Security verification failed. Please complete Turnstile and try again."
                if is_json:
                    return jsonify(status="error", message=msg), 400
                flash(msg, "error")
                return redirect(url_for('admin.signup'))

        # Step 2: Check username uniqueness
        if _auth_username_exists(username):
            current_app.logger.warning("Admin signup failed: username already exists")
            msg = "Username already exists."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        # Step 3: Generate TOTP secret and show QR code (if not already in session)
        if "admin_totp_secret" not in session or session.get("admin_totp_username") != username:
            totp_secret = pyotp.random_base32()
            session["admin_totp_secret"] = totp_secret
            session["admin_totp_username"] = username
        else:
            totp_secret = session["admin_totp_secret"]
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
        # Step 4: If no TOTP code submitted yet, show QR
        if not totp_code:
            # Generate QR code in-memory
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            # Populate form with data
            totp_form = AdminTOTPConfirmForm()
            totp_form.username.data = username
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 5: Validate entered TOTP code
        current_app.logger.info(f"TOTP code submitted (length: {len(totp_code)})")
        totp = pyotp.TOTP(totp_secret)
        is_valid = totp.verify(totp_code)
        current_app.logger.info(f"TOTP verification result: {is_valid}")
        if not is_valid:
            current_app.logger.warning(f"TOTP verification failed for user")
            msg = "Invalid TOTP code. Please try again."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            # Show QR again for retry
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            # Populate form with data
            totp_form = AdminTOTPConfirmForm()
            totp_form.username.data = username
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 6: Create admin account and mark invite as used
        current_app.logger.info(f"TOTP verified. Creating admin account")
        # v2: no DOB usage in teacher signup.
        salt = get_random_salt()
        signup_seed = int.from_bytes(salt[:2], "big") % 10000
        signup_seed_hash = hash_hmac(str(signup_seed).encode(), salt)

        # Check ToS acknowledgement
        tos_agreed = request.form.get('tos_agreed') == 'true'
        if not tos_agreed:
            # Should have been caught by frontend, but safety check
            current_app.logger.warning("Admin signup: ToS not agreed")
            msg = "You must agree to the Terms of Service and Privacy Policy."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")

            # Show QR again for retry
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')

            # Populate form with data
            totp_form = AdminTOTPConfirmForm()
            totp_form.username.data = username
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                qr_b64=img_b64,
                totp_secret=totp_secret,
                tos_agreed=False
            )

        # Encrypt TOTP secret before storing
        encrypted_totp_secret = encrypt_totp(totp_secret)

        salt, username_hash, username_lookup_hash = _build_admin_auth_fields(username, existing_salt=salt)
        new_admin = Admin(
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            teacher_public_id=_generate_unique_teacher_public_id(),
            totp_secret=encrypted_totp_secret,
            dob_sum_hash=signup_seed_hash,
            salt=salt,
            hall_pass_verify_token=Admin.generate_verify_token(),
            tos_accepted=True,
            tos_accepted_at=utc_now()
        )
        new_user = User(
            user_role=UserRole.TEACHER,
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            totp_secret_encrypted=encrypted_totp_secret,
            has_completed_setup=True,
        )
        # Close any read-only transaction opened during validation before FEAT entry.
        db.session.rollback()

        signup_idempotency_key = f"feat:iden:admin-signup:{username}"
        with FEATContext("FEAT-IDEN-001", idempotency_key=signup_idempotency_key):
            db.session.add_all([new_admin, new_user])
            db.session.flush()
        current_app.logger.info(f"Admin account created successfully")
        # Clear session
        session.pop("admin_totp_secret", None)
        session.pop("admin_totp_username", None)
        msg = "Admin account created successfully! Please log in using your authenticator app."
        if is_json:
            return jsonify(status="success", message=msg)
        flash(msg, "success")
        return redirect(url_for("admin.login"))
    # GET or invalid POST: render signup form with form instance (for CSRF)
    if request.method == 'POST':
        current_app.logger.warning("Form validation failed")
        current_app.logger.warning(f"   Form errors: {form.errors}")
    return render_template(
        "admin_signup.html",
        form=form,
        turnstile_site_key=current_app.config.get("TURNSTILE_SITE_KEY"),
    )


@admin_bp.route('/recover', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def recover():
    """
    Teacher account recovery - Step 1: Roster pair verification.

    Teacher submits one (join_code, student_username) pair per class taught.
    Lookup order (enforced):
      1. Resolve join_code -> ClassEconomy (establishes teacher_id and class scope)
      2. Find student by username_lookup_hash *within* that join_code's roster
    All pairs must resolve to the same teacher and must cover all active join codes.
    No DOB is used.

    Generic errors only — do not reveal which pair failed.
    Rate limited to prevent brute-force enumeration.
    """
    form = AdminRecoveryForm()
    _GENERIC_ERROR = "Unable to verify identity. Please check your entries and try again."

    if request.method == 'POST' and form.validate_on_submit():
        join_codes = request.form.getlist('join_code[]')
        student_usernames = request.form.getlist('student_username[]')

        # Strip and filter empty entries
        pairs = [
            (jc.strip().upper(), un.strip())
            for jc, un in zip(join_codes, student_usernames)
            if jc.strip() and un.strip()
        ]

        if not pairs:
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # ----------------------------------------------------------------
        # Step 1: Establish teacher identity from the first join_code
        # ----------------------------------------------------------------
        first_join_code = pairs[0][0]
        first_class = ClassEconomy.query.filter_by(join_code=first_join_code).first()
        if not first_class:
            current_app.logger.warning(
                f"Admin recovery: initial join_code '{first_join_code}' not found"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        teacher_id = first_class.teacher_id

        # ----------------------------------------------------------------
        # Step 2: Verify submitted join codes exactly match the teacher's active classes
        # ----------------------------------------------------------------
        teacher = db.session.get(Admin, teacher_id)
        if not teacher:
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        teacher_classes = ClassEconomy.query.filter_by(teacher_id=teacher_id).all()
        all_active_join_codes = {c.join_code for c in teacher_classes if c.join_code}
        submitted_join_codes = set(jc for jc, _ in pairs)

        # Must exactly match backend list
        if all_active_join_codes != submitted_join_codes:
            current_app.logger.warning(
                f"Admin recovery: join_code set mismatch for teacher {teacher_id}"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # Reject duplicates (e.g. submitting the same valid class 3 times)
        if len(submitted_join_codes) != len(pairs):
            current_app.logger.warning(
                f"Admin recovery: duplicate join_codes submitted"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # ----------------------------------------------------------------
        # Step 3: Verify each username belongs in the correct join_code
        # ----------------------------------------------------------------
        resolved_students = {}   # join_code -> Student

        # Group Seat student_ids by join_code for quick lookup
        seats_by_jc = {}
        for c in teacher_classes:
            if c.join_code:
                jc_seats = Seat.query.filter(
                    Seat.class_id == c.class_id,
                    Seat.student_id.isnot(None),
                    Seat.claimed_at.isnot(None),
                ).all()
                seats_by_jc[c.join_code] = jc_seats

        for join_code, username in pairs:
            # We already know this join_code belongs to the teacher from the set comparison
            lookup_hash = hash_username_lookup(username)

            # Get all student IDs associated with this specific join_code
            seats_for_jc = seats_by_jc.get(join_code, [])
            student_ids_in_class = [s.student_id for s in seats_for_jc if s.student_id]

            student = (
                Student.query
                .filter(
                    Student.id.in_(student_ids_in_class),
                    Student.username_lookup_hash == lookup_hash,
                )
                .first()
            )

            if not student:
                current_app.logger.warning(
                    f"Admin recovery: username not found in join_code scope"
                )
                flash(_GENERIC_ERROR, "error")
                return render_template("admin_recover.html", form=form)

            resolved_students[join_code] = student

        # ----------------------------------------------------------------
        # Step 4: Check for existing active recovery request
        # ----------------------------------------------------------------
        existing_request = get_active_recovery_request_for_teacher(teacher.id, utc_now())

        if existing_request:
            flash("You already have an active recovery request. Please check back or wait for it to expire.", "info")
            session['recovery_request_id'] = existing_request.id
            return redirect(url_for('admin.recovery_status'))

        # ----------------------------------------------------------------
        # Step 4: Create recovery request (5-day expiration)
        # ----------------------------------------------------------------
        expires_at = utc_now() + timedelta(days=5)
        recovery_request = create_recovery_request_with_students(
            teacher_id=teacher.id,
            student_ids=[student.id for student in resolved_students.values()],
            expires_at=expires_at,
        )

        session['recovery_request_id'] = recovery_request.id
        current_app.logger.info(
            f"Admin recovery: request created for teacher {teacher.id}, expires {expires_at}"
        )

        flash("Recovery request created! Your students have been notified. You have 5 days to complete this process.", "success")
        return redirect(url_for('admin.recovery_status'))

    return render_template("admin_recover.html", form=form)



@admin_bp.route('/recovery-status', methods=['GET'])
def recovery_status():
    """
    Show status of recovery request and collected codes.
    """
    recovery_request_id = session.get('recovery_request_id')
    if not recovery_request_id:
        flash("No active recovery request found.", "error")
        return redirect(url_for('admin.recover'))

    recovery_request = get_recovery_request_by_id(recovery_request_id)
    if not recovery_request:
        flash("Recovery request not found.", "error")
        session.pop('recovery_request_id', None)
        return redirect(url_for('admin.recover'))

    # Check if expired (handle timezone-naive datetimes from SQLite)
    expires_at = ensure_utc(recovery_request.expires_at)
    if expires_at < utc_now():
        flash("Your recovery request has expired. Please start a new recovery.", "error")
        session.pop('recovery_request_id', None)
        return redirect(url_for('admin.recover'))

    # Get verification codes
    codes = list_recovery_codes_for_request(recovery_request.id)
    verified_count = sum(1 for c in codes if c.code_hash is not None)
    total_count = len(codes)

    # Check if all verified
    all_verified = verified_count == total_count and total_count > 0

    return render_template("admin_recovery_status.html",
                         recovery_request=recovery_request,
                         codes=codes,
                         verified_count=verified_count,
                         total_count=total_count,
                         all_verified=all_verified)


@admin_bp.route('/reset-credentials', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def reset_credentials():
    """
    Reset teacher username and TOTP after verifying student recovery codes.
    Security: On ANY failed attempt, ALL codes are invalidated and must be regenerated.
    Rate limited to prevent brute force attempts on recovery codes.
    """
    recovery_request_id = session.get('recovery_request_id')
    if not recovery_request_id:
        flash("No active recovery request found.", "error")
        return redirect(url_for('admin.recover'))

    recovery_request = get_recovery_request_by_id(recovery_request_id)
    if not recovery_request or recovery_request.status != 'pending':
        flash("Invalid or expired recovery request.", "error")
        return redirect(url_for('admin.recover'))

    form = AdminResetCredentialsForm()
    if request.method == 'POST' and form.validate_on_submit():
        # Get recovery codes from dynamic fields
        entered_codes = request.form.getlist('recovery_code')
        entered_codes = [c.strip() for c in entered_codes if c.strip()]
        new_username = form.new_username.data.strip()

        # Get all student recovery codes for this request
        student_codes = list_recovery_codes_for_request(recovery_request.id)

        # Verify all students have generated codes
        if any(sc.code_hash is None for sc in student_codes):
            flash("Not all students have verified yet. Please wait for all students to generate their recovery codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Verify count matches
        if len(entered_codes) != len(student_codes):
            current_app.logger.warning(f"Admin recovery: code count mismatch for request {recovery_request.id} - expected {len(student_codes)}, got {len(entered_codes)}")
            # Invalidate ALL codes
            _invalidate_all_recovery_codes(recovery_request.id)
            flash(f"Wrong number of codes entered. All codes have been invalidated. Your students must generate new codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Verify entered codes match (in any order)
        entered_hashes = set()
        for code in entered_codes:
            # Validate format
            if not code.isdigit() or len(code) != 6:
                current_app.logger.warning(f"Admin recovery: invalid code format for request {recovery_request.id}")
                _invalidate_all_recovery_codes(recovery_request.id)
                flash("Invalid code format detected. All codes have been invalidated. Your students must generate new codes.", "error")
                return redirect(url_for('admin.recovery_status'))
            # Hash the entered code (no salt for recovery codes - they're already random)
            code_hash = hash_hmac(code.encode(), b'')
            entered_hashes.add(code_hash)

        stored_hashes = set(sc.code_hash for sc in student_codes)

        if entered_hashes != stored_hashes:
            current_app.logger.warning(f"Admin recovery: code mismatch for request {recovery_request.id}")
            # Invalidate ALL codes on failed attempt
            _invalidate_all_recovery_codes(recovery_request.id)
            flash("Recovery codes do not match. All codes have been invalidated. Your students must generate new codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Check username uniqueness
        if _auth_username_exists(new_username, exclude_admin_id=recovery_request.teacher_id):
            flash("Username already exists. Please choose a different username.", "error")
            return render_template("admin_reset_credentials.html", form=form, show_qr=False)

        # Generate new TOTP secret
        totp_secret = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=new_username, issuer_name="Classroom Economy Admin")

        # Generate QR code
        img = qrcode.make(totp_uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')

        # Store in session for TOTP verification
        session['reset_totp_secret'] = totp_secret
        session['reset_new_username'] = new_username

        return render_template("admin_reset_credentials.html", form=form, show_qr=True, qr_b64=img_b64, totp_secret=totp_secret, new_username=new_username)

    # Check if resuming from saved progress
    resume_mode = session.get('resume_mode', False)
    saved_codes = recovery_request.partial_codes if resume_mode else []
    saved_username = recovery_request.resume_new_username if resume_mode else ''

    # Clear resume mode flag
    if resume_mode:
        session.pop('resume_mode', None)

    return render_template("admin_reset_credentials.html",
                         form=form,
                         show_qr=False,
                         saved_codes=saved_codes,
                         saved_username=saved_username)


def _invalidate_all_recovery_codes(recovery_request_id: int):
    """
    Invalidate all recovery codes forcing students to regenerate new ones.
    This prevents attackers from testing codes individually.
    """
    invalidated_count = invalidate_recovery_codes(recovery_request_id)
    db.session.flush()  # FEAT-LEGACY-WRAP: commit removed
    current_app.logger.info(
        f"Invalidated {invalidated_count} recovery codes - students must regenerate"
    )


@admin_bp.route('/confirm-reset', methods=['POST'])
@limiter.limit("10 per hour")
def confirm_reset():
    """
    Confirm TOTP code and complete the account reset.
    Rate limited to prevent brute force attacks on TOTP codes.
    """
    recovery_request_id = session.get('recovery_request_id')
    if not recovery_request_id:
        flash("Invalid recovery session.", "error")
        return redirect(url_for('admin.recover'))

    recovery_request = get_recovery_request_by_id(recovery_request_id)
    if not recovery_request:
        flash("Invalid recovery session.", "error")
        return redirect(url_for('admin.recover'))

    teacher = db.session.get(Admin, recovery_request.teacher_id)
    if not teacher:
        flash("Invalid recovery session.", "error")
        return redirect(url_for('admin.recover'))

    totp_code = request.form.get('totp_code', '').strip()
    totp_secret = session.get('reset_totp_secret')
    new_username = session.get('reset_new_username')

    if not totp_code or not totp_secret or not new_username:
        flash("Invalid reset session.", "error")
        return redirect(url_for('admin.reset_credentials'))

    # Verify TOTP code
    totp = pyotp.TOTP(totp_secret)
    if not totp.verify(totp_code):
        flash("Invalid TOTP code. Please try again.", "error")
        return redirect(url_for('admin.reset_credentials'))

    # Update teacher account
    previous_username_lookup_hash = teacher.username_lookup_hash
    user = User.query.filter_by(username_lookup_hash=previous_username_lookup_hash).first()
    if not user:
        flash("Canonical account identity is missing. Contact support.", "error")
        return redirect(url_for('admin.recover'))

    salt, username_hash, username_lookup_hash = _build_admin_auth_fields(new_username, existing_salt=teacher.salt)
    teacher.salt = salt
    teacher.username = None
    teacher.username_hash = username_hash
    teacher.username_lookup_hash = username_lookup_hash
    teacher.totp_secret = encrypt_totp(totp_secret)  # Encrypt before storing
    user.username_hash = username_hash
    user.username_lookup_hash = username_lookup_hash
    user.totp_secret_encrypted = teacher.totp_secret

    # Mark recovery request as completed
    mark_recovery_request_verified(recovery_request.id, utc_now())

    db.session.flush()

    # Clear recovery session
    session.pop('reset_totp_secret', None)
    session.pop('reset_new_username', None)

    flash("Your account has been successfully reset! Please log in with your new username and TOTP.", "success")
    return redirect(url_for('admin.login'))


@admin_bp.route('/save-recovery-progress', methods=['POST'])
@limiter.limit("10 per hour")
def save_recovery_progress():
    """
    Save partial recovery progress and generate a resume PIN.
    Allows teachers to enter codes gradually without needing all students at once.
    """
    recovery_request_id = session.get('recovery_request_id')
    if not recovery_request_id:
        flash("No active recovery request found.", "error")
        return redirect(url_for('admin.recover'))

    recovery_request = get_recovery_request_by_id(recovery_request_id)
    if not recovery_request or recovery_request.status != 'pending':
        flash("Invalid or expired recovery request.", "error")
        return redirect(url_for('admin.recover'))

    # Get entered codes and new username
    entered_codes = request.form.getlist('recovery_code')
    entered_codes = [c.strip() for c in entered_codes if c.strip()]
    new_username = request.form.get('new_username', '').strip()

    if not entered_codes:
        flash("Please enter at least one recovery code before saving progress.", "error")
        return redirect(url_for('admin.reset_credentials'))

    # Generate a 6-digit resume PIN using cryptographically secure randomness
    resume_pin = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

    # Hash the PIN
    resume_pin_hash = hash_hmac(resume_pin.encode(), b'')

    # Save partial progress
    save_recovery_progress(
        recovery_request.id,
        partial_codes=entered_codes,
        resume_pin_hash=resume_pin_hash,
        resume_new_username=new_username,
    )
    db.session.flush()

    current_app.logger.info(f"Admin recovery: saved partial progress for request {recovery_request.id}")

    # Show the PIN to the teacher
    return render_template("admin_recovery_saved.html",
                         resume_pin=resume_pin,
                         codes_saved=len(entered_codes),
                         recovery_request=recovery_request)


@admin_bp.route('/resume-credentials', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def resume_credentials():
    """
    Resume recovery process with a previously saved PIN.
    """
    if request.method == 'GET':
        # Show PIN entry form
        return render_template("admin_resume_credentials.html")

    # POST: Verify PIN and load saved progress
    resume_pin = request.form.get('resume_pin', '').strip()

    if not resume_pin or len(resume_pin) != 6 or not resume_pin.isdigit():
        flash("Please enter a valid 6-digit resume PIN.", "error")
        return render_template("admin_resume_credentials.html")

    # Find recovery request with matching PIN
    resume_pin_hash = hash_hmac(resume_pin.encode(), b'')

    recovery_request = find_recovery_request_by_resume_pin(resume_pin_hash, utc_now())

    if not recovery_request:
        current_app.logger.warning("Admin recovery: invalid resume PIN attempt")
        flash("Invalid or expired resume PIN. Please check your PIN or start a new recovery.", "error")
        return render_template("admin_resume_credentials.html")

    # Set session and redirect to reset credentials with saved progress
    session['recovery_request_id'] = recovery_request.id
    session['resume_mode'] = True

    current_app.logger.info(f"Admin recovery: resumed progress for request {recovery_request.id}")
    flash(f"Progress resumed! You have {len(recovery_request.partial_codes or [])} code(s) already saved.", "info")
    return redirect(url_for('admin.reset_credentials'))


@admin_bp.route('/setup-recovery', methods=['GET', 'POST'])
@admin_required
def setup_recovery():
    """v2: recovery setup no longer collects DOB."""
    if request.method == 'POST':
        flash("Recovery setup is already enabled without date-of-birth requirements.", "success")
        return redirect(url_for('admin.dashboard'))
    return render_template('admin_setup_recovery.html')


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Teacher account settings - configure display name and class labels."""
    admin_id = session.get("admin_id")
    admin = db.get_or_404(Admin, admin_id)

    if request.method == 'POST':
        form_pairs = sorted((key, value) for key, value in request.form.items())
        payload_hash = hashlib.sha256(repr(form_pairs).encode("utf-8")).hexdigest()[:16]
        idempotency_key = f"feat:iden:admin-settings:{admin_id}:{payload_hash}"

        # Ensure FEAT owns transaction boundary for this write path.
        db.session.rollback()
        with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
            admin = db.get_or_404(Admin, admin_id)

            # Update display name
            display_name = request.form.get('display_name', '').strip()
            if display_name:
                admin.display_name = display_name
            else:
                admin.display_name = None  # Use teacher_public_id as fallback

            # Update class labels for each ClassEconomy (canonical class label store)
            teacher_classes = ClassEconomy.query.filter_by(teacher_id=admin_id).all()
            for cls in teacher_classes:
                section_key = cls.section or cls.join_code or ''
                class_label_key = f'class_label_{section_key}'
                class_label = request.form.get(class_label_key, '').strip()
                cls.display_name = class_label if class_label else None

        set_admin_display_name_cache(admin_id=admin.id, display_name=admin.get_display_name())
        flash("Settings updated successfully!", "success")
        return redirect(url_for('admin.settings'))

    # GET: Show settings form
    # Derive blocks from ClassEconomy (canonical class anchor)
    blocks = [
        (cls.section or cls.join_code or '', cls.display_name)
        for cls in ClassEconomy.query.filter_by(teacher_id=admin_id).order_by(ClassEconomy.section.asc()).all()
    ]

    return render_template(
        'admin_settings.html',
        admin=admin,
        blocks=blocks,
        current_page='settings',
        page_title='Account Personalization'
    )


@admin_bp.route('/logout')
def logout():
    """Admin logout."""
    clear_admin_display_name_cache()
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("user_id", None)
    session.pop("admin_auth_username", None)
    session.pop("last_activity", None)
    session.pop("force_admin_username_migration", None)
    session.pop("passkey_auth_username", None)
    flash("Logged out.")
    return redirect(url_for("admin.login"))


# -------------------- Rent privilege helpers --------------------

def _build_rent_privileges_by_block(current_admin, blocks, join_codes_by_block, students_by_block):
    """
    Build a dict {(student_id, block): [privileges]} using batched queries to avoid N+1 issues.
    """
    # Use UTC-aware datetime to match database-stored UTC expiry dates.
    now = utc_now()
    student_rent_privileges = {}

    # 1. Fetch all RentSettings for the teacher and blocks in a single query
    # Filter out "Unassigned" and blocks not in join_codes_by_block
    target_blocks = [b for b in blocks if b != "Unassigned" and b in join_codes_by_block]
    if not target_blocks:
        return student_rent_privileges

    target_join_codes = [join_codes_by_block[b] for b in target_blocks if join_codes_by_block.get(b)]
    target_classes = ClassEconomy.query.filter(ClassEconomy.join_code.in_(target_join_codes)).all()
    class_id_by_join_code = {c.join_code: c.class_id for c in target_classes if c.join_code}
    class_id_by_block = {
        block: class_id_by_join_code.get(join_codes_by_block.get(block))
        for block in target_blocks
        if join_codes_by_block.get(block)
    }
    # Use projected columns only; local dev DB may not have newer RentSettings fields yet.
    rent_settings_rows = (
        db.session.query(
            RentSettings.id,
            RentSettings.class_id,
            RentSettings.is_enabled,
            RentSettings.first_rent_due_date,
            RentSettings.frequency_type,
            RentSettings.custom_frequency_value,
            RentSettings.custom_frequency_unit,
            RentSettings.due_day_of_month,
            RentSettings.grace_period_days,
        )
        .filter(
            RentSettings.class_id.in_([c.class_id for c in target_classes]),
            RentSettings.is_enabled == True
        )
        .all()
    )
    all_rent_settings = [
        SimpleNamespace(
            id=row.id,
            class_id=row.class_id,
            is_enabled=row.is_enabled,
            first_rent_due_date=row.first_rent_due_date,
            frequency_type=row.frequency_type,
            custom_frequency_value=row.custom_frequency_value,
            custom_frequency_unit=row.custom_frequency_unit,
            due_day_of_month=row.due_day_of_month,
            grace_period_days=row.grace_period_days,
        )
        for row in rent_settings_rows
    ]
    settings_by_block = {
        block: next((rs for rs in all_rent_settings if rs.class_id == class_id_by_block.get(block)), None)
        for block in target_blocks
    }

    if not settings_by_block:
        return student_rent_privileges

    # 2. Fetch active policy versions and extract privilege items from frozen manifests.
    #    This ensures mid-cycle teacher edits don't change visible perks until next cycle.
    from app.models import RentPolicyVersion
    from app.services.store_service import get_frozen_privilege_items

    active_version_ids = [
        rs.active_version_id for rs in (
            RentSettings.query
            .filter(RentSettings.class_id.in_([c.class_id for c in target_classes]))
            .with_entities(RentSettings.active_version_id)
            .all()
        )
        if rs.active_version_id
    ]
    active_versions_by_class = {}
    if active_version_ids:
        for v in RentPolicyVersion.query.filter(RentPolicyVersion.id.in_(active_version_ids)).all():
            active_versions_by_class[v.class_id] = v

    frozen_items_by_class_id = {}
    all_store_item_ids = set()
    for class_id_val, version in active_versions_by_class.items():
        frozen_privs = get_frozen_privilege_items(version)
        frozen_items_by_class_id[class_id_val] = frozen_privs
        for fp in frozen_privs:
            if fp.get('store_item_id'):
                all_store_item_ids.add(fp['store_item_id'])

    # 3. Collect all student IDs across all blocks and calculate coverage periods
    all_student_ids = set()
    payment_filters = []
    from app.routes.student import _calculate_rent_coverage_due_date

    for block in target_blocks:
        rent_settings = settings_by_block.get(block)
        if not rent_settings:
            continue

        block_students = students_by_block.get(block, [])
        if not block_students:
            continue

        block_student_ids = [student.id for student in block_students]
        all_student_ids.update(block_student_ids)

        # Calculate current coverage period (pre-paid system)
        # Use the most recently PASSED due date so that payments made for
        # period N are found even after the calendar month rolls over but
        # before the next due date arrives.
        from app.routes.student import _calculate_rent_coverage_due_date
        coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
        if not coverage_due_date:
            continue
        coverage_month = coverage_due_date.month
        coverage_year = coverage_due_date.year

        join_code = join_codes_by_block[block]
        class_id = class_id_by_block.get(block)
        if not class_id:
            continue
        payment_filters.append(and_(
            RentPayment.class_id == class_id,
            RentPayment.coverage_month == coverage_month,
            RentPayment.coverage_year == coverage_year,
        ))

    if not all_student_ids:
        return student_rent_privileges

    # 4. Fetch all relevant RentPayments in a single query each
    paid_student_ids_by_block = defaultdict(set)
    if payment_filters:
        rent_payments = RentPayment.query.filter(
            RentPayment.student_id.in_(list(all_student_ids)),
            or_(*payment_filters)
        ).with_entities(RentPayment.student_id, RentPayment.class_id).all()

        for student_id, class_id in rent_payments:
            for block, block_class_id in class_id_by_block.items():
                if block_class_id == class_id:
                    paid_student_ids_by_block[block].add(student_id)

    # 5. Fetch all relevant StudentItems in a single query each
    items_by_student = defaultdict(set)
    if all_store_item_ids:
        student_items = StudentItem.query.filter(
            StudentItem.student_id.in_(list(all_student_ids)),
            StudentItem.store_item_id.in_(list(all_store_item_ids)),
            StudentItem.status.in_(['purchased', 'redeemed']),
            or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > now
            )
        ).with_entities(StudentItem.student_id, StudentItem.store_item_id).all()

        for student_id, store_item_id in student_items:
            items_by_student[student_id].add(store_item_id)

    # 6. Process the data in memory within the loop
    for block in target_blocks:
        rent_settings = settings_by_block.get(block)
        if not rent_settings:
            continue

        block_class_id = class_id_by_block.get(block)
        per_period_items = frozen_items_by_class_id.get(block_class_id, [])
        if not per_period_items:
            continue

        block_students = students_by_block.get(block, [])
        paid_student_ids = paid_student_ids_by_block.get(block, set())

        for student in block_students:
            privileges = []
            has_paid_rent = student.id in paid_student_ids
            student_store_items = items_by_student.get(student.id, set())

            for frozen_item in per_period_items:
                source = None

                if has_paid_rent:
                    source = 'rent'
                elif frozen_item.get('store_item_id') and frozen_item['store_item_id'] in student_store_items:
                    source = 'purchased'

                if source:
                    privileges.append({
                        'name': frozen_item['name'],
                        'source': source
                    })

            if privileges:
                key = (student.id, block)
                student_rent_privileges[key] = privileges

    return student_rent_privileges


def _get_rent_privileges_for_student(student, class_id, join_code):
    """Return rent privileges for a single student in the current class context.

    Pre-paid system: Check if student has paid rent that COVERS the current period.
    A payment made for January covers the student until the February due date.
    """
    rent_privileges = []
    if not (class_id and join_code):
        return rent_privileges

    class_row_for_block = ClassEconomy.query.filter_by(join_code=join_code).first()
    current_block = class_row_for_block.section if class_row_for_block else None
    if not current_block:
        return rent_privileges

    rent_settings = RentSettings.query.filter_by(class_id=class_id, block=current_block).first()
    if not rent_settings or not rent_settings.is_enabled:
        return rent_privileges

    # Use a timezone-aware UTC datetime to match how expiry dates are stored.
    now = utc_now()

    # Calculate current due date and determine which coverage period we're in.
    # Use the most recently PASSED due date for correct coverage matching.
    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    if not coverage_due_date:
        return rent_privileges
    coverage_month = coverage_due_date.month
    coverage_year = coverage_due_date.year
    seat_ids = get_seat_ids_for_student_join(student.id, join_code)
    rent_scope = RentPayment.seat_id.in_(seat_ids) if seat_ids else sa.false()

    has_paid_rent = RentPayment.query.filter(
        rent_scope,
        RentPayment.class_id == class_id,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
    ).first() is not None

    # Read privilege items from the active policy version's frozen manifest
    # so mid-cycle teacher edits don't change what students see until next cycle.
    from app.services.obligations_service import resolve_active_rent_policy_version
    from app.services.store_service import get_frozen_privilege_items
    active_version = resolve_active_rent_policy_version(class_id)
    if not active_version:
        return rent_privileges

    frozen_privileges = get_frozen_privilege_items(active_version)
    store_item_ids = [item['store_item_id'] for item in frozen_privileges if item.get('store_item_id')]
    items_by_student = set()
    if store_item_ids:
        student_items = StudentItem.query.filter(
            StudentItem.student_id == student.id,
            StudentItem.store_item_id.in_(store_item_ids),
            StudentItem.status.in_(['purchased', 'redeemed']),
            db.or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > now
            )
        ).all()
        items_by_student = {si.store_item_id for si in student_items}

    for frozen_item in frozen_privileges:
        source = None
        if has_paid_rent:
            source = 'rent'
        elif frozen_item.get('store_item_id') and frozen_item['store_item_id'] in items_by_student:
            source = 'purchased'

        if source:
            rent_privileges.append({
                'name': frozen_item['name'],
                'description': frozen_item.get('description'),
                'source': source
            })

    return rent_privileges


# -------------------- STUDENT MANAGEMENT --------------------

@admin_bp.route('/students')
@admin_required
def students():
    """View all students with basic information organized by block."""
    current_admin = session.get('admin_id')
    pending_class_timezone_confirmations = _consume_pending_class_timezone_confirmations(current_admin)

    class_context = g.admin_class_context or {}
    current_class_id = (class_context.get('class_id') or session.get('current_class_id') or '').strip()
    current_join_code = (class_context.get('join_code') or session.get('current_join_code') or '').strip()
    if not current_class_id:
        first_class = (
            ClassEconomy.query.with_entities(ClassEconomy.class_id, ClassEconomy.join_code)
            .filter(ClassEconomy.teacher_id == current_admin)
            .order_by(ClassEconomy.display_name.asc(), ClassEconomy.join_code.asc())
            .first()
        )
        if not first_class:
            flash("Create a class before managing students.", "error")
            return redirect(url_for('admin.dashboard'))
        current_class_id = first_class.class_id
        current_join_code = first_class.join_code
        session['current_class_id'] = current_class_id
        session['current_join_code'] = current_join_code

    # Single-context invariant: timezone prompt on this page must only target current class.
    if current_class_id:
        pending_class_timezone_confirmations = [
            item for item in pending_class_timezone_confirmations
            if item.get("class_id") == current_class_id
        ]
    else:
        pending_class_timezone_confirmations = []

    pending_ids = {item.get("class_id") for item in pending_class_timezone_confirmations if item.get("class_id")}
    if current_class_id and current_class_id not in pending_ids:
        class_row = ClassEconomy.query.filter(
            ClassEconomy.teacher_id == current_admin,
            ClassEconomy.class_id == current_class_id,
            sa.or_(
                ClassEconomy.class_timezone.is_(None),
                ClassEconomy.class_timezone == 'UTC',
            ),
        ).first()
        if class_row:
            pending_class_timezone_confirmations.append(_build_pending_class_timezone_payload(class_row))


    # Strict single-context: only Seat data anchored to the active class_id.
    class_seats = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(
            Seat.class_id == current_class_id,
            IdentityProfile.profile_type != 'teacher_shadow_student',
        )
        .all()
    ) if current_class_id else []

    # Derive unique blocks from the Seat roster.
    blocks = sorted({
        (s.block or '').strip().upper()
        for s in class_seats
        if (s.block or '').strip()
    })

    # Group students by block (students can appear in multiple blocks)
    students_by_block = {}

    # Claimed students are resolved through Seat rows in the active class.
    claimed_student_ids = sorted({
        s.student_id for s in class_seats
        if s.student_id is not None and s.claimed_at is not None
    })
    all_students = _scoped_students().filter(Student.id.in_(claimed_student_ids)).order_by(Student.block, Student.first_name).all() if claimed_student_ids else []

    # Group students by block within this class only.
    for block in blocks:
        block_claimed_ids = {
            s.student_id for s in class_seats
            if (s.block or '').strip().upper() == block
            and s.student_id is not None
            and s.claimed_at is not None
        }
        students_by_block[block] = [s for s in all_students if s.id in block_claimed_ids]

    # Add username_display attribute to each student
    for student in all_students:
        if student.username_hash and student.has_completed_setup:
            student.username_display = f"user_{student.id}"
        else:
            student.username_display = "Not Set"

    # Fetch join codes, class labels, and unclaimed seats for each block.
    # Source of truth: ClassEconomy for join codes/labels, Seat for unclaimed counts.
    join_codes_by_block = {}
    class_labels_by_block = {}
    class_ids_by_block = {}
    unclaimed_seats_by_block = {}
    unclaimed_seats_list_by_block = {}

    if current_class_id:
        class_row = ClassEconomy.query.filter_by(
            teacher_id=current_admin,
            class_id=current_class_id,
        ).first()
        if class_row:
            for block in blocks:
                unclaimed_seats_list_by_block[block] = []
                join_codes_by_block[block] = class_row.join_code
                class_labels_by_block[block] = class_row.display_name or block
                class_ids_by_block[block] = class_row.class_id
                unclaimed_seats_by_block[block] = 0

    # Count unclaimed seats per block (exclude teacher shadow student seats).
    for s in class_seats:
        block_name = (s.block or '').strip().upper()
        if block_name and block_name in unclaimed_seats_list_by_block:
            if s.claimed_at is None and s.student_id is None:
                unclaimed_seats_list_by_block[block_name].append(s)
                unclaimed_seats_by_block[block_name] += 1

    # CRITICAL: Add scoped balances for each student in each block
    # This prevents multi-tenancy violations where students see aggregated balances across all classes
    student_balances_by_block = {}  # {(student_id, block): {'checking': X, 'savings': Y, 'earnings': Z}}

    # 1. Identify all class_ids to query
    target_class_ids = set()
    for block in blocks:
        if block != "Unassigned" and block in class_ids_by_block:
            if class_ids_by_block[block]:
                target_class_ids.add(class_ids_by_block[block])

    # 2. Fetch seats for these classes and get balances by seat
    seats = Seat.query.filter(Seat.class_id.in_(target_class_ids), Seat.role == 'student').all()
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)

    seat_map = {(seat.student_id, seat.class_id): seat for seat in seats}

    # 3. Populate the result dictionary for ALL students to ensure 0-balance entries exist
    for block in blocks:
        if block != "Unassigned" and block in class_ids_by_block:
            class_id = class_ids_by_block[block]
            for student in students_by_block.get(block, []):
                seat = seat_map.get((student.id, class_id))
                bals = raw_balances.get((str(class_id), seat.id)) if seat else None
                if not bals:
                    bals = {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}

                final_key = (student.id, block)
                student_balances_by_block[final_key] = {
                    'checking': float(Decimal(bals['checking_cents']) / 100),
                    'savings': float(Decimal(bals['savings_cents']) / 100),
                    'earnings': float(bals.get('earnings', Decimal('0.00')))
                }

    # Calculate rent privileges for each student in each block (batched)
    from app.models import RentItem, RentSettings, RentPayment, StudentItem
    student_rent_privileges = _build_rent_privileges_by_block(current_admin, blocks, join_codes_by_block, students_by_block)

    # Canonical class context (single page scope).
    if blocks and current_join_code:
        for block in blocks:
            join_codes_by_block[block] = current_join_code

    return render_template('admin_students.html',
                         students=all_students,
                         blocks=blocks,
                         students_by_block=students_by_block,
                         join_codes_by_block=join_codes_by_block,
                         class_labels_by_block=class_labels_by_block,
                         unclaimed_seats_by_block=unclaimed_seats_by_block,
                         unclaimed_seats_list_by_block=unclaimed_seats_list_by_block,
                         student_balances_by_block=student_balances_by_block,
                         student_rent_privileges=student_rent_privileges,
                         timezone_choices=pytz.common_timezones,
                         pending_class_timezone_confirmations=pending_class_timezone_confirmations,
                         single_context_mode=True,
                         current_page="students")


@admin_bp.route('/current-class', methods=['POST'])
@admin_required
def set_current_class():
    """Set the current class using class_id as the backend session reference."""
    data = request.get_json(silent=True) or {}
    class_id = (data.get('class_id') or '').strip()
    join_code = (data.get('join_code') or '').strip().upper()
    if not class_id and not join_code:
        return jsonify({'status': 'error', 'message': 'Class ID required'}), 400

    admin_id = session.get('admin_id')
    query = ClassEconomy.query.with_entities(ClassEconomy.class_id, ClassEconomy.join_code).filter(
        ClassEconomy.teacher_id == admin_id,
    )
    if class_id:
        query = query.filter(ClassEconomy.class_id == class_id)
    else:
        query = query.filter(ClassEconomy.join_code == join_code)
    class_row = query.first()
    if class_row is None:
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    session['current_class_id'] = class_row.class_id
    session['current_join_code'] = class_row.join_code
    return jsonify({'status': 'success'}), 200


@admin_bp.route('/classes/<class_id>/timezone', methods=['POST'])
@admin_required
def set_class_timezone(class_id: str):
    """Set the immutable timezone for a newly created class."""
    data = request.get_json(silent=True) or {}
    timezone_name = (data.get('timezone') or '').strip()
    if not timezone_name:
        return jsonify({'status': 'error', 'message': 'Timezone is required.'}), 400
    if timezone_name not in pytz.all_timezones_set:
        return jsonify({'status': 'error', 'message': 'Invalid timezone.'}), 400

    admin_id = session.get('admin_id')
    current_class_id = (session.get('current_class_id') or '').strip()
    if current_class_id and class_id != current_class_id:
        return jsonify({
            'status': 'error',
            'message': 'Class scope mismatch. Switch class from the navigation to continue.',
        }), 403

    class_row = ClassEconomy.query.filter_by(class_id=class_id, teacher_id=admin_id).first()
    if class_row is None:
        return jsonify({'status': 'error', 'message': 'Class not found.'}), 404

    timezone_needs_confirmation = _class_timezone_needs_confirmation(class_row)
    if not timezone_needs_confirmation:
        if class_row.class_timezone == timezone_name:
            _remove_pending_class_timezone_confirmation(class_id)
            return jsonify({
                'status': 'success',
                'message': 'Class timezone already set.',
                'class_timezone': class_row.class_timezone,
            }), 200
        return jsonify({
            'status': 'error',
            'message': 'Class timezone is already locked and cannot be changed.',
        }), 409

    try:
        idempotency_key = f"feat:iden:set-class-timezone:{admin_id}:{class_id}:{timezone_name}"
        # Route reads above may open an implicit transaction; clear it so FEAT owns the boundary.
        db.session.rollback()
        with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
            # Persist an explicit confirmed UTC value distinct from default placeholder UTC.
            class_row.class_timezone = 'Etc/UTC' if timezone_name == 'UTC' else timezone_name
            db.session.flush()
    except Exception:
        current_app.logger.error(
            "Failed to set class timezone for class_id=%s", class_id, exc_info=True
        )
        return jsonify({'status': 'error', 'message': 'Could not save class timezone.'}), 500

    _remove_pending_class_timezone_confirmation(class_id)
    return jsonify({
        'status': 'success',
        'message': 'Class timezone saved.',
        'class_timezone': class_row.class_timezone,
        'class_identifier': class_row.display_name or class_row.join_code,
    }), 200


@admin_bp.route('/students/<int:student_id>')
@admin_required
def student_detail(student_id):
    """Legacy numeric student-detail URL is intentionally disabled in V2."""
    abort(404)


@admin_bp.route('/students/<string:student_public_id>')
@admin_required
def student_detail_public(student_public_id):
    """View detailed information for a specific student via public-id URL."""
    teacher_id = session.get('admin_id')
    current_class_id = str(session.get('current_class_id') or "")
    nav_payload = _read_student_detail_nav_token(request.args.get('nav', ''))
    if not nav_payload:
        abort(404)

    expected_admin_id = int(nav_payload.get("admin_id") or 0)
    if expected_admin_id and expected_admin_id != int(teacher_id or 0):
        abort(404)
    expected_public_id = str(nav_payload.get("seat_public_id") or "")
    expected_student_id = int(nav_payload.get("student_id") or 0)
    expected_class_id = str(nav_payload.get("class_id") or "")
    if expected_public_id != student_public_id:
        abort(404)

    scoped_seat = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.public_id == student_public_id,
            Seat.role == "student",
            ClassEconomy.teacher_id == teacher_id,
        )
        .first()
    )
    if not scoped_seat or not scoped_seat.student_id:
        abort(404)
    if expected_student_id and scoped_seat.student_id != expected_student_id:
        abort(404)
    if expected_class_id and str(scoped_seat.class_id or "") != expected_class_id:
        abort(404)

    student = _get_student_or_404(scoped_seat.student_id)
    join_code = scoped_seat.join_code
    class_id = scoped_seat.class_id
    seat_id = scoped_seat.id
    if join_code:
        session['current_join_code'] = join_code
    if class_id:
        session['current_class_id'] = class_id

    tx_scope = sa.and_(Transaction.seat_id == seat_id, Transaction.class_id == class_id)
    tap_scope = sa.and_(TapEvent.seat_id == seat_id, TapEvent.class_id == class_id)

    # Remove deprecated last_tap_in/last_tap_out logic; rely on TapEvent backend.
    # Fetch last rent payment
    rent_query = Transaction.query.filter(tx_scope, Transaction.type == "rent")
    if join_code:
        rent_query = rent_query.filter(Transaction.join_code == join_code)
    latest_rent = rent_query.order_by(Transaction.timestamp.desc()).first()
    student.rent_last_paid = latest_rent.timestamp if latest_rent else None

    # Fetch last property tax payment
    tax_query = Transaction.query.filter(tx_scope, Transaction.type == "property_tax")
    if join_code:
        tax_query = tax_query.filter(Transaction.join_code == join_code)
    latest_tax = tax_query.order_by(Transaction.timestamp.desc()).first()
    student.property_tax_last_paid = latest_tax.timestamp if latest_tax else None

    # Compute due dates and overdue status
    from datetime import date
    effective_tz = get_timezone()
    today = utc_now().astimezone(effective_tz).date()
    # Rent due on 5th, overdue after 6th
    rent_due = date(today.year, today.month, 5)
    student.rent_due_date = rent_due
    student.rent_overdue = today > rent_due and (
        not student.rent_last_paid or student.rent_last_paid.astimezone(effective_tz).date() <= rent_due
    )

    # Property tax due on 5th, overdue after 6th
    tax_due = date(today.year, today.month, 5)
    student.property_tax_due_date = tax_due
    student.property_tax_overdue = today > tax_due and (
        not student.property_tax_last_paid or student.property_tax_last_paid.astimezone(effective_tz).date() <= tax_due
    )

    transactions_query = Transaction.query.filter(tx_scope)
    student_items_query = student.items
    latest_tap_event_query = TapEvent.query.filter(tap_scope)
    if join_code:
        transactions_query = transactions_query.filter(Transaction.join_code == join_code)
        student_items_query = student_items_query.filter(StudentItem.join_code == join_code)
        latest_tap_event_query = latest_tap_event_query.filter(TapEvent.join_code == join_code)

    transactions = transactions_query.order_by(Transaction.timestamp.desc()).all()
    student_items = student_items_query.order_by(StudentItem.purchase_date.desc()).all()
    # Fetch most recent TapEvent for this student
    latest_tap_event = latest_tap_event_query.order_by(TapEvent.timestamp.desc()).first()

    class_row = ClassEconomy.query.filter_by(join_code=join_code).first() if join_code else None
    class_id = class_row.class_id if class_row else class_id
    scoped_seat = Seat.query.filter_by(student_id=student.id, class_id=class_id).first() if class_id else None

    # Get student's active insurance policy scoped to current class.
    active_insurance = student.get_active_insurance(class_id=class_id, teacher_id=teacher_id)

    # Get all blocks for the edit modal
    all_students = _scoped_students().all()
    blocks = sorted({b.strip() for s in all_students for b in (s.block or "").split(',') if b.strip()})

    # Get StudentBlock settings for this student
    from app.models import StudentBlock
    student_blocks_settings = {}
    student_periods = [b.strip().upper() for b in (student.block or "").split(',') if b.strip()]
    for period in student_periods:
        if join_code:
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=period,
                join_code=join_code,
            ).first()
        else:
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=period
            ).first()
        student_blocks_settings[period] = {
            'tap_enabled': student_block.tap_enabled if student_block else True,
            'done_for_day_date': student_block.done_for_day_date if student_block else None
        }

    # CRITICAL: Get scoped balances for current class_id + seat_id only.
    scoped_checking_balance = 0
    scoped_savings_balance = 0
    scoped_total_earnings = 0

    if class_id and scoped_seat:
        scoped_checking_balance = student.get_checking_balance(class_id=class_id, seat_id=scoped_seat.id)
        scoped_savings_balance = student.get_savings_balance(class_id=class_id, seat_id=scoped_seat.id)
        scoped_total_earnings = student.get_total_earnings(join_code=join_code)
    else:
        current_app.logger.warning(
            "Missing canonical class/seat scope for student_detail student=%s join_code=%s.",
            student.id,
            join_code,
        )

    # Get active rent privileges (per-period items)
    rent_privileges = _get_rent_privileges_for_student(student, class_row.class_id if class_row else None, join_code)

    # CRITICAL: Fetch Join Codes for student's blocks (for Account Recovery display)
    join_codes = {}
    if student.block:
        block_parts = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        if block_parts:
            class_rows = ClassEconomy.query.filter(
                ClassEconomy.teacher_id == teacher_id,
                ClassEconomy.section.in_(block_parts)
            ).all()
            for class_row in class_rows:
                if class_row.join_code and class_row.section:
                    join_codes[class_row.section] = class_row.join_code

    reset_code_is_active = bool(
        student.reset_code
        and student.reset_code_expires_at
        and ensure_utc(student.reset_code_expires_at) >= utc_now()
        and student.recovery_status == 'to_be_claimed'
    )

    return render_template('student_detail.html',
                         student=student,
                         reset_code_is_active=reset_code_is_active,
                         join_codes=join_codes,
                         transactions=transactions,
                         student_items=student_items,
                         latest_tap_event=latest_tap_event,
                         active_insurance=active_insurance,
                         blocks=blocks,
                         student_blocks_settings=student_blocks_settings,
                         scoped_checking_balance=scoped_checking_balance,
                         scoped_savings_balance=scoped_savings_balance,
                         scoped_total_earnings=scoped_total_earnings,
                         current_join_code=join_code,
                         rent_privileges=rent_privileges)


@admin_bp.route('/student/<int:student_id>/set-hall-passes', methods=['POST'])
@admin_required
def set_hall_passes(student_id):
    """Set hall pass balance for a student."""
    student = _get_student_or_404(student_id)
    new_balance = request.form.get('hall_passes', type=int)

    if new_balance is not None and new_balance >= 0:
        student.hall_passes = new_balance
        db.session.flush()
        flash(f"Successfully updated {student.full_name}'s hall pass balance to {new_balance}.", "success")
    else:
        flash("Invalid hall pass balance provided.", "error")

    return _redirect_to_student_detail(student_id)


@admin_bp.route('/student/edit', methods=['POST'])
@admin_required
def edit_student():
    """Edit student basic information."""
    student_id = request.form.get('student_id', type=int)
    current_admin_id = session.get('admin_id')

    # Try to get student from scoped query first
    student = get_student_for_admin(student_id)

    if not student:
        # Not accessible by this admin
        abort(404)

    # Get form data
    new_first_name = request.form.get('first_name', '').strip()
    last_name_input = request.form.get('last_name', '').strip()
    new_last_initial = last_name_input[0].upper() if last_name_input else student.last_initial

    # Get selected blocks (multiple checkboxes)
    selected_blocks = request.form.getlist('blocks')

    # Guard: Teacher students cannot move between classes
    if student.is_teacher:
        # Ignore form input for blocks, preserve existing blocks
        # This enforces "cannot be moved between classes"
        current_blocks = [b.strip().upper() for b in (student.block or '').split(',') if b.strip()]
        new_blocks = ','.join(sorted(current_blocks))

        # Check if user tried to change blocks
        form_blocks_set = set(b.strip().upper() for b in selected_blocks)
        current_blocks_set = set(current_blocks)

        if form_blocks_set != current_blocks_set:
            flash("Teacher student accounts cannot be moved between classes manually.", "warning")

    # Join blocks with commas (e.g., "A,B,C")
    # At least one block is required for tap/hall pass functionality to work
    elif selected_blocks:
        new_blocks = ','.join(sorted(b.strip().upper() for b in selected_blocks))
    else:
        # No blocks selected - this would break tap/hall pass functionality
        flash("At least one block must be selected.", "error")
        return _redirect_to_student_detail(student_id)

    # Track old blocks for Seat updates
    old_blocks = set(b.strip().upper() for b in (student.block or '').split(',') if b.strip())
    new_blocks_set = set(b.strip().upper() for b in new_blocks.split(',') if b.strip())

    # Determine which blocks are being removed/added
    print(f"DEBUG_TRANSFER: old_blocks={old_blocks} new_blocks_set={new_blocks_set}")

    removed_blocks = old_blocks - new_blocks_set
    added_blocks = new_blocks_set - old_blocks

    # Handle per-period balance transfers
    transferred_blocks = []
    if added_blocks:
        # Get join codes for old blocks (source of transfers)
        old_join_codes = []
        for block in removed_blocks:
            ce = ClassEconomy.query.filter_by(
                teacher_id=current_admin_id,
                section=block
            ).first()
            if ce and ce.join_code:
                old_join_codes.append(ce.join_code)

        # For each added block, check if teacher wants to transfer balance
        for block in added_blocks:
            # Get the balance action for this specific period
            balance_action_key = f'balance_action_{block}'
            balance_action = request.form.get(balance_action_key, 'start_fresh')

            if balance_action == 'transfer' and old_join_codes:
                # Get join code for this new block
                ce = ClassEconomy.query.filter_by(
                    teacher_id=current_admin_id,
                    section=block
                ).first()

                if ce and ce.join_code:
                    target_join_code = ce.join_code
                    target_seat_id = (
                        Seat.query
                        .with_entities(Seat.id)
                        .filter(
                            Seat.student_id == student.id,
                            Seat.join_code == target_join_code,
                        )
                        .scalar()
                    )

                    # Transfer transactions from old blocks to this new block
                    for old_join_code in old_join_codes:
                        old_seat_id = (
                            Seat.query.with_entities(Seat.id)
                            .filter(Seat.student_id == student.id, Seat.join_code == old_join_code)
                            .scalar()
                        )
                        if not old_seat_id:
                            continue

                        update_values = {
                            'join_code': target_join_code,
                            'class_id': ce.class_id,
                            # Ensure seat scope tracks the transferred join_code.
                            # If target seat is missing, clear legacy seat link to avoid stale cross-scope seat_id.
                            'seat_id': target_seat_id,
                        }
                        update_res = Transaction.query.filter_by(
                            seat_id=old_seat_id,
                            join_code=old_join_code
                        ).update(update_values, synchronize_session=False)

                    transferred_blocks.append(block)
                    current_app.logger.info(
                        f"Transferred transactions for student {student.id} from {old_join_codes} to {target_join_code} (block: {block})"
                    )
            # If 'start_fresh', do nothing - student starts with $0 in that period

    # Check if name changed (keep seat identity fields in sync).
    name_changed = (new_first_name != student.first_name or new_last_initial != student.last_initial)

    # Update basic fields
    student.first_name = new_first_name
    student.last_initial = new_last_initial
    student.block = new_blocks

    # Handle account reset — generate recovery code per recovery spec
    reset_login = request.form.get('reset_login') == 'on'
    if reset_login:
        import secrets as _secrets
        code = _secrets.token_hex(4).upper()  # 8-char mixed alphanumeric
        student.reset_code = code
        student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        student.recovery_status = 'to_be_claimed'

        current_app.logger.info(
            f"Reset code generated for student {student.id} by admin {current_admin_id}"
        )

        flash(f"Reset code generated for {student.full_name}: {code} — Expires in 10 minutes. "
              f"Give this code to the student along with their join code.", "warning")

    if name_changed:
        # Sync name onto IdentityProfile rows linked to Seats for this student in this teacher's classes.
        class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=current_admin_id).subquery()
        seats_to_update = (
            Seat.query
            .filter(
                Seat.student_id == student.id,
                Seat.class_id.in_(sa.select(class_ids_subq)),
            )
            .all()
        )
        for seat in seats_to_update:
            if seat.identity_profile:
                seat.identity_profile.first_name = student.first_name
                seat.identity_profile.last_initial = student.last_initial

    # Handle block changes - update Seat entries
    print(f"DEBUG_TRANSFER: old_blocks={old_blocks} new_blocks_set={new_blocks_set}")

    removed_blocks = old_blocks - new_blocks_set
    added_blocks = new_blocks_set - old_blocks

    # Check if this student already has Seat entries in any of this teacher's classes.
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=current_admin_id).subquery()
    existing_seat_count = (
        Seat.query
        .filter(
            Seat.student_id == student.id,
            Seat.class_id.in_(sa.select(class_ids_subq)),
        )
        .count()
    )

    if existing_seat_count == 0:
        # Legacy student — ensure Seat entries for ALL blocks
        blocks_to_ensure = new_blocks_set
    else:
        # Normal case — only create Seat entries for newly added blocks
        blocks_to_ensure = added_blocks

    # Remove Seat entries for blocks the student is no longer in
    for block in removed_blocks:
        ce_row = ClassEconomy.query.filter_by(teacher_id=current_admin_id, section=block).first()
        if ce_row:
            Seat.query.filter_by(
                student_id=student.id,
                class_id=ce_row.class_id,
            ).delete()

    # Create Seat entries for blocks that need them (reusing existing join codes)
    for block in blocks_to_ensure:
        # Resolve class economy for this block
        ce_row = ClassEconomy.query.filter_by(teacher_id=current_admin_id, section=block).first()
        if ce_row:
            join_code = ce_row.join_code
            class_id = ce_row.class_id
        else:
            # Generate a unique join code with bounded retries and fallback
            join_code = None
            for _ in range(MAX_JOIN_CODE_RETRIES):
                candidate = generate_join_code()
                if not ClassEconomy.query.filter_by(join_code=candidate).first():
                    join_code = candidate
                    break
            else:
                # Fallback to timestamp-based code
                block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                join_code = f"B{block_initial}{timestamp_suffix:04d}"

            # Ensure the teacher student seat exists for this new join code
            if join_code:
                _ensure_teacher_student_seat(current_admin_id, join_code, block)
            class_id = _ensure_join_code_anchors(current_admin_id, join_code, class_label=block)

        # Check if a Seat already exists for this student in this class
        existing_seat = Seat.query.filter_by(
            student_id=student.id,
            class_id=class_id,
        ).first()

        if not existing_seat:
            is_claimed = bool(student.username_hash)
            new_seat = Seat(
                student_id=student.id,
                class_id=class_id,
                join_code=join_code,
                block=block,
                claimed_at=utc_now() if is_claimed else None,
            )
            db.session.add(new_seat)

    try:
        db.session.flush()

        # Build flash message with balance transfer info
        message = f"Successfully updated {student.full_name}'s information."
        if transferred_blocks:
            blocks_str = ', '.join(transferred_blocks)
            message += f" Balance transferred to: {blocks_str}."
        elif added_blocks and not transferred_blocks:
            message += " Student will start fresh in new period(s)."

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"FAILED TO EDIT STUDENT EXCEPTION: {e}")
        current_app.logger.error(f"Error updating student {student_id}", exc_info=True)
        flash("Error updating student due to internal error", "error")

    if reset_login:
        return _redirect_to_student_detail(student.id)

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/archive', methods=['GET', 'POST'])
@admin_bp.route('/student/delete', methods=['GET', 'POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_student():
    """Remove a student from this teacher and delete fully if no links remain."""
    current_app.logger.info(f"Delete student route accessed. Method: {request.method}, Form data: {dict(request.form)}")

    # If GET request, show error and redirect (for debugging)
    if request.method == 'GET':
        flash("Delete student must be accessed via POST request.", "error")
        return redirect(url_for('admin.students'))

    student_id = request.form.get('student_id', type=int)
    confirmation = request.form.get('confirmation', '').strip()

    if not student_id:
        current_app.logger.error("No student_id provided in delete request")
        flash("Error: No student ID provided.", "error")
        return redirect(url_for('admin.students'))

    if confirmation != 'DELETE':
        current_app.logger.info(f"Delete cancelled: confirmation '{confirmation}' != 'DELETE'")
        flash("Delete cancelled: confirmation text did not match.", "warning")
        return redirect(url_for('admin.students'))

    student = _get_student_or_404(student_id)
    student_name = student.full_name

    # Prevent deletion of teacher student accounts
    if student.is_teacher:
        flash("Teacher student accounts cannot be deleted directly. They are removed only when the class is deleted.", "error")
        return redirect(url_for('admin.students'))

    try:
        was_hard_deleted = _remove_student_from_teacher_scope(student, session.get('admin_id'))
        if was_hard_deleted:
            flash(f"Deleted {student_name}.", "success")
        else:
            flash(f"Removed {student_name} from this class. Student still exists in other linked classes.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting student {student_name}", exc_info=True)
        flash("Cannot delete student due to internal error", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/bulk-delete', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def bulk_delete_students():
    """Remove multiple students from this teacher and delete true orphans."""
    data = request.get_json(silent=True) or {}
    student_ids = data.get('student_ids', [])

    if not student_ids:
        return jsonify({"status": "error", "message": "No students selected."}), 400

    gate_error = _validate_destruction_gate(data, expected_phrase="DELETE STUDENTS")
    if gate_error:
        return gate_error

    try:
        removed_count = 0
        deleted_count = 0
        for student_id in student_ids:
            student = _get_student_or_404(student_id)
            if student and not student.is_teacher:
                was_hard_deleted = _remove_student_from_teacher_scope(student, session.get('admin_id'))
                removed_count += 1
                if was_hard_deleted:
                    deleted_count += 1

        return jsonify({
            "status": "success",
            "message": (
                f"Successfully removed {removed_count} student(s) from this class. "
                f"{deleted_count} student(s) were fully deleted."
            )
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting students: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while deleting students. Please try again."}), 500


@admin_bp.route('/students/delete-block', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_block():
    """Backwards-compatible block deletion wrapper that resolves to join-code deletion."""
    data = request.get_json(silent=True) or {}
    block = data.get('block', '').strip().upper()
    current_admin_id = session.get('admin_id')

    if not block:
        return jsonify({"status": "error", "message": "No block specified."}), 400

    gate_error = _validate_destruction_gate(data, expected_phrase=f"DELETE BLOCK {block}")
    if gate_error:
        return gate_error

    try:
        join_codes = [
            code for (code,) in db.session.query(ClassEconomy.join_code).filter(
                ClassEconomy.teacher_id == current_admin_id,
                ClassEconomy.section == block,
                ClassEconomy.join_code.isnot(None),
            ).distinct().all()
        ]
        if not join_codes:
            return jsonify({"status": "success", "message": f"No join code found for Block {block}. Nothing to delete."})
        if len(join_codes) > 1:
            return jsonify({
                "status": "error",
                "message": f"Block {block} has multiple join codes. Delete by join code explicitly."
            }), 400

        join_code = join_codes[0]
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if not class_row:
            return jsonify({"status": "error", "message": "Join code not found or access denied."}), 404
        _hard_delete_class_scope(class_row.class_id, current_admin_id)

        # Cleanup any residual unclaimed seats in same block for this join code owner.
        # Find the class_id(s) for this block, then delete unclaimed Seats.
        block_class_ids = [
            cid for (cid,) in db.session.query(ClassEconomy.class_id).filter(
                ClassEconomy.teacher_id == current_admin_id,
                ClassEconomy.section == block,
            ).all()
        ]
        if block_class_ids:
            Seat.query.filter(
                Seat.class_id.in_(block_class_ids),
                Seat.student_id.is_(None),
                Seat.claimed_at.is_(None),
            ).delete(synchronize_session=False)
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted class Block {block} (join code {join_code}) and scoped records."
        })
    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting block {block}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while deleting the block. Please try again."}), 500


@admin_bp.route('/join-code/delete', methods=['POST'])
@admin_bp.route('/join-code', methods=['DELETE'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_join_code():
    """Hard-delete a class economy and all records scoped to the join code."""
    data = request.get_json(silent=True) or request.form
    join_code = (data.get('join_code') or '').strip().upper()
    current_admin_id = session.get('admin_id')

    if not join_code:
        return jsonify({"status": "error", "message": "join_code is required."}), 400

    if not _admin_owns_join_code(current_admin_id, join_code):
        return jsonify({"status": "error", "message": "Join code not found or access denied."}), 403

    legacy_confirm_join_code = str((data or {}).get("confirm_join_code", "")).strip().upper()
    if legacy_confirm_join_code:
        if legacy_confirm_join_code != join_code:
            return jsonify({
                "status": "error",
                "message": "Confirmation failed: join code did not match."
            }), 400
    else:
        gate_error = _validate_destruction_gate(data, expected_phrase=f"DELETE JOIN CODE {join_code}")
        if gate_error:
            return gate_error

    try:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if not class_row:
            return jsonify({"status": "error", "message": "Join code not found or access denied."}), 404
        _hard_delete_class_scope(class_row.class_id, current_admin_id)
        return jsonify({
            "status": "success",
            "message": f"Join code {join_code} and all scoped records were permanently deleted."
        })
    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting join code {join_code}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while deleting the join code. Please try again."}), 500


@admin_bp.route('/pending-students/delete', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_pending_student():
    """
    Delete a single pending student (unclaimed Seat entry).

    Pending students are roster entries that have not yet been claimed by students.
    This route ensures comprehensive cleanup with no leftover traces.
    """
    data = request.get_json()
    teacher_block_id = data.get('teacher_block_id')
    if teacher_block_id:
        try:
            teacher_block_id = int(teacher_block_id)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid seat ID."}), 400

    current_admin_id = session.get('admin_id')

    if not teacher_block_id:
        return jsonify({"status": "error", "message": "No seat ID provided."}), 400

    try:
        # Find the Seat entry (joining to ClassEconomy to verify teacher ownership)
        seat_entry = (
            Seat.query
            .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
            .filter(
                Seat.id == teacher_block_id,
                ClassEconomy.teacher_id == current_admin_id,
            )
            .first()
        )

        if not seat_entry:
            return jsonify({"status": "error", "message": "Pending student not found or access denied."}), 404

        # Verify it's actually unclaimed
        if seat_entry.claimed_at is not None or seat_entry.student_id is not None:
            return jsonify({
                "status": "error",
                "message": "This seat has already been claimed. Use the regular student deletion route instead."
            }), 400

        student_name = f"{seat_entry.display_first_name or 'Unknown'} {seat_entry.display_last_initial or ''}."

        # Delete the Seat entry (this is the only record for unclaimed seats)
        db.session.delete(seat_entry)
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted pending student {student_name}."
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting pending student: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while deleting the pending student. Please try again."}), 500


@admin_bp.route('/pending-students/bulk-delete', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def bulk_delete_pending_students():
    """
    Delete multiple pending students (unclaimed Seat entries) at once.

    This route ensures comprehensive cleanup with no leftover traces.
    Accepts a list of Seat IDs or a block name to delete all pending students in that block.
    """
    data = request.get_json()
    teacher_block_ids = data.get('teacher_block_ids', [])
    block = data.get('block', '').strip().upper()
    current_admin_id = session.get('admin_id')

    if not teacher_block_ids and not block:
        return jsonify({
            "status": "error",
            "message": "Either teacher_block_ids or block must be provided."
        }), 400

    try:
        deleted_count = 0

        if block:
            # Delete all unclaimed Seat entries for this teacher and block
            block_class_ids = [
                cid for (cid,) in db.session.query(ClassEconomy.class_id).filter(
                    ClassEconomy.teacher_id == current_admin_id,
                    ClassEconomy.section == block,
                ).all()
            ]
            if block_class_ids:
                deleted_count = Seat.query.filter(
                    Seat.class_id.in_(block_class_ids),
                    Seat.claimed_at.is_(None),
                    Seat.student_id.is_(None),
                ).delete(synchronize_session=False)
        else:
            # Delete specific Seat entries
            for tb_id in teacher_block_ids:
                seat_entry = (
                    Seat.query
                    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                    .filter(
                        Seat.id == tb_id,
                        ClassEconomy.teacher_id == current_admin_id,
                    )
                    .first()
                )

                if seat_entry:
                    # Verify it's actually unclaimed
                    if seat_entry.claimed_at is None and seat_entry.student_id is None:
                        db.session.delete(seat_entry)
                        deleted_count += 1

        message = f"Successfully deleted {deleted_count} pending student(s)."
        if block:
            message = f"Successfully deleted {deleted_count} pending student(s) from Block {block}."

        return jsonify({
            "status": "success",
            "message": message,
            "deleted_count": deleted_count
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error bulk deleting pending students: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while bulk deleting pending students. Please try again."}), 500


@admin_bp.route('/legacy-unclaimed-students/bulk-delete', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def bulk_delete_legacy_unclaimed_students():
    """
    Delete multiple legacy unclaimed students (Student records without username_hash) at once.

    Legacy unclaimed students are Student records that exist but don't have a username_hash set yet.
    This route removes students from this teacher and hard-deletes true orphans.
    Accepts a block name to delete all legacy unclaimed students in that block.
    """
    data = request.get_json()
    block = data.get('block', '').strip().upper()
    current_admin_id = session.get('admin_id')

    if not block:
        return jsonify({
            "status": "error",
            "message": "Block must be provided."
        }), 400

    try:
        # Query for legacy unclaimed students in this block for this teacher
        students = _scoped_students().filter(
            Student.block == block,
            Student.username_hash.is_(None)
        ).all()

        removed_count = 0
        deleted_count = 0
        for student in students:
            was_hard_deleted = _remove_student_from_teacher_scope(student, current_admin_id)
            removed_count += 1
            if was_hard_deleted:
                deleted_count += 1

        message = (
            f"Successfully removed {removed_count} legacy unclaimed student(s) from Block {block}. "
            f"{deleted_count} student(s) were fully deleted."
        )

        return jsonify({
            "status": "success",
            "message": message,
            "deleted_count": deleted_count
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting legacy unclaimed students: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred while bulk deleting legacy students. Please try again."}), 500


@admin_bp.route('/student/add-individual', methods=['POST'])
@admin_required
def add_individual_student():
    """Add a single student (same as bulk upload but for one student)."""
    try:
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        block = request.form.get('block', '').strip().upper()
        additional_notes = (request.form.get('additional_notes') or '').strip()

        if not all([first_name, last_name, block]):
            flash("All fields are required.", "error")
            return redirect(url_for('admin.students'))

        # Student.block is VARCHAR(10) in the DB; enforce before insert to avoid flush-time errors.
        if len(block) > 10:
            flash("Class section name must be 10 characters or fewer.", "error")
            return redirect(url_for('admin.students'))

        # Generate initials
        first_initial = first_name[0].upper()
        last_initial = last_name[0].upper()

        # Generate salt
        salt = get_random_salt()

        # v2: eliminate DOB-based credential material.
        claim_seed = int.from_bytes(salt[:2], "big") % 10000
        first_half_hash = compute_primary_claim_hash(first_initial, claim_seed, salt)
        second_half_hash = hash_hmac(str(claim_seed).encode(), salt)
        seed_hash = hash_hmac(str(claim_seed).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        last_name_parts = hash_last_name_parts(last_name, salt)

        current_admin_id = session.get("admin_id")
        class_context = _resolve_student_add_class_context(current_admin_id, block)
        if not class_context:
            flash("Select a class before making changes.", "error")
            return redirect(url_for('admin.students'))

        join_code = class_context['join_code']
        class_id = class_context['class_id']
        dedupe_key = _build_teacher_block_dedupe_key(class_id, first_name, last_name)

        existing_seat_in_class = Seat.query.filter_by(
            class_id=class_id,
            dedupe_code=dedupe_key,
        ).first()
        if existing_seat_in_class:
            flash(f"Student {first_name} {last_name} is already in your class.", "info")
            return redirect(url_for('admin.students'))

        if additional_notes:
            current_app.logger.info(
                "Student add additional notes provided (not persisted): class_id=%s block=%s length=%s",
                class_id,
                block,
                len(additional_notes),
            )

        # Create student
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            join_code=join_code,
            class_id=class_id,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            has_completed_setup=False,
        )

        db.session.add(new_student)
        db.session.flush()
        db.session.add(StudentTeacher(student_id=new_student.id, teacher_id=current_admin_id, join_code=join_code))

        # Ensure ClassEconomy record exists before creating Seat
        _ensure_join_code_anchors(current_admin_id, join_code)

        new_seat = Seat(
            student_id=new_student.id,
            class_id=class_id,
            join_code=join_code,
            block=block,
            dedupe_code=dedupe_key,
            claimed_at=None,  # Student hasn't set up username yet
        )
        db.session.add(new_seat)

        if class_context.get('class_created'):
            _queue_pending_class_timezone_confirmation(class_context.get('class_row'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error adding individual student", exc_info=True)
        flash(f"Cannot add student due to internal error", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/add-manual', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def add_manual_student():
    """Add a student with full manual configuration (advanced mode)."""
    try:
        from werkzeug.security import generate_password_hash

        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob', '').strip()
        block = request.form.get('block', '').strip().upper()
        username = request.form.get('username', '').strip()
        pin = request.form.get('pin', '').strip()
        passphrase = request.form.get('passphrase', '').strip()
        hall_passes = int(request.form.get('hall_passes', 3))
        rent_enabled = request.form.get('rent_enabled') == 'on'
        setup_complete = request.form.get('setup_complete') == 'on'

        if not all([first_name, last_name, dob_str, block]):
            flash("Required fields missing.", "error")
            return redirect(url_for('admin.students'))

        # Generate initials
        first_initial = first_name[0].upper()
        last_initial = last_name[0].upper()

        # Parse DOB and calculate sum
        try:
            dob_date = _parse_dob_date(dob_str)
            dob_sum = parse_dob_input(dob_str)
        except ValueError:
            flash("Invalid date of birth. Please use the date picker.", "error")
            return redirect(url_for('admin.students'))

        # Generate salt
        salt = get_random_salt()

        # Compute first_half_hash using canonical claim credential (first initial + DOB sum)
        first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, salt)
        second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        last_name_parts = hash_last_name_parts(last_name, salt)

        current_admin_id = session.get("admin_id")
        class_context = _resolve_student_add_class_context(current_admin_id, block)
        if not class_context:
            flash("Select a class before making changes.", "error")
            return redirect(url_for('admin.students'))

        join_code = class_context['join_code']
        class_id = class_context['class_id']
        dedupe_key = _build_teacher_block_dedupe_key(class_id, first_name, last_name)
        dob_sum_hash = hash_hmac(str(dob_sum).encode(), salt)

        existing_seat_in_class = Seat.query.filter_by(
            class_id=class_id,
            dedupe_code=dedupe_key,
        ).first()
        if existing_seat_in_class:
            flash(f"Student {first_name} {last_name} is already in your class.", "info")
            return redirect(url_for('admin.students'))

        # Check for duplicates GLOBALLY (not scoped to teacher)
        potential_duplicates = Student.query.filter_by(
            first_name=first_name,
            last_initial=last_initial,
        ).all()

        for existing_student in potential_duplicates:
            # Verify credential matches (canonical + legacy)
            credential_matches, is_primary, canonical_hash = match_claim_hash(
                existing_student.first_half_hash,
                first_initial,
                last_initial,
                dob_sum,
                existing_student.salt,
            )

            if credential_matches:
                if canonical_hash and not is_primary:
                    existing_student.first_half_hash = canonical_hash
                current_admin_id = session.get("admin_id")
                existing_class_seat = Seat.query.filter_by(
                    student_id=existing_student.id,
                    class_id=class_id,
                ).first()
                if existing_class_seat and existing_class_seat.claimed_at:
                    flash(f"Student {first_name} {last_name} is already in your class.", "info")
                else:
                    flash(f"Student {first_name} {last_name} already exists. Linking to your class.", "warning")
                    _link_student_to_admin(
                        existing_student,
                        current_admin_id,
                        join_code=join_code,
                        class_id=class_id,
                        block=block,
                    )
                    if class_context.get('class_created'):
                        _queue_pending_class_timezone_confirmation(class_context.get('class_row'))
                return redirect(url_for('admin.students'))

        # Create student
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            join_code=join_code,
            class_id=class_id,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            hall_passes=hall_passes,
            is_rent_enabled=rent_enabled,
            has_completed_setup=setup_complete,
        )

        # Set username if provided
        if username:
            new_student.username_hash = hash_username(username, salt)
            new_student.username_lookup_hash = hash_username_lookup(username)

        # Set PIN if provided
        if pin:
            new_student.pin_hash = generate_password_hash(pin)

        # Set passphrase if provided
        if passphrase:
            new_student.passphrase_hash = generate_password_hash(passphrase)

        db.session.add(new_student)
        db.session.flush()
        db.session.add(StudentTeacher(student_id=new_student.id, teacher_id=current_admin_id, join_code=join_code))

        # Ensure ClassEconomy record exists before creating Seat
        _ensure_join_code_anchors(current_admin_id, join_code)

        # Student is claimed if they have a username set
        is_claimed = bool(username)

        new_seat = Seat(
            student_id=new_student.id,
            class_id=class_id,
            join_code=join_code,
            block=block,
            dedupe_code=dedupe_key,
            claimed_at=utc_now() if is_claimed else None,
        )
        db.session.add(new_seat)

        if class_context.get('class_created'):
            _queue_pending_class_timezone_confirmation(class_context.get('class_row'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error creating manual student", exc_info=True)
        flash(f"Cannot create student due to internal error", "error")

    return redirect(url_for('admin.students'))


# -------------------- STORE MANAGEMENT --------------------

def _end_of_day_utc(date_obj):
    """Convert a local date to end-of-day UTC using effective teacher timezone."""
    if not date_obj:
        return None
    return local_date_end_utc(date_obj)

import uuid

def generate_collective_goal_instance_code():
    return str(uuid.uuid4())

@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store_management():
    """Manage store items - view, create, edit, delete."""
    admin_id = session.get("admin_id")
    feature_options = get_admin_feature_join_code_options('store', admin_id=admin_id)
    selected_scope = require_admin_feature_scope(
        'store',
        admin_id=admin_id,
        requested_block=request.args.get('block'),
    )
    selected_join_code = selected_scope['join_code']
    selected_block = selected_scope['block']
    student_ids_subq = _student_scope_subquery_for_join_code(selected_join_code)
    form = StoreItemForm()

    # Limit store scope to classes where the feature is enabled.
    blocks = [option['block'] for option in feature_options if option.get('block')]
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Build class_labels_by_block dictionary for template
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    if form.validate_on_submit():
        submitted_blocks = {block.strip().upper() for block in (form.blocks.data or []) if block}
        enabled_blocks = {block for block in blocks if block}
        if submitted_blocks and not submitted_blocks.issubset(enabled_blocks):
            abort(404)
        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "class_id": selected_scope["class_id"],
                    "join_code": selected_scope["join_code"],
                    "name": form.name.data,
                    "item_type": form.item_type.data,
                    "price": str(form.price.data),
                    "is_active": bool(form.is_active.data),
                    "blocks": sorted(submitted_blocks),
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = f"feat:store:item-create:{selected_scope['class_id']}:{payload_hash}"

        db.session.rollback()
        with FEATContext("FEAT-STOR-001", idempotency_key=idempotency_key):
            new_item = StoreItem(
                teacher_id=admin_id,
                join_code=selected_scope['join_code'],
                class_id=selected_scope['class_id'],
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                tier=form.tier.data if form.tier.data else None,
                item_type=form.item_type.data,
                inventory=form.inventory.data,
                limit_per_student=form.limit_per_student.data,
                auto_delist_date=form.auto_delist_date.data,
                auto_expiry_days=form.auto_expiry_days.data,
                is_active=form.is_active.data,
                is_long_term_goal=form.is_long_term_goal.data,
                bypass_cwi_warnings=form.bypass_cwi_warnings.data,
                # Bundle settings
                is_bundle=form.is_bundle.data,
                bundle_quantity=form.bundle_quantity.data if form.is_bundle.data else None,
                # Bulk discount settings
                bulk_discount_enabled=form.bulk_discount_enabled.data,
                bulk_discount_quantity=form.bulk_discount_quantity.data if form.bulk_discount_enabled.data else None,
                bulk_discount_percentage=form.bulk_discount_percentage.data if form.bulk_discount_enabled.data else None,
                # Collective goal settings
                collective_goal_type=form.collective_goal_type.data if form.item_type.data == 'collective' else None,
                collective_goal_target=form.collective_goal_target.data if form.item_type.data == 'collective' else None,
                collective_goal_expires_at=(
                    _end_of_day_utc(form.collective_goal_expires_at.data)
                    if form.item_type.data == 'collective'
                    else None
                ),
                collective_goal_instance_code=(
                    generate_collective_goal_instance_code()
                    if form.item_type.data == 'collective' and form.is_active.data
                    else None
                ),
                # Redemption prompt
                redemption_prompt=form.redemption_prompt.data if form.redemption_prompt.data else None
            )
            db.session.add(new_item)
            db.session.flush()  # Get the ID for the item before adding blocks
            # Set blocks using many-to-many relationship
            if form.blocks.data:
                new_item.set_blocks(form.blocks.data)
        flash(f"'{new_item.name}' has been added to the store.", "success")
        return redirect(url_for('admin.store_management'))

    # Get items for this teacher only (reuse admin_id from above)
    items = [
        item for item in StoreItem.query.filter_by(class_id=selected_scope['class_id']).order_by(StoreItem.name).all()
        if not item.blocks_list or selected_block in {b.strip().upper() for b in item.blocks_list if b}
    ]

    # Get store statistics for overview tab
    from app.models import StudentItem
    total_items = len(items)
    active_items = len([i for i in items if i.is_active])
    total_purchases = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StudentItem.join_code == selected_join_code)
        .count()
    )

    # Get pending redemption requests (items awaiting teacher approval)
    pending_redemptions = (
        StudentItem.query
        .options(joinedload(StudentItem.student), joinedload(StudentItem.store_item))
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StudentItem.join_code == selected_join_code)
        .filter(StudentItem.status == 'processing')
        .order_by(StudentItem.redemption_date.desc())
        .limit(10)
        .all()
    )

    # Get recent purchases (all statuses, ordered by purchase date)
    recent_purchases = (
        StudentItem.query
        .options(joinedload(StudentItem.student), joinedload(StudentItem.store_item))
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StudentItem.join_code == selected_join_code)
        .order_by(StudentItem.purchase_date.desc())
        .limit(10)
        .all()
    )

    collective_progress_by_item = {}
    collective_items = [item for item in items if item.item_type == 'collective']
    if collective_items:
        class_economy_rows = ClassEconomy.query.filter_by(class_id=selected_scope['class_id']).all()
        join_code_to_block = {}
        join_code_to_label = {}

        # Count unique claimed students per join_code via Seat
        class_sizes = {}
        class_size_query = (
            db.session.query(
                Seat.join_code,
                db.func.count(db.func.distinct(Seat.student_id)).label('student_count')
            )
            .filter(
                Seat.class_id == selected_scope['class_id'],
                Seat.claimed_at.isnot(None),
                Seat.student_id.isnot(None),
                Seat.join_code.isnot(None),
            )
            .group_by(Seat.join_code)
            .all()
        )
        class_sizes = {row.join_code: int(row.student_count or 0) for row in class_size_query}

        for ce_row in class_economy_rows:
            if not ce_row.join_code:
                continue
            join_code_to_block.setdefault(ce_row.join_code, (ce_row.section or '').strip().upper())
            join_code_to_label.setdefault(ce_row.join_code, ce_row.display_name or ce_row.join_code)

        collective_item_ids = [item.id for item in collective_items]
        collective_counts = (
            db.session.query(
                StudentItem.store_item_id,
                StudentItem.join_code,
                db.func.count(db.distinct(StudentItem.student_id)).label('student_count'),
            )
            .join(Student, StudentItem.student_id == Student.id)
            .join(StoreItem, StudentItem.store_item_id == StoreItem.id)
            .filter(
                Student.id.in_(sa.select(student_ids_subq)),
                StudentItem.join_code == selected_join_code,
                StudentItem.store_item_id.in_(collective_item_ids),
                StudentItem.join_code.isnot(None),
                StudentItem.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
                StudentItem.collective_goal_instance_code == StoreItem.collective_goal_instance_code,
            )
            .group_by(StudentItem.store_item_id, StudentItem.join_code)
            .all()
        )
        counts_lookup = {
            (row.store_item_id, row.join_code): int(row.student_count or 0)
            for row in collective_counts
        }

        for item in collective_items:
            if item.blocks_list:
                applicable_join_codes = [
                    jc for jc, block in join_code_to_block.items()
                    if block in {b.strip().upper() for b in item.blocks_list if b}
                ]
            else:
                applicable_join_codes = list(join_code_to_block.keys())

            per_class = []
            for jc in sorted(applicable_join_codes):
                if jc != selected_join_code:
                    continue
                count = counts_lookup.get((item.id, jc), 0)
                if item.collective_goal_type == 'fixed':
                    target = int(item.collective_goal_target or 0)
                else:
                    target = class_sizes.get(jc, 0)
                per_class.append({
                    'join_code': jc,
                    'class_label': join_code_to_label.get(jc, jc),
                    'count': count,
                    'target': target,
                    'remaining': max(0, target - count),
                    'percent': min(100, int((count / target) * 100)) if target > 0 else 0,
                    'is_complete': bool(target > 0 and count >= target),
                })
            collective_progress_by_item[item.id] = per_class

    # -------------------- Redemption Audit (live + inferred legacy adapter) --------------------
    audit_student = request.args.get('audit_student', '').strip()
    audit_class = request.args.get('audit_class', '').strip()
    audit_action = request.args.get('audit_action', '').strip()
    audit_start_date = request.args.get('audit_start_date', '').strip()
    audit_end_date = request.args.get('audit_end_date', '').strip()
    audit_page = max(1, request.args.get('audit_page', 1, type=int))
    audit_per_page = 25

    join_code_label_map = {}
    teacher_class_rows = ClassEconomy.query.filter_by(teacher_id=admin_id).all()
    for ce_row in teacher_class_rows:
        if ce_row.join_code and ce_row.join_code not in join_code_label_map:
            join_code_label_map[ce_row.join_code] = ce_row.display_name or ce_row.join_code

    parsed_audit_action = None
    if audit_action:
        try:
            parsed_audit_action = RedemptionAuditAction(audit_action)
        except ValueError:
            flash("Invalid audit action filter.", "warning")

    live_query = RedemptionAuditLog.query.filter(
        RedemptionAuditLog.teacher_id == admin_id,
        RedemptionAuditLog.source == RedemptionAuditSource.LIVE,
        RedemptionAuditLog.join_code == selected_join_code,
    )
    if audit_student:
        live_query = live_query.filter(RedemptionAuditLog.student_display_name.ilike(f"%{audit_student}%"))
    if audit_class:
        live_query = live_query.filter(RedemptionAuditLog.class_display_label == audit_class)
    if parsed_audit_action:
        live_query = live_query.filter(RedemptionAuditLog.action == parsed_audit_action)
    if audit_start_date:
        try:
            start_day = datetime.strptime(audit_start_date, '%Y-%m-%d').date()
            start_dt, _ = local_date_bounds_utc(start_day)
            live_query = live_query.filter(RedemptionAuditLog.timestamp >= start_dt)
        except ValueError:
            flash("Invalid audit start date format. Please use YYYY-MM-DD.", "warning")
    if audit_end_date:
        try:
            end_day = datetime.strptime(audit_end_date, '%Y-%m-%d').date()
            _, end_dt = local_date_bounds_utc(end_day)
            end_dt = end_dt + timedelta(seconds=1)
            live_query = live_query.filter(RedemptionAuditLog.timestamp < end_dt)
        except ValueError:
            flash("Invalid audit end date format. Please use YYYY-MM-DD.", "warning")

    live_rows = live_query.order_by(RedemptionAuditLog.timestamp.desc()).limit(5000).all()
    live_keys = {
        (row.student_item_id, row.action.value if hasattr(row.action, 'value') else row.action)
        for row in live_rows
    }

    inferred_query = (
        StudentItem.query
        .options(joinedload(StudentItem.student), joinedload(StudentItem.store_item))
        .join(Student, StudentItem.student_id == Student.id)
        .join(StoreItem, StudentItem.store_item_id == StoreItem.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(StoreItem.class_id == selected_scope['class_id'])
        .filter(StudentItem.join_code == selected_join_code)
    )
    if audit_student:
        matching_student_ids = []
        for s in _scoped_students().all():
            if audit_student.lower() in s.full_name.lower():
                matching_student_ids.append(s.id)
        if matching_student_ids:
            inferred_query = inferred_query.filter(StudentItem.student_id.in_(matching_student_ids))
        else:
            inferred_query = inferred_query.filter(sa.false())

    inferred_items = inferred_query.all()
    inferred_rows = []
    for si in inferred_items:
        if si.status == 'processing':
            inferred_action = 'request'
            inferred_ts = si.redemption_date or si.purchase_date
        elif si.status == 'completed':
            inferred_action = 'approved'
            inferred_ts = si.redemption_date or si.purchase_date
        else:
            continue

        if (si.id, inferred_action) in live_keys:
            continue

        class_label = join_code_label_map.get(si.join_code)
        if not class_label:
            class_label = class_labels_by_block.get((si.student.block or '').upper(), si.student.block or 'Unknown Class')

        row = {
            'student_item_id': si.id,
            'student_display_name': si.student.full_name if si.student else 'Unknown Student',
            'class_display_label': class_label,
            'action': inferred_action,
            'notes': si.redemption_details,
            'timestamp': inferred_ts,
            'source': 'inferred_legacy',
        }

        if audit_class and row['class_display_label'] != audit_class:
            continue
        if parsed_audit_action and row['action'] != parsed_audit_action.value:
            continue
        if audit_start_date:
            try:
                start_day = datetime.strptime(audit_start_date, '%Y-%m-%d').date()
                start_dt, _ = local_date_bounds_utc(start_day)
                if not row['timestamp'] or ensure_utc(row['timestamp']) < start_dt:
                    continue
            except ValueError:
                pass
        if audit_end_date:
            try:
                end_day = datetime.strptime(audit_end_date, '%Y-%m-%d').date()
                _, end_dt = local_date_bounds_utc(end_day)
                end_dt = end_dt + timedelta(seconds=1)
                if not row['timestamp'] or ensure_utc(row['timestamp']) >= end_dt:
                    continue
            except ValueError:
                pass
        inferred_rows.append(row)

    live_serialized = [{
        'student_item_id': row.student_item_id,
        'student_display_name': row.student_display_name,
        'class_display_label': row.class_display_label,
        'action': row.action.value if hasattr(row.action, 'value') else row.action,
        'notes': row.notes,
        'timestamp': row.timestamp,
        'source': row.source.value if hasattr(row.source, 'value') else row.source,
    } for row in live_rows]

    audit_rows_all = live_serialized + inferred_rows
    audit_rows_all.sort(key=lambda r: ensure_utc(r['timestamp']) if r['timestamp'] else UTC_MIN, reverse=True)

    audit_total = len(audit_rows_all)
    audit_total_pages = max(1, math.ceil(audit_total / audit_per_page)) if audit_total else 1
    if audit_page > audit_total_pages:
        audit_page = audit_total_pages
    audit_start_idx = (audit_page - 1) * audit_per_page
    audit_end_idx = audit_start_idx + audit_per_page
    audit_rows = audit_rows_all[audit_start_idx:audit_end_idx]

    audit_class_options = sorted(set(class_labels_by_block.values()))

    rent_managed_item_ids = {
        row[0] for row in db.session.query(RentItem.store_item_id).join(
            RentSettings, RentItem.rent_setting_id == RentSettings.id
        ).filter(
            RentSettings.class_id == selected_scope['class_id'],
            RentItem.store_item_id.isnot(None)
        ).all()
    }

    return render_template('admin_store.html', form=form, items=items, current_page="store",
                         total_items=total_items, active_items=active_items, total_purchases=total_purchases,
                         pending_redemptions=pending_redemptions, recent_purchases=recent_purchases,
                         class_labels_by_block=class_labels_by_block,
                         rent_managed_item_ids=rent_managed_item_ids,
                         collective_progress_by_item=collective_progress_by_item,
                         audit_rows=audit_rows,
                         audit_total=audit_total,
                         audit_page=audit_page,
                         audit_total_pages=audit_total_pages,
                         audit_class_options=audit_class_options,
                         audit_student=audit_student,
                         audit_class=audit_class,
                         audit_action=audit_action,
                         audit_start_date=audit_start_date,
                         audit_end_date=audit_end_date,
                         feature_options=feature_options,
                         selected_feature_scope=selected_scope)


@admin_bp.route('/store/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_store_item(item_id):
    """Edit an existing store item."""
    admin_id = session.get("admin_id")
    selected_scope = require_admin_feature_scope(
        'store',
        admin_id=admin_id,
        requested_block=request.values.get('block'),
    )
    item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
    if item.blocks_list and selected_scope['block'] not in {b.strip().upper() for b in item.blocks_list if b}:
        abort(404)
    form = StoreItemForm(obj=item)

    # Populate blocks choices from teacher's students
    blocks = [option['block'] for option in get_admin_feature_join_code_options('store', admin_id=admin_id) if option.get('block')]
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Pre-populate selected blocks on GET request (using many-to-many relationship)
    if request.method == 'GET':
        form.blocks.data = item.blocks_list
        # Convert stored datetime to date for the DateField
        if item.collective_goal_expires_at:
            form.collective_goal_expires_at.data = item.collective_goal_expires_at.date()

    if form.validate_on_submit():
        submitted_blocks = {block.strip().upper() for block in (form.blocks.data or []) if block}
        enabled_blocks = {block for block in blocks if block}
        if submitted_blocks and not submitted_blocks.issubset(enabled_blocks):
            abort(404)
        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "item_id": item.id,
                    "class_id": selected_scope["class_id"],
                    "name": form.name.data,
                    "item_type": form.item_type.data,
                    "price": str(form.price.data),
                    "is_active": bool(form.is_active.data),
                    "blocks": sorted(submitted_blocks),
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = f"feat:store:item-edit:{selected_scope['class_id']}:{item.id}:{payload_hash}"

        db.session.rollback()
        with FEATContext("FEAT-STOR-001", idempotency_key=idempotency_key):
            item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
            was_active = item.is_active

            # Populate other fields first
            form.populate_obj(item)
            # Set blocks using many-to-many relationship
            item.set_blocks(form.blocks.data if form.blocks.data else [])

            item.collective_goal_expires_at = (
                _end_of_day_utc(form.collective_goal_expires_at.data)
                if item.item_type == 'collective'
                else None
            )

            # Rotate instance code if reviving an inactive collective goal or changing to collective
            if item.item_type == 'collective' and form.is_active.data:
                if not was_active or not item.collective_goal_instance_code:
                    # Issue new instance code
                    item.collective_goal_instance_code = generate_collective_goal_instance_code()
        flash(f"'{item.name}' has been updated.", "success")
        return redirect(url_for('admin.store_management'))
    payroll_settings = PayrollSettings.query.filter_by(class_id=selected_scope['class_id'], is_active=True).first()
    return render_template('admin_edit_item.html', form=form, item=item, current_page="store", payroll_settings=payroll_settings, selected_feature_scope=selected_scope)


@admin_bp.route('/store/delete/<int:item_id>', methods=['POST'])
@admin_bp.route('/item/deactivate/<int:item_id>', methods=['POST'])
@admin_required
def delete_store_item(item_id):
    """Deactivate a store item (soft delete)."""
    admin_id = session.get("admin_id")
    selected_scope = require_admin_feature_scope(
        'store',
        admin_id=admin_id,
        requested_block=request.values.get('block'),
    )
    item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
    if item.blocks_list and selected_scope['block'] not in {b.strip().upper() for b in item.blocks_list if b}:
        abort(404)

    # Prevent deletion if linked to rent settings
    if _block_rent_linked_store_item(item):
        return redirect(url_for('admin.store_management'))

    # For active collective items, refund any pending purchases before deactivating
    # so students are not left with purchased but unredeemable items.
    idempotency_key = f"feat:store:item-deactivate:{selected_scope['class_id']}:{item.id}"
    db.session.rollback()
    with FEATContext("FEAT-STOR-003", idempotency_key=idempotency_key):
        item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
        refunded = 0
        if item.item_type == 'collective' and item.is_active:
            refunded = refund_pending_collective_purchases(item, description_suffix="Item Removed by Teacher")

        # To preserve history, we'll just deactivate it instead of a hard delete
        # A hard delete would be: db.session.delete(item)
        item.is_active = False

    if refunded:
        flash(
            f"{refunded} pending purchase(s) for '{item.name}' have been refunded automatically.",
            "info",
        )
    flash(f"'{item.name}' has been deactivated and removed from the store.", "success")
    return redirect(url_for('admin.store_management'))


@admin_bp.route('/store/hard-delete/<int:item_id>', methods=['POST'])
@admin_required
def hard_delete_store_item(item_id):
    """Legacy endpoint: hard item deletion is restricted to join-code deletion workflow."""
    admin_id = session.get("admin_id")
    selected_scope = require_admin_feature_scope(
        'store',
        admin_id=admin_id,
        requested_block=request.values.get('block'),
    )
    item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
    if item.blocks_list and selected_scope['block'] not in {b.strip().upper() for b in item.blocks_list if b}:
        abort(404)

    # Prevent deletion if linked to rent settings
    if _block_rent_linked_store_item(item):
        return redirect(url_for('admin.store_management'))

    flash(
        f"Hard deletion for '{item.name}' is disabled. Deactivate items instead, "
        "or delete the class join code for full scoped cleanup.",
        "error",
    )
    return redirect(url_for('admin.store_management'))


# -------------------- RENT SETTINGS --------------------

def _block_rent_linked_store_item(item: StoreItem) -> bool:
    """Return True if store item is rent-linked and deletion should be blocked."""
    is_managed_by_rent = item.is_rent_linked or db.session.query(RentItem.id).join(
        RentSettings, RentItem.rent_setting_id == RentSettings.id
    ).filter(
        RentSettings.class_id == item.class_id,
        RentItem.store_item_id == item.id
    ).first() is not None

    if is_managed_by_rent:
        flash(f"Cannot delete '{item.name}' because it is managed by Rent Settings. Please remove it from Rent Settings instead.", "error")
        return True
    return False

def _sync_rent_items_to_store(rent_settings, teacher_id, block):
    """
    Sync rent items with store items.
    Creates or updates store items for rent items that are marked as available in store.
    Deactivates store items for rent items that are no longer available.

    FIX: Prevents duplicate store items when applying rent settings to all periods.
    Store items are now shared across blocks using StoreItemBlock for visibility.
    """
    from app.models import RentItem, StoreItem, StoreItemBlock

    join_code = _resolve_join_code_for_block(teacher_id, block)
    class_id = _ensure_join_code_anchors(teacher_id, join_code, class_label=block) if join_code else None
    if not join_code or not class_id:
        current_app.logger.warning(
            "Skipping rent-to-store sync for teacher %s block %s due to missing class scope",
            teacher_id,
            block,
        )
        return

    rent_items = RentItem.query.filter_by(rent_setting_id=rent_settings.id).all()

    for rent_item in rent_items:
        # Skip store sync for hall passes
        if rent_item.rent_item_type == 'hall_pass':
            continue

        if rent_item.is_available_in_store and rent_item.store_price:
            # Determine purchase limit based on duration type
            limit = None
            duration_note = ""

            if rent_item.rent_item_type == 'per_use':
                limit = None
                if rent_item.use_limit:
                    duration_note = f"Includes {rent_item.use_limit} free uses per period."
                else:
                    duration_note = "Unlimited free uses per period for rent payers."
            elif rent_item.rent_item_type == 'privilege':
                limit = 1  # Can only buy once per rent period
                duration_note = "Valid until next rent payment is due."
            else:  # fallback
                limit = None
                duration_note = "Purchase each time you need to use it."

            base_desc = rent_item.description or f"Single purchase alternative to rent. By paying rent (${rent_settings.rent_amount:.2f}), you get access to this and other items included in rent."
            description = f"{base_desc}\n\n{duration_note}"

            store_item = None

            # Check if this rent_item already has a store_item_id
            if rent_item.store_item_id:
                store_item = db.session.get(StoreItem, rent_item.store_item_id)

            # If no store_item yet, check if a rent-linked one exists for this teacher+name.
            # Only consider store items already linked to a RentItem to avoid
            # overwriting unrelated non-rent store items with the same name.
            if not store_item:
                store_item = StoreItem.query.join(
                    RentItem, RentItem.store_item_id == StoreItem.id
                ).filter(
                    StoreItem.class_id == class_id,
                    StoreItem.name == rent_item.name
                ).first()

            # Mark any store-backed rent item as rent-linked (privilege + per-use).
            # Hall pass items are skipped earlier and never synced to store.
            is_rent_linked_item = rent_item.rent_item_type in ('privilege', 'per_use')

            if store_item:
                # Update existing store item
                if not store_item.join_code:
                    store_item.join_code = join_code
                if not store_item.class_id:
                    store_item.class_id = class_id
                store_item.name = rent_item.name
                store_item.description = description
                store_item.price = rent_item.store_price
                store_item.limit_per_student = limit
                store_item.is_active = True
                store_item.is_rent_linked = is_rent_linked_item

                # Link this rent_item to the store_item if not already linked
                if not rent_item.store_item_id:
                    rent_item.store_item_id = store_item.id
            else:
                # Create new store item only if it doesn't exist
                # Rent items should be 'delayed' (redeemable) to allow use tracking
                # especially for multi-use items or privileges valid for a period
                store_item = StoreItem(
                    teacher_id=teacher_id,
                    join_code=join_code,
                    class_id=class_id,
                    name=rent_item.name,
                    description=description,
                    price=rent_item.store_price,
                    item_type='delayed',
                    limit_per_student=limit,
                    is_active=True,
                    is_rent_linked=is_rent_linked_item
                )
                db.session.add(store_item)
                db.session.flush()  # Get the store_item.id

                # Link the rent item to this store item
                rent_item.store_item_id = store_item.id

            # Ensure block visibility is set (don't replace, add to existing)
            if block:
                existing_block = StoreItemBlock.query.filter_by(
                    store_item_id=store_item.id,
                    block=block
                ).first()

                if not existing_block:
                    store_item_block = StoreItemBlock(store_item_id=store_item.id, block=block)
                    db.session.add(store_item_block)

        elif rent_item.store_item_id:
            # Remove this block's visibility for the store item
            store_item = db.session.get(StoreItem, rent_item.store_item_id)
            if store_item and block:
                StoreItemBlock.query.filter_by(
                    store_item_id=store_item.id,
                    block=block
                ).delete()

                # Only deactivate the shared StoreItem if no other RentItem
                # references it (i.e., it's not used by any other block)
                other_refs = RentItem.query.filter(
                    RentItem.store_item_id == store_item.id,
                    RentItem.id != rent_item.id,
                    RentItem.is_available_in_store == True
                ).count()
                if other_refs == 0:
                    store_item.is_active = False

    db.session.flush()


def _calculate_base_rent_amount(rent_settings: RentSettings, current_year: int, current_month: int) -> Decimal:
    """
    Normalize the configured rent amount to a monthly view based on frequency type.

    For 'daily', we use the actual number of days in the current month for accuracy.
    For 'weekly', we approximate 4 weeks per month.
    For 'custom', we scale based on the custom frequency configuration.
    For all other types, we use the configured amount as-is.

    Args:
        rent_settings: RentSettings object with frequency configuration
        current_year: Year to calculate for (used for accurate day count)
        current_month: Month to calculate for (used for accurate day count)

    Returns:
        Base rent amount normalized to monthly view
    """
    base_amount = rent_settings.rent_amount

    if rent_settings.frequency_type == 'daily':
        # Use actual number of days in the month for accuracy
        days_in_month = Decimal(monthrange(current_year, current_month)[1])
        return rent_settings.rent_amount * days_in_month

    if rent_settings.frequency_type == 'weekly':
        # Approximation: 4 weeks per month
        return rent_settings.rent_amount * Decimal('4')

    if rent_settings.frequency_type == 'custom':
        # Approximate a monthly amount based on custom frequency configuration
        unit = getattr(rent_settings, 'custom_frequency_unit', None)
        value = getattr(rent_settings, 'custom_frequency_value', None)
        try:
            if value and value > 0:
                from app.models import _quantize_currency
                normalized_unit = str(unit).lower().rstrip('s') if unit else None
                if normalized_unit == 'day':
                    # Every N days -> scale to days per month
                    days_in_month = monthrange(current_year, current_month)[1]
                    return _quantize_currency(rent_settings.rent_amount * Decimal(days_in_month) / Decimal(value))
                elif normalized_unit == 'week':
                    # Every N weeks -> scale to ~4 weeks per month
                    return _quantize_currency(rent_settings.rent_amount * Decimal('4') / Decimal(value))
                elif normalized_unit == 'month':
                    # Every N months -> monthly share of that amount
                    return _quantize_currency(rent_settings.rent_amount / Decimal(value))
        except (TypeError, ValueError, ZeroDivisionError):
            # If anything goes wrong, fall back to the base amount
            pass

    return base_amount


@admin_bp.route('/rent-settings', methods=['GET', 'POST'])
@admin_required
def rent_settings():
    """Configure rent settings."""
    admin_id = session.get("admin_id")
    student_ids_subq = _student_scope_subquery()
    feature_options = get_admin_feature_join_code_options('rent', admin_id=admin_id)
    selected_scope = require_admin_feature_scope(
        'rent',
        admin_id=admin_id,
        requested_block=request.values.get('settings_block'),
    )
    payroll_settings = PayrollSettings.query.filter_by(
        class_id=selected_scope['class_id'],
        is_active=True,
    ).first()
    teacher_blocks = [option['block'] for option in feature_options]
    settings_block = selected_scope['block']

    # Get or create rent settings for this class
    settings = None
    if settings_block:
        settings = RentSettings.query.filter_by(class_id=selected_scope['class_id'], block=settings_block).first()

    if request.method == 'POST':
        apply_to_all = request.form.get('apply_to_all') == 'true'
        blocks_to_update = teacher_blocks if apply_to_all else [settings_block]
        join_code_map = {}
        blocks_with_rows = set()
        if blocks_to_update:
            join_code_rows = db.session.query(ClassEconomy.section, ClassEconomy.join_code).filter(
                ClassEconomy.teacher_id == admin_id,
                ClassEconomy.section.in_(blocks_to_update)
            ).all()
            for block, join_code in join_code_rows:
                blocks_with_rows.add(block)
                if join_code and not join_code_map.get(block):
                    join_code_map[block] = join_code

        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "class_id": selected_scope["class_id"],
                    "settings_block": settings_block,
                    "apply_to_all": apply_to_all,
                    "blocks_to_update": sorted([b for b in blocks_to_update if b]),
                    "form_keys": sorted(request.form.keys()),
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:rent:settings-update:{selected_scope['class_id']}:{payload_hash}"
        )

        db.session.rollback()
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            for block in blocks_to_update:
                scope_for_block = require_admin_feature_scope('rent', admin_id=admin_id, requested_block=block, allow_default=False)
                # Get or create settings for this class
                block_settings = RentSettings.query.filter_by(class_id=scope_for_block['class_id'], block=block).first()
                if not block_settings:
                    block_settings = RentSettings(
                        class_id=scope_for_block['class_id'],
                        block=block,
                    )
                    db.session.add(block_settings)

                # Main toggle
                block_settings.is_enabled = request.form.get('is_enabled') == 'on'

                # Rent amount and frequency
                from app.models import _quantize_currency
                block_settings.rent_amount = _quantize_currency(request.form.get('rent_amount', '50.0'))
                block_settings.frequency_type = request.form.get('frequency_type', 'monthly')

                if block_settings.frequency_type == 'custom':
                    block_settings.custom_frequency_value = int(request.form.get('custom_frequency_value', 1))
                    block_settings.custom_frequency_unit = request.form.get('custom_frequency_unit', 'days')
                else:
                    block_settings.custom_frequency_value = None
                    block_settings.custom_frequency_unit = None

                # Due date settings
                first_due_date_str = request.form.get('first_rent_due_date')
                if first_due_date_str:
                    block_settings.first_rent_due_date = datetime.strptime(first_due_date_str, '%Y-%m-%d')
                else:
                    block_settings.first_rent_due_date = None

                block_settings.due_day_of_month = int(request.form.get('due_day_of_month', 1))

                # Grace period and late penalties
                block_settings.grace_period_days = int(request.form.get('grace_period_days', 3))
                block_settings.late_penalty_amount = _quantize_currency(request.form.get('late_penalty_amount', '10.0'))
                block_settings.late_penalty_type = request.form.get('late_penalty_type', 'once')

                if block_settings.late_penalty_type == 'recurring':
                    block_settings.late_penalty_frequency_days = int(request.form.get('late_penalty_frequency_days', 7))
                else:
                    block_settings.late_penalty_frequency_days = None

                # Student payment options
                block_settings.bill_preview_enabled = request.form.get('bill_preview_enabled') == 'on'
                block_settings.bill_preview_days = int(request.form.get('bill_preview_days', 7))
                block_settings.allow_incremental_payment = request.form.get('allow_incremental_payment') == 'on'
                block_settings.prevent_purchase_when_late = request.form.get('prevent_purchase_when_late') == 'on'
                block_settings.bypass_cwi_warnings = request.form.get('bypass_cwi_warnings') == 'on'

        # Handle rent items (for all blocks in blocks_to_update)
        # Parse rent items from form once
        rent_item_indices = set()
        for key in request.form.keys():
            if key.startswith('rent_item_name_'):
                idx = key.split('_')[-1]
                rent_item_indices.add(idx)

        parsed_items = []
        for idx in sorted(rent_item_indices):
            name = request.form.get(f'rent_item_name_{idx}', '').strip()
            if not name:
                continue

            rent_item_type = request.form.get(f'rent_item_type_{idx}', 'privilege') # Default to privilege if missing
            if rent_item_type == 'privilege':
                purchase_duration = 'per_period'
            elif rent_item_type == 'per_use':
                purchase_duration = 'per_use'
            else:
                purchase_duration = None
            use_limit = None
            if rent_item_type == 'per_use':
                use_limit_val = request.form.get(f'rent_item_use_limit_{idx}', '').strip()
                if use_limit_val and use_limit_val.isdigit():
                    use_limit = int(use_limit_val)

            hall_pass_count = None
            if rent_item_type == 'hall_pass':
                hall_pass_val = request.form.get(f'rent_item_hall_pass_count_{idx}', '').strip()
                if hall_pass_val and hall_pass_val.isdigit():
                    hall_pass_count = int(hall_pass_val)

            # Logic changes based on type
            is_available = request.form.get(f'rent_item_store_available_{idx}') == 'on'
            if rent_item_type == 'per_use':
                is_available = True  # Always available in store for per_use items
            elif rent_item_type == 'hall_pass':
                # Hall passes are not typically listed in store via this mechanism
                pass

            item_data = {
                'id': request.form.get(f'rent_item_id_{idx}'),
                'name': name,
                'description': request.form.get(f'rent_item_description_{idx}', '').strip(),
                'is_available': is_available,
                'store_price_str': request.form.get(f'rent_item_store_price_{idx}', '').strip(),
                'purchase_duration': purchase_duration,
                'order_index': int(idx),
                'rent_item_type': rent_item_type,
                'use_limit': use_limit,
                'hall_pass_count': hall_pass_count
            }

            # Validation logic reuse
            store_price = None
            if item_data['is_available']:
                if not item_data['store_price_str']:
                    flash(f"Store price is required for '{name}' which is available in the store.", 'error')
                    item_data['is_available'] = False
                else:
                    try:
                        from app.models import _quantize_currency
                        store_price = _quantize_currency(item_data['store_price_str'])
                        if store_price <= Decimal('0'):
                            flash(f"Store price must be positive for '{name}'.", 'error')
                            item_data['is_available'] = False
                            store_price = None
                    except (ValueError, InvalidOperation):
                        flash(f"Invalid store price for '{name}'.", 'error')
                        item_data['is_available'] = False
                        store_price = None

            item_data['store_price'] = store_price
            parsed_items.append(item_data)

        from app.models import RentItem

        # Apply parsed items to each block
        for block in blocks_to_update:
                # Re-fetch settings for this block to ensure we have the object attached to session
                scope_for_block = require_admin_feature_scope('rent', admin_id=admin_id, requested_block=block, allow_default=False)
                block_settings = RentSettings.query.filter_by(class_id=scope_for_block['class_id'], block=block).first()
                if not block_settings:
                    continue

                existing_items = block_settings.rent_items.all()
                existing_map = {}

                # For the original block, we map by ID to preserve precise identity
                # For other blocks, we map by Name to attempt to sync updates across classes
                if block == settings_block:
                    existing_map = {str(item.id): item for item in existing_items}
                else:
                    existing_map = {item.name: item for item in existing_items}

                processed_items = set()

                # Mid-period lock: detect if any student has paid rent for current coverage period
                mid_period_locked = False
                block_join_code = join_code_map.get(block)
                if block in blocks_with_rows:
                    from app.routes.student import _calculate_rent_coverage_due_date
                    now = utc_now()
                    coverage_due = _calculate_rent_coverage_due_date(block_settings, now)
                    if coverage_due:
                        paid_query = RentPayment.query.filter_by(
                            class_id=block_settings.class_id,
                            coverage_month=coverage_due.month,
                            coverage_year=coverage_due.year
                        )
                        paid_count = paid_query.count()
                        if paid_count > 0:
                            mid_period_locked = True

                for item_data in parsed_items:
                    target_item = None

                    # Try to find matching existing item
                    if block == settings_block:
                        target_item = existing_map.get(item_data['id'])
                    else:
                        target_item = existing_map.get(item_data['name'])

                    if target_item:
                        # Update existing - always allow cosmetic fields
                        target_item.name = item_data['name']
                        target_item.description = item_data['description'] if item_data['description'] else None
                        target_item.order_index = item_data['order_index']
                        target_item.store_price = item_data['store_price']
                        if item_data['purchase_duration'] is not None:
                            target_item.purchase_duration = item_data['purchase_duration']

                        if mid_period_locked:
                            # Semantic fields locked: rent_item_type, use_limit, hall_pass_count
                            # Only allow is_available_in_store change for privilege items
                            if target_item.rent_item_type == 'privilege':
                                target_item.is_available_in_store = item_data['is_available']
                        else:
                            # No lock - update all fields freely
                            target_item.is_available_in_store = item_data['is_available']
                            target_item.rent_item_type = item_data['rent_item_type']
                            target_item.use_limit = item_data['use_limit']
                            target_item.hall_pass_count = item_data['hall_pass_count']
                        processed_items.add(target_item)
                    else:
                        # Create new
                        new_item = RentItem(
                            rent_setting_id=block_settings.id,
                            name=item_data['name'],
                            description=item_data['description'] if item_data['description'] else None,
                            order_index=item_data['order_index'],
                            is_available_in_store=item_data['is_available'],
                            store_price=item_data['store_price'],
                            purchase_duration=item_data['purchase_duration'] or 'per_use',
                            rent_item_type=item_data['rent_item_type'],
                            use_limit=item_data['use_limit'],
                            hall_pass_count=item_data['hall_pass_count']
                        )
                        db.session.add(new_item)
                        # No need to add to processed_items as it's new

                # Delete items that were not in the form (and thus not processed)
                for item in existing_items:
                    if item not in processed_items:
                        # If this item had a linked store item, deactivate it
                        if item.store_item_id:
                            store_item = db.session.get(StoreItem, item.store_item_id)
                            if store_item:
                                store_item.is_active = False
                        db.session.delete(item)

                # Sync to store
                _sync_rent_items_to_store(block_settings, admin_id, block)

                if mid_period_locked and block == settings_block:
                    flash("Some changes are locked because students have already paid rent this period. "
                          "Item type, use limits, and hall pass counts will apply next period.", "warning")

        # Snapshot current settings + items into a new immutable policy version
        db.session.flush()  # ensure all items are persisted before snapshotting
        from app.services.obligations_service import create_and_schedule_rent_policy_version
        for block in blocks_to_update:
            scope_for_block = require_admin_feature_scope('rent', admin_id=admin_id, requested_block=block, allow_default=False)
            create_and_schedule_rent_policy_version(scope_for_block['class_id'])

        if apply_to_all:
            flash(f"Rent settings applied to all {len(blocks_to_update)} classes!", "success")
        else:
            flash("Rent settings updated successfully!", "success")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block))

    # Get statistics
    total_students = _scoped_students().filter_by(is_rent_enabled=True).count()

    # Get active waivers
    now = utc_now()
    active_waivers = (
        RentWaiver.query
        .join(Student, RentWaiver.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(RentWaiver.waiver_end_date >= now)
        .all()
    )

    # Get all students for waiver form
    all_students = _scoped_students().order_by(Student.first_name).all()

    # Build class_labels_by_block dictionary
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, teacher_blocks)

    # Build join_codes_by_block dictionary
    join_codes_by_block = _get_join_codes_by_block(admin_id, teacher_blocks)

    # Calculate payroll warning
    payroll_warning = None
    if settings and settings.is_enabled and settings.rent_amount > Decimal('0') and payroll_settings:
        # Calculate rent per month based on frequency
        rent_per_month = settings.rent_amount
        thirty_days = Decimal('30')
        four_weeks = Decimal('4')
        if settings.frequency_type == 'daily':
            rent_per_month = settings.rent_amount * thirty_days
        elif settings.frequency_type == 'weekly':
            rent_per_month = settings.rent_amount * four_weeks
        elif settings.frequency_type == 'custom':
            if settings.custom_frequency_unit == 'days':
                rent_per_month = settings.rent_amount * (
                    thirty_days / Decimal(str(settings.custom_frequency_value))
                )
            elif settings.custom_frequency_unit == 'weeks':
                rent_per_month = settings.rent_amount * (
                    thirty_days / (Decimal(str(settings.custom_frequency_value)) * Decimal('7'))
                )
            elif settings.custom_frequency_unit == 'months':
                rent_per_month = settings.rent_amount / Decimal(str(settings.custom_frequency_value))

        # Using simple mode settings if available
        pay_per_minute = Decimal(str(payroll_settings.pay_rate))
        estimated_monthly_payroll = pay_per_minute * 60 * 6 * 20  # 6 hours/day * 20 days

        if rent_per_month > estimated_monthly_payroll * Decimal('0.8'):  # If rent is more than 80% of payroll
            payroll_warning = f"Rent (${rent_per_month:.2f}/month) exceeds recommended 80% of estimated monthly payroll (${estimated_monthly_payroll:.2f}). Students may struggle to afford rent."

    # Get rent items for this setting
    rent_items = []
    if settings:
        from app.models import RentItem
        rent_items = RentItem.query.filter_by(rent_setting_id=settings.id).order_by(RentItem.order_index).all()

    # Calculate rent active status, backlog buckets, and logs
    rent_active_for_period = False
    rent_status_counts = {
        'current': 0,
        'behind_1': 0,
        'behind_2': 0,
        'behind_3_plus': 0,
    }
    rent_status_total = 0
    unpaid_rent_log = []
    payment_log = []
    current_period_start = None
    current_period_end = None
    next_due_date = None

    if settings and settings.is_enabled:
        now_utc = utc_now()
        from app.routes.student import (
            _build_rent_coverage_context,
            _calculate_rent_coverage_due_date,
            _calculate_rent_deadlines,
            _calculate_upcoming_rent_due_date,
            _get_rent_period_delta,
            _is_student_coverage_period_paid,
        )

        # Current selected-class period card data
        selected_coverage_due = _calculate_rent_coverage_due_date(settings, now_utc)
        selected_due_date, _ = _calculate_rent_deadlines(settings, now_utc)
        selected_next_due = _calculate_upcoming_rent_due_date(settings, selected_due_date, selected_coverage_due)
        if selected_coverage_due and selected_next_due:
            current_period_start = selected_coverage_due + timedelta(days=1)
            current_period_end = selected_next_due
            next_due_date = selected_next_due

        # Build class/join_code map for this teacher using ClassEconomy + Seat
        ce_rows = ClassEconomy.query.filter_by(teacher_id=admin_id).all()
        classes_by_join_code = {}
        for ce in ce_rows:
            block_name = (ce.section or '').strip().upper()
            join_code = (ce.join_code or '').strip()
            if not join_code:
                continue
            claimed_student_ids = {
                s_id for (s_id,) in db.session.query(Seat.student_id).filter(
                    Seat.class_id == ce.class_id,
                    Seat.claimed_at.isnot(None),
                    Seat.student_id.isnot(None),
                ).all()
            }
            if not claimed_student_ids:
                continue
            classes_by_join_code[join_code] = {
                'block': block_name,
                'join_code': join_code,
                'class_id': ce.class_id,
                'class_label': ce.display_name or join_code,
                'student_ids': claimed_student_ids,
            }

        for class_info in classes_by_join_code.values():
            block_name = class_info['block']
            join_code = class_info['join_code']
            class_id = class_info['class_id']
            class_label = class_info['class_label']
            student_ids = list(class_info['student_ids'])

            if not student_ids:
                continue

            block_settings = RentSettings.query.filter_by(class_id=class_id, block=block_name).first()
            if not block_settings or not block_settings.is_enabled:
                continue

            coverage_due_date = _calculate_rent_coverage_due_date(block_settings, now_utc)
            if not coverage_due_date or now_utc < coverage_due_date:
                continue

            rent_active_for_period = True
            period_delta = _get_rent_period_delta(block_settings)
            first_due = ensure_utc(block_settings.first_rent_due_date) if block_settings.first_rent_due_date else None
            class_students = Student.query.filter(
                Student.id.in_(student_ids),
                Student.is_rent_enabled == True
            ).order_by(Student.first_name).all()
            class_student_ids = [student.id for student in class_students]
            class_seat_rows = (
                db.session.query(Seat.id, Seat.student_id)
                .filter(
                    Seat.class_id == class_id,
                    Seat.student_id.in_(class_student_ids),
                )
                .all()
            )
            seat_id_by_student = {student_id: seat_id for seat_id, student_id in class_seat_rows}
            class_seat_ids = [seat_id for seat_id, _student_id in class_seat_rows]
            coverage_context_cache = {}

            for student in class_students:
                unpaid_due_dates = []
                cursor = coverage_due_date
                seat_id = seat_id_by_student.get(student.id)
                for _ in range(24):
                    if first_due and cursor < first_due:
                        break
                    cursor_key = ensure_utc(cursor).isoformat()
                    if cursor_key not in coverage_context_cache:
                        coverage_context_cache[cursor_key] = _build_rent_coverage_context(
                            block_settings,
                            class_id=class_id,
                            seat_ids=class_seat_ids,
                            coverage_due_date=cursor,
                            include_waivers=True,
                        )
                    is_paid = _is_student_coverage_period_paid(
                        block_settings,
                        seat_id,
                        class_id,
                        cursor,
                        coverage_context=coverage_context_cache.get(cursor_key),
                    )
                    if is_paid:
                        break
                    unpaid_due_dates.append(cursor)
                    cursor = cursor - period_delta

                months_behind = len(unpaid_due_dates)
                rent_status_total += 1
                if months_behind <= 0:
                    rent_status_counts['current'] += 1
                elif months_behind == 1:
                    rent_status_counts['behind_1'] += 1
                elif months_behind == 2:
                    rent_status_counts['behind_2'] += 1
                else:
                    rent_status_counts['behind_3_plus'] += 1

                if months_behind > 0:
                    unpaid_month_labels = [(d + timedelta(days=1)).strftime('%b %Y') for d in unpaid_due_dates]
                    item = {
                        'student': student,
                        'join_code': join_code,
                        'class_label': class_label,
                        'block': block_name,
                        'months_behind': months_behind,
                        'unpaid_months': unpaid_month_labels,
                        'unpaid_due_dates': list(unpaid_due_dates),
                    }
                    unpaid_rent_log.append(item)

        payment_query = (
            RentPayment.query
            .join(Student, RentPayment.student_id == Student.id)
            .filter(Student.id.in_(sa.select(student_ids_subq)))
            .filter(RentPayment.class_id.in_([info['class_id'] for info in classes_by_join_code.values() if info.get('class_id')]))
            .order_by(RentPayment.payment_date.desc())
            .limit(200)
        )
        class_label_by_join = {
            info['join_code']: info['class_label']
            for info in classes_by_join_code.values()
        }
        block_by_join = {
            info['join_code']: info['block']
            for info in classes_by_join_code.values()
        }
        for payment in payment_query.all():
            payment_join = (payment.join_code or '').strip()
            payment_block = block_by_join.get(payment_join, payment.period)
            coverage_label = "Unknown"
            if payment.coverage_year and payment.coverage_month:
                coverage_label = datetime(
                    payment.coverage_year, payment.coverage_month, 1
                ).strftime('%b %Y')
            payment_log.append({
                'student': payment.student,
                'join_code': payment_join,
                'class_label': class_label_by_join.get(payment_join, payment.period),
                'block': payment_block,
                'coverage_label': coverage_label,
                'amount_paid': payment.amount_paid,
                'payment_date': payment.payment_date,
            })

    student_past_due_json = {}
    current_coverage_due_date = None
    upcoming_coverage_due_date = None
    if settings and settings.is_enabled:
        now_for_waiver = utc_now()
        from app.routes.student import (
            _calculate_rent_coverage_due_date as _crd,
            _calculate_upcoming_rent_due_date as _curd,
            _calculate_rent_deadlines as _crdeadlines,
        )
        current_coverage_due_date = _crd(settings, now_for_waiver)
        _cur_due, _ = _crdeadlines(settings, now_for_waiver)
        upcoming_coverage_due_date = _curd(settings, _cur_due, current_coverage_due_date)

    waiver_join_code = session.get('current_join_code')
    for log_item in unpaid_rent_log:
        if log_item.get('join_code') != waiver_join_code:
            continue
        sid = str(log_item['student'].id)
        dates = log_item.get('unpaid_due_dates', [])
        labels = log_item.get('unpaid_months', [])
        student_past_due_json.setdefault(sid, [])
        for due_date, label in zip(dates, labels):
            student_past_due_json[sid].append({
                'label': label,
                'date_iso': due_date.isoformat(),
            })

    # Determine period label based on frequency type
    period_label = "Month"  # Default
    if settings and settings.is_enabled:
        if settings.frequency_type == 'daily':
            period_label = "Day"
        elif settings.frequency_type == 'weekly':
            period_label = "Week"
        elif settings.frequency_type == 'monthly':
            period_label = "Month"
        elif settings.frequency_type == 'custom':
            # For custom, use the unit specified
            unit = settings.custom_frequency_unit
            if unit == 'days':
                if settings.custom_frequency_value == 1:
                    period_label = "Day"
                else:
                    period_label = f"{settings.custom_frequency_value} Days"
            elif unit == 'weeks':
                if settings.custom_frequency_value == 1:
                    period_label = "Week"
                else:
                    period_label = f"{settings.custom_frequency_value} Weeks"
            elif unit == 'months':
                if settings.custom_frequency_value == 1:
                    period_label = "Month"
                else:
                    period_label = f"{settings.custom_frequency_value} Months"

    return render_template('admin_rent_settings.html',
                          settings=settings,
                          total_students=total_students,
                          active_waivers=active_waivers,
                          all_students=all_students,
                          payroll_warning=payroll_warning,
                          payroll_settings=payroll_settings,
                          settings_block=settings_block,
                          teacher_blocks=teacher_blocks,
                          class_labels_by_block=class_labels_by_block,
                          join_codes_by_block=join_codes_by_block,
                          rent_items=rent_items,
                          rent_active_for_period=rent_active_for_period,
                          period_label=period_label,
                          rent_status_counts=rent_status_counts,
                          rent_status_total=rent_status_total,
                          payment_log=payment_log,
                          unpaid_rent_log=unpaid_rent_log,
                          current_period_start=current_period_start,
                          current_period_end=current_period_end,
                          next_due_date=next_due_date,
                          student_past_due_json=student_past_due_json,
                          current_coverage_due_date=current_coverage_due_date,
                          upcoming_coverage_due_date=upcoming_coverage_due_date,
                          selected_feature_scope=selected_scope)


@admin_bp.route('/rent-waiver/add', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def add_rent_waiver():
    """Add rent waiver for selected students."""
    from app.routes.student import (
        _add_rent_period,
        _calculate_rent_coverage_due_date,
        _calculate_rent_deadlines,
        _calculate_upcoming_rent_due_date,
        _get_rent_period_delta,
    )

    student_ids = request.form.getlist('student_ids')
    waiver_scopes = request.form.getlist('waiver_scope')
    past_due_dates_iso = request.form.getlist('past_due_dates')
    future_periods_count = 1
    if 'future' in waiver_scopes:
        raw_future_periods = request.form.get('future_periods_count', '') or ''
        try:
            future_periods_count = max(1, int(raw_future_periods))
        except ValueError:
            flash("Future periods count must be a positive whole number.", "danger")
            return redirect(url_for('admin.rent_settings'))
    reason = request.form.get('reason', '')
    settings_block = request.form.get('settings_block', '')

    if not student_ids:
        flash("Please select at least one student.", "danger")
        return redirect(url_for('admin.rent_settings'))

    if not waiver_scopes:
        flash("Please select at least one waiver scope (past due, current, or future).", "danger")
        return redirect(url_for('admin.rent_settings'))

    admin_id = session.get("admin_id")
    join_code = session.get('current_join_code')
    if not join_code:
        flash(
            "Unable to resolve the class join code for this waiver. Please select a class/block and try again.",
            "danger",
        )
        return redirect(url_for('admin.rent_settings'))

    class_id = session.get('current_class_id')
    if not class_id and join_code:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = class_row.class_id if class_row else None
    settings = (
        RentSettings.query.filter_by(class_id=class_id, block=settings_block).first()
        if class_id and settings_block
        else None
    )
    if not settings:
        flash("Rent settings not configured.", "danger")
        return redirect(url_for('admin.rent_settings'))

    now = utc_now()
    period_delta = _get_rent_period_delta(settings)
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    current_due, _ = _calculate_rent_deadlines(settings, now)
    upcoming_due_date = _calculate_upcoming_rent_due_date(settings, current_due, coverage_due_date)

    waiver_windows = []
    past_due_window_count = 0

    if 'past_due' in waiver_scopes:
        for iso_str in past_due_dates_iso:
            try:
                dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = ensure_utc(dt)
                waiver_windows.append((dt, dt, 1))
                past_due_window_count += 1
            except (ValueError, AttributeError):
                continue

    if 'current' in waiver_scopes and coverage_due_date:
        waiver_windows.append((coverage_due_date, coverage_due_date, 1))

    if 'future' in waiver_scopes and upcoming_due_date:
        future_end = upcoming_due_date
        for _ in range(future_periods_count - 1):
            future_end = _add_rent_period(future_end, period_delta)
        waiver_windows.append((upcoming_due_date, future_end, future_periods_count))

    if not waiver_windows:
        flash("No valid waiver periods could be determined. Check that rent is configured and a scope was selected.", "danger")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block))

    scope_labels = []
    if 'past_due' in waiver_scopes:
        scope_labels.append(f"{past_due_window_count} past-due period(s)")
    if 'current' in waiver_scopes:
        scope_labels.append("current period")
    if 'future' in waiver_scopes:
        scope_labels.append(f"{future_periods_count} future period(s)")
    scope_str = ", ".join(scope_labels) or "selected periods"

    count = 0
    for student_id in student_ids:
        student = _get_student_or_404(int(student_id))
        seat_id = get_seat_id_for_class(student.id, class_id) if class_id else None
        for waiver_start, waiver_end, periods_count in waiver_windows:
            obligations_service.record_rent_waiver(
                seat_id=seat_id or 0,
                class_id=class_id or "",
                waiver_start_date=waiver_start,
                waiver_end_date=waiver_end,
                periods_count=periods_count,
                reason=reason,
                created_by_user_id=admin_id,
            )
        description = f"Rent waiver added for {student.full_name} covering: {scope_str}."
        if reason:
            description = f"{description} Reason: {reason}"
        db.session.add(AnalyticsEvent(
            teacher_id=admin_id,
            join_code=join_code,
            event_type='rent_waiver',
            event_date=now,
            description=description[:255],
            created_by_admin=True,
        ))
        count += 1

    flash(f"Rent waiver added for {count} student(s) covering: {scope_str}.", "success")
    return redirect(url_for('admin.rent_settings', settings_block=settings_block))


@admin_bp.route('/rent-waiver/<int:waiver_id>/remove', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def remove_rent_waiver(waiver_id):
    """Remove a rent waiver."""
    waiver = db.get_or_404(RentWaiver, waiver_id)
    _get_student_or_404(waiver.student_id)
    student_name = waiver.student.full_name
    admin_id = session.get("admin_id")
    join_code = waiver.join_code or session.get('current_join_code')
    db.session.delete(waiver)
    if admin_id and join_code:
        removal_description = (f"Rent waiver removed for {student_name}.")[:255]
        db.session.add(AnalyticsEvent(
            teacher_id=admin_id,
            join_code=join_code,
            event_type='rent_waiver',
            event_date=utc_now(),
            description=removal_description,
            created_by_admin=True,
        ))
    flash(f"Rent waiver removed for {student_name}.", "success")
    return redirect(url_for('admin.rent_settings'))


@admin_bp.route('/rent/reverse-cycle-penalties', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def reverse_cycle_penalties():
    """Reverse misapplied rent late fees for the current cycle."""
    from app.routes.student import (
        RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
        _calculate_rent_coverage_due_date,
        _calculate_rent_timeline,
        _get_locked_rent_amount_for_join_code_cycle,
    )

    admin_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    settings_block = request.form.get('settings_block') or request.args.get('settings_block')

    if not join_code:
        flash("No class period selected. Please select a class first.", "error")
        return redirect(url_for('admin.rent_settings'))

    class_row_for_rent = ClassEconomy.query.filter_by(
        teacher_id=admin_id,
        join_code=join_code,
    ).first()
    if not class_row_for_rent:
        flash("Could not find a class matching the current session.", "error")
        return redirect(url_for('admin.rent_settings'))

    block = class_row_for_rent.section
    rent_settings = RentSettings.query.filter_by(
        class_id=class_row_for_rent.class_id,
        block=block,
    ).first()
    if not rent_settings or not rent_settings.is_enabled:
        flash("Rent system is not enabled for this class.", "info")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block or block))

    now = utc_now()
    timeline = _calculate_rent_timeline(rent_settings, now)
    coverage_due_date = timeline.get('coverage_due_date')
    if not coverage_due_date:
        flash("No active coverage period found for this class.", "info")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block or block))

    locked_rate = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due_date)
    if locked_rate is None:
        flash("No valid payments found for the current cycle — nothing to reverse.", "info")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block or block))

    grace_end_date = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    cycle_payments = RentPayment.query.filter(
        RentPayment.class_id == class_row_for_rent.class_id,
        RentPayment.coverage_month == coverage_due_date.month,
        RentPayment.coverage_year == coverage_due_date.year,
    ).order_by(RentPayment.seat_id, RentPayment.payment_date).all()

    payments_by_seat = defaultdict(list)
    for payment in cycle_payments:
        txn = Transaction.query.filter(
            Transaction.seat_id == payment.seat_id,
            Transaction.class_id == payment.class_id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.amount == -payment.amount_paid,
        ).first()

        if txn and not txn.is_void:
            payments_by_seat[payment.seat_id].append(payment)

    students_fixed = 0
    total_refunded = Decimal('0.00')

    for seat_id, payments in payments_by_seat.items():
        paid_by_grace = sum(
            payment.amount_paid for payment in payments
            if payment.payment_date and ensure_utc(payment.payment_date) <= ensure_utc(grace_end_date)
        )
        total_late_fee_charged = sum(payment.late_fee_charged or Decimal('0.00') for payment in payments)
        if total_late_fee_charged <= Decimal('0.00'):
            continue

        if paid_by_grace >= locked_rate:
            refund_amount = total_late_fee_charged
            ledger_service.create_pending_transaction(
                seat_id=seat_id,
                class_id=teacher_block.class_id,
                teacher_id=admin_id,
                amount=refund_amount,
                account_type='checking',
                type='Rent Late Fee Reversal',
                description=(
                    f'Late fee reversal: rate was raised mid-cycle for '
                    f'{coverage_due_date.strftime("%B %Y")} (locked at ${locked_rate:.2f})'
                ),
            )

            for payment in payments:
                if payment.late_fee_charged and payment.late_fee_charged > Decimal('0.00'):
                    payment.late_fee_charged = Decimal('0.00')
                    payment.was_late = False

            students_fixed += 1
            total_refunded += refund_amount

    if students_fixed:
        flash(
            f"Reversed misapplied late fees for {students_fixed} student(s). Total refunded: ${total_refunded:.2f}.",
            "success",
        )
    else:
        flash(
            "No misapplied penalties found for the current cycle at the locked rate "
            f"(${locked_rate:.2f}). Students who were genuinely late keep their fees.",
            "info",
        )

    return redirect(url_for('admin.rent_settings', settings_block=settings_block or block))


# -------------------- INSURANCE MANAGEMENT --------------------


def _get_tier_namespace_seed(teacher_id):
    """Return a stable seed for tenant-scoped tier IDs using the teacher's join code."""
    join_code_row = (
        db.session.query(ClassEconomy.join_code)
        .filter_by(teacher_id=teacher_id)
        .order_by(ClassEconomy.join_code)
        .first()
    )

    return join_code_row[0] if join_code_row else f"teacher-{teacher_id}"


def _generate_tenant_scoped_tier_id(seed, sequence):
    """Create a globally unique tier ID by hashing the teacher join code with a sequence."""
    digest = hashlib.blake2b(f"{seed}:{sequence}".encode(), digest_size=8).digest()
    candidate = int.from_bytes(digest, byteorder='big') % 2_000_000_000
    return candidate or sequence


def _next_tenant_scoped_tier_id(seed, existing_ids):
    """Return the next available tier ID that won't collide across teachers."""
    sequence = len(existing_ids) + 1
    candidate = _generate_tenant_scoped_tier_id(seed, sequence)

    while candidate in existing_ids:
        sequence += 1
        candidate = _generate_tenant_scoped_tier_id(seed, sequence)

    return candidate


@admin_bp.route('/insurance', methods=['GET', 'POST'])
@admin_required
def insurance_management():
    """Main insurance management dashboard."""
    admin_id = session.get('admin_id')
    form = InsurancePolicyForm()
    class_context = _resolve_admin_class_context(admin_id)
    if not class_context:
        flash("Select a class from the sidebar before managing insurance.", "warning")
        return redirect(url_for('admin.dashboard'))
    selected_class_id = class_context['class_id']
    selected_join_code = class_context['join_code']
    selected_scope = resolve_feature_class_for_class(selected_class_id, 'insurance')
    if not selected_scope or not selected_scope.get('enabled'):
        abort(404)
    insurance_class_row = (
        ClassEconomy.query
        .filter_by(
            teacher_id=admin_id,
            join_code=selected_join_code,
        )
        .first()
    )
    settings_block = insurance_class_row.section if insurance_class_row else None
    active_class_label = (insurance_class_row.display_name or selected_join_code) if insurance_class_row else selected_join_code

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # V2 class-authoritative scoping: all policy reads are bounded by canonical class_id.
    existing_policies = InsurancePolicy.query.filter_by(class_id=selected_class_id).all()

    # Collect existing tier groups for the current teacher
    tier_groups_map = {}
    for policy in existing_policies:
        if policy.tier_category_id:
            category_id = policy.tier_category_id
            if category_id not in tier_groups_map:
                tier_groups_map[category_id] = {
                    'id': category_id,
                    'name': policy.tier_name or f"Group {category_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups_map[category_id]['policies'].append({
                'title': policy.title,
                'level': policy.tier_level
            })

    tier_groups = sorted(tier_groups_map.values(), key=lambda g: g['id'])
    tier_namespace_seed = _get_tier_namespace_seed(admin_id)
    existing_tier_ids = set(tier_groups_map.keys())
    next_tier_category_id = _next_tenant_scoped_tier_id(tier_namespace_seed, existing_tier_ids)

    if request.method == 'POST' and form.validate_on_submit():
        # Generate unique policy code
        policy_code = secrets.token_urlsafe(12)[:16]
        while InsurancePolicy.query.filter_by(policy_code=policy_code).first():
            policy_code = secrets.token_urlsafe(12)[:16]

        tier_category_id = None
        if form.tier_category_id.data:
            tier_category_id = form.tier_category_id.data
        elif form.tier_name.data or form.tier_color.data:
            tier_category_id = next_tier_category_id

        # Create new insurance policy
        policy = InsurancePolicy(
            policy_code=policy_code,
            teacher_id=session.get('admin_id'),
            class_id=selected_class_id,
            settings_mode=request.form.get('settings_mode', 'advanced'),
        )
        _populate_policy_from_form(policy, form, next_tier_category_id=tier_category_id)
        db.session.add(policy)
        db.session.flush()  # Get the ID for the policy before adding blocks
        db.session.flush()
        flash(f"Insurance policy '{policy.title}' created successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get policies for current teacher only
    policies = existing_policies

    # V2 class-authoritative scoping: _scoped_students() is already bounded by active class_id.
    students_in_scope = _scoped_students().all()
    student_ids_in_scope = [s.id for s in students_in_scope]

    # Get student enrollments for selected block
    # CRITICAL: Filter by join_code for proper multi-tenancy scoping
    active_enrollments = []
    cancelled_enrollments = []
    claims = []
    pending_claims_count = 0

    if student_ids_in_scope and selected_join_code:
        # Filter enrollments by join_code to ensure proper class isolation
        active_enrollments = (
            StudentInsurance.query
            .join(Student, StudentInsurance.student_id == Student.id)
            .filter(Student.id.in_(student_ids_in_scope))
            .filter(StudentInsurance.join_code == selected_join_code)
            .filter(StudentInsurance.status == 'active')
            .all()
        )
        cancelled_enrollments = (
            StudentInsurance.query
            .join(Student, StudentInsurance.student_id == Student.id)
            .filter(Student.id.in_(student_ids_in_scope))
            .filter(StudentInsurance.join_code == selected_join_code)
            .filter(StudentInsurance.status == 'cancelled')
            .all()
        )

        # Get claims for selected block, filtered by join_code for proper multi-tenancy isolation
        claims = (
            InsuranceClaim.query
            .join(StudentInsurance, InsuranceClaim.enrollment_id == StudentInsurance.id)
            .filter(StudentInsurance.student_id.in_(student_ids_in_scope))
            .filter(StudentInsurance.join_code == selected_join_code)
            .order_by(InsuranceClaim.filed_date.desc())
            .all()
        )
        pending_claims_count = (
            InsuranceClaim.query
            .join(StudentInsurance, InsuranceClaim.enrollment_id == StudentInsurance.id)
            .filter(StudentInsurance.student_id.in_(student_ids_in_scope))
            .filter(StudentInsurance.join_code == selected_join_code)
            .filter(InsuranceClaim.status == 'pending')
            .count()
        )

    policy_enrollment_counts = {}
    for enrollment in active_enrollments:
        policy_enrollment_counts[enrollment.policy_id] = (
            policy_enrollment_counts.get(enrollment.policy_id, 0) + 1
        )

    policy_pending_claim_counts = {}
    for claim in claims:
        if claim.status != 'pending':
            continue
        policy_pending_claim_counts[claim.policy_id] = (
            policy_pending_claim_counts.get(claim.policy_id, 0) + 1
        )

    insurance_recommendation = _build_insurance_recommendation_context(
        admin_id,
        block=settings_block,
        charge_frequency=form.charge_frequency.data or 'monthly',
    )

    return render_template('admin_insurance.html',
                          form=form,
                          policies=policies,
                          active_enrollments=active_enrollments,
                          cancelled_enrollments=cancelled_enrollments,
                          claims=claims,
                          pending_claims_count=pending_claims_count,
                          policy_enrollment_counts=policy_enrollment_counts,
                          policy_pending_claim_counts=policy_pending_claim_counts,
                          tier_groups=tier_groups,
                          next_tier_category_id=next_tier_category_id,
                          settings_block=settings_block,
                          active_class_label=active_class_label,
                          active_join_code=selected_join_code,
                          insurance_recommendation=insurance_recommendation,
                          selected_feature_scope=selected_scope)


@admin_bp.route('/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def edit_insurance_policy(policy_id):
    """Edit existing insurance policy."""
    policy = db.get_or_404(InsurancePolicy, policy_id)

    # Verify this policy belongs to a class currently owned by the current teacher.
    class_owned = ClassEconomy.query.filter_by(
        class_id=policy.class_id,
        teacher_id=session.get('admin_id'),
    ).first()
    if not class_owned:
        abort(403)

    form = InsurancePolicyForm(obj=policy)

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Pre-populate selected blocks on GET request (using many-to-many relationship)
    if request.method == 'GET':
        form.blocks.data = policy.blocks_list

    teacher_policies = InsurancePolicy.query.filter_by(class_id=policy.class_id).all()
    tier_groups_map = {}
    for teacher_policy in teacher_policies:
        if teacher_policy.tier_category_id:
            category_id = teacher_policy.tier_category_id
            if category_id not in tier_groups_map:
                tier_groups_map[category_id] = {
                    'id': category_id,
                    'name': teacher_policy.tier_name or f"Group {category_id}",
                    'color': teacher_policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups_map[category_id]['policies'].append({
                'title': teacher_policy.title,
                'level': teacher_policy.tier_level
            })

    tier_groups = sorted(tier_groups_map.values(), key=lambda g: g['id'])
    tier_namespace_seed = _get_tier_namespace_seed(policy.teacher_id)
    existing_tier_ids = set(tier_groups_map.keys())
    next_tier_category_id = _next_tenant_scoped_tier_id(tier_namespace_seed, existing_tier_ids)

    if request.method == 'POST' and form.validate_on_submit():
        _populate_policy_from_form(policy, form, next_tier_category_id=next_tier_category_id)

        db.session.flush()
        flash(f"Insurance policy '{policy.title}' updated successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get other active policies for bundle selection (excluding current policy)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.class_id == policy.class_id,
        InsurancePolicy.id != policy_id
    ).all()

    recommendation_block = policy.blocks_list[0] if policy.blocks_list else None
    payroll_settings = _resolve_admin_payroll_settings_for_block(session.get('admin_id'), recommendation_block)
    insurance_recommendation = _build_insurance_recommendation_context(
        session.get('admin_id'),
        block=recommendation_block,
        charge_frequency=policy.charge_frequency or 'monthly',
    )

    return render_template(
        'admin_edit_insurance_policy.html',
        form=form,
        policy=policy,
        available_policies=available_policies,
        tier_groups=tier_groups,
        next_tier_category_id=next_tier_category_id,
        payroll_settings=payroll_settings,
        insurance_recommendation=insurance_recommendation,
    )


@admin_bp.route('/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy."""
    policy = db.get_or_404(InsurancePolicy, policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    policy.is_active = False
    flash(f"Insurance policy '{policy.title}' has been deactivated.", "success")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/delete/<int:policy_id>', methods=['POST'])
@admin_required
def delete_insurance_policy(policy_id):
    """Delete an insurance policy and all associated data.

    Since each teacher has their own policy instances (identified by policy_code),
    this safely deletes only the current teacher's policy data without affecting
    other teachers.
    """
    policy = db.get_or_404(InsurancePolicy, policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    force_delete = request.form.get('force_delete') == 'true'

    student_ids_subq = _student_scope_subquery()

    # Check for active enrollments within scope
    active_enrollments = StudentInsurance.query.filter(
        StudentInsurance.policy_id == policy_id,
        StudentInsurance.status == 'active',
        StudentInsurance.student_id.in_(sa.select(student_ids_subq)),
    ).count()

    # Check for pending claims within scope
    pending_claims = (
        InsuranceClaim.query
        .join(Seat, InsuranceClaim.seat_id == Seat.id)
        .filter(
            InsuranceClaim.policy_id == policy_id,
            InsuranceClaim.status == 'pending',
            Seat.student_id.in_(sa.select(student_ids_subq)),
        ).count()
    )

    if not force_delete and (active_enrollments > 0 or pending_claims > 0):
        flash(f"Cannot delete policy '{policy.title}': {active_enrollments} active enrollments and {pending_claims} pending claims. Cancel all enrollments first or use force delete.", "danger")
        return redirect(url_for('admin.insurance_management'))

    try:
        # Cancel active enrollments if force delete
        if force_delete and active_enrollments > 0:
            cancelled_count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.status == 'active',
                StudentInsurance.student_id.in_(sa.select(student_ids_subq)),
            ).update({'status': 'cancelled'}, synchronize_session=False)
            flash(f"Cancelled {cancelled_count} active enrollments.", "info")

        # Delete all claims for this policy
        claim_ids_to_delete = [
            c.id for c in InsuranceClaim.query
            .join(Seat, InsuranceClaim.seat_id == Seat.id)
            .filter(
                InsuranceClaim.policy_id == policy_id,
                Seat.student_id.in_(sa.select(student_ids_subq)),
            ).all()
        ]
        claims_deleted = InsuranceClaim.query.filter(InsuranceClaim.id.in_(claim_ids_to_delete)).delete(synchronize_session=False) if claim_ids_to_delete else 0

        # Delete all enrollments for this policy (legacy + canonical)
        enrollments_deleted = StudentInsurance.query.filter(
            StudentInsurance.policy_id == policy_id,
            StudentInsurance.student_id.in_(sa.select(student_ids_subq)),
        ).delete(synchronize_session=False)
        InsuranceEnrollment.query.filter(
            InsuranceEnrollment.policy_id == policy_id,
        ).delete(synchronize_session=False)

        # Delete the policy itself
        db.session.delete(policy)
        db.session.flush()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting policy {policy_id}", exc_info=True)
        flash(f"Cannot delete insurance policy due to internal error", "danger")

    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/mass-remove/<int:policy_id>', methods=['POST'])
@admin_required
def mass_remove_policy(policy_id):
    """Cancel insurance policy for multiple or all students."""
    policy = db.get_or_404(InsurancePolicy, policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    # Get list of student IDs to remove (or 'all')
    student_ids_raw = request.form.get('student_ids', 'all')

    # Get scoped student IDs subquery
    student_ids_subq = _student_scope_subquery()

    if student_ids_raw == 'all':
        # Cancel for all active students in scope
        count = StudentInsurance.query.filter(
            StudentInsurance.policy_id == policy_id,
            StudentInsurance.status == 'active',
            StudentInsurance.student_id.in_(sa.select(student_ids_subq))
        ).update({'status': 'cancelled'}, synchronize_session=False)
    else:
        # Cancel for specific students
        try:
            student_ids = [int(sid.strip()) for sid in student_ids_raw.split(',') if sid.strip()]
            count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.student_id.in_(student_ids),
                StudentInsurance.student_id.in_(sa.select(student_ids_subq)),
                StudentInsurance.status == 'active'
            ).update({'status': 'cancelled'}, synchronize_session=False)
        except ValueError:
            flash("Invalid student IDs provided.", "danger")
            return redirect(url_for('admin.insurance_management'))

    db.session.flush()

    if student_ids_raw == 'all':
        flash(f"Cancelled policy '{policy.title}' for {count} students.", "success")
    else:
        flash(f"Cancelled policy '{policy.title}' for {count} selected students.", "success")

    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/student-policy/<int:enrollment_id>')
@admin_required
def view_student_policy(enrollment_id):
    """View student's policy enrollment details and claims history."""
    enrollment = (
        StudentInsurance.query
        .join(Student, StudentInsurance.student_id == Student.id)
        .filter(StudentInsurance.id == enrollment_id)
        .filter(Student.id.in_(sa.select(_student_scope_subquery())))
        .first_or_404()
    )

    # Get claims for this enrollment
    claims = InsuranceClaim.query.filter_by(enrollment_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    # Get join_code for the student's block
    admin_id = session.get("admin_id")
    student = enrollment.student
    join_codes_by_block = _get_join_codes_by_block(admin_id, [student.block] if student.block else [])
    join_code = join_codes_by_block.get(student.block, '')

    return render_template('admin_view_student_policy.html',
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          student=student,
                          join_code=join_code,
                          claims=claims)


@admin_bp.route('/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def process_claim(claim_id):
    """Process insurance claim with auto-deposit for monetary claims."""
    claim = db.session.get(InsuranceClaim, claim_id)
    if claim is None:
        abort(404)

    enrollment = db.session.get(InsuranceEnrollment, claim.enrollment_id)
    if enrollment is None:
        enrollment = db.session.get(StudentInsurance, claim.enrollment_id)
    if enrollment is None:
        abort(404)

    try:
        scope = resolve_scope(
            actor=get_current_admin(),
            selected_join_code=enrollment.join_code or claim.join_code or session.get("current_join_code"),
            actor_role="teacher",
        )
        access_policy_service.assert_can_process_claim(
            scope=scope,
            enrollment=enrollment,
            claim=claim,
        )
    except (AccessScopeDenied, access_policy_service.AccessPolicyDenied):
        abort(403)

    form = AdminClaimProcessForm(obj=claim)

    claim_type = resolve_claim_type(
        claim=claim,
        policy_claim_type=getattr(enrollment.policy, "claim_type", None),
    )
    max_claim_amount = enrollment.contract_max_claim_amount
    max_payout_per_period = enrollment.contract_max_payout_per_period
    max_claims_count = enrollment.contract_max_claims_count
    max_claims_period = (enrollment.contract_max_claims_period or 'month').lower()
    claim_time_limit_days = enrollment.contract_claim_time_limit_days

    period_start, period_end = claim_period_bounds_utc(max_claims_period)
    period_start_db = normalize_for_db(period_start)
    period_end_db = normalize_for_db(period_end)

    def _claim_base_amount(target_claim):
        if claim_type == 'transaction_monetary' and target_claim.transaction:
            return abs(target_claim.transaction.amount)
        return target_claim.claim_amount or Decimal('0.00')

    # Validate claim
    validation_errors = []

    # Canonical waiting-period gate:
    # 00:00 next class-local day after purchase through 00:00 after day N.
    now_utc = utc_now()
    waiting_end_class = compute_waiting_end_class_for_enrollment(
        enrollment,
        fallback_purchase_utc=claim.transaction.timestamp if claim.transaction else claim.incident_date,
        fallback_class_id=getattr(claim.transaction, "class_id", None),
    )
    if waiting_end_class is not None and enrollment.class_id:
        now_class = get_class_now(enrollment.class_id, reference_time_utc=now_utc)
        if now_class < waiting_end_class:
            validation_errors.append("Coverage has not started yet (still in waiting period)")

    # Check if payment is current
    if not enrollment.payment_current:
        validation_errors.append("Premium payments are not current")

    if claim_type == 'transaction_monetary' and not claim.transaction:
        validation_errors.append("Transaction-based claim is missing a linked transaction")
    if claim_type == 'transaction_monetary' and claim.transaction and claim.transaction.is_void:
        validation_errors.append("Linked transaction has been voided and cannot be reimbursed")

    # P0-3 Fix: Validate transaction ownership to prevent cross-student fraud
    if claim_type == 'transaction_monetary' and claim.transaction:
        if claim.transaction.seat_id != claim.seat_id:
            validation_errors.append(
                f"SECURITY: Transaction ownership mismatch. "
                f"Transaction belongs to seat ID {claim.transaction.seat_id}, "
                f"but claim filed by seat ID {claim.seat_id}."
            )
            current_app.logger.error(
                f"SECURITY ALERT: Transaction ownership mismatch in claim {claim.id}. "
                f"Claim seat_id={claim.seat_id}, transaction seat_id={claim.transaction.seat_id}"
            )

    if claim_type == 'transaction_monetary' and claim.transaction_id:
        duplicate_claim = InsuranceClaim.query.filter(
            InsuranceClaim.transaction_id == claim.transaction_id,
            InsuranceClaim.id != claim.id,
        ).first()
        if duplicate_claim:
            validation_errors.append("Another claim is already tied to this transaction")

    if claim_type == 'transaction_monetary' and claim.transaction:
        reason_to_message = {
            CLAIM_REASON_HARD_DENY_CATEGORY: "Linked transaction category is never eligible for reimbursement",
            CLAIM_REASON_INTERNAL_TRANSFER: "Internal transfer transactions are not eligible for reimbursement",
            CLAIM_REASON_DELAY_USE_NOT_USED: "Delay-use purchase has not been used yet",
            CLAIM_REASON_DELAY_USE_EXPIRED: "Delay-use purchase was used after expiration",
            CLAIM_REASON_PREMIUM_NOT_CURRENT: "Premium payments are not current",
            CLAIM_REASON_WAITING_PERIOD: "Coverage waiting period requirements are not satisfied",
            CLAIM_REASON_TIME_LIMIT_EXCEEDED: "Claim is outside the filing time limit",
            CLAIM_REASON_ALREADY_CLAIMED: "Another claim is already tied to this transaction",
            CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS: "A reimbursement already exists for this source transaction/policy",
            CLAIM_REASON_UNCLASSIFIED_TRANSACTION: "Transaction could not be classified as eligible",
        }
        claimed_tx_ids = {
            row[0]
            for row in db.session.query(InsuranceClaim.transaction_id)
            .filter(InsuranceClaim.transaction_id.isnot(None), InsuranceClaim.id != claim.id)
            .all()
            if row[0] is not None
        }
        reimbursed_tx_ids = collect_reimbursed_source_tx_ids(claim.policy_id)
        transaction_eligible, reason_code = evaluate_claim_transaction_eligibility(
            claim.transaction,
            enrollment=enrollment,
            now_utc=now_utc,
            claim_type=claim_type,
            claim_time_limit_days=claim_time_limit_days,
            policy_id=claim.policy_id,
            enrollment_join_code=enrollment.join_code,
            claimed_tx_ids=claimed_tx_ids,
            reimbursed_tx_ids=reimbursed_tx_ids,
        )
        if not transaction_eligible:
            validation_errors.append(reason_to_message.get(reason_code, "Linked transaction is not eligible"))

    incident_reference = claim.transaction.timestamp if claim_type == 'transaction_monetary' and claim.transaction else claim.incident_date
    incident_reference = ensure_utc(incident_reference)
    days_since_incident = (now_utc - incident_reference).days if incident_reference else 0
    if claim_time_limit_days is not None and days_since_incident > claim_time_limit_days:
        validation_errors.append(f"Claim filed too late ({days_since_incident} days after incident, limit is {claim_time_limit_days} days)")

    # Check max claims count
    approved_claims = InsuranceClaim.query.filter(
        InsuranceClaim.enrollment_id == enrollment.id,
        InsuranceClaim.status.in_(['approved', 'paid']),
        InsuranceClaim.processed_date >= period_start_db,
        InsuranceClaim.processed_date < period_end_db,
        InsuranceClaim.id != claim.id,
    )
    if max_claims_count and approved_claims.count() >= max_claims_count:
        validation_errors.append(f"Maximum claims limit reached ({max_claims_count} per {max_claims_period})")

    period_payouts = None
    remaining_period_cap = None
    if max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.enrollment_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start_db,
            InsuranceClaim.processed_date < period_end_db,
            InsuranceClaim.approved_amount.isnot(None),
            InsuranceClaim.id != claim.id,
        ).scalar() or Decimal('0.00')

        requested_amount = _claim_base_amount(claim)
        remaining_period_cap = max(max_payout_per_period - period_payouts, Decimal('0.00'))
        if remaining_period_cap is not None and requested_amount > remaining_period_cap and claim_type != 'non_monetary':
            validation_errors.append(
                f"Maximum payout limit would be exceeded (${period_payouts:.2f} paid + ${requested_amount:.2f} requested > ${max_payout_per_period:.2f} limit per {max_claims_period})"
            )

    # Get claims statistics
    claims_stats = {
        'pending': InsuranceClaim.query.filter_by(enrollment_id=enrollment.id, status='pending').count(),
        'approved': InsuranceClaim.query.filter_by(enrollment_id=enrollment.id, status='approved').count(),
        'rejected': InsuranceClaim.query.filter_by(enrollment_id=enrollment.id, status='rejected').count(),
        'paid': InsuranceClaim.query.filter_by(enrollment_id=enrollment.id, status='paid').count(),
    }

    if request.method == 'POST' and form.validate_on_submit():
        old_status = claim.status
        new_status = form.status.data

        is_monetary_claim = claim_type != 'non_monetary'
        requires_payout = is_monetary_claim and new_status in ('approved', 'paid') and old_status not in ('approved', 'paid')

        if validation_errors and requires_payout:
            flash("Resolve validation errors before approving or paying out this claim.", "danger")
            return redirect(url_for('admin.process_claim', claim_id=claim_id))

        approved_amount = None
        if requires_payout:
            approved_claims_count = approved_claims.count()
            if max_claims_count and approved_claims_count >= max_claims_count:
                flash(f"Cannot approve claim: maximum of {max_claims_count} claims already reached this {max_claims_period}.", "danger")
                db.session.rollback()
                return redirect(url_for('admin.process_claim', claim_id=claim_id))

            base_amount = _claim_base_amount(claim)
            approved_amount = base_amount
            if claim_type == 'legacy_monetary' and form.approved_amount.data is not None:
                approved_amount = Decimal(str(form.approved_amount.data))

            if max_claim_amount:
                approved_amount = min(approved_amount, max_claim_amount)

            if remaining_period_cap is not None:
                if remaining_period_cap <= 0:
                    flash(
                        f"Cannot approve claim: Would exceed maximum payout limit of ${max_payout_per_period:.2f} per {max_claims_period} (${period_payouts:.2f} already paid)",
                        "danger",
                    )
                    db.session.rollback()
                    return redirect(url_for('admin.process_claim', claim_id=claim_id))
                approved_amount = min(approved_amount, remaining_period_cap)
        elif claim_type == 'non_monetary' and new_status == 'approved':
            flash(f"Non-monetary claim approved for {claim.claim_item}. Item/service will be provided offline.", "success")
        elif new_status == 'rejected':
            flash("Claim has been rejected.", "warning")

        try:
            execute_insurance_claim_resolution(
                scope=scope,
                claim=claim,
                enrollment=enrollment,
                new_status=new_status,
                teacher_notes=form.teacher_notes.data,
                rejection_reason=form.rejection_reason.data,
                processed_by_user_id=session.get('admin_id'),
                approved_amount=approved_amount,
            )
            if requires_payout:
                flash(f"Monetary claim approved! ${approved_amount:.2f} deposited to {enrollment.student.full_name}'s checking account.", "success")
        except IntegrityError as exc:
            db.session.rollback()
            if 'uq_insurance_reimbursement_source_policy' in str(exc.orig):
                flash("Reimbursement already exists for this source transaction and policy.", "danger")
            else:
                flash("Could not process the claim due to a concurrent update. Please retry.", "danger")
            return redirect(url_for('admin.process_claim', claim_id=claim_id))
        return redirect(url_for('admin.insurance_management'))

    return render_template('admin_process_claim.html',
                          claim=claim,
                          form=form,
                          enrollment=enrollment,
                          claim_type=claim_type,
                          contract_title=enrollment.contract_title,
                          contract_description=enrollment.contract_description,
                          contract_max_claim_amount=max_claim_amount,
                          contract_max_claims_count=max_claims_count,
                          contract_max_claims_period=max_claims_period,
                          contract_claim_time_limit_days=claim_time_limit_days,
                          contract_max_payout_per_period=max_payout_per_period,
                          validation_errors=validation_errors,
                          claims_stats=claims_stats,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


# -------------------- TRANSACTIONS --------------------

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """Redirect to banking page - transactions now under banking."""
    safe_args = {
        key: value for key, value in request.args.items()
        if key in _BANKING_REDIRECT_QUERY_KEYS
    }
    return redirect(url_for('admin.banking', **safe_args))


@admin_bp.route('/void-transaction/<int:transaction_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def void_transaction(transaction_id):
    """Void a transaction."""
    requested_with = (request.headers.get("X-Requested-With") or "").strip().lower()
    is_json = request.is_json or requested_with == "xmlhttprequest"
    def _safe_referrer_redirect():
        safe_target = _safe_local_redirect_target(request.referrer)
        if safe_target:
            return redirect(safe_target)
        return redirect(url_for('admin.dashboard'))

    def _void_error(message, status_code=400):
        if is_json:
            return jsonify(status="error", message=message), status_code
        flash(message, "error")
        return _safe_referrer_redirect()

    tx = db.session.get(Transaction, transaction_id)
    if tx is None:
        abort(404)

    if tx.is_void:
        return _void_error("Transaction is already voided.")

    try:
        current_admin = get_current_admin()
        scope = resolve_scope(
            actor=current_admin,
            selected_join_code=tx.join_code or session.get("current_join_code"),
            actor_role="teacher",
        )
        access_policy_service.assert_can_void_transaction(scope=scope, transaction=tx)
        execute_void_transaction(tx)
        current_app.logger.info(f"Transaction {transaction_id} voided")
    except (AccessScopeDenied, access_policy_service.AccessPolicyDenied) as e:
        db.session.rollback()
        current_app.logger.info("Transaction void denied for %s: %s", transaction_id, e)
        return _void_error("You do not have permission to void this transaction.", status_code=403)
    except ValueError as e:
        db.session.rollback()
        current_app.logger.info("Transaction void validation failed for %s: %s", transaction_id, e)
        return _void_error(
            _safe_known_message(str(e), _SAFE_VOID_ERROR_MESSAGES, "Transaction could not be voided."),
        )
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to void transaction {transaction_id}: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Failed to void transaction"), 500
        flash("Error voiding transaction.", "error")
        return _safe_referrer_redirect()
    if is_json:
        return jsonify(status="success", message="Transaction voided.")
    flash("Transaction voided.", "success")
    return _safe_referrer_redirect()


# -------------------- HALL PASS MANAGEMENT --------------------

@admin_bp.route('/hall-pass')
@admin_required
def hall_pass():
    """Manage hall pass requests and active passes."""
    admin_id = session.get('admin_id')
    feature_options = get_admin_feature_join_code_options('hall_pass', admin_id=admin_id)
    selected_scope = require_admin_feature_scope(
        'hall_pass',
        admin_id=admin_id,
        requested_block=None,
    )
    selected_join_code = selected_scope['join_code']
    selected_class_id = selected_scope.get('class_id')
    student_ids_subq = _student_scope_subquery_for_join_code(selected_join_code)
    pending_requests = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(HallPassLog.join_code == selected_join_code)
        .filter(HallPassLog.class_id == selected_class_id)
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.asc())
        .all()
    )
    approved_queue = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(HallPassLog.join_code == selected_join_code)
        .filter(HallPassLog.class_id == selected_class_id)
        .filter(HallPassLog.status == 'approved')
        .order_by(HallPassLog.decision_time.asc())
        .all()
    )
    out_of_class = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .filter(HallPassLog.join_code == selected_join_code)
        .filter(HallPassLog.class_id == selected_class_id)
        .filter(HallPassLog.status == 'left')
        .order_by(HallPassLog.left_time.asc())
        .all()
    )

    # Get available periods/blocks from teacher's students
    available_periods = (
        db.session.query(Student.block)
        .filter(Student.id.in_(sa.select(student_ids_subq)))
        .distinct()
        .order_by(Student.block)
        .all()
    )
    # Extract just the block values from tuples and filter out None/empty
    periods = sorted([p[0] for p in available_periods if p[0]])

    # Lazily generate the hall pass verification token if needed
    teacher_id = admin_id
    teacher = db.session.get(Admin, teacher_id)

    verify_url = None
    if teacher and teacher.hall_pass_verify_token:
        verify_url = f"/verify/hallpass/{teacher.hall_pass_verify_token}"

    return render_template(
        'admin_hall_pass.html',
        pending_requests=pending_requests,
        approved_queue=approved_queue,
        out_of_class=out_of_class,
        available_periods=periods,
        current_page="hall_pass",
        verify_url=verify_url,
        feature_options=feature_options,
        selected_feature_scope=selected_scope,
        current_join_code=selected_join_code,
    )


@admin_bp.route('/hall-pass/setup')
@admin_required
def hall_pass_setup():
    """Configure hall pass types, queue limits, and simultaneous limits."""
    admin_id = session.get('admin_id')
    selected_scope = require_admin_feature_scope(
        'hall_pass',
        admin_id=admin_id,
    )
    return render_template(
        'hall_pass_setup.html',
        current_join_code=selected_scope['join_code'],
        feature_options=get_admin_feature_join_code_options('hall_pass', admin_id=admin_id),
        selected_feature_scope=selected_scope,
    )


# -------------------- ECONOMY HEALTH --------------------

@admin_bp.route('/economy-policy', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def update_economy_policy():
    admin_id = session.get('admin_id')
    selected_block = (request.form.get('block') or '').strip().upper() or None
    if not selected_block:
        flash("Select a class period before updating economy policy.", "warning")
        return redirect(url_for('admin.economy_health'))
    selected_scope = require_admin_feature_scope(
        'payroll',
        admin_id=admin_id,
        requested_block=selected_block,
        allow_default=False,
    )
    policy_mode = normalize_policy_mode(request.form.get('policy_mode'))
    settings_row = get_feature_settings_row_for_class(
        selected_scope['class_id'],
        create=True,
    )
    if not settings_row:
        flash("Class scope not found for the selected period.", "warning")
        return redirect(url_for('admin.economy_health', block=selected_scope['block']))
    settings_row.economy_policy_mode = policy_mode
    settings_row.economy_policy_updated_at = utc_now()
    cancel_pending_policy_transitions(settings_row.class_id, actor_id=admin_id)
    current_app.logger.info(
        "Economy policy mode changed teacher=%s block=%s mode=%s",
        admin_id,
        selected_scope['block'],
        policy_mode,
    )
    flash(f"Economy policy updated to {POLICY_MODES[policy_mode]['label']}.", "success")
    return redirect(url_for('admin.economy_health', block=selected_scope['block'], review_rebalance=1))


@admin_bp.route('/economy-policy/rebalance', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def apply_economy_rebalance():
    admin_id = session.get('admin_id')
    selected_block = (request.form.get('block') or '').strip().upper() or None
    if not selected_block:
        flash("Select a class period before applying a rebalance.", "warning")
        return redirect(url_for('admin.economy_health'))
    selected_scope = require_admin_feature_scope(
        'payroll',
        admin_id=admin_id,
        requested_block=selected_block,
        allow_default=False,
    )
    activation_mode = (request.form.get('activation_mode') or REBALANCE_ACTIVATION_NEXT_RENEWAL).strip().lower()
    selected_keys = set(request.form.getlist('selected_changes'))
    settings_row = get_feature_settings_row_for_class(
        selected_scope['class_id'],
        create=True,
    )
    if not settings_row:
        flash("Class scope not found for the selected period.", "warning")
        return redirect(url_for('admin.economy_health', block=selected_scope['block'], review_rebalance=1))
    allowed_activation_modes = {
        REBALANCE_ACTIVATION_IMMEDIATE,
        REBALANCE_ACTIVATION_NEXT_RENEWAL,
        REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL,
    }

    if activation_mode == REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL:
        activation_mode = REBALANCE_ACTIVATION_NEXT_RENEWAL

    if activation_mode not in allowed_activation_modes:
        flash("Invalid rebalance activation mode.", "warning")
        return redirect(url_for('admin.economy_health', block=selected_scope['block'], review_rebalance=1))

    effective_block, payroll_settings, rent_settings, insurance_policies, _all_payroll_settings = _load_economy_rebalance_context(
        admin_id,
        selected_scope['block'],
    )

    if not payroll_settings:
        flash("Payroll settings are required before a rebalance can be applied.", "warning")
        return redirect(url_for('admin.economy_health', block=effective_block, review_rebalance=1))

    checker = EconomyBalanceChecker(admin_id, effective_block, class_id=getattr(payroll_settings, "class_id", None))
    effective_join_code = _resolve_join_code_for_block(admin_id, effective_block)
    effective_class = ClassEconomy.query.filter_by(join_code=effective_join_code).first() if effective_join_code else None
    scoped_store_items = (
        StoreItem.query.filter_by(class_id=effective_class.class_id, is_active=True).all()
        if effective_class else []
    )
    analysis = checker.analyze_economy(
        payroll_settings=payroll_settings,
        rent_settings=rent_settings,
        insurance_policies=insurance_policies,
        fines=(
            PayrollFine.query.filter_by(class_id=effective_class.class_id, is_active=True).all()
            if effective_class else []
        ),
        store_items=scoped_store_items,
        expected_weekly_hours=payroll_settings.expected_weekly_hours if payroll_settings.expected_weekly_hours is not None else 5.0,
    )
    preview_items = _build_rebalance_preview(
        admin_id,
        effective_block,
        checker,
        analysis.cwi.cwi,
        rent_settings,
        insurance_policies,
    )

    change_plan = [
        item['change']
        for item in preview_items
        if item.get('key') in selected_keys and item.get('change')
    ]

    if not change_plan:
        flash("No rebalance changes were selected.", "warning")
        return redirect(url_for('admin.economy_health', block=effective_block, review_rebalance=1))

    if activation_mode == REBALANCE_ACTIVATION_IMMEDIATE and request.form.get('confirm_immediate') != 'yes':
        flash("Confirm the immediate change warning before applying now.", "warning")
        return redirect(url_for('admin.economy_health', block=effective_block, review_rebalance=1))

    if activation_mode == REBALANCE_ACTIVATION_IMMEDIATE:
        applied_labels = _apply_rebalance_plan(
            admin_id,
            settings_row,
            change_plan,
            activation_mode=REBALANCE_ACTIVATION_IMMEDIATE,
        )
        flash(f"Applied economy rebalance now for {len(applied_labels)} setting(s).", "success")
    else:
        scheduled_changes = prepare_scheduled_rebalance_changes(
            change_plan,
            rent_settings=rent_settings,
            insurance_policies=insurance_policies,
        )
        queued_transition_count = queue_scheduled_policy_transitions(
            admin_id,
            settings_row,
            scheduled_changes,
            activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL,
        )
        current_app.logger.info(
            "Scheduled economy rebalance teacher=%s block=%s changes=%s",
            admin_id,
            effective_block,
            [change.get('type') for change in change_plan],
        )
        flash(
            f"Scheduled economy rebalance for the renewal after the upcoming bill ({len(change_plan)} setting(s), {queued_transition_count} policy transition(s)).",
            "success",
        )

    return redirect(url_for('admin.economy_health', block=effective_block))


@admin_bp.route('/economy-health')
@admin_required
def economy_health():
    """Show a holistic view of the current economy configuration and CWI health."""
    admin_id = session.get("admin_id")
    requested_block = (request.args.get('block') or '').strip().upper() or None
    selected_scope = require_admin_feature_scope(
        'payroll',
        admin_id=admin_id,
        requested_block=requested_block,
    )

    blocks = _get_teacher_blocks()
    # Always use per-class view since CWI is inherently per-class (multi-tenancy by join_code)
    selected_block = selected_scope['block']

    selected_block, payroll_settings, rent_settings, insurance_policies, all_payroll_settings = _load_economy_rebalance_context(
        admin_id,
        selected_block,
    )
    has_payroll_settings = len(all_payroll_settings) > 0

    selected_class_id = selected_scope['class_id']
    fines = (
        PayrollFine.query.filter_by(class_id=selected_class_id, is_active=True).all()
        if selected_class_id else []
    )
    store_items = (
        StoreItem.query.filter_by(class_id=selected_class_id, is_active=True).all()
        if selected_class_id else []
    )

    banking_settings = _resolve_banking_settings_for_block(admin_id, selected_block) if selected_block else None

    def summarize_banking(settings):
        if not settings:
            return {
                'level': 'warning',
                'title': 'Banking not configured',
                'message': 'Savings interest is off. Enable interest to reward saving and balance rent.',
                'apy': None,
            }

        # Keep as Decimal for precise comparison
        from app.models import _quantize_currency
        apy = _quantize_currency(settings.savings_apy or Decimal('0'))
        payout = settings.interest_schedule_type or 'monthly'

        if apy <= Decimal('0'):
            level = 'warning'
            message = 'Interest is disabled. Set a small APY so students can grow savings over time.'
        elif apy >= 25:
            level = 'warning'
            message = 'High APY may cause runaway balances. Consider lowering the rate to keep savings meaningful.'
        else:
            level = 'success'
            message = f'Savings APY is set to {apy:.2f}% with {payout} payouts.'

        return {
            'level': level,
            'title': 'Banking & Interest',
            'message': message,
            'apy': apy,
            'payout': payout,
        }

    analysis = None
    warnings_by_level = {'critical': [], 'warning': [], 'info': []}
    warnings_by_feature = {}
    actionable_warnings = []
    health_warning_summary = []
    recommendations = {}
    cwi_calc = None
    snapshot = None
    analysis_schedule = None
    expected_hours = payroll_settings.expected_weekly_hours if payroll_settings and payroll_settings.expected_weekly_hours is not None else 5.0
    pay_rate_per_minute = payroll_settings.pay_rate if payroll_settings else None

    if payroll_settings:
        checker = EconomyBalanceChecker(admin_id, selected_block, class_id=getattr(payroll_settings, "class_id", None))
        payload, snapshot = _get_frozen_economy_analysis_payload(
            admin_id,
            selected_block,
            checker,
            payroll_settings,
            rent_settings=rent_settings,
            insurance_policies=insurance_policies,
            fines=fines,
            store_items=store_items,
        )
        analysis = _deserialize_economy_analysis_payload(payload)
        cwi_calc = analysis.cwi
        analysis_schedule = analysis.analysis_schedule
        pay_rate_per_minute = cwi_calc.pay_rate_per_minute
        recommendations = analysis.recommendations

        actionable_warnings, warnings_by_level, warnings_by_feature, health_warning_summary = _filter_economy_health_warnings(
            analysis,
            rent_settings,
            insurance_policies,
            fines,
            store_items,
            selected_block=selected_block,
        )

    policy_summary = _build_policy_summary(
        selected_scope,
        analysis,
        rent_settings,
        insurance_policies,
        fines,
        warnings=actionable_warnings,
    )
    pending_rebalance_effective_at = _extract_pending_rebalance_effective_at(policy_summary)
    rebalance_preview = []
    show_rebalance_review = request.args.get('review_rebalance') == '1'
    if payroll_settings and show_rebalance_review and cwi_calc:
        checker = EconomyBalanceChecker(
            admin_id,
            selected_block,
            policy_mode=policy_summary['mode'],
            class_id=getattr(payroll_settings, "class_id", None),
        )
        rebalance_preview = _build_rebalance_preview(
            admin_id,
            selected_block,
            checker,
            cwi_calc.cwi,
            rent_settings,
            insurance_policies,
        )

    feature_links = {
        'rent': url_for('admin.rent_settings', settings_block=selected_block),
        'insurance': url_for('admin.insurance_management', settings_block=selected_block),
        'fine': url_for('admin.payroll', cwi_block=selected_block),
        'store': url_for('admin.store_management'),
        'budget survival test': url_for('admin.payroll', cwi_block=selected_block),
    }

    return render_template(
        'admin_economy_health.html',
        current_page='economy_health',
        blocks=blocks,
        selected_block=selected_block,
        payroll_settings=payroll_settings,
        has_payroll_settings=has_payroll_settings,
        cwi_calc=cwi_calc,
        expected_hours=expected_hours,
        pay_rate_per_minute=pay_rate_per_minute,
        rent_settings=rent_settings,
        insurance_count=len(insurance_policies),
        store_item_count=len(store_items),
        fine_count=len(fines),
        banking_settings=banking_settings,
        banking_summary=summarize_banking(banking_settings),
        analysis=analysis,
        warnings_by_level=warnings_by_level,
        warnings_by_feature=warnings_by_feature,
        actionable_warning_count=len(actionable_warnings),
        health_warning_summary=health_warning_summary,
        recommendations=recommendations,
        snapshot=snapshot,
        analysis_schedule=analysis_schedule,
        policy_modes=POLICY_MODES,
        policy_summary=policy_summary,
        pending_rebalance_effective_at=pending_rebalance_effective_at,
        rebalance_preview=rebalance_preview,
        show_rebalance_review=show_rebalance_review,
        feature_links=feature_links,
        payroll_link=url_for('admin.payroll', cwi_block=selected_block),
        banking_link=url_for('admin.banking'),
        rent_link=url_for('admin.rent_settings', settings_block=selected_block),
        insurance_link=url_for('admin.insurance_management', settings_block=selected_block),
        store_link=url_for('admin.store_management'),
    )


@admin_bp.route('/payroll-history')
@admin_required
def payroll_history():
    """View payroll history with filtering."""
    current_app.logger.info("Entered admin_payroll_history route")
    admin_id = session.get("admin_id")

    block = request.args.get("block")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    teacher_join_codes = _get_admin_owned_join_codes(admin_id)
    teacher_class_ids = [
        class_id for (class_id,) in db.session.query(ClassEconomy.class_id)
        .filter(ClassEconomy.join_code.in_(teacher_join_codes)).all() if class_id
    ]

    query = Transaction.query.filter(
        Transaction.class_id.in_(teacher_class_ids),
        Transaction.type == "payroll",
    )

    if block:
        # Stream students in batches for this block
        join_code_tuple = db.session.query(ClassEconomy.join_code).filter_by(teacher_id=admin_id, section=block).first()
        if join_code_tuple and join_code_tuple[0]:
            block_class_id = db.session.query(ClassEconomy.class_id).filter_by(join_code=join_code_tuple[0]).scalar()
            query = query.filter(Transaction.class_id == block_class_id)
        else:
            query = query.filter(Transaction.class_id == "NONE")

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        query = query.filter(Transaction.timestamp >= start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)

    payroll_transactions = query.order_by(desc(Transaction.timestamp)).all()
    current_app.logger.info(f"Payroll transactions found: {len(payroll_transactions)}")

    # Fetch lookup data
    seat_lookup = {s.id: s for s in Seat.query.filter(Seat.class_id.in_(teacher_class_ids)).all()}
    student_lookup = {s.id: s for s in _scoped_students().yield_per(50)}
    blocks = sorted({s.block for s in student_lookup.values() if s.block})
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)
    join_codes_by_block = _get_join_codes_by_block(admin_id, blocks)

    payroll_records = []
    for tx in payroll_transactions:
        seat = seat_lookup.get(tx.seat_id)
        student = student_lookup.get(seat.student_id) if seat else None
        student_block = student.block if student else 'Unknown'
        payroll_records.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'block': student_block,
            'class_label': class_labels_by_block.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown',
            'student_id': student.id if student else None,
            'student': student,
            'student_name': student.full_name if student else 'Unknown',
            'join_code': join_codes_by_block.get(student_block, ''),
            'amount': tx.amount,
            'notes': tx.description,
        })

    current_app.logger.info(f"Payroll records prepared: {len(payroll_records)}")

    # Current timestamp for header (effective class timezone)
    current_time = utc_now().astimezone(get_timezone())

    return render_template(
        'admin_payroll_history.html',
        payroll_history=payroll_records,
        blocks=blocks,
        class_labels_by_block=class_labels_by_block,
        join_codes_by_block=join_codes_by_block,
        current_page="payroll_history",
        selected_block=block,
        selected_start=start_date_str,
        selected_end=end_date_str,
        current_time=current_time
    )


@admin_bp.route('/run_payroll', methods=['POST'])
@admin_required
@feat_shell("FEAT-LED-004")
def run_payroll(*args, **kwargs):
    """FEAT-Shell for payroll execution."""
    res = _run_payroll_legacy(*args, **kwargs)
    # No manual commit here; feat_shell owns it
    return res

def _run_payroll_legacy():
    """
    Run payroll by computing earned seconds from TapEvent append-only log (LEGACY).
    For each student, for each block, match active/inactive pairs since last payroll,
    sum total seconds, and post ledger payroll entries.

    CRITICAL: Creates one transaction per student with join_code for proper scoping.
    If student has multiple blocks with this teacher, uses first block's join_code.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        # Get current admin's teacher_id for proper transaction scoping
        current_admin_id = session.get('admin_id')

        if not current_admin_id:
            error_msg = "No admin_id in session"
            current_app.logger.error(f"Payroll error: {error_msg}")
            if is_json:
                return jsonify(status="error", message=error_msg), 401
            flash(error_msg, "admin_error")
            return redirect(url_for('admin.dashboard'))

        selected_scope = _require_payroll_feature_scope_from_request()
        selected_join_code = selected_scope['join_code']

        # Get last payroll for the selected class only.
        last_payroll_tx = Transaction.query.filter_by(
            type="payroll",
            teacher_id=current_admin_id,
            join_code=selected_join_code,
        ).order_by(Transaction.timestamp.desc()).first()
        last_payroll_time = last_payroll_tx.timestamp if last_payroll_tx else None
        current_app.logger.info(f"Run payroll: last payroll at {last_payroll_time}")

        students_query = (
            _scoped_students(include_unassigned=False)
            .join(Seat, Seat.student_id == Student.id)
            .filter(
                Seat.join_code == selected_join_code,
                Seat.claimed_at.isnot(None),
            )
            .distinct()
        )
        # We fetch students merely to maintain parity with the V1 adjustment creation below
        # but the actual payroll computation is bound purely by the canonical class_id.

        class_id = selected_scope['class_id']
        seats = Seat.query.filter_by(class_id=class_id, role='student').all()
        seat_ids = [s.id for s in seats]

        summary = calculate_payroll_breakdown(
            class_id,
            seat_ids,
            last_payroll_time,
        )

        adjustments = []
        for seat_id, amount in summary.items():
            seat = db.session.get(Seat, seat_id)
            if not seat:
                continue
            adjustments.append({
                'seat': seat,
                'teacher_id': current_admin_id,
                'amount': amount,
                'description': "Payroll based on attendance",
                'type': 'payroll',
                'account_type': 'checking',
            })

        result = execute_admin_adjustments(adjustments=adjustments)

        scheduled_rebalances_applied, _scheduled_labels = activate_due_rebalances(
            current_admin_id,
            class_id=selected_scope['class_id'],
        )
        db.session.flush() # FEAT-LEGACY-WRAP: commit removed
        current_app.logger.info(f"Payroll complete. Created {result.applied_count} transactions.")

        success_message = f"Payroll complete. Processed {result.applied_count} payments."
        if scheduled_rebalances_applied:
            success_message += f" Activated {scheduled_rebalances_applied} scheduled economy update(s)."
        if is_json:
            return jsonify(status="success", message=success_message), 200

        flash(success_message, "admin_success")
        return redirect(url_for('admin.payroll'))
    except (SQLAlchemyError, Exception) as e:
        db.session.rollback()
        is_db_error = isinstance(e, SQLAlchemyError)
        error_type = "database" if is_db_error else "unexpected"
        current_app.logger.error(f"Payroll {error_type} error: {e}", exc_info=True)

        if is_json:
            message = "Database error during payroll. Check logs." if is_db_error else "Unexpected error during payroll."
            return jsonify(status="error", message=message), 500

        flash_message = "Database error during payroll. Check logs." if is_db_error else "Unexpected error during payroll."
        flash(flash_message, "admin_error")
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/payroll')
@admin_required
def payroll():
    """
    Enhanced payroll page with tabs for settings, students, rewards, fines, and manual payments.
    """
    now_utc = utc_now()
    current_time = now_utc.astimezone(get_timezone())

    current_admin = get_current_admin()
    if not current_admin:
        abort(404)
    admin_id = current_admin.id
    feature_options = get_admin_feature_join_code_options('payroll', admin_id=admin_id)
    selected_scope = require_admin_feature_scope(
        'payroll',
        admin_id=admin_id,
        requested_block=request.args.get('cwi_block') or request.args.get('block'),
    )
    selected_join_code = selected_scope['join_code']
    selected_block = selected_scope['block']
    selected_class_id = selected_scope['class_id']
    class_row = ClassEconomy.query.filter_by(class_id=selected_class_id).first()
    class_label = (
        (class_row.display_name if class_row and class_row.display_name else None)
        or (f"Period {selected_block}" if selected_block else selected_join_code)
    )

    # Get class-scoped students and seats directly from canonical seat bindings.
    seats = (
        Seat.query
        .filter(
            Seat.class_id == selected_class_id,
            Seat.role == 'student',
            Seat.claimed_at.isnot(None),
        )
        .all()
    )
    if selected_block:
        selected_block_upper = selected_block.upper()
        seats = [
            seat for seat in seats
            if ((seat.block_identifier or seat.block or '').strip().upper() == selected_block_upper)
        ]
    student_ids = [seat.student_id for seat in seats if seat.student_id]
    students = (
        Student.query
        .filter(Student.id.in_(student_ids))
        .distinct()
        .all()
        if student_ids else []
    )
    blocks = [selected_block] if selected_block else []
    # Check if payroll settings exist for the selected class scope
    has_settings = (
        PayrollSettings.query.filter_by(class_id=selected_class_id, block=selected_block)
        .first()
        is not None
    )
    show_setup_banner = not has_settings

    # Get payroll settings for this teacher, filtered to only include blocks with current students
    block_settings = (
        PayrollSettings.query.filter_by(
            class_id=selected_class_id,
            is_active=True,
            block=selected_block,
        ).all()
        if selected_block
        else []
    )

    # Get first block's settings for form pre-population (no global settings)
    default_setting = block_settings[0] if block_settings else None

    # Organize settings by block for display and lookup
    settings_by_block = {}
    for setting in block_settings:
        if setting.block:
            settings_by_block[setting.block] = setting



    def _compute_next_pay_date(setting, now):
        freq_days = setting.payroll_frequency_days if setting and setting.payroll_frequency_days else 14
        first_pay = ensure_utc(setting.first_pay_date) if setting and setting.first_pay_date else None

        # Anchor the schedule strictly to the configured first pay date so manual runs
        # don't shift the calendar. If no first date is set, fall back to now + frequency.
        if first_pay:
            if first_pay > now:
                return first_pay

            elapsed_days = (now - first_pay).days
            periods_since_first = elapsed_days // freq_days
            candidate = first_pay + timedelta(days=freq_days * (periods_since_first + 1))
        else:
            candidate = now + timedelta(days=freq_days)

        while candidate <= now:
            candidate += timedelta(days=freq_days)
        return candidate

    # Next scheduled payroll calculation (keep in UTC for template)
    next_pay_date_utc = _compute_next_pay_date(default_setting, now_utc)

    # Recent payroll activity
    # CRITICAL: Filter by canonical class_id for class isolation.
    my_join_codes = [selected_join_code]
    join_codes_by_block = {selected_block: selected_join_code} if selected_block else {}
    my_class_ids = [selected_class_id] if selected_class_id else []
    payroll_preview = _build_payroll_preview_state(students, join_codes_by_block)
    payroll_summary = payroll_preview["total_summary"]
    payroll_updated_at = payroll_preview["latest_updated_at"]
    payroll_anchor_by_join_code = payroll_preview["anchor_by_join_code"]
    payroll_summary_by_join_code = payroll_preview["summary_by_join_code"]

    recent_payrolls = (
        Transaction.query
        .filter(Transaction.class_id.in_(my_class_ids))
        .filter_by(type='payroll')
        .order_by(Transaction.timestamp.desc())
        .limit(20)
        .all()
    )

    total_payroll_estimate = sum(payroll_summary.values())

    class_labels_by_block = {selected_block: class_label} if selected_block else {}

    # Next payroll by block
    next_payroll_by_block = []
    for block in blocks:
        join_code = join_codes_by_block.get(block)
        block_students = [s for s in students if block in [b.strip() for b in (s.block or '').split(',')]]
        block_estimate = sum(
            payroll_summary_by_join_code.get(join_code, {}).get(s.id, Decimal("0.00"))
            for s in block_students
        ) if join_code else Decimal("0.00")
        setting = settings_by_block.get(block, default_setting)
        block_next_payroll = _compute_next_pay_date(setting, now_utc)
        next_payroll_by_block.append({
            'block': block,
            'class_label': class_labels_by_block.get(block, block),
            'next_date': block_next_payroll,  # Keep in UTC
            'next_date_iso': format_utc_iso(block_next_payroll),
            'estimate': block_estimate
        })

    # Student statistics
    student_stats = []

    # Pre-fetch payroll earnings and last payroll dates in batch
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)
    seat_map = {(seat.student_id, seat.class_id): seat for seat in seats}

    scoped_balances_by_student = {}
    for student in students:
        seat = seat_map.get((student.id, selected_class_id))
        balances = raw_balances.get((str(selected_class_id), seat.id)) if seat else None
        if not balances:
            balances = {'checking_cents': 0, 'savings_cents': 0}

        checking_total = Decimal(balances['checking_cents']) / 100
        savings_total = Decimal(balances['savings_cents']) / 100
        scoped_balances_by_student[student.id] = {
            'checking': checking_total,
            'savings': savings_total,
        }

    seat_ids = [s.id for s in seats]
    student_id_by_seat = {seat.id: seat.student_id for seat in seats}

    # Batch: Total Earned
    earnings_rows = db.session.query(
        Transaction.seat_id,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.seat_id.in_(seat_ids),
        Transaction.type == 'payroll',
        Transaction.is_void == False,
        Transaction.class_id.in_(my_class_ids),
    ).group_by(Transaction.seat_id).all()
    earnings_map = {student_id_by_seat[seat_id]: float(amt or 0) for seat_id, amt in earnings_rows if seat_id in student_id_by_seat}

    # Batch: Last Payroll Date
    last_payroll_rows = db.session.query(
        Transaction.seat_id,
        func.max(Transaction.timestamp)
    ).filter(
        Transaction.seat_id.in_(seat_ids),
        Transaction.type == 'payroll',
        Transaction.class_id.in_(my_class_ids),
    ).group_by(Transaction.seat_id).all()
    last_payroll_map = {student_id_by_seat[seat_id]: ts for seat_id, ts in last_payroll_rows if seat_id in student_id_by_seat}

    events_map_by_join_code = {}
    seat_ids_by_join_code = defaultdict(set)
    seat_id_by_student_block_class = {}
    class_rows = (
        ClassEconomy.query.with_entities(ClassEconomy.join_code, ClassEconomy.class_id)
        .filter(ClassEconomy.join_code.in_(my_join_codes))
        .all()
    )
    class_id_by_join_code = {row.join_code: row.class_id for row in class_rows if row.class_id}
    for seat_row in seats:
        if not seat_row.join_code or seat_row.join_code not in my_join_codes:
            continue
        seat_block = (seat_row.block_identifier or seat_row.block or "").strip().upper()
        seat_ids_by_join_code[seat_row.join_code].add(seat_row.id)
        seat_id_by_student_block_class.setdefault(
            (seat_row.student_id, seat_block, seat_row.class_id),
            seat_row.id,
        )

    for join_code in my_join_codes:
        anchor = payroll_anchor_by_join_code.get(join_code)
        class_id = class_id_by_join_code.get(join_code)
        if not class_id:
            events_map_by_join_code[join_code] = {}
            continue
        scoped_seat_ids = sorted(seat_ids_by_join_code.get(join_code, set()))
        events_map_by_join_code[join_code] = get_batch_attendance_events(
            scoped_seat_ids,
            anchor,
            allowed_class_ids=[class_id],
        )

    for student in students:
        # Calculate unpaid minutes across all blocks
        unpaid_seconds = 0
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        for block in student_blocks:
            block_upper = block.upper()
            join_code = join_codes_by_block.get(block)
            if not join_code:
                continue
            class_id = class_id_by_join_code.get(join_code)
            if not class_id:
                continue
            seat_id = seat_id_by_student_block_class.get((student.id, block_upper, class_id))
            if not seat_id:
                continue
            key = (seat_id, block_upper, class_id)
            events = events_map_by_join_code.get(join_code, {}).get(key, [])
            if events:
                unpaid_seconds += calculate_seconds_in_memory(
                    events,
                    payroll_anchor_by_join_code.get(join_code),
                )

        unpaid_minutes = unpaid_seconds / 60.0
        estimated_payout = payroll_summary.get(student.id, 0)

        student_stats.append({
            'student_id': student.id,
            'student_name': student.full_name,
            'block': student.block,
            'class_label': class_labels_by_block.get(student.block, student.block) if student.block else 'Unknown',
            'unpaid_minutes': int(unpaid_minutes),
            'estimated_payout': estimated_payout,
            'last_payroll_date': last_payroll_map.get(student.id),
            'total_earned': earnings_map.get(student.id, Decimal('0.00'))
        })

    # Get saved templates for this class scope
    saved_adjustments = (
        SavedAdjustment.query
        .filter_by(class_id=selected_scope['class_id'])
        .order_by(SavedAdjustment.created_at.desc())
        .all()
    )
    # Initialize forms
    settings_form = PayrollSettingsForm()
    settings_form.block.choices = (
        [(selected_block, class_labels_by_block.get(selected_block, selected_block))]
        if selected_block else []
    )

    manual_payment_form = ManualPaymentForm()
    # Quick stats
    avg_payout = total_payroll_estimate / len(students) if students else 0

    # Payroll history for History tab (all transaction types, not just payroll)
    payroll_history_transactions = (
        Transaction.query
        .filter(Transaction.class_id.in_(my_class_ids))
        .filter(Transaction.type.in_(['payroll', 'reward', 'fine', 'manual_payment']))
        .order_by(Transaction.timestamp.desc())
        .limit(100)
        .all()
    )
    student_lookup = {s.id: s for s in students}
    seat_lookup = {s.id: s for s in seats}
    payroll_history = []
    for tx in payroll_history_transactions:
        seat = seat_lookup.get(tx.seat_id)
        student = student_lookup.get(seat.student_id) if seat else None
        student_block = student.block if student else 'Unknown'
        payroll_history.append({
            'transaction_id': tx.id,
            'timestamp': tx.timestamp,
            'type': tx.type or 'manual_payment',
            'block': student_block,
            'class_label': class_labels_by_block.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown',
            'student_id': seat.student_id if seat else tx.student_id,
            'student': student,
            'student_name': student.full_name if student else 'Unknown',
            'join_code': join_codes_by_block.get(student_block, ''),
            'amount': tx.amount,
            'notes': tx.description or '',
            'is_void': tx.is_void
        })

    # CWI Configuration - Get selected block from query param
    cwi_block = selected_block
    cwi_setting = None
    if cwi_block:
        # Get the payroll setting for this specific block
        cwi_setting = PayrollSettings.query.filter_by(
            class_id=selected_scope['class_id'],
            block=cwi_block
        ).first()

    # Build join_code to label map for payroll display
    # This is needed because transactions are now scoped by join_code
    join_code_to_label = {selected_join_code: class_label}

    return render_template(
        'admin_payroll.html',
        # Overview tab
        recent_payrolls=recent_payrolls,
        join_code_to_label=join_code_to_label, # Pass lookup map
        join_codes_by_block=join_codes_by_block, # Pass block to join_code map
        next_payroll_date=next_pay_date_utc,  # Pass UTC timestamp
        next_payroll_by_block=next_payroll_by_block,
        total_payroll_estimate=total_payroll_estimate,
        payroll_updated_at=payroll_updated_at,
        total_students=len(students),
        avg_payout=avg_payout,
        total_blocks=len(blocks),
        # Settings tab
        settings_form=settings_form,
        block_settings=block_settings,
        default_setting=default_setting,
        settings_by_block=settings_by_block,
        next_global_payroll=next_pay_date_utc,  # Pass UTC timestamp
        show_setup_banner=show_setup_banner,
        # Students tab
        student_stats=student_stats,
        scoped_balances_by_student=scoped_balances_by_student,
        # Saved Adjustments
        saved_adjustments=saved_adjustments,
        # Manual Payment tab
        manual_payment_form=manual_payment_form,
        all_students=students,
        # History tab
        payroll_history=payroll_history,
        # CWI Configuration
        cwi_block=cwi_block,
        cwi_setting=cwi_setting,
        # General
        blocks=blocks,
        class_labels_by_block=class_labels_by_block,
        current_page="payroll",
        format_utc_iso=format_utc_iso,
        feature_options=feature_options,
        selected_feature_scope=selected_scope,
    )


@admin_bp.route('/payroll/settings', methods=['POST'])
@admin_required
def payroll_settings():
    """Save payroll settings for a block or globally (Simple or Advanced mode)."""
    try:
        current_admin = get_current_admin()
        if not current_admin:
            abort(404)
        admin_id = current_admin.id
        feature_options = get_admin_feature_join_code_options('payroll', admin_id=admin_id)
        enabled_blocks = [option['block'] for option in feature_options if option.get('block')]
        enabled_block_set = set(enabled_blocks)
        class_id_by_block = {
            option['block']: option['class_id']
            for option in feature_options
            if option.get('block') and option.get('class_id')
        }
        selected_scope = require_admin_feature_scope(
            'payroll',
            admin_id=admin_id,
            requested_block=request.form.get('cwi_block') or request.form.get('block'),
        )

        # Derive assignable blocks from canonical feature scopes, not legacy student.block text.
        blocks = enabled_blocks

        # Determine which mode we're in
        settings_mode = request.form.get('settings_mode', 'simple')

        # Shared fields
        from app.models import _quantize_currency
        expected_weekly_hours_raw = request.form.get('expected_weekly_hours')
        expected_weekly_hours = _quantize_currency(expected_weekly_hours_raw) if expected_weekly_hours_raw else Decimal('5.0')

        # Parse form data based on mode
        if settings_mode == 'simple':
            # Simple mode fields
            pay_rate_per_hour = _quantize_currency(request.form.get('simple_pay_rate', '15.0'))
            pay_rate_per_minute = pay_rate_per_hour / Decimal('60')  # Convert to per-minute for storage

            frequency = request.form.get('simple_frequency', 'biweekly')
            frequency_days_map = {'weekly': 7, 'biweekly': 14, 'monthly': 30}
            payroll_frequency_days = frequency_days_map.get(frequency, 14)

            first_pay_date_str = request.form.get('simple_first_pay_date')
            first_pay_date = datetime.strptime(first_pay_date_str, '%Y-%m-%d') if first_pay_date_str else None

            daily_limit_hours_raw = request.form.get('simple_daily_limit')
            daily_limit_hours = _quantize_currency(daily_limit_hours_raw) if daily_limit_hours_raw else None

            apply_to = request.form.get('simple_apply_to', 'all')
            selected_blocks = request.form.getlist('simple_blocks[]') if apply_to == 'selected' else blocks

            # Create settings dict for simple mode
            settings_data = {
                'settings_mode': 'simple',
                'pay_rate': pay_rate_per_minute,
                'payroll_frequency_days': payroll_frequency_days,
                'first_pay_date': first_pay_date,
                'daily_limit_hours': daily_limit_hours,
                'expected_weekly_hours': expected_weekly_hours,
                'time_unit': 'minutes',
                'pay_schedule_type': frequency,
                'is_active': True,
                # Reset advanced fields
                'overtime_enabled': False,
                'overtime_threshold': None,
                'overtime_threshold_unit': None,
                'overtime_threshold_period': None,
                'overtime_multiplier': Decimal('1.0'),
                'max_time_per_day': None,
                'max_time_per_day_unit': None,
                'rounding_mode': 'down'
            }

        else:  # Advanced mode
            pay_amount = _quantize_currency(request.form.get('adv_pay_amount', '0.25'))
            time_unit = request.form.get('adv_time_unit', 'minutes')

            # Convert to per-minute for storage
            unit_to_minute_multiplier = {
                'seconds': Decimal('60'),
                'minutes': Decimal('1'),
                'hours': Decimal('1') / Decimal('60'),
                'days': Decimal('1') / (Decimal('60') * Decimal('24'))
            }
            pay_rate_per_minute = pay_amount * unit_to_minute_multiplier.get(time_unit, Decimal('1'))

            # Overtime settings
            overtime_enabled = 'adv_overtime_enabled' in request.form
            overtime_threshold_raw = request.form.get('adv_overtime_threshold')
            overtime_threshold = _quantize_currency(overtime_threshold_raw) if overtime_threshold_raw else None
            overtime_unit = request.form.get('adv_overtime_unit')
            overtime_period = request.form.get('adv_overtime_period')
            overtime_multiplier_raw = request.form.get('adv_overtime_multiplier')
            overtime_multiplier = _quantize_currency(overtime_multiplier_raw) if overtime_multiplier_raw else Decimal('1.0')

            # Max time per day
            max_time_value_raw = request.form.get('adv_max_time_value')
            max_time_value = _quantize_currency(max_time_value_raw) if max_time_value_raw else None
            max_time_unit = request.form.get('adv_max_time_unit')

            # Pay schedule
            pay_schedule = request.form.get('adv_pay_schedule', 'biweekly')
            custom_value = request.form.get('adv_custom_schedule_value')
            custom_unit = request.form.get('adv_custom_schedule_unit')

            # Calculate payroll_frequency_days
            if pay_schedule == 'custom':
                custom_value = int(custom_value) if custom_value else 14
                if custom_unit == 'weeks':
                    payroll_frequency_days = custom_value * 7
                else:  # days
                    payroll_frequency_days = custom_value
            else:
                schedule_map = {'daily': 1, 'weekly': 7, 'biweekly': 14, 'monthly': 30}
                payroll_frequency_days = schedule_map.get(pay_schedule, 14)

            first_pay_date_str = request.form.get('adv_first_pay_date')
            first_pay_date = datetime.strptime(first_pay_date_str, '%Y-%m-%d') if first_pay_date_str else None

            rounding = request.form.get('adv_rounding', 'down')

            apply_to = request.form.get('adv_apply_to', 'all')
            selected_blocks = request.form.getlist('adv_blocks[]') if apply_to == 'selected' else blocks

            settings_data = {
                'settings_mode': 'advanced',
                'pay_rate': pay_rate_per_minute,
                'time_unit': time_unit,
                'overtime_enabled': overtime_enabled,
                'overtime_threshold': overtime_threshold,
                'overtime_threshold_unit': overtime_unit if overtime_enabled else None,
                'overtime_threshold_period': overtime_period if overtime_enabled else None,
                'overtime_multiplier': overtime_multiplier if overtime_enabled else 1.0,
                'max_time_per_day': max_time_value,
                'max_time_per_day_unit': max_time_unit if max_time_value else None,
                'pay_schedule_type': pay_schedule,
                'pay_schedule_custom_value': int(custom_value) if pay_schedule == 'custom' and custom_value else None,
                'pay_schedule_custom_unit': custom_unit if pay_schedule == 'custom' else None,
                'payroll_frequency_days': payroll_frequency_days,
                'first_pay_date': first_pay_date,
                'rounding_mode': rounding,
                'expected_weekly_hours': expected_weekly_hours,
                'is_active': True,
                # Reset simple fields
                'daily_limit_hours': None
            }

        # Apply settings to selected blocks or all
        # NO global settings - always scoped by block/join_code
        if apply_to == 'all' or not selected_blocks:
            # Apply to all blocks (no global None)
            target_blocks = blocks
        else:
            # Apply to selected blocks only
            target_blocks = [str(block).strip().upper() for block in selected_blocks if str(block).strip()]

        target_blocks = [block for block in target_blocks if block in enabled_block_set]
        target_blocks = list(dict.fromkeys(target_blocks))
        if not target_blocks:
            raise ValueError("No valid payroll class scope selected")

        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "settings_mode": settings_mode,
                    "apply_to": apply_to,
                    "target_blocks": sorted(target_blocks),
                    "selected_scope_class_id": selected_scope["class_id"],
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:class:payroll-settings:update:{selected_scope['class_id']}:{payload_hash}"
        )

        db.session.rollback()
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            for block_value in target_blocks:
                class_id = class_id_by_block.get(block_value)
                if not class_id:
                    raise ValueError(f"Missing class scope for payroll block '{block_value}'")

                setting = PayrollSettings.query.filter_by(class_id=class_id, block=block_value).first()
                if not setting:
                    setting = PayrollSettings(class_id=class_id, block=block_value)

                # Update all fields
                for key, value in settings_data.items():
                    setattr(setting, key, value)

                setting.updated_at = utc_now()
                db.session.add(setting)

        if apply_to == 'all' or not selected_blocks:
            flash(f'Payroll settings ({settings_mode} mode) applied to all periods successfully!', 'success')
        else:
            flash(f'Payroll settings ({settings_mode} mode) applied to {len(selected_blocks)} period(s) successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving payroll settings: {e}")
        flash(f'Error saving payroll settings', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/update-expected-hours', methods=['POST'])
@admin_required
def update_expected_weekly_hours():
    """Update the expected weekly hours for CWI calculation for a specific block or all blocks."""
    redirect_block = (request.form.get('cwi_block') or request.form.get('block') or '').strip().upper()
    try:
        from app.models import _quantize_currency
        selected_scope = _require_payroll_feature_scope_from_request()
        expected_weekly_hours = _quantize_currency(request.form.get('expected_weekly_hours', '5.0'))
        cwi_block = selected_scope['block']
        apply_to_all = request.form.get('apply_to_all', 'false').lower() == 'true'
        current_admin = get_current_admin()
        if not current_admin:
            abort(404)
        admin_id = current_admin.id
        feature_options = get_admin_feature_join_code_options('payroll', admin_id=admin_id)
        enabled_blocks = {option['block'] for option in feature_options if option.get('block')}
        class_id_by_block = {
            option['block']: option['class_id']
            for option in feature_options
            if option.get('block') and option.get('class_id')
        }

        # Validate expected_weekly_hours is within a reasonable range (0.25 to 80)
        if not (0.25 <= expected_weekly_hours <= 80):
            flash('Expected weekly hours must be between 0.25 and 80.', 'error')
            return redirect(url_for('admin.payroll', cwi_block=cwi_block))

        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "expected_weekly_hours": str(expected_weekly_hours),
                    "cwi_block": cwi_block,
                    "apply_to_all": apply_to_all,
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:class:payroll-expected-hours:update:{selected_scope['class_id']}:{payload_hash}"
        )

        db.session.rollback()
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            if apply_to_all:
                # Update all existing payroll settings
                class_ids = [class_id_by_block[block] for block in enabled_blocks if block in class_id_by_block]
                settings_to_update = (
                    PayrollSettings.query
                    .filter(
                        PayrollSettings.class_id.in_(class_ids),
                        PayrollSettings.block.in_(enabled_blocks),
                    )
                    .all()
                )

                if settings_to_update:
                    for setting in settings_to_update:
                        setting.expected_weekly_hours = expected_weekly_hours
                    flash_message = f'Expected weekly hours updated to {expected_weekly_hours} hours/week for all classes.'
                else:
                    # No settings exist - create a default one for the selected block
                    class_id = class_id_by_block.get(cwi_block)
                    if not class_id:
                        abort(404)
                    new_setting = PayrollSettings(
                        class_id=class_id,
                        block=cwi_block,
                        pay_rate=0.25,  # Default $0.25/min = $15/hour
                        expected_weekly_hours=expected_weekly_hours,
                        payroll_frequency_days=14,
                        settings_mode='simple'
                    )
                    db.session.add(new_setting)
                    flash_message = f'Expected weekly hours set to {expected_weekly_hours} hours/week for all classes.'
            else:
                # Update only the selected block
                class_id = class_id_by_block.get(cwi_block)
                if not class_id:
                    abort(404)
                block_setting = PayrollSettings.query.filter_by(class_id=class_id, block=cwi_block).first()

                if block_setting:
                    block_setting.expected_weekly_hours = expected_weekly_hours
                    flash_message = f'Expected weekly hours updated to {expected_weekly_hours} hours/week for {cwi_block}.'
                else:
                    # Create new setting for this block
                    new_setting = PayrollSettings(
                        class_id=class_id,
                        block=cwi_block,
                        pay_rate=0.25,  # Default $0.25/min = $15/hour
                        expected_weekly_hours=expected_weekly_hours,
                        payroll_frequency_days=14,
                        settings_mode='simple'
                    )
                    db.session.add(new_setting)
                    flash_message = f'Expected weekly hours set to {expected_weekly_hours} hours/week for {cwi_block}.'

        flash(flash_message, 'success')

    except ValueError:
        flash('Invalid expected weekly hours value', 'error')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating expected weekly hours: {e}")
        flash(f'Error updating expected weekly hours', 'error')

    # Redirect back with cwi_block parameter to maintain the selected class
    safe_next_target = _safe_local_redirect_target(request.form.get('next'))
    if safe_next_target:
        return redirect(safe_next_target)

    if redirect_block:
        return redirect(url_for('admin.payroll', cwi_block=redirect_block))
    return redirect(url_for('admin.payroll'))


# -------------------- PAYROLL REWARDS & FINES --------------------

@admin_bp.route('/payroll/rewards/add', methods=['POST'])


@admin_bp.route('/payroll/transactions/<int:transaction_id>/void', methods=['POST'])
@admin_required
def void_payroll_transaction(transaction_id):
    """Void a single transaction from payroll interface."""
    try:
        selected_scope = _require_payroll_feature_scope_from_request()
        transaction = (
            Transaction.query
            .filter(Transaction.id == transaction_id)
            .filter(Transaction.class_id == selected_scope['class_id'])
            .first_or_404()
        )

        if transaction.is_void:
            return jsonify({'success': False, 'message': 'Transaction is already voided'}), 400

        idempotency_key = (
            f"feat:led:payroll-void:{selected_scope['class_id']}:{selected_scope['join_code']}:{transaction.id}"
        )
        db.session.rollback()
        with FEATContext("FEAT-LED-004", idempotency_key=idempotency_key):
            transaction = (
                Transaction.query
                .filter(Transaction.id == transaction_id)
                .filter(Transaction.class_id == selected_scope['class_id'])
                .first_or_404()
            )

            if transaction.is_void:
                return jsonify({'success': False, 'message': 'Transaction is already voided'}), 400

            execute_void_transaction(transaction)

        return jsonify({'success': True, 'message': 'Transaction voided successfully'})
    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voiding transaction: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transaction'}), 500


@admin_bp.route('/payroll/transactions/void-bulk', methods=['POST'])
@admin_required
def void_transactions_bulk():
    """Void multiple transactions at once."""
    try:
        data = request.get_json()
        transaction_ids = data.get('transaction_ids', [])
        selected_scope = _require_payroll_feature_scope_from_request()

        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transactions selected'}), 400

        student_ids_subq = _student_scope_subquery_for_join_code(selected_scope['join_code'])
        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "class_id": selected_scope["class_id"],
                    "join_code": selected_scope["join_code"],
                    "transaction_ids": [int(tx_id) for tx_id in transaction_ids],
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:led:payroll-void-bulk:{selected_scope['class_id']}:{payload_hash}"
        )

        count = 0
        db.session.rollback()
        with FEATContext("FEAT-LED-004", idempotency_key=idempotency_key):
            for tx_id in transaction_ids:
                transaction = (
                    Transaction.query
                    .filter(Transaction.id == int(tx_id))
                    .filter(Transaction.class_id == selected_scope['class_id'])
                    .first()
                )
                if transaction and not transaction.is_void:
                    execute_void_transaction(transaction)
                    count += 1
        return jsonify({'success': True, 'message': f'{count} transaction(s) voided successfully'})
    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voiding transactions in bulk: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transactions'}), 500




@admin_bp.route('/payroll/manual-payment', methods=['POST'])
@admin_required
def payroll_manual_payment():
    """Send manual payments to selected students and optionally save as a template."""
    form = ManualPaymentForm()

    if form.validate_on_submit():
        try:
            student_ids = request.form.getlist('student_ids')
            save_action = request.form.get('save_action', 'apply_only') # apply_only, save_and_apply, save_only
            payment_type = request.form.get('payment_type', 'deposit') # deposit or deduction

            description = form.description.data
            amount = form.amount.data
            account_type = form.account_type.data

            # Amount logic: deduction means negative amount for transactions
            transaction_amount = amount if payment_type == 'deposit' else -amount

            if save_action in ['apply_only', 'save_and_apply'] and not student_ids:
                flash('Please select at least one student to apply the payment.', 'warning')
                return redirect(url_for('admin.payroll'))

            # Get current admin ID for teacher_id
            selected_scope = _require_payroll_feature_scope_from_request()
            selected_join_code = selected_scope['join_code']
            selected_class_id = selected_scope['class_id']
            teacher_seat = selected_scope['teacher_seat']

            # Save Template Logic
            if save_action in ['save_only', 'save_and_apply']:
                saved_adj = SavedAdjustment(
                    seat_id=teacher_seat.id,
                    class_id=selected_class_id,
                    join_code=selected_join_code,
                    name=description,
                    description=description,
                    amount=amount,
                    type=payment_type,
                    is_active=True
                )
                db.session.add(saved_adj)
                db.session.commit()
                if save_action == 'save_only':
                    flash(f'Template "{description}" saved successfully!', 'success')
                    return redirect(url_for('admin.payroll'))

            banking_settings = BankingSettings.query.filter_by(
                teacher_id=current_admin_id,
                block=selected_scope['block'],
            ).first()

            adjustments = []
            for student_id in student_ids:
                student = _get_student_or_404(int(student_id))
                if student:
                    seat = Seat.query.filter_by(student_id=student.id, class_id=selected_class_id).first()
                    if not seat:
                        flash('One or more selected students are outside the selected class scope.', 'error')
                        return redirect(url_for('admin.payroll'))

                    adjustments.append({
                        'seat': seat,
                        'teacher_id': current_admin_id,
                        'amount': transaction_amount,
                        'description': f"Manual Payment: {description}",
                        'account_type': account_type,
                        'type': 'manual_payment',
                    })

            result = execute_admin_adjustments(adjustments=adjustments, banking_settings=banking_settings)

            # Message formatting
            action_verb = "Deposit" if payment_type == 'deposit' else "Deduction"
            message = f'{action_verb} of ${amount:.2f} applied to {result.applied_count} student(s)!'
            if save_action == 'save_and_apply':
                message = f'Template saved and {action_verb.lower()} applied to {result.applied_count} student(s)!'

            if result.declined_count:
                message += f" {result.declined_count} declined for insufficient funds."
            if result.fee_count:
                message += f" Overdraft fee charged for {result.fee_count}."
            flash(message, 'warning' if result.declined_count else 'success')

        except HTTPException:
            raise
        except Exception as e:
            from app.feats.base import InvariantViolation
            if isinstance(e, InvariantViolation):
                raise

            db.session.rollback()
            current_app.logger.error(f"Error processing manual payment: {e}")
            flash('Error processing manual payment. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


# -------------------- ATTENDANCE --------------------

@admin_bp.route('/attendance-log')
@admin_required
def attendance_log():
    """View complete attendance log."""
    # Get accessible student IDs for tenant scoping
    student_ids_subq = _student_scope_subquery(include_unassigned=False)

    # Get distinct periods from TapEvents for this admin's students
    periods_query = (
        db.session.query(TapEvent.period)
        .filter(TapEvent.student_id.in_(sa.select(student_ids_subq)))
        .filter(TapEvent.is_deleted.is_not(True))
        .distinct()
        .order_by(TapEvent.period)
    )
    periods = [p[0] for p in periods_query.all() if p[0]]

    # Get distinct blocks from Students for this admin's students
    blocks = _get_teacher_blocks()

    # Build class_labels_by_block dictionary
    admin_id = session.get("admin_id")
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    return render_template(
        'admin_attendance_log.html',
        periods=periods,
        blocks=blocks,
        class_labels_by_block=class_labels_by_block,
        current_page="attendance"
    )


# -------------------- STUDENT DATA IMPORT/EXPORT --------------------

@admin_bp.route('/upload-students', methods=['POST'])
@admin_required
def upload_students():
    """
    Upload student roster from CSV file.

    Creates Seat entries (unclaimed accounts) with join codes.
    Students later claim their seat by providing the join code + credentials.
    """
    file = request.files.get('csv_file')
    if not file:
        flash("No file provided", "admin_error")
        return redirect(url_for('admin.students'))

    # Read file content and remove BOM if present
    content = file.stream.read().decode("UTF-8-sig")  # UTF-8-sig removes BOM
    teacher_id = session.get("admin_id")
    idempotency_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    idempotency_key = f"feat:iden:upload-students:{teacher_id}:{idempotency_hash}"

    # Close any open read transaction before FEAT entry.
    db.session.rollback()

    with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
        stream = io.StringIO(content, newline=None)
        csv_input = csv.DictReader(stream)
        added_count = 0
        errors = 0
        duplicated = 0

        # Track join codes for each block
        from app.models import Seat, IdentityProfile, ClassEconomy
        from app.utils.join_code import generate_join_code
        from app.hash_utils import hash_username_lookup
        import random
        import string

        # Get or generate join codes for each block in this upload
        join_codes_by_block = {}
        class_ids_by_block = {}
        created_class_rows_by_block = {}

        # Keep track of matched DB seats during this upload to avoid recreating them
        matched_seats = set()
        name_counts_in_run = {}  # (class_id, name_key) -> count

        for row in csv_input:
            try:
                # Handle both template column names and code-friendly names (case-insensitive)
                # Try template column names first, then fall back to lowercase versions
                first_name = (row.get('First Name') or row.get('first_name') or '').strip()
                last_name = (row.get('Last Name') or row.get('last_name') or '').strip()
                block = (row.get('Class Section') or row.get('class_section') or row.get('block') or '').strip().upper()
                class_name = (row.get('Class Name') or row.get('class_name') or '').strip()
                additional_notes = (row.get('Additional Notes') or row.get('additional_notes') or '').strip()

                if not all([first_name, last_name, block]):
                    raise ValueError("Missing required fields.")

                # Generate initials
                first_initial = first_name[0].upper()
                last_initial = last_name[0].upper()

                # Get or generate join code for this teacher-block combination
                if block not in join_codes_by_block:
                    # Check if this teacher already has a class for this block
                    existing_class = ClassEconomy.query.filter_by(
                        teacher_id=teacher_id,
                        section=block
                    ).first()

                    if existing_class:
                        # Reuse existing join code and class_id
                        join_codes_by_block[block] = existing_class.join_code
                        class_ids_by_block[block] = existing_class.class_id
                    else:
                        # Generate new unique join code with retry limit
                        new_code = None
                        for _ in range(MAX_JOIN_CODE_RETRIES):
                            new_code = generate_join_code()
                            # Ensure uniqueness across all classes
                            if not ClassEconomy.query.filter_by(join_code=new_code).first():
                                join_codes_by_block[block] = new_code
                                break
                        else:
                            # If we couldn't generate a unique code after max_retries, use a timestamp-based fallback
                            block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                            timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                            new_code = f"B{block_initial}{timestamp_suffix:04d}"
                            join_codes_by_block[block] = new_code
                            current_app.logger.warning(
                                f"Failed to generate unique join code after {MAX_JOIN_CODE_RETRIES} attempts. "
                                f"Using fallback code {new_code} for block {block} in roster upload"
                            )

                    # Ensure the teacher student seat exists for this new or existing join code
                    _ensure_teacher_student_seat(teacher_id, join_codes_by_block[block], block)

                if block not in class_ids_by_block:
                    class_id, class_created, class_row = _ensure_join_code_anchors(
                        teacher_id,
                        join_codes_by_block[block],
                        class_label=class_name or block,
                        return_metadata=True,
                    )
                    class_ids_by_block[block] = class_id
                    if class_created:
                        created_class_rows_by_block[block] = class_row

                join_code = join_codes_by_block[block]
                class_id = class_ids_by_block[block]

                claim_first_name_hash = hash_username_lookup(first_name.lower())
                claim_last_name_hash = hash_username_lookup(last_name.lower())
                name_key = (first_name.lower(), last_name.lower())

                # Find all seats in the DB for this class with the same name hashes.
                # Exclude teacher shadow student seats from collision counts.
                db_seats = (
                    Seat.query
                    .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
                    .filter(
                        Seat.class_id == class_id,
                        Seat.claim_first_name_hash == claim_first_name_hash,
                        Seat.claim_last_name_hash == claim_last_name_hash,
                        IdentityProfile.profile_type != 'teacher_shadow_student',
                    )
                    .all()
                )

                # Check if we can match this row to an unmatched existing seat in the DB
                matched_seat = None
                for s in db_seats:
                    if s.id not in matched_seats:
                        matched_seat = s
                        matched_seats.add(s.id)
                        break

                if matched_seat:
                    # This seat already exists, skip creating it
                    duplicated += 1
                    continue

                # If we got here, we need to create a new Seat.
                # Dedupe symmetry rule: once any duplicate exists in this class (either in the
                # DB or created in this upload run), ALL seats with this name require a
                # dedupe_code — including seats that already exist without one. This prevents
                # the asymmetry where seat #1 is claimable without a code but seat #2 requires
                # one.
                total_existing = len(db_seats) + name_counts_in_run.get((class_id, name_key), 0)
                is_collision = total_existing > 0

                dedupe_code = None
                if is_collision:
                    alphabet = string.ascii_uppercase + string.digits
                    dedupe_code = "".join(random.choices(alphabet, k=4))

                    # Backfill: if the first DB seat for this name still has no dedupe_code,
                    # assign one now so it cannot be claimed without a code either.
                    for s in db_seats:
                        if s.dedupe_code is None:
                            backfill_code = "".join(random.choices(alphabet, k=4))
                            s.dedupe_code = backfill_code
                            # Regenerate its fingerprint to be code-scoped too.
                            s.roster_fingerprint = hash_username_lookup(
                                f"{class_id}|{first_name.lower()}|{last_name.lower()}|{backfill_code}"
                            )

                name_counts_in_run[(class_id, name_key)] = name_counts_in_run.get((class_id, name_key), 0) + 1

                # Roster fingerprint is class-scoped (INV-CORE: no cross-class correlators).
                if dedupe_code:
                    roster_fingerprint = hash_username_lookup(
                        f"{class_id}|{first_name.lower()}|{last_name.lower()}|{dedupe_code}"
                    )
                else:
                    roster_fingerprint = hash_username_lookup(
                        f"{class_id}|{first_name.lower()}|{last_name.lower()}"
                    )

                # Create Seat (unclaimed account)
                seat = Seat(
                    class_id=class_id,
                    role='student',
                    block_identifier=block,
                    block=block,
                    claim_first_name_hash=claim_first_name_hash,
                    claim_last_name_hash=claim_last_name_hash,
                    roster_fingerprint=roster_fingerprint,
                    dedupe_code=dedupe_code,
                    join_code=join_code,
                    claimed_at=None
                )
                db.session.add(seat)
                db.session.flush()

                # Create associated IdentityProfile
                profile = IdentityProfile(
                    seat_id=seat.id,
                    profile_type='student',
                    first_name=first_name,
                    last_initial=last_initial
                )
                db.session.add(profile)

                if additional_notes:
                    current_app.logger.info(
                        "Bulk upload additional notes provided (not persisted): class_id=%s block=%s length=%s",
                        class_id,
                        block,
                        len(additional_notes),
                    )
                added_count += 1
            except Exception as e:
                current_app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
                errors += 1

        for class_row in created_class_rows_by_block.values():
            _queue_pending_class_timezone_confirmation(class_row)

        # Build success message with join codes
        success_msg = f"{added_count} roster seats created successfully"
        if errors > 0:
            success_msg += f"\n{errors} rows could not be processed"
        if duplicated > 0:
            success_msg += f"\n{duplicated} duplicate seats skipped"

        # Display join codes for each block
        if join_codes_by_block:
            success_msg += "\n\nJoin Codes by Period:\n"
            for period, code in sorted(join_codes_by_block.items()):
                success_msg += f"Period {period}: {code}\n"
            success_msg += "\nShare these codes with your students so they can claim their accounts."

        flash(success_msg, "admin_success")

    return redirect(url_for('admin.students'))


@admin_bp.route('/download-csv-template')
@admin_required
def download_csv_template():
    """
    Serves the student_upload_template.csv from app/data/.
    """
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "student_upload_template.csv")
    return send_file(template_path, as_attachment=True, download_name="student_upload_template.csv", mimetype='text/csv')


@admin_bp.route('/export-students')
@admin_required
def export_students():
    """Export all student data to CSV."""
    admin_id = session.get('admin_id')
    teacher_join_codes = _get_admin_owned_join_codes(admin_id)
    selected_join_code = (_get_current_admin_join_code(admin_id) or '').strip() or None
    if selected_join_code and selected_join_code not in teacher_join_codes:
        selected_join_code = None
    selected_class_id = None
    if selected_join_code:
        selected_class_id = db.session.query(ClassEconomy.class_id).filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.join_code == selected_join_code,
        ).scalar()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'First Name', 'Last Initial', 'Block', 'Checking Balance',
        'Savings Balance', 'Total Earnings', 'Insurance Plan',
        'Rent Enabled', 'Has Completed Setup'
    ])

    # Write student data
    students_query = _scoped_students().order_by(Student.first_name, Student.last_initial)
    if selected_join_code:
        students_query = students_query.filter(
            Student.id.in_(
                db.session.query(ClassMembership.student_id).filter(
                    ClassMembership.join_code == selected_join_code,
                    ClassMembership.role == 'student',
                    ClassMembership.student_id.isnot(None),
                )
            )
        )

    students = students_query.all()
    teacher_id = admin_id
    student_ids = [s.id for s in students]
    scoped_class_ids = []
    if selected_class_id:
        scoped_class_ids = [selected_class_id]
    elif teacher_join_codes:
        scoped_class_ids = [
            class_id
            for (class_id,) in db.session.query(ClassEconomy.class_id).filter(
                ClassEconomy.join_code.in_(teacher_join_codes)
            ).all()
            if class_id
        ]

    seats = Seat.query.filter(Seat.class_id.in_(scoped_class_ids), Seat.role == 'student').all()
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)
    seat_map = {(seat.student_id, seat.class_id): seat for seat in seats}

    scoped_balances_by_student = {}
    for student in students:
        checking_total = Decimal('0.00')
        savings_total = Decimal('0.00')
        earnings_total = Decimal('0.00')
        for class_id in scoped_class_ids:
            seat = seat_map.get((student.id, class_id))
            balances = raw_balances.get((str(class_id), seat.id)) if seat else None
            if not balances:
                balances = {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}
            checking_total += Decimal(balances['checking_cents']) / 100
            savings_total += Decimal(balances['savings_cents']) / 100
            earnings_total += Decimal(balances.get('earnings', Decimal('0.00')))
        scoped_balances_by_student[student.id] = {
            'checking': checking_total,
            'savings': savings_total,
            'earnings': earnings_total,
        }

    # Prefetch active insurances to avoid N+1 queries
    active_insurances_map = {}
    if teacher_id and student_ids:
        class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=teacher_id).subquery()
        scoped_insurances = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id.in_(student_ids),
            StudentInsurance.status == 'active',
            InsurancePolicy.class_id.in_(sa.select(class_ids_subq)),
        )
        if selected_join_code:
            scoped_insurances = scoped_insurances.filter(StudentInsurance.join_code == selected_join_code)
        scoped_insurances = scoped_insurances.all()

        for ins in scoped_insurances:
            if ins.student_id not in active_insurances_map:
                active_insurances_map[ins.student_id] = ins

    for student in students:
        export_block = student.block
        if selected_join_code:
            scoped_seat = Seat.query.filter(
                Seat.student_id == student.id,
                Seat.join_code == selected_join_code,
                Seat.claimed_at.isnot(None),
            ).first()
            if scoped_seat and scoped_seat.block:
                export_block = scoped_seat.block

        # Get active insurance for this student from pre-fetched map
        active_insurance = active_insurances_map.get(student.id)
        insurance_name = active_insurance.policy.title if active_insurance else 'None'

        if selected_join_code:
            export_seat = Seat.query.filter_by(student_id=student.id, class_id=selected_class_id).first() if selected_class_id else None
            if not export_seat:
                raise ValueError(
                    f"Missing canonical seat scope for export student_id={student.id} class_id={selected_class_id}"
                )
            checking_balance = student.get_checking_balance(class_id=selected_class_id, seat_id=export_seat.id)
            savings_balance = student.get_savings_balance(class_id=selected_class_id, seat_id=export_seat.id)
            total_earnings = Decimal(str(student.get_total_earnings(join_code=selected_join_code)))
        else:
            scoped_balances = scoped_balances_by_student.get(student.id, {})
            checking_balance = scoped_balances.get('checking', Decimal('0.00'))
            savings_balance = scoped_balances.get('savings', Decimal('0.00'))
            total_earnings = scoped_balances.get('earnings', Decimal('0.00'))

        writer.writerow([
            _sanitize_csv_field(student.first_name),
            _sanitize_csv_field(student.last_initial),
            _sanitize_csv_field(export_block),
            f"{checking_balance:.2f}",
            f"{savings_balance:.2f}",
            f"{total_earnings:.2f}",
            _sanitize_csv_field(insurance_name),
            'Yes' if student.is_rent_enabled else 'No',
            'Yes' if student.has_completed_setup else 'No'
        ])

    # Prepare response
    output.seek(0)
    filename = f"students_export_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# -------------------- ADMIN TAP OUT --------------------

@admin_bp.route('/enforce-daily-limits', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def enforce_daily_limits():
    """
    Manually trigger auto tap-out for all students who have exceeded their daily limit.
    Returns a report of students who were auto-tapped out.
    """
    from app.payroll import get_daily_limit_seconds
    from app.attendance import calculate_period_attendance_utc_range

    students = _scoped_students().all()
    tapped_out = []
    checked = 0
    errors = []
    current_admin_id = session.get('admin_id')

    now_utc = utc_now()
    today_local = class_date(timestamp_utc=now_utc)
    start_of_day_utc, end_of_day_utc = day_bounds_utc(timestamp_utc=now_utc)

    for student in students:
        period_upper = None
        try:
            student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
            for block_original in student_blocks:
                period_upper = block_original.upper()
                join_code = get_join_code_for_student_period(student.id, period_upper, teacher_id=current_admin_id)
                if not join_code:
                    continue
                class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
                class_id = class_row.class_id if class_row else None
                if not class_id:
                    continue
                seat_id = get_seat_id_for_class(student.id, class_id)
                if not seat_id:
                    continue
                att_state = SeatAttendanceState.query.filter_by(
                    seat_id=seat_id,
                    class_id=class_id,
                    period=period_upper,
                ).first()

                if not att_state or not att_state.is_active:
                    continue

                checked += 1
                daily_limit = get_daily_limit_seconds(
                    block_original,
                    class_id=class_id,
                )
                if not daily_limit:
                    continue

                today_attendance = calculate_period_attendance_utc_range(
                    seat_id, class_id, period_upper, start_of_day_utc, end_of_day_utc
                )
                if att_state.last_event_at:
                    last_tap_in_utc = ensure_utc(att_state.last_event_at)
                    if start_of_day_utc <= last_tap_in_utc < end_of_day_utc:
                        today_attendance += (now_utc - last_tap_in_utc).total_seconds()

                if today_attendance < daily_limit:
                    continue

                student_tap(
                    student_id=student.id,
                    seat_id=seat_id,
                    class_id=class_id,
                    join_code=join_code,
                    period=period_upper,
                    status="inactive",
                    reason=f"Daily limit reached ({daily_limit / 3600:.1f}h)",
                    reason_code=TapEventReasonCode.DAILY_LIMIT,
                    timestamp_utc=now_utc,
                )
                att_state.done_for_day_date = today_local
                tapped_out.append(f"{student.full_name} (Period {period_upper})")
                break
        except Exception as e:
            errors.append(
                f"Error when executing auto-timeout for {student.full_name} (ID {student.id}, Period {period_upper or 'unknown'})"
            )
            current_app.logger.error(
                f"Error enforcing limits for student {student.id} ({student.full_name}) in period {period_upper or 'unknown'}",
                exc_info=True,
            )
            continue

    message = f"Checked {checked} active students. Auto-tapped out {len(tapped_out)} student(s)."

    return jsonify({
        "status": "success",
        "message": message,
        "checked": checked,
        "tapped_out": tapped_out,
        "errors": errors
    })


@admin_bp.route('/tap-out-students', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def tap_out_students():
    """
    Admin endpoint to tap out one or more students from a specific period.
    Supports single student, multiple students, or entire block tap-out.
    """
    data = request.get_json()

    # Get parameters
    student_ids = data.get('student_ids', [])  # List of student IDs, or 'all' for entire block
    period = data.get('period', '').strip().upper()
    reason = data.get('reason', 'Teacher tap-out')
    tap_out_all = data.get('tap_out_all', False)  # If true, tap out all active students in this period

    if not period:
        return jsonify({"status": "error", "message": "Period is required."}), 400

    if not tap_out_all and not student_ids:
        return jsonify({"status": "error", "message": "Either student_ids or tap_out_all must be provided."}), 400

    now_utc = utc_now()
    tapped_out = []
    already_inactive = []
    errors = []
    current_admin_id = session.get('admin_id')

    try:
        # If tap_out_all is true, get all students with this period who are currently active
        if tap_out_all:
            # Find all students in this block
            students = _scoped_students().all()
            for student in students:
                student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
                if period not in student_blocks:
                    continue

                join_code = get_join_code_for_student_period(student.id, period, teacher_id=current_admin_id)
                if not join_code:
                    continue

                class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
                class_id_for_state = class_row.class_id if class_row else None
                if not class_id_for_state:
                    continue
                seat_id_for_state = get_seat_id_for_class(student.id, class_id_for_state)
                if not seat_id_for_state:
                    continue

                att_state = SeatAttendanceState.query.filter_by(
                    seat_id=seat_id_for_state,
                    class_id=class_id_for_state,
                    period=period,
                ).first()

                if att_state and att_state.is_active:
                    student_ids.append(student.id)

        # Process each student ID
        for student_id in student_ids:
            student = _get_student_or_404(student_id)

            if not student:
                errors.append(f"Student ID {student_id} not found")
                continue

            # Verify the student has this period in their block
            student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            if period not in student_blocks:
                errors.append(f"{student.full_name} is not enrolled in period {period}")
                continue

            join_code = get_join_code_for_student_period(student.id, period, teacher_id=current_admin_id)
            if not join_code:
                errors.append(f"{student.full_name} has no join code for period {period} in this class scope")
                continue

            class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
            class_id = class_row.class_id if class_row else None
            if not class_id:
                errors.append(f"{student.full_name} has no class record for join code {join_code}")
                continue
            seat_id = get_seat_id_for_class(student.id, class_id)
            if not seat_id:
                errors.append(f"{student.full_name} has no seat in class {class_id}")
                continue

            att_state = SeatAttendanceState.query.filter_by(
                seat_id=seat_id,
                class_id=class_id,
                period=period,
            ).first()

            if not att_state or not att_state.is_active:
                already_inactive.append(student.full_name)
                continue

            student_tap(
                student_id=student.id,
                seat_id=seat_id,
                class_id=class_id,
                join_code=join_code,
                period=period,
                status="inactive",
                reason=reason,
                timestamp_utc=now_utc,
            )
            att_state.done_for_day_date = class_date(timestamp_utc=now_utc)

            tapped_out.append(student.full_name)

            current_app.logger.info(
                f"Admin tapped out student {student.id} ({student.full_name}) from period {period}, locked until midnight"
            )

        # Build response message
        message_parts = []
        if tapped_out:
            message_parts.append(f"Successfully tapped out {len(tapped_out)} student(s)")
        if already_inactive:
            message_parts.append(f"{len(already_inactive)} student(s) were already inactive")
        if errors:
            message_parts.append(f"{len(errors)} error(s) occurred")

        return jsonify({
            "status": "success",
            "message": ". ".join(message_parts),
            "tapped_out": tapped_out,
            "already_inactive": already_inactive,
            "errors": errors
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin tap-out failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to tap out students due to an internal error."
        }), 500


@admin_bp.route('/tap-in-students', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def tap_in_students():
    """
    Admin endpoint to tap in one or more students for a specific period.
    """
    data = request.get_json()

    # Get parameters
    student_ids = data.get('student_ids', [])
    period = data.get('period', '').strip().upper()

    if not period:
        return jsonify({"status": "error", "message": "Period is required."}), 400

    if not student_ids:
        return jsonify({"status": "error", "message": "student_ids must be provided."}), 400

    now_utc = utc_now()
    tapped_in = []
    already_active = []
    errors = []
    current_admin_id = session.get('admin_id')

    try:
        # Process each student ID
        for student_id in student_ids:
            student = _get_student_or_404(student_id)

            if not student:
                errors.append(f"Student ID {student_id} not found")
                continue

            # Verify the student has this period in their block
            student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            if period not in student_blocks:
                errors.append(f"{student.full_name} is not enrolled in period {period}")
                continue

            join_code = get_join_code_for_student_period(student.id, period, teacher_id=current_admin_id)
            if not join_code:
                errors.append(f"{student.full_name} has no join code for period {period} in this class scope")
                continue

            class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
            class_id = class_row.class_id if class_row else None
            if not class_id:
                errors.append(f"{student.full_name} has no class record for join code {join_code}")
                continue
            seat_id = get_seat_id_for_class(student.id, class_id)
            if not seat_id:
                errors.append(f"{student.full_name} has no seat in class {class_id}")
                continue

            att_state = SeatAttendanceState.query.filter_by(
                seat_id=seat_id,
                class_id=class_id,
                period=period,
            ).first()

            if att_state and att_state.is_active:
                already_active.append(student.full_name)
                continue

            student_tap(
                student_id=student.id,
                seat_id=seat_id,
                class_id=class_id,
                join_code=join_code,
                period=period,
                status="active",
                reason="Teacher tap-in",
                timestamp_utc=now_utc,
            )
            tapped_in.append(student.full_name)

            current_app.logger.info(
                f"Admin tapped in student {student.id} ({student.full_name}) for period {period}"
            )

        # Build response message
        message_parts = []
        if tapped_in:
            message_parts.append(f"Successfully tapped in {len(tapped_in)} student(s)")
        if already_active:
            message_parts.append(f"{len(already_active)} student(s) were already active")
        if errors:
            message_parts.append(f"{len(errors)} error(s) occurred")

        return jsonify({
            "status": "success",
            "message": ". ".join(message_parts),
            "tapped_in": tapped_in,
            "already_active": already_active,
            "errors": errors
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin tap-in failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to tap in students. Please try again or contact support."
        }), 500


@admin_bp.route('/students/bulk-update-hall-passes', methods=['POST'])
@admin_required
def bulk_update_hall_passes():
    """
    Admin endpoint to bulk update hall passes for selected students.
    Supports set, add, and subtract operations.
    """
    data = request.get_json()

    # Get parameters
    student_ids = data.get('student_ids', [])
    update_type = data.get('update_type', 'set')  # 'set', 'add', or 'subtract'
    value = data.get('value', 0)

    if not student_ids:
        return jsonify({"status": "error", "message": "student_ids must be provided."}), 400

    if update_type not in ['set', 'add', 'subtract']:
        return jsonify({"status": "error", "message": "update_type must be 'set', 'add', or 'subtract'."}), 400

    try:
        value = int(value)
        if value < 0:
            return jsonify({"status": "error", "message": "Value must be non-negative."}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Value must be a valid integer."}), 400

    updated = []
    errors = []

    try:
        # Process each student ID
        for student_id in student_ids:
            student = _get_student_or_404(student_id)

            if not student:
                errors.append(f"Student ID {student_id} not found")
                continue

            # Update hall passes based on operation type
            if update_type == 'set':
                student.hall_passes = value
            elif update_type == 'add':
                student.hall_passes = (student.hall_passes or 0) + value
            elif update_type == 'subtract':
                student.hall_passes = max(0, (student.hall_passes or 0) - value)

            updated.append(student.full_name)

            current_app.logger.info(
                f"Admin updated hall passes for student {student.id} ({student.full_name}): {update_type} {value}, new value: {student.hall_passes}"
            )

        # Commit all updates
        db.session.flush()

        # Build response message
        action_text = {
            'set': f'set to {value}',
            'add': f'increased by {value}',
            'subtract': f'decreased by {value}'
        }

        message = f"Successfully updated hall passes for {len(updated)} student(s) ({action_text[update_type]})"
        if errors:
            message += f". {len(errors)} error(s) occurred"

        return jsonify({
            "status": "success",
            "message": message,
            "updated": updated,
            "errors": errors
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Bulk hall pass update failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to update hall passes. Please try again or contact support."
        }), 500


# -------------------- BANKING ROUTES --------------------

@admin_bp.route('/banking')
@admin_required
def banking():
    """Banking management page with transactions and settings."""
    admin_id = session.get("admin_id")
    feature_options = get_admin_feature_join_code_options('banking', admin_id=admin_id)
    selected_scope = require_admin_feature_scope(
        'banking',
        admin_id=admin_id,
        requested_block=request.args.get('settings_block'),
    )
    teacher_blocks = [option['block'] for option in feature_options]
    settings_block = selected_scope['block']

    # Get current banking settings for this class
    settings = None
    if settings_block:
        settings = BankingSettings.query.filter_by(
            class_id=selected_scope['class_id'],
            block=settings_block,
        ).first()

    # Create form and populate with existing data
    form = BankingSettingsForm()
    if settings:
        form.savings_apy.data = settings.savings_apy
        form.savings_monthly_rate.data = settings.savings_monthly_rate
        form.interest_calculation_type.data = settings.interest_calculation_type or 'simple'
        form.compound_frequency.data = settings.compound_frequency or 'monthly'
        form.interest_schedule_type.data = settings.interest_schedule_type
        form.interest_schedule_cycle_days.data = settings.interest_schedule_cycle_days
        form.interest_payout_start_date.data = settings.interest_payout_start_date
        form.overdraft_protection_enabled.data = settings.overdraft_protection_enabled
        form.overdraft_fee_enabled.data = settings.overdraft_fee_enabled
        form.overdraft_fee_type.data = settings.overdraft_fee_type
        form.overdraft_fee_flat_amount.data = settings.overdraft_fee_flat_amount
        form.overdraft_fee_progressive_1.data = settings.overdraft_fee_progressive_1
        form.overdraft_fee_progressive_2.data = settings.overdraft_fee_progressive_2
        form.overdraft_fee_progressive_3.data = settings.overdraft_fee_progressive_3
        form.overdraft_fee_progressive_cap.data = settings.overdraft_fee_progressive_cap

    # Get filter and pagination parameters
    student_q = request.args.get('student', '').strip()
    block_q = request.args.get('block', '')
    account_q = request.args.get('account', '')
    type_q = request.args.get('type', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = 50

    # Get admin's class_ids
    admin_id = session.get('admin_id')
    teacher_join_codes = _get_admin_owned_join_codes(admin_id)
    teacher_class_ids = [
        class_id for (class_id,) in db.session.query(ClassEconomy.class_id)
        .filter(ClassEconomy.join_code.in_(teacher_join_codes)).all() if class_id
    ]

    # Base query joining Transaction with Seat and Student
    query = (
        db.session.query(Transaction, Student, Seat)
        .join(Seat, Transaction.seat_id == Seat.id)
        .join(Student, Seat.student_id == Student.id)
        .filter(Transaction.class_id.in_(teacher_class_ids))
    )

    # Apply filters
    if student_q:
        # Since first_name is encrypted, we cannot use `ilike`.
        # We must fetch students, decrypt names, and filter in Python.
        matching_student_ids = []
        # Handle if the query is a student ID
        if student_q.isdigit():
            matching_student_ids.append(int(student_q))

        # Handle if the query is a name
        all_students = _scoped_students().all()
        for s in all_students:
            # The full_name property will decrypt the first_name
            if student_q.lower() in s.full_name.lower():
                matching_student_ids.append(s.id)

        # If there are any matches (by ID or name), filter the query
        if matching_student_ids:
            query = query.filter(Student.id.in_(matching_student_ids))
        else:
            # If no students match, return no results
            query = query.filter(sa.false())

    if block_q:
        query = query.filter(Student.block == block_q)
    if account_q:
        query = query.filter(Transaction.account_type == account_q)
    if type_q:
        query = query.filter(Transaction.type == type_q)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Transaction.timestamp >= start_date_obj)
        except ValueError:
            flash("Invalid start date format. Please use YYYY-MM-DD.", "danger")
    if end_date:
        # P1-1 Fix: Prevent SQL injection by validating and parsing date in Python
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            # Add one day to include entire end_date (safe in Python, not SQL)
            end_date_inclusive = end_date_obj + timedelta(days=1)
            query = query.filter(Transaction.timestamp < end_date_inclusive)
        except ValueError:
            flash("Invalid end date format. Please use YYYY-MM-DD.", "danger")

    # Count total for pagination
    total_transactions = query.count()
    total_pages = math.ceil(total_transactions / per_page) if total_transactions else 1

    # Get paginated results
    recent_transactions = (
        query.order_by(Transaction.timestamp.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )

    # Build transaction list for template
    transactions = []
    for tx, student, seat in recent_transactions:
        transactions.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'student_id': student.id,
            'student_name': student.full_name,
            'student_block': student.block,
            'amount': tx.amount,
            'account_type': tx.account_type,
            'description': tx.description,
            'type': tx.type,
            'is_void': tx.is_void
        })

    # Get all students for stats
    students = _scoped_students().all()

    # Calculate banking stats through the ledger authority for the selected class only.
    total_checking = Decimal('0.00')
    total_savings = Decimal('0.00')
    students_with_savings = 0
    selected_class_id = selected_scope['class_id']
    for student in students:
        seat_id = get_seat_id_for_class(student.id, selected_class_id)
        if seat_id:
            checking_balance, savings_balance = get_available_balances(seat_id, selected_class_id)
        else:
            checking_balance, savings_balance = Decimal('0.00'), Decimal('0.00')
        total_checking += checking_balance
        total_savings += savings_balance
        if savings_balance > 0:
            students_with_savings += 1
    total_deposits = total_checking + total_savings

    # Calculate average savings balance (across all students, including those with 0)
    average_savings_balance = total_savings / len(students) if len(students) > 0 else 0

    # Get all blocks for filter
    blocks = sorted(set(s.block for s in students))

    # Build class_labels_by_block dictionary
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    # Build join_codes_by_block dictionary
    join_codes_by_block = _get_join_codes_by_block(admin_id, blocks)

    # Get transaction types for filter (filtered to this teacher's students)
    transaction_types = (
        db.session.query(Transaction.type)
        .filter(Transaction.class_id.in_(teacher_class_ids))
        .filter(Transaction.type.isnot(None))
        .distinct()
        .all()
    )
    transaction_types = sorted([t[0] for t in transaction_types if t[0]])


    return render_template(
        'admin_banking.html',
        settings=settings,
        form=form,
        transactions=transactions,
        total_checking=total_checking,
        total_savings=total_savings,
        total_deposits=total_deposits,
        students_with_savings=students_with_savings,
        total_students=len(students),
        average_savings_balance=average_savings_balance,
        blocks=blocks,
        class_labels_by_block=class_labels_by_block,
        join_codes_by_block=join_codes_by_block,
        transaction_types=transaction_types,
        page=page,
        total_pages=total_pages,
        total_transactions=total_transactions,
        current_page="banking",
        format_utc_iso=format_utc_iso,
        settings_block=settings_block,
        teacher_blocks=teacher_blocks,
        selected_feature_scope=selected_scope,
    )


@admin_bp.route('/banking/settings', methods=['POST'])
@admin_required
def banking_settings_update():
    """Update banking settings for a specific class or all classes."""
    from app.models import _quantize_currency

    admin_id = session.get("admin_id")
    form = BankingSettingsForm()

    if form.validate_on_submit():
        selected_scope = require_admin_feature_scope(
            'banking',
            admin_id=admin_id,
            requested_block=request.form.get('settings_block'),
        )
        settings_block = selected_scope['block']
        apply_to_all = request.form.get('apply_to_all') == 'true'

        feature_options = get_admin_feature_join_code_options('banking', admin_id=admin_id)
        enabled_blocks = [option['block'] for option in feature_options if option.get('block')]
        blocks_to_update = enabled_blocks if apply_to_all else [settings_block]

        try:
            payload_hash = hashlib.sha256(
                json.dumps(
                    {
                        "class_id": selected_scope["class_id"],
                        "settings_block": settings_block,
                        "apply_to_all": apply_to_all,
                        "blocks_to_update": sorted([b for b in blocks_to_update if b]),
                        "savings_apy": str(form.savings_apy.data or 0),
                        "savings_monthly_rate": str(form.savings_monthly_rate.data or 0),
                        "interest_calculation_type": form.interest_calculation_type.data or 'simple',
                        "compound_frequency": form.compound_frequency.data or 'monthly',
                        "interest_schedule_type": form.interest_schedule_type.data,
                        "interest_schedule_cycle_days": form.interest_schedule_cycle_days.data or 30,
                        "overdraft_protection_enabled": bool(form.overdraft_protection_enabled.data),
                        "overdraft_fee_enabled": bool(form.overdraft_fee_enabled.data),
                        "overdraft_fee_type": form.overdraft_fee_type.data,
                    },
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()[:16]
            idempotency_key = (
                f"feat:banking:settings-update:{selected_scope['class_id']}:{payload_hash}"
            )

            db.session.rollback()
            with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
                for block in blocks_to_update:
                    scope_for_block = require_admin_feature_scope(
                        'banking',
                        admin_id=admin_id,
                        requested_block=block,
                        allow_default=False,
                    )
                    # Get or create settings for this class
                    settings = BankingSettings.query.filter_by(
                        class_id=scope_for_block['class_id'],
                        block=block,
                    ).first()
                    if not settings:
                        settings = BankingSettings(
                            class_id=scope_for_block['class_id'],
                            block=block,
                        )
                        db.session.add(settings)

                    # Update settings from form
                    settings.savings_apy = Decimal(str(form.savings_apy.data or 0)).quantize(Decimal('0.000001'))
                    settings.savings_monthly_rate = Decimal(str(form.savings_monthly_rate.data or 0)).quantize(Decimal('0.000001'))
                    settings.interest_calculation_type = form.interest_calculation_type.data or 'simple'
                    settings.compound_frequency = form.compound_frequency.data or 'monthly'
                    settings.interest_schedule_type = form.interest_schedule_type.data
                    settings.interest_schedule_cycle_days = form.interest_schedule_cycle_days.data or 30
                    settings.interest_payout_start_date = form.interest_payout_start_date.data
                    settings.overdraft_protection_enabled = form.overdraft_protection_enabled.data
                    settings.overdraft_fee_enabled = form.overdraft_fee_enabled.data
                    settings.overdraft_fee_type = form.overdraft_fee_type.data
                    settings.overdraft_fee_flat_amount = _quantize_currency(form.overdraft_fee_flat_amount.data or Decimal('0.00'))
                    settings.overdraft_fee_progressive_1 = _quantize_currency(form.overdraft_fee_progressive_1.data or Decimal('0.00'))
                    settings.overdraft_fee_progressive_2 = _quantize_currency(form.overdraft_fee_progressive_2.data or Decimal('0.00'))
                    settings.overdraft_fee_progressive_3 = _quantize_currency(form.overdraft_fee_progressive_3.data or Decimal('0.00'))
                    settings.overdraft_fee_progressive_cap = (
                        _quantize_currency(form.overdraft_fee_progressive_cap.data)
                        if form.overdraft_fee_progressive_cap.data is not None
                        else None
                    )
                    settings.updated_at = utc_now()

            if apply_to_all:
                flash(f'Banking settings applied to all {len(blocks_to_update)} classes!', 'success')
            else:
                flash('Banking settings updated successfully!', 'success')
            current_app.logger.info(f"Banking settings updated by admin for {len(blocks_to_update)} class(es)")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update banking settings: {e}", exc_info=True)
            flash('Error updating banking settings.', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')

    # Redirect back to the same settings block
    settings_block = request.form.get('settings_block')
    return redirect(url_for('admin.banking', settings_block=settings_block))


# -------------------- DELETION REQUESTS --------------------

@admin_bp.route('/account-delete', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
@admin_required
def account_delete():
    """
    Teacher-managed account deletion.

    Deletion executes immediately after timed confirmation gate checks.
    """
    admin_id = session.get('admin_id')
    admin = db.session.get(Admin, admin_id)
    if not admin:
        flash('Unable to load your account.', 'error')
        return redirect(url_for('admin.login'))
    admin_username = admin.get_display_name().strip()

    if request.method == 'POST':
        request_type = request.form.get('request_type')  # account only

        # Validate
        if request_type != 'account':
            flash('Invalid request type. Only account deletion is supported.', 'error')
            return redirect(url_for('admin.account_delete'))

        expected_phrase = f'CONFIRM DELETE {admin_username} ACCOUNT'.upper()
        gate_phrase = str(request.form.get('gate_phrase', '')).strip().upper()
        if gate_phrase != expected_phrase:
            flash('Account deletion blocked: confirmation phrase did not match.', 'error')
            return redirect(url_for('admin.account_delete'))

        try:
            gate_countdown_seconds = int(request.form.get('gate_countdown_seconds', 0))
        except (TypeError, ValueError):
            gate_countdown_seconds = 0
        if gate_countdown_seconds < 30:
            flash('Account deletion blocked: 30-second safety countdown is required.', 'error')
            return redirect(url_for('admin.account_delete'))

        try:
            gate_hold_seconds = float(request.form.get('gate_hold_seconds', 0))
        except (TypeError, ValueError):
            gate_hold_seconds = 0.0
        if gate_hold_seconds < 10:
            flash('Account deletion blocked: 10-second hold is required.', 'error')
            return redirect(url_for('admin.account_delete'))

        try:
            _hard_delete_teacher_account_scope(admin_id)
            db.session.delete(admin)
            db.session.flush()

            session.pop("is_admin", None)
            session.pop("admin_id", None)
            session.pop("last_activity", None)
            flash('Your account and associated class data were permanently deleted.', 'success')
            return redirect(url_for('admin.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error deleting teacher account: {e}")
            flash('Error deleting account.', 'error')
            return redirect(url_for('admin.account_delete'))

    return render_template(
        'admin_account_delete.html',
        current_page="account_delete",
        admin_username=admin_username,
    )


@admin_bp.route('/help-support', methods=['GET', 'POST'])
@admin_required
def help_support():
    """Teacher support center with direct ticket submission to sysadmin."""

    admin_id = session.get('admin_id')
    selected_join_code = (_get_current_admin_join_code(admin_id) or '').strip()

    teacher_class_rows = ClassEconomy.query.filter_by(teacher_id=admin_id).all()
    class_scope_map = {}
    for ce_row in teacher_class_rows:
        if ce_row.join_code and ce_row.join_code not in class_scope_map:
            class_scope_map[ce_row.join_code] = ce_row.display_name or ce_row.join_code

    class_scope_options = [
        {'join_code': join_code, 'label': label}
        for join_code, label in sorted(class_scope_map.items(), key=lambda item: item[1] or item[0])
    ]

    category_to_report_type = {
        'general': 'comment',
        'bug': 'bug',
        'feature': 'suggestion',
    }

    def _build_scope_metadata(join_code_value, class_label_value, category_value):
        return (
            f"SUPPORT_SCOPE|join_code={join_code_value}|class_label={class_label_value}|category={category_value}"
        )

    def _parse_scope_metadata(raw_description):
        if not raw_description:
            return None, None, None, raw_description

        first_line, _, body = raw_description.partition("\n")
        if not first_line.startswith("SUPPORT_SCOPE|"):
            return None, None, None, raw_description

        metadata = {}
        for token in first_line.split("|")[1:]:
            key, _, value = token.partition("=")
            if key and value:
                metadata[key] = value

        cleaned_body = body.strip() if body else raw_description
        return (
            metadata.get('join_code'),
            metadata.get('class_label'),
            metadata.get('category'),
            cleaned_body,
        )

    if not class_scope_options and request.method == 'GET':
        # Inform teachers who have no classes that they must create one before submitting tickets.
        flash(
            "You don't have any classes yet. Please add a class from your dashboard before submitting a support ticket.",
            "info",
        )

    if request.method == 'POST':
        # If the teacher has no classes, prevent submission and provide a clear message.
        if not class_scope_options:
            flash(
                "You cannot submit a support ticket until you have at least one class. "
                "Please add a class from your dashboard first.",
                "error",
            )
            return redirect(url_for('admin.help_support'))
        issue_category = request.form.get('issue_category', 'general').strip().lower()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        expected_behavior = request.form.get('expected_behavior', '').strip()
        page_url = request.form.get('page_url', '').strip()
        class_label = class_scope_map.get(selected_join_code)

        if not selected_join_code or selected_join_code not in class_scope_map:
            flash("Please select one of your classes before submitting a support ticket.", "error")
            return redirect(url_for('admin.help_support'))

        if issue_category not in category_to_report_type:
            flash("Please select a valid support ticket category.", "error")

            anonymous_code = generate_anonymous_code(f"admin:{admin_id}")
            my_reports_query = UserReport.query.filter_by(anonymous_code=anonymous_code, user_type='teacher')
            if selected_join_code:
                my_reports_query = my_reports_query.filter_by(error_code=selected_join_code)
            my_reports = my_reports_query.order_by(UserReport.submitted_at.desc()).limit(20).all()

            return render_template(
                'admin_support_tickets.html',
                current_page='help',
                page_title='Help & Support',
                class_scope_options=class_scope_options,
                selected_join_code=selected_join_code,
                my_reports=my_reports,
                help_content=HELP_ARTICLES['teacher'],
                format_utc_iso=format_utc_iso,
                form_issue_category=issue_category,
                form_title=title,
                form_description=description,
                form_expected_behavior=expected_behavior,
                form_page_url=page_url,
            )

        if not title or not description or not issue_category:
            flash("Please provide a category, title, and description for your support ticket.", "error")

            anonymous_code = generate_anonymous_code(f"admin:{admin_id}")
            my_reports_query = UserReport.query.filter_by(anonymous_code=anonymous_code, user_type='teacher')
            if selected_join_code:
                my_reports_query = my_reports_query.filter_by(error_code=selected_join_code)
            my_reports = my_reports_query.order_by(UserReport.submitted_at.desc()).limit(20).all()

            return render_template(
                'admin_support_tickets.html',
                current_page='help',
                page_title='Help & Support',
                class_scope_options=class_scope_options,
                selected_join_code=selected_join_code,
                my_reports=my_reports,
                help_content=HELP_ARTICLES['teacher'],
                format_utc_iso=format_utc_iso,
                form_issue_category=issue_category,
                form_title=title,
                form_description=description,
                form_expected_behavior=expected_behavior,
                form_page_url=page_url,
            )
        anonymous_code = generate_anonymous_code(f"admin:{admin_id}")
        metadata_header = _build_scope_metadata(selected_join_code, class_label or 'Unknown', issue_category)
        scoped_description = f"{metadata_header}\n\n{description}"

        try:
            report = UserReport(
                anonymous_code=anonymous_code,
                user_type='teacher',
                report_type=category_to_report_type[issue_category],
                title=title,
                description=scoped_description,
                expected_behavior=expected_behavior if expected_behavior else None,
                page_url=page_url if page_url else None,
                ip_address=get_real_ip(),
                user_agent=request.headers.get('User-Agent'),
                status='new'
            )

            db.session.add(report)
            db.session.flush()

            flash("Your support ticket has been submitted directly to system administration.", "success")
            return redirect(url_for('admin.help_support'))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.error("Error submitting report", exc_info=True)
            flash("An error occurred while submitting your ticket. Please try again.", "error")
            return redirect(url_for('admin.help_support'))

    anonymous_code = generate_anonymous_code(f"admin:{admin_id}")
    my_reports_query = UserReport.query.filter_by(anonymous_code=anonymous_code, user_type='teacher')

    reports = my_reports_query.order_by(UserReport.submitted_at.desc()).limit(50).all()
    my_reports = []
    for report in reports:
        scope_join_code, class_label, issue_category, clean_description = _parse_scope_metadata(report.description)
        if selected_join_code and scope_join_code != selected_join_code:
            continue
        my_reports.append({
            'report': report,
            'scope_join_code': scope_join_code,
            'class_label': class_label,
            'issue_category': issue_category,
            'clean_description': clean_description,
        })
        if len(my_reports) >= 20:
            break

    return render_template('admin_support_tickets.html',
                         current_page='help',
                         page_title='Help & Support',
                         class_scope_options=class_scope_options,
                         selected_join_code=selected_join_code,
                         my_reports=my_reports,
                         help_content=HELP_ARTICLES['teacher'],
                         format_utc_iso=format_utc_iso)


# -------------------- FEATURE SETTINGS --------------------

@admin_bp.route('/feature-settings', methods=['GET', 'POST'])
@admin_required
def feature_settings():
    """
    Manage feature toggles for all periods/blocks.

    GET: Display feature settings page with toggles for each period
    POST: Update feature settings
    """
    admin_id = session.get('admin_id')

    # Get all configured periods for this teacher from class economy anchors.
    period_rows = (
        db.session.query(ClassEconomy.section)
        .filter(
            ClassEconomy.teacher_id == admin_id,
            ClassEconomy.section.isnot(None),
        )
        .all()
    )
    periods = sorted({
        (section or '').strip().upper()
        for (section,) in period_rows
        if (section or '').strip()
    })
    join_codes_by_period = _get_join_codes_by_block(admin_id, periods)

    period_settings = {}
    for period in periods:
        scoped_features = get_class_feature_settings(admin_id, block=period)
        period_settings[period] = scoped_features["features"] if scoped_features else FeatureSettings.get_defaults()

    return render_template(
        'admin_feature_settings.html',
        current_page='feature_settings',
        periods=periods,
        period_settings=period_settings,
        join_codes_by_period=join_codes_by_period,
        features_list=[
            ('payroll_enabled', 'Payroll', 'payments', 'Time tracking and student payments'),
            ('insurance_enabled', 'Insurance', 'shield', 'Insurance policies and claims'),
            ('banking_enabled', 'Banking', 'account_balance', 'Savings accounts and interest'),
            ('rent_enabled', 'Rent', 'home', 'Housing costs and payments'),
            ('hall_pass_enabled', 'Hall Pass', 'confirmation_number', 'Bathroom and water break passes'),
            ('store_enabled', 'Store', 'storefront', 'Marketplace for student rewards'),
        ]
    )


@admin_bp.route('/feature-settings/period/<period>', methods=['POST'])
@admin_required
def update_period_feature_settings(period):
    """Update feature settings for a specific period via AJAX."""
    admin_id = session.get('admin_id')

    try:
        data = request.get_json()
        period = period.strip().upper()

        scope = resolve_class_scope(admin_id, block=period)
        if not scope:
            return jsonify({'status': 'error', 'message': 'Class scope not found for this period.'}), 400

        current_features = get_class_feature_settings(admin_id, block=period)
        enabled_features = {
            feature_name
            for feature_name in ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')
            if current_features and current_features["features"].get(f'{feature_name}_enabled')
        }
        for feature_name in ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store'):
            if feature_name in data:
                if bool(data[feature_name]):
                    enabled_features.add(feature_name)
                else:
                    enabled_features.discard(feature_name)

        payload_hash = hashlib.sha256(
            json.dumps({"period": period, "data": data}, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = f"feat:class:feature-settings:update:{scope['class_id']}:{payload_hash}"

        # Ensure FEAT owns transaction boundary for feature-toggle writes.
        db.session.rollback()
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            replace_enabled_class_features(scope["class_id"], enabled_features)

        return jsonify({
            'status': 'success',
            'message': f'Settings updated for Period {period}',
            'settings': get_class_feature_settings(admin_id, block=period)["features"]
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating period feature settings: {e}")
        return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500


@admin_bp.route('/feature-settings/copy', methods=['POST'])
@admin_required
def copy_feature_settings():
    """Copy feature settings from one period to other periods."""
    admin_id = session.get('admin_id')

    try:
        data = request.get_json()
        source_period = data.get('source_period', '').strip().upper()
        target_periods = [p.strip().upper() for p in data.get('target_periods', [])]

        if not source_period or not target_periods:
            return jsonify({
                'status': 'error',
                'message': 'Source period and at least one target period are required.'
            }), 400

        # Get source settings
        source_scope = resolve_class_scope(admin_id, block=source_period)
        if not source_scope:
            return jsonify({
                'status': 'error',
                'message': f'Class scope not found for period {source_period}.'
            }), 400
        source_dict = get_class_feature_settings(admin_id, block=source_period)["features"]

        payload_hash = hashlib.sha256(
            json.dumps(
                {"source_period": source_period, "target_periods": target_periods},
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:class:feature-settings:copy:{source_scope['class_id']}:{payload_hash}"
        )

        # Ensure FEAT owns transaction boundary for feature-toggle writes.
        db.session.rollback()

        # Copy to target periods
        copied_count = 0
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            for period in target_periods:
                if period == source_period:
                    continue  # Skip copying to self

                target_scope = resolve_class_scope(admin_id, block=period)
                if not target_scope:
                    return jsonify({
                        'status': 'error',
                        'message': f'Class scope not found for period {period}.'
                    }), 400

                replace_enabled_class_features(
                    target_scope["class_id"],
                    {
                        feature_name
                        for feature_name in ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')
                        if source_dict.get(f'{feature_name}_enabled')
                    },
                )
                copied_count += 1

        return jsonify({
            'status': 'success',
            'message': f'Settings copied from Period {source_period} to {copied_count} period(s).'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error copying feature settings: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to copy settings due to an internal error.'}), 500


# -------------------- ANNOUNCEMENTS --------------------

@admin_bp.route('/announcements')
@admin_required
def announcements():
    """
    Manage class announcements for the currently selected class context.
    """
    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    class_context = _resolve_admin_class_context(scoped_admin_id)
    if not class_context:
        flash("Select a class from the sidebar before managing announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    selected_join_code = class_context["join_code"]

    # Get announcements for this teacher scoped to the active class context only.
    from app.models import Announcement
    announcements_list = Announcement.query.filter_by(
        teacher_id=scoped_admin_id,
        join_code=selected_join_code,
        system_admin_id=None  # Only teacher-created announcements
    ).order_by(Announcement.created_at.desc()).all()

    ann_class_row = ClassEconomy.query.filter_by(
        teacher_id=scoped_admin_id,
        join_code=selected_join_code,
    ).first()

    active_class_label = (ann_class_row.display_name or selected_join_code) if ann_class_row else selected_join_code

    return render_template(
        'admin_announcements.html',
        announcements=announcements_list,
        active_class_label=active_class_label,
        active_join_code=selected_join_code,
    )


@admin_bp.route('/announcements/create', methods=['GET', 'POST'])
@admin_required
def announcement_create():
    """Create a new announcement for the currently selected class context."""
    from app.forms import AnnouncementForm
    from app.models import Announcement

    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    class_context = _resolve_admin_class_context(scoped_admin_id)
    if not class_context:
        flash("Select a class from the sidebar before creating announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    selected_join_code = class_context["join_code"]
    ann_create_class_row = ClassEconomy.query.filter_by(
        teacher_id=scoped_admin_id,
        join_code=selected_join_code,
    ).first()

    # Keep periods field for form validation, but lock it to active class context.
    form = AnnouncementForm()
    form.periods.choices = [(selected_join_code, selected_join_code)]
    if request.method == 'GET':
        form.periods.data = [selected_join_code]

    if form.validate_on_submit():
        try:
            announcement = Announcement(
                teacher_id=scoped_admin_id,
                join_code=selected_join_code,
                title=form.title.data,
                message=form.message.data,
                priority=form.priority.data,
                is_active=form.is_active.data,
                expires_at=form.expires_at.data
            )
            db.session.add(announcement)

            db.session.flush()
            flash(f'Announcement "{form.title.data}" created successfully!', 'success')

            return redirect(url_for('admin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating announcement: {e}")
            flash('An error occurred while creating the announcement.', 'danger')

    return render_template(
        'admin_announcement_form.html',
        form=form,
        action='Create',
        active_join_code=selected_join_code,
        active_class_label=(ann_create_class_row.display_name or selected_join_code) if ann_create_class_row else selected_join_code,
        active_block=ann_create_class_row.section if ann_create_class_row else None,
    )


@admin_bp.route('/announcements/edit/<int:announcement_id>', methods=['GET', 'POST'])
@admin_required
def announcement_edit(announcement_id):
    """Edit an existing announcement."""
    from app.forms import AnnouncementForm
    from app.models import Announcement

    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    class_context = _resolve_admin_class_context(scoped_admin_id)
    if not class_context:
        flash("Select a class from the sidebar before editing announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=scoped_admin_id,
        join_code=class_context["join_code"],
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    # Get the class info for this announcement
    ann_edit_class_row = ClassEconomy.query.filter_by(
        teacher_id=scoped_admin_id,
        join_code=announcement.join_code
    ).first()

    form = AnnouncementForm(obj=announcement)
    # Don't need periods field for editing - it's locked to one period
    del form.periods

    if form.validate_on_submit():
        try:
            announcement.title = form.title.data
            announcement.message = form.message.data
            announcement.priority = form.priority.data
            announcement.is_active = form.is_active.data
            announcement.expires_at = form.expires_at.data
            announcement.updated_at = utc_now()

            db.session.flush()

            flash(f'Announcement "{announcement.title}" updated successfully!', 'success')
            return redirect(url_for('admin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating announcement: {e}")
            flash('An error occurred while updating the announcement.', 'danger')

    return render_template(
        'admin_announcement_form.html',
        form=form,
        announcement=announcement,
        teacher_block=ann_edit_class_row,
        action='Edit'
    )


@admin_bp.route('/announcements/delete/<int:announcement_id>', methods=['POST'])
@admin_required
def announcement_delete(announcement_id):
    """Delete an announcement."""
    from app.models import Announcement

    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    class_context = _resolve_admin_class_context(scoped_admin_id)
    if not class_context:
        flash("Select a class from the sidebar before deleting announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=scoped_admin_id,
        join_code=class_context["join_code"],
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    try:
        title = announcement.title
        db.session.delete(announcement)
        db.session.flush()

        flash(f'Announcement "{title}" deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting announcement: {e}")
        flash('An error occurred while deleting the announcement.', 'danger')

    return redirect(url_for('admin.announcements'))


@admin_bp.route('/announcements/toggle/<int:announcement_id>', methods=['POST'])
@admin_required
def announcement_toggle(announcement_id):
    """Toggle announcement active status."""
    from app.models import Announcement

    current_admin = get_current_admin()
    scoped_admin_id = current_admin.id if current_admin else session.get('admin_id')
    class_context = _resolve_admin_class_context(scoped_admin_id)
    if not class_context:
        return jsonify({'status': 'error', 'message': 'Select a class from the sidebar first.'}), 400

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=scoped_admin_id,
        join_code=class_context["join_code"],
    ).first()

    if not announcement:
        return jsonify({'status': 'error', 'message': 'Announcement not found'}), 404

    try:
        announcement.is_active = not announcement.is_active
        announcement.updated_at = utc_now()
        db.session.flush()

        return jsonify({
            'status': 'success',
            'is_active': announcement.is_active,
            'message': f'Announcement {"activated" if announcement.is_active else "deactivated"}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling announcement: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An error occurred while toggling the announcement. Please try again.'}), 500


# -------------------- TEACHER ONBOARDING --------------------

@admin_bp.route('/onboarding/status', methods=['GET'])
@admin_required
def onboarding_status():
    """Get onboarding task completion status for the Getting Started widget."""
    admin_id = session.get('admin_id')
    join_code = session.get('current_join_code')

    try:
        # GET endpoint must remain read-only: do not create records here.
        onboarding_record = get_teacher_onboarding(admin_id)

        # Check if widget is dismissed
        if onboarding_record and onboarding_record.widget_dismissed:
            return jsonify({
                'status': 'success',
                'dismissed': True,
                'completion': {}
            })

        # If join_code is not set in session, try to use the teacher's first ClassEconomy row
        if not join_code:
            first_class_row = ClassEconomy.query.filter_by(teacher_id=admin_id).order_by(ClassEconomy.class_id).first()
            if first_class_row:
                join_code = first_class_row.join_code
                # Set it in session for future requests
                session['current_join_code'] = join_code

        # No early return when a teacher has no class periods yet.
        # The widget should still render the full checklist so teachers can
        # see all setup tasks immediately.

        # Get all blocks for this teacher (for account-wide onboarding checks)
        all_blocks = list({
            (section or '').strip().upper()
            for (section,) in db.session.query(ClassEconomy.section).filter_by(teacher_id=admin_id).all()
            if (section or '').strip()
        })

        # Initialize completion status
        completion = {
            'roster': False,
            'payroll': False,
            'store': False,
            'banking': False,
            'rent': False,
            'insurance': False,
            'hall_pass': False,
            'personalization': False,
            'passkey': False
        }
        data_completed = completion.copy()
        skipped_tasks = {}

        widget_task_statuses = (onboarding_record.widget_tasks_completed if onboarding_record else {}) or {}
        for task_name, status in widget_task_statuses.items():
            if status is True or status == 'skipped':
                skipped_tasks[task_name] = True

        # ACCOUNT-WIDE ONBOARDING CHECKS
        # Onboarding is per teacher account, not per class section
        # If ANY of the teacher's class sections has a feature set up, mark as complete

        # Roster: has at least one student in ANY class OR marked complete
        # Use StudentTeacher to get all students for this teacher
        student_count = StudentTeacher.query.filter_by(teacher_id=admin_id).count()
        data_completed['roster'] = student_count > 0

        class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=admin_id).subquery()
        # Payroll: has payroll settings configured for ANY class OR marked complete
        payroll_settings = (
            PayrollSettings.query
            .filter(PayrollSettings.class_id.in_(sa.select(class_ids_subq)))
            .first()
        )
        data_completed['payroll'] = payroll_settings is not None

        # Store: has at least one store item for ANY block OR marked complete
        store_items = (
            StoreItem.query
            .filter(StoreItem.class_id.in_(sa.select(class_ids_subq)))
            .count()
        )
        data_completed['store'] = store_items > 0

        # Banking: has banking settings configured for ANY block OR marked complete
        banking_settings = (
            BankingSettings.query
            .filter(BankingSettings.class_id.in_(sa.select(class_ids_subq)))
            .first()
        )
        data_completed['banking'] = banking_settings is not None

        # Rent: has rent settings configured for ANY block OR marked complete
        rent_settings = (
            RentSettings.query.with_entities(RentSettings.id)
            .filter(RentSettings.class_id.in_(sa.select(class_ids_subq)))
            .first()
        )
        data_completed['rent'] = rent_settings is not None

        # Insurance: has at least one insurance policy for ANY block OR marked complete
        insurance_policies = (
            InsurancePolicy.query
            .filter(InsurancePolicy.class_id.in_(sa.select(class_ids_subq)))
            .count()
        )
        data_completed['insurance'] = insurance_policies > 0

        # Hall pass: check if hall pass settings exist for ANY block OR marked complete
        hall_pass_settings = (
            HallPassSettings.query
            .filter(HallPassSettings.class_id.in_(sa.select(class_ids_subq)))
            .first()
        )
        data_completed['hall_pass'] = hall_pass_settings is not None

        # Personalization: check if ANY ClassEconomy row has a display_name set OR marked complete
        has_label = bool(
            ClassEconomy.query.filter(
                ClassEconomy.teacher_id == admin_id,
                ClassEconomy.display_name.isnot(None),
                ClassEconomy.display_name != '',
            ).first()
        )
        data_completed['personalization'] = has_label

        # Passkey: check if at least one credential exists OR marked complete
        has_passkey = admin_has_passkeys(admin_id)
        data_completed['passkey'] = has_passkey

        for task_name in completion.keys():
            completion[task_name] = data_completed.get(task_name, False) or skipped_tasks.get(task_name, False)

        return jsonify({
            'status': 'success',
            'dismissed': False,
            'completion': completion,
            'data_completed': data_completed,
            'skipped': skipped_tasks
        })

    except Exception as e:
        current_app.logger.error(f"Error checking onboarding status: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to retrieve onboarding status'}), 500


@admin_bp.route('/onboarding', methods=['GET'])
@admin_required
def onboarding():
    """
    Legacy onboarding entry point.

    The guided onboarding wizard has been replaced by the Getting Started widget.
    Keep this route to satisfy legacy links/tests and redirect to the dashboard.
    """
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/onboarding/skip', methods=['POST'])
@admin_required
def onboarding_skip():
    """Mark onboarding as skipped for the current admin (legacy endpoint)."""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    get_or_create_teacher_onboarding(admin_id, utc_now())
    set_teacher_onboarding_skipped(admin_id, utc_now())
    db.session.flush()
    return jsonify({'status': 'success'})


@admin_bp.route('/onboarding/skip-task', methods=['POST'])
@admin_required
def onboarding_skip_task():
    """Mark an optional onboarding task as skipped."""
    admin_id = session.get('admin_id')

    try:
        data = request.get_json()
        task_name = data.get('task')

        if not task_name:
            return jsonify({'status': 'error', 'message': 'Task name required'}), 400

        # Get or create onboarding record
        set_teacher_onboarding_widget_task_status(
            admin_id,
            task_name=task_name,
            status='skipped',
            now=utc_now(),
        )

        db.session.flush()

        return jsonify({
            'status': 'success',
            'message': f'Task "{task_name}" marked as skipped'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error skipping task: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to skip task'}), 500


@admin_bp.route('/onboarding/dismiss-widget', methods=['POST'])
@admin_required
def onboarding_dismiss_widget():
    """Dismiss the Getting Started widget permanently."""
    admin_id = session.get('admin_id')

    try:
        # Get or create onboarding record
        set_teacher_onboarding_widget_dismissed(admin_id, dismissed=True, now=utc_now())

        db.session.flush()

        return jsonify({
            'status': 'success',
            'message': 'Getting Started widget dismissed'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dismissing widget: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to dismiss widget'}), 500


@admin_bp.route('/onboarding/undismiss-widget', methods=['POST'])
@admin_required
def onboarding_undismiss_widget():
    """Un-dismiss the Getting Started widget to show it again."""
    admin_id = session.get('admin_id')

    try:
        # Get onboarding record
        set_teacher_onboarding_widget_dismissed(admin_id, dismissed=False, now=utc_now())

        db.session.flush()

        return jsonify({
            'status': 'success',
            'message': 'Getting Started widget will appear again'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error un-dismissing widget: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to show widget'}), 500


# ==================== ECONOMY BALANCE CHECKER API ====================

@admin_bp.route('/api/economy/calculate-cwi', methods=['POST'])
@admin_required
def api_calculate_cwi():
    """
    Calculate CWI (Classroom Wage Index) based on payroll settings.

    Expected JSON payload:
    {
        "pay_rate": 15.0,          // Per hour rate
        "expected_weekly_hours": 5.0,
        "block": "A" (optional)
    }

    Returns CWI calculation with breakdown.
    """
    try:
        admin_id = session.get('admin_id')
        data = request.get_json()

        # Get pay rate and convert to per-minute (as stored in DB)
        pay_rate_per_hour = float(data.get('pay_rate', 15.0))
        pay_rate_per_minute = pay_rate_per_hour / 60.0
        expected_weekly_hours = float(data.get('expected_weekly_hours', 5.0))
        block = data.get('block')

        # Create a temporary PayrollSettings-like object for calculation
        class TempPayrollSettings:
            def __init__(self, pay_rate, time_unit='minutes', frequency_days=7, expected_weekly_hours=None):
                self.pay_rate = pay_rate
                self.time_unit = time_unit
                self.payroll_frequency_days = frequency_days
                self.expected_weekly_hours = expected_weekly_hours

        temp_settings = TempPayrollSettings(pay_rate_per_minute, expected_weekly_hours=expected_weekly_hours)

        # Calculate CWI
        checker = EconomyBalanceChecker(admin_id, block)
        cwi_calc = checker.calculate_cwi(temp_settings, expected_weekly_hours)

        recommendations = get_price_recommendation_context(checker.policy_mode, cwi_calc.cwi)

        return jsonify({
            'status': 'success',
            'cwi': cwi_calc.cwi,
            'breakdown': {
                'pay_rate_per_hour': pay_rate_per_hour,
                'pay_rate_per_minute': cwi_calc.pay_rate_per_minute,
                'expected_weekly_hours': expected_weekly_hours,
                'expected_weekly_minutes': cwi_calc.expected_weekly_minutes,
                'notes': cwi_calc.notes
            },
            'recommendations': recommendations
        })

    except Exception as e:
        current_app.logger.error(f"Error calculating CWI: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to calculate CWI'}), 500


def _resolve_admin_payroll_settings_for_block(admin_id: int, block: str | None):
    """
    Resolve payroll settings with class-first precedence when a block is selected.

    - If block is provided: resolve class-scoped settings for that block.
    - If block is absent: resolve first active settings row across admin-owned classes.
    """
    if block:
        class_id_row = (
            db.session.query(ClassEconomy.class_id)
            .filter(
                ClassEconomy.teacher_id == admin_id,
                ClassEconomy.section == block,
                ClassEconomy.class_id.isnot(None),
            )
            .first()
        )
        class_id = class_id_row[0] if class_id_row and class_id_row[0] else None
        if not class_id:
            raise NotFound("Payroll class scope is unavailable for the selected block.")

        scoped_settings = (
            PayrollSettings.query.filter(
                PayrollSettings.class_id == class_id,
                PayrollSettings.is_active.is_(True),
            )
            .order_by(desc(PayrollSettings.block.isnot(None)))
            .first()
        )
        if scoped_settings:
            return scoped_settings

        return (
            PayrollSettings.query.filter(
                PayrollSettings.class_id == class_id,
                PayrollSettings.block == block,
                PayrollSettings.is_active.is_(True),
            )
            .first()
        )

    class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=admin_id).subquery()
    return (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id.in_(sa.select(class_ids_subq)),
            PayrollSettings.is_active.is_(True),
        )
        .first()
    )


@admin_bp.route('/api/economy/analyze', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def api_economy_analyze():
    """
    Perform comprehensive economy balance analysis.

    Returns complete economy analysis including CWI, warnings, recommendations.
    """
    try:
        admin_id = session.get('admin_id')
        data = request.get_json() or {}
        block = data.get('block')

        try:
            payroll_settings = _resolve_admin_payroll_settings_for_block(admin_id, block)
        except NotFound:
            from app.feats.base import get_correlation_id
            operational_event_service.record(
                event_type="INVALID_CLASS_SCOPE",
                severity="warning",
                domain="economy",
                route=request.path,
                actor_id=admin_id,
                class_id=None,
                correlation_id=get_correlation_id(),
                details={
                    "reason": "missing_or_unresolvable_class_scope",
                    "endpoint": "economy_analyze",
                    "provided_class_id": (data or {}).get("class_id"),
                    "provided_join_code": (data or {}).get("join_code"),
                    "resolution_path": "denied",
                },
            )
            return jsonify({
                'status': 'error',
                'message': 'Please configure payroll settings first to calculate CWI.'
            }), 400

        if not payroll_settings:
            return jsonify({
                'status': 'error',
                'message': 'Please configure payroll settings first to calculate CWI.'
            }), 400
        checker = EconomyBalanceChecker(admin_id, block, class_id=getattr(payroll_settings, "class_id", None))

        # Get other economy features
        rent_settings = RentSettings.query.filter_by(
            teacher_id=admin_id,
            is_enabled=True
        ).first() if block is None else RentSettings.query.filter_by(
            teacher_id=admin_id,
            block=block,
            is_enabled=True
        ).first()

        class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=admin_id)
        scoped_class_id = None
        if block:
            class_id_row = (
                db.session.query(ClassEconomy.class_id)
                .filter(
                    ClassEconomy.teacher_id == admin_id,
                    ClassEconomy.section == block,
                    ClassEconomy.class_id.isnot(None),
                )
                .first()
            )
            scoped_class_id = class_id_row[0] if class_id_row and class_id_row[0] else None
            if not scoped_class_id:
                return jsonify({'status': 'error', 'message': 'Class scope is unavailable for the selected block.'}), 404

        insurance_policies_query = InsurancePolicy.query.filter(
            InsurancePolicy.class_id.in_(sa.select(class_ids_query.subquery())),
            InsurancePolicy.is_active.is_(True),
        )
        fines_query = PayrollFine.query.filter(
            PayrollFine.class_id.in_(sa.select(class_ids_query.subquery())),
            PayrollFine.is_active.is_(True),
        )
        store_items_query = StoreItem.query.filter(
            StoreItem.class_id.in_(sa.select(class_ids_query.subquery())),
            StoreItem.is_active.is_(True),
        )

        if scoped_class_id:
            insurance_policies_query = insurance_policies_query.filter(InsurancePolicy.class_id == scoped_class_id)
            fines_query = fines_query.filter(PayrollFine.class_id == scoped_class_id)
            store_items_query = store_items_query.filter(StoreItem.class_id == scoped_class_id)

        insurance_policies = insurance_policies_query.all()
        fines = fines_query.all()
        store_items = store_items_query.all()

        # Perform analysis
        # Use expected_weekly_hours from payroll_settings unless explicitly overridden in request
        from app.models import _quantize_currency
        expected_weekly_hours_override = data.get('expected_weekly_hours')

        if expected_weekly_hours_override is not None:
            expected_weekly_hours = _quantize_currency(expected_weekly_hours_override)
        else:
            expected_weekly_hours = None  # Will read from payroll_settings

        payload, _snapshot = _get_frozen_economy_analysis_payload(
            admin_id,
            block,
            checker,
            payroll_settings,
            rent_settings=rent_settings,
            insurance_policies=insurance_policies,
            fines=fines,
            store_items=store_items,
            expected_weekly_hours=expected_weekly_hours,
            persist_snapshot=True,
        )
        return jsonify(payload)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error analyzing economy: {e}")
        return jsonify({'status': 'error', 'message': 'An internal error occurred while analyzing the economy.'}), 500


@admin_bp.route('/api/economy/validate/<feature>', methods=['POST'])
@admin_required
def api_economy_validate(feature):
    """
    Validate a specific feature value against CWI.

    Features: 'rent', 'insurance', 'fine', 'store_item'

    Expected JSON payload:
    {
        "value": 100.0,
        "frequency": "weekly" (for insurance),
        "block": "A" (optional)
    }
    """
    try:
        from app.models import _quantize_currency
        admin_id = session.get('admin_id')
        data = request.get_json()

        value = _quantize_currency(data.get('value', '0'))
        block = data.get('block')
        feature = feature.lower()
        valid_features = ['rent', 'insurance', 'fine', 'store_item']
        if feature not in valid_features:
            return jsonify({
                'status': 'error',
                'message': f"Invalid feature type. Must be one of: {', '.join(valid_features)}"
            }), 400

        try:
            payroll_settings = _resolve_admin_payroll_settings_for_block(admin_id, block)
        except NotFound:
            from app.feats.base import get_correlation_id
            operational_event_service.record(
                event_type="INVALID_CLASS_SCOPE",
                severity="warning",
                domain="economy",
                route=request.path,
                actor_id=admin_id,
                class_id=None,
                correlation_id=get_correlation_id(),
                details={
                    "reason": "missing_or_unresolvable_class_scope",
                    "endpoint": "economy_validate",
                    "provided_class_id": (data or {}).get("class_id"),
                    "provided_join_code": (data or {}).get("join_code"),
                    "resolution_path": "denied",
                    "feature": feature,
                },
            )
            return jsonify({
                'status': 'warning',
                'message': 'Configure payroll first to get recommendations.',
                'is_valid': True,
                'warnings': []
            })

        if not payroll_settings:
            return jsonify({
                'status': 'warning',
                'message': 'Configure payroll first to get recommendations.',
                'is_valid': True,
                'warnings': []
            })

        # Calculate CWI
        checker = EconomyBalanceChecker(admin_id, block, class_id=getattr(payroll_settings, "class_id", None))
        # Use expected_weekly_hours from payroll_settings, not from request
        cwi_calc = checker.calculate_cwi(payroll_settings)
        cwi = cwi_calc.cwi
        expected_weekly_hours = cwi_calc.expected_weekly_minutes / 60.0

        warnings = []
        recommendations = {}
        ratio = None

        validation_kwargs = {
            'frequency': data.get('frequency', 'weekly'),
            'frequency_type': data.get('frequency_type', data.get('frequency', 'monthly')),
            'custom_frequency_value': data.get('custom_frequency_value'),
            'custom_frequency_unit': data.get('custom_frequency_unit'),
            # Insurance-specific parameters for coverage and period cap validation
            'max_claim_amount': data.get('max_claim_amount'),
            'max_payout_per_period': data.get('max_payout_per_period'),
            'claim_type': data.get('claim_type'),
        }

        warnings, recommendations, ratio = checker.validate_feature_value(
            feature,
            value,
            cwi,
            **validation_kwargs,
        )

        # Determine status based on warnings
        if warnings:
            # Check if there are critical warnings
            critical_warnings = [w for w in warnings if w.get('level') == 'critical']
            status = 'error' if critical_warnings else 'warning'
        else:
            status = 'success'

        return jsonify({
            'status': status,
            'is_valid': len([w for w in warnings if w.get('level') == 'critical']) == 0,
            'warnings': warnings,
            'recommendations': recommendations,
            'cwi': cwi,
            'ratio': ratio if feature != 'insurance' else None,
            'cwi_breakdown': {
                'pay_rate_per_hour': float(cwi_calc.pay_rate_per_minute) * 60,
                'pay_rate_per_minute': float(cwi_calc.pay_rate_per_minute),
                'expected_weekly_hours': float(expected_weekly_hours),
                'expected_weekly_minutes': float(cwi_calc.expected_weekly_minutes),
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error validating {feature}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to validate feature due to an internal error.'}), 500


# ==================== PASSKEY AUTHENTICATION (Official SDK Implementation) ====================

@admin_bp.route('/passkey/register/start', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def passkey_register_start():
    """
    Start passkey registration - Generate registration token.

    Official SDK Pattern: Create RegisterToken and get token from passwordless.dev
    """
    try:
        user = get_current_user()
        if not user or getattr(user.user_role, "value", user.user_role) != "teacher":
            abort(404)
        admin = resolve_admin_shadow_for_user(user)
        if not admin or admin.id != session.get('admin_id'):
            abort(404)

        # Generate registration token using official SDK
        user_id = f"user_{user.id}"
        username = session.get("admin_auth_username") or admin.teacher_public_id or f"teacher_{admin.id}"
        displayname = admin.get_display_name()

        token = create_register_token(user_id, username, displayname)

        return jsonify({
            "token": token,
            "apiKey": get_public_api_key()
        }), 200

    except ValueError as e:
        current_app.logger.error(f"Passwordless.dev configuration error: {e}")
        return jsonify({"error": "Passkey service not configured"}), 503
    except Exception as e:
        current_app.logger.error(f"Error starting passkey registration: {e}")
        return jsonify({"error": "Failed to start registration"}), 500


@admin_bp.route('/passkey/register/finish', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def passkey_register_finish():
    """
    Finish passkey registration - Save credential metadata.

    After frontend completes WebAuthn ceremony, store credential metadata.
    """
    try:
        admin_id = session.get('admin_id')
        data = request.get_json()

        # No need to check for or use 'token' in the request payload.

        # Note: Credential is stored on passwordless.dev servers
        # We just track that registration occurred for UX purposes
        authenticator_name = data.get('authenticatorName', 'Unnamed Passkey')

        # Save credential metadata (credential_id is optional, stored on passwordless.dev)
        create_admin_credential(
            teacher_id=admin_id,
            credential_id=None,  # Not needed - stored on passwordless.dev servers
            authenticator_name=authenticator_name,
        )
        db.session.flush()

        flash("Passkey registered successfully!", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error finishing passkey registration: {e}")
        return jsonify({"error": "Failed to register passkey"}), 500


@admin_bp.route('/passkey/auth/start', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_start():
    """
    Start passkey authentication - Return public API key.

    Official SDK Pattern: Frontend needs public API key to initiate signin
    """
    try:
        data = request.get_json()
        session.pop('passkey_auth_username', None)

        if not data or 'username' not in data:
            return jsonify({"error": "Missing username"}), 400

        username = normalize_auth_username(data['username'])

        user = find_canonical_user_by_auth_username(username, expected_role="teacher")
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        admin = resolve_admin_shadow_for_user(user)
        if not admin:
            return jsonify({"error": "Invalid credentials"}), 401

        # Check if user has passkeys
        has_passkeys = admin_has_passkeys(admin.id)
        if not has_passkeys:
            return jsonify({"error": "Invalid credentials"}), 401

        session['passkey_auth_username'] = username

        return jsonify({
            "apiKey": get_public_api_key()
        }), 200

    except ValueError as e:
        current_app.logger.error(f"Passwordless.dev configuration error: {e}")
        return jsonify({"error": "Passkey service not configured"}), 503
    except Exception as e:
        current_app.logger.error(f"Error starting passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 500


@admin_bp.route('/passkey/auth/finish', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_finish():
    """
    Finish passkey authentication - Verify token and create session.

    Official SDK Pattern: Verify signin token and create authenticated session
    """
    try:
        data = request.get_json()

        if not data or 'token' not in data:
            return jsonify({"error": "Missing token"}), 400

        # Verify token using official SDK
        verified_user = verify_signin_token(data['token'])

        # Extract canonical user ID from Passwordless user_id (format: "user_{id}").
        external_user_id = verified_user.user_id
        if not external_user_id or not external_user_id.startswith('user_'):
            return jsonify({"error": "Invalid user ID"}), 401

        try:
            canonical_user_id = int(external_user_id.replace('user_', ''))
        except ValueError:
            current_app.logger.error(f"Invalid userId format: {external_user_id}")
            return jsonify({"error": "Invalid user ID format"}), 401

        user = db.session.get(User, canonical_user_id)
        if not user or getattr(user.user_role, "value", user.user_role) != "teacher":
            return jsonify({"error": "Invalid user ID"}), 401
        admin = resolve_admin_shadow_for_user(user)
        if not admin:
            return jsonify({"error": "Admin not found"}), 401

        # Update credential last_used timestamp
        # Credentials are stored without credential_id (managed by passwordless.dev),
        # so update last_used for all credentials belonging to this admin.
        now = utc_now()
        touch_admin_credentials_last_used(admin.id, now)

        admin.last_login = now
        db.session.flush()

        # Create session
        auth_username = session.get('passkey_auth_username')
        session.clear()
        session['admin_id'] = admin.id
        session['is_admin'] = True
        session["user_id"] = user.id
        session['admin_auth_username'] = auth_username or admin.teacher_public_id
        session['last_activity'] = now.isoformat()
        set_admin_display_name_cache(admin_id=admin.id, display_name=admin.get_display_name())
        session.permanent = True

        redirect_url = url_for('admin.dashboard')
        if _admin_requires_username_migration(admin):
            session['force_admin_username_migration'] = True
            redirect_url = url_for('admin.username_migration')

        return jsonify({
            "success": True,
            "redirect": redirect_url
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error finishing passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 401


@admin_bp.route('/passkey/list', methods=['GET'])
@admin_required
def passkey_list():
    """List all passkeys for current teacher."""
    try:
        admin_id = session.get('admin_id')
        credentials = list_admin_credentials(admin_id)

        return jsonify({
            "passkeys": [{
                "id": cred.id,
                "name": cred.authenticator_name or "Unnamed Passkey",
                "created_at": cred.created_at.isoformat() if cred.created_at else None,
                "last_used": cred.last_used.isoformat() if cred.last_used else None
            } for cred in credentials]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing passkeys: {e}")
        return jsonify({"error": "Failed to list passkeys"}), 500


@admin_bp.route('/passkey/<int:passkey_id>/delete', methods=['DELETE'])
@admin_required
@limiter.limit("10 per minute")
def passkey_delete(passkey_id):
    """Delete a passkey."""
    try:
        admin_id = session.get('admin_id')
        credential = get_admin_credential(passkey_id, admin_id)

        if not credential:
            return jsonify({"error": "Passkey not found"}), 404

        delete_admin_credential(passkey_id, admin_id)
        db.session.flush()

        flash("Passkey deleted successfully", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting passkey: {e}")
        return jsonify({"error": "Failed to delete passkey"}), 500


@admin_bp.route('/passkey/settings')
@admin_required
def passkey_settings():
    """Passkey management page."""
    admin_id = session.get('admin_id')
    admin = db.get_or_404(Admin, admin_id)
    credentials = list_admin_credentials(admin_id)

    return render_template('admin_passkey_settings.html',
                         admin=admin,
                         credentials=credentials)


# ==================== ISSUE RESOLUTION SYSTEM - TEACHER ROUTES ====================

def _resolve_issue_id_from_ref(issue_ref: str) -> int | None:
    if issue_ref.isdigit():
        return int(issue_ref)
    return resolve_opaque_ref('issue', issue_ref)

@admin_bp.route('/issues')
@admin_required
def issues_queue():
    """
    Teacher issue review queue.
    Shows all student-submitted issues for this teacher's classes.
    """
    from app.models import Issue
    from app.utils.issue_categories import init_default_categories

    admin_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    if join_code and not _admin_owns_join_code(admin_id, join_code):
        join_code = None

    # INV-ARC-007: keep GET route read-only.
    if not getattr(g, "read_only", False):
        init_default_categories()

    # Filter by join code if one is selected, otherwise show all issues for this teacher
    if join_code:
        issues_query = Issue.query.filter_by(teacher_id=admin_id, join_code=join_code)
    else:
        issues_query = Issue.query.filter_by(teacher_id=admin_id)

    # Get issues by status (canonical + legacy compatibility)
    pending_issues = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_OPEN,
            Issue.STATUS_TEACHER_REVIEW,
            'submitted',
            'teacher_review',
        ])
    ).order_by(Issue.submitted_at.desc()).all()

    resolved_issues = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_TEACHER_FINAL_REVIEW,
            Issue.STATUS_DEV_RESOLVED,
            'teacher_resolved',
            'developer_resolved',
        ])
    ).order_by(Issue.updated_at.desc()).limit(50).all()

    escalated_issues = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            'elevated',
            'developer_review',
        ])
    ).order_by(Issue.escalated_at.desc()).all()

    return render_template('admin_issues_queue.html',
                         current_page='issues',
                         page_title='Student Issues',
                         pending_issues=pending_issues,
                         resolved_issues=resolved_issues,
                         escalated_issues=escalated_issues,
                         issue_ref_for=lambda issue_id: make_opaque_ref('issue', issue_id),
                         format_utc_iso=format_utc_iso)


@admin_bp.route('/issues/<issue_ref>')
@admin_required
def view_issue(issue_ref):
    """View detailed information about a specific issue."""
    from app.models import Issue

    admin_id = session.get('admin_id')

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    # Get the issue and verify it belongs to this teacher
    issue = Issue.query.filter_by(id=issue_id, teacher_id=admin_id).first_or_404()

    return render_template('admin_view_issue.html',
                         current_page='issues',
                         page_title=f'Issue #{issue.id}',
                         issue=issue,
                         issue_ref=make_opaque_ref('issue', issue.id),
                         format_utc_iso=format_utc_iso)


@admin_bp.route('/issues/<issue_ref>/resolve', methods=['POST'])
@admin_required
def resolve_issue(issue_ref):
    """
    Resolve an issue at the teacher level.
    Can apply various resolution actions depending on issue type.
    """
    from app.models import Issue, Transaction
    from app.utils.issue_helpers import update_issue_status, record_resolution_action

    admin_id = session.get('admin_id')

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    # Get the issue and verify it belongs to this teacher
    issue = Issue.query.filter_by(id=issue_id, teacher_id=admin_id).first_or_404()

    action_type = request.form.get('action_type')
    teacher_notes = request.form.get('teacher_notes', '').strip()
    allowed_statuses = {
        Issue.STATUS_OPEN,
        Issue.STATUS_TEACHER_REVIEW,
        Issue.STATUS_DEV_RESOLVED,
        'submitted',
        'teacher_review',
        'developer_resolved',
    }

    if issue.status not in allowed_statuses:
        flash("This ticket cannot be resolved in its current state.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    try:
        # Apply resolution based on action type
        if action_type == 'reverse_transaction' and issue.related_transaction_id:
            transaction = db.session.get(Transaction, issue.related_transaction_id)
            if (
                not transaction
                or transaction.student_id != issue.student_id
                or transaction.is_void
                or transaction.join_code != issue.join_code
            ):
                flash("The related transaction could not be reversed for this issue.", "error")
                return redirect(url_for('admin.view_issue', issue_ref=issue_ref))

            reversal_tx = ledger_service.compensate_posted_transaction(
                transaction,
                description=f"Issue #{issue.id} reversal for transaction #{transaction.id}",
                compensation_type='issue_reversal',
            )

            issue.teacher_resolution = 'Transaction Reversed'
            record_resolution_action(
                issue,
                'reverse_transaction',
                'teacher',
                admin_id,
                action_description=f"Reversed transaction #{transaction.id} with reversal #{reversal_tx.id}",
                related_transaction_id=reversal_tx.id,
                amount_changed=float(reversal_tx.amount),
                before_value=str(transaction.amount),
                after_value=str(reversal_tx.amount),
            )

        elif action_type == 'compensating_transaction' and issue.related_transaction_id:
            # Append-only correction: create a compensating ledger entry.
            transaction = db.session.get(Transaction, issue.related_transaction_id)
            if not transaction or transaction.student_id != issue.student_id or transaction.is_void:
                flash("The related transaction could not be found for this issue.", "error")
                return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

            compensating_tx = ledger_service.compensate_posted_transaction(
                transaction,
                description=f"Issue #{issue.id} compensating entry for transaction #{transaction.id}",
                compensation_type='issue_compensation',
            )

            issue.teacher_resolution = 'Compensating Transaction Posted'
            record_resolution_action(
                issue,
                'compensating_transaction',
                'teacher',
                admin_id,
                action_description=f"Posted compensating transaction #{compensating_tx.id} for transaction #{transaction.id}",
                related_transaction_id=compensating_tx.id,
                amount_changed=float(compensating_tx.amount),
                before_value=str(transaction.amount),
                after_value=str(compensating_tx.amount),
            )

        elif action_type == 'manual_adjustment':
            # Teacher handles manually (no automatic action)
            issue.teacher_resolution = 'Manual Adjustment'
            record_resolution_action(
                issue, 'manual_adjustment', 'teacher', admin_id,
                action_description=teacher_notes
            )

        elif action_type == 'deny_issue':
            # Deny the issue
            denial_reason = request.form.get('denial_reason', '').strip()
            issue.teacher_resolution = 'Denied'
            teacher_notes = denial_reason  # Reassign to preserve denial reason
            record_resolution_action(
                issue, 'deny_issue', 'teacher', admin_id,
                action_description=denial_reason
            )
        else:
            flash("Please select a valid resolution action.", "error")
            return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

        # Move to teacher final review; closure is a separate explicit action.
        update_issue_status(issue, Issue.STATUS_TEACHER_FINAL_REVIEW, 'teacher', admin_id, notes=teacher_notes)
        issue.teacher_resolved_at = utc_now()
        issue.teacher_notes = teacher_notes

        db.session.flush()

        flash("Issue moved to teacher final review. Close it after confirming classroom state.", "success")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolving issue {issue_id}", exc_info=True)
        flash("An error occurred while resolving the issue. Please try again.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))


@admin_bp.route('/issues/<issue_ref>/escalate', methods=['POST'])
@admin_required
def escalate_issue(issue_ref):
    """
    Escalate an issue to sysadmin (developer).
    Teacher marks the issue for developer investigation.
    """
    from app.models import Issue
    from app.utils.issue_helpers import update_issue_status

    admin_id = session.get('admin_id')

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    # Get the issue and verify it belongs to this teacher
    issue = Issue.query.filter_by(id=issue_id, teacher_id=admin_id).first_or_404()

    escalation_reason = request.form.get('escalation_reason', '').strip()
    diagnostic_note = request.form.get('diagnostic_note', '').strip()
    share_class_name = request.form.get('share_class_name') == 'on'
    allowed_statuses = {
        Issue.STATUS_OPEN,
        Issue.STATUS_TEACHER_REVIEW,
        'submitted',
        'teacher_review',
    }

    if issue.status not in allowed_statuses:
        flash("Only tickets under teacher review can be escalated.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    if not escalation_reason:
        flash("Please provide an escalation reason.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    try:
        # Update issue with escalation details
        issue.escalation_reason = escalation_reason
        issue.teacher_diagnostic_note = diagnostic_note
        issue.share_class_name_with_sysadmin = share_class_name
        issue.escalated_at = utc_now()

        # Update status
        update_issue_status(
            issue,
            Issue.STATUS_ESCALATED_TO_DEV,
            'teacher',
            admin_id,
            notes=f"Escalated: {escalation_reason}",
        )

        db.session.flush()

        flash("Issue escalated to developer successfully.", "success")
        return redirect(url_for('admin.issues_queue'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error escalating issue {issue_id}", exc_info=True)
        flash("An error occurred while escalating the issue. Please try again.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))


@admin_bp.route('/issues/<issue_ref>/close', methods=['POST'])
@admin_required
def close_issue(issue_ref):
    """Teacher-only closure after final review."""
    from app.models import Issue
    from app.utils.issue_helpers import update_issue_status

    admin_id = session.get('admin_id')
    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)
    issue = Issue.query.filter_by(id=issue_id, teacher_id=admin_id).first_or_404()

    allowed_statuses = {
        Issue.STATUS_TEACHER_FINAL_REVIEW,
        'teacher_resolved',
    }
    if issue.status not in allowed_statuses:
        flash("This ticket is not ready to be closed.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    resolution_summary = request.form.get('resolution_summary', '').strip()
    if not resolution_summary:
        flash("Please include a closure summary.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    try:
        if issue.teacher_notes:
            issue.teacher_notes = f"{issue.teacher_notes}\n\nClosure Summary: {resolution_summary}"
        else:
            issue.teacher_notes = resolution_summary
        issue.closed_at = utc_now()
        issue.closed_by_type = 'teacher'
        update_issue_status(issue, Issue.STATUS_CLOSED, 'teacher', admin_id, notes=resolution_summary)
        db.session.flush()
        flash("Issue closed.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.error(f"Error closing issue {issue_id}", exc_info=True)
        flash("An error occurred while closing the issue. Please try again.", "error")

    return redirect(url_for('admin.issues_queue'))
