"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import secrets
import re
from collections import defaultdict
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Blueprint, redirect, url_for, flash, request, session, jsonify, current_app, has_app_context, abort
from sqlalchemy import or_, func, select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from dateutil.relativedelta import relativedelta

from app.extensions import db, limiter
from app.models import (
    Transaction, TransactionStatus, AttendanceSession, StoreItem, StoreItemVisibility, StorePurchase,
    # StoreItemBlock removed — store_item_blocks unauthorized; use store_item_visibility (DOM-STORE-001)
    RentSettings,
    BankingSettings, FeatureSettings, Issue, Seat, User, UserRole,
    ClassEconomy, IdentityProfile, _quantize_currency
)
from app.auth import (
    admin_required,
    establish_student_session,
    get_current_class_id,
    get_current_seat,
    get_current_user,
    get_current_student_seat,
    find_canonical_user_by_auth_username,
    login_required,
    is_student_account_active,
    SESSION_TIMEOUT_MINUTES,
)
from app.services.context_resolver import ContextResolutionError, resolve_canonical_context
from app.forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, StudentCompleteProfileForm
)

# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso, render_template_with_fallback as render_template
from app.utils.constants import THEME_PROMPTS
from app.utils.turnstile import verify_turnstile_token
from app.utils.ip_handler import get_real_ip
from app.utils.claim_credentials import compute_primary_claim_hash, match_claim_hash
from app.utils.name_utils import hash_last_name_parts
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.utils.help_content import HELP_ARTICLES
from app.utils.economy_policy import (
    get_class_feature_settings,
    get_class_feature_settings_for_class,
    resolve_feature_class,
    resolve_feature_class_for_class,
)
from app.hash_utils import hash_username_lookup
from app.access import (
    AccessScopeDenied,
    resolve_scope,
    resolve_student_class_switch_scope,
)
from app.services.attendance_service import get_all_block_statuses
from app.services.ledger_service import (
    apply_monthly_savings_interest as post_monthly_savings_interest,
    get_available_balances,
)
from app.services import access_policy_service, store_service
from app.services.entitlement_service import reconcile_rent_hall_pass_top_off as _reconcile_rent_hall_pass_top_off
from app.services.recovery_service import (
    dismiss_recovery_code as dismiss_recovery_code_row,
    get_pending_recovery_code_for_seat,
    get_recovery_code_for_seat,
    set_recovery_code_verified,
)
from app.services.classroom_setup import create_student_user_for_seat
from app.feats.base import feat_shell
from app.feats.rent_payment_feat import execute_rent_payment
from app.feats.transfer_feat import execute_account_transfer
from app.feats.insurance_purchase_feat import execute_insurance_purchase
# execute_file_claim removed — insurance_claim_feat.py deleted; insurance feature broken pending DOM-OBL-001 migration
from app.payroll import get_pay_rate_for_block
from app.utils.join_code import get_display_join_code
from app.utils.time import (
    utc_now,
    ensure_utc,
    normalize_for_db,
    get_timezone,
    get_class_timezone,
    class_date,
    claim_period_bounds_utc,
    get_class_month_start_utc,
    get_class_week_range_utc,
    get_class_now,
)
from app.utils.seat_scope import transaction_scope_filter, seat_scoped_filter
from app.utils.insurance_eligibility import (
    compute_waiting_end_class_for_enrollment,
    evaluate_claim_transaction_eligibility,
    collect_reimbursed_source_tx_ids,
    resolve_claim_type,
)


def _get_identity_bound_seat_options(user_id: int):
    """Return class options for the canonical student's claimed seats."""
    seat_rows = (
        db.session.query(Seat, ClassEconomy)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.user_id == user_id,
            Seat.user_id.isnot(None),
            Seat.claimed_at.isnot(None),
            Seat.class_id.isnot(None),
        )
        .order_by(ClassEconomy.display_name.asc(), ClassEconomy.class_id.asc(), Seat.id.asc())
        .all()
    )
    return [
        {
            "seat_id": seat.id,
            "class_id": seat.class_id,
            "join_code": get_display_join_code(class_row.class_id),
            "class_identifier": class_row.display_name or get_display_join_code(class_row.class_id),
            "class_name": class_row.display_name,
        }
        for seat, class_row in seat_rows
    ]


def _reset_student_login_session():
    """Remove transient student login state before redirecting away from auth."""
    session.pop("user_id", None)
    session.pop("current_join_code", None)
    session.pop("login_time", None)
    session.pop("last_activity", None)


def _student_login_failure_message() -> str:
    return "We are having trouble with your account, please try again or ask your teacher for help"


def _student_login_hard_fail(*, student_id: int, reason: str, is_json: bool, status_code: int = 500):
    current_app.logger.error(
        "TLCP-INVARIANT-VIOLATION: %s",
        reason,
        extra={
            "actor_type": "student",
            "actor_public_id": "-",
            "class_id": "-",
            "error_class": "InvariantViolation",
            "correlation_version": "v1",
        },
    )
    _reset_student_login_session()
    if is_json:
        return jsonify(status="error", message=_student_login_failure_message()), status_code
    flash(_student_login_failure_message(), "error")
    return redirect(url_for("student.login", next=request.args.get("next")))
from app.utils.display_name_session import (
    get_teacher_display_name_cache,
    upsert_teacher_display_name_cache,
    clear_teacher_display_name_cache,
)
from app.services.tlcp import has_recent_error_for_actor
from app.services.context_resolver import (
    resolve_canonical_context,
    ContextResolutionError,
    ContextNotEstablished,
    ContextForbidden,
    ContextMismatch,
)

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.errorhandler(ContextForbidden)
@student_bp.errorhandler(ContextMismatch)
def handle_context_forbidden(e):
    current_app.logger.warning(f"Class context resolution failed (403/404 mapping): {e}")
    # Following security disclosure requirements, we hide forbidden/mismatched contexts
    abort(404)

@student_bp.errorhandler(ContextNotEstablished)
def handle_context_not_established(e):
    current_app.logger.info(f"Class context not established: {e}")
    flash("Please select a class to continue.", "info")
    return redirect(url_for('student.select_class_context'))

STUDENT_FEATURE_ENDPOINTS = {
    'student.payroll': 'payroll',
    'student.transfer': 'banking',
    'student.student_insurance': 'insurance',
    'student.purchase_insurance': 'insurance',
    'student.cancel_insurance': 'insurance',
    'student.file_claim': 'insurance',
    'student.view_policy': 'insurance',
    'student.shop': 'store',
    'student.rent': 'rent',
    'student.rent_pay': 'rent',
}


@student_bp.before_request
def enforce_student_feature_gates():
    """Hide disabled student features by returning hard 404 for mapped routes."""
    endpoint = request.endpoint or ""
    feature_name = STUDENT_FEATURE_ENDPOINTS.get(endpoint)
    if not feature_name:
        return None

    # Let auth/session guards run first when no canonical student context exists.
    context = resolve_canonical_context()
    if not context or getattr(context, "actor_role", None) != "student":
        return None

    # Some tests/flows hydrate seat context lazily during route execution.
    # Only enforce here when class context is already resolvable.
    if not context:
        return None

    if not is_feature_enabled(feature_name):
        abort(404)
    return None

# Tolerance used to match rent rows with their Transaction rows.
# This guards against small timestamp drift without weakening ownership checks.
RENT_PAYMENT_MATCH_TOLERANCE_SECONDS = 300


# -------------------- DATETIME HELPERS --------------------




# -------------------- PERIOD SELECTION HELPERS --------------------

def _find_linked_user_for_student(student: Seat | None) -> User | None:
    if not student or not student.identity_profile or not student.identity_profile.seat_id:
        return None
    return (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .filter(
            Seat.id == student.identity_profile.seat_id,
            Seat.user_id.isnot(None),
        )
        .order_by(Seat.id.asc())
        .first()
    )


def _get_canonical_student_from_context() -> Seat | None:
    """Resolve the current seat directly from canonical context."""
    context = resolve_canonical_context()
    if not context or not getattr(context, "seat_id", None):
        return None
    return db.session.get(Seat, context.seat_id)




def _get_total_earnings_for_seat(seat_id: int | None, *, class_id: str | None = None) -> Decimal:
    if not seat_id:
        return Decimal('0.00')
    query = Transaction.query.filter(
        Transaction.seat_id == seat_id,
        Transaction.amount > 0,
        Transaction.is_void == False,
        ~Transaction.description.startswith("Transfer"),
    )
    if class_id:
        query = query.filter(Transaction.class_id == class_id)
    total = query.with_entities(func.sum(Transaction.amount)).scalar()
    return _quantize_currency(total) if total else Decimal('0.00')






def _get_claimed_setup_state():
    """
    Returns (seat, user) for the active setup or recovery flow.

    During new claim: seat is the unclaimed Seat, user is None (no User created yet).
    During recovery: seat is already bound; user is the existing User with cleared credentials.
    """
    seat_id = session.get('onboarding_seat_ref')
    seat = db.session.get(Seat, seat_id) if seat_id else None

    # For recovery the User exists on the seat; for new claim seat.user_id is NULL.
    user = None
    if seat and seat.user_id:
        user_ref = session.get('onboarding_user_ref')
        if user_ref:
            user = db.session.get(User, user_ref)
        if not user:
            user = db.session.get(User, seat.user_id)

    return seat, user




def _prime_seat_teacher_display_name_cache(student_user_id: int) -> None:
    """Cache teacher display names in session for this seat-scoped session."""
    from app.models import Seat, ClassEconomy

    seats = Seat.query.filter(
        Seat.user_id == student_user_id,
        Seat.claimed_at.isnot(None),
    ).all()
    class_ids = sorted({seat.class_id for seat in seats if seat.class_id})
    seat_owner_ids = []
    if class_ids:
        classes = ClassEconomy.query.filter(ClassEconomy.class_id.in_(class_ids)).all()
        seat_owner_ids = sorted({c.user_id for c in classes if c.user_id})
    if not seat_owner_ids:
        clear_teacher_display_name_cache()
        return

    cache_updates = {str(seat_owner_id): "Teacher" for seat_owner_id in seat_owner_ids}
    upsert_teacher_display_name_cache(cache_updates)


def get_rent_settings_for_context(context):
    """Return rent settings scoped strictly to the current class_id."""
    if not context:
        return None

    if isinstance(context, dict):
        class_id = context.get('class_id')
    else:
        class_id = getattr(context, 'class_id', None)

    seat = get_current_seat()
    current_block = seat.class_economy.section.strip().upper() if seat and seat.class_economy and seat.class_economy.section else ""
    if not class_id:
        return None

    return RentSettings.query.filter_by(class_id=class_id).first()


def _support_actor_public_id(class_context):
    if not class_context:
        return None
    if isinstance(class_context, dict):
        seat_id = class_context.get('seat_id')
    else:
        seat_id = getattr(class_context, 'seat_id', None)
    seat = db.session.get(Seat, seat_id) if seat_id else None
    return seat.public_id if seat else None


def _get_rent_coverage_window(settings, coverage_due_date):
    """Return canonical [start, end) coverage window for a rent cycle."""
    if not settings or not coverage_due_date:
        return (None, None)
    start = ensure_utc(coverage_due_date)
    period_delta = _get_rent_period_delta(settings)
    end = _add_rent_period(start, period_delta)
    return (start, end)


def get_banking_settings_for_context(context):
    """Return banking settings scoped strictly to the current class_id."""
    if not context:
        return None

    if isinstance(context, dict):
        class_id = context.get('class_id')
    else:
        class_id = getattr(context, 'class_id', None)

    seat = get_current_seat()
    current_block = seat.class_economy.section.strip().upper() if seat and seat.class_economy and seat.class_economy.section else ""
    if not class_id:
        return None

    base_query = BankingSettings.query.filter(
        BankingSettings.class_id == class_id,
    )
    if current_block:
        scoped = base_query.filter(func.upper(BankingSettings.block) == current_block).first()
        if scoped:
            return scoped

    return base_query.filter(BankingSettings.block.is_(None)).first()


def get_feature_settings_for_student():
    """
    Get feature settings for the currently logged-in student.

    Returns the class-scoped feature settings for the student's current teacher/period context.

    Returns:
        dict: Feature settings dictionary with enabled/disabled flags
    """
    context = resolve_canonical_context()
    if not context:
        return FeatureSettings.get_defaults()

    class_id = context.class_id
    if not class_id:
        return FeatureSettings.get_defaults()

    scoped_features = get_class_feature_settings_for_class(class_id)
    if scoped_features:
        return scoped_features["features"]

    # Return system defaults
    return FeatureSettings.get_defaults()


def is_feature_enabled(feature_name):
    """
    Check if a specific feature is enabled for the current student context.

    Args:
        feature_name: The feature to check (e.g., 'store', 'insurance', 'rent')

    Returns:
        bool: True if feature is enabled, False otherwise
    """
    if feature_name == 'rent':
        rent_settings = get_rent_settings_for_context(resolve_canonical_context())
        if rent_settings:
            return True

    context = resolve_canonical_context()
    if not context:
        return False

    class_id = context.class_id
    if not class_id:
        return False

    scoped_feature = resolve_feature_class_for_class(class_id, feature_name)
    return bool(scoped_feature["enabled"]) if scoped_feature else False


def calculate_scoped_balances(seat_id: int | None, class_id: str | None) -> tuple[Decimal, Decimal]:
    """Return seat-scoped balances from the ledger service."""
    if not seat_id or not class_id:
        return Decimal('0.00'), Decimal('0.00')
    return get_available_balances(seat_id, class_id)



# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-001")
def claim_account():
    """
    PAGE 1: Claim Account - Verify identity using join code to begin setup.

    New join code-based flow:
    1. Student enters join code (resolves to class_id)
    2. Student enters full first + last name
    3. If multiple seats match, student enters optional dedupe code
    4. System finds matching unclaimed seat in Seat
    5. Creates Student record for the matched seat
    6. Links Seat to Student
    7. Creates the canonical student-seat linkage
    """
    from app.models import ClassEconomy, Seat
    from app.hash_utils import hash_username_lookup
    from app.utils.join_code import format_join_code

    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        display_join_code = format_join_code(form.join_code.data)
        first_name = (form.first_name.data or "").strip()
        last_name = form.last_name.data.strip()
        dedupe_code = (form.dedupe_code.data or "").strip().upper()

        # Resolve the ingress join code to its canonical class_id before any seat lookup.
        class_row = ClassEconomy.query.filter_by(join_code=display_join_code).first()
        if not class_row:
            current_app.logger.warning(
                f"Claim attempt failed: No class found for join_code={display_join_code}"
            )
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "claim")
            return redirect(url_for('student.claim_account'))

        class_id = class_row.class_id

        # Find all unclaimed seats with this class_id (unclaimed = user_id IS NULL, DOM-IDEN-002 §VIII)
        unclaimed_seats = (
            Seat.query
            .filter(
                Seat.class_id == class_id,
                Seat.user_id.is_(None),
            )
            .all()
        )

        if not unclaimed_seats:
            current_app.logger.warning(
                f"Claim attempt failed: No unclaimed seats for class_id={class_id}"
            )
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "claim")
            return redirect(url_for('student.claim_account'))

        claim_first_name_hash = hash_username_lookup(first_name.lower())
        claim_last_name_hash = hash_username_lookup(last_name.lower())

        matched_seats = []
        for seat in unclaimed_seats:
            if seat.claim_first_name_hash == claim_first_name_hash and seat.claim_last_name_hash == claim_last_name_hash:
                matched_seats.append(seat)

        if not matched_seats:
            current_app.logger.warning(
                f"Claim attempt failed for join_code={display_join_code}, "
                f"first_name={first_name}, last_name={last_name}. "
                f"No matching seat found."
            )
            flash("No matching account found. Please check your join code and credentials.", "claim")
            return redirect(url_for('student.claim_account'))

        matched_seat = None
        if len(matched_seats) == 1:
            matched_seat = matched_seats[0]
        else:
            if not dedupe_code:
                flash(
                    "Multiple students in this class share that name. Enter your deduplication code from your teacher.",
                    "claim",
                )
                return redirect(url_for('student.claim_account'))
            dedupe_matches = [
                seat
                for seat in matched_seats
                if (seat.dedupe_code == dedupe_code)
            ]
            if len(dedupe_matches) != 1:
                flash("Invalid deduplication code. Check with your teacher.", "claim")
                return redirect(url_for('student.claim_account'))
            matched_seat = dedupe_matches[0]

        # Store seat reference in session — no DB writes until setup_pin_passphrase completes.
        # User creation and seat binding happen atomically at the end of the setup flow
        # (DOM-IDEN-002 §VIII, seat.user_id stays NULL until claim is fully complete).
        session['onboarding_seat_ref'] = matched_seat.id
        session.pop('onboarding_user_ref', None)
        session.pop('generated_username', None)
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)

        return redirect(url_for('student.create_username'))

    return render_template('student_account_claim.html', form=form)


@student_bp.route('/create-username', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-002")
def create_username():
    """PAGE 2: Create Username - Generate themed username."""
    # Only allow if claimed
    seat, user = _get_claimed_setup_state()
    if not seat:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student.claim_account'))
    if user and user.pin_hash is not None and (user.reset_code is None or not user.reset_code_expires_at or ensure_utc(user.reset_code_expires_at) < utc_now()):
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    # Assign a random theme prompt if not yet in session
    if 'theme_prompt' not in session:
        selected_theme = random.choice(THEME_PROMPTS)
        session['theme_slug'] = selected_theme['slug']
        session['theme_prompt'] = selected_theme['prompt']
    form = StudentCreateUsernameForm()
    if form.validate_on_submit():
        write_in_word = form.write_in_word.data.strip().lower()
        if not write_in_word.isalpha() or len(write_in_word) < 3 or len(write_in_word) > 12:
            flash("Please enter a valid word (3-12 letters, no numbers or spaces).", "setup")
            return redirect(url_for('student.create_username'))
        adjectives = [
            "brave", "clever", "curious", "daring", "eager", "fancy", "gentle", "honest", "jolly", "kind",
            "lucky", "mighty", "noble", "quick", "proud", "silly", "witty", "zesty", "sunny", "chill"
        ]
        adjective = random.choice(adjectives)
        # Username generation uses a transient backend-generated 4-digit
        # segment so setup never derives usernames from DOB or stable IDs.
        numeric_segment = random.randint(1000, 9999)
        _ip = seat.identity_profile
        last_name_initial = ((_ip.last_initial if _ip else "") or "")[:1].upper()
        _first = (_ip.first_name if _ip else "") or ""
        initials = f"{_first[0].upper() if _first else 'X'}{last_name_initial}"
        username = f"{adjective}{write_in_word}{numeric_segment}{initials}"
        # Save username plaintext in session for display
        # Store username in session only — no DB writes until setup_pin_passphrase.
        session['generated_username'] = username
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)


@student_bp.route('/setup-pin-passphrase', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-001")
def setup_pin_passphrase():
    """PAGE 3: Setup PIN & Passphrase - Secure the account."""
    # Only allow if claimed and username generated
    seat, user = _get_claimed_setup_state()
    username = session.get('generated_username')
    if not seat or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student.claim_account'))
    if user and user.pin_hash is not None and (user.reset_code is None or not user.reset_code_expires_at or ensure_utc(user.reset_code_expires_at) < utc_now()):
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    form = StudentPinPassphraseForm()
    if form.validate_on_submit():
        pin = form.pin.data
        passphrase = form.passphrase.data
        if not pin or not passphrase:
            flash("PIN and passphrase are required.", "setup")
            return redirect(url_for('student.setup_pin_passphrase'))
        # Atomically write credentials and bind seat (DOM-IDEN-002 §VIII).
        now = utc_now()
        if user:
            # Recovery path: User already exists, update credentials in place.
            user.username_lookup_hash = hash_username_lookup(username)
            user.username_hash = hash_username_lookup(username)
            user.pin_hash = generate_password_hash(pin)
            user.passphrase_hash = generate_password_hash(passphrase)
            user.reset_code = None
            user.reset_code_generated_at = None
            user.reset_code_expires_at = None
        else:
            # New claim path: create canonical student User and bind the existing seat atomically.
            try:
                user = create_student_user_for_seat(
                    seat,
                    username=username,
                    pin=pin,
                    passphrase=passphrase,
                )
            except IntegrityError:
                db.session.rollback()
                flash("That username is already taken. Please go back and choose another word.", "setup")
                return redirect(url_for('student.create_username'))
        if seat and user:
            seat.user_id = user.id
            seat.claimed_at = seat.claimed_at or now
        # Clear session onboarding keys
        session.pop('onboarding_seat_ref', None)
        session.pop('onboarding_user_ref', None)
        session.pop('generated_username', None)
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('student.setup_complete'))
    return render_template('student_pin_setup.html', username=username, form=form)


# -------------------- ADD NEW CLASS --------------------

@student_bp.route('/add-class', methods=['GET', 'POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def add_class():
    """
    Allow logged-in students to add a new class by entering a join code.

    Each join_code is an independent universe. Credentials entered here
    are matched against the *new* class's own unclaimed roster seat.
    """
    from app.models import ClassEconomy, Seat, IdentityProfile
    from app.utils.join_code import format_join_code
    from app.forms import StudentAddClassForm
    from app.hash_utils import hash_username_lookup

    context = resolve_canonical_context()
    if not context or getattr(context, "actor_role", None) != "student":
        return redirect(url_for('student.login'))
    student = db.session.get(Seat, context.seat_id)
    if not student:
        return redirect(url_for('student.login'))
    form = StudentAddClassForm()

    def _is_safe_url(target: str) -> bool:
        """
        Wrapper around the shared is_safe_url helper to make the sanitizer
        explicit within this view. Ensures that only same-origin or relative
        URLs are treated as safe redirect targets.
        """
        try:
            return bool(target) and is_safe_url(target)
        except Exception:
            # In case the helper raises for malformed URLs, treat as unsafe.
            return False

    def _get_return_target(default_endpoint: str = 'student.dashboard'):
        """
        Return the safest place to redirect back to after add-class attempts.

        Prioritize an explicit `next` value, fall back to referrer, then dashboard.

        Security: All redirect targets are validated with _is_safe_url() and
        additionally restricted to internal, relative URLs (no scheme or host)
        to prevent open redirect vulnerabilities.
        """
        def _normalize_and_validate_internal_target(raw_target: str) -> str | None:
            """
            Ensure the target is an internal relative URL:
            - strip backslashes, which some browsers treat like slashes
            - disallow any scheme or netloc
            Returns the cleaned path if valid, otherwise None.
            """
            if not raw_target:
                return None
            # Normalize backslashes to reduce browser inconsistencies
            cleaned = raw_target.replace('\\', '')
            parsed = urlparse(cleaned)
            # Require relative URL: no scheme and no netloc
            if parsed.scheme or parsed.netloc:
                return None
            return cleaned

        # 1) Explicit next parameter (form or query string)
        next_url = request.form.get('next') or request.args.get('next')
        if next_url and _is_safe_url(next_url):
            internal_next = _normalize_and_validate_internal_target(next_url)
            if internal_next:
                return internal_next

        # 2) Referrer header, after validation
        ref_url = request.referrer
        if ref_url and _is_safe_url(ref_url):
            internal_ref = _normalize_and_validate_internal_target(ref_url)
            if internal_ref:
                return internal_ref

        # 3) Safe fallback: always use internal route
        return url_for(default_endpoint)

    if form.validate_on_submit():
        display_join_code = format_join_code(form.join_code.data)
        first_name = (form.first_name.data or "").strip()
        last_name = form.last_name.data.strip()
        dedupe_code = (form.dedupe_code.data or "").strip().upper()

        # Resolve class context
        class_row = ClassEconomy.query.filter_by(join_code=display_join_code).first()
        if not class_row:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "danger")
            return redirect(_get_return_target())

        class_id = class_row.class_id

        # Find all unclaimed seats with this class_id
        unclaimed_seats = (
            Seat.query
            .filter(
                Seat.class_id == class_id,
                Seat.claimed_at.is_(None)
            )
            .all()
        )

        if not unclaimed_seats:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "danger")
            return redirect(_get_return_target())

        claim_first_name_hash = hash_username_lookup(first_name.lower())
        claim_last_name_hash = hash_username_lookup(last_name.lower())

        matched_seats = []
        for seat in unclaimed_seats:
            if seat.claim_first_name_hash == claim_first_name_hash and seat.claim_last_name_hash == claim_last_name_hash:
                matched_seats.append(seat)

        if not matched_seats:
            flash("No matching seat found. Please verify your join code and credentials with your teacher.", "danger")
            return redirect(_get_return_target())

        matched_seat = None
        if len(matched_seats) == 1:
            matched_seat = matched_seats[0]
        else:
            if not dedupe_code:
                flash(
                    "Multiple students in this class share that name. Enter your deduplication code from your teacher.",
                    "danger",
                )
                return redirect(_get_return_target())
            dedupe_matches = [
                seat
                for seat in matched_seats
                if (seat.dedupe_code == dedupe_code)
            ]
            if len(dedupe_matches) != 1:
                flash("Invalid deduplication code. Check with your teacher.", "danger")
                return redirect(_get_return_target())
            matched_seat = dedupe_matches[0]

        current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        new_block_check = matched_seat.class_economy.section.strip().upper() if matched_seat.class_economy and matched_seat.class_economy.section else ""
        if new_block_check in current_blocks:
            flash(f"You are already enrolled in Block {new_block_check}.", "warning")
            return redirect(_get_return_target())

        # Bind this new seat to the authenticated user (student already has a User row).
        matched_seat.user_id = student.user_id
        matched_seat.claimed_at = utc_now()
        # Update student's block to include the new block if not already there
        current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        new_block = matched_seat.class_economy.section.strip().upper() if matched_seat.class_economy and matched_seat.class_economy.section else ""

        if new_block not in current_blocks:
            current_blocks.append(new_block)
            student.block = ','.join(sorted(current_blocks))

        try:
            flash(f"Successfully added to Block {new_block}! You can now access this class from your dashboard.", "success")
            return redirect(_get_return_target())
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding class for seat {student.id}: {str(e)}")
            flash("An error occurred while adding the class. Please try again or contact your teacher.", "danger")
            return redirect(_get_return_target())

    return render_template('student_add_class.html', form=form)


# -------------------- STUDENT DASHBOARD --------------------

