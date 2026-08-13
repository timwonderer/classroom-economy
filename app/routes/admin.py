"""
Admin routes for Classroom Token Hub.

Contains all admin/teacher-facing functionality including dashboard, student management,
store management, insurance, payroll, attendance tracking, and data import/export.
"""

import csv
import html
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
from app.utils.canonical_temporal_resolver import (
    utc_now,
    ensure_utc,
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
    CLASS_LEVEL_EVALUATION,
)
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, redirect, url_for, flash, request, session,
    jsonify, Response, send_file, current_app, abort, g
)
from urllib.parse import urlparse
from sqlalchemy import desc, text, or_, and_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import sqlalchemy as sa
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import pyotp
import pytz
import bleach
from werkzeug.exceptions import HTTPException, NotFound

from app.extensions import db, limiter
from app.feats.base import feat_shell, FEATContext, InvariantViolation, generate_correlation_id
from app.access.scope import Scope
from app.access import AccessScopeDenied, resolve_scope
from app.models import (
    ClassEconomy, Transaction, TransactionStatus, AttendanceSession, StoreItem, StoreItemVisibility,
    # Legacy tap table removed; use attendance_sessions (DOM-PROD-001).
    # StudentItem removed — student_items unauthorized; use store_purchases + redemption_events (DOM-STORE-001)
    # StoreItemBlock removed — store_item_blocks unauthorized; use store_item_visibility (DOM-STORE-001)
    # RedemptionAuditLog / RedemptionAuditAction / RedemptionAuditSource removed — use redemption_events (DOM-STORE-001)
    # Legacy tap reason enum removed with the legacy tap table.
    # StorePurchase, Entitlement, EntitlementConsumption, GrantType, RedemptionEvent, etc. deleted per Phase 2 migration
    RentSettings,
    HallPassLog, HallPassSettings, PayrollSettings,
    BankingSettings,
    ClassFeature,
    Announcement, Issue, IssueCategory, IssueStatusHistory, IssueResolutionAction, Seat,
    LedgerBalanceSnapshot, User, UserRole, _quantize_currency,
    ObligationAssessment,
    AttendanceReasonCode, IdentityProfile, PayrollEvent, PolicyVersion,
    EntitlementEvent, PendingAction,
)
from app.auth import (
    admin_required,
    establish_teacher_session,
    find_canonical_user_by_auth_username,
    get_current_user,
)
from app.services.context_resolver import CanonicalContext
from app.forms import (
    AdminLoginForm, AdminSignupForm, AdminTOTPConfirmForm, AdminRecoveryForm, AdminResetCredentialsForm, StoreItemForm,
    AdminClaimProcessForm, PayrollSettingsForm,
    ManualPaymentForm, BankingSettingsForm
)
# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso, generate_anonymous_code, render_template_with_fallback as render_template
from app.utils.join_code import generate_join_code, get_display_join_code
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
    REBALANCE_ACTIVATION_NEXT_RENEWAL,
    REBALANCE_ACTIVATION_NEXT_PAYROLL,
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
from app.services.announcement_service import (
    create_class_announcement,
    delete_class_announcement,
    update_class_announcement,
)
from app.services.insurance_policy_service import (
    create_policy_version,
    get_insurance_policy_version,
    list_insurance_policy_versions,
    schedule_policy_deletion,
)
# TODO (Phase 4): insurance_claim_feat deleted; use FEAT-STOR-003 instead
# from app.feats.insurance_claim_feat import execute_claim_approval, execute_claim_rejection
# TODO (Phase 4): store_entitlement_service deleted
# from app.services.store_entitlement_service import get_insurance_claim, get_last_entitlement_end_for_policy_version, derive_display_status
from app.services.classroom_setup import (
    create_class_with_roster,
    create_teacher_account_with_class,
    create_pending_student_seat,
    delete_seat_with_profile,
    create_roster_student_seat,
    update_or_create_roster_seat,
)
from app.services.payroll_settings_service import (
    upsert_payroll_settings_for_blocks,
    update_expected_weekly_hours_for_blocks,
)
from app.services.store_service import (
    create_store_item,
    deactivate_store_item,
    create_store_item_block,
    deactivate_linked_store_item,
    delete_rent_item,
)
from app.services.view_model_builders import build_identity_profile_view, build_store_management_view
from app.services.class_configuration_economic_service import build_economic_view
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_class_economy_by_join_code,
    get_all_classes_by_teacher,
    get_teacher_classes_by_ids,
    verify_teacher_owns_class,
    get_payroll_settings,
    get_rent_settings,
    get_banking_settings,
    get_hall_pass_settings,
    has_personalized_class,
)
from app.services.admin_identity_service import delete_admin_account_rows
from app.services.admin_settings_service import create_rent_settings, create_banking_settings
from app.services.issue_service import create_support_ticket
from app.utils.ip_handler import get_real_ip
from app.utils.turnstile import verify_turnstile_token
from app.utils.name_utils import hash_last_name_parts, verify_last_name_parts
from app.utils.help_content import HELP_ARTICLES
from app.utils.encryption import encrypt_totp, decrypt_totp
from app.utils.passwordless_client import (
    create_register_token,
    verify_signin_token,
    get_public_api_key
)
from app.utils.display_name_session import (
    set_admin_display_name_cache,
    clear_admin_display_name_cache,
)
from app.utils.opaque_refs import make_opaque_ref, resolve_opaque_ref
from app.utils.auth_username import (
    normalize_auth_username,
    build_hashed_username_fields,
)
from app.utils.student_deletion import (
    hard_delete_student_if_orphaned,
    remove_student_from_teacher_scope,
)
from app.utils.seat_scope import seat_scoped_filter, transaction_scope_filter
from app.feats.admin_adjustment_feat import execute_admin_adjustments
from app.feats.prod import record_attendance_session, record_payroll_event
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
# execute_insurance_claim_resolution removed — insurance_claim_feat.py deleted; insurance feature broken pending DOM-OBL-001 migration
from app.feats.transaction_void_feat import (
    ImmediatePurchaseNotVoidable,
    UsedDelayedPurchaseNotVoidable,
    execute_void_transaction,
)
from app.hash_utils import get_random_salt, hash_hmac, hash_username, hash_username_lookup
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    get_batch_attendance_events,
    calculate_seconds_in_memory,
)
from app.services.balance_service import get_batch_balances_by_class_seat
from app.services.attendance_service import calculate_unpaid_attendance_seconds as calculate_prod_attendance_seconds
from app.services.hall_pass_request_queue import list_pending_hall_pass_requests_for_class
from app.services import access_policy_service, ledger_service, obligations_service
from app.services.entitlement_service import get_hall_pass_balance, grant_hall_passes, remove_hall_passes
from app.services import operational_event_service
from app.services.ledger_service import get_available_balances
from app.services.admin_identity_service import (
    admin_has_passkeys,
    create_admin_credential,
    delete_admin_credential,
    delete_admin_credentials_for_user,
    get_admin_credential,
    list_admin_credentials,
    touch_admin_credentials_last_used,
)
from app.services.recovery_service import (
    create_recovery_request_with_seats,
    delete_recovery_rows_for_user,
    find_recovery_request_by_resume_pin,
    get_active_recovery_request_for_user,
    get_recovery_request_by_id,
    invalidate_recovery_codes,
    list_recovery_codes_for_request,
    mark_recovery_request_verified,
    save_recovery_progress,
)
# TODO (Phase 4): insurance_eligibility deleted; use canonical tools + FEAT-STOR-003
# from app.utils.insurance_eligibility import (
#     collect_reimbursed_source_tx_ids,
#     compute_waiting_end_class_for_enrollment,
#     evaluate_claim_transaction_eligibility,
#     resolve_claim_type,
#     CLAIM_REASON_ALREADY_CLAIMED,
#     CLAIM_REASON_DELAY_USE_EXPIRED,
#     CLAIM_REASON_DELAY_USE_NOT_USED,
#     CLAIM_REASON_HARD_DENY_CATEGORY,
#     CLAIM_REASON_INTERNAL_TRANSFER,
#     CLAIM_REASON_PREMIUM_NOT_CURRENT,
#     CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS,
#     CLAIM_REASON_TIME_LIMIT_EXCEEDED,
#     CLAIM_REASON_UNCLASSIFIED_TRANSACTION,
#     CLAIM_REASON_WAITING_PERIOD,
# )
# TODO (Phase 4): store_entitlement_service deleted
# from app.services.store_entitlement_service import get_insurance_claim, list_insurance_claims
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
# Synthetic roster-import values
PLACEHOLDER_CREDENTIAL = "LEGACY0"  # Synthetic roster-import credential
PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"  # Marks synthetic roster entries
PLACEHOLDER_LAST_INITIAL = "P"  # Synthetic roster placeholder initial

# Module-level cache for schema table-name lookups (keyed by DB URL to be app-config safe).
_table_names_cache: dict[str, set[str]] = {}
_table_columns_cache: dict[tuple[str, str], set[str]] = {}
_table_names_cache_lock = threading.Lock()

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

_BANKING_REDIRECT_QUERY_KEYS = {
    "student",
    "account",
    "type",
    "start_date",
    "end_date",
    "page",
    "settings_block",
}

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
    """Resolve request-scoped class_id from an explicit class selector."""
    endpoint = request.endpoint or ''

    if request.method == 'GET':
        class_candidate = request.args.get('class_id')
    elif request.is_json:
        payload = request.get_json(silent=True) or {}
        class_candidate = payload.get('class_id')
    else:
        class_candidate = request.form.get('class_id')

    if class_candidate:
        normalized_class_id = (class_candidate or '').strip()
        if normalized_class_id:
            return normalized_class_id

    return None


def _admin_write_has_join_code_conflict(canonical_context=None) -> bool:
    if canonical_context is None or request.method == 'GET':
        return False

    requested_class_id = _get_requested_admin_class_id()
    if not requested_class_id:
        return False

    session_class_id = (getattr(canonical_context, "class_id", None) or '').strip()
    if not session_class_id:
        return True

    return requested_class_id != session_class_id


def _admin_request_has_join_code_conflict(canonical_context=None) -> bool:
    """Return True when request-supplied class selector disagrees with active class context."""
    if canonical_context is None:
        return False

    requested_class_id = _get_requested_admin_class_id()
    if not requested_class_id:
        return False

    session_class_id = (getattr(canonical_context, "class_id", None) or '').strip()
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


def _resolve_admin_class_context(canonical_context=None) -> dict | None:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return None

    user_id = canonical_context.user_id
    candidate_class_id = (getattr(canonical_context, "class_id", None) or '').strip() or None
    if not candidate_class_id:
        return None

    class_row = verify_teacher_owns_class(candidate_class_id, user_id)
    if not class_row:
        return None

    return {
        'class_id': class_row.class_id,
        'join_code': get_display_join_code(class_row.class_id),
    }


def _handle_mismatched_admin_class_context():
    canonical_context = getattr(g, "canonical_context", None)
    user_id = canonical_context.user_id if canonical_context else None
    current_app.logger.error(
        "Blocked admin write with mismatched class context",
        extra={
            'user_id': user_id,
            'endpoint': request.endpoint,
            'method': request.method,
            'path': request.path,
            'session_join_code': _get_teacher_user_join_code(canonical_context),
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
    canonical_context = getattr(g, "canonical_context", None)
    user_id = canonical_context.user_id if canonical_context else None
    if not user_id:
        return None

    current_class_id = (getattr(canonical_context, "class_id", None) or '').strip()
    if current_class_id:
        return None

    current_app.logger.error(
        "Blocked admin write without class context",
        extra={
            'user_id': user_id,
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

    canonical_context = getattr(g, "canonical_context", None)
    if canonical_context and _route_uses_admin_class_context():
        context = _resolve_admin_class_context(canonical_context)
        if context:
            g.admin_class_context = context
            g.admin_join_code = context['join_code']

        if _admin_request_has_join_code_conflict(canonical_context):
            return _handle_mismatched_admin_class_context()

        if _route_requires_admin_class_context() and _admin_write_has_join_code_conflict(canonical_context):
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
        scope = resolve_feature_class_for_class(g.admin_class_context["class_id"], feature_name)
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


def _get_teacher_user_join_code(canonical_context=None) -> str | None:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return None
    user_id = canonical_context.user_id
    current_class_id = (getattr(canonical_context, "class_id", None) or '').strip()
    if not current_class_id:
        return None
    class_row = verify_teacher_owns_class(current_class_id, user_id)
    if not class_row:
        return None
    return get_display_join_code(class_row.class_id)


def get_admin_feature_settings_for_class_id(canonical_context=None, class_id: str | None = None) -> dict:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return ClassFeature.defaults_dict()

    resolved_class_id = (class_id or getattr(canonical_context, "class_id", None) or "").strip()
    if not resolved_class_id:
        return ClassFeature.defaults_dict()

    class_row = verify_teacher_owns_class(resolved_class_id, canonical_context.user_id)
    if not class_row:
        return ClassFeature.defaults_dict()

    scoped_features = get_class_feature_settings_for_class(class_row.class_id)
    return scoped_features["features"] if scoped_features else ClassFeature.defaults_dict()


def is_admin_feature_enabled(canonical_context: CanonicalContext, feature_name: str) -> bool:
    if canonical_context is None or not getattr(canonical_context, "class_id", None):
        return False
    resolved_class_id = canonical_context.class_id
    scope = resolve_feature_class_for_class(resolved_class_id, feature_name) if resolved_class_id else None
    return bool(scope["enabled"]) if scope else False


def get_admin_feature_join_code_options(feature_name: str, canonical_context=None) -> list[dict[str, str]]:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return []
    resolved_admin_user_id = canonical_context.user_id

    classes = sorted(
        get_all_classes_by_teacher(resolved_admin_user_id),
        key=lambda c: (c.display_name or "", c.class_id),
    )
    options: list[dict[str, str]] = []
    seen_class_ids: set[str] = set()
    for cls in classes:
        class_id, section, display_name = cls.class_id, cls.section, cls.display_name
        if not class_id or class_id in seen_class_ids:
            continue
        seen_class_ids.add(class_id)
        scope = resolve_feature_class_for_class(class_id, feature_name)
        if not scope or not scope["enabled"]:
            continue
        normalized_block = (section or "").strip().upper()
        label = display_name or (f"Period {normalized_block}" if normalized_block else scope["join_code"])
        options.append({
            'join_code': scope["join_code"],
            'class_id': scope["class_id"],
            'block': normalized_block,
            'label': label,
        })
    return options


def resolve_admin_feature_join_code(feature_name: str, canonical_context=None) -> str | None:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return None

    options = get_admin_feature_join_code_options(feature_name, canonical_context=canonical_context)
    enabled_join_codes = {option['join_code'] for option in options}
    current_class_id = (getattr(canonical_context, "class_id", None) or "").strip()
    if current_class_id:
        current_class = verify_teacher_owns_class(current_class_id, canonical_context.user_id)
        current_join_code = get_display_join_code(current_class.class_id) if current_class else None
        if current_join_code and current_join_code in enabled_join_codes:
            return current_join_code

    return options[0]['join_code'] if options else None


def require_admin_feature_scope(
    feature_name: str,
    *,
    canonical_context=None,
    requested_block: str | None = None,
    allow_default: bool = True,
) -> dict:
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        abort(404)

    options = get_admin_feature_join_code_options(feature_name, canonical_context=canonical_context)
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


def _build_teacher_block_dedupe_key(class_id: str, first_name: str, last_name: str) -> str:
    """Build deterministic dedupe key: class_id|normalized_full_name."""
    normalized_full_name = _normalize_full_name_for_dedupe(first_name, last_name)
    dedupe_input = f"{class_id}|{normalized_full_name}".encode()
    return hash_hmac(dedupe_input, b"")[:8]


def _find_admin_by_auth_username(username: str):
    """Lookup the canonical admin record by hashed auth username."""
    normalized = normalize_auth_username(username)
    if not normalized:
        return None

    lookup_hash = hash_username_lookup(normalized)
    return User.query.filter_by(
        username_lookup_hash=lookup_hash,
        user_role=UserRole.TEACHER,
    ).first()


def _auth_username_exists(username: str, *, exclude_admin_id: int | None = None) -> bool:
    normalized = normalize_auth_username(username)
    if not normalized:
        return False
    lookup_hash = hash_username_lookup(normalized)
    user = User.query.filter_by(username_lookup_hash=lookup_hash).first()
    if user:
        if exclude_admin_id is not None:
            excluded_admin = db.session.get(User, exclude_admin_id)
            if excluded_admin and excluded_admin.username_lookup_hash == lookup_hash:
                return False
        return True

    admin = _find_admin_by_auth_username(username)
    if not admin:
        return False
    if exclude_admin_id is not None and admin.id == exclude_admin_id:
        return False
    return True



def _build_admin_auth_fields(username: str, *, existing_salt: bytes | None = None) -> tuple[bytes, str, str]:
    return build_hashed_username_fields(username, existing_salt=existing_salt)


# -------------------- DASHBOARD & QUICK ACTIONS --------------------


def _get_teacher_blocks(canonical_context):
    """Get sorted list of blocks from the current teacher user's Seat roster."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return []
    user_id = canonical_context.user_id
    class_id = (getattr(canonical_context, "class_id", None) or "").strip() or None

    # Derive blocks from ClassEconomy (canonical class anchor) for the current teacher.
    query = (
        db.session.query(ClassEconomy.section)
        .filter(
            ClassEconomy.teacher_user_id == user_id,
            ClassEconomy.section.isnot(None),
        )
    )
    if class_id:
        query = query.filter(ClassEconomy.class_id == class_id)
    rows = query.all()
    return sorted({(section or "").strip().upper() for (section,) in rows if (section or "").strip()})


def _get_teacher_seat_for_class(class_id: str):
    """Return the teacher seat for a class, if present."""
    if not class_id:
        return None
    return Seat.query.filter_by(class_id=class_id, role="teacher").order_by(Seat.id.asc()).first()


def _resolve_block_class_ids(canonical_context, blocks):
    """Resolve display labels to canonical class IDs for the current teacher."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not blocks:
        return []

    user_id = canonical_context.user_id
    class_id = (getattr(canonical_context, "class_id", None) or "").strip() or None
    rows = (
        db.session.query(ClassEconomy.section, ClassEconomy.class_id)
        .filter(
            ClassEconomy.teacher_user_id == user_id,
            ClassEconomy.class_id.isnot(None),
        )
        .all()
    )
    wanted_blocks = {(block or "").strip().upper() for block in blocks if (block or "").strip()}
    if not wanted_blocks:
        return []

    resolved_class_ids = [
        resolved_class_id
        for section, resolved_class_id in rows
        if (section or "").strip().upper() in wanted_blocks and resolved_class_id
    ]
    if class_id:
        resolved_class_ids = [resolved_class_id for resolved_class_id in resolved_class_ids if resolved_class_id == class_id]
    return resolved_class_ids


def _count_rent_waiver_periods(settings, waiver) -> int:
    """Return how many rent periods a canonical waiver covers."""
    from app.routes.student import _add_rent_period, _get_rent_period_delta

    if not settings or not waiver or not waiver.coverage_start_time or not waiver.coverage_end_time:
        return 0

    delta = _get_rent_period_delta(settings)
    current = ensure_utc(waiver.coverage_start_time)
    end = ensure_utc(waiver.coverage_end_time)
    count = 0

    while current and end and current <= end:
        count += 1
        next_date = _add_rent_period(current, delta)
        if next_date <= current:
            break
        current = next_date

    return count


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

def _get_class_labels_for_blocks(canonical_context, blocks):
    """Return mapping of block -> class display_name for the given admin without N+1 queries."""

    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not blocks:
        return {}

    class_ids = _resolve_block_class_ids(canonical_context, blocks)
    if not class_ids:
        return {block: block for block in blocks}

    rows = (
        db.session.query(ClassEconomy.section, ClassEconomy.display_name)
        .filter(ClassEconomy.class_id.in_(class_ids))
        .all()
    )
    labels = {section: (display_name or section) for section, display_name in rows}

    for block in blocks:
        labels.setdefault(block, block)

    return labels


def _get_join_codes_by_block(canonical_context, blocks):
    """Return mapping of block -> join_code for the given admin without N+1 queries."""

    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not blocks:
        return {}

    class_ids = _resolve_block_class_ids(canonical_context, blocks)
    if not class_ids:
        return {}

    rows = (
        db.session.query(ClassEconomy.section, ClassEconomy.class_id)
        .filter(ClassEconomy.class_id.in_(class_ids))
        .all()
    )
    return {
        section: get_display_join_code(resolved_class_id)
        for section, resolved_class_id in rows
        if resolved_class_id and get_display_join_code(resolved_class_id)
    }


def _get_class_ids_by_block(canonical_context, blocks):
    """Return mapping of block -> class_id for the given admin without N+1 queries."""

    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not blocks:
        return {}

    class_ids = _resolve_block_class_ids(canonical_context, blocks)
    if not class_ids:
        return {}

    rows = (
        db.session.query(ClassEconomy.section, ClassEconomy.class_id)
        .filter(ClassEconomy.class_id.in_(class_ids))
        .all()
    )
    return {section: resolved_class_id for section, resolved_class_id in rows if resolved_class_id}


def _build_payroll_preview_state(students, class_ids_by_block):
    """Aggregate payroll preview data from PROD attendance/payroll facts."""
    students_by_class_id: dict[str, dict[int, Seat]] = defaultdict(dict)

    for student in students:
        class_id = getattr(student, "class_id", None)
        if class_id:
            students_by_class_id[class_id][student.id] = student

    summary_by_class_id: dict[str, dict[int, Decimal]] = {}
    anchor_by_class_id: dict[str, datetime | None] = {}
    updated_at_by_class_id: dict[str, datetime] = {}
    total_summary: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for class_id, students_map in students_by_class_id.items():
        class_students = list(students_map.values())

        economy = get_class_economy(class_id)
        if not economy:
            continue

        setting = (
            PayrollSettings.query
            .filter(
                PayrollSettings.class_id == class_id,
                PayrollSettings.is_active.is_(True),
            )
            .order_by(PayrollSettings.updated_at.desc(), PayrollSettings.id.desc())
            .first()
        )
        rate_per_second = (
            Decimal(str(setting.pay_rate)) / Decimal("60")
            if setting and setting.pay_rate is not None
            else Decimal("0.25") / Decimal("60")
        )

        seat_ids = [seat.id for seat in class_students]
        latest_payroll_events = (
            PayrollEvent.query
            .filter(
                PayrollEvent.class_id == class_id,
                PayrollEvent.target_seat_id.in_(seat_ids),
                PayrollEvent.payroll_event_type == "payroll",
            )
            .order_by(
                PayrollEvent.target_seat_id.asc(),
                PayrollEvent.recorded_at.desc(),
                PayrollEvent.id.desc(),
            )
            .all()
            if seat_ids
            else []
        )
        latest_payroll_by_seat_id = {}
        for event in latest_payroll_events:
            latest_payroll_by_seat_id.setdefault(event.target_seat_id, event)

        anchor = (
            max((event.recorded_at for event in latest_payroll_by_seat_id.values()), default=None)
        )

        summary = {}
        for seat in class_students:
            last_payroll = latest_payroll_by_seat_id.get(seat.id)
            attendance_seconds = calculate_prod_attendance_seconds(
                seat.id,
                class_id,
                last_payroll.recorded_at if last_payroll else None,
                ctx=g.canonical_context,
            )
            summary[seat.id] = (Decimal(attendance_seconds) * rate_per_second).quantize(Decimal("0.01"))

        anchor_by_class_id[class_id] = anchor
        summary_by_class_id[class_id] = summary
        if anchor is not None:
            updated_at_by_class_id[class_id] = ensure_utc(anchor)
        for seat_id, amount in summary.items():
            total_summary[seat_id] += Decimal(str(amount))

    latest_updated_at = max(updated_at_by_class_id.values()) if updated_at_by_class_id else None
    return {
        "summary_by_class_id": summary_by_class_id,
        "anchor_by_class_id": anchor_by_class_id,
        "updated_at_by_class_id": updated_at_by_class_id,
        "total_summary": dict(total_summary),
        "latest_updated_at": latest_updated_at,
    }


def _seat_scope_subquery_for_class(class_id: str, *, include_unassigned: bool = False):
    """Return a subquery of seat IDs scoped to one class by class_id."""
    canonical_context = getattr(g, "canonical_context", None)
    user_id = canonical_context.user_id if canonical_context else None
    if not user_id or not class_id:
        return sa.select(Seat.id).where(sa.false()).subquery()

    query = (
        db.session.query(Seat.id)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            ClassEconomy.teacher_user_id == user_id,
            Seat.class_id == class_id,
            Seat.role == "student",
        )
        .distinct()
    )
    if not include_unassigned:
        query = query.filter(Seat.claimed_at.isnot(None))

    return query.subquery()


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
    from flask import request
    from app.models import Seat, ClassFeature
    from app.feats.base import InvariantViolation

    # 1. Resolve canonical context variables from the active canonical context.
    resolved_class_id = class_id
    resolved_seat_id = seat_id
    if (not resolved_class_id or not resolved_seat_id) and getattr(g, "canonical_context", None):
        resolved_class_id = resolved_class_id or getattr(g.canonical_context, "class_id", None)
        resolved_seat_id = resolved_seat_id or getattr(g.canonical_context, "seat_id", None)

    if not resolved_class_id:
        raise InvariantViolation("Missing canonical class_id context.")

    if not resolved_seat_id:
        raise InvariantViolation("Missing canonical seat_id context.")

    # 2. Retrieve Seat first to verify against the class_id before anything else
    canonical_seat = Seat.query.filter_by(id=resolved_seat_id).first()
    if not canonical_seat:
        raise InvariantViolation(
            f"Seat not found for seat_id={resolved_seat_id}. "
            "Canonical context construction failed."
        )

    # Verify the seat.seat_id against the class_id before anything else
    if canonical_seat.class_id != resolved_class_id:
        raise InvariantViolation(
            f"Seat class mismatch: seat.class_id={canonical_seat.class_id} != requested class_id={resolved_class_id}"
        )

    # 3. Ensure the Seat has teacher role/authority
    if canonical_seat.role != 'teacher':
        raise InvariantViolation(
            f"Insufficient authority: Seat {canonical_seat.id} is role='{canonical_seat.role}', not 'teacher'."
        )

    class_row = get_class_economy(resolved_class_id)
    available_blocks = [class_row.section] if class_row and class_row.section else []

    resolved_block = available_blocks[0] if available_blocks else None
    if not resolved_block and not allow_default:
        raise InvariantViolation("No blocks found and default block is not allowed.")

    # 5. Verify feature is enabled
    enabled = "payroll" in ClassFeature.enabled_names_for_class(resolved_class_id)

    return {
        'join_code': get_display_join_code(class_row.class_id) if class_row else None,
        'class_id': resolved_class_id,
        'block': resolved_block,
        'teacher_seat': canonical_seat,
        'enabled': enabled,
    }


def _require_active_payroll_policy_version_id(class_id: str) -> int:
    """Return the active class-owned payroll policy version or fail closed."""
    policy_version = (
        PolicyVersion.query.filter_by(class_id=class_id, domain="payroll", is_active=True)
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .first()
    )
    if policy_version is None:
        raise InvariantViolation("No active payroll policy version exists for this class.")
    return policy_version.id



def _class_exists(class_id):
    """Return True when a class identified by class_id still exists in ClassEconomy."""
    if not class_id:
        return False
    return get_class_economy(class_id) is not None


def _assert_transaction_deletion_allowed(class_id, *, join_code_deletion=False):
    """
    Guardrail: transactions are immutable while the class exists.

    Hard transaction deletion is only allowed from class destruction workflow.
    """
    if not join_code_deletion and _class_exists(class_id):
        raise AssertionError(
            f"Refusing to delete transactions for active class '{class_id}'. "
            "Use student removal or class deletion flows instead."
        )


def _hard_delete_student_if_orphaned(student_id):
    """Compatibility wrapper for internal call sites and tests."""
    return hard_delete_student_if_orphaned(student_id)


def _remove_student_from_teacher_scope(student, user_id):
    """
    Remove a student from a teacher's roster.

    If the student is shared with other teachers, only the current teacher
    association is removed. The student record is hard-deleted only when it no
    longer has any canonical class-seat links.
    """
    return remove_student_from_teacher_scope(student.id, user_id)


def _delete_transactions_for_class(class_id, *, join_code_deletion=False):
    """Hard-delete transactions scoped to class_id (class destruction only)."""
    _assert_transaction_deletion_allowed(class_id, join_code_deletion=join_code_deletion)
    return Transaction.query.filter_by(class_id=class_id).delete(synchronize_session=False)


def _hard_delete_class_scope(class_id, canonical_context):
    """
    Permanently remove records scoped to a destroyed class.

    The boundary may enter through join_code, but internal deletion uses the
    canonical class_id anchor only.
    """
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        raise ValueError("canonical_context is required for class deletion")
    user_id = canonical_context.user_id

    if not class_id:
        current_app.logger.critical("P0 INVARIANT VIOLATION: class deletion invoked without class_id.")
        raise InvariantViolation("class deletion requires canonical class_id")

    class_row = get_class_economy(class_id)
    if not class_row:
        return

    invalid_scope_rows = []
    scoped_models = (
        ("ledger_transaction", Transaction),
        ("attendance_sessions", AttendanceSession),
        ("hall_pass_logs", HallPassLog),
        ("payroll_event", PayrollEvent),
        ("student_items", EntitlementEvent),
        ("issues", Issue),
        ("announcements", Announcement),
    )
    for label, model in scoped_models:
        join_code_column = getattr(model, "join_code", None)
        class_id_column = getattr(model, "class_id", None)
        if join_code_column is None or class_id_column is None:
            continue
        count = db.session.query(model).filter(
            class_id_column.is_(None),
            ).count()
        if count:
            invalid_scope_rows.append(f"{label}={count}")
    if invalid_scope_rows:
        message = (
            f"class_id NULL rows detected for class_id={class_id}: {', '.join(invalid_scope_rows)}"
        )
        current_app.logger.critical("P0 INVARIANT VIOLATION: %s", message)
        raise InvariantViolation(message)

    scoped_student_ids = [
        sid for (sid,) in db.session.query(Seat.user_id)
        .filter(Seat.class_id == class_id, Seat.user_id.isnot(None))
        .distinct()
        .all()
    ]
    store_purchase_entitlement_ids_subq = (
        db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .subquery()
    )
    tx_ids_subq = (
        db.session.query(Transaction.id)
        .filter(Transaction.class_id == class_id)
        .subquery()
    )
    _class_row = get_class_economy(class_id)
    _class_pub_id = _class_row.class_public_id if _class_row else None
    issue_ids_subq = (
        db.session.query(Issue.id)
        .filter(Issue.class_public_id == _class_pub_id)
        .subquery()
    )
    class_blocks = _get_teacher_blocks(g.canonical_context)
    if class_blocks and scoped_student_ids:
        pass

    # Class-scoped records
    PendingAction.query.filter(
        PendingAction.class_id == class_id,
        PendingAction.entitlement_id.in_(sa.select(store_purchase_entitlement_ids_subq)),
    ).delete(synchronize_session=False)
    EntitlementEvent.query.filter(
        EntitlementEvent.class_id == class_id,
        EntitlementEvent.event_type.in_(["GRANTED", "CONSUMED", "EXPIRED", "REVOKED"]),
        EntitlementEvent.acquisition_type == "PURCHASE",
    ).delete(synchronize_session=False)
    AttendanceSession.query.filter(AttendanceSession.class_id == class_id).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.class_id == class_id).delete(synchronize_session=False)
    PayrollEvent.query.filter(PayrollEvent.class_id == class_id).delete(synchronize_session=False)
    LedgerBalanceSnapshot.query.filter(LedgerBalanceSnapshot.class_id == class_id).delete(synchronize_session=False)
    Announcement.query.filter(
        Announcement.user_id == user_id,
        Announcement.class_id == class_id,
    ).delete(synchronize_session=False)

    # Issue data tied to this class
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.class_public_id == _class_pub_id).delete(synchronize_session=False)

    # Financial ledger (only here)
    Transaction.query.filter(Transaction.class_id == class_id).delete(synchronize_session=False)
    PayrollSettings.query.filter(PayrollSettings.class_id == class_id).delete(synchronize_session=False)
    RentSettings.query.filter(RentSettings.class_id == class_id).delete(synchronize_session=False)

    # Remove store items that no longer have any canonical visibility rows for this class.
    if class_blocks:
        visible_seat_ids_for_class = (
            db.session.query(StoreItemVisibility.seat_id)
            .join(Seat, Seat.id == StoreItemVisibility.seat_id)
            .filter(Seat.class_id == class_id)
            .subquery()
        )
        StoreItemVisibility.query.filter(
            StoreItemVisibility.seat_id.in_(sa.select(visible_seat_ids_for_class))
        ).delete(synchronize_session=False)

        deletable_store_item_ids = (
            db.session.query(StoreItem.id)
            .filter(StoreItem.class_id == class_id)
            .outerjoin(StoreItemVisibility, StoreItem.id == StoreItemVisibility.store_item_id)
            .filter(StoreItemVisibility.store_item_id.is_(None))
            .subquery()
        )
        class_item_entitlement_ids = (
            db.session.query(EntitlementEvent.entitlement_id)
            .filter(
                EntitlementEvent.product_id.in_(sa.select(deletable_store_item_ids)),
                EntitlementEvent.class_id == class_id,
                EntitlementEvent.event_type == "GRANTED",
                EntitlementEvent.acquisition_type == "PURCHASE",
            )
            .subquery()
        )
        PendingAction.query.filter(
            PendingAction.class_id == class_id,
            PendingAction.entitlement_id.in_(sa.select(class_item_entitlement_ids))
        ).delete(synchronize_session=False)
        EntitlementEvent.query.filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id.in_(sa.select(deletable_store_item_ids)),
        ).delete(synchronize_session=False)
        StoreItem.query.filter(
            StoreItem.id.in_(sa.select(deletable_store_item_ids))
        ).delete(synchronize_session=False)

    # Seats/ownership for this class
    Seat.query.filter(Seat.class_id == class_id).delete(synchronize_session=False)
    ClassEconomy.query.filter_by(class_id=class_id).delete(synchronize_session=False)

    # Remove students that no longer belong to any class after this class deletion.
    remaining_student_ids_subq = (
        db.session.query(Seat.user_id)
        .filter(Seat.class_id != class_id, Seat.user_id.isnot(None))
        .subquery()
    )
    orphan_student_ids = (
        db.session.query(Seat.user_id)
        .filter(Seat.user_id.in_(scoped_student_ids))
        .filter(~Seat.user_id.in_(sa.select(remaining_student_ids_subq)))
        .subquery()
    )
    Seat.query.filter(
        Seat.user_id.in_(sa.select(orphan_student_ids))
    ).delete(synchronize_session=False)