@student_bp.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard with balance, attendance, transactions, and quick actions."""
    context = resolve_canonical_context()
    if not context:
        raise AccessScopeDenied(reason_code="no_class_scope", message="Please select a class to continue.")
    student = db.session.get(Seat, context.seat_id)

    try:
        scope = resolve_scope(actor=student, selected_class_id=None)
        if context and scope.class_id != context.class_id:
            raise AccessScopeDenied(reason_code="foreign_class_scope", message="Please switch to the selected class.")
        access_policy_service.assert_can_view_dashboard(scope)
    except ContextResolutionError:
        raise AccessScopeDenied(reason_code="no_class_scope", message="Please select a class to continue.")
    except AccessScopeDenied as exc:
        flash(exc.message, "error")
        return redirect(url_for("student.select_class_context"))
    except access_policy_service.AccessPolicyDenied as exc:
        flash(exc.message, "error")
        return redirect(url_for('student.login'))

    join_code = scope.join_code
    current_block = (
        (getattr(scope, "section", None) or "")
        or (getattr(scope, "block", None) or "")
    ).strip()
    if not scope.class_id:
        flash("Class context unavailable. Please select a class and retry.", "error")
        return redirect(url_for("student.select_class_context"))
    if not scope.seat_id:
        flash("Seat context unavailable. Please select a class and retry.", "error")
        return redirect(url_for("student.select_class_context"))

    # Canonical ledger scope: seat_id + class_id.
    transactions = Transaction.query.filter_by(
        seat_id=scope.seat_id,
        class_id=scope.class_id,
    ).order_by(Transaction.timestamp.desc()).all()

    # Canonical store purchases scoped to the active seat/class.
    student_items = (
        StorePurchase.query
        .filter(
            StorePurchase.class_id == scope.class_id,
            StorePurchase.seat_id == scope.seat_id,
            StorePurchase.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        )
        .order_by(StorePurchase.purchased_at.desc())
        .all()
    )

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    checking_balance, savings_balance = get_available_balances(scope.seat_id, scope.class_id)
    # Calculate forecast interest using Decimal
    forecast_interest = _quantize_currency(savings_balance * Decimal('0.045') / Decimal('12'))

    # FIX: Only show tap in/out status for CURRENT class, not all classes
    # Get status for only the current block (not all blocks)
    period_states = get_all_block_statuses(student, class_id=scope.class_id)
    # Filter to only current class block
    current_block_key = current_block.upper() if current_block else ""
    period_states = {current_block_key: period_states.get(current_block_key, {})} if current_block_key else {}
    student_blocks = [current_block_key] if current_block_key else []  # Only current block

    # Convert Decimal values to float for JSON serialization
    for state in period_states.values():
        if 'projected_pay' in state and state['projected_pay'] is not None:
            state['projected_pay'] = float(state['projected_pay'])

    period_states_json = json.dumps(period_states, separators=(',', ':'))

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: (state.get("projected_pay") or 0)
        for blk, state in period_states.items()
    }

    # Compute total unpaid seconds and format as HH:MM:SS for display
    total_unpaid_seconds = sum(unpaid_seconds_per_block.values())
    hours, remainder = divmod(total_unpaid_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    total_unpaid_elapsed = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    student_name = (student.identity_profile.full_name if student.identity_profile else str(student.id))

    # Compute most recent deposit and insurance paid flag
    recent_deposit = student.recent_deposits[0] if student.recent_deposits else None

    # Track seen deposits in session to show notification only once
    if 'seen_deposit_ids' not in session:
        session['seen_deposit_ids'] = []

    # Only show deposit if it hasn't been seen yet
    if recent_deposit and recent_deposit.id not in session['seen_deposit_ids']:
        # Mark as seen
        session['seen_deposit_ids'].append(recent_deposit.id)
        session.modified = True
        # Keep only last 10 seen deposit IDs to prevent session bloat
        session['seen_deposit_ids'] = session['seen_deposit_ids'][-10:]
    else:
        # Don't show if already seen
        recent_deposit = None

    # Get student's active insurance policies (scoped to current class)
    context = {
        'join_code': scope.join_code,
        'user_id': scope.user_id,
        'class_id': scope.class_id,
        'block': scope.block,
        'seat_id': scope.seat_id,
    }
    class_id = scope.class_id
    active_insurance = None

    rent_status = None
    rent_settings = get_rent_settings_for_context(context)
    if rent_settings and student.is_rent_enabled:
        now = utc_now()
        timeline = _calculate_rent_timeline(rent_settings, now)
        due_date = timeline['due_date']
        grace_end_date = timeline['grace_end_date']
        coverage_due_date = timeline['coverage_due_date']
        upcoming_due_date = timeline['upcoming_due_date']
        preview_start_date = timeline['preview_start_date']
        rent_is_active = timeline['rent_is_active']
        is_preview_period = timeline['is_preview_period_candidate']

        rent_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]

        # Calculate coverage period for pre-paid system
        if is_preview_period:
            coverage_month = upcoming_due_date.month
            coverage_year = upcoming_due_date.year
            grace_end_date_for_status = upcoming_due_date + timedelta(days=rent_settings.grace_period_days)
        else:
            coverage_month = coverage_due_date.month if coverage_due_date else upcoming_due_date.month
            coverage_year = coverage_due_date.year if coverage_due_date else upcoming_due_date.year
            grace_end_date_for_status = (coverage_due_date + timedelta(days=rent_settings.grace_period_days)) if coverage_due_date else grace_end_date

        from app.services.obligations_service import get_paid_rent_assessments_for_cycle
        seat_ids = [scope.seat_id]
        all_paid = True
        for period in rent_blocks:
            payments = get_paid_rent_assessments_for_cycle(
                class_id,
                coverage_month,
                coverage_year,
                seat_ids=seat_ids,
            )
            payments = [payment for payment in payments if payment.satisfaction is not None]

            total_paid = sum((p.satisfaction.amount_paid for p in payments), Decimal('0.00'))
            paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
            late_fee = Decimal('0.00')
            if rent_is_active and now > grace_end_date_for_status and paid_by_grace < rent_settings.rent_amount:
                late_fee = rent_settings.late_fee
            total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
            is_paid = total_paid >= total_due if rent_is_active else False

            if rent_is_active and not is_paid:
                all_paid = False
                break

        rent_status = {
            'is_active': rent_is_active,
            'is_paid': all_paid if rent_is_active else False,
            'is_preview': is_preview_period
        }

    tz = get_timezone()
    local_now = utc_now().astimezone(tz)
    # --- DASHBOARD DEBUG LOGGING ---
    current_app.logger.info(f"DASHBOARD DEBUG: Student {student.id} - Block states:")
    for blk, blk_state in period_states.items():
        active = blk_state.get("active")
        done = blk_state.get("done")
        seconds = blk_state.get("duration")
        current_app.logger.info(f"Block {blk} => DB Active={active}, Done={done}, Seconds (today)={seconds}, Total Unpaid Seconds={unpaid_seconds_per_block.get(blk, 0)}")


    # --- Calculate remaining session time for frontend timer ---
    login_time = datetime.fromisoformat(session['login_time'])
    expiry_time = login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    session_remaining_seconds = max(0, int((expiry_time - utc_now()).total_seconds()))

    # --- Get feature settings for this student ---
    feature_settings = get_feature_settings_for_student()

    # --- Check for pending recovery request ---
    pending_recovery_code = get_pending_recovery_code_for_seat(student.id, utc_now())

    # --- Calculate weekly/monthly analytics ---
    from app.models import AttendanceSession as _AttSession
    now_utc = utc_now()
    if class_id:
        class_now_utc = get_class_now(class_id, reference_time_utc=now_utc).astimezone(timezone.utc)
        week_start, week_end = get_class_week_range_utc(class_id, reference_time_utc=class_now_utc)
        month_start = get_class_month_start_utc(class_id, reference_time=class_now_utc)
    else:
        week_start, week_end = get_class_week_range_utc(
            context.class_id,
            reference_time_utc=now_utc,
        ) if context.class_id else (now_utc, now_utc + timedelta(days=7))
        month_start = get_class_month_start_utc(
            context.class_id,
            reference_time=now_utc,
        ) if context.class_id else now_utc

    effective_class_id = class_id or context.class_id
    sessions_this_week = _AttSession.query.filter(
        _AttSession.seat_id == student.id,
        _AttSession.class_id == effective_class_id,
        _AttSession.started_at >= week_start,
        _AttSession.started_at < week_end,
        _AttSession.is_deleted.is_(False),
    ).all()

    unique_days_tapped = len(
        {ensure_utc(s.started_at).astimezone(tz).date() for s in sessions_this_week}
    )

    total_minutes_this_week = 0
    for s in sessions_this_week:
        if s.duration_seconds is not None:
            total_minutes_this_week += s.duration_seconds / 60
        elif s.ended_at is None:
            total_minutes_this_week += (now_utc - ensure_utc(s.started_at)).total_seconds() / 60

    def _occurred_after(ts, start):
        ts_utc = ensure_utc(ts)
        return ts_utc is not None and ts_utc >= start

    # Earnings this week/month
    # FIX: Add null check to prevent decimal.InvalidOperation on corrupted data
    earnings_this_week = sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount > Decimal('0') and _occurred_after(tx.timestamp, week_start) and not tx.is_void),
        Decimal('0.00')
    )
    earnings_this_month = sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount > Decimal('0') and _occurred_after(tx.timestamp, month_start) and not tx.is_void),
        Decimal('0.00')
    )

    # Spending this week/month
    # FIX: Add null check to prevent decimal.InvalidOperation on corrupted data
    spending_this_week = abs(sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount < Decimal('0') and _occurred_after(tx.timestamp, week_start) and not tx.is_void),
        Decimal('0.00')
    ))
    spending_this_month = abs(sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount < Decimal('0') and _occurred_after(tx.timestamp, month_start) and not tx.is_void),
        Decimal('0.00')
    ))

    # Get active announcements for this student
    # Include: class-specific, system-wide, all students, and teacher's all classes
    from app.models import Announcement

    user_id = scope.user_id
    announcements = Announcement.query.filter(
        Announcement.is_active.is_(True),
        or_(
            Announcement.expires_at.is_(None),
            Announcement.expires_at > utc_now()
        ),
        or_(
            # Class-specific announcements
            Announcement.class_id == scope.class_id,
            # System-wide announcements
            Announcement.audience_type == 'system_wide',
            # All students announcements
            Announcement.audience_type == 'all_students',
            # Teacher's all classes announcements
            (Announcement.audience_type == 'teacher_all_classes') & (Announcement.target_teacher_id == scope.user_id)
        )
    ).order_by(Announcement.created_at.desc()).all()

    return render_template(
        'student_dashboard.html',
        student=student,
        session_remaining_seconds=session_remaining_seconds,
        student_blocks=student_blocks,
        period_states=period_states,
        period_states_json=period_states_json,
        checking_transactions=checking_transactions,
        savings_transactions=savings_transactions,
        student_items=student_items,
        recent_transactions=transactions[:5],  # Most recent 5 transactions
        now=local_now,
        forecast_interest=float(forecast_interest),
        recent_deposit=recent_deposit,
        active_insurance=active_insurance,
        rent_status=rent_status,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block={blk: float(pay or 0) for blk, pay in projected_pay_per_block.items()},
        student_name=student_name,
        total_unpaid_elapsed=total_unpaid_elapsed,
        feature_settings=feature_settings,
        # FIX: Pass scoped balances to template instead of using unscoped properties
        checking_balance=float(checking_balance),
        savings_balance=float(savings_balance),
        # user_id is resolved from class context.
        pending_recovery_code=pending_recovery_code,
        # Weekly/monthly analytics
        unique_days_tapped=unique_days_tapped,
        total_minutes_this_week=int(total_minutes_this_week),
        earnings_this_week=float(round(earnings_this_week, 2)),
        earnings_this_month=float(round(earnings_this_month, 2)),
        spending_this_week=float(round(spending_this_week, 2)),
        spending_this_month=float(round(spending_this_month, 2)),
        announcements=announcements,
        current_class_id=class_id,
        scoped_total_earnings=_get_total_earnings_for_seat(student.id, class_id=class_id),
    )


@student_bp.route('/payroll')
@login_required
def payroll():
    """Student payroll page with attendance record, productivity stats, and projected pay."""
    # Check if payroll feature is enabled
    if not is_feature_enabled('payroll'):
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = _get_canonical_student_from_context()

    context = resolve_canonical_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))
    if not class_id:
        flash("Class context unavailable. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))
    effective_class_id = class_id or context.class_id

    current_block = seat.class_economy.section.upper() if seat and seat.class_economy and seat.class_economy.section else ""
    join_code = get_display_join_code(context.class_id)
    period_states = get_all_block_statuses(student, class_id=class_id)

    # Scope dashboard data to the selected class context only
    period_states = {current_block: period_states.get(current_block, {})}
    student_blocks = [current_block]

    # Determine the pay rate for the current block (per minute)
    pay_rate_per_second = get_pay_rate_for_block(
        current_block,
        class_id=class_id,
    )
    pay_rate_per_minute = round(pay_rate_per_second * 60, 2)

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: round((state.get("projected_pay") or 0), 2)
        for blk, state in period_states.items()
    }

    from app.models import AttendanceSession as _AttSession

    att_query = _AttSession.query.filter(
        _AttSession.seat_id == student.id,
        _AttSession.class_id == effective_class_id,
        _AttSession.is_deleted.is_(False),
    )
    recent_sessions = att_query.order_by(_AttSession.started_at.desc()).limit(20).all()
    all_tap_events = recent_sessions
    tap_events_by_block = {}
    for sess in recent_sessions:
        sess.action = 'start_work' if sess.ended_at is None else 'stop_work'
        if sess.period not in tap_events_by_block:
            tap_events_by_block[sess.period] = []
        tap_events_by_block[sess.period].append(sess)

    return render_template(
        'student_payroll.html',
        student=student,
        student_blocks=student_blocks,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        period_states=period_states,
        all_tap_events=all_tap_events,
        tap_events_by_block=tap_events_by_block,
        pay_rate_per_minute=pay_rate_per_minute,
        pay_rate_table=[
            ("1 minute", pay_rate_per_minute),
            ("10 minutes", round(pay_rate_per_minute * 10, 2)),
            ("30 minutes", round(pay_rate_per_minute * 30, 2)),
            ("1 hour", round(pay_rate_per_minute * 60, 2)),
            ("2 hours", round(pay_rate_per_minute * 120, 2)),
            ("4 hours", round(pay_rate_per_minute * 240, 2)),
        ],
        now=utc_now(),
        scoped_total_earnings=_get_total_earnings_for_seat(student.id, class_id=effective_class_id),
    )


# -------------------- FINANCIAL TRANSACTIONS --------------------

@student_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer funds between checking and savings accounts."""
    # Check if banking feature is enabled
    if not is_feature_enabled('banking'):
        abort(404)

    student = _get_canonical_student_from_context()

    # CRITICAL FIX v2: Get full class context (class_id, seat_id, block)
    context = resolve_canonical_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        
        # Enforce single-use transfer token to prevent form replay
        submitted_token = request.form.get("transfer_token")
        expected_token = session.pop('transfer_token', None)
        if not expected_token or submitted_token != expected_token:
            message = "This transfer has already been processed or the session is invalid. Please refresh the page and try again."
            if is_json:
                return jsonify(status="error", message=message), 400
            flash(message, "transfer_error")
            return redirect(url_for("student.transfer"))

        passphrase = request.form.get("passphrase")
        user = get_current_user()
        if not user or not check_password_hash(user.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student.transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        # Convert form input to Decimal for precise financial calculation
        from app.models import _quantize_currency
        amount = _quantize_currency(request.form.get('amount'))

        # CRITICAL FIX: Calculate balances using canonical seat/class scoping
        checking_balance, savings_balance = calculate_scoped_balances(context.seat_id, context.class_id)
        banking_settings = get_banking_settings_for_context(context)

        if from_account == to_account:
            if is_json:
                return jsonify(status="error", message="Cannot transfer to the same account."), 400
            flash("Cannot transfer to the same account.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif amount <= Decimal('0'):
            if is_json:
                return jsonify(status="error", message="Amount must be greater than 0."), 400
            flash("Amount must be greater than 0.", "transfer_error")
            return redirect(url_for("student.transfer"))
        class_id = context.class_id
        seat_id = context.seat_id
        if not seat_id:
            if is_json:
                return jsonify(status="error", message="No seat assigned in this class."), 400
            flash("No seat assigned in this class.", "transfer_error")
            return redirect(url_for("student.transfer"))

        if from_account == 'checking' and amount > checking_balance:
            intended_plan = build_intended_ledger_plan(
                seat_id=seat_id,
                class_id=class_id,
                user_id=student.user_id,
                debit_amount=amount,
                description=f"Transfer to {to_account}",
                source_account=from_account,
                target_account=to_account,
            )
            resolved_plan = resolve_intended_ledger_plan(
                plan=intended_plan,
                banking_settings=banking_settings,
                idempotency_key=f"student-transfer:{seat_id}:{class_id}:{amount}:{from_account}:{to_account}:resolve",
                force_overdraft_fee=True,
                allow_recovery_transfer=False,
            )
            apply_resolved_ledger_plan(
                resolved_plan=resolved_plan,
                banking_settings=banking_settings,
                idempotency_key=f"student-transfer:{seat_id}:{class_id}:{amount}:{from_account}:{to_account}",
            )

            message = "Insufficient checking funds."
            if resolved_plan.overdraft_fee_amount > 0:
                message += f" Overdraft fee of ${resolved_plan.overdraft_fee_amount:.2f} charged."
            if is_json:
                return jsonify(status="error", message=message), 400
            flash(message, "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'savings' and amount > savings_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient savings funds."), 400
            flash("Insufficient savings funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        else:
            try:
                execute_account_transfer(
                    seat_id=seat_id,
                    class_id=class_id,
                    # user_id is resolved from class context.
                    amount=amount,
                    from_account=from_account,
                    to_account=to_account,
                )
                current_app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for seat {seat_id}"
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(
                    f"Transfer failed for student {student.id}: {e}", exc_info=True
                )
                if is_json:
                    return jsonify(status="error", message="Transfer failed."), 500
                flash("Transfer failed due to a database error.", "transfer_error")
                return redirect(url_for("student.transfer"))
            if is_json:
                return jsonify(status="success", message="Transfer completed successfully!")
            flash("Transfer completed successfully!", "transfer_success")
            return redirect(url_for('student.dashboard'))

    # CRITICAL FIX v2: Get transactions for display - strict class_id/seat_id scoping.
    transactions = Transaction.query.filter(
        Transaction.seat_id == context.seat_id,
        Transaction.class_id == context.class_id,
        Transaction.is_void == False,
    ).order_by(Transaction.timestamp.desc()).all()
    checking_transactions = [t for t in transactions if t.account_type == 'checking']
    savings_transactions = [t for t in transactions if t.account_type == 'savings']

    # Get banking settings for interest rate display
    settings = get_banking_settings_for_context(context)
    # Convert APY to decimal rate (e.g., 5% = 0.05)
    from app.models import _quantize_currency
    annual_rate = _quantize_currency(settings.savings_apy / Decimal('100')) if settings and settings.savings_apy is not None else Decimal('0.045')
    calculation_type = settings.interest_calculation_type if settings else 'simple'
    compound_frequency = settings.compound_frequency if settings else 'monthly'

    # Calculate forecast interest based on settings
    # CRITICAL FIX v3: Calculate BOTH checking and savings balances using canonical seat/class scoping
    checking_balance, savings_balance = calculate_scoped_balances(context.seat_id, context.class_id)

    if calculation_type == 'compound':
        if compound_frequency == 'daily':
            periods_per_month = Decimal('30')
            rate_per_period = annual_rate / Decimal('365')
            # For Decimal exponentiation, convert to float, calculate, then back to Decimal
            forecast_interest = _quantize_currency(savings_balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        elif compound_frequency == 'weekly':
            periods_per_month = Decimal('4.33')
            rate_per_period = annual_rate / Decimal('52')
            forecast_interest = _quantize_currency(savings_balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        else:  # monthly
            forecast_interest = _quantize_currency(savings_balance * (annual_rate / Decimal('12')))
    else:
        # Simple interest: calculate only on principal (excluding interest earnings)
        principal = _quantize_currency(sum((tx.amount for tx in savings_transactions if tx.type != 'Interest' and 'Interest' not in (tx.description or '')), Decimal('0')))
        forecast_interest = _quantize_currency(principal * (annual_rate / Decimal('12')))

    # Calculate 12-month savings projection for graph
    projection_months = []
    projection_balances = []
    current_balance = savings_balance

    for month in range(13):  # 0 to 12 months
        projection_months.append(month)
        # Convert to float for JSON serialization in template
        projection_balances.append(float(current_balance))

        if month < 12:  # Don't calculate interest for the last point
            if calculation_type == 'compound':
                if compound_frequency == 'daily':
                    periods = Decimal('30')
                    rate = annual_rate / Decimal('365')
                    interest = _quantize_currency(current_balance * ((Decimal('1') + rate) ** periods - Decimal('1')))
                elif compound_frequency == 'weekly':
                    periods = Decimal('4.33')
                    rate = annual_rate / Decimal('52')
                    interest = _quantize_currency(current_balance * ((Decimal('1') + rate) ** periods - Decimal('1')))
                else:  # monthly
                    interest = _quantize_currency(current_balance * (annual_rate / Decimal('12')))
                current_balance = _quantize_currency(current_balance + interest)
            else:  # simple interest
                interest = _quantize_currency(savings_balance * (annual_rate / Decimal('12')))  # Simple interest on original principal
                current_balance = _quantize_currency(current_balance + interest)

    import secrets
    transfer_token = secrets.token_hex(16)
    session['transfer_token'] = transfer_token

    return render_template('student_transfer.html',
                         student=student,
                         transactions=transactions,
                         checking_transactions=checking_transactions,
                         savings_transactions=savings_transactions,
                         checking_balance=checking_balance,
                         savings_balance=savings_balance,
                         forecast_interest=forecast_interest,
        scoped_total_earnings=_get_total_earnings_for_seat(student.id, class_id=context.class_id),
                         settings=settings,
                         calculation_type=calculation_type,
                         compound_frequency=compound_frequency,
                         projection_months=projection_months,
                         projection_balances=projection_balances,
                         transfer_token=transfer_token)


def apply_savings_interest(student, annual_rate=Decimal('0.045')):
    """Compatibility command wrapper that forwards savings-interest writes into the ledger service."""
    context = resolve_canonical_context()
    if not context:
        return None
    seat = get_current_seat()
    if not seat:
        return None
    interest_tx = post_monthly_savings_interest(seat, annual_rate=annual_rate)
    return interest_tx


# -------------------- INSURANCE --------------------

@student_bp.route('/insurance', endpoint='student_insurance')
@login_required
def insurance_marketplace():
    """Insurance marketplace - browse and manage policies."""


    abort(404)


@student_bp.route('/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def purchase_insurance(policy_id):
    """Purchase insurance policy."""
    abort(404)


@student_bp.route('/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-OBL-001")
def cancel_insurance(enrollment_id):
    """Cancel insurance policy."""
    abort(404)


@student_bp.route('/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def file_claim(policy_id):
    """File insurance claim."""
    abort(404)


@student_bp.route('/insurance/policy/<int:enrollment_id>')
@login_required
def view_policy(enrollment_id):
    """View policy details and claims history."""
    abort(404)

    return render_template('student_view_policy.html',
                          student=student,
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          claims=claims,
                          now=now_utc)


# -------------------- SHOPPING --------------------

@student_bp.route('/shop')
@login_required
def shop():
    """Student shop - browse and purchase items."""
    # Check if store feature is enabled
    if not is_feature_enabled('store'):
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    context = resolve_canonical_context()

    # CRITICAL FIX v2: Get full class context
    context = resolve_canonical_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    join_code = get_display_join_code(context.class_id)
    if not class_id:
        class_id = context.class_id

    now = utc_now()
    now_db = normalize_for_db(now)
    items_query = StoreItem.query.filter(
        StoreItem.class_id == class_id,
        StoreItem.is_active == True,
        or_(StoreItem.auto_delist_date == None, StoreItem.auto_delist_date > now_db),
    )
    items = [
        item for item in items_query.order_by(StoreItem.name).all()
        if store_service.is_item_visible_to_seat(item.id, seat.id)
    ]

    student_items = (
        StorePurchase.query
        .filter(
            StorePurchase.class_id == class_id,
            StorePurchase.seat_id == seat.id,
            StorePurchase.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        )
        .order_by(StorePurchase.purchased_at.desc())
        .all()
    )

    # Check if student has paid rent this month using canonical rent settings only.
    from app.models import RentSettings
    has_paid_rent = False
    per_period_rent_item_ids = set()
    rent_item_types_by_store_id = {}
    per_use_limit_by_store_id = {}

    # v2: scope is class_id + seat_id from canonical context (INV-ARC-019)
    if class_id and context:
        seat_id = context.seat_id
        rent_settings = get_rent_settings_for_context(context)
        if rent_settings:
            now = utc_now()

            # Calculate current coverage period (pre-paid system)
            coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)

            
            if coverage_due_date and seat_id:
                has_paid_rent = _is_student_coverage_period_paid(
                    rent_settings,
                    seat_id,
                    class_id,
                    coverage_due_date,
                    include_waivers=False,
                )

            # Read store-linked rent items from canonical rent settings so
            # mid-cycle teacher edits don't change what students see.
            from app.services.store_service import get_frozen_store_linked_items, get_frozen_privilege_items
            rent_settings = get_rent_settings_for_context(context)
            rent_item_types_by_store_id = {}
            per_use_limit_by_store_id = {}
            per_period_rent_item_ids = set()

            if rent_settings:
                frozen_store_items = get_frozen_store_linked_items(rent_settings)
                for frozen_item in frozen_store_items:
                    sid = frozen_item['store_item_id']
                    effective_type = frozen_item.get('rent_item_type', 'privilege')
                    # Some rows can still carry privilege as the
                    # default type while semantically behaving per-use via duration.
                    if effective_type == 'privilege' and frozen_item.get('purchase_duration') == 'per_use':
                        effective_type = 'per_use'
                    rent_item_types_by_store_id.setdefault(sid, set()).add(effective_type)

                    if effective_type == 'per_use':
                        use_limit = frozen_item.get('use_limit')
                        per_use_limit_by_store_id[sid] = use_limit if use_limit else -1

                # Privilege items get the "Included in your rent!" badge
                frozen_privileges = get_frozen_privilege_items(rent_settings)
                per_period_rent_item_ids = {
                    fp['store_item_id'] for fp in frozen_privileges if fp.get('store_item_id')
                }

    # Build free uses remaining map for rent-linked per-use items
    rent_free_uses = {}  # {store_item_id: uses_remaining or -1 for unlimited}
    if seat:
        now_utc = utc_now()
        rent_linked_items_query = StorePurchase.query.filter(
            StorePurchase.seat_id == seat.id,
            StorePurchase.uses_remaining != None,
            db.or_(
                StorePurchase.uses_remaining > 0,
                StorePurchase.uses_remaining == -1
            ),
            db.or_(
                StorePurchase.expiry_date.is_(None),
                StorePurchase.expiry_date > now_utc
            )
        )
        rent_linked_items = rent_linked_items_query.all()
        for si in rent_linked_items:
            if si.store_item_id:
                rent_free_uses[si.store_item_id] = si.uses_remaining

        # Backfill UI for paid-rent students who are entitled to per-use perks
        # but are missing grant rows (edge-state). Do not override items
        # that already have an explicit grant record (including exhausted = 0).
        if has_paid_rent and per_use_limit_by_store_id:
            existing_per_use_rows = StorePurchase.query.filter(
                StorePurchase.seat_id == seat.id,
                StorePurchase.store_item_id.in_(list(per_use_limit_by_store_id.keys())),
                StorePurchase.uses_remaining.isnot(None),
                db.or_(
                    StorePurchase.expiry_date.is_(None),
                    StorePurchase.expiry_date > now_utc
                )
            ).all()
            existing_per_use_ids = {row.store_item_id for row in existing_per_use_rows if row.store_item_id}

            for store_item_id, granted_uses in per_use_limit_by_store_id.items():
                if store_item_id not in existing_per_use_ids and store_item_id not in rent_free_uses:
                    rent_free_uses[store_item_id] = granted_uses

    # Calculate class size for collective goals (count unique students in this class)
    from app.models import Seat
    class_size = 0
    if class_id:
        class_size = (
            db.session.query(db.func.count(db.func.distinct(Seat.id)))
            .filter(
                Seat.class_id == class_id,
                Seat.claimed_at.isnot(None),
                Seat.role == "student",  # Exclude teacher account from class size
            )
            .scalar() or 0
        )

    collective_progress = {}
    collective_items = [item for item in items if item.item_type == 'collective']
    collective_item_ids = [item.id for item in collective_items]
    if collective_item_ids and class_id:
        progress_rows = (
            db.session.query(
                StorePurchase.store_item_id,
                db.func.count(db.distinct(StorePurchase.seat_id)).label('student_count'),
            )
            .join(Seat, StorePurchase.seat_id == Seat.id)
            .join(StoreItem, StorePurchase.store_item_id == StoreItem.id)
            .filter(
                StorePurchase.store_item_id.in_(collective_item_ids),
                StorePurchase.class_id == class_id,
                StorePurchase.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
                Seat.role == "student",  # Exclude teacher purchases from progress
                StorePurchase.collective_goal_instance_code == StoreItem.collective_goal_instance_code,
            )
            .group_by(StorePurchase.store_item_id)
            .all()
        )
        progress_counts = {row.store_item_id: int(row.student_count or 0) for row in progress_rows}

        for item in collective_items:
            if item.collective_goal_type == 'whole_class':
                target = class_size
            elif item.collective_goal_type == 'fixed':
                target = int(item.collective_goal_target or 0)
            else:
                target = 0
            count = progress_counts.get(item.id, 0)
            collective_progress[item.id] = {
                'count': count,
                'target': target,
                'remaining': max(0, target - count),
                'percent': min(100, int((count / target) * 100)) if target > 0 else 0,
                'is_complete': bool(target > 0 and count >= target),
            }

    current_block = seat.class_economy.section.strip().upper() if seat and seat.class_economy and seat.class_economy.section else ""
    return render_template('student_shop.html', student=seat, items=items, student_items=student_items,
                         has_paid_rent=has_paid_rent, per_period_rent_item_ids=per_period_rent_item_ids,
                         rent_item_types_by_store_id=rent_item_types_by_store_id,
                         rent_free_uses=rent_free_uses,
                         class_size=class_size, current_block=current_block,
                         collective_progress=collective_progress)


# -------------------- RENT --------------------


def _get_rent_timezone(class_id: str):
    """
    Return the class-authoritative timezone used for rent schedule semantics.

    Rent is a class-level evaluation and must use the class timezone
    established on ClassEconomy. If the class cannot be resolved, fail closed.
    """
    if not class_id:
        raise ValueError("Rent timezone resolution requires class_id")
    return get_timezone(get_class_timezone(class_id))


def _calculate_rent_deadlines(settings, reference_date=None):
    """Return the due date and grace end date for the active month."""
    reference_date = ensure_utc(reference_date) if reference_date else utc_now()
    class_id = getattr(settings, "class_id", None)
    teacher_tz = _get_rent_timezone(class_id)
    reference_local = reference_date.astimezone(teacher_tz)

    def _local_due_to_utc(
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
    ) -> datetime:
        local_due = teacher_tz.localize(datetime(year, month, day, hour, minute, second))
        return local_due.astimezone(timezone.utc)

    # If first_rent_due_date is set and we haven't reached it yet, return it
    if settings.first_rent_due_date:
        first_due = ensure_utc(settings.first_rent_due_date)
        first_due_local = first_due.astimezone(teacher_tz) if first_due else None
        if (
            first_due
            and first_due.hour == 0
            and first_due.minute == 0
            and first_due.second == 0
            and first_due.microsecond == 0
        ):
            # Preserve day-only anchors that were stored as UTC midnight.
            first_due_local = teacher_tz.localize(datetime(first_due.year, first_due.month, first_due.day, 0, 0, 0))
            first_due = first_due_local.astimezone(timezone.utc)
        # If we're before the first due date, return the first due date
        if first_due_local and reference_local < first_due_local:
            grace_end_date = first_due + timedelta(days=settings.grace_period_days)
            return first_due, grace_end_date

        # Calculate due date based on frequency from first_rent_due_date
        if settings.frequency_type == 'monthly':
            # Calculate how many months have passed since first due date
            months_diff = (reference_local.year - first_due_local.year) * 12 + (reference_local.month - first_due_local.month)
            # Calculate the due date for the current period
            target_year = first_due_local.year + (first_due_local.month + months_diff - 1) // 12
            target_month = (first_due_local.month + months_diff - 1) % 12 + 1
            last_day_of_month = monthrange(target_year, target_month)[1]
            due_day = min(first_due_local.day, last_day_of_month)
            due_date = _local_due_to_utc(
                target_year,
                target_month,
                due_day,
                first_due_local.hour,
                first_due_local.minute,
                first_due_local.second,
            )
        else:
            # Calculate due date based on frequency
            freq_delta = None
            if settings.frequency_type == 'daily':
                freq_delta = timedelta(days=1)
            elif settings.frequency_type == 'weekly':
                freq_delta = timedelta(weeks=1)
            elif settings.frequency_type == 'custom':
                if settings.custom_frequency_unit == 'days':
                    freq_delta = timedelta(days=settings.custom_frequency_value)
                elif settings.custom_frequency_unit == 'weeks':
                    freq_delta = timedelta(weeks=settings.custom_frequency_value)
                elif settings.custom_frequency_unit == 'months':
                    # Custom monthly logic (Every X months)
                    # Calculate how many months have passed since first due date
                    months_diff = (reference_local.year - first_due_local.year) * 12 + (reference_local.month - first_due_local.month)

                    # Calculate the number of full periods passed
                    # We use integer division to find the start of the current cycle
                    periods = months_diff // settings.custom_frequency_value
                    total_months_add = periods * settings.custom_frequency_value

                    target_year = first_due_local.year + (first_due_local.month + total_months_add - 1) // 12
                    target_month = (first_due_local.month + total_months_add - 1) % 12 + 1

                    last_day_of_month = monthrange(target_year, target_month)[1]
                    due_day = min(first_due_local.day, last_day_of_month)
                    due_date = _local_due_to_utc(
                        target_year,
                        target_month,
                        due_day,
                        first_due_local.hour,
                        first_due_local.minute,
                        first_due_local.second,
                    )

            if freq_delta:
                # Calculate periods passed for fixed time deltas
                time_diff = reference_date - first_due
                periods = time_diff // freq_delta
                due_date = first_due + (periods * freq_delta)

            use_fallback = False
            if not freq_delta and settings.frequency_type != 'custom':
                # Fallback for unknown frequency types
                use_fallback = True
            elif settings.frequency_type == 'custom' and settings.custom_frequency_unit not in ['days', 'weeks', 'months']:
                 # Fallback for unknown custom units
                use_fallback = True

            if use_fallback:
                current_year = reference_local.year
                current_month = reference_local.month
                last_day_of_month = monthrange(current_year, current_month)[1]
                due_day = min(settings.due_day_of_month, last_day_of_month)
                due_date = _local_due_to_utc(current_year, current_month, due_day)

    else:
        # No first_rent_due_date set, use traditional monthly logic
        current_year = reference_local.year
        current_month = reference_local.month
        last_day_of_month = monthrange(current_year, current_month)[1]
        due_day = min(settings.due_day_of_month, last_day_of_month)
        due_date = _local_due_to_utc(current_year, current_month, due_day)

    grace_end_date = due_date + timedelta(days=settings.grace_period_days)
    return due_date, grace_end_date


def _get_rent_period_delta(settings):
    """Return a timedelta/relativedelta representing one rent period."""
    if settings.frequency_type == 'daily':
        return timedelta(days=1)
    if settings.frequency_type == 'weekly':
        return timedelta(weeks=1)
    if settings.frequency_type == 'monthly':
        return relativedelta(months=1)
    if settings.frequency_type == 'custom':
        unit = getattr(settings, 'custom_frequency_unit', None)
        value = getattr(settings, 'custom_frequency_value', None) or 1
        if unit == 'days':
            return timedelta(days=value)
        if unit == 'weeks':
            return timedelta(weeks=value)
        if unit == 'months':
            return relativedelta(months=value)
    # Fallback to monthly behavior
    return relativedelta(months=1)


def _add_rent_period(dt, delta):
    """Add a timedelta or relativedelta to dt."""
    return dt + delta


def _calculate_due_dates(settings, now):
    """Return the current and next due dates for rent-linked expiry calculations."""
    first_due = ensure_utc(settings.first_rent_due_date)
    if not first_due:
        return (None, None)

    delta = _get_rent_period_delta(settings)
    if now < first_due:
        return (first_due, _add_rent_period(first_due, delta))

    current_due = first_due
    next_due = _add_rent_period(first_due, delta)
    while next_due and next_due <= now:
        current_due = next_due
        next_due = _add_rent_period(next_due, delta)

    return (current_due, next_due)


def _calculate_upcoming_rent_due_date(settings, due_date, coverage_due_date):
    """
    Return the next due date students can preview/pay toward.

    For monthly schedules without first_rent_due_date, derive next due date using
    _calculate_rent_deadlines to preserve due_day_of_month clamping (e.g., 31st).
    """
    if not coverage_due_date:
        return due_date

    if settings.frequency_type == 'monthly' and not settings.first_rent_due_date:
        reference_date = coverage_due_date + relativedelta(months=1)
        next_due, _ = _calculate_rent_deadlines(settings, reference_date)
        return next_due

    period_delta = _get_rent_period_delta(settings)
    return _add_rent_period(coverage_due_date, period_delta)


def _calculate_rent_timeline(settings, now):
    """Compute due-date timeline and activation flags used by rent views/payments."""
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    upcoming_due_date = _calculate_upcoming_rent_due_date(settings, due_date, coverage_due_date)

    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = upcoming_due_date - timedelta(days=settings.bill_preview_days)

    rent_is_active = False
    is_preview_period_candidate = False
    if coverage_due_date and now >= coverage_due_date:
        rent_is_active = True
    if preview_start_date and now >= preview_start_date and now < upcoming_due_date:
        rent_is_active = True
        is_preview_period_candidate = True

    return {
        'due_date': due_date,
        'grace_end_date': grace_end_date,
        'coverage_due_date': coverage_due_date,
        'upcoming_due_date': upcoming_due_date,
        'preview_start_date': preview_start_date,
        'rent_is_active': rent_is_active,
        'is_preview_period_candidate': is_preview_period_candidate,
    }


def _total_paid_by_grace(assessments, grace_end_date):
    """Sum satisfaction amounts for assessments satisfied on or before the grace end date."""
    if not assessments or not grace_end_date:
        return Decimal('0.00')
    grace_end_date = ensure_utc(grace_end_date)
    return sum(
        (a.satisfaction.amount_paid for a in assessments
         if a.satisfaction and a.satisfaction.satisfied_at
         and ensure_utc(a.satisfaction.satisfied_at) <= grace_end_date),
        Decimal('0.00')
    )


def _get_locked_rent_amount_for_class_cycle(class_id, coverage_due_date):
    """Return the policy-defined rent amount for a class coverage cycle."""
    from app.services.obligations_service import get_cycle_rent_amount

    if not class_id or not coverage_due_date:
        return None
    return get_cycle_rent_amount(class_id, coverage_due_date.month, coverage_due_date.year)


def _get_effective_rent_amount_for_coverage_period(
    settings,
    assessments,
    coverage_due_date,
    class_id=None,
    locked_amount=None,
):
    """
    Return the effective base rent for the coverage period.

    If the class rate changed mid-cycle, lock to the first valid payer's base
    amount for that class. As a fallback, keep a student's earlier paid
    base amount when the setting update happened after their first payment.
    """
    current_amount = settings.rent_amount or Decimal('0.00')

    if locked_amount is None:
        locked_amount = _get_locked_rent_amount_for_class_cycle(class_id, coverage_due_date)
    if locked_amount is not None:
        return locked_amount

    if assessments:
        updated_at = getattr(settings, 'updated_at', None)
        if updated_at:
            satisfied_dates = [
                ensure_utc(a.satisfaction.satisfied_at)
                for a in assessments
                if a.satisfaction and a.satisfaction.satisfied_at
            ]
            if satisfied_dates:
                earliest = min(satisfied_dates)
                if ensure_utc(updated_at) > earliest:
                    base_paid = sum(
                        (a.satisfaction.amount_paid or Decimal('0.00'))
                        - (a.satisfaction.late_fee_charged or Decimal('0.00'))
                        for a in assessments if a.satisfaction
                    )
                    if base_paid > Decimal('0.00'):
                        return base_paid

    return current_amount


def _match_valid_rent_payments(payments, candidate_txns):
    """Match payments to non-void rent transactions using existing tolerance rules."""
    if not payments:
        return []
    txns_by_amount = {}
    for txn in candidate_txns:
        txns_by_amount.setdefault(txn.amount, []).append(txn)

    used_txn_ids = set()
    valid_payments = []
    for payment in payments:
        candidates = txns_by_amount.get(-payment.amount_paid, [])
        for txn in candidates:
            if txn.id in used_txn_ids or txn.is_void:
                continue
            if not txn.timestamp or not payment.payment_date:
                continue
            if abs((ensure_utc(txn.timestamp) - ensure_utc(payment.payment_date)).total_seconds()) > RENT_PAYMENT_MATCH_TOLERANCE_SECONDS:
                continue
            used_txn_ids.add(txn.id)
            valid_payments.append(payment)
            break

    return valid_payments


def _filter_valid_rent_payments(payments, student_id, class_id, seat_ids=None):
    """Return payments that have a matching, non-void rent transaction."""
    if not payments:
        return []

    payment_dates = [p.payment_date for p in payments if p.payment_date]
    if not payment_dates:
        return []

    min_payment_date = min(payment_dates)
    max_payment_date = max(payment_dates)
    window_start = min_payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)
    window_end = max_payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)

    payment_amounts = {-(p.amount_paid) for p in payments}

    txn_scope = transaction_scope_filter(Transaction, student_id, seat_ids or [])
    txn_query = Transaction.query.filter(
        txn_scope,
        Transaction.type == 'Rent Payment',
        Transaction.timestamp >= window_start,
        Transaction.timestamp <= window_end,
        Transaction.amount.in_(payment_amounts)
    )
    if not class_id:
        return []
    txn_query = txn_query.filter(Transaction.class_id == class_id)

    candidate_txns = txn_query.all()
    return _match_valid_rent_payments(payments, candidate_txns)


def _build_rent_coverage_context(
    settings,
    *,
    class_id,
    seat_ids,
    coverage_due_date,
    include_waivers=True,
):
    """
    Preload rent facts for a single class + coverage period.

    Callers can pass this to _is_student_coverage_period_paid(...) to avoid
    repeating equivalent queries for every student in the same request.

    Returns canonical ``ObligationAssessment`` rows grouped by seat.  Each
    assessment's ``.satisfaction`` holds the payment details (amount_paid,
    satisfied_at, was_late, late_fee_charged, transaction_id).
    """
    from app.services.obligations_service import (
        get_paid_rent_assessments_for_cycle,
        get_waived_seat_ids_for_cycle,
    )

    if not settings or not class_id or not coverage_due_date or not seat_ids:
        return None

    join_code = get_display_join_code(class_id)
    if not join_code:
        return None

    valid_seats = (
        db.session.query(Seat.id, Seat.user_id)
        .filter(Seat.class_id == class_id, Seat.id.in_(seat_ids))
        .all()
    )
    valid_seat_ids = [s.id for s in valid_seats]
    student_id_by_seat = {s.id: s.user_id for s in valid_seats}
    if not valid_seat_ids:
        return None

    waived_seat_ids = set()
    if include_waivers:
        waived_seat_ids = get_waived_seat_ids_for_cycle(
            class_id, coverage_due_date, valid_seat_ids,
        )

    assessments = get_paid_rent_assessments_for_cycle(
        class_id,
        coverage_due_date.month,
        coverage_due_date.year,
        seat_ids=valid_seat_ids,
    )

    assessments_by_seat: dict[int, list] = defaultdict(list)
    for a in assessments:
        assessments_by_seat[a.seat_id].append(a)

    return {
        "class_id": class_id,
        "coverage_due_date": ensure_utc(coverage_due_date),
        "join_code": join_code,
        "student_id_by_seat": student_id_by_seat,
        "waived_seat_ids": waived_seat_ids,
        "valid_payments_by_seat": dict(assessments_by_seat),
        "locked_rent_amount": _get_locked_rent_amount_for_class_cycle(class_id, coverage_due_date),
    }


def _is_coverage_period_paid(
    settings,
    assessments,
    coverage_due_date,
    include_late_fee=True,
    class_id=None,
    locked_amount=None,
):
    """
    Return True when a coverage period is fully paid.

    ``assessments`` is a list of canonical ``ObligationAssessment`` rows
    whose ``satisfaction`` relationship holds the payment details.

    When include_late_fee is True (default), late fee is required when rent
    was not fully paid by grace. When False, this checks base-rent coverage
    only (used by hall-pass perk restoration).
    """
    if not settings or not coverage_due_date:
        return False
    effective_rent_amount = _get_effective_rent_amount_for_coverage_period(
        settings,
        assessments,
        coverage_due_date,
        class_id=class_id,
        locked_amount=locked_amount,
    )
    if effective_rent_amount <= Decimal('0.00'):
        return True
    if not assessments:
        return False

    total_paid = sum(
        (a.satisfaction.amount_paid for a in assessments if a.satisfaction),
        Decimal('0.00'),
    )
    grace_for_coverage = coverage_due_date + timedelta(days=settings.grace_period_days)
    paid_by_grace = _total_paid_by_grace(assessments, grace_for_coverage)

    required_total = effective_rent_amount
    if include_late_fee and paid_by_grace < effective_rent_amount:
        required_total += settings.late_fee

    return total_paid >= required_total


def _get_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
    """Return the canonical waiver assessment covering the given coverage period, if any."""
    from app.services.obligations_service import get_rent_waiver_for_seat

    if not seat_id or not class_id or not coverage_due_date:
        return None
    return get_rent_waiver_for_seat(seat_id, class_id, coverage_due_date)


def _has_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
    """Return True when a waiver covers the given coverage period."""
    return _get_active_rent_waiver_v2(seat_id, class_id, coverage_due_date) is not None


def _iter_rent_waiver_coverage_dates(settings, waiver):
    """Expand a waiver row into the individual coverage due dates it covers."""
    if not settings or not waiver:
        return []

    delta = _get_rent_period_delta(settings)
    dates = []
    current = ensure_utc(getattr(waiver, "coverage_start_time", None))
    end = ensure_utc(getattr(waiver, "coverage_end_time", None))

    while current and end and current <= end:
        dates.append(current)
        next_date = _add_rent_period(current, delta)
        if next_date <= current:
            break
        current = next_date

    return dates


def _get_rent_coverage_label(coverage_due_date):
    if not coverage_due_date:
        return "Unknown"
    return (ensure_utc(coverage_due_date) + timedelta(days=1)).strftime('%b %Y')


def _expand_rent_waiver_history(settings, waivers, *, now=None):
    """Return one waiver-history row per covered rent period."""
    now = ensure_utc(now or utc_now())
    current_coverage_due_date = _calculate_rent_coverage_due_date(settings, now) if settings else None
    entries = []

    for waiver in waivers or []:
        for coverage_due_date in _iter_rent_waiver_coverage_dates(settings, waiver):
            coverage_day = ensure_utc(coverage_due_date).date()
            current_day = ensure_utc(current_coverage_due_date).date() if current_coverage_due_date else None
            seat = getattr(waiver, "seat", None)
            student = _get_canonical_student_from_context() if seat else None

            if current_day is None or coverage_day > current_day:
                status = 'upcoming'
                status_label = 'Upcoming'
                cancellable = True
            elif current_day and coverage_day == current_day:
                status = 'current'
                status_label = 'Current'
                cancellable = False
            else:
                status = 'used'
                status_label = 'Used'
                cancellable = False

            entries.append({
                'waiver': waiver,
                'student': student,
                'coverage_due_date': coverage_due_date,
                'coverage_label': _get_rent_coverage_label(coverage_due_date),
                'status': status,
                'status_label': status_label,
                'is_cancellable': cancellable,
                'created_at': ensure_utc(getattr(waiver, "assessed_at", None)) if getattr(waiver, "assessed_at", None) else None,
                'reason': waiver.reversal.reason if getattr(waiver, "reversal", None) else None,
            })

    status_rank = {'current': 0, 'upcoming': 1, 'used': 2}
    entries.sort(
        key=lambda item: (
            status_rank.get(item['status'], 3),
            -(item['coverage_due_date'].timestamp() if item['coverage_due_date'] else 0),
            -(item['created_at'].timestamp() if item['created_at'] else 0),
        )
    )
    return entries


def _is_student_coverage_period_paid(
    settings,
    seat_id,
    class_id,
    coverage_due_date,
    include_late_fee=True,
    include_waivers=True,
    coverage_context=None,
):
    """
    Return True when a student's specific coverage period is fully paid or waived.
    """
    if not settings:
        return False
    if not coverage_due_date or not class_id:
        return False

    context_applies = False
    if coverage_context:
        context_class_id = coverage_context.get("class_id")
        context_coverage_due = ensure_utc(coverage_context.get("coverage_due_date"))
        context_applies = (
            context_class_id == class_id
            and context_coverage_due == ensure_utc(coverage_due_date)
        )

    student_id = None
    locked_amount = None
    if context_applies:
        student_id = (coverage_context.get("student_id_by_seat") or {}).get(seat_id)
        locked_amount = coverage_context.get("locked_rent_amount")
        if include_waivers and seat_id in (coverage_context.get("waived_seat_ids") or set()):
            return True
    else:
        if seat_id:
            seat = db.session.get(Seat, seat_id)
            student_id = seat.user_id if seat else None
        if include_waivers:
            if _has_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
                return True

    if context_applies:
        assessments = (coverage_context.get("valid_payments_by_seat") or {}).get(seat_id, [])
    else:
        from app.services.obligations_service import get_paid_rent_assessments_for_cycle
        assessments = get_paid_rent_assessments_for_cycle(
            class_id,
            coverage_due_date.month,
            coverage_due_date.year,
            seat_ids=[seat_id],
        )
    return _is_coverage_period_paid(
        settings,
        assessments,
        coverage_due_date,
        include_late_fee=include_late_fee,
        class_id=class_id,
        locked_amount=locked_amount,
    )


def _calculate_rent_coverage_due_date(settings, reference_date=None):
    """
    Return the most recently passed due date for coverage tracking.

    If we're before the current due date, this returns the previous due date.
    """
    reference_date = ensure_utc(reference_date) if reference_date else utc_now()
    if settings.first_rent_due_date:
        first_due = ensure_utc(settings.first_rent_due_date)
        if first_due and reference_date < first_due:
            return None
    current_due_date, _ = _calculate_rent_deadlines(settings, reference_date)
    if not current_due_date:
        return None

    if reference_date >= current_due_date:
        return current_due_date

    # If we're before the current due date, compute the previous due date.
    # For monthly settings without a first_rent_due_date, compute the prior
    # month explicitly to preserve the configured day-of-month.
    if settings.frequency_type == 'monthly' and not settings.first_rent_due_date:
        teacher_tz = _get_rent_timezone(getattr(settings, "class_id", None))
        current_due_local = ensure_utc(current_due_date).astimezone(teacher_tz)
        prev_year = current_due_local.year
        prev_month = current_due_local.month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1

        _, last_day = monthrange(prev_year, prev_month)
        due_day = settings.due_day_of_month or last_day
        due_day = min(due_day, last_day)
        previous_due_local = teacher_tz.localize(datetime(prev_year, prev_month, due_day, current_due_local.hour, current_due_local.minute, current_due_local.second))
        return previous_due_local.astimezone(timezone.utc)

    delta = _get_rent_period_delta(settings)
    return current_due_date - delta


def _ensure_rent_hall_pass_top_off(student, context, settings=None, now=None):
    """
    Reconcile rent-granted hall passes for the current coverage period.

    Returns:
        tuple[int, int, bool]: (passes_awarded, passes_revoked, state_changed)
    """
    if not student or not context:
        return 0, 0, False

    seat = get_current_seat()
    if not seat and student and context:
        seat = db.session.get(Seat, context.seat_id)
    current_block = seat.class_economy.section.strip().upper() if seat and seat.class_economy and seat.class_economy.section else ""
    class_id = context.class_id

    if not class_id:
        return 0, 0, False

    seat_id = student.identity_profile.seat_id if student and student.identity_profile else None
    if not seat_id:
        return 0, 0, False

    settings = settings or get_rent_settings_for_context(context)
    if not settings:
        return 0, 0, False

    now = now or utc_now()
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    if not coverage_due_date:
        return 0, 0, False

    is_paid = _is_student_coverage_period_paid(
        settings,
        seat_id,
        class_id,
        coverage_due_date,
        include_late_fee=False,
    )

    seat = Seat.query.get(seat_id)

    total_grant = store_service.get_rent_hall_pass_grant_total(settings.id)
    target_rent_passes = total_grant if is_paid else 0
    return _reconcile_rent_hall_pass_top_off(
        seat=seat,
        target_rent_passes=target_rent_passes,
    )


@student_bp.route('/rent')
@login_required
def rent():
    """View rent status and payment history (per period)."""
    # Check if rent feature is enabled
    if not is_feature_enabled('rent'):
        abort(404)

    class_id = get_current_class_id()
    _ = get_current_user()
    context = resolve_canonical_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    seat_id = context.seat_id
    if not seat_id:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))

    from app.models import Seat
    seat = db.session.get(Seat, seat_id)
    if not seat:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))

    class_id = class_id or context.class_id
    current_block = (
        seat.class_economy.section.strip().upper()
        if seat and seat.class_economy and seat.class_economy.section
        else ""
    )
    settings = get_rent_settings_for_context(context)

    if not settings:
        flash("Rent system is currently disabled.", "info")
        return redirect(url_for('student.dashboard'))

    if not current_block:
        flash("No class period found for this class.", "error")
        return redirect(url_for('student.dashboard'))

    if not class_id:
        flash("No class context available.", "error")
        return redirect(url_for('student.dashboard'))

    # Calculate rent status for each period
    now = utc_now()

    timeline = _calculate_rent_timeline(settings, now)
    due_date = timeline['due_date']
    grace_end_date = timeline['grace_end_date']
    coverage_due_date = timeline['coverage_due_date']
    upcoming_due_date = timeline['upcoming_due_date']
    preview_start_date = timeline['preview_start_date']
    rent_is_active = timeline['rent_is_active']
    is_preview_period_candidate = timeline['is_preview_period_candidate']

    # CRITICAL FIX: Before allowing preview period, check if current coverage is paid
    # Students must pay overdue periods before pre-paying for upcoming periods
    current_coverage_paid = False
    if is_preview_period_candidate and not coverage_due_date:
        # No prior coverage period to settle; allow preview payments
        current_coverage_paid = True
    elif is_preview_period_candidate and coverage_due_date:
        current_coverage_paid = _is_student_coverage_period_paid(
            settings,
            seat_id,
            class_id,
            coverage_due_date,
        )

    # Only allow preview period if current coverage is already paid
    is_preview_period = is_preview_period_candidate and current_coverage_paid

    # Calculate which coverage period we're checking for (pre-paid system)
    # CRITICAL FIX: Determine which due date to show for payment (matches payment route logic)
    if is_preview_period:
        coverage_month = upcoming_due_date.month
        coverage_year = upcoming_due_date.year
        grace_end_date_for_status = upcoming_due_date + timedelta(days=settings.grace_period_days)
        payment_due_date = upcoming_due_date  # Paying for upcoming period
    else:
        coverage_month = coverage_due_date.month if coverage_due_date else upcoming_due_date.month
        coverage_year = coverage_due_date.year if coverage_due_date else upcoming_due_date.year
        grace_end_date_for_status = (coverage_due_date + timedelta(days=settings.grace_period_days)) if coverage_due_date else grace_end_date
        payment_due_date = coverage_due_date or upcoming_due_date  # Paying for overdue/current period

    period_status = {}

    from app.services.obligations_service import get_paid_rent_assessments_for_cycle
    payments = get_paid_rent_assessments_for_cycle(
        class_id,
        coverage_month,
        coverage_year,
        seat_ids=[seat_id],
    )
    payments = [payment for payment in payments if payment.satisfaction is not None]

    total_paid = sum((p.satisfaction.amount_paid for p in payments), Decimal('0.00'))

    paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
    late_fee = Decimal('0.00')
    if rent_is_active and now > grace_end_date_for_status and paid_by_grace < settings.rent_amount:
        late_fee = settings.late_fee

    total_due = settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
    active_waiver = _get_active_rent_waiver_v2(seat_id, class_id, payment_due_date) if payment_due_date else None
    is_paid = total_paid >= total_due if rent_is_active else False
    is_late = now > grace_end_date_for_status and not is_paid if rent_is_active else False
    remaining_amount = max(Decimal('0.00'), total_due - total_paid) if rent_is_active else Decimal('0.00')

    period_status[current_block] = {
        'is_paid': is_paid,
        'is_waived': bool(active_waiver and total_paid <= Decimal('0.00')),
        'is_late': is_late,
        'payments': payments,
        'total_paid': total_paid,
        'total_due': total_due,
        'remaining_amount': remaining_amount,
        'late_fee': late_fee,
        'rent_is_active': rent_is_active,
        'is_preview_period': is_preview_period,
        'waiver': active_waiver,
    }

    # Get scoped balances for this class only
    checking_balance, savings_balance = get_available_balances(seat_id, class_id)

    # Get payment history for the current class only
    from app.services.obligations_service import get_rent_payment_history
    payment_history = get_rent_payment_history(seat_id, class_id, limit=24)

    waiver_history = []
    if settings:
        from app.services.obligations_service import get_rent_waivers_for_seat

        waiver_rows = get_rent_waivers_for_seat(seat_id, class_id)
        waiver_history = _expand_rent_waiver_history(settings, waiver_rows, now=now)

    payment_history_rows = []
    for payment in payment_history:
        payment_history_rows.append({
            'period_month': payment.period_month,
            'period_year': payment.period_year,
            'amount_paid': payment.satisfaction.amount_paid if payment.satisfaction else Decimal('0.00'),
            'recorded_at': payment.satisfaction.satisfied_at if payment.satisfaction else payment.assessed_at,
            'status_text': (
                f"Paid late with fee of ${payment.satisfaction.late_fee_charged:.2f}"
                if payment.satisfaction and payment.satisfaction.was_late else "On Time"
            ),
            'entry_type': 'payment',
        })

    for waiver_entry in waiver_history:
        payment_history_rows.append({
            'period_month': waiver_entry['coverage_due_date'].month,
            'period_year': waiver_entry['coverage_due_date'].year,
            'amount_paid': None,
            'recorded_at': waiver_entry['created_at'] or waiver_entry['coverage_due_date'],
            'status_text': waiver_entry['status_label'],
            'entry_type': 'waiver',
        })

    payment_history_rows.sort(
        key=lambda row: ensure_utc(row['recorded_at']) if row.get('recorded_at') else now,
        reverse=True,
    )

    # Rent item rows were removed in v2; the page now renders from rent settings
    # and store-item linkage only.
    rent_items = []

    # Calculate days until the currently payable due date for dynamic display
    days_until_due = None
    reference_due_date = payment_due_date or upcoming_due_date
    if reference_due_date:
        days_until_due = (reference_due_date - now).days

    student_blocks = [current_block] if current_block else []
    return render_template('student_rent.html',
                          student=seat,
                          settings=settings,
                          student_blocks=student_blocks,
                          period_status=period_status,
                          current_block=current_block,
                          checking_balance=checking_balance,
                          savings_balance=savings_balance,
                          due_date=due_date,
                          payment_due_date=payment_due_date,  # CRITICAL FIX: Show correct period being paid for
                          grace_end_date=grace_end_date,
                          grace_end_date_for_status=grace_end_date_for_status,  # Add grace date for the payment period
                          preview_start_date=preview_start_date,
                          payment_history=payment_history_rows,
                          rent_items=rent_items,
                          days_until_due=days_until_due)


@student_bp.route('/rent/pay/<period>', methods=['POST'])
@login_required
@feat_shell("FEAT-OBL-001")
def rent_pay(period):
    """Process rent payment for a specific period."""
    context = resolve_canonical_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))
    class_id = context.class_id
    if not class_id:
        flash("No class context available.", "error")
        return redirect(url_for('student.dashboard'))

    seat_id = context.seat_id
    if not seat_id:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))

    from app.models import Seat
    seat = db.session.get(Seat, seat_id)
    if not seat:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))
    student = _get_canonical_student_from_context()

    settings = get_rent_settings_for_context(context)

    if not settings:
        current_app.logger.info("rent_pay exit: rent settings missing or disabled")
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student.dashboard'))

    if not seat.is_rent_enabled:
        current_app.logger.info("rent_pay exit: student rent disabled")
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student.dashboard'))

    # Validate period for the current class context only
    period = (period or '').strip().upper()
    current_block = (seat.class_economy.section or '').strip().upper() if seat and seat.class_economy else ''
    if not current_block:
        current_block = period
    current_app.logger.info(
        "rent_pay state: seat_id=%s class_id=%s current_block=%s",
        seat_id,
        class_id,
        current_block,
    )
    if period != current_block:
        current_app.logger.info(
            "rent_pay exit: period mismatch period=%s current_block=%s seat_id=%s class_id=%s",
            period,
            current_block,
            seat_id,
            class_id,
        )
        flash("Invalid period.", "error")
        return redirect(url_for('student.rent'))

    now = utc_now()

    timeline = _calculate_rent_timeline(settings, now)
    due_date = timeline['due_date']
    grace_end_date = timeline['grace_end_date']
    coverage_due_date = timeline['coverage_due_date']
    upcoming_due_date = timeline['upcoming_due_date']
    preview_start_date = timeline['preview_start_date']
    rent_is_active = timeline['rent_is_active']

    if not rent_is_active:
        current_app.logger.info(
            "rent_pay exit: rent inactive preview_start=%s upcoming_due=%s",
            preview_start_date,
            upcoming_due_date,
        )
        if preview_start_date:
            available_date = preview_start_date
            message = f"Rent is not due yet. You can start paying on {available_date.strftime('%B %d, %Y')}."
        else:
            message = f"Rent is not due yet. Payment opens on {upcoming_due_date.strftime('%B %d, %Y')}."
        flash(message, "info")
        return redirect(url_for('student.rent'))

    current_month = now.month
    current_year = now.year

    # CRITICAL FIX: Check if student has paid current coverage period BEFORE allowing preview
    # If student is overdue, they must pay the overdue period first, not pre-pay for next month
    current_coverage_paid = False
    if not coverage_due_date:
        # No prior coverage period to settle; allow preview payments
        current_coverage_paid = True
    else:
        current_coverage_paid = _is_student_coverage_period_paid(
            settings,
            seat_id,
            class_id,
            coverage_due_date,
        )

    # Determine which due date this payment should cover
    # Only allow preview period if current coverage is already paid
    is_preview_period = (
        current_coverage_paid and
        preview_start_date and
        now >= preview_start_date and
        now < upcoming_due_date
    )
    payment_due_date = upcoming_due_date if is_preview_period else (coverage_due_date or upcoming_due_date)

    # Calculate coverage period (pre-paid system)
    coverage_month = payment_due_date.month
    coverage_year = payment_due_date.year

    checking_balance, savings_balance = get_available_balances(seat_id, class_id)

    from app.services.obligations_service import get_paid_rent_assessments_for_cycle
    existing_payments = get_paid_rent_assessments_for_cycle(
        class_id,
        coverage_month,
        coverage_year,
        seat_ids=[seat_id],
    )
    existing_payments = [payment for payment in existing_payments if payment.satisfaction is not None]

    total_paid_so_far = sum((p.satisfaction.amount_paid for p in existing_payments), Decimal('0.00'))

    # Calculate if late and total amount due
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    grace_end_date_for_payment = grace_end_date
    if payment_due_date and payment_due_date != due_date:
        grace_end_date_for_payment = payment_due_date + timedelta(days=settings.grace_period_days)
    paid_by_grace = _total_paid_by_grace(existing_payments, grace_end_date_for_payment)
    is_late = now > grace_end_date_for_payment and paid_by_grace < settings.rent_amount

    # Calculate late fee if applicable
    late_fee = Decimal('0.00')
    if is_late:
        late_fee = settings.late_fee

    # Total amount due (rent + late fee if applicable)
    total_due = _quantize_currency(settings.rent_amount + late_fee)

    # Calculate remaining amount to pay
    remaining_amount = _quantize_currency(total_due - total_paid_so_far)
    current_app.logger.info(
        "rent_pay totals: total_paid_so_far=%s total_due=%s remaining_amount=%s current_coverage_paid=%s preview=%s",
        total_paid_so_far,
        total_due,
        remaining_amount,
        current_coverage_paid,
        is_preview_period,
    )

    # Check if already fully paid
    if remaining_amount <= 0:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    # Get payment amount from form (supports incremental payments)
    payment_amount_input = request.form.get('amount', '').strip()

    # Determine payment amount based on incremental setting
    if settings.allow_incremental_payment and payment_amount_input:
        try:
            payment_amount = _quantize_currency(payment_amount_input)
            # Validate payment amount
            if payment_amount <= Decimal('0'):
                flash("Payment amount must be greater than 0.", "error")
                return redirect(url_for('student.rent'))
            if payment_amount > remaining_amount:
                flash(f"Payment amount (${payment_amount:.2f}) exceeds remaining balance (${remaining_amount:.2f}). Paying exact remaining amount.", "info")
                payment_amount = remaining_amount
        except (ValueError, InvalidOperation):
            flash("Invalid payment amount.", "error")
            return redirect(url_for('student.rent'))
    else:
        # Full payment required (or no amount specified with incremental disabled)
        payment_amount = remaining_amount

    # Get banking settings for overdraft handling (reuse class context from above)
    banking_settings = get_banking_settings_for_context(context)

    from app.models import Seat
    seat = db.session.get(Seat, seat_id)

    intended_plan = build_intended_ledger_plan(
        seat_id=seat_id,
        class_id=class_id,
        user_id=student.user_id,
        debit_amount=payment_amount,
        description=f"Rent for Period {period}",
        source_account="checking",
        target_account="rent",
    )
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        banking_settings=banking_settings,
        idempotency_key=f"rent_payment:{seat.id}:{class_id}:{period}:{coverage_year}-{coverage_month}:{payment_amount}:resolve",
        force_overdraft_fee=False,
        allow_recovery_transfer=True,
    )
    current_app.logger.info(
        "rent_pay overdraft gate: outcome=%s shortfall=%s banking_enabled=%s payment_amount=%s",
        resolved_plan.outcome,
        resolved_plan.shortfall,
        getattr(banking_settings, "overdraft_protection_enabled", None) if banking_settings else None,
        payment_amount,
    )
    if resolved_plan.outcome == "DENY":
        if banking_settings and banking_settings.overdraft_protection_enabled:
            message = (f"Insufficient funds in both checking and savings. You need "
                       f"${payment_amount:.2f} but have ${checking_balance + savings_balance:.2f}.")
        else:
            message = (f"Insufficient funds. You need ${payment_amount:.2f} but only "
                       f"have ${checking_balance:.2f}.")
        flash(message, "error")
        return redirect(url_for('student.rent'))

    overdraft_shortfall = resolved_plan.recovery_transfer_amount if resolved_plan.recovery_transfer_amount > 0 else Decimal('0.00')

    current_app.logger.info(
        "rent_pay before execute: seat_id=%s class_id=%s period=%s amount=%s",
        seat_id,
        class_id,
        period,
        payment_amount,
    )
    result = execute_rent_payment(
        seat=seat,
        context=context,
        payment_amount=payment_amount,
        period=period,
        settings=settings,
        is_late=is_late,
        late_fee=late_fee,
        total_paid_so_far=total_paid_so_far,
        total_due=total_due,
        remaining_amount=remaining_amount,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        current_month=current_month,
        current_year=current_year,
        payment_due_date=payment_due_date,
        banking_settings=banking_settings,
        overdraft_shortfall=overdraft_shortfall,
        now=now,
        calculate_due_dates_fn=_calculate_due_dates,
    )
    current_app.logger.info(
        "rent_pay after execute: transaction_id=%s payment_id=%s",
        result.transaction_id,
        result.payment_id,
    )
    # Success message
    if result.is_partial and settings.allow_incremental_payment:
        if result.new_remaining > 0:
            flash(f"Partial payment of ${result.amount_paid:.2f} successful! Remaining balance: ${result.new_remaining:.2f}", "success")
        else:
            msg = f"Final payment of ${result.amount_paid:.2f} successful! Rent for Period {period} is now fully paid."
            if result.passes_awarded > 0:
                msg += f" You received {result.passes_awarded} hall passes!"
            flash(msg, "success")
    else:
        msg = f"Rent payment for Period {period} (${result.amount_paid:.2f}) successful!"
        if result.passes_awarded > 0:
            msg += f" You received {result.passes_awarded} hall passes!"
        flash(msg, "success")

    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
@feat_shell("FEAT-IDEN-001")
def login():
    """Student login with username and PIN."""
    form = StudentLoginForm()
    if form.validate_on_submit():
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Verify Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response')
        if not verify_turnstile_token(turnstile_token, get_real_ip()):
            current_app.logger.warning(f"Turnstile verification failed for student login attempt")
            if is_json:
                return jsonify(status="error", message="CAPTCHA verification failed. Please try again."), 403
            flash("CAPTCHA verification failed. Please try again.", "error")
            return redirect(url_for('student.login', next=request.args.get('next')))

        username = form.username.data.strip()
        pin = form.pin.data.strip()

        user = find_canonical_user_by_auth_username(username, expected_role="student")

        try:
            pin_valid = bool(user and check_password_hash(user.pin_hash or '', pin))
            student = None
            if pin_valid:
                from app.models import Seat

                student = Seat.query.filter(
                    Seat.user_id == user.id,
                    Seat.role == "student",
                    Seat.claimed_at.isnot(None),
                ).first()

            if not student or not pin_valid:
                if is_json:
                    return jsonify(status="error", message="Invalid credentials"), 401
                flash("Invalid credentials", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))

            if not is_student_account_active(student):
                if is_json:
                    return jsonify(status="error", message="Account is inactive. Contact your teacher."), 403
                flash("Your account is inactive. Contact your teacher.", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error("Error during student login authentication")
            if is_json:
                return jsonify(status="error", message="An error occurred during login. Please try again."), 500
            flash("An error occurred during login. Please try again.", "error")
            return redirect(url_for('student.login'))

        # --- Set session timeout ---
        # Clear old student-specific session keys without wiping the CSRF token
        _reset_student_login_session()
        # Explicitly clear other potential student-related session keys
        session.pop('onboarding_seat_ref', None)
        session.pop('onboarding_user_ref', None)
        session.pop('generated_username', None)
        clear_teacher_display_name_cache()


        session['login_time'] = utc_now().isoformat()
        session['last_activity'] = session['login_time']

        linked_user = user
        establish_student_session(linked_user, class_id=valid_persisted_selection["class_id"])
        session['current_session_nonce'] = secrets.token_urlsafe(32)
        linked_user.current_session_nonce = session['current_session_nonce']

        seat_options = _get_identity_bound_seat_options(linked_user.id)
        persisted_class_id = getattr(linked_user, "last_active_class_id", None)
        valid_persisted_selection = None
        if persisted_class_id:
            valid_persisted_selection = next(
                (item for item in seat_options if item["class_id"] == persisted_class_id),
                None,
            )
            if valid_persisted_selection is None:
                current_app.logger.error(
                    "TLCP-INVARIANT-VIOLATION: Student %s login has invalid persisted class %s.",
                    student.id,
                    persisted_class_id,
                    extra={
                        "actor_type": "student",
                        "actor_public_id": "-",
                        "class_id": "-",
                        "error_class": "InvariantViolation",
                        "correlation_version": "v1",
                    },
                )
                linked_user.last_active_class_id = None

        if not seat_options:
            return _student_login_hard_fail(
                student_id=student.id,
                reason=f"Student {student.id} login has no valid class seats.",
                is_json=is_json,
            )

        if valid_persisted_selection is None:
            return redirect(url_for('student.select_class_context'))

        seat = None
        from app.models import Seat, IdentityProfile
        seat = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .filter(
                IdentityProfile.seat_id == student.id,
                Seat.class_id == valid_persisted_selection["class_id"],
                Seat.claimed_at.isnot(None),
            )
            .first()
        )
        if seat is None:
            return _student_login_hard_fail(
                student_id=student.id,
                reason=f"Student {student.id} login failed to hydrate canonical seat for class {valid_persisted_selection['class_id']}.",
                is_json=is_json,
            )
        _prime_seat_teacher_display_name_cache(student.id)


        # Removed redirect to student_setup for has_completed_setup; new onboarding flow uses claim → username → pin/passphrase.

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            return redirect(url_for('student.dashboard'))
        return redirect(next_url or url_for('student.dashboard'))  # nosec # Safe: validated by is_safe_url()

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)