def _delete_teacher_residual_ownership_rows(canonical_context):
    """Delete teacher-user link rows not already removed by class-scoped deletion."""
    user_id = canonical_context.user_id
    Seat.query.join(ClassEconomy, ClassEconomy.class_id == Seat.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).delete(synchronize_session=False)


def _delete_teacher_settings_activity_and_audit_rows(canonical_context):
    """Delete teacher-user scoped settings, activity, and audit rows."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    BankingSettings.query.filter(
        BankingSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    HallPassSettings.query.filter(
        HallPassSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    Announcement.query.filter(
        Announcement.user_id == user_id
    ).delete(synchronize_session=False)
    Transaction.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    PendingAction.query.filter(
        PendingAction.authoritative_feat == "FEAT-STOR-002",
        PendingAction.class_id.in_(sa.select(class_ids_subq)),
    ).delete(synchronize_session=False)


def _delete_teacher_rent_rows(canonical_context):
    """Delete rent settings and dependent items owned by the teacher user."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    RentSettings.query.filter(
        RentSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)


def _delete_teacher_insurance_rows(canonical_context):
    """Delete insurance policies and dependent rows scoped to classes owned by the teacher user."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    # Insurance tables are removed in v2; no legacy cleanup path remains here.
    _ = class_ids_subq


def _delete_teacher_issue_rows(canonical_context):
    """Delete issue records belonging to classes owned by this teacher.

    Issues are scoped by class_public_id matching the teacher's classes.
    """
    user_id = canonical_context.user_id
    class_public_ids = [
        pub_id for (pub_id,) in
        db.session.query(ClassEconomy.class_public_id).filter(ClassEconomy.teacher_user_id == user_id).all()
    ]
    if not class_public_ids:
        return
    issue_ids_subq = db.session.query(Issue.id).filter(
        Issue.class_public_id.in_(class_public_ids)
    ).subquery()
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    IssueStatusHistory.query.filter(
        IssueStatusHistory.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.class_public_id.in_(class_public_ids)).delete(synchronize_session=False)


def _delete_teacher_recovery_and_credentials_rows(canonical_context):
    """Delete teacher-user recovery and credential rows."""
    user_id = canonical_context.user_id
    delete_recovery_rows_for_user(user_id)
    delete_admin_credentials_for_user(user_id)


def _delete_teacher_store_rows(canonical_context):
    """Delete store rows owned by the teacher user."""
    user_id = canonical_context.user_id
    store_item_ids_subq = db.session.query(StoreItem.id).filter_by(user_id=user_id).subquery()
    EntitlementEvent.query.filter(
        EntitlementEvent.product_id.in_(sa.select(store_item_ids_subq))
    ).delete(synchronize_session=False)
    StoreItem.query.filter_by(user_id=user_id).delete(synchronize_session=False)


def _delete_orphan_students(affected_student_ids):
    """Delete students that no longer have any canonical seat attachments."""
    if not affected_student_ids:
        return
    linked_student_ids_subq = (
        db.session.query(Seat.user_id)
        .filter(Seat.user_id.in_(affected_student_ids), Seat.user_id.isnot(None))
        .subquery()
    )
    orphan_student_ids_subq = (
        db.session.query(Seat.user_id)
        .filter(Seat.user_id.in_(affected_student_ids))
        .filter(~Seat.user_id.in_(sa.select(linked_student_ids_subq)))
        .subquery()
    )
    Seat.query.filter(
        Seat.user_id.in_(sa.select(orphan_student_ids_subq))
    ).delete(synchronize_session=False)


def _hard_delete_teacher_account_scope(canonical_context):
    """Hard-delete a teacher user account and all class-scoped data owned by that user."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        raise ValueError("canonical_context is required for account deletion")
    user_id = canonical_context.user_id

    class_ids = [
        value for (value,) in db.session.query(ClassEconomy.class_id).filter(
            ClassEconomy.teacher_user_id == user_id,
        ).distinct().all()
    ]

    affected_student_ids = {
        sid for (sid,) in db.session.query(Seat.user_id)
        .filter(Seat.class_id.in_(class_ids), Seat.user_id.isnot(None))
        .distinct()
        .all()
    }

    # Required ordering: all join-code-scoped data is destroyed before admin account deletion.
    for class_id in class_ids:
        _hard_delete_class_scope(class_id, canonical_context)

    _delete_teacher_residual_ownership_rows(canonical_context)
    _delete_teacher_settings_activity_and_audit_rows(canonical_context)
    _delete_teacher_rent_rows(canonical_context)
    _delete_teacher_insurance_rows(canonical_context)
    _delete_teacher_issue_rows(canonical_context)
    _delete_teacher_recovery_and_credentials_rows(canonical_context)
    _delete_teacher_store_rows(canonical_context)
    _delete_orphan_students(affected_student_ids)


def _sanitize_csv_field(value):
    """Prevent CSV injection by prefixing risky leading characters."""

    if value is None:
        return ""

    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _sanitize_roster_text(value):
    """Normalize inbound roster text before persisting it."""

    if value is None:
        return ""

    text = bleach.clean(str(value), tags=[], attributes={}, strip=True, strip_comments=True)
    return html.unescape(text.strip())


def _get_admin_owned_join_codes(canonical_context):
    """Return active class economies for the current admin via membership."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return []
    user_id = canonical_context.user_id

    class_ids = [
        class_id
        for (class_id,) in (
            db.session.query(ClassEconomy.class_id)
            .join(Seat, Seat.class_id == ClassEconomy.class_id)
            .filter(Seat.user_id == user_id, Seat.role == 'teacher')
            .distinct()
            .all()
        )
        if class_id
    ]
    return [code for code in (get_display_join_code(class_id) for class_id in class_ids) if code]


def _admin_owns_class(canonical_context, class_id):
    """Return True when the admin has an active seat membership for the class."""
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


def _get_seat_or_404(seat_id, include_unassigned=True):
    """Fetch a seat the current admin can access or 404."""
    class_id = (getattr(getattr(g, "canonical_context", None), "class_id", None) or "").strip() or None
    query = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.id == seat_id,
            ClassEconomy.teacher_user_id == g.canonical_context.user_id,
        )
    )
    if class_id:
        query = query.filter(Seat.class_id == class_id)
    if not include_unassigned:
        query = query.filter(Seat.claimed_at.isnot(None))
    seat = query.first()
    if not seat:
        abort(404)
    return seat


_STUDENT_DETAIL_NAV_TTL_SECONDS = 300


def _student_detail_nav_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")


def _issue_student_detail_nav_token(*, actor_public_id: str, class_id: str | None = None) -> str:
    payload = {
        "actor_public_id": str(actor_public_id),
        "class_id": str(class_id) if class_id else None,
        "user_id": int(getattr(getattr(g, "canonical_context", None), "user_id", 0) or 0),
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


def _resolve_student_detail_seat(actor_public_id: str) -> Seat | None:
    selected_class_id = (getattr(getattr(g, "canonical_context", None), "class_id", None) or "").strip()

    seat_query = Seat.query.filter(
        Seat.role == "student",
        Seat.public_id == actor_public_id,
    )
    if selected_class_id:
        return seat_query.filter(Seat.class_id == selected_class_id).first()
    return seat_query.order_by(Seat.id.asc()).first()


def _build_student_detail_url(actor_public_id: str) -> str | None:
    seat = _resolve_student_detail_seat(str(actor_public_id))
    if not seat or not seat.public_id:
        return None
    nav_token = _issue_student_detail_nav_token(
        actor_public_id=seat.public_id,
        class_id=seat.class_id,
    )
    return url_for("admin.student_detail_public", actor_public_id=seat.public_id, nav=nav_token)


def _redirect_to_student_detail(actor_public_id: str):
    detail_url = _build_student_detail_url(actor_public_id)
    if not detail_url:
        abort(404)
    return redirect(detail_url)


@admin_bp.app_template_global("student_detail_url")
def student_detail_url(actor_public_id: str) -> str:
    detail_url = _build_student_detail_url(actor_public_id)
    return detail_url or url_for("admin.students")


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
        "join_code": get_display_join_code(class_row.class_id),
        "class_identifier": class_row.display_name or get_display_join_code(class_row.class_id),
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


def _consume_pending_class_timezone_confirmations(canonical_context) -> list[dict]:
    pending = session.get("pending_class_timezone_confirmations", [])
    if not pending or canonical_context is None or not getattr(canonical_context, "user_id", None):
        return []
    user_id = canonical_context.user_id

    class_ids = [item.get("class_id") for item in pending if item.get("class_id")]
    if not class_ids:
        session.pop("pending_class_timezone_confirmations", None)
        return []

    class_rows = get_teacher_classes_by_ids(user_id, class_ids)

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



# _ensure_join_code_anchors: DELETED — v1 bridge function that treated join_code
# as primary identity (violates INV-IDEN-001: class_id is canonical, join_code is alias),
# created classes outside the FEAT layer (violates DOM-CLASS-001: FEAT-CLASS-001 owns
# class creation), and allowed join_code-first class creation (inverted authority).
# Callers replaced with FEAT-CLASS-001 execute_create_class_boundary() for creation,
# and get_class_economy() guards for existence checks.

# _generate_unique_teacher_join_code: DELETED — join code generation is internal to
# FEAT-CLASS-001; routes should not generate join codes independently.


def _resolve_student_add_class_context(canonical_context, *, block_select: str, section: str | None) -> dict | None:
    """Resolve the target class for add-student flows, creating one when requested."""
    from app.feats.class_configuration import execute_create_class_boundary
    import uuid as _uuid

    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        return None

    if block_select != '__CREATE_NEW__':
        return _resolve_admin_class_context(g.canonical_context)

    if not section:
        return None

    class_label = (request.form.get('class_name') or '').strip() or section
    result = execute_create_class_boundary(
        canonical_context=canonical_context,
        class_name=class_label,
        idempotency_key=f"feat:class:create:{canonical_context.user_id}:{_uuid.uuid4().hex}",
    )
    if not result.success:
        current_app.logger.error(
            "FEAT-CLASS-001 failed in add-student class creation: %s", result.error_message
        )
        return None

    class_row = get_class_economy(result.class_id)
    return {
        'join_code': result.join_code,
        'class_id': result.class_id,
        'block': section,
        'class_created': True,
        'class_row': class_row,
    }



# _link_student_to_admin: DELETED — v1 bridge function that violated INV-IDEN-001
# (join_code-first class creation), bypassed FEAT layer, and had a live bug
# (passed user_id int where canonical_context object expected).
# Callers replaced with FEAT-CLASS-002 execute_provision_student_seat().


def _get_feature_settings(class_id=None):
    """
    Get class-scoped feature settings for a specific class.
    """
    if not class_id:
        return ClassFeature.defaults_dict()
    scoped_features = get_class_feature_settings(None, class_id=class_id)
    if scoped_features:
        return scoped_features["features"]
    return ClassFeature.defaults_dict()


def _build_economy_snapshot_from_analysis(class_id, checker, analysis):
    return {
        "class_id": class_id,
        "policy_mode": checker.policy_mode,
        "analysis_payload": _serialize_economy_analysis_payload(analysis),
    }


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
    canonical_context,
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
    user_id = canonical_context.user_id if canonical_context and getattr(canonical_context, "user_id", None) else None
    expected_inputs = _current_economy_snapshot_inputs(
        checker,
        payroll_settings,
        expected_weekly_hours=expected_weekly_hours,
    )
    class_id = getattr(payroll_settings, "class_id", None)
    analysis = checker.analyze_economy(
        payroll_settings=payroll_settings,
        rent_settings=rent_settings,
        insurance_policies=insurance_policies,
        fines=fines,
        store_items=store_items,
        expected_weekly_hours=float(expected_inputs['expected_hours']),
    )

    if class_id and expected_weekly_hours is None:
        payload = _serialize_economy_analysis_payload(analysis, frozen=True)
        payload['analysis_schedule'] = _economy_analysis_schedule(None, frozen=False)
        payload['snapshot_cached'] = False
        return payload, None

    payload = _serialize_economy_analysis_payload(analysis, frozen=False)
    payload['snapshot_cached'] = False
    return payload, None


def _resolve_payroll_settings_for_class_id(canonical_context, class_id):
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


def _resolve_rent_settings_for_class_id(class_id, policy_uuid=None):
    if policy_uuid:
        scoped_policy = RentSettings.query.filter_by(policy_uuid=policy_uuid).first()
        if scoped_policy:
            return scoped_policy
    if not class_id:
        return None
    from app.models import BillCycle
    current_cycle = (
        BillCycle.query.filter_by(class_id=class_id)
        .order_by(BillCycle.cycle_number.desc(), BillCycle.id.desc())
        .first()
    )
    if not current_cycle or not current_cycle.policy_uuid:
        return None
    return RentSettings.query.filter_by(policy_uuid=current_cycle.policy_uuid).first()


def _resolve_banking_settings_for_class_id(class_id):
    if not class_id:
        return None
    return (
        BankingSettings.query.filter(
            BankingSettings.class_id == class_id,
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
        url_for('admin.payroll'),
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


def _build_rebalance_preview(canonical_context, selected_block, class_id, checker, cwi, rent_settings, insurance_policies):
    preview_items = []
    recommendations = get_price_recommendation_context(checker.policy_mode, cwi) or {}

    if rent_settings:
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
                    'class_id': class_id,
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


def _build_insurance_recommendation_context(canonical_context, *, class_id=None, charge_frequency='weekly'):
    if not class_id:
        return None
    payroll_settings = _resolve_admin_payroll_settings_for_class_id(
        canonical_context,
        class_id,
    )
    if not payroll_settings:
        return None

    checker = EconomyBalanceChecker(canonical_context.user_id, None, class_id=getattr(payroll_settings, "class_id", None))
    cwi_calc = checker.calculate_cwi(payroll_settings)
    return get_insurance_premium_recommendation(
        checker.policy_mode,
        Decimal(str(cwi_calc.cwi)),
        frequency=charge_frequency,
    )


def _load_economy_rebalance_context(canonical_context, class_id, selected_block):
    user_id = canonical_context.user_id
    selected_class_id = (class_id or "").strip() or None
    if not selected_class_id:
        raise InvariantViolation("Missing canonical class_id for economy rebalance context.")

    class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id)
    payroll_query = PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(sa.select(class_ids_query.subquery())),
        PayrollSettings.is_active.is_(True),
    )
    all_payroll_settings = payroll_query.order_by(PayrollSettings.block.asc()).all()
    settings_by_block = {s.block: s for s in all_payroll_settings if s.block}

    payroll_settings = _resolve_payroll_settings_for_class_id(canonical_context, selected_class_id)
    effective_block = selected_block

    rent_settings = _resolve_rent_settings_for_class_id(selected_class_id)

    class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id)
    insurance_policies = []

    return effective_block, payroll_settings, rent_settings, insurance_policies, all_payroll_settings


def _apply_rebalance_plan(canonical_context, settings_row, change_plan, activation_mode):
    """Apply rebalance plan for a class (wrapper for economy_rebalance function).

    Refactored in Phase 2 to extract class_id from settings_row instead of passing
    the FeatureSettings object directly (FeatureSettings table dropped).
    """
    user_id = canonical_context.user_id
    class_id = getattr(settings_row, "class_id", None)
    applied_labels = apply_rebalance_changes(user_id, class_id, change_plan, activation_mode)
    current_app.logger.info(
        "Applied economy rebalance for teacher=%s class_id=%s activation=%s changes=%s",
        user_id,
        class_id,
        activation_mode,
        applied_labels,
    )
    return applied_labels


def _check_onboarding_redirect():
    """Onboarding status is derived live — no redirect needed."""
    return None


def _normalize_claim_credentials_for_admin(canonical_context) -> int:
    """No-op: seat claim credential normalization is no longer needed.

    Returns 0 always.
    """
    return 0


def _get_validated_teacher_class_options(user_id: int) -> list[dict]:
    """Return teacher-owned classes validated by canonical seat ownership."""
    if not user_id:
        return []

    class_rows = (
        db.session.query(ClassEconomy.class_id, ClassEconomy.display_name)
        .filter(ClassEconomy.teacher_user_id == user_id)
        .order_by(ClassEconomy.created_at.asc(), ClassEconomy.class_id.asc())
        .all()
    )
    if not class_rows:
        return []

    class_ids = [class_id for class_id, _display_name in class_rows if class_id]
    teacher_seats = {
        seat.class_id: seat
        for seat in Seat.query.filter(
            Seat.class_id.in_(class_ids),
            Seat.user_id == user_id,
            Seat.role == "teacher",
        ).all()
        if seat.class_id
    }
    options = []
    for class_id, display_name in class_rows:
        if not class_id:
            continue
        # Resolve the canonical seat for this class; fail closed if missing.
        seat = teacher_seats.get(class_id)
        if not seat:
            continue
        join_code = get_display_join_code(class_id)
        options.append(
            {
                "class_id": class_id,
                "join_code": join_code,
                "display_name": display_name or join_code or class_id,
                "seat_id": seat.id,
            }
        )
    return options


@admin_bp.route('/select-class-context', methods=['GET', 'POST'])
@admin_required
def select_class_context():
    """Explicit teacher class-selection gate before dashboard access."""
    ctx = getattr(g, "canonical_context", None)
    if not ctx:
        flash("Admin session is invalid. Please log in again.", "error")
        return redirect(url_for("admin.login"))

    raw_options = _get_validated_teacher_class_options(ctx.user_id)
    if not raw_options:
        return redirect(url_for("admin.onboarding"))

    if request.method == "POST":
        selected_class_id = (request.form.get("class_id") or "").strip()
        selected = next((item for item in raw_options if item["class_id"] == selected_class_id), None)
        if not selected:
            flash("Invalid class selection.", "error")
            from app.services.identity.builders import build_admin_class_selection_view
            from app.utils.display_name_session import get_admin_display_name_cache
            admin_name = get_admin_display_name_cache(user_id=ctx.user_id)
            class_selection_view = build_admin_class_selection_view(admin_name, raw_options)
            return render_template(
                "admin_select_class_context.html",
                class_selection_view=class_selection_view,
            ), 400

        session["last_activity"] = utc_now().isoformat()
        user = db.session.get(User, ctx.user_id)
        if user and user.last_active_class_id != selected["class_id"]:
            user.last_active_class_id = selected["class_id"]
        return redirect(url_for("admin.dashboard"))

    from app.services.identity.builders import build_admin_class_selection_view
    from app.utils.display_name_session import get_admin_display_name_cache
    admin_name = get_admin_display_name_cache(user_id=ctx.user_id)
    class_selection_view = build_admin_class_selection_view(admin_name, raw_options)
    return render_template(
        "admin_select_class_context.html",
        class_selection_view=class_selection_view,
    )

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics, pending actions, and recent activity."""
    ctx = getattr(g, "canonical_context", None)
    if not ctx:
        flash("Admin session is invalid. Please log in again.", "error")
        return redirect(url_for("admin.login"))

    class_options = _get_validated_teacher_class_options(ctx.user_id)
    current_class_id = (getattr(getattr(g, "canonical_context", None), "class_id", None) or "").strip()
    if not current_class_id:
        if not class_options:
            return redirect(url_for("admin.onboarding"))
        return redirect(url_for("admin.select_class_context"))

    current_class_validated = any(option["class_id"] == current_class_id for option in class_options)
    if not current_class_validated:
        if not class_options:
            return redirect(url_for("admin.onboarding"))
        return redirect(url_for("admin.select_class_context"))

    # Check if teacher needs onboarding
    onboarding_redirect = _check_onboarding_redirect()
    if onboarding_redirect:
        return onboarding_redirect
    current_user_id = ctx.user_id

    temporal_now = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    now = temporal_now.canonical_now_utc

    # INV-ARC-007: dashboard GET must remain read-only.
    # Daily-limit auto tap-out is handled by scheduled tasks only.

    # V2 canonical: scope everything through class_id from canonical context.
    teacher_class_ids = [
        c.class_id for c in
        get_all_classes_by_teacher(current_user_id)
    ]

    seats = Seat.query.filter(Seat.class_id.in_(teacher_class_ids), Seat.role == 'student').all()
    total_students = len(seats)

    # Seat-based name lookup for templates (keyed by seat_id)
    seat_profiles = {
        p.seat_id: p for p in
        IdentityProfile.query.filter(
            IdentityProfile.seat_id.in_([s.id for s in seats])
        ).all()
    } if seats else {}

    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    batch_balances = get_batch_balances_by_class_seat(class_seat_pairs)

    # Sum up balances
    total_balance_decimal = Decimal('0.00')
    for bal in batch_balances.values():
        total_balance_decimal += Decimal(bal['checking_cents']) / 100
        total_balance_decimal += Decimal(bal['savings_cents']) / 100

    total_balance = float(total_balance_decimal)
    avg_balance = total_balance / total_students if total_students > 0 else 0

    # Pending actions - count all types of pending approvals (scoped by class_id)
    pending_redemptions_count = (
        PendingAction.query
        .filter(
            PendingAction.class_id.in_(teacher_class_ids),
            PendingAction.authoritative_feat == "FEAT-STOR-002",
            EntitlementEvent.event_type == "GRANTED",
        )
        .count()
    )
    pending_hall_pass_requests = list_pending_hall_pass_requests_for_class(ctx.class_id)
    pending_hall_passes_count = len(pending_hall_pass_requests)
    pending_insurance_claims_count = 0
    total_pending_actions = pending_redemptions_count + pending_hall_passes_count

    # Get recent items for each pending type (limited for display)
    recent_redemptions = [
        SimpleNamespace(
            id=ent.entitlement_id,
            seat_id=ent.target_seat_id,
            reason="",
            request_time=ent.granted_at,
        )
        for ent in EntitlementEvent.query.filter(
            EntitlementEvent.class_id.in_(teacher_class_ids),
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        ).order_by(EntitlementEvent.timestamp.desc()).limit(5).all()
    ]
    recent_hall_passes = [
        SimpleNamespace(
            id=pending_request.request_id,
            seat_id=pending_request.requested_by_seat_id,
            reason=pending_request.destination,
            request_time=pending_request.requested_at_utc,
        )
        for pending_request in pending_hall_pass_requests[:5]
    ]
    recent_insurance_claims = []

    pending_redemptions = (
        db.session.query(PendingAction, EntitlementEvent, StoreItem)
        .join(EntitlementEvent, EntitlementEvent.entitlement_id == PendingAction.entitlement_id)
        .join(StoreItem, StoreItem.id == EntitlementEvent.product_id)
        .filter(
            PendingAction.class_id.in_(teacher_class_ids),
            PendingAction.authoritative_feat == "FEAT-STOR-002",
        )
        .order_by(PendingAction.submitted_at.desc())
        .limit(10)
        .all()
    )
    pending_redemptions = [
        SimpleNamespace(
            id=pending.pending_action_id,
            seat=SimpleNamespace(id=ent.target_seat_id),
            store_item=item,
            class_id=pending.class_id,
            purchased_at=pending.submitted_at,
            status='processing',
        )
        for pending, ent, item in pending_redemptions
    ]

    # Recent transactions (limited to 5 for display)
    recent_transactions = (
        Transaction.query
        .filter(Transaction.class_id.in_(teacher_class_ids))
        .filter_by(is_void=False)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
    _day_bounds = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="evaluation_day_boundaries",
    )
    today_start_db = ensure_utc(_day_bounds.boundary_start_utc)
    total_transactions_today = (
        Transaction.query
        .filter(Transaction.class_id.in_(teacher_class_ids))
        .filter(
            Transaction.timestamp >= today_start_db,
            Transaction.is_void == False,
        )
        .count()
    )

    # Recent PROD attendance facts for the active canonical class.
    raw_logs = (
        db.session.query(AttendanceSession, Seat, IdentityProfile, ClassEconomy)
        .join(Seat, AttendanceSession.target_seat_id == Seat.id)
        .outerjoin(
            IdentityProfile,
            sa.and_(
                IdentityProfile.seat_id == AttendanceSession.target_seat_id,
                IdentityProfile.class_id == AttendanceSession.class_id,
            ),
        )
        .join(ClassEconomy, AttendanceSession.class_id == ClassEconomy.class_id)
        .filter(AttendanceSession.class_id == ctx.class_id)
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .limit(5)
        .all()
    )
    recent_logs = []
    for log, seat, profile, class_row in raw_logs:
        recent_logs.append({
            'seat_id': log.target_seat_id,
            'student_name': (profile.full_name if profile else 'Unknown'),
            'period': class_row.section or '',
            'timestamp': log.timestamp,
            'reason': log.reason_code,
            'status': log.status
        })

    # --- Payroll Info ---
    dashboard_blocks = sorted({b.strip() for s in seats for b in (s.block or "").split(',') if b.strip()})
    dashboard_class_ids_by_block = _get_class_ids_by_block(g.canonical_context, dashboard_blocks)
    payroll_preview = _build_payroll_preview_state(seats, dashboard_class_ids_by_block)
    payroll_summary = payroll_preview["total_summary"]
    payroll_updated_at = payroll_preview["latest_updated_at"]
    total_payroll_estimate = sum(payroll_summary.values())

    # Calculate next payroll date (keep in UTC for template conversion)
    anchor_candidates = [
        anchor + timedelta(days=14)
        for anchor in payroll_preview["anchor_by_class_id"].values()
        if anchor is not None
    ]
    if anchor_candidates:
        next_payroll_date = min(anchor_candidates)
    else:
        now_utc = now
        days_until_friday = (4 - now_utc.weekday() + 7) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_payroll_date = now_utc + timedelta(days=days_until_friday)

    # v2: DOB-based recovery setup prompt is disabled.
    show_recovery_setup = False

    # Prompt teachers to upgrade insurance policies to the new tiered design.
    show_insurance_tier_prompt = False
    show_insurance_tier_prompt = False

    return render_template(
        'admin_dashboard.html',
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
        # Lookup table (v2: keyed by seat_id → IdentityProfile)
        seat_profiles=seat_profiles,
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

    ctx = g.canonical_context
    class_ids_subq = [ctx.class_id]
    seats = Seat.query.filter(Seat.class_id.in_(sa.select(class_ids_subq)), Seat.role == 'student').all()
    user_id = ctx.user_id

    banking_settings = (
        BankingSettings.query
        .filter(BankingSettings.class_id.in_(sa.select(class_ids_subq)))
        .first()
    )
    adjustments = []

    for seat in seats:
        adjustments.append({
            'seat': seat,
            'user_id': user_id,
            'amount': amount,
            'type': tx_type,
            'description': title,
            'account_type': 'checking',
        })

    result = execute_admin_adjustments(
        ctx=ctx,
        adjustments=adjustments,
        banking_settings=banking_settings,
        actor_seat_id=ctx.seat_id,
    )
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
@feat_shell("FEAT-ADMN-001")
def login():
    """Admin login with TOTP authentication."""
    session.pop("user_id", None)
    session.pop("current_session_nonce", None)
    session.pop("last_activity", None)
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
                    establish_teacher_session(user)
                    nonce = secrets.token_urlsafe(32)
                    session["current_session_nonce"] = nonce
                    user.current_session_nonce = nonce
                    session["login_time"] = utc_now().isoformat()
                    session["last_activity"] = utc_now().isoformat()
                    session["admin_auth_username"] = username
                    set_admin_display_name_cache(user_id=user.id, display_name=user.get_display_username())
                    flash("Admin login successful.")
                    next_url = request.args.get("next")
                    class_options = _get_validated_teacher_class_options(user.id)
                    if not class_options:
                        return redirect(url_for("admin.onboarding"))

                    return redirect(url_for("admin.select_class_context"))
        flash("Invalid credentials or TOTP code.", "error")
        return redirect(url_for("admin.login", next=request.args.get("next")))
    return render_template("admin_login.html", form=form)



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
            from app.services.identity.builders import build_totp_setup_view
            totp_view = build_totp_setup_view(totp_secret, img_b64, [])
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                totp_view=totp_view,
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
            from app.services.identity.builders import build_totp_setup_view
            totp_view = build_totp_setup_view(totp_secret, img_b64, [])
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                totp_view=totp_view,
            )
        # Step 6: Create admin account and mark invite as used
        current_app.logger.info(f"TOTP verified. Creating admin account")
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
            from app.services.identity.builders import build_totp_setup_view
            totp_view = build_totp_setup_view(totp_secret, img_b64, [])
            return render_template(
                "admin_signup_totp.html",
                form=totp_form,
                totp_view=totp_view,
                tos_agreed=False
            )

        # Encrypt TOTP secret before storing
        encrypted_totp_secret = encrypt_totp(totp_secret)

        salt, username_hash, username_lookup_hash = _build_admin_auth_fields(username)
        new_user = User(
            user_role=UserRole.TEACHER,
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            totp_secret_encrypted=encrypted_totp_secret,
            hall_pass_verify_token=User.generate_verify_token(),
        )
        # Close any read-only transaction opened during validation before FEAT entry.
        db.session.rollback()

        signup_idempotency_key = f"feat:iden:admin-signup:{username}"
        with FEATContext("FEAT-IDEN-001", idempotency_key=signup_idempotency_key):
            initial_join_code = generate_join_code()
            initial_display_name = username.strip() or "New Class"
            new_user = create_teacher_account_with_class(
                username=username,
                totp_secret=totp_secret,
                join_code=initial_join_code,
                display_name=initial_display_name,
            )
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
    Account recovery - Step 1: Roster verification.

    Teacher submits one (join_code, student_username) pair per class taught.
    Lookup order (enforced):
      1. Resolve join_code -> ClassEconomy -> class_id (establishes user_id and class scope)
      2. Find the seat by username_lookup_hash *within* the resolved class roster
    All pairs must resolve to the same teacher and must cover all active class_ids.
    No DOB is used.

    Generic errors only — do not reveal which pair failed.
    Rate limited to prevent brute-force enumeration.
    """
    form = AdminRecoveryForm()
    _GENERIC_ERROR = "Unable to verify identity. Please check your entries and try again."

    if request.method == 'POST' and form.validate_on_submit():
        recovery_join_codes = request.form.getlist('join_code[]')
        recovery_usernames = request.form.getlist('student_username[]')

        # Strip and filter empty entries
        recovery_pairs = [
            (jc.strip().upper(), un.strip())
            for jc, un in zip(recovery_join_codes, recovery_usernames)
            if jc.strip() and un.strip()
        ]

        if not recovery_pairs:
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # ----------------------------------------------------------------
        # Step 1: Establish class authority from the first explicit ingress boundary
        # ----------------------------------------------------------------
        display_join_code = recovery_pairs[0][0]
        first_class = get_class_economy_by_join_code(display_join_code)
        if not first_class:
            current_app.logger.warning(
                f"Admin recovery: initial join_code '{display_join_code}' not found"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        recovered_account_id = first_class.teacher_user_id
        active_classes = get_all_classes_by_teacher(recovered_account_id)
        class_by_id = {c.class_id: c for c in active_classes if c.class_id}

        resolved_pairs = []
        for recovery_join_code, recovery_username in recovery_pairs:
            resolved_class = next((c for c in active_classes if c.join_code == recovery_join_code), None)
            if not resolved_class:
                current_app.logger.warning(
                    f"Admin recovery: join_code '{recovery_join_code}' not found in recovered account scope"
                )
                flash(_GENERIC_ERROR, "error")
                return render_template("admin_recover.html", form=form)
            resolved_pairs.append((resolved_class.class_id, recovery_username))

        # ----------------------------------------------------------------
        # Step 2: Verify submitted class_ids exactly match the active class records
        # ----------------------------------------------------------------
        all_active_class_ids = set(class_by_id)
        submitted_class_ids = set(class_id for class_id, _ in resolved_pairs)

        # Must exactly match backend list
        if all_active_class_ids != submitted_class_ids:
            current_app.logger.warning(
                f"Admin recovery: class_id set mismatch for recovered account {recovered_account_id}"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # Reject duplicates (e.g. submitting the same valid class 3 times)
        if len(submitted_class_ids) != len(resolved_pairs):
            current_app.logger.warning(
                f"Admin recovery: duplicate class_ids submitted"
            )
            flash(_GENERIC_ERROR, "error")
            return render_template("admin_recover.html", form=form)

        # ----------------------------------------------------------------
        # Step 3: Verify each recovered seat belongs in the correct class scope
        # ----------------------------------------------------------------
        resolved_seats = {}   # class_id -> seat record

        # Group seat IDs by class for quick lookup
        seats_by_class_id = {}
        for c in active_classes:
            if c.class_id:
                jc_seats = (
                    Seat.query
                    .join(User, User.id == Seat.user_id)
                    .filter(
                        Seat.class_id == c.class_id,
                        Seat.claimed_at.isnot(None),
                    )
                    .with_entities(Seat.id, User.id)
                    .all()
                )
                seats_by_class_id[c.class_id] = jc_seats

        for recovery_class_id, recovery_username in resolved_pairs:
            # We already know this class is in scope from the set comparison.
            recovery_lookup_hash = hash_username_lookup(recovery_username)

            # Get all seat IDs associated with this specific class
            seats_for_jc = seats_by_class_id.get(recovery_class_id, [])
            seat_ids_in_class = [seat_id for seat_id, _student_id in seats_for_jc if seat_id]

            seat = (
                Seat.query
                .join(User, User.id == Seat.user_id)
                .filter(
                    Seat.id.in_(seat_ids_in_class),
                    User.username_lookup_hash == recovery_lookup_hash,
                )
                .first()
            )

            if not seat:
                current_app.logger.warning(
                    f"Admin recovery: recovered seat not found in recovery scope"
                )
                flash(_GENERIC_ERROR, "error")
                return render_template("admin_recover.html", form=form)

            resolved_seats[recovery_class_id] = seat

        # ----------------------------------------------------------------
        # Step 4: Check for existing active recovery request
        # ----------------------------------------------------------------
        existing_request = get_active_recovery_request_for_user(recovered_account_id, utc_now())

        if existing_request:
            flash("You already have an active recovery request. Please check back or wait for it to expire.", "info")
            session['recovery_request_id'] = existing_request.id
            return redirect(url_for('admin.recovery_status'))

        # ----------------------------------------------------------------
        # Step 4: Create recovery request (5-day expiration)
        # ----------------------------------------------------------------
        expires_at = utc_now() + timedelta(days=5)
        recovery_request = create_recovery_request_with_seats(
            user_id=recovered_account_id,
            seat_class_pairs=[(seat.id, class_id) for class_id, seat in resolved_seats.items()],
            expires_at=expires_at,
        )

        session['recovery_request_id'] = recovery_request.id
        current_app.logger.info(
            f"Admin recovery: request created for recovered account {recovered_account_id}, expires {expires_at}"
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
        if _auth_username_exists(new_username, exclude_admin_id=recovery_request.user_id):
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

    teacher = db.session.get(User, recovery_request.user_id)
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

    # Update admin account
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
    encrypted_totp_secret = encrypt_totp(totp_secret)
    user.username_hash = username_hash
    user.username_lookup_hash = username_lookup_hash
    user.totp_secret_encrypted = encrypted_totp_secret

    # Mark recovery request as completed
    mark_recovery_request_verified(recovery_request.id, utc_now())

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
    ctx = g.canonical_context
    user_id = ctx.user_id
    from app.models import User
    user = db.session.get(User, user_id)
    admin = User.query.filter_by(username_lookup_hash=user.username_lookup_hash, user_role=UserRole.TEACHER).first() if user else None
    if not admin:
        abort(404)

    if request.method == 'POST':
        form_pairs = sorted((key, value) for key, value in request.form.items())
        payload_hash = hashlib.sha256(repr(form_pairs).encode("utf-8")).hexdigest()[:16]
        idempotency_key = f"feat:iden:admin-settings:{user_id}:{payload_hash}"

        # Ensure FEAT owns transaction boundary for this write path.
        db.session.rollback()
        with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
            user = db.session.get(User, user_id)
            admin = User.query.filter_by(username_lookup_hash=user.username_lookup_hash, user_role=UserRole.TEACHER).first() if user else None

            # Update display name
            display_name = request.form.get('display_name', '').strip()
            if display_name:
                admin.display_name = display_name
            else:
                admin.display_name = None  # Use canonical public_id as fallback

            # Update class labels for each ClassEconomy (canonical class label store)
            teacher_classes = get_all_classes_by_teacher(user_id)
            for cls in teacher_classes:
                section_key = cls.section or cls.join_code or ''
                class_label_key = f'class_label_{section_key}'
                class_label = request.form.get(class_label_key, '').strip()
                cls.display_name = class_label if class_label else None

        set_admin_display_name_cache(user_id=admin.id, display_name=admin.get_display_name())
        flash("Settings updated successfully!", "success")
        return redirect(url_for('admin.settings'))

    # GET: Show settings form
    # Derive blocks from ClassEconomy (canonical class anchor)
    blocks = [
        {'block': cls.section or cls.join_code or '', 'class_label': cls.display_name}
        for cls in get_all_classes_by_teacher(user_id)
    ]

    # Pass admin object directly so template can call methods like get_display_username()
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
    session.pop("user_id", None)
    session.pop("admin_auth_username", None)
    session.pop("last_activity", None)
    session.pop("passkey_auth_username", None)
    flash("Logged out.")
    return redirect(url_for("admin.login"))


# -------------------- Rent privilege helpers --------------------

def _build_rent_privileges_by_block(user_id, blocks, class_ids_by_block, students_by_block):
    """
    Build a dict {(seat_id, block): [privileges]} using batched queries to avoid N+1 issues.
    """
    # Use UTC-aware datetime to match database-stored UTC expiry dates.
    now = utc_now()
    student_rent_privileges = {}

    # 1. Fetch all RentSettings for the teacher and blocks in a single query.
    target_blocks = [b for b in blocks if b != "Unassigned" and b in class_ids_by_block]
    if not target_blocks:
        return student_rent_privileges

    target_class_ids = [class_ids_by_block[b] for b in target_blocks if class_ids_by_block.get(b)]
    # Use projected columns only; local dev DB may not have newer RentSettings fields yet.
    rent_settings_rows = (
        db.session.query(
            RentSettings.id,
            RentSettings.class_id,
            RentSettings.first_rent_due_date,
            RentSettings.frequency_type,
            RentSettings.custom_frequency_value,
            RentSettings.custom_frequency_unit,
            RentSettings.due_day_of_month,
            RentSettings.grace_period_days,
        )
        .filter(RentSettings.class_id.in_(target_class_ids))
        .all()
    )
    all_rent_settings = [
        SimpleNamespace(
            id=row.id,
            class_id=row.class_id,
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
        block: next((rs for rs in all_rent_settings if rs.class_id == class_ids_by_block.get(block)), None)
        for block in target_blocks
    }

    if not settings_by_block:
        return student_rent_privileges

    from app.services.store_service import get_frozen_privilege_items
    frozen_items_by_class_id = {}
    all_store_item_ids = set()
    for block, rent_settings in settings_by_block.items():
        frozen_privs = get_frozen_privilege_items(rent_settings)
        class_id_val = class_ids_by_block.get(block)
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
        class_id = class_ids_by_block.get(block)
        if not class_id:
            continue
        payment_filters.append((class_id, coverage_month, coverage_year))

    if not all_student_ids:
        return student_rent_privileges

    # 4. Fetch all relevant RentPayments in a single query each
    paid_seat_ids_by_block = defaultdict(set)
    if payment_filters:
        from app.services.obligations_service import get_paid_rent_assessments_for_cycle
        for class_id, coverage_month, coverage_year in payment_filters:
            assessments = get_paid_rent_assessments_for_cycle(
                class_id,
                coverage_month,
                coverage_year,
            )
            for assessment in assessments:
                if assessment.seat and assessment.seat.id is not None:
                    for block, block_class_id in class_id_by_block.items():
                        if block_class_id == class_id:
                            paid_seat_ids_by_block[block].add(assessment.seat.id)

    # 5. Fetch all relevant entitlement grant rows in a single query each
    items_by_seat = defaultdict(set)
    if all_store_item_ids:
        student_items = (
            EntitlementEvent.query.filter(
                EntitlementEvent.target_seat_id.in_(sa.select(Seat.id).where(Seat.user_id.in_(list(all_student_ids)))),
                EntitlementEvent.product_id.in_(list(all_store_item_ids)),
                EntitlementEvent.event_type == "GRANTED",
                EntitlementEvent.acquisition_type.in_(["PURCHASE", "PERK"]),
            )
            .with_entities(EntitlementEvent.target_seat_id, EntitlementEvent.product_id)
            .all()
        )

        for seat_id, store_item_id in student_items:
            if seat_id is not None:
                items_by_seat[seat_id].add(store_item_id)

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
        paid_seat_ids = paid_seat_ids_by_block.get(block, set())

        for student in block_students:
            privileges = []
            seat_id = student.identity_profile.seat_id if student.identity_profile and student.identity_profile.seat_id else None
            has_paid_rent = seat_id in paid_seat_ids if seat_id else False
            student_store_items = items_by_seat.get(seat_id, set()) if seat_id else set()

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
                key = (seat_id or student.id, block)
                student_rent_privileges[key] = privileges

    return student_rent_privileges


def _get_rent_privileges_for_student(student, class_id, seat_id):
    """Return rent privileges for a single student in the current class context.

    Pre-paid system: Check if student has paid rent that COVERS the current period.
    A payment made for January covers the student until the February due date.
    """
    rent_privileges = []
    if not class_id:
        return rent_privileges

    if not seat_id and student and student.identity_profile:
        seat_id = student.identity_profile.seat_id
    if not seat_id:
        return rent_privileges

    rent_settings = get_rent_settings(class_id)
    if not rent_settings:
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
    seat_ids = [seat_id]
    from app.services.obligations_service import get_paid_rent_assessments_for_cycle
    has_paid_rent = bool(
        seat_ids
        and get_paid_rent_assessments_for_cycle(
            class_id,
            coverage_month,
            coverage_year,
            seat_ids=seat_ids,
        )
    )

    # Read privilege items from canonical rent settings so mid-cycle edits
    # don't change what students see until next cycle.
    from app.services.store_service import get_frozen_privilege_items
    rent_settings = get_rent_settings(class_id)
    if not rent_settings:
        return rent_privileges

    frozen_privileges = get_frozen_privilege_items(rent_settings)
    store_item_ids = [item['store_item_id'] for item in frozen_privileges if item.get('store_item_id')]
    items_by_seat = set()
    if store_item_ids and seat_id:
        student_seat = Seat.query.filter_by(id=seat_id, class_id=class_id).first()
        if student_seat:
            student_items = EntitlementEvent.query.filter(
                EntitlementEvent.target_seat_id == seat_id,
                EntitlementEvent.product_id.in_(store_item_ids),
                EntitlementEvent.event_type == "GRANTED",
                EntitlementEvent.acquisition_type.in_(["PURCHASE", "PERK"]),
            ).all()
            items_by_seat = {si.product_id for si in student_items}

    for frozen_item in frozen_privileges:
        source = None
        if has_paid_rent:
            source = 'rent'
        elif frozen_item.get('store_item_id') and frozen_item['store_item_id'] in items_by_seat:
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
    """View all students in the active canonical class."""
    user_id = g.canonical_context.user_id
    pending_class_timezone_confirmations = _consume_pending_class_timezone_confirmations(g.canonical_context)

    current_class_id = g.canonical_context.class_id
    if not current_class_id:
        teacher_classes = sorted(
            get_all_classes_by_teacher(user_id),
            key=lambda c: (c.display_name or "", c.class_id),
        )
        if not teacher_classes:
            flash("Create a class before managing students.", "error")
            return redirect(url_for('admin.dashboard'))
        current_class_id = teacher_classes[0].class_id

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
        class_row = verify_teacher_owns_class(current_class_id, user_id)
        if class_row and (not class_row.class_timezone or class_row.class_timezone == 'UTC'):
            pending_class_timezone_confirmations.append(_build_pending_class_timezone_payload(class_row))

    class_row = (
        verify_teacher_owns_class(current_class_id, user_id)
        if current_class_id
        else None
    )

    # Strict single-context: only Seat data anchored to the active class_id.
    class_seats = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(Seat.class_id == current_class_id)
        .all()
    ) if current_class_id else []

    # Claimed students are resolved through Seat rows in the active class.
    active_seat_ids = sorted({
        s.id for s in class_seats
        if s.user_id is not None and s.claimed_at is not None
    })
    all_students = (
        sorted(
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .filter(Seat.id.in_(active_seat_ids))
            .all(),
            key=lambda seat: (
                ((seat.class_economy.section if seat.class_economy and seat.class_economy.section else "").lower()),
                (seat.identity_profile.first_name if seat.identity_profile else "").lower(),
                seat.id,
            ),
        )
        if active_seat_ids else []
    )

    # Add username_display attribute to each student
    for seat in all_students:
        if seat.user_id and seat.identity_profile:
            seat.username_display = f"user_{seat.user_id}"
        else:
            seat.username_display = "Not Set"

    unclaimed_seats_raw = [
        seat for seat in class_seats
        if seat.user_id is None and seat.claimed_at is None
    ]
    # Build view model dicts for unclaimed seats (no raw SQLAlchemy in templates).
    unclaimed_seats = [
        {
            'id': seat.id,
            'public_id': seat.public_id,
            'class_id': seat.class_id,
            'is_teacher': getattr(seat, 'is_teacher', False),
            'created_at': seat.created_at,
            'full_name': seat.identity_profile.full_name if seat.identity_profile else 'Unknown',
        }
        for seat in unclaimed_seats_raw
    ]

    # CRITICAL: Add scoped balances by canonical seat_id only.
    class_seat_pairs = [(current_class_id, seat.id) for seat in all_students] if current_class_id else []
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)
    student_balances_by_seat_id = {}
    for student in all_students:
        bals = raw_balances.get((str(current_class_id), student.id)) if current_class_id else None
        if not bals:
            bals = {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}
        student_balances_by_seat_id[student.id] = {
            'checking': float(Decimal(bals['checking_cents']) / 100),
            'savings': float(Decimal(bals['savings_cents']) / 100),
            'earnings': float(bals.get('earnings', Decimal('0.00')))
        }

    student_rent_privileges_by_seat_id = {}
    student_hall_pass_balances_by_seat_id = {}
    for student in all_students:
        student_hall_pass_balances_by_seat_id[student.id] = get_hall_pass_balance(
            student.id,
            current_class_id,
        )

    class_label_parts = []
    if class_row and class_row.section:
        class_label_parts.append(class_row.section)
    if class_row and class_row.display_name:
        class_label_parts.append(class_row.display_name)
    class_display_label = " - ".join(class_label_parts) or (class_row.class_id if class_row else "Current Class")
    display_join_code = class_row.join_code if class_row else None

    # Build view model dicts for claimed students (no raw SQLAlchemy in templates).
    claimed_student_views = []
    for seat in all_students:
        profile = seat.identity_profile
        claimed_student_views.append({
            'id': seat.id,
            'public_id': seat.public_id,
            'class_id': seat.class_id,
            'identity_profile': {
                'full_name': profile.full_name if profile else '',
                'first_name': profile.first_name if profile else '',
                'last_name': profile.last_name if profile else '',
                'notes': profile.notes if profile and profile.notes else '',
            },
        })

    return render_template('admin_students.html',
                         students=claimed_student_views,
                         class_display_label=class_display_label,
                         current_class_id=current_class_id,
                         current_class_section=class_row.section if class_row else None,
                         current_class_display_name=class_row.display_name if class_row else None,
                         current_class_join_code=display_join_code,
                         claimed_students=claimed_student_views,
                         unclaimed_seats=unclaimed_seats,
                         student_balances_by_seat_id=student_balances_by_seat_id,
                         student_rent_privileges_by_seat_id=student_rent_privileges_by_seat_id,
                         student_hall_pass_balances_by_seat_id=student_hall_pass_balances_by_seat_id,
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
    if not class_id:
        return jsonify({'status': 'error', 'message': 'Class ID required'}), 400

    user_id = g.canonical_context.user_id
    class_row = verify_teacher_owns_class(class_id, user_id)
    if class_row is None:
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

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

    ctx = g.canonical_context
    user_id = ctx.user_id
    current_class_id = ctx.class_id
    if current_class_id and class_id != current_class_id:
        return jsonify({
            'status': 'error',
            'message': 'Class scope mismatch. Switch class from the navigation to continue.',
        }), 403

    class_row = verify_teacher_owns_class(class_id, user_id)
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
        idempotency_key = f"feat:iden:set-class-timezone:{user_id}:{class_id}:{timezone_name}"
        # Route reads above may open an implicit transaction; clear it so FEAT owns the boundary.
        db.session.rollback()
        with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
            # Persist an explicit confirmed UTC value distinct from default placeholder UTC.
            class_row.class_timezone = 'Etc/UTC' if timezone_name == 'UTC' else timezone_name
    except Exception:
        current_app.logger.error(
            "Failed to set class timezone for class_id=%s", class_id
        )
        return jsonify({'status': 'error', 'message': 'Could not save class timezone.'}), 500

    _remove_pending_class_timezone_confirmation(class_id)
    return jsonify({
        'status': 'success',
        'message': 'Class timezone saved.',
        'class_timezone': class_row.class_timezone,
        'class_identifier': class_row.display_name or get_display_join_code(class_row.class_id),
    }), 200


@admin_bp.route('/students/<string:actor_public_id>')
@admin_required
def student_detail_public(actor_public_id):
    """View detailed information for a specific student via public-id URL."""
    user_id = g.canonical_context.user_id
    current_class_id = g.canonical_context.class_id
    nav_payload = _read_student_detail_nav_token(request.args.get('nav', ''))
    if not nav_payload:
        abort(404)

    expected_user_id = int(nav_payload.get("user_id") or 0)
    if expected_user_id and expected_user_id != int(user_id or 0):
        abort(404)
    expected_public_id = str(nav_payload.get("actor_public_id") or "")
    expected_class_id = str(nav_payload.get("class_id") or "")
    if expected_public_id != actor_public_id:
        abort(404)

    scoped_seat = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.public_id == actor_public_id,
            Seat.role == "student",
            ClassEconomy.teacher_user_id == user_id,
        )
        .first()
    )
    if not scoped_seat or not scoped_seat.user_id:
        abort(404)
    if expected_class_id and str(scoped_seat.class_id or "") != expected_class_id:
        abort(404)
    # DOM-IDEN-006: student detail must be scoped to the active canonical class
    if current_class_id and str(scoped_seat.class_id or "") != str(current_class_id):
        abort(404)

    student = scoped_seat
    class_id = scoped_seat.class_id
    seat_id = scoped_seat.id

    # Phase 6-7: Build canonical identity view model
    identity_view = build_identity_profile_view(seat_id, class_id)
    if not identity_view:
        abort(404)

    tx_scope = sa.and_(Transaction.seat_id == seat_id, Transaction.class_id == class_id)
    att_scope = sa.and_(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    )

    # Attendance context uses the canonical PROD session backend.
    # Fetch last rent payment
    rent_query = Transaction.query.filter(tx_scope, Transaction.type == "rent")
    latest_rent = rent_query.order_by(Transaction.timestamp.desc()).first()
    student.rent_last_paid = latest_rent.timestamp if latest_rent else None

    # Fetch last property tax payment
    tax_query = Transaction.query.filter(tx_scope, Transaction.type == "property_tax")
    latest_tax = tax_query.order_by(Transaction.timestamp.desc()).first()
    student.property_tax_last_paid = latest_tax.timestamp if latest_tax else None

    # Compute due dates and overdue status using class-local timezone
    from datetime import date
    from app.utils.canonical_temporal_resolver import _get_class_timezone
    effective_tz = _get_class_timezone(class_id)
    today = utc_now().astimezone(effective_tz).date()
    class_tz = effective_tz
    # Rent due on 5th, overdue after 6th
    rent_due = date(today.year, today.month, 5)
    student.rent_due_date = rent_due
    student.rent_overdue = today > rent_due and (
        not student.rent_last_paid or student.rent_last_paid.astimezone(class_tz).date() <= rent_due
    )

    # Property tax due on 5th, overdue after 6th
    tax_due = date(today.year, today.month, 5)
    student.property_tax_due_date = tax_due
    student.property_tax_overdue = today > tax_due and (
        not student.property_tax_last_paid or student.property_tax_last_paid.astimezone(class_tz).date() <= tax_due
    )

    transactions_query = Transaction.query.filter(tx_scope)

    transactions = transactions_query.order_by(Transaction.timestamp.desc()).all()
    _entitlement_query = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.event_type == "GRANTED",
        )
    )
    if class_id:
        _entitlement_query = _entitlement_query.filter(EntitlementEvent.class_id == class_id)
    _entitlements_raw = _entitlement_query.order_by(EntitlementEvent.timestamp.desc()).all()
    store_purchases = [
        SimpleNamespace(
            id=ent.entitlement_id,
            seat_id=ent.target_seat_id,
            class_id=ent.class_id,
            store_item=db.session.get(StoreItem, ent.product_id),
            store_item_id=ent.product_id,
            status=derive_display_status(ent.entitlement_id),
            purchased_at=ent.timestamp,
            purchase_date=ent.timestamp,
            expiry_date=None,
            quantity=1,
        )
        for ent in _entitlements_raw
    ]
    attendance_rows = (
        AttendanceSession.query.filter(att_scope)
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .limit(50)
        .all()
    )
    class_section = (
        scoped_seat.class_economy.section
        if scoped_seat and scoped_seat.class_economy and scoped_seat.class_economy.section
        else ""
    )
    attendance_display_rows = [
        SimpleNamespace(
            id=row.id,
            timestamp=row.timestamp,
            status=row.status,
            period=class_section,
            reason=row.reason_code,
        )
        for row in attendance_rows
    ]
    latest_attendance_event = attendance_display_rows[0] if attendance_display_rows else None

    scoped_seat = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(IdentityProfile.id == student.identity_profile.id, Seat.class_id == class_id)
        .first()
        if class_id else None
    )

    # Removed legacy insurance enrollment lookup.
    active_insurance = None

    # CRITICAL: Get scoped balances for current class_id + seat_id only.
    scoped_checking_balance = 0
    scoped_savings_balance = 0
    scoped_total_earnings = 0

    if class_id and scoped_seat:
        from app.services.ledger_service import get_available_balance
        scoped_checking_balance = get_available_balance(scoped_seat.id, class_id, 'checking')
        scoped_savings_balance = get_available_balance(scoped_seat.id, class_id, 'savings')
    else:
        current_app.logger.warning(
            "Missing canonical class/seat scope for student_detail student=%s class_id=%s.",
            student.id,
            class_id,
        )

    # Get active rent privileges (per-period items)
    rent_privileges = _get_rent_privileges_for_student(student, class_id, None)
    hall_pass_balance = get_hall_pass_balance(student.id, class_id)

    class_row = scoped_seat.class_economy if scoped_seat and scoped_seat.class_economy else None
    class_display_label = (
        (class_row.section or class_row.display_name or class_row.class_id)
        if class_row
        else "Current Class"
    )

    payroll_events = (
        PayrollEvent.query
        .filter(
            PayrollEvent.class_id == class_id,
            PayrollEvent.target_seat_id == seat_id,
        )
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .limit(50)
        .all()
    )
    payroll_event_history = _build_payroll_event_display_rows(
        ctx=g.canonical_context,
        payroll_events=payroll_events,
        class_label=class_display_label,
    )
    scoped_total_earnings = float(
        sum(
            Decimal(row.get("amount") or 0)
            for row in payroll_event_history
        )
    )

    # CRITICAL: Fetch current class Join Code for Account Recovery display.
    join_codes = {}
    if class_row and class_row.join_code:
        join_codes[class_display_label] = class_row.join_code

    _student_user = db.session.get(User, student.user_id) if student.user_id else None
    reset_code_is_active = bool(
        _student_user
        and _student_user.reset_code
        and _student_user.reset_code_expires_at
        and ensure_utc(_student_user.reset_code_expires_at) >= utc_now()
    )
    # Phase 6-7: identity fields sourced from view model (not raw ORM attributes)
    student_has_completed_setup = bool(_student_user and _student_user.username_hash)
    reset_code = _student_user.reset_code if _student_user else None
    reset_code_expires_at = _student_user.reset_code_expires_at if _student_user else None

    # Phase 6-7 VERIFIED: identity_view passes all name/notes fields via view model namespace
    return render_template('student_detail.html',
                         student=student,
                         identity_view=identity_view,
                         student_has_completed_setup=student_has_completed_setup,
                         reset_code=reset_code,
                         reset_code_expires_at=reset_code_expires_at,
                         reset_code_is_active=reset_code_is_active,
                         join_codes=join_codes,
                         transactions=transactions,
                         entitlements=store_purchases,
                         latest_attendance_event=latest_attendance_event,
                         attendance_events=attendance_display_rows,
                         active_insurance=active_insurance,
                         scoped_checking_balance=scoped_checking_balance,
                         scoped_savings_balance=scoped_savings_balance,
                         scoped_total_earnings=scoped_total_earnings,
                         payroll_event_history=payroll_event_history,
                         hall_pass_balance=hall_pass_balance,
                         current_join_code=None,
                         current_class_id=class_id,
                         rent_privileges=rent_privileges)


@admin_bp.route('/student/<int:seat_id>/adjust-hall-pass-entitlements', methods=['POST'])
@admin_required
def adjust_hall_pass_entitlements(seat_id):
    """Grant or remove hall-pass entitlements for a student."""
    canonical_context = getattr(g, "canonical_context", None)
    if not canonical_context:
        abort(403)

    target_seat = db.session.get(Seat, seat_id)
    if not target_seat:
        abort(404)

    # Verify teacher owns this class
    if not verify_teacher_owns_class(target_seat.class_id, canonical_context.user_id):
        abort(404)

    action = (request.form.get('hall_pass_action') or '').strip().lower()
    quantity = request.form.get('hall_pass_quantity', type=int)

    if quantity is None or quantity <= 0 or action not in {"add", "remove"}:
        flash("Choose Add or Remove and enter a positive hall-pass quantity.", "error")
        return _redirect_to_student_detail(target_seat.public_id)

    student_name = target_seat.identity_profile.full_name if target_seat.identity_profile else str(target_seat.id)

    # Get teacher seat for actor_seat_id
    teacher_seat = Seat.query.filter_by(
        user_id=canonical_context.user_id,
        class_id=target_seat.class_id,
    ).first()

    if not teacher_seat:
        flash(f"Error: Teacher seat not found for class {target_seat.class_id}.", "error")
        return _redirect_to_student_detail(target_seat.public_id)

    if action == "add":
        # Use FEAT-STOR-004 to grant entitlements
        result = execute_direct_grant(
            canonical_context=canonical_context,
            target_seat_id=target_seat.id,
            product_id=1,  # TODO: Determine correct product_id for hall passes from policy
            quantity=quantity,
        )

        if result.success:
            flash(f"Granted {quantity} hall pass(es) to {student_name}.", "success")
        else:
            error_msg = result.error_message or f"Grant failed: {result.error_code}"
            flash(error_msg, "error")
    else:
        # Remove functionality requires FEAT-STOR-002 (revocation/lifecycle transitions)
        # which is not yet implemented in Phase 4
        flash(
            "Hall pass removal is not yet available. Use FEAT-STOR-002 (pending implementation). "
            "Contact support to revoke hall passes.",
            "warning"
        )

    return _redirect_to_student_detail(target_seat.public_id)


@admin_bp.route('/student/edit', methods=['POST'])
@admin_required
def edit_student():
    """Edit student basic information."""
    seat_id = request.form.get('seat_id', type=int)
    canonical_context = getattr(g, "canonical_context", None)
    user_id = canonical_context.user_id
    current_class_id = (getattr(canonical_context, "class_id", None) or "").strip()

    if not seat_id:
        abort(404)
    if not current_class_id:
        abort(404)

    student = db.session.get(Seat, seat_id)
    if not student:
        # Not accessible by this admin
        abort(404)
    if student.class_id != current_class_id:
        abort(404)
    if not verify_teacher_owns_class(current_class_id, user_id):
        abort(404)

    # Get form data
    new_first_name = request.form.get('first_name', '').strip()
    last_name_input = request.form.get('last_name', '').strip()
    if not new_first_name or not last_name_input:
        flash("First name and last name are required.", "error")
        return _redirect_to_student_detail(student.public_id)
    notes_input = request.form.get('notes', '').strip()
    student_profile = student.identity_profile
    if student_profile is None:
        flash("Student display profile is missing.", "error")
        return redirect(url_for('admin.students'))

    # Check if name changed (keep seat identity fields in sync).
    current_first_name = student_profile.first_name or ""
    current_last_name = student_profile.last_name or ""
    current_notes = student_profile.notes or ""
    name_changed = (
        new_first_name != current_first_name
        or last_name_input != current_last_name
        or notes_input != current_notes
    )

    student_profile.first_name = new_first_name
    student_profile.last_name = last_name_input
    student_profile.notes = notes_input or None
    student.claim_first_name_hash = hash_username_lookup(new_first_name.lower())
    student.claim_last_name_hash = hash_username_lookup(last_name_input.lower())

    # Handle account reset — generate recovery code per DOM-IDEN-002 §IX
    reset_login = request.form.get('reset_login') == 'on'
    if reset_login:
        import secrets as _secrets
        _ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = ''.join(_secrets.choice(_ALPHABET) for _ in range(8))
        _reset_user = db.session.get(User, student.user_id) if student.user_id else None
        if _reset_user:
            _now = utc_now()
            _reset_user.reset_code = code
            _reset_user.reset_code_generated_at = _now
            _reset_user.reset_code_expires_at = _now + timedelta(minutes=10)

            current_app.logger.info(
                f"Reset code generated for seat {student.id} (user {_reset_user.id}) by admin {user_id}"
            )

            flash(f"Reset code generated for {student_profile.full_name}: {code} — Expires in 10 minutes. "
                  f"Give this code to the student.", "warning")

    try:
        db.session.commit()
        if name_changed:
            flash(f"Successfully updated {student_profile.full_name}'s information.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"FAILED TO EDIT STUDENT EXCEPTION: {e}")
        current_app.logger.error(f"Error updating student {seat_id}")
        flash("Error updating student due to internal error", "error")
        return redirect(url_for('admin.students'))

    if reset_login:
        return _redirect_to_student_detail(student.public_id)

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

    seat_id = request.form.get('seat_id', type=int)
    confirmation = request.form.get('confirmation', '').strip()

    if not seat_id:
        current_app.logger.error("No seat_id provided in delete request")
        flash("Error: No student identifier provided.", "error")
        return redirect(url_for('admin.students'))

    if confirmation != 'DELETE':
        current_app.logger.info(f"Delete cancelled: confirmation '{confirmation}' != 'DELETE'")
        flash("Delete cancelled: confirmation text did not match.", "warning")
        return redirect(url_for('admin.students'))

    student = db.session.get(Seat, seat_id)
    if not student:
        abort(404)
    if not verify_teacher_owns_class(student.class_id, g.canonical_context.user_id):
        abort(404)
    student_name = student.identity_profile.full_name if student.identity_profile else str(student.id)

    # Prevent deletion of teacher student accounts
    if student.role == "teacher":
        flash("Teacher student accounts cannot be deleted directly. They are removed only when the class is deleted.", "error")
        return redirect(url_for('admin.students'))

    try:
        was_hard_deleted = _remove_student_from_teacher_scope(student, g.canonical_context.user_id)
        if was_hard_deleted:
            flash(f"Deleted {student_name}.", "success")
        else:
            flash(f"Removed {student_name} from this class. Student still exists in other linked classes.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting student {student_name}")
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
        for seat_id in student_ids:
            student = db.session.get(Seat, int(seat_id))
            if student and student.role != "teacher":
                was_hard_deleted = _remove_student_from_teacher_scope(student, g.canonical_context.user_id)
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
        current_app.logger.error(f"Error deleting students: {e}")
        return jsonify({"status": "error", "message": "An error occurred while deleting students. Please try again."}), 500


@admin_bp.route('/students/delete-block', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_block():
    """Backwards-compatible block deletion wrapper that resolves to join-code deletion."""
    data = request.get_json(silent=True) or {}
    section = data.get('block', '').strip().upper()
    user_id = g.canonical_context.user_id

    if not section:
        return jsonify({"status": "error", "message": "No block specified."}), 400

    gate_error = _validate_destruction_gate(data, expected_phrase=f"DELETE BLOCK {section}")
    if gate_error:
        return gate_error

    try:
        class_ids = [
            cid for cid in _get_class_ids_by_block(g.canonical_context, [section]).values() if cid
        ]
        if not class_ids:
            return jsonify({"status": "success", "message": f"No class found for Block {section}. Nothing to delete."})
        if len(class_ids) > 1:
            return jsonify({
                "status": "error",
                "message": f"Block {section} has multiple classes. Delete by class explicitly."
            }), 400

        class_row = get_class_economy(class_ids[0])
        if not class_row:
            return jsonify({"status": "error", "message": "Join code not found or access denied."}), 404
        _hard_delete_class_scope(class_row.class_id, g.canonical_context)

        if class_ids:
            Seat.query.filter(
                Seat.class_id.in_(class_ids),
                Seat.claimed_at.is_(None),
            ).delete(synchronize_session=False)
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted class Block {section} and scoped records."
        })
    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting block {section}: {e}")
        return jsonify({"status": "error", "message": "An error occurred while deleting the block. Please try again."}), 500


@admin_bp.route('/join-code/delete', methods=['POST'])
@admin_bp.route('/join-code', methods=['DELETE'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def delete_join_code():
    """Hard-delete a class economy and all records scoped to the join code."""
    data = request.get_json(silent=True) or request.form
    display_join_code = (data.get('join_code') or '').strip().upper()
    user_id = g.canonical_context.user_id

    if not display_join_code:
        return jsonify({"status": "error", "message": "join_code is required."}), 400

    class_rows = get_all_classes_by_teacher(user_id)
    class_row = next(
        (row for row in class_rows if (get_display_join_code(row.class_id) or "").upper() == display_join_code),
        None,
    )
    if not class_row or not _admin_owns_class(g.canonical_context, class_row.class_id):
        return jsonify({"status": "error", "message": "Join code not found or access denied."}), 403

    confirm_join_code = str((data or {}).get("confirm_join_code", "")).strip().upper()
    if confirm_join_code:
        if confirm_join_code != display_join_code:
            return jsonify({
                "status": "error",
                "message": "Confirmation failed: join code did not match."
            }), 400
    else:
        gate_error = _validate_destruction_gate(data, expected_phrase=f"DELETE JOIN CODE {display_join_code}")
        if gate_error:
            return gate_error

    try:
        if not class_row:
            return jsonify({"status": "error", "message": "Join code not found or access denied."}), 404
        _hard_delete_class_scope(class_row.class_id, g.canonical_context)
        return jsonify({
            "status": "success",
            "message": f"Join code {display_join_code} and all scoped records were permanently deleted."
        })
    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting join code {display_join_code}: {e}")
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
    seat_id = data.get('seat_id')
    if seat_id:
        try:
            seat_id = int(seat_id)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid seat ID."}), 400

    user_id = g.canonical_context.user_id

    if not seat_id:
        return jsonify({"status": "error", "message": "No seat ID provided."}), 400

    try:
        # Find the Seat entry (joining to ClassEconomy to verify user ownership)
        seat_entry = (
            Seat.query
            .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
            .filter(
                Seat.id == seat_id,
                ClassEconomy.teacher_user_id == user_id,
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

        student_name = (
            seat_entry.identity_profile.full_name
            if seat_entry.identity_profile
            else 'Unknown'
        )

        # Delete the Seat entry (this is the only record for unclaimed seats)
        delete_seat_with_profile(seat_entry)
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted pending student {student_name}."
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting pending student: {e}")
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
    seat_ids = data.get('seat_ids', [])
    section = data.get('block', '').strip().upper()
    user_id = g.canonical_context.user_id

    if not seat_ids and not section:
        return jsonify({
            "status": "error",
            "message": "Either seat_ids or block must be provided."
        }), 400

    try:
        deleted_count = 0

        if section:
            # Delete all unclaimed Seat entries for this teacher and section
            block_class_ids = [
                cid for cid in _get_class_ids_by_block(g.canonical_context, [section]).values() if cid
            ]
            if block_class_ids:
                deleted_count = Seat.query.filter(
                    Seat.class_id.in_(block_class_ids),
                    Seat.claimed_at.is_(None),
                ).delete(synchronize_session=False)
        else:
            # Delete specific Seat entries
            for seat_id in seat_ids:
                seat_entry = (
                    Seat.query
                    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                    .filter(
                        Seat.id == seat_id,
                        ClassEconomy.teacher_user_id == user_id,
                    )
                    .first()
                )

                if seat_entry:
                    # Verify it's actually unclaimed
                    if seat_entry.claimed_at is None and seat_entry.student_id is None:
                        delete_seat_with_profile(seat_entry)
                        deleted_count += 1

        message = f"Successfully deleted {deleted_count} pending student(s)."
        if section:
            message = f"Successfully deleted {deleted_count} pending student(s) from Block {section}."

        return jsonify({
            "status": "success",
            "message": message,
            "deleted_count": deleted_count
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error bulk deleting pending students: {e}")
        return jsonify({"status": "error", "message": "An error occurred while bulk deleting pending students. Please try again."}), 500


@admin_bp.route('/student/add-individual', methods=['POST'])
@admin_required
def add_individual_student():
    """Add a single student (same as bulk upload but for one student)."""
    try:
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        block_select = (request.form.get('block_select') or '').strip()
        new_block_name = request.form.get('new_block_name', '').strip().upper()
        additional_notes = (request.form.get('additional_notes') or '').strip()

        if not all([first_name, last_name, block_select]):
            flash("All fields are required.", "error")
            return redirect(url_for('admin.students'))

        section = new_block_name if block_select == '__CREATE_NEW__' else block_select.upper()
        # Student.block is VARCHAR(10) in the DB; enforce before insert to avoid flush-time errors.
        if len(section) > 10:
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

        user_id = g.canonical_context.user_id
        class_context = _resolve_student_add_class_context(
            g.canonical_context,
            block_select=block_select,
            section=section,
        )
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

        with FEATContext("FEAT-IDEN-001", idempotency_key=f"admin:add-individual-student:{class_id}:{first_name}:{last_name}:{dedupe_key}"):
            # Seat only — no User until student completes claim (DOM-IDEN-002 §VIII).
            profile = IdentityProfile(
                profile_type='student',
                first_name=first_name,
                last_name=last_name,
                notes=additional_notes or None,
            )

            # Verify class exists before creating Seat
            if not get_class_economy(class_id):
                raise ValueError(f"Class {class_id} does not exist")

            new_seat = create_pending_student_seat(
                class_id=class_id,
                dedupe_code=dedupe_key,
            )

            profile.seat_id = new_seat.id

            if class_context.get('class_created'):
                _queue_pending_class_timezone_confirmation(class_context.get('class_row'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error adding individual student")
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
        section = request.form.get('block', '').strip().upper()
        username = request.form.get('username', '').strip()
        pin = request.form.get('pin', '').strip()
        passphrase = request.form.get('passphrase', '').strip()
        hall_passes = int(request.form.get('hall_passes', 3))
        rent_enabled = request.form.get('rent_enabled') == 'on'
        setup_complete = request.form.get('setup_complete') == 'on'

        if not all([first_name, last_name, dob_str, section]):
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

        user_id = g.canonical_context.user_id
        class_context = _resolve_student_add_class_context(
            g.canonical_context,
            block_select=section,
            section=section,
        )
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

        # Check for duplicates globally.
        potential_duplicates = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .filter(
                IdentityProfile.first_name == first_name,
            )
            .all()
        )

        for existing_student in potential_duplicates:
            # Verify credential matches.
            credential_matches, is_primary, canonical_hash = match_claim_hash(
                existing_student.first_half_hash if existing_student.identity_profile else None,
                first_initial,
                last_initial,
                dob_sum,
                existing_student.salt,
            )

            if credential_matches:
                if canonical_hash and not is_primary:
                    existing_student.first_half_hash = canonical_hash
                user_id = g.canonical_context.user_id
                existing_class_seat = Seat.query.filter_by(
                    user_id=existing_student.user_id,
                    class_id=class_id,
                ).first()
                if existing_class_seat and existing_class_seat.claimed_at:
                    flash(f"Student {first_name} {last_name} is already in your class.", "info")
                else:
                    flash(f"Student {first_name} {last_name} already exists. Linking to your class.", "warning")
                    from app.feats.class_configuration import execute_provision_student_seat
                    provision_result = execute_provision_student_seat(
                        canonical_context=g.canonical_context,
                        class_id=class_id,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    if not provision_result.success:
                        current_app.logger.error(
                            "FEAT-CLASS-002 provision failed linking duplicate: %s",
                            provision_result.error_message,
                        )
                    if class_context.get('class_created'):
                        _queue_pending_class_timezone_confirmation(class_context.get('class_row'))
                return redirect(url_for('admin.students'))

        with FEATContext("FEAT-IDEN-001", idempotency_key=f"admin:add-manual-student:{class_id}:{first_name}:{last_name}:{dedupe_key}"):
            # Seat only — no User until student completes claim (DOM-IDEN-002 §VIII).
            profile = IdentityProfile(
                profile_type='student',
                first_name=first_name,
                last_name=last_name,
            )

            # Verify class exists before creating Seat (class was resolved or created above)
            if not get_class_economy(class_id):
                raise ValueError(f"Class {class_id} does not exist")

            new_seat = create_pending_student_seat(
                class_id=class_id,
                dedupe_code=dedupe_key,
                has_received_rent_exemption=not rent_enabled,
            )

            profile.seat_id = new_seat.id

            if class_context.get('class_created'):
                _queue_pending_class_timezone_confirmation(class_context.get('class_row'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error creating manual student")
        flash(f"Cannot create student due to internal error", "error")

    return redirect(url_for('admin.students'))


# -------------------- STORE MANAGEMENT --------------------

def _end_of_day_utc(date_obj):
    """Convert a local date to end-of-day UTC using SLE day boundaries."""
    if not date_obj:
        return None
    bounds = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="evaluation_day_boundaries",
        evaluation_date=date_obj,
    )
    return bounds.boundary_end_utc

import uuid

def generate_collective_goal_instance_code():
    return str(uuid.uuid4())

@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store_management():
    """Manage store items - view, create, edit, delete."""
    user_id = g.canonical_context.user_id
    feature_options = get_admin_feature_join_code_options('store', canonical_context=g.canonical_context)
    current_class_id = g.canonical_context.class_id
    selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
    if not selected_scope:
        abort(404)
    selected_join_code = selected_scope['join_code']
    selected_block = selected_scope['block']
    form = StoreItemForm()

    # Limit store scope to classes where the feature is enabled.
    blocks = [option['block'] for option in feature_options if option.get('block')]
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Build class_labels_by_block dictionary for template
    class_labels_by_block = _get_class_labels_for_blocks(g.canonical_context, blocks)

    if form.validate_on_submit():
        submitted_blocks = {block.strip().upper() for block in (form.blocks.data or []) if block}
        enabled_blocks = {block for block in blocks if block}
        if submitted_blocks and not submitted_blocks.issubset(enabled_blocks):
            abort(404)
        payload_hash = hashlib.sha256(
            json.dumps(
                {
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
        idempotency_key = f"feat:store:item-create:{selected_scope['class_id']}:{payload_hash}"

        db.session.rollback()
        with FEATContext("FEAT-SETTINGS-001", idempotency_key=idempotency_key):
            new_item = create_store_item(
                user_id=user_id,
                class_id=selected_scope['class_id'],
                name=form.name.data,
                description=form.description.data,
                item_type=form.item_type.data,
                price=form.price.data,
                limit_per_student=form.limit_per_student.data,
                is_active=form.is_active.data,
                is_long_term_goal=form.is_long_term_goal.data,
                bypass_cwi_warnings=form.bypass_cwi_warnings.data,
                is_bundle=form.is_bundle.data,
                bundle_quantity=form.bundle_quantity.data if form.is_bundle.data else None,
                bulk_discount_enabled=form.bulk_discount_enabled.data,
                bulk_discount_quantity=form.bulk_discount_quantity.data if form.bulk_discount_enabled.data else None,
                bulk_discount_percentage=form.bulk_discount_percentage.data if form.bulk_discount_enabled.data else None,
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
                redemption_prompt=form.redemption_prompt.data if form.redemption_prompt.data else None,
            )
            # Set blocks using many-to-many relationship
            if form.blocks.data:
                new_item.set_blocks(form.blocks.data)
        flash(f"'{new_item.name}' has been added to the store.", "success")
        return redirect(url_for('admin.store_management'))

    # Get items for this teacher only.
    items = [
        item for item in StoreItem.query.filter_by(class_id=selected_scope['class_id']).order_by(StoreItem.name).all()
        if not item.blocks_list or selected_block in {b.strip().upper() for b in item.blocks_list if b}
    ]

    # Get store statistics for overview tab
    total_items = len(items)
    active_items = len([i for i in items if i.is_active])
    total_purchases = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.class_id == selected_scope['class_id'],
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .count()
    )

    # Get pending redemption requests from the canonical pending-action workflow.
    pending_redemption_events = (
        PendingAction.query.filter(
            PendingAction.class_id == selected_scope['class_id'],
            PendingAction.authoritative_feat == "FEAT-STOR-002",
        )
        .order_by(PendingAction.submitted_at.desc())
        .limit(10)
        .all()
    )
    pending_redemptions = []
    if pending_redemption_events:
        entitlement_ids = [e.entitlement_id for e in pending_redemption_events]
        grants = EntitlementEvent.query.filter(
            EntitlementEvent.class_id == selected_scope["class_id"],
            EntitlementEvent.entitlement_id.in_(entitlement_ids),
            EntitlementEvent.event_type == 'GRANTED'
        ).all()
        grants_dict = {}
        for grant in grants:
            if grant.entitlement_id not in grants_dict or grant.timestamp > grants_dict[grant.entitlement_id].timestamp:
                grants_dict[grant.entitlement_id] = grant

        store_item_ids = {grant.product_id for grant in grants_dict.values() if grant.product_id}
        store_items_dict = {}
        if store_item_ids:
            store_items = StoreItem.query.filter(StoreItem.id.in_(store_item_ids)).all()
            store_items_dict = {i.id: i for i in store_items}

        for event in pending_redemption_events:
            # Enforce class_id validation: seat must belong to the selected class
            seat = db.session.get(Seat, event.seat_id)
            if not seat or seat.class_id != selected_scope['class_id']:
                continue
            profile = seat.identity_profile if seat else None
            grant = grants_dict.get(event.entitlement_id)
            store_item = store_items_dict.get(grant.product_id) if grant and grant.product_id else None
            
            pending_redemptions.append(SimpleNamespace(
                id=event.entitlement_id,
                student_name=profile.full_name if profile else 'Unknown',
                store_item=store_item,
                class_id=event.class_id,
                purchased_at=event.submitted_at,
                status='processing',
            ))

    # Get recent purchases (all statuses, ordered by purchase date)
    recent_purchases = []
    recent_entitlements = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.class_id == selected_scope['class_id'],
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .order_by(EntitlementEvent.timestamp.desc())
        .limit(10)
        .all()
    )
    for entitlement in recent_entitlements:
        item = db.session.get(StoreItem, entitlement.product_id)
        seat = db.session.get(Seat, entitlement.target_seat_id)
        profile = seat.identity_profile if seat else None

        # Extract quantity from payload (defaults to 1 if not present)
        payload = entitlement.payload or {}
        quantity_total = payload.get('quantity_total', 1)

        # Determine if this is from a bundle purchase
        is_from_bundle = item.is_bundle if item else False

        recent_purchases.append(SimpleNamespace(
            id=entitlement.entitlement_id,
            student_name=profile.full_name if profile else 'Unknown',
            class_id=entitlement.class_id,
            store_item=item,
            status=derive_display_status(entitlement.entitlement_id),
            purchased_at=entitlement.timestamp,
            purchase_date=entitlement.timestamp,
            quantity=quantity_total,
            is_from_bundle=is_from_bundle,
        ))

    collective_progress_by_item = {}
    collective_items = [item for item in items if item.item_type == 'collective']
    if collective_items:
        _ce = get_class_economy(selected_scope['class_id'])
        class_economy_rows = [_ce] if _ce else []
        join_code_to_block = {}
        join_code_to_label = {}

        # Count unique claimed seats per class
        class_sizes = {}
        class_size_query = (
            db.session.query(
                ClassEconomy.class_id,
                db.func.count(db.func.distinct(Seat.id)).label('student_count')
            )
            .join(Seat, Seat.class_id == ClassEconomy.class_id)
            .filter(
                ClassEconomy.class_id == selected_scope['class_id'],
                Seat.role == 'student',
                Seat.claimed_at.isnot(None),
            )
            .group_by(ClassEconomy.class_id)
            .all()
        )
        class_sizes = {row.class_id: int(row.student_count or 0) for row in class_size_query}

        for ce_row in class_economy_rows:
            if not ce_row.class_id:
                continue
            display_join_code = get_display_join_code(ce_row.class_id)
            if not display_join_code:
                continue
            join_code_to_block.setdefault(display_join_code, (ce_row.section or '').strip().upper())
            join_code_to_label.setdefault(display_join_code, ce_row.display_name or display_join_code)

        collective_item_ids = [item.id for item in collective_items]
        collective_counts = (
            db.session.query(
                EntitlementEvent.product_id,
                EntitlementEvent.class_id,
                db.func.count(db.distinct(EntitlementEvent.target_seat_id)).label('student_count'),
            )
            .filter(
                EntitlementEvent.class_id == selected_scope['class_id'],
                EntitlementEvent.product_id.in_(collective_item_ids),
                EntitlementEvent.event_type == "GRANTED",
                EntitlementEvent.acquisition_type == "PURCHASE",
            )
            .group_by(EntitlementEvent.product_id, EntitlementEvent.class_id)
            .all()
        )
        counts_lookup = {
            (row.product_id, row.class_id): int(row.student_count or 0)
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
                count = counts_lookup.get((item.id, selected_scope['class_id']), 0)
                if item.collective_goal_type == 'fixed':
                    target = int(item.collective_goal_target or 0)
                else:
                    target = class_sizes.get(selected_scope['class_id'], 0)
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

    # -------------------- Redemption Audit --------------------
    audit_student = request.args.get('audit_student', '').strip()
    audit_class = request.args.get('audit_class', '').strip()
    audit_action = request.args.get('audit_action', '').strip()
    audit_start_date = request.args.get('audit_start_date', '').strip()
    audit_end_date = request.args.get('audit_end_date', '').strip()
    audit_page = max(1, request.args.get('audit_page', 1, type=int))
    audit_per_page = 25

    join_code_label_map = {}
    teacher_class_rows = get_all_classes_by_teacher(user_id)
    for ce_row in teacher_class_rows:
        display_join_code = get_display_join_code(ce_row.class_id)
        if display_join_code and display_join_code not in join_code_label_map:
            join_code_label_map[display_join_code] = ce_row.display_name or display_join_code

    parsed_audit_action = audit_action.upper() if audit_action else None

    live_query = (
        db.session.query(
            PendingAction.pending_action_id.label("id"),
            PendingAction.entitlement_id.label("entitlement_id"),
            Seat.id.label("seat_id"),
            Seat.class_id.label("class_id"),
            PendingAction.authoritative_feat.label("action"),
            PendingAction.payload.label("notes"),
            ClassEconomy.teacher_user_id.label("user_id"),
            PendingAction.class_id.label("class_id"),
            PendingAction.submitted_at.label("timestamp"),
            sa.literal("LIVE").label("source"),
        )
        .filter(
            PendingAction.class_id == selected_scope['class_id'],
            PendingAction.authoritative_feat == "FEAT-STOR-002",
        )
    )
    if audit_class:
        live_query = live_query.join(ClassEconomy, ClassEconomy.class_id == PendingAction.class_id).filter(
            ClassEconomy.display_name == audit_class
        )
    if parsed_audit_action:
        live_query = live_query.filter(PendingAction.payload["action"].as_string() == parsed_audit_action)
    if audit_start_date:
        try:
            start_day = datetime.strptime(audit_start_date, '%Y-%m-%d').date()
            _sb = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="evaluation_day_boundaries", evaluation_date=start_day)
            live_query = live_query.filter(PendingAction.submitted_at >= _sb.boundary_start_utc)
        except ValueError:
            flash("Invalid audit start date format. Please use YYYY-MM-DD.", "warning")
    if audit_end_date:
        try:
            end_day = datetime.strptime(audit_end_date, '%Y-%m-%d').date()
            _eb = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="evaluation_day_boundaries", evaluation_date=end_day)
            end_dt = _eb.boundary_end_utc + timedelta(seconds=1)
            live_query = live_query.filter(PendingAction.submitted_at < end_dt)
        except ValueError:
            flash("Invalid audit end date format. Please use YYYY-MM-DD.", "warning")

    live_rows = live_query.order_by(PendingAction.submitted_at.desc()).limit(5000).all()
    if audit_student:
        audit_student_lower = audit_student.lower()
        live_rows = [
            row for row in live_rows
            if audit_student_lower in (
                row.student_display_name or "Unknown"
            ).lower()
        ]
    live_keys = {
        (row.id, row.action.value if hasattr(row.action, 'value') else row.action)
        for row in live_rows
    }
    inferred_rows = []

    live_serialized = []
    for row in live_rows:
        seat = db.session.get(Seat, row.seat_id)
        profile = seat.identity_profile if seat else None
        live_serialized.append({
            'student_item_id': row.entitlement_id,
            'student_display_name': profile.full_name if profile else "Unknown",
            'class_display_label': selected_scope.get('join_code') or selected_scope.get('block') or "Unknown",
            'action': row.action.value if hasattr(row.action, 'value') else row.action,
            'notes': row.notes,
            'timestamp': row.timestamp,
            'source': row.source.value if hasattr(row.source, 'value') else row.source,
        })

    audit_rows_all = live_serialized + inferred_rows
    _UTC_MIN = datetime.min.replace(tzinfo=timezone.utc)
    audit_rows_all.sort(key=lambda r: ensure_utc(r['timestamp']) if r['timestamp'] else _UTC_MIN, reverse=True)

    audit_total = len(audit_rows_all)
    audit_total_pages = max(1, math.ceil(audit_total / audit_per_page)) if audit_total else 1
    if audit_page > audit_total_pages:
        audit_page = audit_total_pages
    audit_start_idx = (audit_page - 1) * audit_per_page
    audit_end_idx = audit_start_idx + audit_per_page
    audit_rows = audit_rows_all[audit_start_idx:audit_end_idx]

    audit_class_options = sorted(set(class_labels_by_block.values()))

    rent_managed_item_ids = {
        item.id for item in StoreItem.query.filter_by(
            class_id=selected_scope['class_id'],
            is_rent_linked=True,
        ).all()
    }

    # Group recent purchases by item for template iteration
    purchases_by_item_id = {}
    for purchase in recent_purchases:
        if purchase.store_item and hasattr(purchase.store_item, 'id'):
            item_id = purchase.store_item.id
            if item_id not in purchases_by_item_id:
                purchases_by_item_id[item_id] = []
            purchases_by_item_id[item_id].append(purchase)

    # Add purchases list to each item for template access
    for item in items:
        item.purchases = purchases_by_item_id.get(item.id, [])

    # Build economic view from Class Configuration domain
    economic_view = build_economic_view(selected_scope['class_id'])

    view = build_store_management_view(
        items=items,
        total_items=total_items,
        active_items=active_items,
        total_purchases=total_purchases,
        pending_redemptions=pending_redemptions,
        recent_purchases=recent_purchases,
        class_labels_by_block=class_labels_by_block,
        rent_managed_item_ids=rent_managed_item_ids,
        collective_progress_by_item=collective_progress_by_item,
        audit_rows=audit_rows,
        audit_total=audit_total,
        audit_page=audit_page,
        audit_total_pages=audit_total_pages,
        audit_class_options=audit_class_options,
        economic=economic_view,
        audit_student=audit_student,
        audit_class=audit_class,
        audit_action=audit_action,
        audit_start_date=audit_start_date,
        audit_end_date=audit_end_date,
        selected_scope=selected_scope,
        feature_options=feature_options,
    )

    return render_template('admin_store.html', form=form, view=view, current_page="store")


@admin_bp.route('/store/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_store_item(item_id):
    """Edit an existing store item."""
    user_id = g.canonical_context.user_id
    selected_scope = require_admin_feature_scope(
        'store',
        canonical_context=g.canonical_context,
    )
    item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
    if item.blocks_list and selected_scope['block'] not in {b.strip().upper() for b in item.blocks_list if b}:
        abort(404)
    form = StoreItemForm(obj=item)

    # Populate blocks choices from the teacher's students
    blocks = [option['block'] for option in get_admin_feature_join_code_options('store', canonical_context=g.canonical_context) if option.get('block')]
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
        with FEATContext("FEAT-SETTINGS-001", idempotency_key=idempotency_key):
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
    user_id = g.canonical_context.user_id
    selected_scope = require_admin_feature_scope(
        'store',
        canonical_context=g.canonical_context,
    )
    item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
    if item.blocks_list and selected_scope['block'] not in {b.strip().upper() for b in item.blocks_list if b}:
        abort(404)

    # Prevent deletion if linked to rent settings
    if _block_rent_linked_store_item(item):
        return redirect(url_for('admin.store_management'))

    idempotency_key = f"feat:store:item-deactivate:{selected_scope['class_id']}:{item.id}"
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=idempotency_key):
        item = StoreItem.query.filter_by(id=item_id, class_id=selected_scope['class_id']).first_or_404()
        deactivate_store_item(item)
    flash(f"'{item.name}' has been deactivated and hidden from new purchases.", "success")
    return redirect(url_for('admin.store_management'))


@admin_bp.route('/store/hard-delete/<int:item_id>', methods=['POST'])
@admin_required
def hard_delete_store_item(item_id):
    """Hard item deletion is restricted to the join-code deletion workflow."""
    user_id = g.canonical_context.user_id
    selected_scope = require_admin_feature_scope(
        'store',
        canonical_context=g.canonical_context,
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
    is_managed_by_rent = bool(item.is_rent_linked)

    if is_managed_by_rent:
        flash(f"Cannot delete '{item.name}' because it is managed by Rent Settings. Please remove it from Rent Settings instead.", "error")
        return True
    return False

def _sync_rent_items_to_store(rent_settings, user_id, class_id):
    """
    Sync rent items with store items.
    Creates or updates store items for rent items that are marked as available in store.
    Deactivates store items for rent items that are no longer available.

    FIX: Prevents duplicate store items when applying rent settings to all periods.
    Store items use canonical seat-level visibility rows; block labels are derived metadata.
    """
    from app.models import StoreItem, StoreItemVisibility, Seat

    if not class_id:
        current_app.logger.warning(
            "Skipping rent-to-store sync for teacher %s: no class_id provided",
            user_id,
        )
        return

    rent_store_items = (
        StoreItem.query.filter(
            StoreItem.class_id == class_id,
            StoreItem.is_rent_linked.is_(True),
        )
        .order_by(StoreItem.id.asc())
        .all()
    )

    for store_item in rent_store_items:
        if not store_item.name:
            continue

        if store_item.class_id != class_id:
            store_item.class_id = class_id
        store_item.is_active = True

        desired_blocks = {block.strip().upper() for block in store_item.blocks_list if block}
        if not desired_blocks:
            continue

        for block in desired_blocks:
            create_store_item_block(store_item_id=store_item.id, block=block)

        existing_visibility_seat_ids = [
            seat_id
            for (seat_id,) in (
                db.session.query(StoreItemVisibility.seat_id)
                .join(Seat, Seat.id == StoreItemVisibility.seat_id)
                .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                .filter(
                    StoreItemVisibility.store_item_id == store_item.id,
                    ClassEconomy.class_id == class_id,
                    ClassEconomy.section.isnot(None),
                    ~ClassEconomy.section.in_(desired_blocks),
                )
                .all()
            )
        ]
        if existing_visibility_seat_ids:
            StoreItemVisibility.query.filter(
                StoreItemVisibility.store_item_id == store_item.id,
                StoreItemVisibility.seat_id.in_(existing_visibility_seat_ids),
            ).delete(synchronize_session=False)


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
@feat_shell("FEAT-ADMN-001")
@admin_required
def rent_settings():
    """Configure rent settings."""
    user_id = g.canonical_context.user_id
    current_class_id = (getattr(g.canonical_context, "class_id", None) or "").strip()
    if not current_class_id:
        abort(404)
    feature_options = get_admin_feature_join_code_options('rent', canonical_context=g.canonical_context)

    class_row = verify_teacher_owns_class(current_class_id, user_id)
    if not class_row:
        abort(404)
    feature_scope = resolve_feature_class_for_class(current_class_id, 'rent')
    if not feature_scope or not feature_scope["enabled"]:
        abort(404)

    selected_scope = {
        "class_id": class_row.class_id,
        "join_code": get_display_join_code(class_row.class_id),
        "block": (class_row.section or "").strip().upper() or None,
        "label": class_row.display_name or class_row.section or get_display_join_code(class_row.class_id),
    }
    class_id = selected_scope['class_id']
    payroll_settings = PayrollSettings.query.filter_by(
        class_id=class_id,
        is_active=True,
    ).first()
    teacher_blocks = [option['block'] for option in get_admin_feature_join_code_options('rent', canonical_context=g.canonical_context)]
    settings_block = selected_scope['block']

    # Get or create rent settings for this class (class_id is the canonical scope; block column is display-only)
    settings = get_rent_settings(class_id)

    if request.method == 'POST':
        blocks_to_update = [class_id]

        payload_hash = hashlib.sha256(
            json.dumps(
                    {
                        "class_id": selected_scope["class_id"],
                        "settings_block": settings_block,
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

        # Per MAP-UI-001, rent policy configuration is Class Configuration domain (FEAT-SETTINGS-001),
        # not admin action (FEAT-ADMN-001). Policy updates define the contractual terms that cause
        # assessments to exist; this is Class Configuration authority, not Obligations mutation.
        with FEATContext("FEAT-SETTINGS-001", idempotency_key=idempotency_key):
            for block in blocks_to_update:
                # block IS a class_id; query directly — no label-based lookup (INV-ARC-014)
                block_settings = get_rent_settings(block)
                if not block_settings:
                    block_settings = create_rent_settings(class_id=block)

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
            if rent_item_type == 'privilege' and request.form.get(f'rent_item_purchase_duration_{idx}', '').strip() == 'per_use':
                flash(
                    f"'{name}' cannot be saved as privilege with per-use duration. Use the per-use item type instead.",
                    'error',
                )
                continue
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

        # Apply parsed items to each class (blocks_to_update now contains class_ids)
        for block in blocks_to_update:
                # block is now a class_id; fetch settings directly by class_id
                block_settings = get_rent_settings(block)
                if not block_settings:
                    continue

                existing_items = (
                    StoreItem.query.filter(
                        StoreItem.class_id == block_settings.class_id,
                        StoreItem.is_rent_linked.is_(True),
                    )
                    .order_by(StoreItem.id.asc())
                    .all()
                )
                existing_map = {}

                # For the target class, map by ID; for other classes, map by name
                if block == class_id:
                    existing_map = {str(item.id): item for item in existing_items}
                else:
                    existing_map = {item.name: item for item in existing_items}

                processed_items = set()

                # Mid-period lock: detect if any student has paid rent for current coverage period
                mid_period_locked = False
                from app.routes.student import _calculate_rent_coverage_due_date
                now = utc_now()
                coverage_due = _calculate_rent_coverage_due_date(block_settings, now)
                if coverage_due:
                    current_bill_cycle = obligations_service.get_latest_bill_cycle_for_class(block_settings.class_id)
                    paid_count = 0
                    if current_bill_cycle:
                        current_cycle_assessments = obligations_service.get_assessments_for_bill_cycle(
                            current_bill_cycle.id,
                            obligation_type='RENT',
                        )
                        for assessment in current_cycle_assessments:
                            satisfaction_events = obligations_service.get_satisfaction_events(assessment.correlation_id)
                            if satisfaction_events:
                                paid_count += 1
                    if paid_count > 0:
                        mid_period_locked = True

                for item_data in parsed_items:
                    target_item = None

                    # Try to find matching existing item
                    if block == class_id:
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
                        new_item = create_store_item(
                            user_id=user_id,
                            class_id=block_settings.class_id,
                            name=item_data['name'],
                            description=item_data['description'] if item_data['description'] else None,
                            item_type='delayed',
                            price=item_data['store_price'],
                            limit_per_student=(1 if item_data['rent_item_type'] == 'privilege' else None),
                            is_active=item_data['is_available'],
                            is_rent_linked=True,
                        )
                        # No need to add to processed_items as it's new

                # Delete items that were not in the form (and thus not processed)
                for item in existing_items:
                    if item not in processed_items:
                        # If this item had a linked store item, deactivate it
                        if item.store_item_id:
                            deactivate_linked_store_item(item.store_item_id)
                        delete_rent_item(item)

                # Sync to store
                _sync_rent_items_to_store(block_settings, user_id, block_settings.class_id)

                if mid_period_locked and block == class_id:
                    flash("Some changes are locked because students have already paid rent this period. "
                          "Item type, use limits, and hall pass counts will apply next period.", "warning")

        # Rent settings are canonical; no policy-version snapshotting in v2.
        flash("Rent settings updated successfully!", "success")
        return redirect(url_for('admin.rent_settings'))

    # Use view model to get student obligation summary (encapsulates all aggregation)
    from app.services.obligation_view_model import (
        build_class_obligation_summary,
        add_display_formatting_to_class_obligation_summary,
    )

    obligation_summary = build_class_obligation_summary(class_id, 'RENT')
    # Phase 1: Apply display formatting (eliminates template-level ORM property access)
    if obligation_summary:
        obligation_summary = add_display_formatting_to_class_obligation_summary(obligation_summary)

    # Extract basic statistics from view model
    total_students = len(obligation_summary.student_rows) if obligation_summary else 0

    # Get active waivers (still needs manual query for waiver-specific fields not in view model)
    now = utc_now()
    active_waivers = []
    for waiver in obligations_service.get_active_rent_waivers_for_class(
        class_id,
        coverage_date=now,
    ):
        profile = IdentityProfile.query.filter_by(seat_id=waiver.seat_id).first() if waiver.seat_id else None
        active_waivers.append(SimpleNamespace(
            id=waiver.id,
            student=SimpleNamespace(
                full_name=profile.full_name if profile else 'Unknown',
            ),
            waiver_start_date=waiver.coverage_start_time,
            waiver_end_date=waiver.coverage_end_time,
            periods_count=_count_rent_waiver_periods(settings, waiver),
            reason=getattr(waiver, 'notes', None) or getattr(waiver, 'reason', None),
            created_at=waiver.assessed_at,
        ))

    # Build all_students view model dicts for waiver form (no raw SQLAlchemy in templates).
    all_students = []
    if obligation_summary and obligation_summary.student_rows:
        for row in obligation_summary.student_rows:
            all_students.append({
                'id': row['seat_id'],
                'full_name': row['student_name'],
                'block': '',
            })
        all_students.sort(
            key=lambda s: (
                s['full_name'].lower(),
                s['id'],
            )
        )

    # Build class_labels_by_block dictionary
    class_labels_by_block = _get_class_labels_for_blocks(g.canonical_context, teacher_blocks)

    # Build join_codes_by_block dictionary
    join_codes_by_block = _get_join_codes_by_block(g.canonical_context, teacher_blocks)

    # Calculate payroll warning
    payroll_warning = None
    if settings and settings.rent_amount > Decimal('0') and payroll_settings:
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
        rent_items = (
            StoreItem.query.filter(
                StoreItem.class_id == settings.class_id,
                StoreItem.is_rent_linked.is_(True),
            )
            .order_by(StoreItem.id.asc())
            .all()
        )

    # Calculate current rent period dates for settings summary
    rent_active_for_period = False
    current_period_start = None
    current_period_end = None
    next_due_date = None
    current_coverage_due_date = None
    upcoming_coverage_due_date = None

    if settings:
        now_utc = utc_now()
        from app.routes.student import (
            _calculate_rent_coverage_due_date,
            _calculate_rent_deadlines,
            _calculate_upcoming_rent_due_date,
        )

        # Current selected-class period card data (for settings summary display)
        selected_coverage_due = _calculate_rent_coverage_due_date(settings, now_utc)
        selected_due_date, _ = _calculate_rent_deadlines(settings, now_utc)
        selected_next_due = _calculate_upcoming_rent_due_date(settings, selected_due_date, selected_coverage_due)
        if selected_coverage_due and selected_next_due:
            current_period_start = selected_coverage_due + timedelta(days=1)
            current_period_end = selected_next_due
            next_due_date = selected_next_due

        # Coverage dates for waiver form state
        current_coverage_due_date = selected_coverage_due
        upcoming_coverage_due_date = selected_next_due

    # Determine period label based on frequency type
    period_label = "Month"  # Default
    if settings:
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

    # Pre-format display values (Phase 1 Jinja2 remediation - no formatting in templates)
    display_rent_amount = ""
    display_late_penalty_amount = ""
    display_first_rent_due_date = ""
    display_first_rent_due_date_iso = ""
    display_current_period_start = ""
    display_current_period_end = ""
    display_next_due_date = ""

    if settings:
        display_rent_amount = f"${settings.rent_amount:.2f}"
        display_late_penalty_amount = f"${settings.late_penalty_amount:.2f}"
        if settings.first_rent_due_date:
            display_first_rent_due_date = settings.first_rent_due_date.strftime("%B %d, %Y")
            display_first_rent_due_date_iso = settings.first_rent_due_date.strftime("%Y-%m-%d")

    if current_period_start and current_period_end:
        display_current_period_start = current_period_start.strftime("%b %d, %Y")
        display_current_period_end = current_period_end.strftime("%b %d, %Y")

    if next_due_date:
        display_next_due_date = next_due_date.strftime("%B %d, %Y")

    return render_template('admin_rent_settings.html',
                          settings=settings,
                          obligation_summary=obligation_summary,
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
                          display_rent_amount=display_rent_amount,
                          display_late_penalty_amount=display_late_penalty_amount,
                          display_first_rent_due_date=display_first_rent_due_date,
                          display_first_rent_due_date_iso=display_first_rent_due_date_iso,
                          display_current_period_start=display_current_period_start,
                          display_current_period_end=display_current_period_end,
                          display_next_due_date=display_next_due_date,
                          current_period_start=current_period_start,
                          current_period_end=current_period_end,
                          next_due_date=next_due_date,
                          current_coverage_due_date=current_coverage_due_date,
                          upcoming_coverage_due_date=upcoming_coverage_due_date,
                          selected_feature_scope=selected_scope)


@admin_bp.route('/rent-waiver/add', methods=['POST'])
@admin_required
@feat_shell("FEAT-OBL-003")
def add_rent_waiver():
    """Add rent waiver for selected students (FEAT-OBL-003).

    Per DOM-OBL-001 §VI: WAIVED events close out outstanding remainder on RENT obligations.
    """
    from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_waiver
    from app.services import obligations_service

    context = g.canonical_context
    class_id = context.class_id
    if not class_id:
        abort(404)

    # Get seat IDs from request (format: student_ids multiple select)
    seat_ids_to_waive = []
    for seat_id_str in request.form.getlist('student_ids'):
        try:
            seat_ids_to_waive.append(int(seat_id_str))
        except ValueError:
            continue

    if not seat_ids_to_waive:
        flash("No students selected for waiver.", "warning")
        return redirect(url_for('admin.rent_settings'))

    # For each selected seat, find current rent assessment and waive it
    waived_count = 0
    failed_count = 0

    for seat_id in seat_ids_to_waive:
        try:
            # Find the most recent ASSESSMENT event for this seat (current rent obligation)
            assessment = (
                db.session.query(ObligationAssessment)
                .filter(
                    ObligationAssessment.seat_id == seat_id,
                    ObligationAssessment.class_id == class_id,
                    ObligationAssessment.obligation_type == 'RENT',
                    ObligationAssessment.event_type == 'ASSESSMENT',
                )
                .order_by(ObligationAssessment.created_at.desc())
                .first()
            )

            if not assessment:
                failed_count += 1
                continue

            # Check if already waived
            existing_waiver = (
                db.session.query(ObligationAssessment)
                .filter(
                    ObligationAssessment.correlation_id == assessment.correlation_id,
                    ObligationAssessment.event_type == 'WAIVED',
                )
                .first()
            )

            if existing_waiver:
                # Already waived, skip
                continue

            # Create WAIVED event via FEAT-OBL-003
            execute_satisfy_obligation_waiver(
                correlation_id=assessment.correlation_id,
                class_id=class_id,
                seat_id=seat_id,
            )
            waived_count += 1

        except ValueError as e:
            current_app.logger.warning(f"Failed to waive rent for seat {seat_id}: {e}")
            failed_count += 1

    db.session.commit()

    if waived_count > 0:
        flash(f"Waived rent for {waived_count} student(s).", "success")
    if failed_count > 0:
        flash(f"Failed to waive rent for {failed_count} student(s).", "warning")
    if waived_count == 0 and failed_count == 0:
        flash("No changes made.", "info")

    return redirect(url_for('admin.rent_settings'))


# -------------------- INSURANCE MANAGEMENT --------------------


def _get_teacher_user_tier_namespace_seed(user_id):
    """Return a stable seed for tenant-scoped tier IDs using a display alias if available."""
    class_row = (
        db.session.query(ClassEconomy.class_id)
        .filter_by(teacher_user_id=user_id)
        .order_by(ClassEconomy.class_id)
        .first()
    )
    if not class_row:
        return f"teacher-{user_id}"
    return get_display_join_code(class_row[0]) or f"teacher-{user_id}"


def _generate_tenant_scoped_tier_id(seed, sequence):
    """Create a globally unique tier ID by hashing the teacher user's join code with a sequence."""
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
    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before managing insurance.", "warning")
        return redirect(url_for('admin.dashboard'))
    selected_class_id = class_context['class_id']
    selected_join_code = class_context['join_code']
    selected_scope = resolve_feature_class_for_class(selected_class_id, 'insurance')
    if not selected_scope or not selected_scope.get('enabled'):
        abort(404)
    settings_block = class_context.get("block")
    active_class_label = selected_join_code
    policy_versions = [
        SimpleNamespace(
            id=version.id,
            version_number=version.version_number,
            is_active=version.is_active,
            payload=json.loads(version.policy_payload_json or "{}"),
        )
        for version in list_insurance_policy_versions(selected_class_id)
    ]
    return render_template(
        'admin_insurance.html',
        current_page='insurance',
        pending_claims_count=0,
        policies=policy_versions,
        student_policies=[],
        cancelled_policies=[],
        claims=[],
        current_class_context=SimpleNamespace(
            class_timezone=class_context.get('class_timezone', ''),
            block_display=class_context.get('block_display', ''),
            join_code=selected_join_code,
            teacher_name=class_context.get('teacher_name', ''),
        ),
        settings_block=settings_block,
        active_class_label=active_class_label,
        selected_scope=selected_scope,
    )