@student_bp.route('/select-class-context', methods=['GET', 'POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def select_class_context():
    """Explicit class-selection gate when no durable class context exists."""
    student = _get_canonical_student_from_context()
    if not student:
        return redirect(url_for('student.login'))

    linked_user = _find_linked_user_for_student(student)
    if not linked_user:
        current_app.logger.critical(
            "P0 INCIDENT: Student %s has no identity-linked user during class-context gate.",
            student.id,
        )
        session.clear()
        flash("Account scope incident detected. Contact support immediately.", "error")
        return redirect(url_for('student.login'))

    seat_options = _get_identity_bound_seat_options(linked_user.id)
    if not seat_options:
        current_app.logger.critical(
            "P0 INCIDENT: Student %s has no surviving seats during class-context gate.",
            student.id,
        )
        session.clear()
        flash("Account scope incident detected. Contact support immediately.", "error")
        return redirect(url_for('student.login'))

    if request.method == 'POST':
        selected_class_id = (request.form.get('class_id') or '').strip()
        allowed_class_ids = {item["class_id"] for item in seat_options}
        if selected_class_id not in allowed_class_ids:
            return _student_login_hard_fail(
                student_id=student.id,
                reason=f"Student {student.id} selected invalid class {selected_class_id} during class-context switch.",
                is_json=False,
                status_code=302,
            )

        selected_seat = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .filter(
                IdentityProfile.id == student.identity_id,
                Seat.class_id == selected_class_id,
                Seat.claimed_at.isnot(None),
            )
            .first()
        )
        if selected_seat is None:
            return _student_login_hard_fail(
                student_id=student.id,
                reason=f"Student {student.id} selected class {selected_class_id} but seat context failed to resolve.",
                is_json=False,
                status_code=302,
            )

        linked_user.last_active_class_id = selected_class_id

        scope = resolve_scope(actor=student, actor_role="student")
        if not scope or scope.class_id != selected_class_id:
            current_app.logger.critical(
                "P0 INCIDENT: Scope construction mismatch for student %s class %s.",
                student.id,
                selected_class_id,
            )
            session.clear()
            flash("Account scope incident detected. Contact support immediately.", "error")
            return redirect(url_for('student.login'))

        return redirect(url_for('student.dashboard'))

    return render_template('student_select_class_context.html', class_options=seat_options)


@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


@student_bp.route('/switch-class/<class_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def switch_class(class_id):
    """Switch to a different class using class_id as the stable backend reference."""
    from app.models import Seat

    student = _get_canonical_student_from_context()
    try:
        resolved_switch = resolve_student_class_switch_scope(actor=student, class_id=class_id)
        access_policy_service.assert_can_switch_class(resolved_switch.scope)
    except (AccessScopeDenied, access_policy_service.AccessPolicyDenied) as exc:
        return jsonify(status="error", message="You don't have access to that class."), 403
    seat = db.session.get(Seat, resolved_switch.seat_id)
    if seat is None:
        return jsonify(status="error", message="You don't have access to that class."), 403

    # Use canonical session context switch (Logs: SESSION-CONTEXT-SWITCH)
    from app.auth import switch_student_session_context
    switch_student_session_context(
        student, 
        class_id=resolved_switch.scope.class_id, 
        seat_id=seat.id,
    )

    # Get teacher name for response
    teacher_cache = get_teacher_display_name_cache()
    teacher_name = teacher_cache.get(str(resolved_switch.scope.user_id))
    if not teacher_name:
        teacher_name = "Teacher"

    # Get block/period info
    block_display = f"Block {seat.class_economy.section.upper()}" if seat and seat.class_economy and seat.class_economy.section else "Unknown Block"

    return jsonify(
        status="success",
        message=f"Switched to {teacher_name}'s class ({block_display})",
        teacher_name=teacher_name,
        block=seat.class_economy.section if seat and seat.class_economy else None
    )


@student_bp.route('/switch-period/<int:user_id>', methods=['POST'])
@login_required
def switch_period(user_id):
    """Disabled switch-period route."""
    current_app.logger.warning(
        "Disabled student switch-period route called for user_id=%s",
        user_id,
    )
    flash("Switch using class context.", "warning")
    return redirect(url_for('student.dashboard'))


# -------------------- SETUP COMPLETE --------------------
    # Note: This route is not prefixed with /student.

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = _get_canonical_student_from_context()
    _ip = student.identity_profile if hasattr(student, 'identity_profile') else None
    return render_template('student_setup_complete.html', student_name=(_ip.first_name if _ip else ""))


# -------------------- HELP AND SUPPORT - ISSUE RESOLUTION SYSTEM --------------------

@student_bp.route('/help-support', methods=['GET'])
@login_required
def help_support():
    """Show the student help and support page with issue tracking."""
    from app.utils.issue_categories import init_default_categories

    class_context = resolve_canonical_context()
    student = db.session.get(Seat, class_context.seat_id) if class_context and getattr(class_context, "seat_id", None) else None

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Initialize default categories if they don't exist
    init_default_categories()

    # Get student's issues for current class (last 20)
    my_issues = Issue.query.filter_by(
        seat_id=student.id,
        class_id=class_context.class_id,
    ).order_by(Issue.submitted_at.desc()).limit(20).all()

    return render_template('student_help_support_new.html',
                         current_page='help',
                         page_title='Help & Support',
                         my_issues=my_issues,
                         help_content=HELP_ARTICLES['student'],
                         format_utc_iso=format_utc_iso)


@student_bp.route('/help-support/submit-issue', methods=['GET', 'POST'])
@login_required
def submit_general_issue():
    """Submit a general issue or help request."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm

    class_context = resolve_canonical_context()
    student = db.session.get(Seat, class_context.seat_id) if class_context and getattr(class_context, "seat_id", None) else None

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    form = StudentIssueSubmissionForm()
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

    # Populate category choices
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('general')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            issue = create_issue(
                actor=student,
                user_id=class_context.user_id,
                class_id=class_context.class_id,
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                include_recent_error=include_recent_error,
            )

            flash("Your issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report an Issue',
                         form=form,
                         issue_type='general',
                         show_recent_error_option=show_recent_error_option)


@student_bp.route('/help-support/transaction/<int:transaction_id>/report', methods=['GET', 'POST'])
@login_required
def report_transaction_issue(transaction_id):
    """Report an issue with a specific transaction."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm, TransactionIssueSubmissionForm

    class_context = resolve_canonical_context()
    student = db.session.get(Seat, class_context.seat_id) if class_context and getattr(class_context, "seat_id", None) else None

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Get the transaction and verify it belongs to this student and class
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        seat_id=student.id,
        join_code=get_display_join_code(class_context.class_id)
    ).first_or_404()

    form = TransactionIssueSubmissionForm()
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

    # Populate category choices with general categories
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('transaction')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            create_issue(
                actor=student,
                user_id=class_context.user_id,
                class_id=class_context.class_id,
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                related_transaction_id=transaction_id,
                related_record_type='transaction',
                include_recent_error=include_recent_error,
            )

            flash("Your transaction issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting transaction issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report Transaction Issue',
                         form=form,
                         issue_type='transaction',
                         transaction=transaction,
                         show_recent_error_option=show_recent_error_option)


@student_bp.route('/help-support/tap-event/<int:tap_event_id>/report', methods=['GET', 'POST'])
@login_required
def report_tap_event_issue(tap_event_id):
    """Report an issue with a specific tap event (clock in/out record)."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm

    class_context = resolve_canonical_context()
    student = db.session.get(Seat, class_context.seat_id) if class_context and getattr(class_context, "seat_id", None) else None

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Get the tap event and verify it belongs to this student and class
    tap_event = AttendanceSession.query.filter_by(
        id=tap_event_id,
        seat_id=student.id,
        class_id=class_context.class_id,
    ).first_or_404()

    form = StudentIssueSubmissionForm()
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

    # Populate category choices with general categories (includes "Clock In/Out Not Working")
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('general')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            create_issue(
                actor=student,
                user_id=class_context.user_id,
                class_id=class_context.class_id,
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                related_transaction_id=None,  # No transaction for tap events
                related_record_type='tap_event',
                related_record_id=tap_event_id,
                include_recent_error=include_recent_error,
            )

            flash("Your attendance issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting tap event issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report Attendance Issue',
                         form=form,
                         issue_type='attendance',
                         tap_event=tap_event,
                         show_recent_error_option=show_recent_error_option)


# ================== TEACHER ACCOUNT RECOVERY ==================

@student_bp.route('/verify-recovery/<int:code_id>', methods=['GET', 'POST'])
@login_required
@feat_shell("FEAT-IDEN-002")
def verify_recovery(code_id):
    """
    Student verification page for teacher account recovery.
    Student authenticates with passphrase, then gets a 6-digit code to give to teacher.
    """
    context = resolve_canonical_context()
    student = db.session.get(Seat, context.seat_id) if context and getattr(context, "seat_id", None) else None

    # Get the recovery code request
    recovery_code = get_recovery_code_for_seat(code_id, student.id)
    if recovery_code is None:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Check if already verified
    if recovery_code.code_hash:
        flash("You have already verified this recovery request.", "info")
        return redirect(url_for('student.dashboard'))

    # Check if expired
    # Handle timezone naive/aware comparison for SQLite/Test
    expires_at = ensure_utc(recovery_code.recovery_request.expires_at)

    if expires_at < utc_now():
        flash("This recovery request has expired.", "error")
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        passphrase = request.form.get('passphrase', '').strip()

        if not passphrase:
            flash("Please enter your passphrase.", "error")
            return render_template('student_verify_recovery.html',
                                 recovery_code=recovery_code,
                                 student=student)

        # Verify passphrase
        user = get_current_user()
        if not user or not user.passphrase_hash or not check_password_hash(user.passphrase_hash, passphrase):
            current_app.logger.warning(f"Recovery verification failed: incorrect passphrase for student {student.id}")
            flash("Incorrect passphrase. Please try again.", "error")
            return render_template('student_verify_recovery.html',
                                 recovery_code=recovery_code,
                                 student=student)

        # Generate 6-digit recovery code using cryptographically secure randomness
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Hash and store the code
        verified_at = utc_now()
        set_recovery_code_verified(code_id, hash_hmac(code.encode(), b''), verified_at)
        recovery_code.code_hash = "verified"
        recovery_code.verified_at = verified_at

        current_app.logger.info(f"Student {student.id} verified recovery request {recovery_code.recovery_request_id}")

        return render_template('student_verify_recovery.html',
                             recovery_code=recovery_code,
                             student=student,
                             generated_code=code,
                             verified=True)

    return render_template('student_verify_recovery.html',
                         recovery_code=recovery_code,
                         student=student)


@student_bp.route('/dismiss-recovery/<int:code_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-IDEN-002")
def dismiss_recovery(code_id):
    """
    Dismiss the recovery notification banner.
    """
    context = resolve_canonical_context()
    student = db.session.get(Seat, context.seat_id) if context and getattr(context, "seat_id", None) else None

    # Get the recovery code request
    recovery_code = get_recovery_code_for_seat(code_id, student.id)
    if recovery_code is None:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Mark as dismissed
    dismiss_recovery_code_row(code_id)

    flash("Recovery notification dismissed. You can still verify later from your notifications.", "info")
    return redirect(url_for('student.dashboard'))