@admin_bp.route('/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def edit_insurance_policy(policy_id):
    """Edit existing insurance policy."""
    class_id = g.canonical_context.class_id
    version = get_insurance_policy_version(policy_id, class_id=class_id)
    if version is None:
        abort(404)
    payload = json.loads(version.policy_payload_json or "{}")
    store_items = (
        StoreItem.query.filter_by(class_id=class_id)
        .order_by(StoreItem.name.asc(), StoreItem.id.asc())
        .all()
    )
    if request.method == "POST":
        action = request.form.get("action", "save")
        title = (request.form.get("title") or payload.get("title") or "").strip()
        if not title:
            flash("Policy title is required.", "danger")
            return redirect(url_for("admin.edit_insurance_policy", policy_id=policy_id))
        entitlement_item_id = request.form.get("entitlement_item_id") or payload.get("entitlement_item_id")
        try:
            entitlement_item_id = int(entitlement_item_id) if entitlement_item_id not in (None, "") else None
        except (TypeError, ValueError):
            entitlement_item_id = None
        payload.update(
            {
                "title": title,
                "description": request.form.get("description", payload.get("description", "")),
                "premium": request.form.get("premium", payload.get("premium", "0.00")),
                "charge_frequency": request.form.get("charge_frequency", payload.get("charge_frequency", "monthly")),
                "autopay": request.form.get("autopay") == "on",
                "waiting_period_days": int(request.form.get("waiting_period_days") or payload.get("waiting_period_days", 0) or 0),
                "claim_time_limit_days": int(request.form.get("claim_time_limit_days") or payload.get("claim_time_limit_days", 0) or 0),
                "max_claims_count": int(request.form.get("max_claims_count") or payload.get("max_claims_count", 0) or 0),
                "max_claim_amount": request.form.get("max_claim_amount", payload.get("max_claim_amount")),
                "max_payout_per_period": request.form.get("max_payout_per_period", payload.get("max_payout_per_period")),
                "claim_type": request.form.get("claim_type", payload.get("claim_type", "transaction_monetary")),
                "tier_group": request.form.get("tier_group", payload.get("tier_group")),
                "tier_name": request.form.get("tier_name", payload.get("tier_name")),
                "tier_color": request.form.get("tier_color", payload.get("tier_color")),
                "tier_level": request.form.get("tier_level", payload.get("tier_level")),
                "bundle_with_policy_ids": [v.strip() for v in (request.form.get("bundle_with_policy_ids") or "").split(",") if v.strip()],
                "bundle_discount_percent": request.form.get("bundle_discount_percent", payload.get("bundle_discount_percent")),
                "bundle_discount_amount": request.form.get("bundle_discount_amount", payload.get("bundle_discount_amount")),
                "is_active": request.form.get("is_active") == "on",
                "entitlement_item_id": entitlement_item_id,
            }
        )
        version = create_policy_version(
            class_id=class_id,
            actor_user_id=g.canonical_context.user_id,
            payload=payload,
            source_version=version,
            is_active=payload["is_active"],
            activation_mode="edit" if action == "save" else action,
            status="applied" if action == "save" else "pending",
        )
        create_class_announcement(
            user_id=g.canonical_context.user_id,
            class_id=class_id,
            title=f"Insurance policy updated: {payload['title']}",
            message=(
                f"{payload['title']} changed. New terms are available for future enrollment."
                if action == "save"
                else f"{payload['title']} was {action}ed. Existing coverage remains valid until its current boundary."
            ),
            priority=7,
            is_active=True,
            expires_at=None,
        )
        db.session.commit()
        flash(f"Insurance policy '{payload['title']}' updated.", "success")
        return redirect(url_for("admin.insurance_management"))
    return render_template(
        "admin_edit_insurance_policy.html",
        policy=SimpleNamespace(id=version.id, title=payload.get("title", ""), payload=payload, version_number=version.version_number),
        policy_version=version,
        payload=payload,
        current_page="insurance",
        store_items=store_items,
        available_versions=[
            SimpleNamespace(
                id=v.id,
                version_number=v.version_number,
                is_active=v.is_active,
                policy_payload_json=v.policy_payload_json,
            )
            for v in list_insurance_policy_versions(class_id)
        ],
    )


@admin_bp.route('/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy."""
    class_id = g.canonical_context.class_id
    version = get_insurance_policy_version(policy_id, class_id=class_id)
    if version is None:
        abort(404)
    payload = json.loads(version.policy_payload_json or "{}")
    payload["is_active"] = False
    create_policy_version(
        class_id=class_id,
        actor_user_id=g.canonical_context.user_id,
        payload=payload,
        source_version=version,
        is_active=False,
        activation_mode="inactive",
        status="applied",
    )
    create_class_announcement(
        user_id=g.canonical_context.user_id,
        class_id=class_id,
        title=f"Insurance policy hidden: {payload.get('title', 'Policy')}",
        message=f"{payload.get('title', 'Policy')} is no longer available for new enrollment. Existing coverage is unchanged.",
        priority=6,
        is_active=True,
        expires_at=None,
    )
    db.session.commit()
    flash("Insurance policy deactivated.", "success")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/delete/<int:policy_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def delete_insurance_policy(policy_id):
    """Delete an insurance policy and all associated data.

    Since each teacher has their own policy instances (identified by policy_code),
    this safely deletes only the current teacher's policy data without affecting
    other teachers.
    """
    class_id = g.canonical_context.class_id
    version = get_insurance_policy_version(policy_id, class_id=class_id)
    if version is None:
        abort(404)
    scheduled_for = get_last_entitlement_end_for_policy_version(
        class_id=class_id,
        policy_version_id=version.id,
    ) or utc_now()
    schedule_policy_deletion(
        class_id=class_id,
        actor_user_id=g.canonical_context.user_id,
        source_version=version,
        deletion_at=scheduled_for,
    )
    create_class_announcement(
        user_id=g.canonical_context.user_id,
        class_id=class_id,
        title=f"Insurance policy scheduled for deletion: {json.loads(version.policy_payload_json or '{}').get('title', 'Policy')}",
        message="The policy has been discontinued for new enrollment and its configuration will be removed after the last current entitlement ends.",
        priority=8,
        is_active=True,
        expires_at=None,
    )
    db.session.commit()
    flash("Insurance policy deletion scheduled.", "success")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/mass-remove/<int:policy_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-SETTINGS-001")
def mass_remove_policy(policy_id):
    """Cancel insurance policy for multiple or all students."""
    flash("Insurance mass-removal is now expressed as policy deactivation/deletion scheduling in the class-config editor.", "info")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/student-policy/<int:enrollment_id>')
@admin_required
def view_student_policy(enrollment_id):
    """View student's policy enrollment details and claims history."""
    class_id = g.canonical_context.class_id
    student = SimpleNamespace(full_name="", public_id="")
    claims = list_insurance_claims(class_id=class_id)
    placeholder_policy = SimpleNamespace(
        id=enrollment_id,
        title="Insurance",
        description="",
        premium=Decimal("0.00"),
        charge_frequency="monthly",
        waiting_period_days=0,
        autopay=False,
        auto_cancel_nonpay_days=0,
        claim_type="transaction_monetary",
        no_repurchase_after_cancel=False,
        repurchase_wait_days=0,
    )
    enrollment = SimpleNamespace(
        id=enrollment_id,
        contract_title="Insurance",
        contract_description="",
        policy=placeholder_policy,
        status="active",
        purchase_date=utc_now(),
        coverage_start_date=None,
        payment_current=True,
        days_unpaid=0,
        next_payment_due=None,
        contract_claim_time_limit_days=0,
        contract_max_claim_amount=None,
        contract_max_claims_count=None,
        contract_max_claims_period="period",
    )
    def _claim_display_row(claim):
        raw_incident = (claim.claimed_dates or [None])[0] if getattr(claim, "claimed_dates", None) else None
        if isinstance(raw_incident, str):
            try:
                incident_dt = datetime.fromisoformat(raw_incident)
            except ValueError:
                incident_dt = claim.submitted_at
        elif raw_incident is not None:
            incident_dt = raw_incident
        else:
            incident_dt = claim.submitted_at
        return SimpleNamespace(
            id=claim.id,
            claim_id=claim.claim_id,
            policy=SimpleNamespace(title=getattr(getattr(claim.entitlement, "store_item", None), "name", "Insurance")),
            status=getattr(claim.status, "value", claim.status),
            approved_amount=getattr(claim, "approved_amount", None),
            claim_amount=getattr(claim, "claim_amount", None),
            rejection_reason=getattr(claim, "rejection_reason", None),
            description=getattr(claim, "description", ""),
            teacher_notes=getattr(claim, "teacher_notes", None),
            incident_date=incident_dt,
            filed_date=claim.submitted_at,
        )
    if claims:
        first_claim = claims[0]
        entitlement_item = getattr(getattr(first_claim, "entitlement", None), "store_item", None)
        if entitlement_item is not None:
            placeholder_policy.title = getattr(entitlement_item, "name", placeholder_policy.title)
            placeholder_policy.description = getattr(entitlement_item, "description", placeholder_policy.description)
    return render_template(
        'admin_view_student_policy.html',
        current_page='insurance',
        student=student,
        enrollment=enrollment,
        policy=placeholder_policy,
        claims=[_claim_display_row(claim) for claim in claims],
        seat=SimpleNamespace(public_id=""),
    )


@admin_bp.route('/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def process_claim(claim_id):
    """Process insurance claim with auto-deposit for monetary claims."""
    claim = get_insurance_claim(claim_id=str(claim_id))
    if claim is None:
        abort(404)
    form = AdminClaimProcessForm()
    if request.method == 'GET':
        form.status.data = getattr(claim.status, "value", claim.status)
    claims = list_insurance_claims(class_id=g.canonical_context.class_id)
    placeholder_policy = SimpleNamespace(
        title=getattr(getattr(claim.entitlement, "store_item", None), "title", "Insurance"),
        description=getattr(getattr(claim.entitlement, "store_item", None), "description", ""),
        premium=Decimal("0.00"),
        charge_frequency="monthly",
        waiting_period_days=0,
        autopay=False,
        auto_cancel_nonpay_days=0,
        claim_type="transaction_monetary",
        no_repurchase_after_cancel=False,
        repurchase_wait_days=0,
    )
    enrollment = SimpleNamespace(
        coverage_start_date=None,
        payment_current=True,
        days_unpaid=0,
    )
    claim_view = SimpleNamespace(
        id=claim.id,
        claim_id=claim.claim_id,
        student=SimpleNamespace(
            full_name=(
                (lambda profile: profile.full_name if profile else getattr(claim.target_seat, "public_id", ""))(
                    IdentityProfile.query.filter_by(seat_id=claim.target_seat_id).first()
                )
                if claim.target_seat_id else getattr(claim.target_seat, "public_id", "")
            )
        ),
        target_seat=claim.target_seat,
        transaction=getattr(claim, "referenced_transaction", None),
        submitted_at=claim.submitted_at,
        decided_at=claim.decided_at,
        claimed_dates=claim.claimed_dates or [],
        status=getattr(claim.status, "value", claim.status),
        entitlement=claim.entitlement,
        description="",
        comments="",
        rejection_reason="",
        teacher_notes="",
        incident_date=claim.submitted_at,
        filed_date=claim.submitted_at,
        claim_amount=None,
        claim_item=None,
    )
    if form.validate_on_submit():
        decision = (form.status.data or "").strip().lower()
        if decision == "approved":
            execute_claim_approval(
                claim_id=claim.claim_id,
                decided_by_seat_id=g.canonical_context.seat_id,
                ctx=g.canonical_context,
            )
            flash("Claim approved.", "success")
            return redirect(url_for("admin.insurance_management"))
        if decision == "rejected":
            execute_claim_rejection(
                claim_id=claim.claim_id,
                decided_by_seat_id=g.canonical_context.seat_id,
            )
            flash("Claim rejected.", "info")
            return redirect(url_for("admin.insurance_management"))
    return render_template(
        'admin_process_claim.html',
        current_page='insurance',
        claim=claim_view,
        claim_type='transaction_monetary',
        contract_title=placeholder_policy.title,
        contract_description=placeholder_policy.description,
        contract_claim_time_limit_days=0,
        contract_max_claim_amount=None,
        remaining_period_cap=None,
        contract_max_claims_count=None,
        contract_max_claims_period='period',
        contract_max_payout_per_period=None,
        validation_errors=[],
        claims_stats=SimpleNamespace(
            pending=sum(1 for c in claims if getattr(c.status, "value", c.status) == "SUBMITTED"),
            approved=sum(1 for c in claims if getattr(c.status, "value", c.status) == "APPROVED"),
            rejected=sum(1 for c in claims if getattr(c.status, "value", c.status) == "REJECTED"),
            paid=0,
        ),
        enrollment=enrollment,
        policy=placeholder_policy,
        form=form,
    )


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
        ctx = g.canonical_context
        if tx.class_id != ctx.class_id:
            raise access_policy_service.AccessPolicyDenied(reason_code="foreign_class_scope", message="You do not have permission to void this transaction.")

        execute_void_transaction(tx)
        current_app.logger.info(f"Transaction {transaction_id} voided")
    except (AccessScopeDenied, access_policy_service.AccessPolicyDenied) as e:
        db.session.rollback()
        current_app.logger.info("Transaction void denied for %s: %s", transaction_id, e)
        return _void_error("You do not have permission to void this transaction.", status_code=403)
    except ImmediatePurchaseNotVoidable:
        db.session.rollback()
        return _void_error("Immediate-use item purchases are not voidable.")
    except UsedDelayedPurchaseNotVoidable:
        db.session.rollback()
        return _void_error(
            "Delayed-use item has already been used and cannot be voided.",
        )
    except ValueError as e:
        db.session.rollback()
        current_app.logger.info("Transaction void validation failed for %s: %s", transaction_id, e)
        return _void_error("Transaction could not be voided.")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to void transaction {transaction_id}: {e}")
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
    ctx = g.canonical_context
    user_id = ctx.user_id
    feature_options = get_admin_feature_join_code_options('hall_pass', canonical_context=g.canonical_context)
    selected_scope = require_admin_feature_scope(
        'hall_pass',
        canonical_context=g.canonical_context,
        requested_block=None,
    )
    selected_join_code = selected_scope['join_code']
    selected_class_id = selected_scope.get('class_id')
    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
    )
    approved_logs = (
        HallPassLog.query
        .filter(HallPassLog.class_id == selected_class_id)
        .filter(HallPassLog.timestamp >= day_bounds.boundary_start_utc)
        .filter(HallPassLog.timestamp < day_bounds.boundary_end_utc)
        .order_by(HallPassLog.timestamp.asc(), HallPassLog.id.asc())
        .all()
    )
    requested_seat_ids = {log.requested_by_seat_id for log in approved_logs}
    latest_hall_pass_events = (
        AttendanceSession.query
        .filter(AttendanceSession.class_id == selected_class_id)
        .filter(AttendanceSession.target_seat_id.in_(requested_seat_ids))
        .filter(AttendanceSession.timestamp >= day_bounds.boundary_start_utc)
        .filter(AttendanceSession.timestamp < day_bounds.boundary_end_utc)
        .order_by(
            AttendanceSession.target_seat_id.asc(),
            AttendanceSession.timestamp.desc(),
            AttendanceSession.id.desc(),
        )
        .all()
        if requested_seat_ids
        else []
    )
    latest_event_by_seat_id = {}
    for event in latest_hall_pass_events:
        latest_event_by_seat_id.setdefault(event.target_seat_id, event)

    def _hall_pass_display_row(log):
        seat = getattr(log, "requested_by_seat", None)
        profile = seat.identity_profile if seat and seat.identity_profile else None
        section = seat.class_economy.section if seat and seat.class_economy else None
        return SimpleNamespace(
            id=log.id,
            student_name=profile.full_name if profile else "Unknown",
            reason=log.destination,
            request_time=log.timestamp,
            decision_time=log.timestamp,
            left_time=log.timestamp,
            period=section or "",
            latest_event=latest_event_by_seat_id.get(log.requested_by_seat_id),
        )

    pending_requests = []
    for pending_request in list_pending_hall_pass_requests_for_class(selected_class_id):
        seat = db.session.get(Seat, pending_request.requested_by_seat_id)
        if not seat or seat.class_id != selected_class_id:
            continue
        profile = seat.identity_profile if seat.identity_profile else None
        section = seat.class_economy.section if seat.class_economy else None
        pending_requests.append(SimpleNamespace(
            id=pending_request.request_id,
            student_name=profile.full_name if profile else "Unknown",
            reason=pending_request.destination,
            request_time=pending_request.requested_at_utc,
            period=section or "",
        ))

    issued_passes = []
    out_of_class = []
    for log in approved_logs:
        row = _hall_pass_display_row(log)
        latest_event = row.latest_event
        if (
            latest_event
            and latest_event.status == "inactive"
            and latest_event.reason_code == AttendanceReasonCode.HALL_PASS.value
        ):
            row.left_time = latest_event.timestamp
            out_of_class.append(row)
        else:
            issued_passes.append(row)

    # Get available sections from ClassEconomy
    class_row = get_class_economy(selected_class_id)
    periods = [class_row.section] if class_row and class_row.section else []

    # Lazily generate the hall pass verification token if needed
    canonical_teacher_user = db.session.get(User, g.canonical_context.user_id) if hasattr(g, 'canonical_context') else None

    verify_url = None
    if canonical_teacher_user and canonical_teacher_user.hall_pass_verify_token:
        verify_url = f"/verify/hallpass/{canonical_teacher_user.hall_pass_verify_token}"

    return render_template(
        'admin_hall_pass.html',
        pending_requests=pending_requests,
        issued_passes=issued_passes,
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
    ctx = g.canonical_context
    user_id = ctx.user_id
    selected_scope = require_admin_feature_scope(
        'hall_pass',
        canonical_context=g.canonical_context,
    )
    return render_template(
        'hall_pass_setup.html',
        current_join_code=selected_scope['join_code'],
        feature_options=get_admin_feature_join_code_options('hall_pass', canonical_context=g.canonical_context),
        selected_feature_scope=selected_scope,
    )


# -------------------- ECONOMY HEALTH --------------------

@admin_bp.route('/economy-policy', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def update_economy_policy():
    user_id = g.canonical_context.user_id
    current_class_id = g.canonical_context.class_id
    feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
    selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
    if not selected_scope:
        abort(404)
    policy_mode = normalize_policy_mode(request.form.get('policy_mode'))
    settings_row = get_feature_settings_row_for_class(
        selected_scope['class_id'],
        create=True,
    )
    if not settings_row:
        flash("Class scope not found for the selected period.", "warning")
        return redirect(url_for('admin.economy_health'))
    settings_row.economy_policy_mode = policy_mode
    settings_row.economy_policy_updated_at = utc_now()
    cancel_pending_policy_transitions(settings_row.class_id, actor_id=user_id)
    current_app.logger.info(
        "Economy policy mode changed teacher=%s block=%s mode=%s",
        user_id,
        selected_scope['block'],
        policy_mode,
    )
    flash(f"Economy policy updated to {POLICY_MODES[policy_mode]['label']}.", "success")
    return redirect(url_for('admin.economy_health', review_rebalance=1))


@admin_bp.route('/economy-policy/rebalance', methods=['POST'])
@admin_required
@feat_shell("FEAT-ADMN-001")
def apply_economy_rebalance():
    user_id = g.canonical_context.user_id
    current_class_id = g.canonical_context.class_id
    feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
    selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
    if not selected_scope:
        abort(404)
    activation_mode = (request.form.get('activation_mode') or REBALANCE_ACTIVATION_NEXT_RENEWAL).strip().lower()
    selected_keys = set(request.form.getlist('selected_changes'))
    settings_row = get_feature_settings_row_for_class(
        selected_scope['class_id'],
        create=True,
    )
    if not settings_row:
        flash("Class scope not found for the selected period.", "warning")
        return redirect(url_for('admin.economy_health', review_rebalance=1))
    allowed_activation_modes = {
        REBALANCE_ACTIVATION_IMMEDIATE,
        REBALANCE_ACTIVATION_NEXT_RENEWAL,
        REBALANCE_ACTIVATION_NEXT_PAYROLL,
    }

    if activation_mode not in allowed_activation_modes:
        flash("Invalid rebalance activation mode.", "warning")
        return redirect(url_for('admin.economy_health', review_rebalance=1))

    effective_block, payroll_settings, rent_settings, insurance_policies, _all_payroll_settings = _load_economy_rebalance_context(
        g.canonical_context,
        selected_scope['class_id'],
        selected_scope['block'],
    )

    if not payroll_settings:
        flash("Payroll settings are required before a rebalance can be applied.", "warning")
        return redirect(url_for('admin.economy_health', review_rebalance=1))

    checker = EconomyBalanceChecker(g.canonical_context.user_id, effective_block, class_id=getattr(payroll_settings, "class_id", None))
    effective_class_id = selected_scope.get("class_id")
    effective_class = get_class_economy(effective_class_id) if effective_class_id else None
    scoped_store_items = (
        StoreItem.query.filter_by(class_id=effective_class.class_id, is_active=True).all()
        if effective_class else []
    )
    analysis = checker.analyze_economy(
        payroll_settings=payroll_settings,
        rent_settings=rent_settings,
        insurance_policies=insurance_policies,
        fines=[],
        store_items=scoped_store_items,
        expected_weekly_hours=payroll_settings.expected_weekly_hours if payroll_settings.expected_weekly_hours is not None else 5.0,
    )
    preview_items = _build_rebalance_preview(
        g.canonical_context,
        effective_block,
        selected_scope.get("class_id"),
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
        return redirect(url_for('admin.economy_health', review_rebalance=1))

    if activation_mode == REBALANCE_ACTIVATION_IMMEDIATE and request.form.get('confirm_immediate') != 'yes':
        flash("Confirm the immediate change warning before applying now.", "warning")
        return redirect(url_for('admin.economy_health', review_rebalance=1))

    if activation_mode == REBALANCE_ACTIVATION_IMMEDIATE:
        applied_labels = _apply_rebalance_plan(
            g.canonical_context,
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
            g.canonical_context.user_id,
            settings_row,
            scheduled_changes,
            activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL,
        )
        current_app.logger.info(
            "Scheduled economy rebalance teacher=%s block=%s changes=%s",
            g.canonical_context.user_id,
            effective_block,
            [change.get('type') for change in change_plan],
        )
        flash(
            f"Scheduled economy rebalance for the renewal after the upcoming bill ({len(change_plan)} setting(s), {queued_transition_count} policy transition(s)).",
            "success",
        )

    return redirect(url_for('admin.economy_health'))


@admin_bp.route('/economy-health')
@admin_required
def economy_health():
    """Show a holistic view of the current economy configuration and CWI health."""
    user_id = g.canonical_context.user_id
    current_class_id = g.canonical_context.class_id
    feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
    selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
    if not selected_scope:
        abort(404)

    blocks = _get_teacher_blocks(g.canonical_context)
    # Always use per-class view since CWI is inherently class-scoped.
    selected_block = selected_scope['block']

    selected_block, payroll_settings, rent_settings, insurance_policies, all_payroll_settings = _load_economy_rebalance_context(
        g.canonical_context,
        selected_scope['class_id'],
        selected_block,
    )
    has_payroll_settings = len(all_payroll_settings) > 0

    selected_class_id = selected_scope['class_id']
    fines = []
    store_items = (
        StoreItem.query.filter_by(class_id=selected_class_id, is_active=True).all()
        if selected_class_id else []
    )

    banking_settings = _resolve_banking_settings_for_class_id(selected_class_id) if selected_class_id else None

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
        checker = EconomyBalanceChecker(user_id, selected_block, class_id=getattr(payroll_settings, "class_id", None))
        payload, snapshot = _get_frozen_economy_analysis_payload(
            user_id,
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
            user_id,
            selected_block,
            policy_mode=policy_summary['mode'],
            class_id=getattr(payroll_settings, "class_id", None),
        )
        rebalance_preview = _build_rebalance_preview(
            g.canonical_context,
            selected_block,
            checker,
            cwi_calc.cwi,
            rent_settings,
            insurance_policies,
        )

    feature_links = {
        'rent': url_for('admin.rent_settings', settings_block=selected_block),
        'insurance': url_for('admin.insurance_management', settings_block=selected_block),
        'fine': url_for('admin.payroll'),
        'store': url_for('admin.store_management'),
        'budget survival test': url_for('admin.payroll'),
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
        payroll_link=url_for('admin.payroll'),
        banking_link=url_for('admin.banking'),
        rent_link=url_for('admin.rent_settings', settings_block=selected_block),
        insurance_link=url_for('admin.insurance_management', settings_block=selected_block),
        store_link=url_for('admin.store_management'),
    )


def _build_payroll_event_display_rows(*, ctx, payroll_events, class_label=None):
    """Build template-safe rows from PROD payroll events plus Ledger amounts."""
    if not payroll_events:
        return []

    target_seat_ids = {event.target_seat_id for event in payroll_events}
    class_row = get_class_economy(ctx.class_id)
    resolved_class_label = class_label or (
        class_row.display_name
        if class_row and class_row.display_name
        else (class_row.join_code if class_row else ctx.class_id)
    )
    seat_lookup = {
        seat.id: seat
        for seat in Seat.query.filter(
            Seat.class_id == ctx.class_id,
            Seat.id.in_(target_seat_ids),
        ).all()
    } if target_seat_ids else {}
    ledger_rows = (
        Transaction.query.filter(
            Transaction.class_id == ctx.class_id,
            Transaction.correlation_id.in_({event.correlation_id for event in payroll_events}),
            Transaction.target_seat_id.in_(target_seat_ids),
        )
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
        .all()
        if payroll_events and target_seat_ids
        else []
    )
    ledger_by_event_key = defaultdict(list)
    for tx in ledger_rows:
        ledger_by_event_key[(tx.correlation_id, tx.target_seat_id)].append(tx)

    def _ledger_amount_for_event(event):
        linked = ledger_by_event_key.get((event.correlation_id, event.target_seat_id), [])
        if event.payroll_event_type == "reversal":
            reversal_tx = next((tx for tx in linked if Decimal(tx.amount or 0) < 0), None)
            return Decimal(reversal_tx.amount) if reversal_tx else Decimal("0.00")
        credit_tx = next((tx for tx in linked if Decimal(tx.amount or 0) > 0), None)
        return Decimal(credit_tx.amount) if credit_tx else Decimal("0.00")

    payroll_records = []
    for event in payroll_events:
        seat = seat_lookup.get(event.target_seat_id)
        summary = event.summary_json or {}
        ledger_amount = _ledger_amount_for_event(event)
        payroll_records.append({
            'id': event.id,
            'payroll_event_id': event.id,
            'transaction_id': None,
            'timestamp': event.recorded_at,
            'type': event.payroll_event_type,
            'block': getattr(class_row, "section", None) or "",
            'class_label': resolved_class_label,
            'class_id': ctx.class_id,
            'actor_public_id': seat.public_id if seat else None,
            'student_name': (seat.identity_profile.full_name if seat and seat.identity_profile else 'Unknown'),
            'student': None,
            'amount': ledger_amount,
            'display_amount': f"${ledger_amount:.2f}",
            'account_type': "checking",
            'notes': summary.get("description") or event.payroll_event_type,
            'is_reversal': event.payroll_event_type == "reversal",
            'can_reverse': False,
        })
    return payroll_records


@admin_bp.route('/payroll-history')
@admin_required
def payroll_history():
    """View payroll history with filtering."""
    current_app.logger.info("Entered admin_payroll_history route")
    ctx = g.canonical_context

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    query = PayrollEvent.query.filter(PayrollEvent.class_id == ctx.class_id)

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        start_bounds = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="evaluation_day_boundaries",
            evaluation_date=start_date,
        )
        query = query.filter(PayrollEvent.recorded_at >= start_bounds.boundary_start_utc)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        end_bounds = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="evaluation_day_boundaries",
            evaluation_date=end_date,
        )
        query = query.filter(PayrollEvent.recorded_at < end_bounds.boundary_end_utc)

    payroll_events = query.order_by(desc(PayrollEvent.recorded_at), desc(PayrollEvent.id)).all()
    current_app.logger.info(f"Payroll events found: {len(payroll_events)}")
    payroll_records = _build_payroll_event_display_rows(ctx=ctx, payroll_events=payroll_events)

    current_app.logger.info(f"Payroll records prepared: {len(payroll_records)}")

    return render_template(
        'admin_payroll_history.html',
        payroll_history=payroll_records,
        current_page="payroll_history",
        selected_class_id=ctx.class_id,
    )


@admin_bp.route('/run_payroll', methods=['POST'])
@admin_required
def run_payroll(*args, **kwargs):
    """Run attendance-based payroll through the PROD payroll event FEAT."""
    return _run_payroll(*args, **kwargs)

def _run_payroll():
    """
    Run payroll by recording one boundary-bearing payroll event per student seat.

    FEAT-PROD-003 derives the payable amount from authoritative productivity
    facts and coordinates the matching Ledger credit.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        # Get the current canonical teacher for proper transaction scoping
        user_id = g.canonical_context.user_id

        if not user_id:
            error_msg = "No canonical user in session"
            current_app.logger.error(f"Payroll error: {error_msg}")
            if is_json:
                return jsonify(status="error", message=error_msg), 401
            flash(error_msg, "admin_error")
            return redirect(url_for('admin.dashboard'))

        selected_scope = _require_payroll_feature_scope_from_request()

        class_id = selected_scope['class_id']
        policy_version_id = _require_active_payroll_policy_version_id(class_id)
        seats = Seat.query.filter_by(class_id=class_id, role='student').all()

        evaluation = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=g.canonical_context,
            primitive="current_time",
        )
        run_anchor_utc = evaluation.canonical_now_utc

        processed_count = 0
        paid_count = 0
        request_nonce = secrets.token_hex(12)
        for seat in seats:
            result = record_payroll_event(
                ctx=g.canonical_context,
                target_seat_id=seat.id,
                payroll_event_type="payroll",
                correlation_id=generate_correlation_id(),
                idempotency_key=f"payroll_run:{class_id}:{seat.id}:{request_nonce}",
                policy_version_id=policy_version_id,
                mechanism="TEACHER",
                summary_json={
                    "source": "admin_run_payroll",
                    "description": "Payroll based on attendance",
                },
                reference_time_utc=run_anchor_utc,
            )
            processed_count += 1
            if result.ledger_transaction is not None:
                paid_count += 1

        current_app.logger.info(
            "Payroll complete. Recorded %s payroll events and %s ledger payments.",
            processed_count,
            paid_count,
        )

        success_message = f"Payroll complete. Recorded {processed_count} payroll events and {paid_count} payments."
        if is_json:
            return jsonify(status="success", message=success_message), 200

        flash(success_message, "admin_success")
        return redirect(url_for('admin.payroll'))
    except (SQLAlchemyError, Exception) as e:
        db.session.rollback()
        is_db_error = isinstance(e, SQLAlchemyError)
        error_type = "database" if is_db_error else "unexpected"
        current_app.logger.error(f"Payroll {error_type} error: {e}")

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
    import pytz as _pytz
    current_time = now_utc.astimezone(_pytz.UTC)

    ctx = g.canonical_context
    now_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    now_utc = now_eval.canonical_now_utc
    current_time = now_eval.canonical_now
    user_id = ctx.user_id
    current_class_id = ctx.class_id
    feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
    selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
    if not selected_scope:
        abort(404)
    selected_join_code = selected_scope['join_code']
    selected_block = selected_scope['block']
    selected_class_id = selected_scope['class_id']
    class_row = get_class_economy(selected_class_id)
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
            if ((seat.class_economy.section if seat and seat.class_economy else '').strip().upper() == selected_block_upper)
        ]
    students = seats
    payroll_class_options = [{
        "class_id": selected_class_id,
        "label": class_label,
        "settings_key": selected_block,
    }]
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
    my_class_ids = [selected_class_id] if selected_class_id else []
    class_ids_by_block = {selected_block: selected_class_id} if selected_block else {}
    payroll_preview = _build_payroll_preview_state(students, class_ids_by_block)
    payroll_summary = payroll_preview["total_summary"]
    payroll_updated_at = payroll_preview["latest_updated_at"]
    payroll_anchor_by_class_id = payroll_preview["anchor_by_class_id"]
    payroll_summary_by_class_id = payroll_preview["summary_by_class_id"]

    recent_payroll_events = (
        PayrollEvent.query
        .filter(PayrollEvent.class_id == selected_class_id)
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .limit(20)
        .all()
    )
    recent_payrolls = _build_payroll_event_display_rows(
        ctx=ctx,
        payroll_events=recent_payroll_events,
        class_label=class_label,
    )

    total_payroll_estimate = sum(payroll_summary.values())

    class_labels_by_block = {selected_block: class_label} if selected_block else {}

    # Next payroll by canonical class scope.
    next_payroll_by_block = []
    for class_option in payroll_class_options:
        class_id = class_option["class_id"]
        block_students = [s for s in students if s.class_id == class_id]
        block_estimate = sum(
            payroll_summary_by_class_id.get(class_id, {}).get(s.id, Decimal("0.00"))
            for s in block_students
        ) if class_id else Decimal("0.00")
        setting = settings_by_block.get(class_option["settings_key"], default_setting)
        block_next_payroll = _compute_next_pay_date(setting, now_utc)
        next_payroll_by_block.append({
            'class_id': class_id,
            'class_label': class_option["label"],
            'next_date': block_next_payroll,  # Keep in UTC
            'next_date_iso': format_utc_iso(block_next_payroll),
            'estimate': block_estimate,
            'display_estimate': f"${block_estimate:.2f}",
        })

    # Student statistics
    student_stats = []

    # Pre-fetch payroll earnings and last payroll dates from PROD payroll events.
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)
    seat_map = {(seat.id, seat.class_id): seat for seat in seats}

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
    payroll_events_for_stats = (
        PayrollEvent.query
        .filter(PayrollEvent.class_id == selected_class_id)
        .filter(PayrollEvent.target_seat_id.in_(seat_ids))
        .all()
        if seat_ids else []
    )
    payroll_stat_rows = _build_payroll_event_display_rows(
        ctx=ctx,
        payroll_events=payroll_events_for_stats,
        class_label=class_label,
    )
    payroll_event_by_id = {event.id: event for event in payroll_events_for_stats}
    last_payroll_map = {}
    earnings_map = defaultdict(lambda: Decimal("0.00"))
    for row in payroll_stat_rows:
        event = payroll_event_by_id.get(row["payroll_event_id"])
        seat = seat_map.get((event.target_seat_id, selected_class_id)) if event else None
        if seat is None:
            continue
        if row["type"] == "payroll":
            previous = last_payroll_map.get(seat.id)
            if previous is None or row["timestamp"] > previous:
                last_payroll_map[seat.id] = row["timestamp"]
        earnings_map[seat.id] += Decimal(row["amount"] or 0)

    events_map_by_class_id = {}
    seat_ids_by_class_id = defaultdict(set)
    seat_id_by_user_class = {}
    for seat_row in seats:
        if seat_row.class_id not in my_class_ids:
            continue
        seat_ids_by_class_id[seat_row.class_id].add(seat_row.id)
        seat_id_by_user_class.setdefault(
            (seat_row.user_id, seat_row.class_id),
            seat_row.id,
        )

    for class_id in my_class_ids:
        anchor = payroll_anchor_by_class_id.get(class_id)
        if not class_id:
            events_map_by_class_id[class_id] = {}
            continue
        scoped_seat_ids = sorted(seat_ids_by_class_id.get(class_id, set()))
        events_map_by_class_id[class_id] = get_batch_attendance_events(
            scoped_seat_ids,
            anchor,
            allowed_class_ids=[class_id],
        )

    for student in students:
        # Calculate unpaid minutes in the canonical class scope.
        unpaid_seconds = 0
        class_id = student.class_id
        seat_id = seat_id_by_user_class.get((student.user_id, class_id))
        if seat_id:
            key = (seat_id, class_id)
            events = events_map_by_class_id.get(class_id, {}).get(key, [])
            if events:
                unpaid_seconds = calculate_seconds_in_memory(
                    events,
                    payroll_anchor_by_class_id.get(class_id),
                )

        unpaid_minutes = unpaid_seconds / 60.0
        estimated_payout = payroll_summary.get(student.id, 0)

        student_stats.append({
            'id': student.id,
            'student_id': student.id,
            'public_id': student.public_id,
            'full_name': (student.identity_profile.full_name if student.identity_profile else str(student.id)),
            'student_name': (student.identity_profile.full_name if student.identity_profile else str(student.id)),
            'class_id': student.class_id,
            'class_label': class_label,
            'unpaid_minutes': int(unpaid_minutes),
            'estimated_payout': estimated_payout,
            'last_payroll_date': last_payroll_map.get(student.id),
            'total_earned': earnings_map.get(student.id, Decimal('0.00'))
        })

    # Initialize forms
    settings_form = PayrollSettingsForm()
    settings_form.block.choices = (
        [(selected_block, class_labels_by_block.get(selected_block, selected_block))]
        if selected_block else []
    )

    manual_payment_form = ManualPaymentForm()
    # Quick stats
    avg_payout = total_payroll_estimate / len(students) if students else 0
    display_total_payroll_estimate = f"${Decimal(str(total_payroll_estimate)):.2f}"
    display_avg_payout = f"${Decimal(str(avg_payout)):.2f}"

    # Phase 1: Build payroll view models (eliminates template-level numeric formatting)
    from app.services.payroll.builders import (
        build_student_payroll_status_view,
        build_payroll_configuration_view,
        build_payroll_settings_display,
    )

    # Pre-format pay rate display strings for the Settings tab (eliminates
    # template-level "%.2f"|format() calls on raw PayrollSettings.pay_rate)
    default_setting_display = build_payroll_settings_display(default_setting)
    display_pay_rate_by_block = {
        block_key: build_payroll_settings_display(setting)['display_pay_rate']
        for block_key, setting in settings_by_block.items()
    }

    # Convert student_stats to StudentPayrollStatusView objects
    student_payroll_views = []
    for stat in student_stats:
        # Get balances from scoped_balances_by_student dict
        balances = scoped_balances_by_student.get(stat['id'], {})
        checking_bal = Decimal(str(balances.get('checking', 0)))
        savings_bal = Decimal(str(balances.get('savings', 0)))

        view = build_student_payroll_status_view(
            seat_id=stat['id'],
            class_id=stat['class_id'],
            student_name=stat['student_name'],
            earnings_this_period=stat.get('estimated_payout', Decimal('0.00')),
            taxes_this_period=Decimal('0.00'),  # Taxes not yet calculated in payroll system
            total_earnings_all_time=stat.get('total_earned', Decimal('0.00')),
            total_taxes_all_time=Decimal('0.00'),  # Taxes not yet calculated
            # Student identification fields for Manual Payment tab display
            public_id=stat['public_id'],
            full_name=stat['full_name'],
            class_label=stat['class_label'],
            # Account balances (pre-formatted to eliminate template filters)
            checking_balance=checking_bal,
            savings_balance=savings_bal,
        )
        student_payroll_views.append(view)

    # Build payroll configuration view (eliminates payroll settings display logic)
    payroll_config = build_payroll_configuration_view(
        class_id=selected_class_id,
        settings=default_setting,
        student_statuses=student_payroll_views,
    )

    # Payroll history for History tab: PROD payroll business events only.
    payroll_history_events = (
        PayrollEvent.query
        .filter(PayrollEvent.class_id == selected_class_id)
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .limit(100)
        .all()
    )
    payroll_history = _build_payroll_event_display_rows(
        ctx=ctx,
        payroll_events=payroll_history_events,
        class_label=class_label,
    )
    join_codes_by_class_id = {selected_class_id: selected_join_code}

    # CWI Configuration - Get selected block from query param
    cwi_block = selected_block
    cwi_setting = None
    if cwi_block:
        # Get the payroll setting for this specific block
        cwi_setting = PayrollSettings.query.filter_by(
            class_id=selected_scope['class_id'],
            block=cwi_block
        ).first()

    # Build class scope to label map for payroll display
    # This is needed because transactions are displayed per class scope
    join_code_to_label = {selected_join_code: class_label}

    # Pre-format display values (Phase 1 Jinja2 remediation - no formatting in templates)
    display_payroll_updated_at = ""
    if payroll_updated_at:
        display_payroll_updated_at = payroll_updated_at.strftime("%H:%M")

    # Format first_pay_date for both display and input
    display_first_pay_date = ""
    display_first_pay_date_iso = ""
    if default_setting and default_setting.first_pay_date:
        display_first_pay_date = default_setting.first_pay_date.strftime("%m/%d/%Y")
        display_first_pay_date_iso = default_setting.first_pay_date.strftime("%Y-%m-%d")

    # Format created_at for each block setting
    display_settings_created_at_list = []
    for setting in block_settings:
        if setting.created_at:
            display_settings_created_at_list.append(setting.created_at.strftime("%B %d, %Y"))
        else:
            display_settings_created_at_list.append("")

    return render_template(
        'admin_payroll.html',
        # Overview tab
        recent_payrolls=recent_payrolls,
        join_code_to_label=join_code_to_label, # Pass lookup map
        join_codes_by_class_id=join_codes_by_class_id,
        next_payroll_date=next_pay_date_utc,  # Pass UTC timestamp
        next_payroll_by_block=next_payroll_by_block,
        total_payroll_estimate=total_payroll_estimate,
        display_total_payroll_estimate=display_total_payroll_estimate,
        payroll_updated_at=payroll_updated_at,
        display_payroll_updated_at=display_payroll_updated_at,
        total_students=len(students),
        avg_payout=avg_payout,
        display_avg_payout=display_avg_payout,
        total_classes=len(payroll_class_options),
        # Settings tab
        settings_form=settings_form,
        block_settings=block_settings,
        default_setting=default_setting,
        default_setting_display=default_setting_display,
        display_first_pay_date=display_first_pay_date,
        display_first_pay_date_iso=display_first_pay_date_iso,
        display_settings_created_at_list=display_settings_created_at_list,
        settings_by_block=settings_by_block,
        display_pay_rate_by_block=display_pay_rate_by_block,
        next_global_payroll=next_pay_date_utc,  # Pass UTC timestamp
        show_setup_banner=show_setup_banner,
        # Students tab (using pre-formatted view models per Phase 1)
        student_stats=student_payroll_views,
        scoped_balances_by_student=scoped_balances_by_student,
        payroll_config=payroll_config,
        # Manual Payment tab
        manual_payment_form=manual_payment_form,
        all_students=student_payroll_views,
        # History tab
        payroll_history=payroll_history,
        # CWI Configuration
        cwi_block=cwi_block,
        cwi_setting=cwi_setting,
        # General
        payroll_class_options=payroll_class_options,
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
        ctx = g.canonical_context
        user_id = ctx.user_id
        feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
        enabled_blocks = [option['block'] for option in feature_options if option.get('block')]
        enabled_block_set = set(enabled_blocks)
        class_id_by_block = {
            option['block']: option['class_id']
            for option in feature_options
            if option.get('block') and option.get('class_id')
        }
        current_class_id = ctx.class_id
        selected_scope = next((option for option in feature_options if option.get('class_id') == current_class_id), None)
        if not selected_scope:
            abort(404)

        # Derive assignable blocks from canonical feature scopes, not student.block text.
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
        # NO global settings - always scoped by block and resolved class context.
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
            upsert_payroll_settings_for_blocks(
                class_id_by_block=class_id_by_block,
                target_blocks=target_blocks,
                settings_data=settings_data,
            )

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
    try:
        from app.models import _quantize_currency
        ctx = g.canonical_context
        feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
        selected_scope = next((option for option in feature_options if option.get('class_id') == ctx.class_id), None)
        if not selected_scope:
            abort(404)
        expected_weekly_hours = _quantize_currency(request.form.get('expected_weekly_hours', '5.0'))
        cwi_block = selected_scope['block']
        apply_to_all = request.form.get('apply_to_all', 'false').lower() == 'true'
        ctx = g.canonical_context
        user_id = ctx.user_id
        feature_options = get_admin_feature_join_code_options('payroll', canonical_context=g.canonical_context)
        enabled_blocks = {option['block'] for option in feature_options if option.get('block')}
        class_id_by_block = {
            option['block']: option['class_id']
            for option in feature_options
            if option.get('block') and option.get('class_id')
        }

        # Validate expected_weekly_hours is within a reasonable range (0.25 to 80)
        if not (0.25 <= expected_weekly_hours <= 80):
            flash('Expected weekly hours must be between 0.25 and 80.', 'error')
            return redirect(url_for('admin.payroll'))

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
                    update_expected_weekly_hours_for_blocks(
                        class_id_by_block=class_id_by_block,
                        target_blocks=[cwi_block],
                        expected_weekly_hours=expected_weekly_hours,
                        default_pay_rate=Decimal('0.25'),
                        payroll_frequency_days=14,
                        settings_mode='simple',
                    )
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
                    update_expected_weekly_hours_for_blocks(
                        class_id_by_block=class_id_by_block,
                        target_blocks=[cwi_block],
                        expected_weekly_hours=expected_weekly_hours,
                        default_pay_rate=Decimal('0.25'),
                        payroll_frequency_days=14,
                        settings_mode='simple',
                    )
                    flash_message = f'Expected weekly hours set to {expected_weekly_hours} hours/week for {cwi_block}.'

        flash(flash_message, 'success')

    except ValueError:
        flash('Invalid expected weekly hours value', 'error')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating expected weekly hours: {e}")
        flash(f'Error updating expected weekly hours', 'error')

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
            f"feat:led:payroll-void:{selected_scope['class_id']}:{transaction.id}"
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

        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "class_id": selected_scope["class_id"],
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
    """Record manual PROD credits for selected students."""
    form = ManualPaymentForm()

    if form.validate_on_submit():
        try:
            student_ids = request.form.getlist('student_ids')
            save_action = request.form.get('save_action', 'apply_only') # apply_only, save_and_apply, save_only
            payment_type = request.form.get('payment_type', 'deposit')

            description = form.description.data
            amount = Decimal(str(form.amount.data))

            if save_action in ['apply_only', 'save_and_apply'] and not student_ids:
                flash('Please select at least one student to apply the payment.', 'warning')
                return redirect(url_for('admin.payroll'))

            if payment_type != 'deposit':
                flash('Manual deductions belong to Obligations and are no longer handled by Payroll.', 'error')
                return redirect(url_for('admin.payroll'))

            if amount <= Decimal("0"):
                flash('Manual credits must use a positive amount.', 'error')
                return redirect(url_for('admin.payroll'))

            selected_scope = _require_payroll_feature_scope_from_request()
            selected_class_id = selected_scope['class_id']
            policy_version_id = _require_active_payroll_policy_version_id(selected_class_id)

            # Save Template Logic
            if save_action in ['save_only', 'save_and_apply']:
                pass
                if save_action == 'save_only':
                    flash(f'Template "{description}" saved successfully!', 'success')
                    return redirect(url_for('admin.payroll'))

            applied_count = 0
            request_nonce = secrets.token_hex(12)
            for actor_public_id in student_ids:
                student = _resolve_student_detail_seat(str(actor_public_id))
                if student is None or student.class_id != selected_class_id:
                    continue

                record_payroll_event(
                    ctx=g.canonical_context,
                    target_seat_id=student.id,
                    payroll_event_type="manual_credit",
                    correlation_id=generate_correlation_id(),
                    idempotency_key=f"manual_credit:{selected_class_id}:{student.id}:{request_nonce}",
                    policy_version_id=policy_version_id,
                    mechanism="TEACHER",
                    summary_json={
                        "description": f"Manual Credit: {description}",
                        "source": "admin_payroll_manual_credit",
                    },
                    amount=amount,
                )
                applied_count += 1

            message = f'Manual credit of ${amount:.2f} applied to {applied_count} student(s)!'
            if save_action == 'save_and_apply':
                message = f'Template saved and manual credit applied to {applied_count} student(s)!'

            flash(message, 'success')

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
    # Attendance history is now seat-scoped; derive periods from canonical session rows.
    periods = _get_teacher_blocks(g.canonical_context)

    # Get distinct blocks from Students for this admin's students
    blocks = _get_teacher_blocks(g.canonical_context)

    # Build class_labels_by_block dictionary
    user_id = g.canonical_context.user_id
    class_labels_by_block = _get_class_labels_for_blocks(g.canonical_context, blocks)

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

    force_new_class = request.form.get("force_new_class") == "1"
    roster_sync = request.form.get("roster_sync") == "1"
    confirm_roster_delete = request.form.get("confirm_roster_delete") == "1"

    # Read file content and remove BOM if present
    content = file.stream.read().decode("UTF-8-sig")  # UTF-8-sig removes BOM
    user_id = g.canonical_context.user_id
    idempotency_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    idempotency_key = f"feat:iden:upload-students:{user_id}:{idempotency_hash}"

    with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
        def _insert_identity_profile(*, seat_id: int, class_id: str | None, profile_type: str, first_name, last_name, notes):
            db.session.execute(
                sa.text(
                    "INSERT INTO identity_profiles "
                    "(seat_id, class_id, profile_type, first_name, last_name, notes, created_at, updated_at) "
                    "VALUES (:seat_id, :class_id, :profile_type, :first_name, :last_name, :notes, :created_at, :updated_at)"
                ),
                {
                    "seat_id": seat_id,
                    "class_id": class_id,
                    "profile_type": profile_type,
                    "first_name": first_name,
                    "last_name": last_name,
                    "notes": notes,
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                },
            )

        if force_new_class and not roster_sync:
            from app.models import Seat, IdentityProfile
            from app.utils.join_code import generate_join_code
            from app.hash_utils import hash_username_lookup

            def _row_value(row, *keys):
                for key in keys:
                    value = row.get(key)
                    if value is not None and str(value).strip():
                        return _sanitize_roster_text(value)
                return ""

            stream = io.StringIO(content, newline=None)
            csv_input = csv.DictReader(stream)
            rows = []
            class_sections = set()
            class_names = set()
            for row in csv_input:
                first_name = _row_value(row, "first_name", "First Name")
                last_name = _row_value(row, "last_name", "Last Name")
                notes = _row_value(row, "notes", "Notes", "Additional Notes")
                class_section = _row_value(row, "class_section", "Class Section", "Class Section Name", "Section")
                class_name = _row_value(row, "class_name", "Class Name", "Class Names", "ClassName", "Class")
                if class_section:
                    class_sections.add(class_section.strip().upper())
                if class_name:
                    class_names.add(class_name.strip().lower())
                if first_name or last_name or notes:
                    rows.append({
                        "first_name": first_name,
                        "last_name": last_name,
                        "notes": notes or None,
                        "class_section": class_section or None,
                        "class_name": class_name or None,
                    })

            if not rows:
                flash("Template is empty. Add at least one student row before creating the class.", "error")
                return redirect(url_for("admin.onboarding"))
            if len(class_sections) > 1 or len(class_names) > 1:
                flash("You can only create one class at a time", "error")
                return redirect(url_for("admin.onboarding"))

            join_code = generate_join_code()

            class_name = next((row.get("class_name") for row in rows if row.get("class_name")), None)
            if not class_name:
                class_name = next((row.get("class_section") for row in rows if row.get("class_section")), None)
            class_name = (class_name or "").strip() or "New Class"
            class_row = create_class_with_roster(
                user_id=user_id,
                join_code=join_code,
                class_name=class_name,
                rows=rows,
            )

            establish_teacher_session(db.session.get(User, user_id))
            flash("Class created and roster uploaded. You are now switched into the new class.", "admin_success")
            return redirect(url_for("admin.dashboard"))

        if roster_sync:
            from app.models import Seat, IdentityProfile
            class_id = (getattr(getattr(g, "canonical_context", None), "class_id", None) or "").strip()
            if not class_id:
                flash("Select a class before syncing roster data.", "error")
                return redirect(url_for("admin.students"))

            class_row = verify_teacher_owns_class(class_id, user_id)
            if not class_row:
                flash("Select a class before syncing roster data.", "error")
                return redirect(url_for("admin.students"))

            stream = io.StringIO(content, newline=None)
            csv_input = csv.DictReader(stream)
            rows = []
            file_join_codes = set()
            for row in csv_input:
                row_join_code = _sanitize_roster_text(row.get("join_code") or row.get("Join Code") or "")
                actor_public_id = _sanitize_roster_text(row.get("actor_public_id") or row.get("Actor Public ID") or "")
                first_name = _sanitize_roster_text(row.get("first_name") or row.get("First Name") or "")
                last_name = _sanitize_roster_text(row.get("last_name") or row.get("Last Name") or "")
                notes = _sanitize_roster_text(row.get("notes") or row.get("Notes") or "")
                # Balance columns are accepted for recordkeeping but never used for writes.
                _ = row.get("checking_balance") or row.get("Checking Balance")
                _ = row.get("savings_balance") or row.get("Savings Balance")
                if row_join_code:
                    file_join_codes.add(row_join_code)
                if actor_public_id:
                    rows.append({
                        "join_code": row_join_code or None,
                        "actor_public_id": actor_public_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "notes": notes or None,
                    })
                elif first_name or last_name or notes:
                    rows.append({
                        "join_code": row_join_code or None,
                        "actor_public_id": None,
                        "first_name": first_name,
                        "last_name": last_name,
                        "notes": notes or None,
                    })

            if not file_join_codes:
                flash("Roster file is missing join_code. Re-export the roster from the current class.", "error")
                return redirect(url_for("admin.students"))
            if len(file_join_codes) != 1:
                flash("Roster file must contain exactly one join_code for one class.", "error")
                return redirect(url_for("admin.students"))
            file_join_code = next(iter(file_join_codes))
            resolved_file_class_id = (
                db.session.query(ClassEconomy.class_id)
                .filter(ClassEconomy.class_id == class_id)
                .scalar()
            )
            if not resolved_file_class_id or resolved_file_class_id != class_id:
                flash("Roster file does not match the currently selected class. Switch class context and export again.", "error")
                return redirect(url_for("admin.students"))

            existing_seats = (
                Seat.query
                .filter(Seat.class_id == class_id, Seat.role == "student", Seat.public_id.isnot(None))
                .all()
            )
            existing_by_public_id = {seat.public_id: seat for seat in existing_seats if seat.public_id}
            requested_public_ids = {row["actor_public_id"] for row in rows if row["actor_public_id"]}
            missing_seats = [seat for pid, seat in existing_by_public_id.items() if pid not in requested_public_ids]

            if missing_seats and not confirm_roster_delete:
                missing_names = []
                for seat in missing_seats:
                    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
                    display_name = " ".join(part for part in [getattr(profile, "first_name", None), getattr(profile, "last_name", None)] if part) or seat.public_id
                    missing_names.append(display_name)
                flash(
                    "Roster is missing existing students: " + ", ".join(missing_names) +
                    ". Re-upload the file with those rows removed only after confirming deletion.",
                    "error",
                )
                return redirect(url_for("admin.students"))

            added_count = 0
            updated_count = 0
            deleted_count = 0
            for row in rows:
                actor_public_id = row["actor_public_id"]
                first_name = row["first_name"]
                last_name = row["last_name"]
                notes = row["notes"]
                if actor_public_id and actor_public_id in existing_by_public_id:
                    seat = existing_by_public_id[actor_public_id]
                    update_or_create_roster_seat(
                        class_id=class_id,
                        first_name=first_name,
                        last_name=last_name,
                        notes=notes,
                        existing_seat=seat,
                    )
                    updated_count += 1
                    continue

                if actor_public_id:
                    # Unknown public_id: treat as add only if it is not already in the class.
                    pass

                update_or_create_roster_seat(
                    class_id=class_id,
                    first_name=first_name,
                    last_name=last_name,
                    notes=notes,
                )
                added_count += 1

            if confirm_roster_delete and missing_seats:
                for seat in missing_seats:
                    delete_seat_with_profile(seat)
                    deleted_count += 1

            flash(
                f"Roster synced: {updated_count} updated, {added_count} added, {deleted_count} deleted.",
                "admin_success",
            )
            return redirect(url_for("admin.students"))

        stream = io.StringIO(content, newline=None)
        csv_input = csv.DictReader(stream)
        added_count = 0
        errors = 0
        duplicated = 0

        from app.models import Seat, IdentityProfile
        from app.hash_utils import hash_username_lookup
        import random
        import string

        # v2: All CSV uploads target the current canonical class.
        # block/period is display metadata only (INV-CORE) — never a scoping key.
        class_id = (getattr(g.canonical_context, "class_id", None) or "").strip()
        if not class_id:
            flash("Select a class before uploading roster data.", "error")
            return redirect(url_for("admin.students"))

        class_row = verify_teacher_owns_class(class_id, user_id)
        if not class_row:
            flash("Class not found or you do not own it.", "error")
            return redirect(url_for("admin.students"))

        join_code = get_display_join_code(class_id)

        # Keep track of matched DB seats during this upload to avoid recreating them
        matched_seats = set()
        name_counts_in_run = {}  # (class_id, name_key) -> count

        for row in csv_input:
            try:
                first_name = (row.get('first_name') or row.get('First Name') or '').strip()
                last_name = (row.get('last_name') or row.get('Last Name') or '').strip()

                if not first_name and not last_name:
                    continue
                if not first_name or not last_name:
                    raise ValueError("Missing required fields.")

                claim_first_name_hash = hash_username_lookup(first_name.lower())
                claim_last_name_hash = hash_username_lookup(last_name.lower())
                name_key = (first_name.lower(), last_name.lower())

                # Find all seats in the DB for this class with the same name hashes.
                db_seats = (
                    Seat.query
                    .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
                    .filter(
                        Seat.class_id == class_id,
                        Seat.claim_first_name_hash == claim_first_name_hash,
                        Seat.claim_last_name_hash == claim_last_name_hash,
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
                seat = create_roster_student_seat(
                    class_id=class_id,
                    first_name=first_name,
                    last_name=last_name,
                    dedupe_code=dedupe_code,
                    claim_first_name_hash=claim_first_name_hash,
                    claim_last_name_hash=claim_last_name_hash,
                    roster_fingerprint=roster_fingerprint,
                )
                added_count += 1
            except Exception as e:
                current_app.logger.error(f"Error processing row {row}: {e}")
                errors += 1

        # Build success message
        success_msg = f"{added_count} roster seats created successfully"
        if errors > 0:
            success_msg += f"\n{errors} rows could not be processed"
        if duplicated > 0:
            success_msg += f"\n{duplicated} duplicate seats skipped"
        if join_code:
            success_msg += f"\n\nJoin Code: {join_code}"
            success_msg += "\nShare this code with your students so they can claim their accounts."

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


@admin_bp.route('/export-class-roster')
@admin_required
def export_class_roster():
    """Export the current class roster as the editable sync CSV."""
    user_id = g.canonical_context.user_id
    class_id = (getattr(getattr(g, "canonical_context", None), "class_id", None) or "").strip()
    if not class_id:
        flash("Select a class before exporting roster.", "error")
        return redirect(url_for("admin.students"))

    class_row = verify_teacher_owns_class(class_id, user_id)
    if not class_row:
        flash("Select a class before exporting roster.", "error")
        return redirect(url_for("admin.students"))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["join_code", "actor_public_id", "first_name", "last_name", "notes", "checking_balance", "savings_balance"])

    seats = (
        Seat.query
        .options(sa.orm.joinedload(Seat.identity_profiles))
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(Seat.class_id == class_id, Seat.role == "student")
        .order_by(Seat.id.asc())
        .all()
    )

    for seat in seats:
        profile = next((p for p in seat.identity_profiles if p.profile_type == "student"), None)
        checking_balance, savings_balance = get_available_balances(seat.id, class_id)
        writer.writerow([
            get_display_join_code(class_row.class_id),
            seat.public_id or "",
            _sanitize_csv_field(getattr(profile, "first_name", "") or ""),
            _sanitize_csv_field(getattr(profile, "last_name", "") or ""),
            _sanitize_csv_field(getattr(profile, "notes", "") or ""),
            f"{checking_balance:.2f}",
            f"{savings_balance:.2f}",
        ])

    output.seek(0)
    filename = f"class_roster_{get_display_join_code(class_row.class_id)}_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route('/export-students')
@admin_required
def export_students():
    """Export all student data to CSV."""
    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before exporting students.", "warning")
        return redirect(url_for('admin.dashboard'))

    selected_class_id = class_context["class_id"]

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'First Name', 'Last Name', 'Block', 'Checking Balance',
        'Savings Balance', 'Total Earnings', 'Insurance Plan',
        'Rent Enabled', 'Has Completed Setup'
    ])

    # Write student data
    seats = Seat.query.filter(Seat.class_id == selected_class_id, Seat.role == 'student').all()
    seats.sort(key=lambda seat: (
        (seat.identity_profile.first_name if seat.identity_profile else "").lower(),
        (seat.identity_profile.last_name if seat.identity_profile else "").lower(),
        seat.id,
    ))
    class_seat_pairs = [(seat.class_id, seat.id) for seat in seats]
    raw_balances = get_batch_balances_by_class_seat(class_seat_pairs)
    seat_map = {(seat.user_id, seat.class_id): seat for seat in seats}

    scoped_balances_by_student = {}
    for seat in seats:
        checking_total = Decimal('0.00')
        savings_total = Decimal('0.00')
        earnings_total = Decimal('0.00')
        balances = raw_balances.get((str(selected_class_id), seat.id))
        if not balances:
            balances = {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}
        checking_total += Decimal(balances['checking_cents']) / 100
        savings_total += Decimal(balances['savings_cents']) / 100
        earnings_total += Decimal(balances.get('earnings', Decimal('0.00')))
        scoped_balances_by_student[seat.id] = {
            'checking': checking_total,
            'savings': savings_total,
            'earnings': earnings_total,
        }

    # Prefetch active insurances to avoid N+1 queries
    active_insurances_map = {}
    if user_id and seat_ids:
        class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id).subquery()
        pass

    for seat in seats:
        export_block = seat.class_economy.section if seat and seat.class_economy else None
        if selected_class_id:
            scoped_seat = next((s for s in seats if s.class_id == selected_class_id and s.user_id == seat.user_id), None)
            if scoped_seat and scoped_seat.class_economy and scoped_seat.class_economy.section:
                export_block = scoped_seat.class_economy.section

        active_insurance = active_insurances_map.get(seat.id)
        insurance_name = active_insurance.policy.title if active_insurance else 'None'

        if selected_join_code:
            checking_balance, savings_balance = get_available_balances(seat.id, selected_class_id)
            total_earnings = Decimal(str(sum(
                row.amount for row in Transaction.query.filter(
                    Transaction.seat_id == seat.id,
                    Transaction.class_id == selected_class_id,
                    Transaction.type == 'payroll',
                ).all()
            )))
        else:
            scoped_balances = scoped_balances_by_student.get(seat.id, {})
            checking_balance = scoped_balances.get('checking', Decimal('0.00'))
            savings_balance = scoped_balances.get('savings', Decimal('0.00'))
            total_earnings = scoped_balances.get('earnings', Decimal('0.00'))

        writer.writerow([
            _sanitize_csv_field(seat.identity_profile.first_name if seat.identity_profile else ''),
            _sanitize_csv_field(seat.identity_profile.last_name if seat.identity_profile else ''),
            _sanitize_csv_field(export_block),
            f"{checking_balance:.2f}",
            f"{savings_balance:.2f}",
            f"{total_earnings:.2f}",
            _sanitize_csv_field(insurance_name),
            'Yes' if seat.is_rent_enabled else 'No',
            'Yes' if (seat.user and seat.user.pin_hash is not None) else 'No'
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

def _latest_attendance_events_for_class(class_id: str, seat_ids: list[int] | None = None) -> dict[int, AttendanceSession]:
    query = AttendanceSession.query.filter(AttendanceSession.class_id == class_id)
    if seat_ids is not None:
        if not seat_ids:
            return {}
        query = query.filter(AttendanceSession.target_seat_id.in_(seat_ids))

    events = query.order_by(
        AttendanceSession.target_seat_id.asc(),
        AttendanceSession.timestamp.desc(),
        AttendanceSession.id.desc(),
    ).all()
    latest_by_seat_id = {}
    for event in events:
        latest_by_seat_id.setdefault(event.target_seat_id, event)
    return latest_by_seat_id


@admin_bp.route('/tap-out-students', methods=['POST'])
@admin_required
def tap_out_students():
    """
    Admin endpoint to tap out one or more seats.
    Accepts seat_ids or tap_out_all (taps out all active seats in the teacher's classes).
    """
    data = request.get_json()

    seat_ids = data.get('seat_ids', [])
    reason = data.get('reason', 'Teacher tap-out')
    tap_out_all = data.get('tap_out_all', False)

    if not tap_out_all and not seat_ids:
        return jsonify({"status": "error", "message": "Either seat_ids or tap_out_all must be provided."}), 400

    tapped_out = []
    already_inactive = []
    errors = []
    ctx = g.canonical_context
    class_id = ctx.class_id

    try:
        if tap_out_all:
            student_seats = Seat.query.filter_by(
                class_id=class_id,
                role="student",
            ).all()
            latest_by_seat_id = _latest_attendance_events_for_class(class_id)
            seat_ids = [
                seat.id for seat in student_seats
                if latest_by_seat_id.get(seat.id) and latest_by_seat_id[seat.id].status == "active"
            ]
        else:
            seat_ids = [int(seat_id) for seat_id in seat_ids]
            latest_by_seat_id = _latest_attendance_events_for_class(class_id, seat_ids)

        for seat_id in seat_ids:
            seat = Seat.query.filter_by(id=seat_id, class_id=class_id, role="student").first()
            if seat is None:
                errors.append(f"Seat {seat_id} not found in the current class")
                continue

            latest_event = latest_by_seat_id.get(seat_id)
            if not latest_event or latest_event.status != "active":
                profile = IdentityProfile.query.filter_by(seat_id=seat_id).first()
                name = f"{profile.first_name} {profile.last_name}" if profile else f"Seat {seat_id}"
                already_inactive.append(name)
                continue

            record_attendance_session(
                ctx=ctx,
                target_seat_id=seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="inactive",
                reason=reason,
                reason_code=AttendanceReasonCode.DONE_FOR_DAY,
                idempotency_key=f"admin_tap_out:{class_id}:{seat_id}:{secrets.token_hex(12)}",
            )

            profile = IdentityProfile.query.filter_by(seat_id=seat_id).first()
            name = f"{profile.first_name} {profile.last_name}" if profile else f"Seat {seat_id}"
            tapped_out.append(name)

            current_app.logger.info("Admin tapped out seat %s in class %s", seat_id, class_id)

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
            "already_inactive": already_inactive
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin tap-out failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to tap out students due to an internal error."
        }), 500


@admin_bp.route('/tap-in-students', methods=['POST'])
@admin_required
def tap_in_students():
    """
    Admin endpoint to tap in one or more seats.
    Accepts seat_ids list.
    """
    data = request.get_json()

    seat_ids = data.get('seat_ids', [])

    if not seat_ids:
        return jsonify({"status": "error", "message": "seat_ids must be provided."}), 400

    tapped_in = []
    already_active = []
    errors = []
    ctx = g.canonical_context
    class_id = ctx.class_id

    try:
        seat_ids = [int(seat_id) for seat_id in seat_ids]
        latest_by_seat_id = _latest_attendance_events_for_class(class_id, seat_ids)

        for seat_id in seat_ids:
            seat = Seat.query.filter_by(id=seat_id, class_id=class_id, role="student").first()
            if not seat:
                errors.append(f"Seat {seat_id} not found in the current class")
                continue

            latest_event = latest_by_seat_id.get(seat_id)
            if latest_event and latest_event.status == "active":
                profile = IdentityProfile.query.filter_by(seat_id=seat_id).first()
                name = f"{profile.first_name} {profile.last_name}" if profile else f"Seat {seat_id}"
                already_active.append(name)
                continue

            record_attendance_session(
                ctx=ctx,
                target_seat_id=seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="active",
                reason="Teacher tap-in",
                idempotency_key=f"admin_tap_in:{class_id}:{seat_id}:{secrets.token_hex(12)}",
            )

            profile = IdentityProfile.query.filter_by(seat_id=seat_id).first()
            name = f"{profile.first_name} {profile.last_name}" if profile else f"Seat {seat_id}"
            tapped_in.append(name)

            current_app.logger.info("Admin tapped in seat %s in class %s", seat_id, class_id)

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
            "already_active": already_active
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin tap-in failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to tap in students. Please try again or contact support."
        }), 500


@admin_bp.route('/students/bulk-adjust-hall-pass-entitlements', methods=['POST'])
@admin_required
@feat_shell("FEAT-STOR-001")
def bulk_adjust_hall_pass_entitlements():
    """Bulk grant or remove hall-pass entitlements for selected students."""
    data = request.get_json()

    # Get parameters
    student_ids = data.get('student_ids', [])
    update_type = data.get('update_type')
    value = data.get('value', 0)

    if not student_ids:
        return jsonify({"status": "error", "message": "student_ids must be provided."}), 400

    if update_type not in ['add', 'remove']:
        return jsonify({"status": "error", "message": "update_type must be 'add' or 'remove'."}), 400

    try:
        value = int(value)
        if value <= 0:
            return jsonify({"status": "error", "message": "Value must be positive."}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Value must be a valid integer."}), 400

    updated = []
    errors = []

    try:
        # Process each student ID
        for seat_id in student_ids:
            student = db.session.get(Seat, int(seat_id))

            if not student:
                errors.append(f"Student {seat_id} not found")
                continue

            if not verify_teacher_owns_class(student.class_id, g.canonical_context.user_id):
                errors.append(f"Student {seat_id} not found")
                continue

            if update_type == 'add':
                grant_hall_passes(
                    student,
                    value,
                )
            else:
                try:
                    remove_hall_passes(
                        student,
                        value,
                    )
                except ValueError as exc:
                    errors.append(f"Student {student.id}: {exc}")
                    continue

            updated.append(student.identity_profile.full_name if student.identity_profile else str(student.id))
            new_value = get_hall_pass_balance(student.id, student.class_id)
            current_app.logger.info(
                f"Admin adjusted hall pass entitlements for student {student.id} ({student.identity_profile.full_name if student.identity_profile else 'unknown'}): {update_type} {value}, new value: {new_value}"
            )

        # Commit all updates
        # Build response message
        action_text = {
            'add': f'granted {value}',
            'remove': f'removed {value}'
        }

        message = f"Successfully adjusted hall-pass entitlements for {len(updated)} student(s) ({action_text[update_type]})"
        if errors:
            message += f". {len(errors)} error(s) occurred"

        return jsonify({
            "status": "success",
            "message": message,
            "updated": updated
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Bulk hall pass update failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to update hall passes. Please try again or contact support."
        }), 500


# -------------------- BANKING ROUTES --------------------

@admin_bp.route('/banking')
@admin_required
def banking():
    """Banking management page with transactions and settings."""
    user_id = g.canonical_context.user_id
    feature_options = get_admin_feature_join_code_options('banking', canonical_context=g.canonical_context)
    selected_scope = require_admin_feature_scope(
        'banking',
        canonical_context=g.canonical_context,
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
    account_q = request.args.get('account', '')
    type_q = request.args.get('type', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = 50

    # Get admin's class_ids
    user_id = g.canonical_context.user_id
    # Base query joining Transaction with Seat for seat-scoped filtering
    query = (
        db.session.query(Transaction, Seat)
        .join(Seat, Transaction.seat_id == Seat.id)
        .filter(Transaction.class_id == selected_scope["class_id"])
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
        all_students = Seat.query.filter(
            Seat.class_id.in_(teacher_class_ids),
            Seat.claimed_at.isnot(None),
        ).all()
        for seat in all_students:
            _ip = seat.identity_profile
            if student_q.lower() in (_ip.full_name if _ip else "").lower() and seat.user_id:
                matching_student_ids.append(seat.user_id)

        # If there are any matches (by ID or name), filter the query
        if matching_student_ids:
            query = query.filter(Seat.user_id.in_(matching_student_ids))
        else:
            # If no students match, return no results
            query = query.filter(sa.false())

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
    for tx, seat in recent_transactions:
        _ip = seat.identity_profile if seat else None
        transactions.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'actor_public_id': seat.public_id if seat else None,
            'student_name': (_ip.full_name if _ip else str(seat.id if seat else "")),
            'student_block': seat.class_economy.section if seat and seat.class_economy else None,
            'amount': tx.amount,
            'account_type': tx.account_type,
            'description': tx.description,
            'type': tx.type,
            'is_void': tx.is_void
        })

    # Get all students for stats
    selected_class_id = selected_scope['class_id']
    students = [
        seat for seat in Seat.query.filter(
            Seat.class_id == selected_class_id,
            Seat.role == 'student',
        ).all()
        if seat.claimed_at is not None
    ]

    # Calculate banking stats through the ledger authority for the selected class only.
    total_checking = Decimal('0.00')
    total_savings = Decimal('0.00')
    students_with_savings = 0
    for student in students:
        seat_id = student.id
        checking_balance, savings_balance = get_available_balances(seat_id, selected_class_id)
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
    class_labels_by_block = _get_class_labels_for_blocks(g.canonical_context, blocks)

    # Build join_codes_by_block dictionary
    join_codes_by_block = _get_join_codes_by_block(g.canonical_context, blocks)

    # Get transaction types for filter (filtered to this teacher's students)
    transaction_types = (
        db.session.query(Transaction.type)
        .filter(Transaction.class_id == selected_class_id)
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
        teacher_blocks=teacher_blocks,
        selected_feature_scope=selected_scope,
    )


@admin_bp.route('/banking/settings', methods=['POST'])
@admin_required
def banking_settings_update():
    """Update banking settings for a specific class or all classes."""
    from app.models import _quantize_currency

    user_id = g.canonical_context.user_id
    form = BankingSettingsForm()

    if form.validate_on_submit():
        selected_scope = require_admin_feature_scope(
            'banking',
            canonical_context=g.canonical_context,
        )
        settings_block = selected_scope['block']
        blocks_to_update = [settings_block]

        try:
            payload_hash = hashlib.sha256(
                json.dumps(
                    {
                        "class_id": selected_scope["class_id"],
                        "settings_block": settings_block,
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
                        canonical_context=g.canonical_context,
                        requested_block=block,
                        allow_default=False,
                    )
                    # Get or create settings for this class
                    settings = BankingSettings.query.filter_by(
                        class_id=scope_for_block['class_id'],
                        block=block,
                    ).first()
                    if not settings:
                        settings = create_banking_settings(
                            class_id=scope_for_block['class_id'],
                            block=block,
                        )

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

            flash('Banking settings updated successfully!', 'success')
            current_app.logger.info(f"Banking settings updated by admin for {len(blocks_to_update)} class(es)")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update banking settings: {e}")
            flash('Error updating banking settings.', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')

    return redirect(url_for('admin.banking'))


# -------------------- DELETION REQUESTS --------------------

@admin_bp.route('/account-delete', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
@admin_required
def account_delete():
    """
    Teacher-managed account deletion.

    Deletion executes immediately after timed confirmation gate checks.
    """
    user_id = g.canonical_context.user_id
    admin = db.session.get(User, user_id)
    if not admin:
        flash('Unable to load your account.', 'error')
        return redirect(url_for('admin.login'))
    admin_username = admin.get_display_username().strip()

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
            _hard_delete_teacher_account_scope(user_id)
            delete_admin_account_rows(admin)

            session.pop("user_id", None)
            session.pop("last_activity", None)
            flash('Your account and associated class data were permanently deleted.', 'success')
            return redirect(url_for('admin.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error deleting admin account: {e}")
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

    canonical_context = g.canonical_context
    user_id = canonical_context.user_id
    selected_class_id = canonical_context.class_id

    teacher_user_class_rows = get_all_classes_by_teacher(user_id)
    selected_option = next(({
        'class_id': ce_row.class_id,
        'join_code': get_display_join_code(ce_row.class_id),
        'label': ce_row.display_name or get_display_join_code(ce_row.class_id),
    } for ce_row in teacher_user_class_rows if ce_row.class_id == selected_class_id), None)
    selected_join_code = (selected_option["join_code"] if selected_option else get_display_join_code(selected_class_id) or "").strip()
    selected_class_label = selected_option["label"] if selected_option else None

    class_scope_options = [
        {
            'class_id': ce_row.class_id,
            'join_code': get_display_join_code(ce_row.class_id),
            'label': ce_row.display_name or get_display_join_code(ce_row.class_id),
        }
        for ce_row in teacher_user_class_rows
    ]

    def _support_report_views(issues):
        """Build view-model dicts for the My Tickets list."""
        views = []
        for issue in issues:
            explanation = issue.student_explanation or ''
            first_line = explanation.split('\n', 1)[0] if explanation else ''
            clean = explanation
            if first_line.startswith('SUPPORT_SCOPE|'):
                clean = explanation.split('\n', 1)[1].strip() if '\n' in explanation else explanation

            scope_jc = selected_join_code or 'Unknown'
            class_label = selected_class_label or 'Unknown Class'

            if issue.class_public_id:
                from app.services.class_configuration_query_service import get_class_by_public_id
                ce = get_class_by_public_id(issue.class_public_id)
                if ce:
                    scope_jc = ce.join_code
                    class_label = ce.display_name or ce.join_code

            views.append({
                'report': {
                    'title': 'Support Ticket',
                    'status': issue.status,
                    'submitted_at': issue.submitted_at,
                    'report_type': issue.issue_type,
                },
                'class_label': class_label,
                'scope_join_code': scope_jc,
                'scope_class_id': issue.class_public_id,
                'issue_category': issue.category.name if issue.category else 'Unknown',
                'clean_description': clean,
            })
        return views

    category_to_report_type = {
        'general': 'comment',
        'bug': 'bug',
        'feature': 'suggestion',
    }

    def _build_scope_metadata(class_id_value, class_label_value, category_value):
        return (
            f"SUPPORT_SCOPE|class_id={class_id_value}|class_label={class_label_value}|category={category_value}"
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
            metadata.get('class_id'),
            metadata.get('class_label'),
            metadata.get('category'),
            cleaned_body,
        )

    if not selected_class_id and request.method == 'GET':
        flash(
            "You don't have any classes yet. Please add a class from your dashboard before submitting a support ticket.",
            "info",
        )

    if request.method == 'POST':
        if not selected_class_id:
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
        if not selected_class_id:
            flash("Please select one of your classes before submitting a support ticket.", "error")
            return redirect(url_for('admin.help_support'))
        class_label = selected_class_label or selected_join_code or 'Unknown'

        if issue_category not in category_to_report_type:
            flash("Please select a valid support ticket category.", "error")
            my_reports = _support_report_views(
                Issue.query.filter(
                    Issue.actor_public_id == generate_anonymous_code(f"admin:{user_id}"),
                    Issue.class_public_id == selected_class_id,
                    Issue.issue_type == 'general',
                ).order_by(Issue.submitted_at.desc()).limit(20).all()
            )

            return render_template(
                'admin_support_tickets.html',
                current_page='help',
                page_title='Help & Support',
                selected_class_id=selected_class_id,
                class_scope_options=class_scope_options,
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
            my_reports = _support_report_views(
                Issue.query.filter(
                    Issue.actor_public_id == generate_anonymous_code(f"admin:{user_id}"),
                    Issue.class_public_id == selected_class_id,
                    Issue.issue_type == 'general',
                ).order_by(Issue.submitted_at.desc()).limit(20).all()
            )

            return render_template(
                'admin_support_tickets.html',
                current_page='help',
                page_title='Help & Support',
                selected_class_id=selected_class_id,
                class_scope_options=class_scope_options,
                my_reports=my_reports,
                help_content=HELP_ARTICLES['teacher'],
                format_utc_iso=format_utc_iso,
                form_issue_category=issue_category,
                form_title=title,
                form_description=description,
                form_expected_behavior=expected_behavior,
                form_page_url=page_url,
            )
        anonymous_code = generate_anonymous_code(f"admin:{user_id}")
        metadata_header = _build_scope_metadata(selected_class_id, class_label or 'Unknown', issue_category)
        scoped_description = f"{metadata_header}\n\n{description}"

        try:
            with FEATContext("FEAT-SUP-001", idempotency_key=f"admin_help_support:{user_id}:{selected_class_id}:{title}"):
                category = IssueCategory.query.filter_by(
                    name=category_to_report_type[issue_category],
                ).first()
                if not category:
                    category = IssueCategory.query.first()
                create_support_ticket(
                    actor_public_id=anonymous_code,
                    class_public_id=selected_class_id,
                    category_id=category.id,
                    scoped_description=scoped_description,
                    expected_behavior=expected_behavior,
                    page_url=page_url,
                )

            flash("Your support ticket has been submitted directly to system administration.", "success")
            return redirect(url_for('admin.help_support'))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.error("Error submitting report")
            flash("An error occurred while submitting your ticket. Please try again.", "error")
            return redirect(url_for('admin.help_support'))

    anonymous_code = generate_anonymous_code(f"admin:{user_id}")
    reports = Issue.query.filter(
        Issue.actor_public_id == anonymous_code,
        Issue.issue_type == 'general',
    ).order_by(Issue.submitted_at.desc()).limit(50).all()
    filtered_reports = [
        r for r in reports
        if not selected_class_id or not r.class_public_id or r.class_public_id == selected_class_id
    ][:20]
    my_reports = _support_report_views(filtered_reports)

    return render_template('admin_support_tickets.html',
                         current_page='help',
                         page_title='Help & Support',
                         selected_class_id=selected_class_id,
                         class_scope_options=class_scope_options,
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
    user_id = g.canonical_context.user_id

    # Get all configured periods for this teacher from class economy anchors.
    periods = _get_teacher_blocks(g.canonical_context)
    join_codes_by_period = _get_join_codes_by_block(g.canonical_context, periods)
    class_id_by_period = {
        block: class_id
        for block, class_id in _get_class_ids_by_block(g.canonical_context, periods).items()
        if class_id
    }

    period_settings = {}
    for period in periods:
        scoped_features = get_class_feature_settings(None, class_id=class_id_by_period.get(period))
        period_settings[period] = scoped_features["features"] if scoped_features else ClassFeature.defaults_dict()

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
    user_id = g.canonical_context.user_id

    try:
        data = request.get_json()
        period = period.strip().upper()

        class_id = (
            next(iter([cid for cid in _get_class_ids_by_block(g.canonical_context, [period]).values() if cid]), None)
        )
        if not class_id:
            return jsonify({'status': 'error', 'message': 'Class scope not found for this period.'}), 400

        current_features = get_class_feature_settings(None, class_id=class_id)
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
        idempotency_key = f"feat:class:feature-settings:update:{class_id}:{payload_hash}"

        # Ensure FEAT owns transaction boundary for feature-toggle writes.
        db.session.rollback()
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            replace_enabled_class_features(class_id, enabled_features)

        return jsonify({
            'status': 'success',
            'message': f'Settings updated for Period {period}',
            'settings': get_class_feature_settings(None, class_id=class_id)["features"]
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating period feature settings: {e}")
        return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500


@admin_bp.route('/feature-settings/copy', methods=['POST'])
@admin_required
def copy_feature_settings():
    """Copy feature settings from one period to other periods."""
    user_id = g.canonical_context.user_id

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
        source_class_id = (
            next(iter([cid for cid in _get_class_ids_by_block(g.canonical_context, [source_period]).values() if cid]), None)
        )
        if not source_class_id:
            return jsonify({
                'status': 'error',
                'message': f'Class scope not found for period {source_period}.'
            }), 400
        source_dict = get_class_feature_settings(None, class_id=source_class_id)["features"]

        payload_hash = hashlib.sha256(
            json.dumps(
                {"source_period": source_period, "target_periods": target_periods},
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        idempotency_key = (
            f"feat:class:feature-settings:copy:{source_class_id}:{payload_hash}"
        )

        # Ensure FEAT owns transaction boundary for feature-toggle writes.
        db.session.rollback()

        # Copy to target periods
        copied_count = 0
        with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
            for period in target_periods:
                if period == source_period:
                    continue  # Skip copying to self

                target_class_id = (
                    next(iter([cid for cid in _get_class_ids_by_block(g.canonical_context, [period]).values() if cid]), None)
                )
                if not target_class_id:
                    return jsonify({
                        'status': 'error',
                        'message': f'Class scope not found for period {period}.'
                    }), 400

                replace_enabled_class_features(
                    target_class_id,
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
    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before managing announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    selected_class_id = class_context["class_id"]
    selected_join_code = get_display_join_code(selected_class_id)

    # Get announcements for this teacher scoped to the active class context only.
    from app.models import Announcement
    announcements_list = Announcement.query.filter_by(
        user_id=user_id,
        class_id=selected_class_id,
    ).order_by(Announcement.created_at.desc()).all()

    active_class_label = selected_join_code

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

    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before creating announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    selected_class_id = class_context["class_id"]
    selected_join_code = get_display_join_code(selected_class_id)

    form = AnnouncementForm()
    form.class_id.data = selected_class_id
    if request.method == 'GET':
        form.class_id.data = selected_class_id

    if form.validate_on_submit():
        try:
            announcement = create_class_announcement(
                user_id=user_id,
                class_id=selected_class_id,
                title=form.title.data,
                message=form.message.data,
                priority=form.priority.data,
                is_active=form.is_active.data,
                expires_at=form.expires_at.data,
            )
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
        active_class_label=selected_join_code,
        active_block=class_context.get("block"),
    )


@admin_bp.route('/announcements/edit/<int:announcement_id>', methods=['GET', 'POST'])
@admin_required
def announcement_edit(announcement_id):
    """Edit an existing announcement."""
    from app.forms import AnnouncementForm
    from app.models import Announcement

    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before editing announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        user_id=user_id,
        class_id=class_context["class_id"],
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    # Get the class info for this announcement
    form = AnnouncementForm(obj=announcement)
    form.class_id.data = class_context["class_id"]

    if form.validate_on_submit():
        try:
            update_class_announcement(
                announcement,
                title=form.title.data,
                message=form.message.data,
                priority=form.priority.data,
                is_active=form.is_active.data,
                expires_at=form.expires_at.data,
            )

            flash(f'Announcement "{announcement.title}" updated successfully!', 'success')
            return redirect(url_for('admin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating announcement: {e}")
            flash('An error occurred while updating the announcement.', 'danger')

    # Build view model for class context display in edit mode.
    class_label = class_context.get("join_code") or class_context.get("class_id") or "Unknown"
    teacher_block_view = {
        'class_label': class_label,
    }

    # Build announcement view model for preview section.
    announcement_view = {
        'title': announcement.title,
        'message': announcement.message,
        'priority_class': announcement.get_priority_class(),
        'priority_icon': announcement.get_priority_icon(),
    }

    return render_template(
        'admin_announcement_form.html',
        form=form,
        announcement=announcement_view,
        teacher_block=teacher_block_view,
        action='Edit'
    )


@admin_bp.route('/announcements/delete/<int:announcement_id>', methods=['POST'])
@admin_required
def announcement_delete(announcement_id):
    """Delete an announcement."""
    from app.models import Announcement

    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        flash("Select a class from the sidebar before deleting announcements.", "warning")
        return redirect(url_for('admin.dashboard'))

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        user_id=user_id,
        class_id=class_context["class_id"],
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    try:
        title = announcement.title
        delete_class_announcement(announcement)

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

    user_id = g.canonical_context.user_id
    class_context = _resolve_admin_class_context(g.canonical_context)
    if not class_context:
        return jsonify({'status': 'error', 'message': 'Select a class from the sidebar first.'}), 400

    # Get announcement and verify ownership in active class context.
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        user_id=user_id,
        class_id=class_context["class_id"],
    ).first()

    if not announcement:
        return jsonify({'status': 'error', 'message': 'Announcement not found'}), 404

    try:
        update_class_announcement(
            announcement,
            title=announcement.title,
            message=announcement.message,
            priority=announcement.priority,
            is_active=not announcement.is_active,
            expires_at=announcement.expires_at,
        )

        return jsonify({
            'status': 'success',
            'is_active': announcement.is_active,
            'message': f'Announcement {"activated" if announcement.is_active else "deactivated"}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling announcement: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred while toggling the announcement. Please try again.'}), 500


# -------------------- TEACHER ONBOARDING --------------------

@admin_bp.route('/onboarding/status', methods=['GET'])
@admin_required
def onboarding_status():
    """Get onboarding task completion status for the Getting Started widget.

    All status is derived live from existing feature configuration — no
    separate onboarding table.
    """
    user_id = g.canonical_context.user_id
    try:
        class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id).subquery()

        completion = {
            'roster': (
                db.session.query(Seat.id)
                .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                .filter(
                    ClassEconomy.teacher_user_id == user_id,
                    Seat.role == "student",
                    Seat.user_id.isnot(None),
                    Seat.claimed_at.isnot(None),
                )
                .count()
            ) > 0,
            'payroll': PayrollSettings.query.filter(
                PayrollSettings.class_id.in_(sa.select(class_ids_subq))
            ).first() is not None,
            'store': StoreItem.query.filter(
                StoreItem.class_id.in_(sa.select(class_ids_subq))
            ).count() > 0,
            'banking': BankingSettings.query.filter(
                BankingSettings.class_id.in_(sa.select(class_ids_subq))
            ).first() is not None,
            'rent': RentSettings.query.with_entities(RentSettings.id).filter(
                RentSettings.class_id.in_(sa.select(class_ids_subq))
            ).first() is not None,
            'insurance': False,
            'hall_pass': HallPassSettings.query.filter(
                HallPassSettings.class_id.in_(sa.select(class_ids_subq))
            ).first() is not None,
            'personalization': has_personalized_class(user_id),
            'passkey': admin_has_passkeys(user_id),
        }

        return jsonify({
            'status': 'success',
            'dismissed': all(completion.values()),
            'completion': completion,
        })

    except Exception as e:
        current_app.logger.error(f"Error checking onboarding status: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to retrieve onboarding status'}), 500


@admin_bp.route('/onboarding', methods=['GET'])
@admin_required
def onboarding():
    """Teacher onboarding page for creating a brand-new class from a blank roster template."""
    return render_template('admin_create_class.html')


@admin_bp.route('/onboarding/skip', methods=['POST'])
@admin_required
def onboarding_skip():
    """No-op — onboarding status is derived live."""
    return jsonify({'status': 'success'})


@admin_bp.route('/onboarding/skip-task', methods=['POST'])
@admin_required
def onboarding_skip_task():
    """No-op — onboarding tasks are derived from feature configuration."""
    return jsonify({'status': 'success'})





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
        user_id = g.canonical_context.user_id
        data = request.get_json()

        # Get pay rate and convert to per-minute (as stored in DB)
        pay_rate_per_hour = float(data.get('pay_rate', 15.0))
        pay_rate_per_minute = pay_rate_per_hour / 60.0
        expected_weekly_hours = float(data.get('expected_weekly_hours', 5.0))
        section = data.get('block')

        # Create a temporary PayrollSettings-like object for calculation
        class TempPayrollSettings:
            def __init__(self, pay_rate, time_unit='minutes', frequency_days=7, expected_weekly_hours=None):
                self.pay_rate = pay_rate
                self.time_unit = time_unit
                self.payroll_frequency_days = frequency_days
                self.expected_weekly_hours = expected_weekly_hours

        temp_settings = TempPayrollSettings(pay_rate_per_minute, expected_weekly_hours=expected_weekly_hours)

        # Calculate CWI
        checker = EconomyBalanceChecker(user_id, block)
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


def _resolve_admin_payroll_settings_for_class_id(canonical_context, class_id: str | None):
    """
    Resolve payroll settings with class-first precedence when a class is selected.

    - If class_id is provided: resolve settings for that canonical class scope.
    - If class_id is absent: resolve first active settings row across admin-owned classes.
    """
    if class_id:
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
                PayrollSettings.is_active.is_(True),
            )
            .first()
        )

    user_id = canonical_context.user_id if canonical_context and getattr(canonical_context, "user_id", None) else None
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id).subquery()
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
        user_id = g.canonical_context.user_id
        data = request.get_json() or {}
        class_id = (data.get('class_id') or '').strip() or None
        if not class_id:
            return jsonify({'status': 'error', 'message': 'class_id is required for economy analysis.'}), 400

        try:
            payroll_settings = _resolve_admin_payroll_settings_for_class_id(g.canonical_context, class_id)
        except NotFound:
            from app.feats.base import get_correlation_id
            operational_event_service.record(
                event_type="INVALID_CLASS_SCOPE",
                severity="warning",
                domain="economy",
                route=request.path,
                actor_id=user_id,
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
        checker = EconomyBalanceChecker(user_id, None, class_id=getattr(payroll_settings, "class_id", None))

        # Get other economy features
        class_ids_query = db.session.query(ClassEconomy.class_id).filter_by(teacher_user_id=user_id)
        scoped_class_id = class_id

        if scoped_class_id:
            rent_settings = get_rent_settings(scoped_class_id)
        else:
            rent_settings = (
                RentSettings.query.filter(
                    RentSettings.class_id.in_(sa.select(class_ids_query.subquery())),
                )
                .first()
            )

        insurance_policies_query = []
        fines_query = []
        store_items_query = StoreItem.query.filter(
            StoreItem.class_id.in_(sa.select(class_ids_query.subquery())),
            StoreItem.is_active.is_(True),
        )

        if scoped_class_id:
            store_items_query = store_items_query.filter(StoreItem.class_id == scoped_class_id)

        insurance_policies = insurance_policies_query
        fines = fines_query
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
            g.canonical_context,
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
        user_id = g.canonical_context.user_id
        data = request.get_json()

        value = _quantize_currency(data.get('value', '0'))
        explicit_class_id = (data.get('class_id') or '').strip() or None
        feature = feature.lower()
        valid_features = ['rent', 'insurance', 'fine', 'store_item']
        if feature not in valid_features:
            return jsonify({
                'status': 'error',
                'message': f"Invalid feature type. Must be one of: {', '.join(valid_features)}"
            }), 400

        try:
            payroll_settings = _resolve_admin_payroll_settings_for_class_id(
                g.canonical_context,
                explicit_class_id,
            )
        except NotFound:
            from app.feats.base import get_correlation_id
            operational_event_service.record(
                event_type="INVALID_CLASS_SCOPE",
                severity="warning",
                domain="economy",
                route=request.path,
                actor_id=user_id,
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
        checker = EconomyBalanceChecker(user_id, None, class_id=getattr(payroll_settings, "class_id", None))
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

        # Generate registration token using official SDK
        user_id = f"user_{user.id}"
        username = session.get("admin_auth_username") or f"user_{user.id}"
        displayname = user.get_display_username()

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
        user_id = g.canonical_context.user_id
        data = request.get_json()

        # No need to check for or use 'token' in the request payload.

        # Note: Credential is stored on passwordless.dev servers
        # We just track that registration occurred for UX purposes
        authenticator_name = data.get('authenticatorName', 'Unnamed Passkey')

        # Save credential metadata (credential_id is optional, stored on passwordless.dev)
        create_admin_credential(
            user_id=user_id,
            credential_id=None,  # Not needed - stored on passwordless.dev servers
            authenticator_name=authenticator_name,
        )
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

        # Check if user has passkeys
        has_passkeys = admin_has_passkeys(user.id)
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
@feat_shell("FEAT-ADMN-001")
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
            user_id = int(external_user_id.replace('user_', ''))
        except ValueError:
            current_app.logger.error(f"Invalid userId format: {external_user_id}")
            return jsonify({"error": "Invalid user ID format"}), 401

        user = db.session.get(User, user_id)
        if not user or getattr(user.user_role, "value", user.user_role) != "teacher":
            return jsonify({"error": "Invalid user ID"}), 401
        # Update credential last_used timestamp.
        # Credentials are stored without credential_id (managed by passwordless.dev),
        # so update last_used for all credentials belonging to this canonical user.
        now = utc_now()
        touch_admin_credentials_last_used(user.id, now)

        # Create session
        auth_username = session.get('passkey_auth_username')
        session.clear()
        establish_teacher_session(user)
        nonce = secrets.token_urlsafe(32)
        session["current_session_nonce"] = nonce
        user.current_session_nonce = nonce
        session["login_time"] = now.isoformat()
        session["last_activity"] = now.isoformat()
        session['admin_auth_username'] = auth_username or f"user_{user.id}"
        set_admin_display_name_cache(user_id=user.id, display_name=user.get_display_username())
        session.permanent = True

        redirect_url = url_for('admin.dashboard')

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
        user_id = g.canonical_context.user_id
        credentials = list_admin_credentials(user_id)

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
        user_id = g.canonical_context.user_id
        credential = get_admin_credential(passkey_id, user_id)

        if not credential:
            return jsonify({"error": "Passkey not found"}), 404

        delete_admin_credential(passkey_id, user_id)
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
    user_id = g.canonical_context.user_id
    admin = db.get_or_404(User, user_id)
    credentials = list_admin_credentials(user_id)

    return render_template('admin_passkey_settings.html',
                         admin=admin,
                         credentials=credentials)


    # ==================== ISSUE RESOLUTION SYSTEM ====================


def _resolve_issue_identity(actor_public_id, class_public_id):
    """Resolve student display name and class label from public IDs.

    Returns (student_display_name, class_label).  Falls back to truncated
    public IDs when canonical records are missing.
    """
    from app.models import Seat

    student_display_name = actor_public_id[:8] if actor_public_id else 'Unknown'
    class_label = None

    if actor_public_id:
        seat = Seat.query.filter_by(public_id=actor_public_id).first()
        if seat and seat.identity_profile:
            student_display_name = seat.identity_profile.full_name

    if class_public_id:
        from app.services.class_configuration_query_service import get_class_by_public_id as _get_cpid
        ce = _get_cpid(class_public_id)
        if ce:
            class_label = ce.display_name or ce.join_code

    return student_display_name, class_label


def _issue_to_view(issue, student_display_name, class_label):
    """Build a plain-dict view model from an Issue row + resolved identity fields."""
    return {
        'id': issue.id,
        'status': issue.status,
        'student_display_name': student_display_name,
        'class_label': class_label,
        'category': {'name': issue.category.name if issue.category else 'Unknown'},
        'issue_type': issue.issue_type,
        'related_transaction_id': issue.related_transaction_id,
        'student_explanation': issue.student_explanation or '',
        'student_expected_outcome': issue.student_expected_outcome,
        'submitted_at': issue.submitted_at,
        'updated_at': issue.updated_at,
        'created_at': issue.created_at,
        'escalated_at': issue.escalated_at,
        'escalation_reason': issue.escalation_reason,
        'teacher_resolution': issue.teacher_resolution,
        'teacher_reviewed_at': issue.teacher_reviewed_at,
        'teacher_notes': issue.teacher_notes,
        'teacher_diagnostic_note': issue.teacher_diagnostic_note,
        'sysadmin_notes': issue.sysadmin_notes,
        'sysadmin_resolved_at': issue.sysadmin_resolved_at,
        'closed_at': issue.closed_at,
        'closed_by_type': issue.closed_by_type,
        'context_snapshot': issue.context_snapshot,
        'page_url': issue.page_url,
        'system_metadata': issue.system_metadata,
        'eligible_for_reward': issue.eligible_for_reward,
        'share_class_name_with_sysadmin': issue.share_class_name_with_sysadmin,
        # Relationships resolved to plain lists below when needed.
        'resolution_actions': [],
        'status_history': [],
    }


def _resolution_action_to_view(action):
    """Build a plain-dict view model from an IssueResolutionAction row."""
    return {
        'action_type': action.action_type,
        'action_description': action.action_description,
        'performed_by_type': action.performed_by_type,
        'performed_by_public_id': action.performed_by_public_id,
        'related_transaction_id': action.related_transaction_id,
        'amount_changed': action.amount_changed,
        'before_value': action.before_value,
        'after_value': action.after_value,
        'created_at': action.created_at,
    }


def _status_history_to_view(history):
    """Build a plain-dict view model from an IssueStatusHistory row."""
    return {
        'previous_status': history.previous_status,
        'new_status': history.new_status,
        'changed_at': history.changed_at,
        'changed_by_type': history.changed_by_type,
        'changed_by_public_id': history.changed_by_public_id,
        'notes': history.notes,
    }


def _resolve_issue_id_from_ref(issue_ref: str) -> int | None:
    if issue_ref.isdigit():
        return int(issue_ref)
    return resolve_opaque_ref('issue', issue_ref)

@admin_bp.route('/issues')
@admin_required
def issues_queue():
    """
    Owner issue review queue.
    Shows all student-submitted issues for this teacher's classes.
    """
    from app.models import Issue
    from app.utils.issue_categories import init_default_categories

    user_id = g.canonical_context.user_id
    canonical_context = getattr(g, "canonical_context", None)
    class_id = getattr(canonical_context, "class_id", None)
    if class_id and not _admin_owns_class(g.canonical_context, class_id):
        class_id = None

    # INV-ARC-007: keep GET route read-only.
    if not getattr(g, "read_only", False):
        init_default_categories()

    # Filter by the active class scope; v2 issues are class-scoped student records.
    if class_id:
        issues_query = Issue.query.filter_by(class_id=class_id)
    else:
        issues_query = Issue.query.filter_by(class_id=None)

    # Get issues by status.
    pending_rows = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_OPEN,
            Issue.STATUS_TEACHER_REVIEW,
            'submitted',
            'teacher_review',
        ])
    ).order_by(Issue.submitted_at.desc()).all()

    resolved_rows = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_TEACHER_FINAL_REVIEW,
            Issue.STATUS_DEV_RESOLVED,
            'teacher_resolved',
            'developer_resolved',
        ])
    ).order_by(Issue.updated_at.desc()).limit(50).all()

    escalated_rows = issues_query.filter(
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            'elevated',
            'developer_review',
        ])
    ).order_by(Issue.escalated_at.desc()).all()

    all_issues = pending_rows + resolved_rows + escalated_rows
    
    actor_ids = {i.actor_public_id for i in all_issues if i.actor_public_id}
    class_ids = {i.class_public_id for i in all_issues if i.class_public_id}
    
    from app.models import Seat

    actor_dict = {}
    if actor_ids:
        seats = Seat.query.filter(Seat.public_id.in_(actor_ids)).all()
        for seat in seats:
            if seat.identity_profile:
                actor_dict[seat.public_id] = seat.identity_profile.full_name

    class_dict = {}
    if class_ids:
        from app.services.class_configuration_query_service import get_classes_by_public_ids
        classes = get_classes_by_public_ids(list(class_ids))
        for ce in classes:
            class_dict[ce.class_public_id] = ce.display_name or ce.join_code

    def _to_queue_view(issue):
        name = actor_dict.get(issue.actor_public_id, issue.actor_public_id[:8] if issue.actor_public_id else 'Unknown')
        label = class_dict.get(issue.class_public_id)
        return _issue_to_view(issue, name, label)

    pending_issues = [_to_queue_view(i) for i in pending_rows]
    resolved_issues = [_to_queue_view(i) for i in resolved_rows]
    escalated_issues = [_to_queue_view(i) for i in escalated_rows]

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

    user_id = g.canonical_context.user_id
    canonical_context = getattr(g, "canonical_context", None)
    class_id = getattr(canonical_context, "class_id", None)

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    issue_query = Issue.query.filter_by(id=issue_id)
    if class_id:
        issue_query = issue_query.filter_by(class_id=class_id)
    issue = issue_query.first_or_404()

    name, label = _resolve_issue_identity(issue.actor_public_id, issue.class_public_id)
    issue_view = _issue_to_view(issue, name, label)
    issue_view['resolution_actions'] = [
        _resolution_action_to_view(a) for a in issue.resolution_actions
    ]
    issue_view['status_history'] = [
        _status_history_to_view(h) for h in issue.status_history
    ]
    # Template checks resolution_actions count via len()
    issue_view['_resolution_actions_count'] = len(issue_view['resolution_actions'])

    return render_template('admin_view_issue.html',
                         current_page='issues',
                         page_title=f'Issue #{issue.id}',
                         issue=issue_view,
                         issue_ref=make_opaque_ref('issue', issue.id),
                         format_utc_iso=format_utc_iso)


@admin_bp.route('/issues/<issue_ref>/resolve', methods=['POST'])
@feat_shell("FEAT-ADMN-001")
@admin_required
def resolve_issue(issue_ref):
    """
    Resolve an issue at the teacher/admin level.
    Can apply various resolution actions depending on issue type.
    """
    from app.models import Issue, Transaction
    from app.utils.issue_helpers import update_issue_status, record_resolution_action, resolve_public_id_for_user

    user_id = g.canonical_context.user_id
    canonical_context = getattr(g, "canonical_context", None)
    class_id = getattr(canonical_context, "class_id", None)

    # Resolve teacher's public identity for external-facing support records
    teacher_public_id = resolve_public_id_for_user(user_id, class_id) if class_id else None

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    issue_query = Issue.query.filter_by(id=issue_id)
    if class_id:
        class_row = get_class_economy(class_id)
        if class_row:
            issue_query = issue_query.filter_by(class_public_id=class_row.class_public_id)
    issue = issue_query.first_or_404()

    action_type = request.form.get('action_type')
    resolution_notes = request.form.get('teacher_notes', '').strip()
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
        # Resolve submitter seat from actor_public_id for transaction ownership checks
        submitter_seat = Seat.query.filter_by(public_id=issue.actor_public_id).first()

        if action_type == 'reverse_transaction' and issue.related_transaction_id:
            transaction = db.session.get(Transaction, issue.related_transaction_id)
            if (
                not transaction
                or not submitter_seat
                or transaction.seat_id != submitter_seat.id
                or transaction.is_void
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
                teacher_public_id,
                action_description=f"Reversed transaction #{transaction.id} with reversal #{reversal_tx.id}",
                related_transaction_id=reversal_tx.id,
                amount_changed=float(reversal_tx.amount),
                before_value=str(transaction.amount),
                after_value=str(reversal_tx.amount),
            )

        elif action_type == 'compensating_transaction' and issue.related_transaction_id:
            # Append-only correction: create a compensating ledger entry.
            transaction = db.session.get(Transaction, issue.related_transaction_id)
            if not transaction or not submitter_seat or transaction.seat_id != submitter_seat.id or transaction.is_void:
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
                teacher_public_id,
                action_description=f"Posted compensating transaction #{compensating_tx.id} for transaction #{transaction.id}",
                related_transaction_id=compensating_tx.id,
                amount_changed=float(compensating_tx.amount),
                before_value=str(transaction.amount),
                after_value=str(compensating_tx.amount),
            )

        elif action_type == 'manual_adjustment':
            # Owner/admin handles manually (no automatic action)
            issue.teacher_resolution = 'Manual Adjustment'
            record_resolution_action(
                issue, 'manual_adjustment', 'teacher', teacher_public_id,
                action_description=resolution_notes
            )

        elif action_type == 'deny_issue':
            # Deny the issue
            denial_reason = request.form.get('denial_reason', '').strip()
            issue.teacher_resolution = 'Denied'
            resolution_notes = denial_reason  # Reassign to preserve denial reason
            record_resolution_action(
                issue, 'deny_issue', 'teacher', teacher_public_id,
                action_description=denial_reason
            )
        else:
            flash("Please select a valid resolution action.", "error")
            return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

        # Move to teacher/admin final review; closure is a separate explicit action.
        update_issue_status(issue, Issue.STATUS_TEACHER_FINAL_REVIEW, 'teacher', teacher_public_id, notes=resolution_notes)
        issue.teacher_resolved_at = utc_now()
        issue.teacher_notes = resolution_notes

        flash("Issue moved to final review. Close it after confirming classroom state.", "success")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolving issue {issue_id}")
        flash("An error occurred while resolving the issue. Please try again.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))


@admin_bp.route('/issues/<issue_ref>/escalate', methods=['POST'])
@admin_required
def escalate_issue(issue_ref):
    """
    Escalate an issue to sysadmin (developer).
    Owner/admin marks the issue for developer investigation.
    """
    from app.models import Issue
    from app.utils.issue_helpers import update_issue_status, resolve_public_id_for_user

    user_id = g.canonical_context.user_id
    canonical_context = getattr(g, "canonical_context", None)
    class_id = getattr(canonical_context, "class_id", None)
    teacher_public_id = resolve_public_id_for_user(user_id, class_id) if class_id else None

    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)

    issue_query = Issue.query.filter_by(id=issue_id)
    if class_id:
        class_row = get_class_economy(class_id)
        if class_row:
            issue_query = issue_query.filter_by(class_public_id=class_row.class_public_id)
    issue = issue_query.first_or_404()

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
        flash("Only tickets under teacher/admin review can be escalated.", "error")
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
            teacher_public_id,
            notes=f"Escalated: {escalation_reason}",
        )

        flash("Issue escalated to developer successfully.", "success")
        return redirect(url_for('admin.issues_queue'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error escalating issue {issue_id}")
        flash("An error occurred while escalating the issue. Please try again.", "error")
        return redirect(url_for('admin.view_issue', issue_ref=make_opaque_ref('issue', issue.id)))


@admin_bp.route('/issues/<issue_ref>/close', methods=['POST'])
@admin_required
@feat_shell("FEAT-SUP-001")
def close_issue(issue_ref):
    """Owner/admin-only closure after final review."""
    from app.models import Issue
    from app.utils.issue_helpers import update_issue_status, resolve_public_id_for_user

    user_id = g.canonical_context.user_id
    canonical_context = getattr(g, "canonical_context", None)
    class_id = getattr(canonical_context, "class_id", None)
    teacher_public_id = resolve_public_id_for_user(user_id, class_id) if class_id else None
    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        abort(404)
    issue_query = Issue.query.filter_by(id=issue_id)
    if class_id:
        class_row = get_class_economy(class_id)
        if class_row:
            issue_query = issue_query.filter_by(class_public_id=class_row.class_public_id)
    issue = issue_query.first_or_404()

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
        update_issue_status(issue, Issue.STATUS_CLOSED, 'teacher', teacher_public_id, notes=resolution_summary)
        flash("Issue closed.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.error(f"Error closing issue {issue_id}")
        flash("An error occurred while closing the issue. Please try again.", "error")

    return redirect(url_for('admin.issues_queue'))
