"""
Admin routes for Classroom Token Hub.

Contains all admin/teacher-facing functionality including dashboard, student management,
store management, insurance, payroll, attendance tracking, and data import/export.
"""

import csv
import io
import os
import re
import base64
import math
import random
import string
import secrets
import qrcode
import hashlib
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, redirect, url_for, flash, request, session,
    jsonify, Response, send_file, current_app, abort
)
from urllib.parse import urlparse
from sqlalchemy import desc, text, or_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy as sa
import pyotp
import pytz

from app.extensions import db, limiter
from app.models import (
    Student, Admin, AdminInviteCode, StudentTeacher, Transaction, TapEvent, StoreItem, StudentItem,
    StoreItemBlock, RentSettings, RentPayment, RentWaiver, InsurancePolicy, InsurancePolicyBlock,
    StudentInsurance, InsuranceClaim, HallPassLog, PayrollSettings, PayrollReward, PayrollFine,
    BankingSettings, TeacherBlock, DeletionRequest, DeletionRequestType, DeletionRequestStatus,
    UserReport, FeatureSettings, TeacherOnboarding, StudentBlock, RecoveryRequest, StudentRecoveryCode,
    DemoStudent, AdminCredential, Announcement
)
from app.auth import admin_required, get_admin_student_query, get_student_for_admin
from forms import (
    AdminLoginForm, AdminSignupForm, AdminTOTPConfirmForm, AdminRecoveryForm, AdminResetCredentialsForm, StoreItemForm,
    InsurancePolicyForm, AdminClaimProcessForm, PayrollSettingsForm,
    PayrollRewardForm, PayrollFineForm, ManualPaymentForm, BankingSettingsForm
)
# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso, generate_anonymous_code, render_template_with_fallback as render_template
from app.utils.join_code import generate_join_code
from app.utils.economy_balance import EconomyBalanceChecker
from app.utils.claim_credentials import (
    compute_primary_claim_hash,
    match_claim_hash,
    normalize_claim_hash,
)
from app.utils.ip_handler import get_real_ip
from app.utils.name_utils import hash_last_name_parts, verify_last_name_parts
from app.utils.help_content import HELP_ARTICLES
from app.utils.passwordless_client import get_passwordless_client, decode_credential_id
from app.utils.encryption import encrypt_totp, decrypt_totp
from hash_utils import get_random_salt, hash_hmac, hash_username, hash_username_lookup
from payroll import calculate_payroll
from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds, get_join_code_for_student_period
import time

# Timezone
PACIFIC = pytz.timezone('America/Los_Angeles')

# Join code generation constants
MAX_JOIN_CODE_RETRIES = 10  # Maximum attempts to generate a unique join code
FALLBACK_BLOCK_PREFIX_LENGTH = 1  # Number of characters from block name in fallback code
FALLBACK_CODE_MODULO = 10000  # Modulo for timestamp suffix (produces 4-digit number)

# Placeholder values for legacy class TeacherBlock entries
LEGACY_PLACEHOLDER_CREDENTIAL = "LEGACY0"  # Placeholder credential for legacy classes
LEGACY_PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"  # Marks legacy placeholder entries
LEGACY_PLACEHOLDER_LAST_INITIAL = "P"  # "P" for Placeholder

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# -------------------- DASHBOARD & QUICK ACTIONS --------------------


def _scoped_students(include_unassigned=True):
    """Return a query for students the current admin can access."""
    return get_admin_student_query(include_unassigned=include_unassigned)


def _get_teacher_blocks():
    """Get sorted list of blocks from teacher's students."""
    students_blocks = _scoped_students().with_entities(Student.block).all()
    return sorted(set(
        b.strip().upper() for s_blocks, in students_blocks if s_blocks
        for b in s_blocks.split(',') if b.strip()
    ))


def _get_class_labels_for_blocks(admin_id, blocks):
    """Return mapping of block -> class label for the given admin without N+1 queries."""

    if not blocks:
        return {}

    teacher_blocks = (
        TeacherBlock.query
        .filter(TeacherBlock.teacher_id == admin_id, TeacherBlock.block.in_(blocks))
        .all()
    )
    labels = {tb.block: tb.get_class_label() for tb in teacher_blocks}

    for block in blocks:
        labels.setdefault(block, block)

    return labels


def _student_scope_subquery(include_unassigned=True):
    """Return a subquery of student IDs the current admin can access."""
    return (
        _scoped_students(include_unassigned=include_unassigned)
        .with_entities(Student.id)
        .subquery()
    )


def _sanitize_csv_field(value):
    """Prevent CSV injection by prefixing risky leading characters."""

    if value is None:
        return ""

    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _get_student_or_404(student_id, include_unassigned=True):
    """Fetch a student the current admin can access or 404."""
    student = get_student_for_admin(student_id, include_unassigned=include_unassigned)
    if not student:
        abort(404)
    return student


def _link_student_to_admin(student: Student, admin_id):
    """
    Ensure the given admin is associated with the student.
    Creates both StudentTeacher link AND TeacherBlock record with join_code.
    """
    if not admin_id:
        return

    if not student.block:
        current_app.logger.warning(
            f"Student {student.id} has no block assigned, skipping TeacherBlock creation"
        )
        return

    # 1. Create StudentTeacher link
    existing_link = StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin_id).first()
    if not existing_link:
        db.session.add(StudentTeacher(student_id=student.id, admin_id=admin_id))

    # 2. Create or update TeacherBlock record with join_code
    # Check if TeacherBlock exists for this student + teacher + block
    existing_teacher_block = TeacherBlock.query.filter_by(
        teacher_id=admin_id,
        student_id=student.id,
        block=student.block
    ).first()

    if not existing_teacher_block:
        # Find or create a join_code for this teacher+block combo
        # Look for any existing TeacherBlock for this teacher+block (even unclaimed ones)
        any_block_record = TeacherBlock.query.filter_by(
            teacher_id=admin_id,
            block=student.block
        ).first()

        if any_block_record and any_block_record.join_code:
            # Reuse existing join_code for this block
            join_code = any_block_record.join_code
            # Preserve class_label if it exists
            class_label = any_block_record.class_label
        else:
            # Generate new join_code for this teacher+block
            join_code = generate_join_code()
            class_label = None

        # Create new TeacherBlock record
        new_teacher_block = TeacherBlock(
            teacher_id=admin_id,
            student_id=student.id,
            block=student.block,
            join_code=join_code,
            class_label=class_label,  # Preserve class_label if it exists
            is_claimed=True,  # Mark as claimed since teacher manually added them
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=student.last_name_hash_by_part,
            dob_sum=student.dob_sum,
            salt=student.salt,
            first_half_hash=student.first_half_hash
        )
        db.session.add(new_teacher_block)
        current_app.logger.info(
            f"Created TeacherBlock for student {student.id} with teacher {admin_id}, "
            f"block {student.block}, join_code {join_code}"
        )
    elif not existing_teacher_block.is_claimed:
        # TeacherBlock exists but not claimed - mark as claimed now
        existing_teacher_block.is_claimed = True
        existing_teacher_block.student_id = student.id
        current_app.logger.info(
            f"Claimed existing TeacherBlock for student {student.id} with join_code {existing_teacher_block.join_code}"
        )


def _get_students_needing_transaction_backfill(teacher_id):
    """
    Get students who have transactions missing proper scoping (teacher_id and/or join_code).
    
    These are orphaned transactions that need to be associated with a join_code
    for proper class isolation. This is CRITICAL because join_code is the source
    of truth for class scoping, not teacher_id.
    
    Args:
        teacher_id: The teacher's admin ID
        
    Returns:
        list: Student objects that have unscoped transactions
    """
    # Get students that belong to this teacher
    student_ids_query = _scoped_students().with_entities(Student.id).all()
    student_ids = [sid[0] for sid in student_ids_query]
    
    if not student_ids:
        return []
    
    # Find transactions for these students that have NO join_code
    # (regardless of whether they have teacher_id)
    transactions_needing_backfill = (
        Transaction.query
        .filter(
            Transaction.student_id.in_(student_ids),
            Transaction.join_code.is_(None)
        )
        .with_entities(Transaction.student_id)
        .distinct()
        .all()
    )
    
    if not transactions_needing_backfill:
        return []
    
    affected_student_ids = [tx.student_id for tx in transactions_needing_backfill]

    # SECURITY FIX: Get the student objects using scoped query for defense-in-depth
    # While the IDs are already from scoped students, this ensures consistency
    students = _scoped_students().filter(Student.id.in_(affected_student_ids)).all()

    return students


def _get_feature_settings(teacher_id, block=None):
    """
    Get feature settings for a teacher, optionally scoped to a specific block.

    Settings are resolved with block-specific overriding global defaults:
    1. Look for block-specific settings if block is provided
    2. Fall back to global (block=NULL) settings
    3. Fall back to system defaults if no settings exist

    Args:
        teacher_id: The teacher's admin ID
        block: Optional block/period name (e.g., "A", "B", "1")

    Returns:
        dict: Feature settings with all toggle values
    """
    # Try block-specific settings first
    if block:
        block_settings = FeatureSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block.strip().upper()
        ).first()
        if block_settings:
            return block_settings.to_dict()

    # Fall back to global settings
    global_settings = FeatureSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None
    ).first()

    if global_settings:
        return global_settings.to_dict()

    # Return defaults if no settings exist
    return FeatureSettings.get_defaults()


def _get_or_create_onboarding(teacher_id):
    """
    Get or create onboarding record for a teacher.

    Args:
        teacher_id: The teacher's admin ID

    Returns:
        TeacherOnboarding: The onboarding record
    """
    onboarding = TeacherOnboarding.query.filter_by(teacher_id=teacher_id).first()
    if not onboarding:
        onboarding = TeacherOnboarding(teacher_id=teacher_id)
        db.session.add(onboarding)
        db.session.commit()
    return onboarding


def _check_onboarding_redirect():
    """
    Check if the current admin needs onboarding and should be redirected.

    Returns:
        None if no redirect needed, otherwise a redirect response
    """
    admin_id = session.get('admin_id')
    if not admin_id:
        return None

    # Check if teacher has completed or skipped onboarding
    onboarding = TeacherOnboarding.query.filter_by(teacher_id=admin_id).first()

    # If no onboarding record exists, teacher needs onboarding
    if not onboarding:
        # Check if teacher has any existing students - if so, they're a legacy teacher
        # and we should skip onboarding for them
        admin = Admin.query.get(admin_id)
        if admin and admin.has_assigned_students:
            # Legacy teacher - create completed onboarding record
            onboarding = TeacherOnboarding(
                teacher_id=admin_id,
                is_completed=True,
                is_skipped=True,
                completed_at=datetime.now(timezone.utc)
            )
            db.session.add(onboarding)
            db.session.commit()
            return None

        # New teacher needs onboarding
        return redirect(url_for('admin.onboarding'))

    # If onboarding exists and is completed or skipped, no redirect needed
    if onboarding.is_completed or onboarding.is_skipped:
        return None

    # Teacher has incomplete onboarding - redirect them
    return redirect(url_for('admin.onboarding'))


def _normalize_claim_credentials_for_admin(admin_id: int) -> int:
    """Normalize claim hashes for all students and seats the admin can access.

    This keeps legacy last-initial hashes claimable while ensuring future
    matches use the canonical first-initial credential. Returns the number of
    records updated.
    """

    if not admin_id:
        return 0

    updated = 0

    # Normalize TeacherBlock seats (claimed and unclaimed)
    teacher_blocks = TeacherBlock.query.filter_by(teacher_id=admin_id).yield_per(100)
    for seat in teacher_blocks:
        if seat.first_name == LEGACY_PLACEHOLDER_FIRST_NAME:
            # Placeholder rows only store join codes and should not be mutated
            continue

        first_initial = seat.first_name.strip()[0].upper() if seat.first_name else None
        updated_hash, changed = normalize_claim_hash(
            seat.first_half_hash,
            first_initial,
            seat.last_initial,
            seat.dob_sum,
            seat.salt,
        )
        if changed and updated_hash:
            seat.first_half_hash = updated_hash
            updated += 1

    # Normalize Student records scoped to this admin
    students = _scoped_students().yield_per(100)
    for student in students:
        first_initial = student.first_name.strip()[0].upper() if student.first_name else None
        updated_hash, changed = normalize_claim_hash(
            student.first_half_hash,
            first_initial,
            student.last_initial,
            student.dob_sum,
            student.salt,
        )
        if changed and updated_hash:
            student.first_half_hash = updated_hash
            updated += 1

    if updated:
        try:
            db.session.commit()
        except Exception as exc:
            current_app.logger.error(
                "Failed to normalize claim credentials for admin %s: %s", admin_id, exc
            )
            db.session.rollback()
            return 0

    return updated

def auto_tapout_all_over_limit():
    """
    Checks all active students and auto-taps them out if they've exceeded their daily limit.
    This is called when admin views the dashboard to ensure limits are enforced.
    """
    from app.routes.api import check_and_auto_tapout_if_limit_reached

    # Get all students
    students = _scoped_students().all()
    tapped_out_count = 0

    for student in students:
        try:
            # Get the student's current active sessions
            student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            for period in student_blocks:
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                # If student is active, run the auto-tapout check
                if latest_event and latest_event.status == "active":
                    check_and_auto_tapout_if_limit_reached(student)
                    tapped_out_count += 1
                    break  # Only need to run once per student
        except Exception as e:
            current_app.logger.error(f"Error checking auto-tapout for student {student.id}: {e}")
            continue

    return tapped_out_count

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics, pending actions, and recent activity."""
    # Check if teacher needs onboarding
    onboarding_redirect = _check_onboarding_redirect()
    if onboarding_redirect:
        return onboarding_redirect

    # Check for students with transactions needing join_code backfill
    current_admin_id = session.get('admin_id')
    students_needing_backfill = _get_students_needing_transaction_backfill(current_admin_id)
    if students_needing_backfill:
        # Redirect to backfill page
        return redirect(url_for('admin.backfill_transactions'))

    student_ids_subq = _student_scope_subquery()
    # Auto-tapout students who have exceeded their daily limit
    auto_tapout_all_over_limit()

    # Get all students for calculations
    students = _scoped_students().order_by(Student.first_name).all()
    student_lookup = {s.id: s for s in students}

    # Quick Stats
    total_students = len(students)
    total_balance = sum(s.checking_balance + s.savings_balance for s in students)
    avg_balance = total_balance / total_students if total_students > 0 else 0

    # Pending actions - count all types of pending approvals
    pending_redemptions_count = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentItem.status == 'processing')
        .count()
    )
    pending_hall_passes_count = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .count()
    )
    pending_insurance_claims_count = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(InsuranceClaim.status == 'pending')
        .count()
    )
    total_pending_actions = pending_redemptions_count + pending_hall_passes_count + pending_insurance_claims_count

    # Get recent items for each pending type (limited for display)
    recent_redemptions = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentItem.status == 'processing')
        .order_by(StudentItem.redemption_date.desc())
        .limit(5)
        .all()
    )
    recent_hall_passes = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.desc())
        .limit(5)
        .all()
    )
    recent_insurance_claims = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(InsuranceClaim.status == 'pending')
        .order_by(InsuranceClaim.filed_date.desc())
        .limit(5)
        .all()
    )

    # Recent transactions (limited to 5 for display)
    demo_ids_subq = db.session.query(DemoStudent.student_id).subquery()
    recent_transactions = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter(~Transaction.student_id.in_(demo_ids_subq))
        .filter_by(is_void=False)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
    total_transactions_today = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter(~Transaction.student_id.in_(demo_ids_subq))
        .filter(
            Transaction.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
            Transaction.is_void == False,
        )
        .count()
    )

    # Recent attendance logs (limited to 5 for display)
    raw_logs = (
        db.session.query(
            TapEvent,
            Student.first_name,
            Student.last_initial
        )
        .join(Student, TapEvent.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .order_by(TapEvent.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_logs = []
    for log, first_name, last_initial in raw_logs:
        recent_logs.append({
            'student_id': log.student_id,
            'student_name': f"{first_name} {last_initial}.",
            'period': log.period,
            'timestamp': log.timestamp,
            'reason': log.reason,
            'status': log.status
        })

    # --- Payroll Info ---
    last_payroll_time = get_last_payroll_time()
    payroll_summary = calculate_payroll(students, last_payroll_time, teacher_id=current_admin_id)
    total_payroll_estimate = sum(payroll_summary.values())

    # Calculate next payroll date (keep in UTC for template conversion)
    if last_payroll_time:
        next_payroll_date = last_payroll_time + timedelta(days=14)
    else:
        now_utc = datetime.now(timezone.utc)
        days_until_friday = (4 - now_utc.weekday() + 7) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_payroll_date = now_utc + timedelta(days=days_until_friday)

    # Check for missing recovery setup (legacy accounts)
    current_admin = Admin.query.get(session['admin_id'])
    show_recovery_setup = current_admin and current_admin.dob_sum_hash is None

    # Prompt legacy teachers to upgrade insurance policies to the new tiered design
    show_insurance_tier_prompt = False
    onboarding_record = TeacherOnboarding.query.filter_by(teacher_id=session['admin_id']).first()
    if onboarding_record and onboarding_record.steps_completed and onboarding_record.steps_completed.get("needs_insurance_tier_upgrade"):
        legacy_policy_exists = (
            db.session.query(InsurancePolicy.id)
            .filter(InsurancePolicy.teacher_id == session['admin_id'])
            .filter(InsurancePolicy.tier_category_id.is_(None))
            .filter(InsurancePolicy.tier_level.is_(None))
            .first()
            is not None
        )
        show_insurance_tier_prompt = legacy_policy_exists

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
    title = request.form.get('title')
    amount = float(request.form.get('amount'))
    tx_type = request.form.get('type')

    # Get current admin ID for teacher_id
    current_admin_id = session.get('admin_id')

    # Prefetch join_codes for all scoped students to avoid N+1 queries
    students_query = _scoped_students()
    student_ids_subquery = students_query.with_entities(Student.id).subquery()
    teacher_blocks = (
        TeacherBlock.query
        .filter(
            TeacherBlock.student_id.in_(student_ids_subquery),
            TeacherBlock.teacher_id == current_admin_id,
            TeacherBlock.is_claimed.is_(True)
        )
        .with_entities(TeacherBlock.student_id, TeacherBlock.join_code)
        .all()
    )
    join_code_map = {student_id: join_code for student_id, join_code in teacher_blocks}

    # Stream students in batches to reduce memory usage
    students = students_query.yield_per(50)
    for student in students:
        join_code = join_code_map.get(student.id)

        tx = Transaction(
            student_id=student.id,
            teacher_id=current_admin_id,  # CRITICAL: Add teacher_id for multi-tenancy
            join_code=join_code,  # CRITICAL: Add join_code for period isolation
            amount=amount,
            type=tx_type,
            description=title,
            account_type='checking'
        )
        db.session.add(tx)

    db.session.commit()
    flash("Bonus/Payroll posted successfully!")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/backfill-transactions', methods=['GET', 'POST'])
@admin_required
def backfill_transactions():
    """
    Backfill join_code for orphaned transactions (CRITICAL for proper class isolation).
    
    join_code is the SOURCE OF TRUTH for class scoping because:
    - A teacher can have multiple periods (Period 1 Math, Period 3 Math)
    - Each period has a unique join_code
    - Students in both periods should see SEPARATE balances for each
    
    Teacher selects which period/block each affected student belongs to,
    and we update:
    1. Transaction join_code (CRITICAL - required for balance scoping)
    2. Transaction teacher_id (if not already set)
    3. Student teacher_id (if not already set)
    4. StudentTeacher association (if not already exists)
    """
    current_admin_id = session.get('admin_id')
    students_needing_backfill = _get_students_needing_transaction_backfill(current_admin_id)
    
    if not students_needing_backfill:
        # No students need backfill, redirect to dashboard
        return redirect(url_for('admin.dashboard'))
    
    # Get teacher's available periods/blocks with join codes
    teacher_blocks = (
        TeacherBlock.query
        .filter_by(teacher_id=current_admin_id, is_claimed=True)
        .with_entities(TeacherBlock.block, TeacherBlock.join_code)
        .distinct()
        .all()
    )
    
    # Create a mapping of block to join_code
    block_to_join_code = {}
    for block, join_code in teacher_blocks:
        if block and join_code:
            block_to_join_code[block] = join_code
    
    # If no blocks available, create a default mapping
    if not block_to_join_code:
        flash("No periods/blocks found. Please add students to periods first.", "error")
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        try:
            # Process each student assignment
            for student in students_needing_backfill:
                block_key = f"student_{student.id}_block"
                selected_block = request.form.get(block_key)
                
                if selected_block and selected_block in block_to_join_code:
                    join_code = block_to_join_code[selected_block]
                    
                    # 1. Update all transactions that have NO join_code
                    #    (CRITICAL: join_code is source of truth, not teacher_id)
                    transactions_to_update = Transaction.query.filter_by(
                        student_id=student.id,
                        join_code=None
                    ).all()
                    
                    for tx in transactions_to_update:
                        # Set join_code (critical for scoping)
                        tx.join_code = join_code
                        # Also set teacher_id if not already set
                        if not tx.teacher_id:
                            tx.teacher_id = current_admin_id
                    
                    # 2. Update student's primary teacher_id if not set
                    if not student.teacher_id:
                        student.teacher_id = current_admin_id
                    
                    # 3. Ensure StudentTeacher association exists
                    _link_student_to_admin(student, current_admin_id)
                    
                    current_app.logger.info(
                        f"Backfilled teacher_id={current_admin_id} and join_code={join_code} "
                        f"for {len(transactions_to_update)} transactions for student {student.id}"
                    )
            
            db.session.commit()
            flash(f"Successfully backfilled transactions for {len(students_needing_backfill)} student(s)! Balances should now be correct.", "success")
            return redirect(url_for('admin.dashboard'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error backfilling transactions: {e}", exc_info=True)
            flash("Error backfilling transactions. Please try again.", "error")
    
    # GET request - show form
    return render_template(
        'admin_backfill_join_codes.html',
        students=students_needing_backfill,
        available_blocks=sorted(block_to_join_code.keys())
    )


# -------------------- AUTHENTICATION --------------------

@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Admin login with TOTP authentication."""
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("last_activity", None)
    form = AdminLoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        totp_code = form.totp_code.data.strip()
        admin = Admin.query.filter_by(username=username).first()
        if admin:
            # Decrypt TOTP secret (handles both encrypted and legacy plaintext)
            decrypted_secret = decrypt_totp(admin.totp_secret)
            totp = pyotp.TOTP(decrypted_secret)
            if totp.verify(totp_code, valid_window=1):
                # Update last login timestamp
                admin.last_login = datetime.now(timezone.utc)
                db.session.commit()

                session["is_admin"] = True
                session["admin_id"] = admin.id
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                flash("Admin login successful.")
                next_url = request.args.get("next")
                if not is_safe_url(next_url):
                    return redirect(url_for("admin.dashboard"))
                return redirect(next_url or url_for("admin.dashboard"))
        flash("Invalid credentials or TOTP code.", "error")
        return redirect(url_for("admin.login", next=request.args.get("next")))
    return render_template("admin_login.html", form=form)


@admin_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    TOTP-only admin registration. Requires valid invite code.
    Uses AdminSignupForm for CSRF and validation.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    form = AdminSignupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        invite_code = form.invite_code.data.strip()
        dob_input = form.dob_sum.data
        totp_code = request.form.get("totp_code", "").strip()

        # Validate and parse DOB sum
        try:
            if isinstance(dob_input, str):
                dob_input = dob_input.strip()
                dob_input = datetime.strptime(dob_input, "%Y-%m-%d").date()
            dob_sum = dob_input.month + dob_input.day + dob_input.year
        except (ValueError, AttributeError, TypeError):
            current_app.logger.warning(f"🛑 Admin signup failed: invalid DOB input")
            msg = "Invalid date of birth. Please enter a valid date."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        # Step 1: Validate invite code
        code_row = db.session.execute(
            text("SELECT * FROM admin_invite_codes WHERE code = :code"),
            {"code": invite_code}
        ).fetchone()
        if not code_row:
            current_app.logger.warning(f"🛑 Admin signup failed: invalid invite code")
            msg = "Invalid invite code."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        if code_row.used:
            current_app.logger.warning(f"🛑 Admin signup failed: invite code already used")
            msg = "Invite code already used."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        if code_row.expires_at and code_row.expires_at < datetime.now(timezone.utc):
            current_app.logger.warning(f"🛑 Admin signup failed: invite code expired")
            msg = "Invite code expired."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        # Step 2: Check username uniqueness
        if Admin.query.filter_by(username=username).first():
            current_app.logger.warning(f"🛑 Admin signup failed: username already exists")
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
            session["admin_dob_sum"] = dob_sum
        else:
            totp_secret = session["admin_totp_secret"]
            dob_sum = session.get("admin_dob_sum", dob_sum)
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
        # Step 4: If no TOTP code submitted yet, show QR
        if not totp_code:
            # Generate QR code in-memory
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            form = AdminTOTPConfirmForm()
            return render_template(
                "admin_signup_totp.html",
                form=form,
                username=username,
                invite_code=invite_code,
                dob_sum=dob_sum,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 5: Validate entered TOTP code
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(totp_code):
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
            return render_template(
                "admin_signup_totp.html",
                form=form,
                username=username,
                invite_code=invite_code,
                dob_sum=dob_sum,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 6: Create admin account and mark invite as used
        # Hash DOB sum
        salt = get_random_salt()
        dob_sum_str = str(dob_sum).encode()
        dob_sum_hash = hash_hmac(dob_sum_str, salt)

        # Encrypt TOTP secret before storing
        encrypted_totp_secret = encrypt_totp(totp_secret)
        new_admin = Admin(username=username, totp_secret=encrypted_totp_secret, dob_sum_hash=dob_sum_hash, salt=salt)
        db.session.add(new_admin)
        db.session.execute(
            text("UPDATE admin_invite_codes SET used = TRUE WHERE code = :code"),
            {"code": invite_code}
        )
        db.session.commit()
        # Clear session
        session.pop("admin_totp_secret", None)
        session.pop("admin_totp_username", None)
        session.pop("admin_dob_sum", None)
        msg = "Admin account created successfully! Please log in using your authenticator app."
        if is_json:
            return jsonify(status="success", message=msg)
        flash(msg, "success")
        return redirect(url_for("admin.login"))
    # GET or invalid POST: render signup form with form instance (for CSRF)
    return render_template("admin_signup.html", form=form)


@admin_bp.route('/recover', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def recover():
    """
    Teacher account recovery - Step 1: Create recovery request.
    Students must verify with passphrase to generate recovery codes.
    Rate limited to prevent brute force attacks on DOB sum.
    """
    form = AdminRecoveryForm()
    if form.validate_on_submit():
        student_usernames_str = form.student_usernames.data.strip()
        dob_input = form.dob_sum.data

        # Parse DOB and calculate sum
        try:
            if isinstance(dob_input, str):
                dob_input = dob_input.strip()
                dob_input = datetime.strptime(dob_input, "%Y-%m-%d").date()
            dob_sum = dob_input.month + dob_input.day + dob_input.year
        except (ValueError, AttributeError, TypeError):
            flash("Invalid date of birth. Please enter a valid date.", "error")
            return render_template("admin_recover.html", form=form)

        # Parse student usernames
        student_usernames = [u.strip() for u in student_usernames_str.split(',') if u.strip()]
        if not student_usernames:
            flash("Please provide at least one student username.", "error")
            return render_template("admin_recover.html", form=form)

        # Find students by username
        students_by_username = {}
        for username in student_usernames:
            # FIX: Use username_lookup_hash for reliable lookup
            lookup_hash = hash_username_lookup(username)
            student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()
            if not student:
                # Try looking up by exact username (for legacy or testing)
                student = Student.query.filter_by(username=username).first()
            if student:
                students_by_username[username] = student

        if not students_by_username:
            flash("No matching students found. Please check the usernames.", "error")
            return render_template("admin_recover.html", form=form)

        # Find common teacher for all students
        teacher_ids = set()
        for username, student in students_by_username.items():
            if student.teacher_id:
                teacher_ids.add(student.teacher_id)

        if len(teacher_ids) != 1:
            flash("The provided students do not all belong to the same teacher.", "error")
            return render_template("admin_recover.html", form=form)

        teacher_id = teacher_ids.pop()
        teacher = Admin.query.get(teacher_id)

        if not teacher or not teacher.dob_sum_hash:
            flash("Teacher account not configured for recovery.", "error")
            return render_template("admin_recover.html", form=form)

        # Verify DOB sum hash
        dob_sum_str = str(dob_sum).encode()
        expected_hash = hash_hmac(dob_sum_str, teacher.salt)

        if teacher.dob_sum_hash != expected_hash:
            current_app.logger.warning(f"🛑 Admin recovery failed: DOB sum mismatch for teacher {teacher_id}")
            flash("Unable to verify your identity. Please check your DOB sum.", "error")
            return render_template("admin_recover.html", form=form)

        # Enforce 'One from each period' policy
        # Get all active blocks for this teacher
        from app.models import TeacherBlock
        teacher_blocks_query = (
            Student.query
            .join(StudentTeacher, Student.id == StudentTeacher.student_id)
            .filter(StudentTeacher.admin_id == teacher_id)
            .with_entities(Student.block)
            .distinct()
        )

        teacher_blocks = set()
        for (blocks_str,) in teacher_blocks_query.all():
            if blocks_str:
                teacher_blocks.update([b.strip().upper() for b in blocks_str.split(',') if b.strip()])

        # Determine blocks covered by selected students
        selected_blocks = set()
        for s in students_by_username.values():
            if s.block:
                selected_blocks.update([b.strip().upper() for b in s.block.split(',') if b.strip()])

        # Verify coverage
        missing_blocks = teacher_blocks - selected_blocks
        if missing_blocks:
            flash(f"You must select at least one student from each of your active periods. Missing: {', '.join(sorted(missing_blocks))}", "error")
            return render_template("admin_recover.html", form=form)

        # Verify student count matches or exceeds block count
        if len(students_by_username) < len(teacher_blocks):
             flash(f"Please select at least {len(teacher_blocks)} students (one from each period).", "error")
             return render_template("admin_recover.html", form=form)

        # Check for existing active recovery request
        existing_request = RecoveryRequest.query.filter_by(
            admin_id=teacher.id,
            status='pending'
        ).filter(
            RecoveryRequest.expires_at > datetime.now(timezone.utc)
        ).first()

        if existing_request:
            flash("You already have an active recovery request. Please check back or wait for it to expire.", "info")
            session['recovery_request_id'] = existing_request.id
            return redirect(url_for('admin.recovery_status'))

        # Create recovery request (5-day expiration)
        expires_at = datetime.now(timezone.utc) + timedelta(days=5)
        recovery_request = RecoveryRequest(
            admin_id=teacher.id,
            dob_sum_hash=teacher.dob_sum_hash,
            status='pending',
            expires_at=expires_at
        )
        db.session.add(recovery_request)
        db.session.flush()  # Get the ID

        # Create student verification entries
        for username, student in students_by_username.items():
            student_code = StudentRecoveryCode(
                recovery_request_id=recovery_request.id,
                student_id=student.id
            )
            db.session.add(student_code)

        db.session.commit()

        session['recovery_request_id'] = recovery_request.id
        current_app.logger.info(f"🔐 Admin recovery: request created for teacher {teacher.id}, expires {expires_at}")

        flash(f"Recovery request created! Your students have been notified. You have 5 days to complete this process.", "success")
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

    recovery_request = RecoveryRequest.query.get(recovery_request_id)
    if not recovery_request:
        flash("Recovery request not found.", "error")
        session.pop('recovery_request_id', None)
        return redirect(url_for('admin.recover'))

    # Check if expired (handle timezone-naive datetimes from SQLite)
    expires_at = recovery_request.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        recovery_request.status = 'expired'
        db.session.commit()
        flash("Your recovery request has expired. Please start a new recovery.", "error")
        session.pop('recovery_request_id', None)
        return redirect(url_for('admin.recover'))

    # Get verification codes
    codes = StudentRecoveryCode.query.filter_by(recovery_request_id=recovery_request.id).all()
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

    recovery_request = RecoveryRequest.query.get(recovery_request_id)
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
        student_codes = StudentRecoveryCode.query.filter_by(
            recovery_request_id=recovery_request.id
        ).all()

        # Verify all students have generated codes
        if any(sc.code_hash is None for sc in student_codes):
            flash("Not all students have verified yet. Please wait for all students to generate their recovery codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Verify count matches
        if len(entered_codes) != len(student_codes):
            current_app.logger.warning(f"🛑 Admin recovery: code count mismatch for request {recovery_request.id} - expected {len(student_codes)}, got {len(entered_codes)}")
            # Invalidate ALL codes
            _invalidate_all_recovery_codes(student_codes)
            flash(f"Wrong number of codes entered. All codes have been invalidated. Your students must generate new codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Verify entered codes match (in any order)
        entered_hashes = set()
        for code in entered_codes:
            # Validate format
            if not code.isdigit() or len(code) != 6:
                current_app.logger.warning(f"🛑 Admin recovery: invalid code format for request {recovery_request.id}")
                _invalidate_all_recovery_codes(student_codes)
                flash("Invalid code format detected. All codes have been invalidated. Your students must generate new codes.", "error")
                return redirect(url_for('admin.recovery_status'))
            # Hash the entered code (no salt for recovery codes - they're already random)
            code_hash = hash_hmac(code.encode(), b'')
            entered_hashes.add(code_hash)

        stored_hashes = set(sc.code_hash for sc in student_codes)

        if entered_hashes != stored_hashes:
            current_app.logger.warning(f"🛑 Admin recovery: code mismatch for request {recovery_request.id}")
            # Invalidate ALL codes on failed attempt
            _invalidate_all_recovery_codes(student_codes)
            flash("Recovery codes do not match. All codes have been invalidated. Your students must generate new codes.", "error")
            return redirect(url_for('admin.recovery_status'))

        # Check username uniqueness
        existing_admin = Admin.query.filter_by(username=new_username).first()
        if existing_admin and existing_admin.id != recovery_request.admin_id:
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


def _invalidate_all_recovery_codes(student_codes):
    """
    Invalidate all recovery codes forcing students to regenerate new ones.
    This prevents attackers from testing codes individually.
    """
    for sc in student_codes:
        sc.code_hash = None
        sc.verified_at = None
    db.session.commit()
    current_app.logger.info(f"🔄 Invalidated {len(student_codes)} recovery codes - students must regenerate")


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

    recovery_request = RecoveryRequest.query.get(recovery_request_id)
    if not recovery_request:
        flash("Invalid recovery session.", "error")
        return redirect(url_for('admin.recover'))

    teacher = Admin.query.get(recovery_request.admin_id)
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
    teacher.username = new_username
    teacher.totp_secret = encrypt_totp(totp_secret)  # Encrypt before storing

    # Mark recovery request as completed
    recovery_request.status = 'verified'
    recovery_request.completed_at = datetime.now(timezone.utc)

    db.session.commit()

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

    recovery_request = RecoveryRequest.query.get(recovery_request_id)
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
    recovery_request.partial_codes = entered_codes
    recovery_request.resume_pin_hash = resume_pin_hash
    recovery_request.resume_new_username = new_username
    db.session.commit()

    current_app.logger.info(f"💾 Admin recovery: saved partial progress for request {recovery_request.id}")

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

    recovery_request = RecoveryRequest.query.filter_by(
        resume_pin_hash=resume_pin_hash,
        status='pending'
    ).filter(
        RecoveryRequest.expires_at > datetime.now(timezone.utc)
    ).first()

    if not recovery_request:
        current_app.logger.warning(f"🛑 Admin recovery: invalid resume PIN attempt")
        flash("Invalid or expired resume PIN. Please check your PIN or start a new recovery.", "error")
        return render_template("admin_resume_credentials.html")

    # Set session and redirect to reset credentials with saved progress
    session['recovery_request_id'] = recovery_request.id
    session['resume_mode'] = True

    current_app.logger.info(f"🔄 Admin recovery: resumed progress for request {recovery_request.id}")
    flash(f"Progress resumed! You have {len(recovery_request.partial_codes or [])} code(s) already saved.", "info")
    return redirect(url_for('admin.reset_credentials'))


@admin_bp.route('/setup-recovery', methods=['GET', 'POST'])
@admin_required
def setup_recovery():
    """Prompt legacy teachers to set up account recovery (DOB sum)."""
    admin = Admin.query.get(session['admin_id'])

    if request.method == 'POST':
        dob_sum_str = request.form.get('dob_sum', '').strip()

        try:
            dob_sum = int(dob_sum_str)
            if dob_sum <= 0:
                raise ValueError("Positive number required")

            # Hash and save
            salt = get_random_salt()
            dob_sum_hash = hash_hmac(str(dob_sum).encode(), salt)

            admin.dob_sum_hash = dob_sum_hash
            admin.salt = salt
            db.session.commit()

            flash("Recovery setup complete! You can now use the student-assisted recovery feature if needed.", "success")
            return redirect(url_for('admin.dashboard'))

        except ValueError:
            flash("Invalid Date of Birth Sum. Please enter a number (e.g. 2028).", "error")

    return render_template('admin_setup_recovery.html')


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Teacher account settings - configure display name and class labels."""
    admin_id = session.get("admin_id")
    admin = Admin.query.get_or_404(admin_id)

    if request.method == 'POST':
        # Update display name
        display_name = request.form.get('display_name', '').strip()
        if display_name:
            admin.display_name = display_name
        else:
            admin.display_name = None  # Use username as fallback

        # Update class labels for each block
        blocks = TeacherBlock.query.filter_by(teacher_id=admin_id).distinct(TeacherBlock.block).all()
        for block in blocks:
            class_label_key = f'class_label_{block.block}'
            class_label = request.form.get(class_label_key, '').strip()

            # Update all TeacherBlock entries with this block value
            TeacherBlock.query.filter_by(
                teacher_id=admin_id,
                block=block.block
            ).update({'class_label': class_label if class_label else None})

        db.session.commit()
        flash("Settings updated successfully!", "success")
        return redirect(url_for('admin.settings'))

    # GET: Show settings form
    # Get unique blocks for this teacher
    blocks = db.session.query(TeacherBlock.block, TeacherBlock.class_label)\
        .filter_by(teacher_id=admin_id)\
        .distinct(TeacherBlock.block)\
        .all()

    return render_template(
        'admin_settings.html',
        admin=admin,
        blocks=blocks,
        current_page='settings',
        page_title='Account Settings'
    )


@admin_bp.route('/logout')
def logout():
    """Admin logout."""
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("last_activity", None)
    flash("Logged out.")
    return redirect(url_for("admin.login"))


# -------------------- STUDENT MANAGEMENT --------------------

@admin_bp.route('/students')
@admin_required
def students():
    """View all students with basic information organized by block."""
    current_admin = session.get('admin_id')

    # Backfill any legacy credential hashes to the canonical format for this admin's data
    updated_records = _normalize_claim_credentials_for_admin(current_admin)
    if updated_records:
        current_app.logger.info(
            "Normalized %s student/seat claim credential(s) for admin %s", updated_records, current_admin
        )

    # Get claimed students (Student records)
    all_students = _scoped_students().order_by(Student.block, Student.first_name).all()

    # Get ALL TeacherBlock records (both claimed and unclaimed seats)
    teacher_blocks = TeacherBlock.query.filter_by(teacher_id=current_admin).all()

    # Collect all blocks from both students and teacher_blocks
    blocks_set = set()

    # Add blocks from claimed students
    for s in all_students:
        if s.block:
            for b in s.block.split(','):
                b = b.strip().upper()
                if b:
                    blocks_set.add(b)

    # Add blocks from TeacherBlock records (including unclaimed)
    for tb in teacher_blocks:
        if tb.block:
            blocks_set.add(tb.block.strip().upper())

    blocks = sorted(blocks_set)

    # Check if there are any students without block assignments
    unassigned_students = [s for s in all_students if not s.block or not s.block.strip()]
    if unassigned_students:
        # Add "Unassigned" as a special block at the beginning
        blocks = ["Unassigned"] + blocks

    # Group students by block (students can appear in multiple blocks)
    students_by_block = {}

    # Handle unassigned students first
    if unassigned_students:
        students_by_block["Unassigned"] = unassigned_students

    # Group students by their assigned blocks
    for block in blocks:
        if block != "Unassigned":  # Skip the special "Unassigned" block
            students_by_block[block] = [
                s for s in all_students
                if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
            ]

    # Add username_display attribute to each student
    for student in all_students:
        if student.username_hash and student.has_completed_setup:
            # Username is hashed, we need to display a placeholder
            student.username_display = f"user_{student.id}"
        else:
            student.username_display = "Not Set"

    # Fetch join codes, class labels, and unclaimed seats for each block
    join_codes_by_block = {}
    class_labels_by_block = {}
    unclaimed_seats_by_block = {}
    unclaimed_seats_list_by_block = {}

    # Process teacher_blocks in one pass to build all required structures
    for tb in teacher_blocks:
        block_name = tb.block.strip().upper() if tb.block else None
        if block_name:
            # Initialize structures if needed
            if block_name not in unclaimed_seats_list_by_block:
                unclaimed_seats_list_by_block[block_name] = []
                # Store the first join code we encounter for this block.
                # All TeacherBlock records for the same block should have the same join_code
                # (enforced by roster import logic), so taking the first one is correct.
                join_codes_by_block[block_name] = tb.join_code
                # Store class label (use the first one; they should all be the same for a given block)
                class_labels_by_block[block_name] = tb.get_class_label()
                unclaimed_seats_by_block[block_name] = 0

            # Track unclaimed seats (excluding legacy placeholders)
            if not tb.is_claimed and tb.first_name != LEGACY_PLACEHOLDER_FIRST_NAME:
                unclaimed_seats_list_by_block[block_name].append(tb)
                unclaimed_seats_by_block[block_name] += 1

    # Ensure all blocks with students have join codes (for legacy teachers with pre-c3aa3a0 classes)
    # If a block has students but no TeacherBlock records, look up or generate a join code
    # Fetch all claimed TeacherBlock records for current admin upfront
    claimed_tb_by_block = {tb.block: tb for tb in teacher_blocks if tb.block and tb.is_claimed}
    for block in blocks:
        if block != "Unassigned" and block not in join_codes_by_block:
            # This block has students but no TeacherBlock records yet
            # Check if there are any claimed TeacherBlock records for this teacher-block combination
            existing_tb = claimed_tb_by_block.get(block)
            
            if existing_tb and existing_tb.join_code:
                # Use existing join code from claimed seat
                join_codes_by_block[block] = existing_tb.join_code
            else:
                # No join code exists for this block yet - generate a new unique one
                # Try up to 10 times to generate a unique code to prevent infinite loops
                new_code = None
                for _ in range(MAX_JOIN_CODE_RETRIES):
                    new_code = generate_join_code()
                    # Ensure uniqueness across all teachers
                    if not TeacherBlock.query.filter_by(join_code=new_code).first():
                        join_codes_by_block[block] = new_code
                        # Persist the new join code to the database to prevent race conditions
                        # Create a placeholder TeacherBlock with dummy values to satisfy NOT NULL constraints
                        # This is for legacy classes that don't have TeacherBlock entries yet
                        placeholder_salt = get_random_salt()
                        placeholder_first_half_hash = hash_hmac(LEGACY_PLACEHOLDER_CREDENTIAL.encode(), placeholder_salt)
                        
                        new_teacher_block = TeacherBlock(
                            teacher_id=current_admin,
                            block=block,
                            join_code=new_code,
                            is_claimed=False,
                            # Placeholder values for required fields
                            first_name=LEGACY_PLACEHOLDER_FIRST_NAME,
                            last_initial=LEGACY_PLACEHOLDER_LAST_INITIAL,
                            last_name_hash_by_part=[],
                            dob_sum=0,
                            salt=placeholder_salt,
                            first_half_hash=placeholder_first_half_hash,
                        )
                        db.session.add(new_teacher_block)
                        try:
                            db.session.commit()
                        except Exception as e:
                            current_app.logger.error(f"Failed to persist TeacherBlock for block {block} with join code {new_code}: {e}")
                            db.session.rollback()
                        break
                else:
                    # If we couldn't generate a unique code after max_retries, use a timestamp-based fallback
                    # Format: B + block_initial + timestamp_suffix (e.g., "BA0123" for block "A")
                    # This produces a 6-character code: B(1) + block_initial(1) + timestamp(4) = 6 total
                    block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                    timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                    new_code = f"B{block_initial}{timestamp_suffix:04d}"
                    join_codes_by_block[block] = new_code
                    current_app.logger.warning(
                        f"Failed to generate unique join code after {MAX_JOIN_CODE_RETRIES} attempts. "
                        f"Using fallback code {new_code} for block {block}"
                    )
            
            # Initialize unclaimed seats counter for this block
            if block not in unclaimed_seats_by_block:
                unclaimed_seats_by_block[block] = 0
                unclaimed_seats_list_by_block[block] = []

    return render_template('admin_students.html',
                         students=all_students,
                         blocks=blocks,
                         students_by_block=students_by_block,
                         join_codes_by_block=join_codes_by_block,
                         class_labels_by_block=class_labels_by_block,
                         unclaimed_seats_by_block=unclaimed_seats_by_block,
                         unclaimed_seats_list_by_block=unclaimed_seats_list_by_block,
                         current_page="students")


@admin_bp.route('/students/<int:student_id>')
@admin_required
def student_detail(student_id):
    """View detailed information for a specific student."""
    student = _get_student_or_404(student_id)
    # Remove deprecated last_tap_in/last_tap_out logic; rely on TapEvent backend.
    # Fetch last rent payment
    latest_rent = Transaction.query.filter_by(student_id=student.id, type="rent").order_by(Transaction.timestamp.desc()).first()
    student.rent_last_paid = latest_rent.timestamp if latest_rent else None

    # Fetch last property tax payment
    latest_tax = Transaction.query.filter_by(student_id=student.id, type="property_tax").order_by(Transaction.timestamp.desc()).first()
    student.property_tax_last_paid = latest_tax.timestamp if latest_tax else None

    # Compute due dates and overdue status
    from datetime import date
    today = datetime.now(PACIFIC).date()
    # Rent due on 5th, overdue after 6th
    rent_due = date(today.year, today.month, 5)
    student.rent_due_date = rent_due
    student.rent_overdue = today > rent_due and (not student.rent_last_paid or student.rent_last_paid.astimezone(PACIFIC).date() <= rent_due)

    # Property tax due on 5th, overdue after 6th
    tax_due = date(today.year, today.month, 5)
    student.property_tax_due_date = tax_due
    student.property_tax_overdue = today > tax_due and (not student.property_tax_last_paid or student.property_tax_last_paid.astimezone(PACIFIC).date() <= tax_due)

    transactions = Transaction.query.filter_by(student_id=student.id).order_by(Transaction.timestamp.desc()).all()
    student_items = student.items.order_by(StudentItem.purchase_date.desc()).all()
    # Fetch most recent TapEvent for this student
    latest_tap_event = TapEvent.query.filter_by(student_id=student.id).order_by(TapEvent.timestamp.desc()).first()

    # Get student's active insurance policy (scoped to current teacher)
    teacher_id = session.get('admin_id')
    active_insurance = student.get_active_insurance(teacher_id)

    # Get all blocks for the edit modal
    all_students = _scoped_students().all()
    blocks = sorted({b.strip() for s in all_students for b in (s.block or "").split(',') if b.strip()})

    # Get StudentBlock settings for this student
    from app.models import StudentBlock
    student_blocks_settings = {}
    student_periods = [b.strip().upper() for b in (student.block or "").split(',') if b.strip()]
    for period in student_periods:
        student_block = StudentBlock.query.filter_by(
            student_id=student.id,
            period=period
        ).first()
        student_blocks_settings[period] = {
            'tap_enabled': student_block.tap_enabled if student_block else True,
            'done_for_day_date': student_block.done_for_day_date if student_block else None
        }

    return render_template('student_detail.html', student=student, transactions=transactions, student_items=student_items, latest_tap_event=latest_tap_event, active_insurance=active_insurance, blocks=blocks, student_blocks_settings=student_blocks_settings)


@admin_bp.route('/student/<int:student_id>/set-hall-passes', methods=['POST'])
@admin_required
def set_hall_passes(student_id):
    """Set hall pass balance for a student."""
    student = _get_student_or_404(student_id)
    new_balance = request.form.get('hall_passes', type=int)

    if new_balance is not None and new_balance >= 0:
        student.hall_passes = new_balance
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s hall pass balance to {new_balance}.", "success")
    else:
        flash("Invalid hall pass balance provided.", "error")

    return redirect(url_for('admin.student_detail', student_id=student_id))


@admin_bp.route('/student/edit', methods=['POST'])
@admin_required
def edit_student():
    """Edit student basic information."""
    student_id = request.form.get('student_id', type=int)
    current_admin_id = session.get('admin_id')

    # Try to get student from scoped query first
    student = get_student_for_admin(student_id)

    # If not found in scoped query, check if it's a legacy student (has teacher_id but no StudentTeacher record)
    if not student:
        student = Student.query.get(student_id)
        if student and student.teacher_id == current_admin_id:
            # This is a legacy student - create StudentTeacher association to upgrade them
            existing_st = StudentTeacher.query.filter_by(
                student_id=student.id,
                admin_id=current_admin_id
            ).first()

            if not existing_st:
                db.session.add(StudentTeacher(
                    student_id=student.id,
                    admin_id=current_admin_id
                ))
                db.session.flush()
        else:
            # Not accessible by this admin
            abort(404)
    else:
        # Student found in scoped query, but check if we need to create StudentTeacher for legacy data
        if student.teacher_id == current_admin_id:
            existing_st = StudentTeacher.query.filter_by(
                student_id=student.id,
                admin_id=current_admin_id
            ).first()

            if not existing_st:
                db.session.add(StudentTeacher(
                    student_id=student.id,
                    admin_id=current_admin_id
                ))
                db.session.flush()

    # Get form data
    new_first_name = request.form.get('first_name', '').strip()
    last_name_input = request.form.get('last_name', '').strip()
    new_last_initial = last_name_input[0].upper() if last_name_input else student.last_initial

    # Get selected blocks (multiple checkboxes)
    selected_blocks = request.form.getlist('blocks')

    # Join blocks with commas (e.g., "A,B,C")
    # At least one block is required for tap/hall pass functionality to work
    if selected_blocks:
        new_blocks = ','.join(sorted(b.strip().upper() for b in selected_blocks))
    else:
        # No blocks selected - this would break tap/hall pass functionality
        flash("At least one block must be selected.", "error")
        return redirect(url_for('admin.student_detail', student_id=student_id))

    # Track old blocks for TeacherBlock updates
    old_blocks = set(b.strip().upper() for b in (student.block or '').split(',') if b.strip())
    new_blocks_set = set(b.strip().upper() for b in selected_blocks)

    # Check if name changed (need to recalculate hashes)
    name_changed = (new_first_name != student.first_name or new_last_initial != student.last_initial)
    dob_changed = False

    # Update basic fields
    student.first_name = new_first_name
    student.last_initial = new_last_initial
    student.block = new_blocks

    # If name changed, refresh last name hashes
    if name_changed:
        student.last_name_hash_by_part = hash_last_name_parts(last_name_input, student.salt)

    # Update DOB sum if provided (and recalculate second_half_hash)
    dob_sum_str = request.form.get('dob_sum', '').strip()
    if dob_sum_str:
        new_dob_sum = int(dob_sum_str)
        if new_dob_sum != student.dob_sum:
            student.dob_sum = new_dob_sum
            # Regenerate second_half_hash (DOB sum hash)
            student.second_half_hash = hash_hmac(str(new_dob_sum).encode(), student.salt)
            dob_changed = True

    if name_changed or dob_changed:
        claim_hash = compute_primary_claim_hash(new_first_name[:1], student.dob_sum, student.salt)
        if claim_hash:
            student.first_half_hash = claim_hash

    # Handle login reset
    reset_login = request.form.get('reset_login') == 'on'
    if reset_login:
        # Clear login credentials but keep account data
        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False
        
        # Update TeacherBlock entries to mark them as unclaimed
        # Keep student_id since the student record still exists
        TeacherBlock.query.filter_by(
            student_id=student.id,
            teacher_id=current_admin_id
        ).update({
            'is_claimed': False,
            'claimed_at': None
        })

        flash(f"{student.full_name}'s login has been reset. They will need to re-claim their account.", "warning")

    if name_changed or dob_changed:
        TeacherBlock.query.filter_by(
            student_id=student.id,
            teacher_id=current_admin_id
        ).update({
            'first_name': student.first_name,
            'last_initial': student.last_initial,
            'last_name_hash_by_part': student.last_name_hash_by_part or [],
            'dob_sum': student.dob_sum or 0,
            'first_half_hash': student.first_half_hash,
        })

    # Handle block changes - update TeacherBlock entries
    removed_blocks = old_blocks - new_blocks_set
    added_blocks = new_blocks_set - old_blocks
    
    # For legacy students (those being upgraded), ensure TeacherBlock entries exist
    # for ALL their blocks, not just newly added ones
    # Check if this is a legacy student being upgraded (had no TeacherBlock entries)
    existing_tb_count = TeacherBlock.query.filter_by(
        student_id=student.id,
        teacher_id=current_admin_id
    ).count()
    
    if existing_tb_count == 0:
        # This is a legacy student - ensure TeacherBlock entries for ALL blocks
        blocks_to_ensure = new_blocks_set
    else:
        # Normal case - only create TeacherBlock entries for newly added blocks
        blocks_to_ensure = added_blocks

    # Remove TeacherBlock entries for blocks the student is no longer in
    for block in removed_blocks:
        TeacherBlock.query.filter_by(
            student_id=student.id,
            teacher_id=current_admin_id,
            block=block
        ).delete()

    # Create TeacherBlock entries for blocks that need them (reusing existing join codes)
    for block in blocks_to_ensure:
        # Check if there's already an unclaimed TeacherBlock for this student in this block
        existing_tb = TeacherBlock.query.filter_by(
            teacher_id=current_admin_id,
            block=block,
            student_id=student.id
        ).first()
        
        if not existing_tb:
            # Get join code for this block (from existing TeacherBlock in this block)
            existing_block_tb = TeacherBlock.query.filter_by(
                teacher_id=current_admin_id,
                block=block
            ).first()
            
            if existing_block_tb:
                join_code = existing_block_tb.join_code
            else:
                # Generate a unique join code with bounded retries and fallback
                join_code = None
                for _ in range(MAX_JOIN_CODE_RETRIES):
                    candidate = generate_join_code()
                    if not TeacherBlock.query.filter_by(join_code=candidate).first():
                        join_code = candidate
                        break
                else:
                    # Fallback to timestamp-based code
                    block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                    timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                    join_code = f"B{block_initial}{timestamp_suffix:04d}"
            
            # Student is claimed if they have a username set
            is_claimed = bool(student.username_hash)
                
            # Create new TeacherBlock entry
            # Always link to the student record since it exists
            new_tb = TeacherBlock(
                teacher_id=current_admin_id,
                block=block,
                first_name=student.first_name,
                last_initial=student.last_initial,
                last_name_hash_by_part=student.last_name_hash_by_part or [],
                dob_sum=student.dob_sum or 0,
                salt=student.salt,
                first_half_hash=student.first_half_hash,
                join_code=join_code,
                is_claimed=is_claimed,
                student_id=student.id,  # Always link since student record exists
                claimed_at=datetime.now(timezone.utc) if is_claimed else None
            )
            db.session.add(new_tb)

    try:
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s information.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/delete', methods=['GET', 'POST'])
@admin_required
def delete_student():
    """Delete a student and all associated data."""
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
        flash("Deletion cancelled: confirmation text did not match.", "warning")
        return redirect(url_for('admin.students'))

    student = _get_student_or_404(student_id)
    student_name = student.full_name

    try:
        # Delete associated records (cascade should handle this, but being explicit)
        Transaction.query.filter_by(student_id=student.id).delete()
        TapEvent.query.filter_by(student_id=student.id).delete()
        StudentItem.query.filter_by(student_id=student.id).delete()
        RentPayment.query.filter_by(student_id=student.id).delete()
        StudentInsurance.query.filter_by(student_id=student.id).delete()
        HallPassLog.query.filter_by(student_id=student.id).delete()
        
        # Delete StudentTeacher associations
        StudentTeacher.query.filter_by(student_id=student.id).delete()

        # Delete TeacherBlock entries for this student
        TeacherBlock.query.filter_by(student_id=student.id).delete()

        # Delete StudentBlock entries for this student
        StudentBlock.query.filter_by(student_id=student.id).delete()

        # Delete the student
        db.session.delete(student)
        db.session.commit()

        flash(f"Successfully deleted {student_name} and all associated data.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_students():
    """Delete multiple students at once."""
    data = request.get_json()
    student_ids = data.get('student_ids', [])

    if not student_ids:
        return jsonify({"status": "error", "message": "No students selected."}), 400

    try:
        deleted_count = 0
        for student_id in student_ids:
            student = _get_student_or_404(student_id)
            if student:
                # Delete associated records
                Transaction.query.filter_by(student_id=student.id).delete()
                TapEvent.query.filter_by(student_id=student.id).delete()
                StudentItem.query.filter_by(student_id=student.id).delete()
                RentPayment.query.filter_by(student_id=student.id).delete()
                RentWaiver.query.filter_by(student_id=student.id).delete()
                StudentInsurance.query.filter_by(student_id=student.id).delete()
                InsuranceClaim.query.filter_by(student_id=student.id).delete()
                HallPassLog.query.filter_by(student_id=student.id).delete()
                
                # Delete StudentTeacher associations
                StudentTeacher.query.filter_by(student_id=student.id).delete()

                # Delete TeacherBlock entries for this student
                TeacherBlock.query.filter_by(student_id=student.id).delete()

                # Delete StudentBlock entries for this student
                StudentBlock.query.filter_by(student_id=student.id).delete()

                # Delete the student
                db.session.delete(student)
                deleted_count += 1

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted {deleted_count} student(s) and all associated data."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/students/delete-block', methods=['POST'])
@admin_required
def delete_block():
    """Delete all students in a specific block."""
    data = request.get_json()
    block = data.get('block', '').strip().upper()
    current_admin_id = session.get('admin_id')

    if not block:
        return jsonify({"status": "error", "message": "No block specified."}), 400

    try:
        # Get all students in this block that the current admin can access
        students = _scoped_students().filter_by(block=block).all()
        student_ids = [s.id for s in students]
        deleted_count = len(students)
        
        current_app.logger.info(f"Deleting block {block} with {deleted_count} students (IDs: {student_ids})")

        if deleted_count > 0:
            # Delete all associated records in bulk where possible to avoid N+1 queries
            # Using synchronize_session=False to avoid session synchronization issues
            Transaction.query.filter(Transaction.student_id.in_(student_ids)).delete(synchronize_session=False)
            TapEvent.query.filter(TapEvent.student_id.in_(student_ids)).delete(synchronize_session=False)
            StudentItem.query.filter(StudentItem.student_id.in_(student_ids)).delete(synchronize_session=False)
            RentPayment.query.filter(RentPayment.student_id.in_(student_ids)).delete(synchronize_session=False)
            RentWaiver.query.filter(RentWaiver.student_id.in_(student_ids)).delete(synchronize_session=False)
            StudentInsurance.query.filter(StudentInsurance.student_id.in_(student_ids)).delete(synchronize_session=False)
            InsuranceClaim.query.filter(InsuranceClaim.student_id.in_(student_ids)).delete(synchronize_session=False)
            HallPassLog.query.filter(HallPassLog.student_id.in_(student_ids)).delete(synchronize_session=False)
            
            # Delete StudentTeacher associations
            StudentTeacher.query.filter(StudentTeacher.student_id.in_(student_ids)).delete(synchronize_session=False)

            # Delete TeacherBlock entries for these students
            TeacherBlock.query.filter(TeacherBlock.student_id.in_(student_ids)).delete(synchronize_session=False)

            # Delete StudentBlock entries for these students
            StudentBlock.query.filter(StudentBlock.student_id.in_(student_ids)).delete(synchronize_session=False)

            # Flush to ensure all associated records are deleted before deleting students
            db.session.flush()
            
            # Delete the students themselves
            for student in students:
                db.session.delete(student)
            
            # Flush student deletions
            db.session.flush()

        # Also delete unclaimed TeacherBlock entries for this block and teacher
        unclaimed_deleted = TeacherBlock.query.filter(
            TeacherBlock.teacher_id == current_admin_id,
            TeacherBlock.block == block,
            TeacherBlock.student_id.is_(None)
        ).delete(synchronize_session=False)
        
        current_app.logger.info(f"Deleted {unclaimed_deleted} unclaimed TeacherBlock entries for block {block}")

        # Final commit
        db.session.commit()
        current_app.logger.info(f"Successfully deleted block {block}")
        
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted all {deleted_count} student(s) in Block {block} and all associated data."
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting block {block}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/pending-students/delete', methods=['POST'])
@admin_required
def delete_pending_student():
    """
    Delete a single pending student (unclaimed TeacherBlock entry).
    
    Pending students are roster entries that have not yet been claimed by students.
    This route ensures comprehensive cleanup with no leftover traces.
    """
    data = request.get_json()
    teacher_block_id = data.get('teacher_block_id')
    if teacher_block_id:
        try:
            teacher_block_id = int(teacher_block_id)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid teacher block ID."}), 400
    
    current_admin_id = session.get('admin_id')

    if not teacher_block_id:
        return jsonify({"status": "error", "message": "No teacher block ID provided."}), 400

    try:
        # Find the TeacherBlock entry
        teacher_block = TeacherBlock.query.filter_by(
            id=teacher_block_id,
            teacher_id=current_admin_id
        ).first()

        if not teacher_block:
            return jsonify({"status": "error", "message": "Pending student not found or access denied."}), 404

        # Verify it's actually unclaimed
        if teacher_block.is_claimed or teacher_block.student_id is not None:
            return jsonify({
                "status": "error",
                "message": "This seat has already been claimed. Use the regular student deletion route instead."
            }), 400

        student_name = f"{teacher_block.first_name} {teacher_block.last_initial}."
        
        # Delete the TeacherBlock entry (this is the only record for unclaimed seats)
        db.session.delete(teacher_block)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Successfully deleted pending student {student_name}."
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting pending student: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/pending-students/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_pending_students():
    """
    Delete multiple pending students (unclaimed TeacherBlock entries) at once.
    
    This route ensures comprehensive cleanup with no leftover traces.
    Accepts a list of TeacherBlock IDs or a block name to delete all pending students in that block.
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
            # Delete all unclaimed TeacherBlock entries for this teacher and block
            deleted_count = TeacherBlock.query.filter(
                TeacherBlock.teacher_id == current_admin_id,
                TeacherBlock.block == block,
                TeacherBlock.is_claimed.is_(False),
                TeacherBlock.student_id.is_(None)
            ).delete(synchronize_session=False)
        else:
            # Delete specific TeacherBlock entries
            for tb_id in teacher_block_ids:
                teacher_block = TeacherBlock.query.filter_by(
                    id=tb_id,
                    teacher_id=current_admin_id
                ).first()

                if teacher_block:
                    # Verify it's actually unclaimed
                    if not teacher_block.is_claimed and teacher_block.student_id is None:
                        db.session.delete(teacher_block)
                        deleted_count += 1

        db.session.commit()
        
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
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/legacy-unclaimed-students/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_legacy_unclaimed_students():
    """
    Delete multiple legacy unclaimed students (Student records without username_hash) at once.
    
    Legacy unclaimed students are Student records that exist but don't have a username_hash set yet.
    This route ensures comprehensive cleanup with no leftover traces.
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
        
        deleted_count = 0
        for student in students:
            # Delete associated records
            Transaction.query.filter_by(student_id=student.id).delete()
            TapEvent.query.filter_by(student_id=student.id).delete()
            StudentItem.query.filter_by(student_id=student.id).delete()
            RentPayment.query.filter_by(student_id=student.id).delete()
            RentWaiver.query.filter_by(student_id=student.id).delete()
            StudentInsurance.query.filter_by(student_id=student.id).delete()
            InsuranceClaim.query.filter_by(student_id=student.id).delete()
            HallPassLog.query.filter_by(student_id=student.id).delete()
            
            # Delete StudentTeacher associations
            StudentTeacher.query.filter_by(student_id=student.id).delete()

            # Delete TeacherBlock entries for this student
            TeacherBlock.query.filter_by(student_id=student.id).delete()

            # Delete StudentBlock entries for this student
            StudentBlock.query.filter_by(student_id=student.id).delete()

            # Delete the student
            db.session.delete(student)
            deleted_count += 1

        db.session.commit()
        
        message = f"Successfully deleted {deleted_count} legacy unclaimed student(s) from Block {block}."

        return jsonify({
            "status": "success",
            "message": message,
            "deleted_count": deleted_count
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error bulk deleting legacy unclaimed students: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/student/add-individual', methods=['POST'])
@admin_required
def add_individual_student():
    """Add a single student (same as bulk upload but for one student)."""
    try:
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob', '').strip()
        block = request.form.get('block', '').strip().upper()

        if not all([first_name, last_name, dob_str, block]):
            flash("All fields are required.", "error")
            return redirect(url_for('admin.students'))

        # Generate initials
        first_initial = first_name[0].upper()
        last_initial = last_name[0].upper()

        # Parse DOB and calculate sum
        month, day, year = map(int, dob_str.split('/'))
        dob_sum = month + day + year

        # Generate salt
        salt = get_random_salt()

        # Compute first_half_hash using canonical claim credential (first initial + DOB sum)
        first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, salt)
        second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        last_name_parts = hash_last_name_parts(last_name, salt)

        # Check for duplicates - need to check ALL students GLOBALLY (not scoped to teacher)
        # This prevents creating duplicate accounts when multiple teachers have the same student
        potential_duplicates = Student.query.filter_by(
            last_initial=last_initial,
            dob_sum=dob_sum
        ).all()

        # Check if any existing student matches (using new credential system)
        for existing_student in potential_duplicates:
            if existing_student.first_name == first_name:
                # Verify credential matches
                credential_matches, is_primary, canonical_hash = match_claim_hash(
                    existing_student.first_half_hash,
                    first_initial,
                    last_initial,
                    dob_sum,
                    existing_student.salt,
                )

                # Also check fuzzy last name matching
                fuzzy_match = False
                if existing_student.last_name_hash_by_part:
                    fuzzy_match = verify_last_name_parts(
                        last_name,
                        existing_student.last_name_hash_by_part,
                        existing_student.salt
                    )

                # Match if BOTH credential AND last name match
                if credential_matches and fuzzy_match:
                    if canonical_hash and not is_primary:
                        existing_student.first_half_hash = canonical_hash
                    # Student already exists - link to this teacher instead of creating duplicate
                    current_admin_id = session.get("admin_id")

                    # Check if this teacher is already linked to this student
                    from app.models import StudentTeacher
                    existing_link = StudentTeacher.query.filter_by(
                        student_id=existing_student.id,
                        admin_id=current_admin_id
                    ).first()

                    if existing_link:
                        flash(f"Student {first_name} {last_name} is already in your class.", "info")
                    else:
                        # Link this teacher to the existing student
                        _link_student_to_admin(existing_student, current_admin_id)
                        db.session.commit()
                        flash(f"Student {first_name} {last_name} already exists. Added to your class.", "success")

                    return redirect(url_for('admin.students'))

        # Create student
        current_admin_id = session.get("admin_id")
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=dob_sum,
            last_name_hash_by_part=last_name_parts,
            has_completed_setup=False,
            teacher_id=current_admin_id,
        )

        db.session.add(new_student)
        db.session.flush()
        _link_student_to_admin(new_student, current_admin_id)
        
        # Create TeacherBlock entry for this student
        # Get or generate join code for this block
        existing_tb = TeacherBlock.query.filter_by(
            teacher_id=current_admin_id,
            block=block
        ).first()
        
        if existing_tb:
            join_code = existing_tb.join_code
        else:
            # Generate a unique join code with bounded retries and fallback
            join_code = None
            for _ in range(MAX_JOIN_CODE_RETRIES):
                candidate = generate_join_code()
                if not TeacherBlock.query.filter_by(join_code=candidate).first():
                    join_code = candidate
                    break
            else:
                # Fallback to timestamp-based code
                block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                join_code = f"B{block_initial}{timestamp_suffix:04d}"
        
        new_tb = TeacherBlock(
            teacher_id=current_admin_id,
            block=block,
            first_name=first_name,
            last_initial=last_initial,
            last_name_hash_by_part=last_name_parts,
            dob_sum=dob_sum,
            salt=salt,
            first_half_hash=first_half_hash,
            join_code=join_code,
            is_claimed=False,  # Student hasn't set up username yet
            student_id=new_student.id,
        )
        db.session.add(new_tb)
        
        db.session.commit()

        flash(f"Successfully added {first_name} {last_initial}. to block {block}.", "success")
    except ValueError:
        flash("Invalid date format. Use MM/DD/YYYY.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/add-manual', methods=['POST'])
@admin_required
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
        month, day, year = map(int, dob_str.split('/'))
        dob_sum = month + day + year

        # Generate salt
        salt = get_random_salt()

        # Compute first_half_hash using canonical claim credential (first initial + DOB sum)
        first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, salt)
        second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        last_name_parts = hash_last_name_parts(last_name, salt)

        # Check for duplicates GLOBALLY (not scoped to teacher)
        potential_duplicates = Student.query.filter_by(
            last_initial=last_initial,
            dob_sum=dob_sum
        ).all()

        for existing_student in potential_duplicates:
            if existing_student.first_name == first_name:
                # Verify credential matches (canonical + legacy)
                credential_matches, is_primary, canonical_hash = match_claim_hash(
                    existing_student.first_half_hash,
                    first_initial,
                    last_initial,
                    dob_sum,
                    existing_student.salt,
                )

                # Also check fuzzy last name matching
                fuzzy_match = False
                if existing_student.last_name_hash_by_part:
                    fuzzy_match = verify_last_name_parts(
                        last_name,
                        existing_student.last_name_hash_by_part,
                        existing_student.salt
                    )

                if credential_matches and fuzzy_match:
                    if canonical_hash and not is_primary:
                        existing_student.first_half_hash = canonical_hash
                    flash(f"Student {first_name} {last_name} already exists. Linking to your class.", "warning")
                    # Link to this teacher
                    from app.models import StudentTeacher
                    current_admin_id = session.get("admin_id")
                    existing_link = StudentTeacher.query.filter_by(
                        student_id=existing_student.id,
                        admin_id=current_admin_id
                    ).first()
                    if not existing_link:
                        _link_student_to_admin(existing_student, current_admin_id)
                        db.session.commit()
                    return redirect(url_for('admin.students'))

        # Create student
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=dob_sum,
            last_name_hash_by_part=last_name_parts,
            hall_passes=hall_passes,
            is_rent_enabled=rent_enabled,
            has_completed_setup=setup_complete,
            teacher_id=session.get("admin_id"),
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

        current_admin_id = session.get("admin_id")
        db.session.add(new_student)
        db.session.flush()
        _link_student_to_admin(new_student, current_admin_id)
        
        # Create TeacherBlock entry for this student
        # Get or generate join code for this block
        existing_tb = TeacherBlock.query.filter_by(
            teacher_id=current_admin_id,
            block=block
        ).first()
        
        if existing_tb:
            join_code = existing_tb.join_code
        else:
            # Generate a unique join code with bounded retries and fallback
            join_code = None
            for _ in range(MAX_JOIN_CODE_RETRIES):
                candidate = generate_join_code()
                if not TeacherBlock.query.filter_by(join_code=candidate).first():
                    join_code = candidate
                    break
            else:
                # Fallback to timestamp-based code
                block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                join_code = f"B{block_initial}{timestamp_suffix:04d}"
        
        # Student is claimed if they have a username set
        is_claimed = bool(username)
        
        new_tb = TeacherBlock(
            teacher_id=current_admin_id,
            block=block,
            first_name=first_name,
            last_initial=last_initial,
            last_name_hash_by_part=last_name_parts,
            dob_sum=dob_sum,
            salt=salt,
            first_half_hash=first_half_hash,
            join_code=join_code,
            is_claimed=is_claimed,
            student_id=new_student.id,
            claimed_at=datetime.now(timezone.utc) if is_claimed else None,
        )
        db.session.add(new_tb)
        
        db.session.commit()

        flash(f"Successfully created {first_name} {last_initial}. in block {block} (manual mode).", "success")
    except ValueError:
        flash("Invalid date format. Use MM/DD/YYYY.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


# -------------------- STORE MANAGEMENT --------------------

@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store_management():
    """Manage store items - view, create, edit, delete."""
    admin_id = session.get("admin_id")
    student_ids_subq = _student_scope_subquery()
    form = StoreItemForm()

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    if form.validate_on_submit():
        new_item = StoreItem(
            teacher_id=admin_id,
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            item_type=form.item_type.data,
            inventory=form.inventory.data,
            limit_per_student=form.limit_per_student.data,
            auto_delist_date=form.auto_delist_date.data,
            auto_expiry_days=form.auto_expiry_days.data,
            is_active=form.is_active.data,
            is_long_term_goal=form.is_long_term_goal.data,
            # Bundle settings
            is_bundle=form.is_bundle.data,
            bundle_quantity=form.bundle_quantity.data if form.is_bundle.data else None,
            # Bulk discount settings
            bulk_discount_enabled=form.bulk_discount_enabled.data,
            bulk_discount_quantity=form.bulk_discount_quantity.data if form.bulk_discount_enabled.data else None,
            bulk_discount_percentage=form.bulk_discount_percentage.data if form.bulk_discount_enabled.data else None
        )
        db.session.add(new_item)
        db.session.flush()  # Get the ID for the item before adding blocks
        # Set blocks using many-to-many relationship
        if form.blocks.data:
            new_item.set_blocks(form.blocks.data)
        db.session.commit()
        flash(f"'{new_item.name}' has been added to the store.", "success")
        return redirect(url_for('admin.store_management'))

    # Get items for this teacher only (reuse admin_id from above)
    items = StoreItem.query.filter_by(teacher_id=admin_id).order_by(StoreItem.name).all()

    # Get store statistics for overview tab
    from app.models import StudentItem
    total_items = len(items)
    active_items = len([i for i in items if i.is_active])
    total_purchases = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .count()
    )

    # Get pending redemption requests (items awaiting teacher approval)
    pending_redemptions = (
        StudentItem.query
        .options(joinedload(StudentItem.student), joinedload(StudentItem.store_item))
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
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
        .filter(Student.id.in_(student_ids_subq))
        .order_by(StudentItem.purchase_date.desc())
        .limit(10)
        .all()
    )

    return render_template('admin_store.html', form=form, items=items, current_page="store",
                         total_items=total_items, active_items=active_items, total_purchases=total_purchases,
                         pending_redemptions=pending_redemptions, recent_purchases=recent_purchases)


@admin_bp.route('/store/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_store_item(item_id):
    """Edit an existing store item."""
    admin_id = session.get("admin_id")
    item = StoreItem.query.filter_by(id=item_id, teacher_id=admin_id).first_or_404()
    form = StoreItemForm(obj=item)

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Pre-populate selected blocks on GET request (using many-to-many relationship)
    if request.method == 'GET':
        form.blocks.data = item.blocks_list

    if form.validate_on_submit():
        # Populate other fields first
        form.populate_obj(item)
        # Set blocks using many-to-many relationship
        item.set_blocks(form.blocks.data if form.blocks.data else [])
        db.session.commit()
        flash(f"'{item.name}' has been updated.", "success")
        return redirect(url_for('admin.store_management'))
    payroll_settings = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True).first()
    return render_template('admin_edit_item.html', form=form, item=item, current_page="store", payroll_settings=payroll_settings)


@admin_bp.route('/store/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_store_item(item_id):
    """Deactivate a store item (soft delete)."""
    admin_id = session.get("admin_id")
    item = StoreItem.query.filter_by(id=item_id, teacher_id=admin_id).first_or_404()
    # To preserve history, we'll just deactivate it instead of a hard delete
    # A hard delete would be: db.session.delete(item)
    item.is_active = False
    db.session.commit()
    flash(f"'{item.name}' has been deactivated and removed from the store.", "success")
    return redirect(url_for('admin.store_management'))


@admin_bp.route('/store/hard-delete/<int:item_id>', methods=['POST'])
@admin_required
def hard_delete_store_item(item_id):
    """Permanently delete a store item (hard delete)."""
    admin_id = session.get("admin_id")
    item = StoreItem.query.filter_by(id=item_id, teacher_id=admin_id).first_or_404()
    item_name = item.name

    # Check if there are any student purchases of this item
    from app.models import StudentItem
    purchase_count = (
        StudentItem.query
        .filter(StudentItem.student_id.in_(_student_scope_subquery()))
        .filter(StudentItem.store_item_id == item_id)
        .count()
    )

    if purchase_count > 0:
        flash(f"Cannot permanently delete '{item_name}' because it has {purchase_count} purchase record(s). Please deactivate instead.", "danger")
        return redirect(url_for('admin.store_management'))

    # Safe to delete - no purchase history
    db.session.delete(item)
    db.session.commit()
    flash(f"'{item_name}' has been permanently deleted from the database.", "success")
    return redirect(url_for('admin.store_management'))


# -------------------- RENT SETTINGS --------------------

@admin_bp.route('/rent-settings', methods=['GET', 'POST'])
@admin_required
def rent_settings():
    """Configure rent settings."""
    admin_id = session.get("admin_id")
    student_ids_subq = _student_scope_subquery()
    payroll_settings = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True).first()

    # Get teacher's blocks for class selector
    teacher_blocks = db.session.query(TeacherBlock.block).filter_by(teacher_id=admin_id).distinct().all()
    teacher_blocks = sorted([b[0] for b in teacher_blocks])

    # Get which class settings to show (default to first block)
    settings_block = request.args.get('settings_block') or request.form.get('settings_block')
    if not settings_block and teacher_blocks:
        settings_block = teacher_blocks[0]

    # Get or create rent settings for this class
    settings = None
    if settings_block:
        settings = RentSettings.query.filter_by(teacher_id=admin_id, block=settings_block).first()
        if not settings:
            settings = RentSettings(teacher_id=admin_id, block=settings_block)
            db.session.add(settings)
            db.session.commit()

    if request.method == 'POST':
        apply_to_all = request.form.get('apply_to_all') == 'true'
        blocks_to_update = teacher_blocks if apply_to_all else [settings_block]

        for block in blocks_to_update:
            # Get or create settings for this class
            block_settings = RentSettings.query.filter_by(teacher_id=admin_id, block=block).first()
            if not block_settings:
                block_settings = RentSettings(teacher_id=admin_id, block=block)
                db.session.add(block_settings)

            # Main toggle
            block_settings.is_enabled = request.form.get('is_enabled') == 'on'

            # Rent amount and frequency
            block_settings.rent_amount = float(request.form.get('rent_amount', 50.0))
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
            block_settings.late_penalty_amount = float(request.form.get('late_penalty_amount', 10.0))
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

        db.session.commit()
        if apply_to_all:
            flash(f"Rent settings applied to all {len(blocks_to_update)} classes!", "success")
        else:
            flash("Rent settings updated successfully!", "success")
        return redirect(url_for('admin.rent_settings', settings_block=settings_block))

    # Get statistics
    total_students = _scoped_students().filter_by(is_rent_enabled=True).count()
    current_month = datetime.now().month
    current_year = datetime.now().year
    paid_this_month = (
        RentPayment.query
        .filter(RentPayment.student_id.in_(student_ids_subq))
        .filter_by(period_month=current_month, period_year=current_year)
        .count()
    )

    # Get active waivers
    now = datetime.now(timezone.utc)
    active_waivers = (
        RentWaiver.query
        .join(Student, RentWaiver.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(RentWaiver.waiver_end_date >= now)
        .all()
    )

    # Get all students for waiver form
    all_students = _scoped_students().order_by(Student.first_name).all()

    # Build class_labels_by_block dictionary
    class_labels_by_block = {}
    for block in teacher_blocks:
        teacher_block_rec = TeacherBlock.query.filter_by(
            teacher_id=admin_id,
            block=block
        ).first()
        if teacher_block_rec:
            class_labels_by_block[block] = teacher_block_rec.get_class_label()
        else:
            class_labels_by_block[block] = block

    # Calculate payroll warning
    payroll_warning = None
    if settings and settings.is_enabled and settings.rent_amount > 0 and payroll_settings:
        # Calculate rent per month based on frequency
        rent_per_month = settings.rent_amount
        if settings.frequency_type == 'daily':
            rent_per_month = settings.rent_amount * 30
        elif settings.frequency_type == 'weekly':
            rent_per_month = settings.rent_amount * 4
        elif settings.frequency_type == 'custom':
            if settings.custom_frequency_unit == 'days':
                rent_per_month = settings.rent_amount * (30 / settings.custom_frequency_value)
            elif settings.custom_frequency_unit == 'weeks':
                rent_per_month = settings.rent_amount * (30 / (settings.custom_frequency_value * 7))
            elif settings.custom_frequency_unit == 'months':
                rent_per_month = settings.rent_amount / settings.custom_frequency_value

        # Estimate monthly payroll (assuming average 20 work days, 6 hours per day)
        # Using simple mode settings if available
        pay_per_minute = payroll_settings.pay_rate
        estimated_monthly_payroll = pay_per_minute * 60 * 6 * 20  # 6 hours/day * 20 days

        if rent_per_month > estimated_monthly_payroll * 0.8:  # If rent is more than 80% of payroll
            payroll_warning = f"Rent (${rent_per_month:.2f}/month) exceeds recommended 80% of estimated monthly payroll (${estimated_monthly_payroll:.2f}). Students may struggle to afford rent."

    return render_template('admin_rent_settings.html',
                          settings=settings,
                          total_students=total_students,
                          paid_this_month=paid_this_month,
                          active_waivers=active_waivers,
                          all_students=all_students,
                          payroll_warning=payroll_warning,
                          payroll_settings=payroll_settings,
                          settings_block=settings_block,
                          teacher_blocks=teacher_blocks,
                          class_labels_by_block=class_labels_by_block)


@admin_bp.route('/rent-waiver/add', methods=['POST'])
@admin_required
def add_rent_waiver():
    """Add rent waiver for selected students."""
    student_ids = request.form.getlist('student_ids')
    periods_count = int(request.form.get('periods_count', 1))
    reason = request.form.get('reason', '')

    if not student_ids:
        flash("Please select at least one student.", "danger")
        return redirect(url_for('admin.rent_settings'))

    # Get rent settings to calculate waiver period
    admin_id = session.get("admin_id")
    settings = RentSettings.query.filter_by(teacher_id=admin_id).first()
    if not settings:
        flash("Rent settings not configured.", "danger")
        return redirect(url_for('admin.rent_settings'))

    # Calculate waiver end date based on frequency
    now = datetime.now(timezone.utc)
    waiver_start = now

    # Calculate days per period based on frequency type
    if settings.frequency_type == 'daily':
        days_per_period = 1
    elif settings.frequency_type == 'weekly':
        days_per_period = 7
    elif settings.frequency_type == 'monthly':
        days_per_period = 30
    elif settings.frequency_type == 'custom':
        if settings.custom_frequency_unit == 'days':
            days_per_period = settings.custom_frequency_value
        elif settings.custom_frequency_unit == 'weeks':
            days_per_period = settings.custom_frequency_value * 7
        elif settings.custom_frequency_unit == 'months':
            days_per_period = settings.custom_frequency_value * 30
        else:
            days_per_period = 30
    else:
        days_per_period = 30

    total_days = days_per_period * periods_count
    waiver_end = waiver_start + timedelta(days=total_days)

    # Get current admin
    admin_id = session.get('admin_id')

    # Create waivers for each student
    count = 0
    for student_id in student_ids:
        student = _get_student_or_404(int(student_id))
        if student:
            waiver = RentWaiver(
                student_id=student.id,
                waiver_start_date=waiver_start,
                waiver_end_date=waiver_end,
                periods_count=periods_count,
                reason=reason,
                created_by_admin_id=admin_id
            )
            db.session.add(waiver)
            count += 1

    db.session.commit()
    flash(f"Rent waiver added for {count} student(s) for {periods_count} period(s).", "success")
    return redirect(url_for('admin.rent_settings'))


@admin_bp.route('/rent-waiver/<int:waiver_id>/remove', methods=['POST'])
@admin_required
def remove_rent_waiver(waiver_id):
    """Remove a rent waiver."""
    waiver = RentWaiver.query.get_or_404(waiver_id)
    _get_student_or_404(waiver.student_id)
    student_name = waiver.student.full_name
    db.session.delete(waiver)
    db.session.commit()
    flash(f"Rent waiver removed for {student_name}.", "success")
    return redirect(url_for('admin.rent_settings'))


# -------------------- INSURANCE MANAGEMENT --------------------


def _get_tier_namespace_seed(teacher_id):
    """Return a stable seed for tenant-scoped tier IDs using the teacher's join code."""
    join_code_row = (
        TeacherBlock.query
        .filter_by(teacher_id=teacher_id)
        .with_entities(TeacherBlock.join_code)
        .order_by(TeacherBlock.join_code)
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

    # Get teacher's blocks for class selector
    teacher_blocks = db.session.query(TeacherBlock.block).filter_by(teacher_id=admin_id).distinct().all()
    teacher_blocks = sorted([b[0] for b in teacher_blocks])

    # Get which class settings to show (default to first block)
    settings_block = request.args.get('settings_block') or request.form.get('settings_block')
    if not settings_block and teacher_blocks:
        settings_block = teacher_blocks[0]

    # Get class labels for display
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, teacher_blocks)

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    current_teacher_id = admin_id
    existing_policies = InsurancePolicy.query.filter_by(teacher_id=current_teacher_id).all()

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
    tier_namespace_seed = _get_tier_namespace_seed(current_teacher_id)
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
            title=form.title.data,
            description=form.description.data,
            premium=form.premium.data,
            charge_frequency=form.charge_frequency.data,
            autopay=form.autopay.data,
            waiting_period_days=form.waiting_period_days.data,
            max_claims_count=form.max_claims_count.data,
            max_claims_period=form.max_claims_period.data,
            max_claim_amount=form.max_claim_amount.data,
            max_payout_per_period=form.max_payout_per_period.data,
            claim_type=form.claim_type.data,
            is_monetary=form.claim_type.data != 'non_monetary',
            no_repurchase_after_cancel=form.no_repurchase_after_cancel.data,
            repurchase_wait_days=form.repurchase_wait_days.data,
            auto_cancel_nonpay_days=form.auto_cancel_nonpay_days.data,
            claim_time_limit_days=form.claim_time_limit_days.data,
            bundle_discount_percent=form.bundle_discount_percent.data,
            marketing_badge=form.marketing_badge.data if form.marketing_badge.data else None,
            tier_category_id=tier_category_id,
            tier_name=form.tier_name.data or None,
            tier_color=form.tier_color.data or None,
            tier_level=form.tier_level.data or None,
            settings_mode=request.form.get('settings_mode', 'advanced'),
            is_active=form.is_active.data
        )
        db.session.add(policy)
        db.session.flush()  # Get the ID for the policy before adding blocks
        # Set blocks using many-to-many relationship
        if form.blocks.data:
            policy.set_blocks(form.blocks.data)
        db.session.commit()
        flash(f"Insurance policy '{policy.title}' created successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get policies for current teacher only
    policies = existing_policies

    # Filter students by selected block
    if settings_block:
        # Use SQL LIKE for more efficient filtering (case-insensitive, match whole block)
        block_pattern = f'%,{settings_block},%'  # for matching in the middle
        block_pattern_start = f'{settings_block},%'  # for matching at the start
        block_pattern_end = f'%,{settings_block}'  # for matching at the end
        block_pattern_exact = f'{settings_block}'  # for exact match
        students_in_block = (
            _scoped_students()
            .filter(
                sa.or_(
                    sa.func.lower(Student.block) == settings_block.lower(),
                    sa.func.lower(Student.block).like(f'{settings_block.lower()},%'),
                    sa.func.lower(Student.block).like(f'%,{settings_block.lower()},%'),
                    sa.func.lower(Student.block).like(f'%,{settings_block.lower()}')
                )
            )
            .all()
        )
    else:
        students_in_block = _scoped_students().all()

    student_ids_in_block = [s.id for s in students_in_block]

    # Get student enrollments for selected block
    active_enrollments = []
    cancelled_enrollments = []
    claims = []
    pending_claims_count = 0

    if student_ids_in_block:
        active_enrollments = (
            StudentInsurance.query
            .join(Student, StudentInsurance.student_id == Student.id)
            .filter(Student.id.in_(student_ids_in_block))
            .filter(StudentInsurance.status == 'active')
            .all()
        )
        cancelled_enrollments = (
            StudentInsurance.query
            .join(Student, StudentInsurance.student_id == Student.id)
            .filter(Student.id.in_(student_ids_in_block))
            .filter(StudentInsurance.status == 'cancelled')
            .all()
        )

        # Get claims for selected block, filtered by student IDs for proper multi-tenancy isolation
        claims = (
            InsuranceClaim.query
            .join(StudentInsurance, InsuranceClaim.student_insurance_id == StudentInsurance.id)
            .filter(StudentInsurance.student_id.in_(student_ids_in_block))
            .order_by(InsuranceClaim.filed_date.desc())
            .all()
        )
        pending_claims_count = (
            InsuranceClaim.query
            .join(StudentInsurance, InsuranceClaim.student_insurance_id == StudentInsurance.id)
            .filter(StudentInsurance.student_id.in_(student_ids_in_block))
            .filter(InsuranceClaim.status == 'pending')
            .count()
        )

    return render_template('admin_insurance.html',
                          form=form,
                          policies=policies,
                          active_enrollments=active_enrollments,
                          cancelled_enrollments=cancelled_enrollments,
                          claims=claims,
                          pending_claims_count=pending_claims_count,
                          tier_groups=tier_groups,
                          next_tier_category_id=next_tier_category_id,
                          teacher_blocks=teacher_blocks,
                          settings_block=settings_block,
                          class_labels_by_block=class_labels_by_block)


@admin_bp.route('/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def edit_insurance_policy(policy_id):
    """Edit existing insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    form = InsurancePolicyForm(obj=policy)

    # Populate blocks choices from teacher's students
    blocks = _get_teacher_blocks()
    form.blocks.choices = [(block, f"Period {block}") for block in blocks]

    # Pre-populate selected blocks on GET request (using many-to-many relationship)
    if request.method == 'GET':
        form.blocks.data = policy.blocks_list

    teacher_policies = InsurancePolicy.query.filter_by(teacher_id=session.get('admin_id')).all()
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
        policy.title = form.title.data
        policy.description = form.description.data
        policy.premium = form.premium.data
        policy.charge_frequency = form.charge_frequency.data
        policy.autopay = form.autopay.data
        policy.waiting_period_days = form.waiting_period_days.data
        policy.max_claims_count = form.max_claims_count.data
        policy.max_claims_period = form.max_claims_period.data
        policy.max_claim_amount = form.max_claim_amount.data
        policy.max_payout_per_period = form.max_payout_per_period.data
        policy.claim_type = form.claim_type.data
        policy.is_monetary = form.claim_type.data != 'non_monetary'
        policy.no_repurchase_after_cancel = form.no_repurchase_after_cancel.data
        policy.enable_repurchase_cooldown = form.enable_repurchase_cooldown.data
        policy.repurchase_wait_days = form.repurchase_wait_days.data
        policy.auto_cancel_nonpay_days = form.auto_cancel_nonpay_days.data
        policy.claim_time_limit_days = form.claim_time_limit_days.data
        policy.bundle_with_policy_ids = form.bundle_with_policy_ids.data
        policy.bundle_discount_percent = form.bundle_discount_percent.data
        policy.bundle_discount_amount = form.bundle_discount_amount.data
        policy.marketing_badge = form.marketing_badge.data if form.marketing_badge.data else None
        # Set blocks using many-to-many relationship
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

        db.session.commit()
        flash(f"Insurance policy '{policy.title}' updated successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get other active policies for bundle selection (excluding current policy)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.id != policy_id
    ).all()

    payroll_settings = PayrollSettings.query.filter_by(teacher_id=session.get('admin_id'), is_active=True).first()

    return render_template(
        'admin_edit_insurance_policy.html',
        form=form,
        policy=policy,
        available_policies=available_policies,
        tier_groups=tier_groups,
        next_tier_category_id=next_tier_category_id,
        payroll_settings=payroll_settings
    )


@admin_bp.route('/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
def deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    policy.is_active = False
    db.session.commit()
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
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    force_delete = request.form.get('force_delete') == 'true'

    student_ids_subq = _student_scope_subquery()

    # Check for active enrollments within scope
    active_enrollments = StudentInsurance.query.filter(
        StudentInsurance.policy_id == policy_id,
        StudentInsurance.status == 'active',
        StudentInsurance.student_id.in_(student_ids_subq),
    ).count()

    # Check for pending claims within scope
    pending_claims = InsuranceClaim.query.filter(
        InsuranceClaim.policy_id == policy_id,
        InsuranceClaim.status == 'pending',
        InsuranceClaim.student_id.in_(student_ids_subq),
    ).count()

    if not force_delete and (active_enrollments > 0 or pending_claims > 0):
        flash(f"Cannot delete policy '{policy.title}': {active_enrollments} active enrollments and {pending_claims} pending claims. Cancel all enrollments first or use force delete.", "danger")
        return redirect(url_for('admin.insurance_management'))

    try:
        # Cancel active enrollments if force delete
        if force_delete and active_enrollments > 0:
            cancelled_count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.status == 'active',
                StudentInsurance.student_id.in_(student_ids_subq),
            ).update({'status': 'cancelled'}, synchronize_session=False)
            flash(f"Cancelled {cancelled_count} active enrollments.", "info")

        # Delete all claims for this policy
        claims_deleted = InsuranceClaim.query.filter(
            InsuranceClaim.policy_id == policy_id,
            InsuranceClaim.student_id.in_(student_ids_subq),
        ).delete(synchronize_session=False)

        # Delete all enrollments for this policy
        enrollments_deleted = StudentInsurance.query.filter(
            StudentInsurance.policy_id == policy_id,
            StudentInsurance.student_id.in_(student_ids_subq),
        ).delete(synchronize_session=False)

        # Delete the policy itself
        db.session.delete(policy)
        db.session.commit()

        flash(f"Successfully deleted policy '{policy.title}' ({enrollments_deleted} enrollments and {claims_deleted} claims removed).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting policy: {str(e)}", "danger")

    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/mass-remove/<int:policy_id>', methods=['POST'])
@admin_required
def mass_remove_policy(policy_id):
    """Cancel insurance policy for multiple or all students."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

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
            StudentInsurance.student_id.in_(student_ids_subq)
        ).update({'status': 'cancelled'}, synchronize_session=False)
    else:
        # Cancel for specific students
        try:
            student_ids = [int(sid.strip()) for sid in student_ids_raw.split(',') if sid.strip()]
            count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.student_id.in_(student_ids),
                StudentInsurance.student_id.in_(student_ids_subq),
                StudentInsurance.status == 'active'
            ).update({'status': 'cancelled'}, synchronize_session=False)
        except ValueError:
            flash("Invalid student IDs provided.", "danger")
            return redirect(url_for('admin.insurance_management'))

    db.session.commit()

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
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )

    # Get claims for this enrollment
    claims = InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    return render_template('admin_view_student_policy.html',
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          student=enrollment.student,
                          claims=claims)


@admin_bp.route('/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def process_claim(claim_id):
    """Process insurance claim with auto-deposit for monetary claims."""
    claim = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(InsuranceClaim.id == claim_id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )
    form = AdminClaimProcessForm(obj=claim)

    # Get enrollment details
    enrollment = StudentInsurance.query.get(claim.student_insurance_id)

    def _get_period_bounds():
        now = datetime.now(timezone.utc)
        if claim.policy.max_claims_period == 'year':
            return (
                now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                now.replace(month=12, day=31, hour=23, minute=59, second=59),
            )
        if claim.policy.max_claims_period == 'semester':
            if now.month <= 6:
                return (
                    now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                    now.replace(month=6, day=30, hour=23, minute=59, second=59),
                )
            return (
                now.replace(month=7, day=1, hour=0, minute=0, second=0, microsecond=0),
                now.replace(month=12, day=31, hour=23, minute=59, second=59),
            )
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(seconds=1)
        return period_start, period_end

    period_start, period_end = _get_period_bounds()

    def _claim_base_amount(target_claim):
        if target_claim.policy.claim_type == 'transaction_monetary' and target_claim.transaction:
            return abs(target_claim.transaction.amount)
        return target_claim.claim_amount or 0.0

    # Validate claim
    validation_errors = []

    # Check if coverage has started (past waiting period)
    # Ensure timezone-aware comparison
    coverage_start = enrollment.coverage_start_date
    if coverage_start and coverage_start.tzinfo is None:
        coverage_start = coverage_start.replace(tzinfo=timezone.utc)

    if not coverage_start or coverage_start > datetime.now(timezone.utc):
        validation_errors.append("Coverage has not started yet (still in waiting period)")

    # Check if payment is current
    if not enrollment.payment_current:
        validation_errors.append("Premium payments are not current")

    if claim.policy.claim_type == 'transaction_monetary' and not claim.transaction:
        validation_errors.append("Transaction-based claim is missing a linked transaction")
    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction and claim.transaction.is_void:
        validation_errors.append("Linked transaction has been voided and cannot be reimbursed")

    # P0-3 Fix: Validate transaction ownership to prevent cross-student fraud
    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction:
        if claim.transaction.student_id != claim.student_id:
            validation_errors.append(
                f"SECURITY: Transaction ownership mismatch. "
                f"Transaction belongs to student ID {claim.transaction.student_id}, "
                f"but claim filed by student ID {claim.student_id}."
            )
            current_app.logger.error(
                f"SECURITY ALERT: Transaction ownership mismatch in claim {claim.id}. "
                f"Claim student_id={claim.student_id}, transaction student_id={claim.transaction.student_id}"
            )

    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction_id:
        duplicate_claim = InsuranceClaim.query.filter(
            InsuranceClaim.transaction_id == claim.transaction_id,
            InsuranceClaim.id != claim.id,
        ).first()
        if duplicate_claim:
            validation_errors.append("Another claim is already tied to this transaction")

    incident_reference = claim.transaction.timestamp if claim.policy.claim_type == 'transaction_monetary' and claim.transaction else claim.incident_date
    # Ensure timezone-aware comparison
    if incident_reference and incident_reference.tzinfo is None:
        incident_reference = incident_reference.replace(tzinfo=timezone.utc)
    days_since_incident = (datetime.now(timezone.utc) - incident_reference).days if incident_reference else 0
    if days_since_incident > claim.policy.claim_time_limit_days:
        validation_errors.append(f"Claim filed too late ({days_since_incident} days after incident, limit is {claim.policy.claim_time_limit_days} days)")

    # Check max claims count
    approved_claims = InsuranceClaim.query.filter(
        InsuranceClaim.student_insurance_id == enrollment.id,
        InsuranceClaim.status.in_(['approved', 'paid']),
        InsuranceClaim.processed_date >= period_start,
        InsuranceClaim.processed_date <= period_end,
        InsuranceClaim.id != claim.id,
    )
    if claim.policy.max_claims_count and approved_claims.count() >= claim.policy.max_claims_count:
        validation_errors.append(f"Maximum claims limit reached ({claim.policy.max_claims_count} per {claim.policy.max_claims_period})")

    period_payouts = None
    remaining_period_cap = None
    if claim.policy.max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start,
            InsuranceClaim.processed_date <= period_end,
            InsuranceClaim.approved_amount.isnot(None),
            InsuranceClaim.id != claim.id,
        ).scalar() or 0.0

        requested_amount = _claim_base_amount(claim)
        remaining_period_cap = max(claim.policy.max_payout_per_period - period_payouts, 0)
        if remaining_period_cap is not None and requested_amount > remaining_period_cap and claim.policy.claim_type != 'non_monetary':
            validation_errors.append(
                f"Maximum payout limit would be exceeded (${period_payouts:.2f} paid + ${requested_amount:.2f} requested > ${claim.policy.max_payout_per_period:.2f} limit per {claim.policy.max_claims_period})"
            )

    # Get claims statistics
    claims_stats = {
        'pending': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='pending').count(),
        'approved': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='approved').count(),
        'rejected': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='rejected').count(),
        'paid': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='paid').count(),
    }

    if request.method == 'POST' and form.validate_on_submit():
        old_status = claim.status
        new_status = form.status.data

        is_monetary_claim = claim.policy.claim_type != 'non_monetary'
        requires_payout = is_monetary_claim and new_status in ('approved', 'paid') and old_status not in ('approved', 'paid')

        if validation_errors and requires_payout:
            flash("Resolve validation errors before approving or paying out this claim.", "danger")
            return redirect(url_for('admin.process_claim', claim_id=claim_id))

        claim.status = new_status
        claim.admin_notes = form.admin_notes.data
        claim.rejection_reason = form.rejection_reason.data if new_status == 'rejected' else None
        claim.processed_date = datetime.now(timezone.utc)
        claim.processed_by_admin_id = session.get('admin_id')

        # Handle monetary claims - auto-deposit when approved/paid
        if requires_payout:
            approved_claims_count = approved_claims.count()
            if claim.policy.max_claims_count and approved_claims_count >= claim.policy.max_claims_count:
                flash(f"Cannot approve claim: maximum of {claim.policy.max_claims_count} claims already reached this {claim.policy.max_claims_period}.", "danger")
                db.session.rollback()
                return redirect(url_for('admin.process_claim', claim_id=claim_id))

            base_amount = _claim_base_amount(claim)
            approved_amount = base_amount
            if claim.policy.claim_type == 'legacy_monetary' and form.approved_amount.data is not None:
                approved_amount = form.approved_amount.data

            if claim.policy.max_claim_amount:
                approved_amount = min(approved_amount, claim.policy.max_claim_amount)

            if remaining_period_cap is not None:
                if remaining_period_cap <= 0:
                    flash(
                        f"Cannot approve claim: Would exceed maximum payout limit of ${claim.policy.max_payout_per_period:.2f} per {claim.policy.max_claims_period} (${period_payouts:.2f} already paid)",
                        "danger",
                    )
                    db.session.rollback()
                    return redirect(url_for('admin.process_claim', claim_id=claim_id))
                approved_amount = min(approved_amount, remaining_period_cap)

            claim.approved_amount = approved_amount

            # Auto-deposit to student's checking account via transaction
            student = claim.student

            transaction_description = f"Insurance reimbursement for claim #{claim.id} ({claim.policy.title})"
            if claim.transaction_id:
                transaction_description += f" linked to transaction #{claim.transaction_id}"

            # CRITICAL FIX: Get join_code from the student's insurance enrollment
            student_insurance = StudentInsurance.query.get(claim.student_insurance_id)
            join_code = student_insurance.join_code if student_insurance else None

            transaction = Transaction(
                student_id=student.id,
                teacher_id=claim.policy.teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=approved_amount,
                account_type='checking',
                type='insurance_reimbursement',
                description=transaction_description,
            )
            db.session.add(transaction)

            flash(f"Monetary claim approved! ${approved_amount:.2f} deposited to {student.full_name}'s checking account.", "success")
        elif claim.policy.claim_type == 'non_monetary' and new_status == 'approved':
            claim.approved_amount = None
            flash(f"Non-monetary claim approved for {claim.claim_item}. Item/service will be provided offline.", "success")
        elif new_status == 'rejected':
            flash("Claim has been rejected.", "warning")

        db.session.commit()
        return redirect(url_for('admin.insurance_management'))

    return render_template('admin_process_claim.html',
                          claim=claim,
                          form=form,
                          enrollment=enrollment,
                          validation_errors=validation_errors,
                          claims_stats=claims_stats,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


# -------------------- TRANSACTIONS --------------------

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """Redirect to banking page - transactions now under banking."""
    # Preserve query parameters when redirecting
    return redirect(url_for('admin.banking', **request.args))


@admin_bp.route('/void-transaction/<int:transaction_id>', methods=['POST'])
@admin_required
def void_transaction(transaction_id):
    """Void a transaction."""
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    tx = (
        Transaction.query
        .join(Student, Transaction.student_id == Student.id)
        .filter(Transaction.id == transaction_id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )
    tx.is_void = True
    try:
        db.session.commit()
        current_app.logger.info(f"Transaction {transaction_id} voided")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to void transaction {transaction_id}: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Failed to void transaction"), 500
        flash("Error voiding transaction.", "error")
        # Safe redirect: validate referrer to prevent open redirects
        ref = request.referrer or ""
        potential_url = ref.replace('\\', '')
        parsed = urlparse(potential_url)
        if not parsed.scheme and not parsed.netloc:
            return_url = potential_url
        else:
            return_url = url_for('admin.dashboard')
        return redirect(return_url)
    if is_json:
        return jsonify(status="success", message="Transaction voided.")
    flash("✅ Transaction voided.", "success")
    # Safe redirect: validate referrer to prevent open redirects
    ref = request.referrer or ""
    potential_url = ref.replace('\\', '')
    parsed = urlparse(potential_url)
    if not parsed.scheme and not parsed.netloc:
        return_url = potential_url
    else:
        return_url = url_for('admin.dashboard')
    return redirect(return_url)


# -------------------- HALL PASS MANAGEMENT --------------------

@admin_bp.route('/hall-pass')
@admin_required
def hall_pass():
    """Manage hall pass requests and active passes."""
    student_ids_subq = _student_scope_subquery()
    pending_requests = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.asc())
        .all()
    )
    approved_queue = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'approved')
        .order_by(HallPassLog.decision_time.asc())
        .all()
    )
    out_of_class = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'left')
        .order_by(HallPassLog.left_time.asc())
        .all()
    )

    # Get available periods/blocks from teacher's students
    available_periods = (
        db.session.query(Student.block)
        .filter(Student.id.in_(student_ids_subq))
        .distinct()
        .order_by(Student.block)
        .all()
    )
    # Extract just the block values from tuples and filter out None/empty
    periods = sorted([p[0] for p in available_periods if p[0]])

    return render_template(
        'admin_hall_pass.html',
        pending_requests=pending_requests,
        approved_queue=approved_queue,
        out_of_class=out_of_class,
        available_periods=periods,
        current_page="hall_pass"
    )


# -------------------- PAYROLL --------------------

@admin_bp.route('/economy-health')
@admin_required
def economy_health():
    """Show a holistic view of the current economy configuration and CWI health."""
    admin_id = session.get("admin_id")

    blocks = _get_teacher_blocks()
    scope = request.args.get('scope', 'all')
    selected_block = None
    if scope == 'class':
        selected_block = request.args.get('block') or (blocks[0] if blocks else None)

    payroll_query = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True)
    payroll_settings = None
    if selected_block:
        payroll_settings = payroll_query.filter_by(block=selected_block).first()

    if not payroll_settings:
        payroll_settings = payroll_query.filter_by(block=None).first()

    # Fallback to first class-specific payroll when no global settings exist
    if not payroll_settings:
        first_class_setting = payroll_query.filter(PayrollSettings.block.isnot(None)).order_by(PayrollSettings.block.asc()).first()
        if first_class_setting:
            payroll_settings = first_class_setting
            selected_block = first_class_setting.block
            scope = 'class'

    # Fallback to the first available class when only class-specific payroll is configured
    if not payroll_settings and not selected_block:
        selected_block = request.args.get('block') or (blocks[0] if blocks else None)
        if selected_block:
            payroll_settings = payroll_query.filter_by(block=selected_block).first()

    has_payroll_settings = payroll_query.count() > 0

    rent_settings = None
    if selected_block:
        rent_settings = RentSettings.query.filter_by(
            teacher_id=admin_id,
            block=selected_block,
            is_enabled=True
        ).first()
    if not rent_settings:
        rent_settings = RentSettings.query.filter_by(
            teacher_id=admin_id,
            block=None,
            is_enabled=True
        ).first()

    insurance_policies_query = InsurancePolicy.query.filter_by(teacher_id=admin_id, is_active=True)
    if selected_block:
        insurance_policies = [
            policy for policy in insurance_policies_query.all()
            if not policy.blocks_list or selected_block.upper() in [b.upper() for b in policy.blocks_list]
        ]
    else:
        insurance_policies = insurance_policies_query.all()

    fines = PayrollFine.query.filter_by(teacher_id=admin_id, is_active=True).all()
    store_items = StoreItem.query.filter_by(teacher_id=admin_id, is_active=True).all()

    banking_settings = None
    if selected_block:
        banking_settings = BankingSettings.query.filter_by(
            teacher_id=admin_id,
            block=selected_block,
            is_active=True
        ).first()
    if not banking_settings:
        banking_settings = BankingSettings.query.filter_by(
            teacher_id=admin_id,
            block=None,
            is_active=True
        ).first()

    def summarize_banking(settings):
        if not settings:
            return {
                'level': 'warning',
                'title': 'Banking not configured',
                'message': 'Savings interest is off. Enable interest to reward saving and balance rent.',
                'apy': None,
            }

        apy = float(settings.savings_apy or 0)
        payout = settings.interest_schedule_type or 'monthly'

        if apy <= 0:
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
    recommendations = {}
    cwi_calc = None
    expected_hours = payroll_settings.expected_weekly_hours if payroll_settings and payroll_settings.expected_weekly_hours is not None else 5.0
    pay_rate_per_minute = payroll_settings.pay_rate if payroll_settings else None

    if payroll_settings:
        checker = EconomyBalanceChecker(admin_id, selected_block)
        analysis = checker.analyze_economy(
            payroll_settings=payroll_settings,
            rent_settings=rent_settings,
            insurance_policies=insurance_policies,
            fines=fines,
            store_items=store_items,
            expected_weekly_hours=expected_hours
        )
        cwi_calc = analysis.cwi
        pay_rate_per_minute = cwi_calc.pay_rate_per_minute
        recommendations = analysis.recommendations

        for warning in analysis.warnings:
            warnings_by_level[warning.level.value].append(warning)
            warnings_by_feature.setdefault(warning.feature, []).append(warning)

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
        scope=scope,
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
        recommendations=recommendations,
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
    current_app.logger.info("🧭 Entered admin_payroll_history route")
    student_ids_subq = _student_scope_subquery()

    block = request.args.get("block")
    current_app.logger.info(f"📊 Block filter: {block}")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    current_app.logger.info(f"📅 Date filters: start={start_date_str}, end={end_date_str}")

    query = Transaction.query.filter(
        Transaction.student_id.in_(student_ids_subq),
        Transaction.type == "payroll",
    )

    if block:
        # Stream students in batches for this block
        student_ids = [s.id for s in _scoped_students().filter_by(block=block).yield_per(50).all()]
        current_app.logger.info(f"👥 Student IDs in block '{block}': {student_ids}")
        query = query.filter(Transaction.student_id.in_(student_ids))

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        query = query.filter(Transaction.timestamp >= start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)

    payroll_transactions = query.order_by(desc(Transaction.timestamp)).all()
    current_app.logger.info(f"🔎 Payroll transactions found: {len(payroll_transactions)}")

    # Stream students in batches to reduce memory usage for the lookup
    student_lookup = {s.id: s for s in _scoped_students().yield_per(50)}
    # Gather distinct block names for the dropdown
    blocks = sorted({s.block for s in student_lookup.values() if s.block})

    # Build class_labels_by_block dictionary
    admin_id = session.get("admin_id")
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    payroll_records = []
    for tx in payroll_transactions:
        student = student_lookup.get(tx.student_id)
        student_block = student.block if student else 'Unknown'
        payroll_records.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'block': student_block,
            'class_label': class_labels_by_block.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown',
            'student_id': student.id if student else tx.student_id,
            'student_name': student.full_name if student else 'Unknown',
            'amount': tx.amount,
            'notes': tx.description,
        })

    current_app.logger.info(f"📄 Payroll records prepared: {len(payroll_records)}")

    # Current timestamp for header (Pacific Time)
    pacific = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific)

    return render_template(
        'admin_payroll_history.html',
        payroll_history=payroll_records,
        blocks=blocks,
        class_labels_by_block=class_labels_by_block,
        current_page="payroll_history",
        selected_block=block,
        selected_start=start_date_str,
        selected_end=end_date_str,
        current_time=current_time
    )


@admin_bp.route('/run-payroll', methods=['POST'])
@admin_required
def run_payroll():
    """
    Run payroll by computing earned seconds from TapEvent append-only log.
    For each student, for each block, match active/inactive pairs since last payroll,
    sum total seconds, and post Transaction(s) of type 'payroll'.

    CRITICAL: Creates one transaction per student with join_code for proper scoping.
    If student has multiple blocks with this teacher, uses first block's join_code.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        # Get current admin's teacher_id for proper transaction scoping
        current_admin_id = session.get('admin_id')

        if not current_admin_id:
            error_msg = "No admin_id in session"
            current_app.logger.error(f"❌ Payroll error: {error_msg}")
            if is_json:
                return jsonify(status="error", message=error_msg), 401
            flash(error_msg, "admin_error")
            return redirect(url_for('admin.dashboard'))

        # Get last payroll for this teacher (scoped by teacher_id)
        last_payroll_tx = Transaction.query.filter_by(
            type="payroll",
            teacher_id=current_admin_id
        ).order_by(Transaction.timestamp.desc()).first()
        last_payroll_time = last_payroll_tx.timestamp if last_payroll_tx else None
        current_app.logger.info(f"🧮 RUN PAYROLL: Last payroll at {last_payroll_time}")

        students = _scoped_students().all()
        # Pass teacher_id to ensure correct payroll settings are used
        summary = calculate_payroll(students, last_payroll_time, teacher_id=current_admin_id)

        for student_id, amount in summary.items():
            # Find the join_code for this student with this teacher
            # If student has multiple periods, use the first one
            teacher_block = TeacherBlock.query.filter_by(
                teacher_id=current_admin_id,
                student_id=student_id,
                is_claimed=True
            ).first()

            join_code = teacher_block.join_code if teacher_block else None

            tx = Transaction(
                student_id=student_id,
                teacher_id=current_admin_id,
                join_code=join_code,  # CRITICAL: Add join_code for proper scoping
                amount=amount,
                description=f"Payroll based on attendance",
                account_type="checking",
                type="payroll"
            )
            db.session.add(tx)

        db.session.commit()
        current_app.logger.info(f"✅ Payroll complete. Paid {len(summary)} students.")

        success_message = f"Payroll complete. Paid {len(summary)} students."
        if is_json:
            return jsonify(status="success", message=success_message), 200

        flash(success_message, "admin_success")
        return redirect(url_for('admin.payroll'))
    except (SQLAlchemyError, Exception) as e:
        db.session.rollback()
        is_db_error = isinstance(e, SQLAlchemyError)
        error_type = "database" if is_db_error else "unexpected"
        current_app.logger.error(f"❌ Payroll {error_type} error: {e}", exc_info=True)

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
    pacific = pytz.timezone('America/Los_Angeles')
    last_payroll_time = get_last_payroll_time()

    # Normalize to UTC to avoid any naive/aware mismatches downstream
    if last_payroll_time and last_payroll_time.tzinfo is None:
        last_payroll_time = last_payroll_time.replace(tzinfo=timezone.utc)


    now_utc = datetime.now(timezone.utc)

    # Get student scope subquery for filtering
    student_ids_subq = _student_scope_subquery()

    # Get all students
    students = _scoped_students().all()

    # Get all blocks (split multi-block assignments like "A, B")
    blocks = sorted({b.strip() for s in students for b in (s.block or "").split(',') if b.strip()})

    # Get admin ID for filtering
    admin_id = session.get("admin_id")

    # Check if payroll settings exist for this teacher
    has_settings = PayrollSettings.query.filter_by(teacher_id=admin_id).first() is not None
    show_setup_banner = not has_settings

    # Get payroll settings for this teacher, filtered to only include blocks with current students
    if blocks:
        block_settings = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True).filter(PayrollSettings.block.in_(blocks)).all()
    else:
        block_settings = []

    # Get first block's settings for form pre-population (no global settings)
    default_setting = block_settings[0] if block_settings else None

    # Organize settings by block for display and lookup
    settings_by_block = {}
    for setting in block_settings:
        if setting.block:
            settings_by_block[setting.block] = setting

    def _as_utc(dt):
        if not dt:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    def _compute_next_pay_date(setting, now):
        freq_days = setting.payroll_frequency_days if setting and setting.payroll_frequency_days else 14
        first_pay = _as_utc(setting.first_pay_date) if setting and setting.first_pay_date else None

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
    recent_payrolls = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter_by(type='payroll')
        .order_by(Transaction.timestamp.desc())
        .limit(20)
        .all()
    )

    # Calculate payroll estimates
    payroll_summary = calculate_payroll(students, last_payroll_time, teacher_id=admin_id)
    total_payroll_estimate = sum(payroll_summary.values())

    # Build class_labels_by_block dictionary
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    # Next payroll by block
    next_payroll_by_block = []
    for block in blocks:
        block_students = [s for s in students if block in [b.strip() for b in (s.block or '').split(',')]]
        block_estimate = sum(payroll_summary.get(s.id, 0) for s in block_students)
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
    for student in students:
        # Calculate unpaid minutes across all blocks
        unpaid_seconds = 0
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        for block in student_blocks:
            # TapEvent.period is stored in uppercase, so uppercase the block name
            unpaid_seconds += calculate_unpaid_attendance_seconds(student.id, block.upper(), last_payroll_time)

        unpaid_minutes = unpaid_seconds / 60.0
        estimated_payout = payroll_summary.get(student.id, 0)

        # Get last payroll date
        last_payroll = Transaction.query.filter_by(
            student_id=student.id,
            type='payroll'
        ).order_by(Transaction.timestamp.desc()).first()

        # Total earned from payroll
        total_earned = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.type == 'payroll',
            Transaction.is_void == False
        ).scalar() or 0.0

        student_stats.append({
            'student_id': student.id,
            'student_name': student.full_name,
            'block': student.block,
            'class_label': class_labels_by_block.get(student.block, student.block) if student.block else 'Unknown',
            'unpaid_minutes': int(unpaid_minutes),
            'estimated_payout': estimated_payout,
            'last_payroll_date': last_payroll.timestamp if last_payroll else None,
            'total_earned': total_earned
        })

    # Get rewards and fines for this teacher
    rewards = PayrollReward.query.filter_by(teacher_id=admin_id).order_by(PayrollReward.created_at.desc()).all()
    fines = PayrollFine.query.filter_by(teacher_id=admin_id).order_by(PayrollFine.created_at.desc()).all()

    # Initialize forms
    settings_form = PayrollSettingsForm()
    settings_form.block.choices = [('', 'Global (All Blocks)')] + [(b, b) for b in blocks]

    reward_form = PayrollRewardForm()
    fine_form = PayrollFineForm()
    manual_payment_form = ManualPaymentForm()

    # Quick stats
    avg_payout = total_payroll_estimate / len(students) if students else 0

    # Payroll history for History tab (all transaction types, not just payroll)
    payroll_history_transactions = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter(Transaction.type.in_(['payroll', 'reward', 'fine', 'manual_payment']))
        .order_by(Transaction.timestamp.desc())
        .limit(100)
        .all()
    )
    student_lookup = {s.id: s for s in students}
    payroll_history = []
    for tx in payroll_history_transactions:
        student = student_lookup.get(tx.student_id)
        student_block = student.block if student else 'Unknown'
        payroll_history.append({
            'transaction_id': tx.id,
            'timestamp': tx.timestamp,
            'type': tx.type or 'manual_payment',
            'block': student_block,
            'class_label': class_labels_by_block.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown',
            'student_id': tx.student_id,
            'student': student,
            'student_name': student.full_name if student else 'Unknown',
            'amount': tx.amount,
            'notes': tx.description or '',
            'is_void': tx.is_void
        })

    # CWI Configuration - Get selected block from query param
    cwi_block = request.args.get('cwi_block', blocks[0] if blocks else None)
    cwi_setting = None
    if cwi_block:
        # Get the payroll setting for this specific block
        cwi_setting = PayrollSettings.query.filter_by(
            teacher_id=admin_id,
            block=cwi_block
        ).first()

    return render_template(
        'admin_payroll.html',
        # Overview tab
        recent_payrolls=recent_payrolls,
        next_payroll_date=next_pay_date_utc,  # Pass UTC timestamp
        next_payroll_by_block=next_payroll_by_block,
        total_payroll_estimate=total_payroll_estimate,
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
        # Rewards & Fines tab
        rewards=rewards,
        fines=fines,
        reward_form=reward_form,
        fine_form=fine_form,
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
        format_utc_iso=format_utc_iso
    )


@admin_bp.route('/payroll/settings', methods=['POST'])
@admin_required
def payroll_settings():
    """Save payroll settings for a block or globally (Simple or Advanced mode)."""
    try:
        # Get current admin ID for teacher scoping
        admin_id = session.get("admin_id")
        
        # Get all blocks
        students = _scoped_students().all()
        blocks = sorted(set(s.block for s in students if s.block))

        # Determine which mode we're in
        settings_mode = request.form.get('settings_mode', 'simple')

        # Shared fields
        expected_weekly_hours_raw = request.form.get('expected_weekly_hours')
        expected_weekly_hours = float(expected_weekly_hours_raw) if expected_weekly_hours_raw else 5.0

        # Parse form data based on mode
        if settings_mode == 'simple':
            # Simple mode fields
            pay_rate_per_hour = float(request.form.get('simple_pay_rate', 15.0))
            pay_rate_per_minute = pay_rate_per_hour / 60.0  # Convert to per-minute for storage

            frequency = request.form.get('simple_frequency', 'biweekly')
            frequency_days_map = {'weekly': 7, 'biweekly': 14, 'monthly': 30}
            payroll_frequency_days = frequency_days_map.get(frequency, 14)

            first_pay_date_str = request.form.get('simple_first_pay_date')
            first_pay_date = datetime.strptime(first_pay_date_str, '%Y-%m-%d') if first_pay_date_str else None

            daily_limit_hours = request.form.get('simple_daily_limit')
            daily_limit_hours = float(daily_limit_hours) if daily_limit_hours else None

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
                'overtime_multiplier': 1.0,
                'max_time_per_day': None,
                'max_time_per_day_unit': None,
                'rounding_mode': 'down'
            }

        else:  # Advanced mode
            pay_amount = float(request.form.get('adv_pay_amount', 0.25))
            time_unit = request.form.get('adv_time_unit', 'minutes')

            # Convert to per-minute for storage
            unit_to_minute_multiplier = {
                'seconds': 60,
                'minutes': 1,
                'hours': 1/60,
                'days': 1/(60*24)
            }
            pay_rate_per_minute = pay_amount * unit_to_minute_multiplier.get(time_unit, 1)

            # Overtime settings
            overtime_enabled = 'adv_overtime_enabled' in request.form
            overtime_threshold = request.form.get('adv_overtime_threshold')
            overtime_threshold = float(overtime_threshold) if overtime_threshold else None
            overtime_unit = request.form.get('adv_overtime_unit')
            overtime_period = request.form.get('adv_overtime_period')
            overtime_multiplier = request.form.get('adv_overtime_multiplier')
            overtime_multiplier = float(overtime_multiplier) if overtime_multiplier else 1.0

            # Max time per day
            max_time_value = request.form.get('adv_max_time_value')
            max_time_value = float(max_time_value) if max_time_value else None
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
            target_blocks = selected_blocks

        for block_value in target_blocks:
            setting = PayrollSettings.query.filter_by(teacher_id=admin_id, block=block_value).first()
            if not setting:
                setting = PayrollSettings(teacher_id=admin_id, block=block_value)

            # Update all fields
            for key, value in settings_data.items():
                setattr(setting, key, value)

            setting.updated_at = datetime.now(timezone.utc)
            db.session.add(setting)

        db.session.commit()

        if apply_to == 'all' or not selected_blocks:
            flash(f'Payroll settings ({settings_mode} mode) applied to all periods successfully!', 'success')
        else:
            flash(f'Payroll settings ({settings_mode} mode) applied to {len(selected_blocks)} period(s) successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving payroll settings: {e}")
        flash(f'Error saving payroll settings: {str(e)}', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/update-expected-hours', methods=['POST'])
@admin_required
def update_expected_weekly_hours():
    """Update the expected weekly hours for CWI calculation for a specific block or all blocks."""
    try:
        admin_id = session.get("admin_id")
        expected_weekly_hours = float(request.form.get('expected_weekly_hours', 5.0))
        cwi_block = request.form.get('cwi_block')
        apply_to_all = request.form.get('apply_to_all', 'false').lower() == 'true'

        # Validate expected_weekly_hours is within a reasonable range (0.25 to 80)
        if not (0.25 <= expected_weekly_hours <= 80):
            flash('Expected weekly hours must be between 0.25 and 80.', 'error')
            return redirect(url_for('admin.payroll', cwi_block=cwi_block))

        if apply_to_all:
            # Update all existing payroll settings
            settings_to_update = PayrollSettings.query.filter_by(teacher_id=admin_id).all()

            if settings_to_update:
                for setting in settings_to_update:
                    setting.expected_weekly_hours = expected_weekly_hours
                flash_message = f'Expected weekly hours updated to {expected_weekly_hours} hours/week for all classes.'
            else:
                # No settings exist - create a default one for the selected block
                new_setting = PayrollSettings(
                    teacher_id=admin_id,
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
            block_setting = PayrollSettings.query.filter_by(
                teacher_id=admin_id,
                block=cwi_block
            ).first()

            if block_setting:
                block_setting.expected_weekly_hours = expected_weekly_hours
                flash_message = f'Expected weekly hours updated to {expected_weekly_hours} hours/week for {cwi_block}.'
            else:
                # Create new setting for this block
                new_setting = PayrollSettings(
                    teacher_id=admin_id,
                    block=cwi_block,
                    pay_rate=0.25,  # Default $0.25/min = $15/hour
                    expected_weekly_hours=expected_weekly_hours,
                    payroll_frequency_days=14,
                    settings_mode='simple'
                )
                db.session.add(new_setting)
                flash_message = f'Expected weekly hours set to {expected_weekly_hours} hours/week for {cwi_block}.'

        db.session.commit()
        flash(flash_message, 'success')

    except ValueError:
        flash('Invalid expected weekly hours value', 'error')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating expected weekly hours: {e}")
        flash(f'Error updating expected weekly hours: {str(e)}', 'error')

    # Redirect back with cwi_block parameter to maintain the selected class
    next_url = request.form.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)

    return redirect(url_for('admin.payroll', cwi_block=cwi_block))


# -------------------- PAYROLL REWARDS & FINES --------------------

@admin_bp.route('/payroll/rewards/add', methods=['POST'])
@admin_required
def payroll_add_reward():
    """Add a new payroll reward."""
    form = PayrollRewardForm()

    if form.validate_on_submit():
        try:
            admin_id = session.get("admin_id")
            reward = PayrollReward(
                teacher_id=admin_id,
                name=form.name.data,
                description=form.description.data,
                amount=form.amount.data,
                is_active=form.is_active.data
            )
            db.session.add(reward)
            db.session.commit()
            flash(f'Reward "{reward.name}" created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating reward: {e}")
            flash('Error creating reward. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/rewards/<int:reward_id>/delete', methods=['POST'])
@admin_required
def payroll_delete_reward(reward_id):
    """Delete a payroll reward."""
    try:
        admin_id = session.get("admin_id")
        reward = PayrollReward.query.filter_by(id=reward_id, teacher_id=admin_id).first_or_404()
        db.session.delete(reward)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reward deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting reward: {e}")
        return jsonify({'success': False, 'message': 'Error deleting reward'}), 500


@admin_bp.route('/payroll/fines/add', methods=['POST'])
@admin_required
def payroll_add_fine():
    """Add a new payroll fine."""
    form = PayrollFineForm()

    if form.validate_on_submit():
        try:
            admin_id = session.get("admin_id")
            fine = PayrollFine(
                teacher_id=admin_id,
                name=form.name.data,
                description=form.description.data,
                amount=form.amount.data,
                is_active=form.is_active.data
            )
            db.session.add(fine)
            db.session.commit()
            flash(f'Fine "{fine.name}" created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating fine: {e}")
            flash('Error creating fine. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/fines/<int:fine_id>/delete', methods=['POST'])
@admin_required
def payroll_delete_fine(fine_id):
    """Delete a payroll fine."""
    try:
        admin_id = session.get("admin_id")
        fine = PayrollFine.query.filter_by(id=fine_id, teacher_id=admin_id).first_or_404()
        db.session.delete(fine)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting fine: {e}")
        return jsonify({'success': False, 'message': 'Error deleting fine'}), 500


@admin_bp.route('/payroll/rewards/<int:reward_id>/edit', methods=['POST'])
@admin_required
def payroll_edit_reward(reward_id):
    """Edit an existing reward."""
    try:
        admin_id = session.get("admin_id")
        reward = PayrollReward.query.filter_by(id=reward_id, teacher_id=admin_id).first_or_404()
        data = request.get_json()

        reward.name = data.get('name', reward.name)
        reward.description = data.get('description', reward.description)
        reward.amount = float(data.get('amount', reward.amount))
        reward.is_active = data.get('is_active', reward.is_active)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Reward updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing reward: {e}")
        return jsonify({'success': False, 'message': 'Error editing reward'}), 500


@admin_bp.route('/payroll/fines/<int:fine_id>/edit', methods=['POST'])
@admin_required
def payroll_edit_fine(fine_id):
    """Edit an existing fine."""
    try:
        admin_id = session.get("admin_id")
        fine = PayrollFine.query.filter_by(id=fine_id, teacher_id=admin_id).first_or_404()
        data = request.get_json()

        fine.name = data.get('name', fine.name)
        fine.description = data.get('description', fine.description)
        fine.amount = float(data.get('amount', fine.amount))
        fine.is_active = data.get('is_active', fine.is_active)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing fine: {e}")
        return jsonify({'success': False, 'message': 'Error editing fine'}), 500


@admin_bp.route('/payroll/transactions/<int:transaction_id>/void', methods=['POST'])
@admin_required
def void_payroll_transaction(transaction_id):
    """Void a single transaction from payroll interface."""
    try:
        transaction = (
            Transaction.query
            .join(Student, Transaction.student_id == Student.id)
            .filter(Transaction.id == transaction_id)
            .filter(Student.id.in_(_student_scope_subquery()))
            .first_or_404()
        )

        if transaction.is_void:
            return jsonify({'success': False, 'message': 'Transaction is already voided'}), 400

        transaction.is_void = True
        db.session.commit()

        return jsonify({'success': True, 'message': 'Transaction voided successfully'})
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

        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transactions selected'}), 400

        student_ids_subq = _student_scope_subquery()
        count = 0
        for tx_id in transaction_ids:
            transaction = (
                Transaction.query
                .join(Student, Transaction.student_id == Student.id)
                .filter(Transaction.id == int(tx_id))
                .filter(Student.id.in_(student_ids_subq))
                .first()
            )
            if transaction and not transaction.is_void:
                transaction.is_void = True
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'{count} transaction(s) voided successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voiding transactions in bulk: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transactions'}), 500


@admin_bp.route('/payroll/rewards/<int:reward_id>/apply', methods=['POST'])
@admin_required
def payroll_apply_reward(reward_id):
    """Apply a reward to selected students."""
    try:
        reward = PayrollReward.query.get_or_404(reward_id)
        student_ids = request.form.getlist('student_ids')

        if not student_ids:
            return jsonify({'success': False, 'message': 'Please select at least one student'}), 400

        # Get current admin ID for teacher_id
        current_admin_id = session.get('admin_id')

        count = 0
        for student_id in student_ids:
            student = _get_student_or_404(int(student_id))
            if student:
                # CRITICAL FIX: Get join_code for this student-teacher pair
                teacher_block = TeacherBlock.query.filter_by(
                    student_id=student.id,
                    teacher_id=current_admin_id,
                    is_claimed=True
                ).first()

                join_code = teacher_block.join_code if teacher_block else None

                transaction = Transaction(
                    student_id=student.id,
                    teacher_id=current_admin_id,  # CRITICAL: Add teacher_id for multi-tenancy
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    amount=reward.amount,
                    description=f"Reward: {reward.name}",
                    account_type='checking',
                    type='reward',
                    timestamp=datetime.now(timezone.utc)
                )
                db.session.add(transaction)
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'Reward "{reward.name}" applied to {count} student(s)!'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying reward: {e}")
        return jsonify({'success': False, 'message': 'Error applying reward'}), 500


@admin_bp.route('/payroll/fines/<int:fine_id>/apply', methods=['POST'])
@admin_required
def payroll_apply_fine(fine_id):
    """Apply a fine to selected students."""
    try:
        fine = PayrollFine.query.get_or_404(fine_id)
        student_ids = request.form.getlist('student_ids')

        if not student_ids:
            return jsonify({'success': False, 'message': 'Please select at least one student'}), 400

        # Get current admin ID for teacher_id
        current_admin_id = session.get('admin_id')

        count = 0
        for student_id in student_ids:
            student = _get_student_or_404(int(student_id))
            if student:
                # CRITICAL FIX: Get join_code for this student-teacher pair
                teacher_block = TeacherBlock.query.filter_by(
                    student_id=student.id,
                    teacher_id=current_admin_id,
                    is_claimed=True
                ).first()

                join_code = teacher_block.join_code if teacher_block else None

                transaction = Transaction(
                    student_id=student.id,
                    teacher_id=current_admin_id,  # CRITICAL: Add teacher_id for multi-tenancy
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    amount=-abs(fine.amount),  # Negative for fine
                    description=f"Fine: {fine.name}",
                    account_type='checking',
                    type='fine',
                    timestamp=datetime.now(timezone.utc)
                )
                db.session.add(transaction)
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'Fine "{fine.name}" applied to {count} student(s)!'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying fine: {e}")
        return jsonify({'success': False, 'message': 'Error applying fine'}), 500


@admin_bp.route('/payroll/manual-payment', methods=['POST'])
@admin_required
def payroll_manual_payment():
    """Send manual payments to selected students."""
    form = ManualPaymentForm()

    if form.validate_on_submit():
        try:
            student_ids = request.form.getlist('student_ids')

            if not student_ids:
                flash('Please select at least one student.', 'warning')
                return redirect(url_for('admin.payroll'))

            description = form.description.data
            amount = form.amount.data
            account_type = form.account_type.data

            # Get current admin ID for teacher_id
            current_admin_id = session.get('admin_id')

            # Create transactions for each selected student
            count = 0
            for student_id in student_ids:
                student = _get_student_or_404(int(student_id))
                if student:
                    # CRITICAL FIX: Get join_code for this student-teacher pair
                    teacher_block = TeacherBlock.query.filter_by(
                        student_id=student.id,
                        teacher_id=current_admin_id,
                        is_claimed=True
                    ).first()

                    join_code = teacher_block.join_code if teacher_block else None

                    transaction = Transaction(
                        student_id=student.id,
                        teacher_id=current_admin_id,  # CRITICAL: Add teacher_id for multi-tenancy
                        join_code=join_code,  # CRITICAL: Add join_code for period isolation
                        amount=amount,
                        description=f"Manual Payment: {description}",
                        account_type=account_type,
                        type='manual_payment',
                        timestamp=datetime.now(timezone.utc)
                    )
                    db.session.add(transaction)
                    count += 1

            db.session.commit()
            flash(f'Manual payment of ${amount:.2f} sent to {count} student(s)!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending manual payments: {e}")
            flash('Error sending manual payments. Please try again.', 'error')
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
        .filter(TapEvent.student_id.in_(student_ids_subq))
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

    Creates TeacherBlock seats (unclaimed accounts) with join codes.
    Students later claim their seat by providing the join code + credentials.
    """
    file = request.files.get('csv_file')
    if not file:
        flash("No file provided", "admin_error")
        return redirect(url_for('admin.students'))

    # Read file content and remove BOM if present
    content = file.stream.read().decode("UTF-8-sig")  # UTF-8-sig removes BOM
    stream = io.StringIO(content, newline=None)
    csv_input = csv.DictReader(stream)
    added_count = 0
    errors = 0
    duplicated = 0

    # Track join codes for each block
    from app.models import TeacherBlock
    from app.utils.join_code import generate_join_code
    teacher_id = session.get("admin_id")

    # Get or generate join codes for each block in this upload
    join_codes_by_block = {}

    for row in csv_input:
        try:
            # Handle both template column names and code-friendly names (case-insensitive)
            # Try template column names first, then fall back to lowercase versions
            first_name = (row.get('First Name') or row.get('first_name') or '').strip()
            last_name = (row.get('Last Name') or row.get('last_name') or '').strip()
            dob_str = (row.get('Date of Birth (MM/DD/YYYY)') or row.get('date_of_birth') or '').strip()
            block = (row.get('Period/Block') or row.get('block') or '').strip().upper()

            if not all([first_name, last_name, dob_str, block]):
                raise ValueError("Missing required fields.")

            # Generate initials
            first_initial = first_name[0].upper()
            last_initial = last_name[0].upper()

            # Get or generate join code for this teacher-block combination
            if block not in join_codes_by_block:
                # Check if this teacher already has a join code for this block
                existing_seat = TeacherBlock.query.filter_by(
                    teacher_id=teacher_id,
                    block=block
                ).first()

                if existing_seat:
                    # Reuse existing join code
                    join_codes_by_block[block] = existing_seat.join_code
                else:
                    # Generate new unique join code with retry limit
                    new_code = None
                    for _ in range(MAX_JOIN_CODE_RETRIES):
                        new_code = generate_join_code()
                        # Ensure uniqueness across all teachers
                        if not TeacherBlock.query.filter_by(join_code=new_code).first():
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

            join_code = join_codes_by_block[block]

            # Generate dob_sum first (needed for duplicate detection)
            # Handle both mm/dd/yy and mm/dd/yyyy formats
            date_parts = dob_str.split('/')
            mm = int(date_parts[0])
            dd = int(date_parts[1])
            year = int(date_parts[2])

            # If year is 2 digits, convert to 4 digits by adding 2000
            if year < 100:
                yyyy = year + 2000
            else:
                yyyy = year

            dob_sum = mm + dd + yyyy

            # Check if this seat already exists for this teacher
            # Duplicate detection: same teacher + block + last_initial + dob_sum + first_name
            # Note: first_name is encrypted, so we must fetch candidates and check in Python
            candidate_seats = TeacherBlock.query.filter_by(
                teacher_id=teacher_id,
                block=block,
                last_initial=last_initial,
                dob_sum=dob_sum
            ).all()
            
            # Check if any candidate has matching first name (after decryption)
            existing_seat = None
            for seat in candidate_seats:
                if seat.first_name == first_name:
                    existing_seat = seat
                    break

            if existing_seat:
                duplicated += 1
                continue

            # Generate salt
            salt = get_random_salt()

            # Compute first_half_hash using canonical claim credential (first initial + DOB sum)
            first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, salt)

            # Compute last_name_hash_by_part for fuzzy matching
            last_name_parts = hash_last_name_parts(last_name, salt)

            # Create TeacherBlock seat (unclaimed account)
            seat = TeacherBlock(
                teacher_id=teacher_id,
                block=block,
                first_name=first_name,
                last_initial=last_initial,
                last_name_hash_by_part=last_name_parts,
                dob_sum=dob_sum,
                salt=salt,
                first_half_hash=first_half_hash,
                join_code=join_code,
                is_claimed=False,
            )
            db.session.add(seat)
            added_count += 1

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
            errors += 1

    try:
        db.session.commit()

        # Build success message with join codes
        success_msg = f"{added_count} roster seats created successfully"
        if errors > 0:
            success_msg += f"<br>{errors} rows could not be processed"
        if duplicated > 0:
            success_msg += f"<br>{duplicated} duplicate seats skipped"

        # Display join codes for each block
        if join_codes_by_block:
            success_msg += "<br><br><strong>Join Codes by Period:</strong><br>"
            for period, code in sorted(join_codes_by_block.items()):
                success_msg += f"Period {period}: <strong>{code}</strong><br>"
            success_msg += "<br>Share these codes with your students so they can claim their accounts."

        flash(success_msg, "admin_success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "admin_error")
        current_app.logger.error(f"Upload commit failed: {e}", exc_info=True)

    return redirect(url_for('admin.students'))


@admin_bp.route('/download-csv-template')
@admin_required
def download_csv_template():
    """
    Serves the updated student_upload_template.csv from the project root.
    """
    template_path = os.path.join(os.getcwd(), "student_upload_template.csv")
    return send_file(template_path, as_attachment=True, download_name="student_upload_template.csv", mimetype='text/csv')


@admin_bp.route('/export-students')
@admin_required
def export_students():
    """Export all student data to CSV."""
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
    students = _scoped_students().order_by(Student.first_name, Student.last_initial).all()
    teacher_id = session.get('admin_id')

    # Prefetch active insurances to avoid N+1 queries
    student_ids = [s.id for s in students]
    active_insurances_map = {}
    if teacher_id and student_ids:
        scoped_insurances = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id.in_(student_ids),
            StudentInsurance.status == 'active',
            InsurancePolicy.teacher_id == teacher_id
        ).all()

        for ins in scoped_insurances:
            if ins.student_id not in active_insurances_map:
                active_insurances_map[ins.student_id] = ins

    for student in students:
        # Get active insurance for this student from pre-fetched map
        active_insurance = active_insurances_map.get(student.id)
        insurance_name = active_insurance.policy.title if active_insurance else 'None'

        writer.writerow([
            _sanitize_csv_field(student.first_name),
            _sanitize_csv_field(student.last_initial),
            _sanitize_csv_field(student.block),
            f"{student.checking_balance:.2f}",
            f"{student.savings_balance:.2f}",
            f"{student.total_earnings:.2f}",
            _sanitize_csv_field(insurance_name),
            'Yes' if student.is_rent_enabled else 'No',
            'Yes' if student.has_completed_setup else 'No'
        ])

    # Prepare response
    output.seek(0)
    filename = f"students_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# -------------------- ADMIN TAP OUT --------------------

@admin_bp.route('/enforce-daily-limits', methods=['POST'])
@admin_required
def enforce_daily_limits():
    """
    Manually trigger auto tap-out for all students who have exceeded their daily limit.
    Returns a report of students who were auto-tapped out.
    """
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    import pytz
    from payroll import get_daily_limit_seconds

    students = _scoped_students().all()
    tapped_out = []
    checked = 0
    errors = []

    pacific = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)

    for student in students:
        try:
            # Get the student's current active sessions
            student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
            for block_original in student_blocks:
                period_upper = block_original.upper()
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period_upper)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                # If student is active, check their limit
                if latest_event and latest_event.status == "active":
                    checked += 1
                    daily_limit = get_daily_limit_seconds(block_original)

                    if daily_limit:
                        # Log the check for debugging
                        current_app.logger.info(
                            f"Checking student {student.id} ({student.full_name}) in period {period_upper} - limit: {daily_limit/3600:.1f}h"
                        )
                        check_and_auto_tapout_if_limit_reached(student)

                        # Check if they were tapped out (latest event changed)
                        new_latest = (
                            TapEvent.query
                            .filter_by(student_id=student.id, period=period_upper)
                            .order_by(TapEvent.timestamp.desc())
                            .first()
                        )
                        if new_latest and new_latest.status == "inactive" and new_latest.id != latest_event.id:
                            tapped_out.append(f"{student.full_name} (Period {period_upper})")
                    break  # Only check once per student
        except Exception as e:
            errors.append(f"{student.full_name}: {str(e)}")
            current_app.logger.error(f"Error enforcing limits for student {student.id}: {e}", exc_info=True)
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

    now_utc = datetime.now(timezone.utc)
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

                # Check if student is currently active in this period
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period)
                    .filter_by(join_code=join_code)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                if latest_event and latest_event.status == "active":
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

            # Check if student is currently active in this period
            latest_event = (
                TapEvent.query
                .filter_by(student_id=student.id, period=period)
                .filter_by(join_code=join_code)
                .order_by(TapEvent.timestamp.desc())
                .first()
            )

            if not latest_event or latest_event.status != "active":
                already_inactive.append(student.full_name)
                continue

            # Create tap-out event
            tap_out_event = TapEvent(
                student_id=student.id,
                period=period,
                status="inactive",
                timestamp=now_utc,
                reason=reason,
                join_code=join_code
            )
            db.session.add(tap_out_event)
            
            # Lock student out until midnight when teacher taps them out
            # Get or create StudentBlock record
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=period
            ).first()
            
            if not student_block:
                student_block = StudentBlock(
                    student_id=student.id,
                    period=period,
                    tap_enabled=True
                )
                db.session.add(student_block)
            
            # Set done_for_day_date to lock them out until midnight
            pacific = pytz.timezone('America/Los_Angeles')
            now_pacific = now_utc.astimezone(pacific)
            today_pacific = now_pacific.date()
            student_block.done_for_day_date = today_pacific
            
            tapped_out.append(student.full_name)

            current_app.logger.info(
                f"Admin tapped out student {student.id} ({student.full_name}) from period {period}, locked until midnight"
            )

        # Commit all tap-outs
        db.session.commit()

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
            "message": f"Failed to tap out students: {str(e)}"
        }), 500


# -------------------- BANKING ROUTES --------------------

@admin_bp.route('/banking')
@admin_required
def banking():
    """Banking management page with transactions and settings."""
    admin_id = session.get("admin_id")

    # Get teacher's blocks for class selector
    teacher_blocks = db.session.query(TeacherBlock.block).filter_by(teacher_id=admin_id).distinct().all()
    teacher_blocks = sorted([b[0] for b in teacher_blocks])

    # Get which class settings to show (default to first block)
    settings_block = request.args.get('settings_block', teacher_blocks[0] if teacher_blocks else None)

    # Get current banking settings for this class
    settings = None
    if settings_block:
        settings = BankingSettings.query.filter_by(teacher_id=admin_id, block=settings_block).first()
        if not settings:
            # Create default settings for this class
            settings = BankingSettings(teacher_id=admin_id, block=settings_block)
            db.session.add(settings)
            db.session.commit()

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

    # Get student IDs for this teacher to filter transactions
    student_ids_subq = _student_scope_subquery()

    # Base query joining Transaction with Student, filtered by teacher's students
    query = (
        db.session.query(Transaction, Student)
        .join(Student, Transaction.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
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
    for tx, student in recent_transactions:
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

    # Calculate banking stats
    total_checking = sum(s.checking_balance for s in students)
    total_savings = sum(s.savings_balance for s in students)
    total_deposits = sum(s.checking_balance + s.savings_balance for s in students)

    # Count students with savings
    students_with_savings = sum(1 for s in students if s.savings_balance > 0)

    # Calculate average savings balance (across all students, including those with 0)
    average_savings_balance = total_savings / len(students) if len(students) > 0 else 0

    # Get all blocks for filter
    blocks = sorted(set(s.block for s in students))

    # Build class_labels_by_block dictionary
    class_labels_by_block = _get_class_labels_for_blocks(admin_id, blocks)

    # Get transaction types for filter (filtered to this teacher's students)
    transaction_types = (
        db.session.query(Transaction.type)
        .join(Student, Transaction.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
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
        transaction_types=transaction_types,
        page=page,
        total_pages=total_pages,
        total_transactions=total_transactions,
        current_page="banking",
        format_utc_iso=format_utc_iso,
        settings_block=settings_block,
        teacher_blocks=teacher_blocks
    )


@admin_bp.route('/banking/settings', methods=['POST'])
@admin_required
def banking_settings_update():
    """Update banking settings for a specific class or all classes."""
    admin_id = session.get("admin_id")
    form = BankingSettingsForm()

    if form.validate_on_submit():
        settings_block = request.form.get('settings_block')
        apply_to_all = request.form.get('apply_to_all') == 'true'

        # Get all teacher blocks
        teacher_blocks = db.session.query(TeacherBlock.block).filter_by(teacher_id=admin_id).distinct().all()
        blocks_to_update = [b[0] for b in teacher_blocks] if apply_to_all else [settings_block]

        for block in blocks_to_update:
            # Get or create settings for this class
            settings = BankingSettings.query.filter_by(teacher_id=admin_id, block=block).first()
            if not settings:
                settings = BankingSettings(teacher_id=admin_id, block=block)
                db.session.add(settings)

            # Update settings from form
            settings.savings_apy = form.savings_apy.data or 0.0
            settings.savings_monthly_rate = form.savings_monthly_rate.data or 0.0
            settings.interest_calculation_type = form.interest_calculation_type.data or 'simple'
            settings.compound_frequency = form.compound_frequency.data or 'monthly'
            settings.interest_schedule_type = form.interest_schedule_type.data
            settings.interest_schedule_cycle_days = form.interest_schedule_cycle_days.data or 30
            settings.interest_payout_start_date = form.interest_payout_start_date.data
            settings.overdraft_protection_enabled = form.overdraft_protection_enabled.data
            settings.overdraft_fee_enabled = form.overdraft_fee_enabled.data
            settings.overdraft_fee_type = form.overdraft_fee_type.data
            settings.overdraft_fee_flat_amount = form.overdraft_fee_flat_amount.data or 0.0
            settings.overdraft_fee_progressive_1 = form.overdraft_fee_progressive_1.data or 0.0
            settings.overdraft_fee_progressive_2 = form.overdraft_fee_progressive_2.data or 0.0
            settings.overdraft_fee_progressive_3 = form.overdraft_fee_progressive_3.data or 0.0
            settings.overdraft_fee_progressive_cap = form.overdraft_fee_progressive_cap.data
            settings.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()
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

@admin_bp.route('/deletion-requests', methods=['GET', 'POST'])
@admin_required
def deletion_requests():
    """
    View and create deletion requests for periods/blocks or account.

    Teachers can request:
    1. Deletion of a specific period/block
    2. Deletion of their entire account

    System admins approve these requests to perform deletions.
    """
    admin_id = session.get('admin_id')

    if request.method == 'POST':
        request_type = request.form.get('request_type')  # 'period' or 'account'
        period = request.form.get('period') if request_type == 'period' else None
        reason = request.form.get('reason', '').strip()

        # Validate
        if request_type not in ['period', 'account']:
            flash('Invalid request type.', 'error')
            return redirect(url_for('admin.deletion_requests'))

        if request_type == 'period':
            if not period:
                flash('Period/block is required for period deletion requests.', 'error')
                return redirect(url_for('admin.deletion_requests'))
            # Validate period format and length
            # Allow spaces, hyphens, underscores since periods may be named like "Period 1A" or "Block-2"
            if not re.match(r'^[a-zA-Z0-9\s\-_]+$', period) or len(period) > 10:
                flash('Invalid period format. Use alphanumeric characters, spaces, hyphens, and underscores only. Max 10 characters.', 'error')
                return redirect(url_for('admin.deletion_requests'))

        # Check for duplicate pending requests
        # Convert string to enum (will raise ValueError if invalid)
        request_type_enum = DeletionRequestType.from_string(request_type)
        existing = DeletionRequest.query.filter_by(
            admin_id=admin_id,
            request_type=request_type_enum,
            period=period,
            status=DeletionRequestStatus.PENDING
        ).first()

        if existing:
            flash(
                f'You already have a pending {request_type} deletion request'
                + (f' for period {period}.' if period else '.'),
                'warning'
            )
            return redirect(url_for('admin.deletion_requests'))

        # Create the deletion request
        deletion_request = DeletionRequest(
            admin_id=admin_id,
            request_type=request_type_enum,
            period=period,
            reason=reason
        )
        db.session.add(deletion_request)

        try:
            db.session.commit()
            flash(
                f'✅ Deletion request submitted successfully. '
                f'A system administrator will review your {request_type} deletion request.',
                'success'
            )
            current_app.logger.info(
                f"Admin {admin_id} submitted {request_type} deletion request"
                + (f" for period {period}" if period else "")
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error creating deletion request: {e}")
            flash('Error submitting deletion request.', 'error')

        return redirect(url_for('admin.deletion_requests'))

    # GET: Display existing deletion requests
    pending_requests = DeletionRequest.query.filter_by(
        admin_id=admin_id,
        status=DeletionRequestStatus.PENDING
    ).order_by(DeletionRequest.requested_at.desc()).all()

    resolved_requests = DeletionRequest.query.filter_by(
        admin_id=admin_id
    ).filter(
        DeletionRequest.status.in_([DeletionRequestStatus.APPROVED, DeletionRequestStatus.REJECTED])
    ).order_by(DeletionRequest.resolved_at.desc()).limit(10).all()

    # Get teacher's periods for the dropdown (from both student_teachers and legacy teacher_id)
    periods_via_link = db.session.query(Student.block).join(
        StudentTeacher, Student.id == StudentTeacher.student_id
    ).filter(StudentTeacher.admin_id == admin_id).distinct()

    # Get periods from legacy teacher_id
    periods_via_legacy = db.session.query(Student.block).filter(
        Student.teacher_id == admin_id
    ).distinct()

    # Union both queries
    periods = periods_via_link.union(periods_via_legacy).all()
    periods = [p[0] for p in periods]

    return render_template(
        'admin_deletion_requests.html',
        current_page="deletion_requests",
        pending_requests=pending_requests,
        resolved_requests=resolved_requests,
        periods=periods
    )


@admin_bp.route('/help-support', methods=['GET', 'POST'])
@admin_required
def help_support():
    """Admin Help & Support page with bug reporting and documentation."""
    admin_id = session.get('admin_id')

    if request.method == 'POST':
        # Handle bug report submission
        report_type = request.form.get('report_type', 'bug')
        error_code = request.form.get('error_code', '')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        steps_to_reproduce = request.form.get('steps_to_reproduce', '').strip()
        expected_behavior = request.form.get('expected_behavior', '').strip()
        page_url = request.form.get('page_url', '').strip()

        # Validation
        if not title or not description:
            flash("Please provide both a title and description for your report.", "error")
            return redirect(url_for('admin.help_support'))

        # Generate anonymous code (using admin ID)
        anonymous_code = generate_anonymous_code(f"admin:{admin_id}")

        # Create report
        try:
            report = UserReport(
                anonymous_code=anonymous_code,
                user_type='teacher',
                report_type=report_type,
                error_code=error_code if error_code else None,
                title=title,
                description=description,
                steps_to_reproduce=steps_to_reproduce if steps_to_reproduce else None,
                expected_behavior=expected_behavior if expected_behavior else None,
                page_url=page_url if page_url else None,
                ip_address=get_real_ip(),
                user_agent=request.headers.get('User-Agent'),
                status='new'
            )
            # Note: _student_id is null for teachers

            db.session.add(report)
            db.session.commit()

            flash("Thank you for your report! It has been submitted to the system administrator.", "success")
            return redirect(url_for('admin.help_support'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting report: {str(e)}")
            flash("An error occurred while submitting your report. Please try again.", "error")
            return redirect(url_for('admin.help_support'))

    # Get admin's previous reports (last 10)
    anonymous_code = generate_anonymous_code(f"admin:{admin_id}")
    my_reports = UserReport.query.filter_by(anonymous_code=anonymous_code).order_by(UserReport.submitted_at.desc()).limit(10).all()

    return render_template('admin_help_support.html',
                         current_page='help',
                         my_reports=my_reports,
                         help_content=HELP_ARTICLES['teacher'])


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

    # Get all periods for this teacher
    students = _scoped_students().all()
    periods = sorted(set(
        b.strip().upper() for s in students
        for b in (s.block or '').split(',') if b.strip()
    ))

    if request.method == 'POST':
        # Handle feature settings update
        try:
            # Determine if applying to all or selected periods
            apply_to = request.form.get('apply_to', 'all')
            selected_periods = request.form.getlist('selected_periods[]') if apply_to == 'selected' else periods

            # Get feature toggle values
            features_data = {
                'payroll_enabled': 'payroll_enabled' in request.form,
                'insurance_enabled': 'insurance_enabled' in request.form,
                'banking_enabled': 'banking_enabled' in request.form,
                'rent_enabled': 'rent_enabled' in request.form,
                'hall_pass_enabled': 'hall_pass_enabled' in request.form,
                'store_enabled': 'store_enabled' in request.form,
                'bug_reports_enabled': 'bug_reports_enabled' in request.form,
                'bug_rewards_enabled': 'bug_rewards_enabled' in request.form,
            }

            # Bug rewards is a subfeature of bug reports - if bug reports is disabled, disable bug rewards too
            if not features_data['bug_reports_enabled']:
                features_data['bug_rewards_enabled'] = False

            # Apply settings to selected periods
            if apply_to == 'all':
                # Update global settings
                global_settings = FeatureSettings.query.filter_by(
                    teacher_id=admin_id,
                    block=None
                ).first()

                if not global_settings:
                    global_settings = FeatureSettings(teacher_id=admin_id, block=None)
                    db.session.add(global_settings)

                for key, value in features_data.items():
                    setattr(global_settings, key, value)

                global_settings.updated_at = datetime.now(timezone.utc)

                # Also update all period-specific settings
                for period in periods:
                    period_settings = FeatureSettings.query.filter_by(
                        teacher_id=admin_id,
                        block=period
                    ).first()

                    if not period_settings:
                        period_settings = FeatureSettings(teacher_id=admin_id, block=period)
                        db.session.add(period_settings)

                    for key, value in features_data.items():
                        setattr(period_settings, key, value)

                    period_settings.updated_at = datetime.now(timezone.utc)

                flash('Feature settings applied to all periods successfully!', 'success')
            else:
                # Apply to selected periods only
                for period in selected_periods:
                    period_settings = FeatureSettings.query.filter_by(
                        teacher_id=admin_id,
                        block=period.strip().upper()
                    ).first()

                    if not period_settings:
                        period_settings = FeatureSettings(
                            teacher_id=admin_id,
                            block=period.strip().upper()
                        )
                        db.session.add(period_settings)

                    for key, value in features_data.items():
                        setattr(period_settings, key, value)

                    period_settings.updated_at = datetime.now(timezone.utc)

                flash(f'Feature settings applied to {len(selected_periods)} period(s) successfully!', 'success')

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving feature settings: {e}")
            flash('Error saving feature settings. Please try again.', 'error')

        return redirect(url_for('admin.feature_settings'))

    # GET: Load current settings
    global_settings = FeatureSettings.query.filter_by(
        teacher_id=admin_id,
        block=None
    ).first()

    if not global_settings:
        global_settings = FeatureSettings(teacher_id=admin_id, block=None)
        db.session.add(global_settings)
        db.session.commit()

    # Load period-specific settings
    period_settings = {}
    for period in periods:
        settings = FeatureSettings.query.filter_by(
            teacher_id=admin_id,
            block=period
        ).first()

        if settings:
            period_settings[period] = settings.to_dict()
        else:
            period_settings[period] = global_settings.to_dict()

    return render_template(
        'admin_feature_settings.html',
        current_page='settings',
        global_settings=global_settings,
        periods=periods,
        period_settings=period_settings,
        features_list=[
            ('payroll_enabled', 'Payroll', 'payments', 'Time tracking and student payments'),
            ('insurance_enabled', 'Insurance', 'shield', 'Insurance policies and claims'),
            ('banking_enabled', 'Banking', 'account_balance', 'Savings accounts and interest'),
            ('rent_enabled', 'Rent', 'home', 'Housing costs and payments'),
            ('hall_pass_enabled', 'Hall Pass', 'confirmation_number', 'Bathroom and water break passes'),
            ('store_enabled', 'Store', 'storefront', 'Marketplace for student rewards'),
            ('bug_reports_enabled', 'Bug Reports', 'bug_report', 'Allow students to report issues'),
            ('bug_rewards_enabled', 'Bug Rewards', 'redeem', 'Reward students for valid bug reports'),
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

        # Get or create period settings
        settings = FeatureSettings.query.filter_by(
            teacher_id=admin_id,
            block=period
        ).first()

        if not settings:
            settings = FeatureSettings(teacher_id=admin_id, block=period)
            db.session.add(settings)

        # Update only the provided features
        feature_map = {
            'payroll': 'payroll_enabled',
            'insurance': 'insurance_enabled',
            'banking': 'banking_enabled',
            'rent': 'rent_enabled',
            'hall_pass': 'hall_pass_enabled',
            'store': 'store_enabled',
            'bug_reports': 'bug_reports_enabled',
            'bug_rewards': 'bug_rewards_enabled',
        }

        for feature_key, db_column in feature_map.items():
            if feature_key in data:
                setattr(settings, db_column, bool(data[feature_key]))

        # Bug rewards is a subfeature of bug reports - if bug reports is disabled, disable bug rewards too
        if not settings.bug_reports_enabled:
            settings.bug_rewards_enabled = False

        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Settings updated for Period {period}',
            'settings': settings.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating period feature settings: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        source_settings = FeatureSettings.query.filter_by(
            teacher_id=admin_id,
            block=source_period
        ).first()

        if not source_settings:
            # Use global defaults if no source settings
            source_settings = FeatureSettings.query.filter_by(
                teacher_id=admin_id,
                block=None
            ).first()

        if not source_settings:
            return jsonify({
                'status': 'error',
                'message': 'No source settings found to copy.'
            }), 404

        source_dict = source_settings.to_dict()

        # Define valid feature columns
        valid_feature_columns = {
            'payroll_enabled', 'insurance_enabled', 'banking_enabled',
            'rent_enabled', 'hall_pass_enabled', 'store_enabled',
            'bug_reports_enabled', 'bug_rewards_enabled'
        }

        # Copy to target periods
        copied_count = 0
        for period in target_periods:
            if period == source_period:
                continue  # Skip copying to self

            target_settings = FeatureSettings.query.filter_by(
                teacher_id=admin_id,
                block=period
            ).first()

            if not target_settings:
                target_settings = FeatureSettings(teacher_id=admin_id, block=period)
                db.session.add(target_settings)

            # Only copy valid feature columns to prevent attribute injection
            for key, value in source_dict.items():
                if key in valid_feature_columns:
                    setattr(target_settings, key, value)

            target_settings.updated_at = datetime.now(timezone.utc)
            copied_count += 1

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Settings copied from Period {source_period} to {copied_count} period(s).'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error copying feature settings: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -------------------- ANNOUNCEMENTS --------------------

@admin_bp.route('/announcements')
@admin_required
def announcements():
    """
    Manage class announcements across all class periods.

    Teachers can view, filter, and manage announcements for all their class periods.
    No period selection required - shows all announcements with period filtering.
    """
    admin_id = session.get('admin_id')

    # Get all teacher blocks (class periods)
    teacher_blocks = TeacherBlock.query.filter_by(
        teacher_id=admin_id
    ).order_by(TeacherBlock.block).all()

    # Create a mapping of join_code to block info
    blocks_by_join_code = {
        tb.join_code: {
            'block': tb.block,
            'label': tb.get_class_label(),
            'join_code': tb.join_code
        }
        for tb in teacher_blocks
    }

    # Get all announcements for this teacher (across all periods)
    # Exclude system admin announcements
    from app.models import Announcement
    announcements_list = Announcement.query.filter_by(
        teacher_id=admin_id,
        system_admin_id=None  # Only teacher-created announcements
    ).order_by(Announcement.created_at.desc()).all()

    # Attach block info to each announcement
    for announcement in announcements_list:
        announcement.block_info = blocks_by_join_code.get(announcement.join_code, {
            'block': 'Unknown',
            'label': 'Unknown Period',
            'join_code': announcement.join_code
        })

    return render_template(
        'admin/announcements.html',
        announcements=announcements_list,
        teacher_blocks=teacher_blocks,
        blocks_by_join_code=blocks_by_join_code
    )


@admin_bp.route('/announcements/create', methods=['GET', 'POST'])
@admin_required
def announcement_create():
    """Create a new announcement for selected class periods."""
    from forms import AnnouncementForm
    from app.models import Announcement

    admin_id = session.get('admin_id')

    # Get all teacher blocks for period selection
    teacher_blocks = TeacherBlock.query.filter_by(
        teacher_id=admin_id
    ).order_by(TeacherBlock.block).all()

    if not teacher_blocks:
        flash('You need to set up class periods before creating announcements.', 'warning')
        return redirect(url_for('admin.dashboard'))

    # Create form and populate period choices
    form = AnnouncementForm()
    form.periods.choices = [
        (tb.join_code, f"{tb.get_class_label()} (Period {tb.block})")
        for tb in teacher_blocks
    ]

    if form.validate_on_submit():
        try:
            selected_join_codes = form.periods.data
            created_count = 0

            # Create an announcement for each selected period
            for join_code in selected_join_codes:
                announcement = Announcement(
                    teacher_id=admin_id,
                    join_code=join_code,
                    title=form.title.data,
                    message=form.message.data,
                    priority=form.priority.data,
                    is_active=form.is_active.data,
                    expires_at=form.expires_at.data
                )
                db.session.add(announcement)
                created_count += 1

            db.session.commit()

            if created_count == 1:
                flash(f'Announcement "{form.title.data}" created successfully!', 'success')
            else:
                flash(f'Announcement "{form.title.data}" posted to {created_count} class periods!', 'success')

            return redirect(url_for('admin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating announcement: {e}")
            flash('An error occurred while creating the announcement.', 'danger')

    return render_template(
        'admin/announcement_form.html',
        form=form,
        action='Create',
        teacher_blocks=teacher_blocks
    )


@admin_bp.route('/announcements/edit/<int:announcement_id>', methods=['GET', 'POST'])
@admin_required
def announcement_edit(announcement_id):
    """Edit an existing announcement."""
    from forms import AnnouncementForm
    from app.models import Announcement

    admin_id = session.get('admin_id')

    # Get announcement and verify ownership
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=admin_id
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    # Get the block info for this announcement
    teacher_block = TeacherBlock.query.filter_by(
        teacher_id=admin_id,
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
            announcement.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            flash(f'Announcement "{announcement.title}" updated successfully!', 'success')
            return redirect(url_for('admin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating announcement: {e}")
            flash('An error occurred while updating the announcement.', 'danger')

    return render_template(
        'admin/announcement_form.html',
        form=form,
        announcement=announcement,
        teacher_block=teacher_block,
        action='Edit'
    )


@admin_bp.route('/announcements/delete/<int:announcement_id>', methods=['POST'])
@admin_required
def announcement_delete(announcement_id):
    """Delete an announcement."""
    from app.models import Announcement

    admin_id = session.get('admin_id')

    # Get announcement and verify ownership
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=admin_id
    ).first()

    if not announcement:
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('admin.announcements'))

    try:
        title = announcement.title
        db.session.delete(announcement)
        db.session.commit()

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

    admin_id = session.get('admin_id')

    # Get announcement and verify ownership
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        teacher_id=admin_id
    ).first()

    if not announcement:
        return jsonify({'status': 'error', 'message': 'Announcement not found'}), 404

    try:
        announcement.is_active = not announcement.is_active
        announcement.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'is_active': announcement.is_active,
            'message': f'Announcement {"activated" if announcement.is_active else "deactivated"}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling announcement: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -------------------- TEACHER ONBOARDING --------------------

@admin_bp.route('/onboarding')
@admin_required
def onboarding():
    """
    Teacher onboarding wizard.

    Guides new teachers through initial setup:
    1. Welcome & Overview
    2. Feature Selection
    3. Period Setup
    4. Roster Upload
    5. Quick Settings
    """
    admin_id = session.get('admin_id')

    # Get or create onboarding record
    onboarding_record = _get_or_create_onboarding(admin_id)

    # If already completed or skipped, redirect to dashboard unless force=true
    force = request.args.get('force')
    if (onboarding_record.is_completed or onboarding_record.is_skipped) and force != 'true':
        return redirect(url_for('admin.dashboard'))

    # Get admin info
    admin = Admin.query.get(admin_id)

    # Define steps
    steps = [
        {
            'id': 'welcome',
            'title': 'Welcome',
            'icon': 'waving_hand',
            'description': 'Get started with Classroom Economy'
        },
        {
            'id': 'features',
            'title': 'Select Features',
            'icon': 'tune',
            'description': 'Choose which features to enable'
        },
        {
            'id': 'periods',
            'title': 'Set Up Periods',
            'icon': 'calendar_today',
            'description': 'Configure your class periods'
        },
        {
            'id': 'roster',
            'title': 'Upload Roster',
            'icon': 'upload_file',
            'description': 'Add your students'
        },
        {
            'id': 'settings',
            'title': 'Quick Settings',
            'icon': 'settings',
            'description': 'Configure basic settings'
        }
    ]

    # Get current step based on onboarding record
    current_step = onboarding_record.current_step

    return render_template(
        'admin_onboarding.html',
        admin=admin,
        onboarding=onboarding_record,
        steps=steps,
        current_step=current_step,
        current_page='onboarding'
    )


@admin_bp.route('/onboarding/step/<step_name>', methods=['POST'])
@admin_required
def onboarding_step(step_name):
    """Process an onboarding step completion."""
    admin_id = session.get('admin_id')

    try:
        data = request.get_json() if request.is_json else {}

        onboarding_record = _get_or_create_onboarding(admin_id)

        # Mark step as completed
        onboarding_record.mark_step_completed(step_name)

        # Process step-specific data
        if step_name == 'features':
            # Save feature selections
            features_data = data.get('features', {})

            global_settings = FeatureSettings.query.filter_by(
                teacher_id=admin_id,
                block=None
            ).first()

            if not global_settings:
                global_settings = FeatureSettings(teacher_id=admin_id, block=None)
                db.session.add(global_settings)

            for feature, enabled in features_data.items():
                feature_column = f"{feature}_enabled"
                if hasattr(global_settings, feature_column):
                    setattr(global_settings, feature_column, bool(enabled))

            global_settings.updated_at = datetime.now(timezone.utc)

        elif step_name == 'periods':
            # Periods are set up via the regular student upload flow
            pass

        # Advance to next step
        step_order = ['welcome', 'features', 'periods', 'roster', 'settings']
        try:
            current_index = step_order.index(step_name)
            if current_index < len(step_order) - 1:
                onboarding_record.current_step = current_index + 2  # Advance to next step (1-indexed)
            else:
                # Last step completed
                onboarding_record.complete_onboarding()
        except ValueError:
            # If step_name is not found in step_order, ignore and do not advance onboarding step.
            pass

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Step "{step_name}" completed.',
            'next_step': onboarding_record.current_step,
            'is_completed': onboarding_record.is_completed
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing onboarding step: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/onboarding/skip', methods=['POST'])
@admin_required
def onboarding_skip():
    """Skip the onboarding process."""
    admin_id = session.get('admin_id')

    try:
        onboarding_record = _get_or_create_onboarding(admin_id)
        onboarding_record.skip_onboarding()
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Onboarding skipped. You can always configure settings later.',
            'redirect': url_for('admin.dashboard')
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error skipping onboarding: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/onboarding/complete', methods=['POST'])
@admin_required
def onboarding_complete():
    """Complete the onboarding process."""
    admin_id = session.get('admin_id')

    try:
        onboarding_record = _get_or_create_onboarding(admin_id)
        onboarding_record.complete_onboarding()
        db.session.commit()

        flash('🎉 Welcome to Classroom Economy! Your setup is complete.', 'success')

        return jsonify({
            'status': 'success',
            'message': 'Onboarding completed successfully!',
            'redirect': url_for('admin.dashboard')
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error completing onboarding: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/onboarding/reset', methods=['POST'])
@admin_required
def onboarding_reset():
    """Reset onboarding to start over (for testing or re-configuration)."""
    admin_id = session.get('admin_id')

    try:
        onboarding_record = TeacherOnboarding.query.filter_by(teacher_id=admin_id).first()

        if onboarding_record:
            onboarding_record.is_completed = False
            onboarding_record.is_skipped = False
            onboarding_record.current_step = 1
            onboarding_record.steps_completed = {}
            onboarding_record.completed_at = None
            onboarding_record.skipped_at = None
            onboarding_record.last_activity_at = datetime.now(timezone.utc)
            db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Onboarding reset. You can now go through setup again.',
            'redirect': url_for('admin.onboarding')
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting onboarding: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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

        recommendations = checker._generate_recommendations(cwi_calc.cwi, [])

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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_bp.route('/api/economy/analyze', methods=['POST'])
@admin_required
def api_economy_analyze():
    """
    Perform comprehensive economy balance analysis.

    Returns complete economy analysis including CWI, warnings, recommendations.
    """
    try:
        admin_id = session.get('admin_id')
        data = request.get_json() or {}
        block = data.get('block')

        # Get or create checker
        checker = EconomyBalanceChecker(admin_id, block)

        # Get current settings from database - filter by block if provided
        if block:
            payroll_settings = PayrollSettings.query.filter_by(
                teacher_id=admin_id,
                block=block,
                is_active=True
            ).first()
        else:
            payroll_settings = PayrollSettings.query.filter_by(
                teacher_id=admin_id,
                is_active=True
            ).first()

        if not payroll_settings:
            return jsonify({
                'status': 'error',
                'message': 'Please configure payroll settings first to calculate CWI.'
            }), 400

        # Get other economy features
        rent_settings = RentSettings.query.filter_by(
            teacher_id=admin_id,
            is_enabled=True
        ).first() if block is None else RentSettings.query.filter_by(
            teacher_id=admin_id,
            block=block,
            is_enabled=True
        ).first()

        insurance_policies = InsurancePolicy.query.filter_by(
            teacher_id=admin_id,
            is_active=True
        ).all()

        fines = PayrollFine.query.filter_by(
            teacher_id=admin_id,
            is_active=True
        ).all()

        store_items = StoreItem.query.filter_by(
            teacher_id=admin_id,
            is_active=True
        ).all()

        # Perform analysis
        # Use expected_weekly_hours from payroll_settings unless explicitly overridden in request
        expected_weekly_hours_override = data.get('expected_weekly_hours')

        if expected_weekly_hours_override is not None:
            expected_weekly_hours = float(expected_weekly_hours_override)
        else:
            expected_weekly_hours = None  # Will read from payroll_settings

        analysis = checker.analyze_economy(
            payroll_settings=payroll_settings,
            rent_settings=rent_settings,
            insurance_policies=insurance_policies,
            fines=fines,
            store_items=store_items,
            expected_weekly_hours=expected_weekly_hours
        )

        # Format response
        warnings_by_level = {
            'critical': [],
            'warning': [],
            'info': []
        }

        for w in analysis.warnings:
            warnings_by_level[w.level.value].append({
                'feature': w.feature,
                'message': w.message,
                'current_value': w.current_value,
                'recommended_min': w.recommended_min,
                'recommended_max': w.recommended_max,
                'cwi_ratio': w.cwi_ratio
            })

        return jsonify({
            'status': 'success',
            'cwi': analysis.cwi.cwi,
            'is_balanced': analysis.is_balanced,
            'budget_survival_test_passed': analysis.budget_survival_test_passed,
            'weekly_savings': analysis.weekly_savings,
            'warnings': warnings_by_level,
            'recommendations': analysis.recommendations,
            'cwi_breakdown': {
                'pay_rate_per_hour': analysis.cwi.pay_rate_per_minute * 60,
                'pay_rate_per_minute': analysis.cwi.pay_rate_per_minute,
                'expected_weekly_hours': analysis.cwi.expected_weekly_minutes / 60.0,
                'expected_weekly_minutes': analysis.cwi.expected_weekly_minutes,
                'notes': analysis.cwi.notes
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error analyzing economy: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        admin_id = session.get('admin_id')
        data = request.get_json()

        value = float(data.get('value', 0))
        block = data.get('block')
        feature = feature.lower()
        valid_features = ['rent', 'insurance', 'fine', 'store_item']
        if feature not in valid_features:
            return jsonify({
                'status': 'error',
                'message': f"Invalid feature type. Must be one of: {', '.join(valid_features)}"
            }), 400

        # Get payroll settings to calculate CWI - filter by block if provided
        if block:
            payroll_settings = PayrollSettings.query.filter_by(
                teacher_id=admin_id,
                block=block,
                is_active=True
            ).first()
        else:
            payroll_settings = PayrollSettings.query.filter_by(
                teacher_id=admin_id,
                is_active=True
            ).first()

        if not payroll_settings:
            return jsonify({
                'status': 'warning',
                'message': 'Configure payroll first to get recommendations.',
                'is_valid': True,
                'warnings': []
            })

        # Calculate CWI
        checker = EconomyBalanceChecker(admin_id, block)
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
                'pay_rate_per_hour': cwi_calc.pay_rate_per_minute * 60,
                'pay_rate_per_minute': cwi_calc.pay_rate_per_minute,
                'expected_weekly_hours': expected_weekly_hours,
                'expected_weekly_minutes': cwi_calc.expected_weekly_minutes,
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error validating {feature}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== PASSKEY AUTHENTICATION ROUTES ====================

@admin_bp.route('/passkey/register/start', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def passkey_register_start():
    """
    Generate a passkey registration token from passwordless.dev.
    
    This is called when a teacher wants to add a new passkey from their account settings.
    Returns a registration token that the frontend uses to initiate the WebAuthn ceremony.
    """
    try:
        admin_id = session.get('admin_id')
        admin = Admin.query.get_or_404(admin_id)
        
        # Get passwordless.dev client
        client = get_passwordless_client()
        
        # Generate registration token
        # userId format: "admin_{id}" to distinguish from system admins
        user_id = f"admin_{admin.id}"
        username = admin.username
        displayname = admin.get_display_name()
        
        token = client.register_token(
            user_id=user_id,
            username=username,
            displayname=displayname
        )
        
        return jsonify({
            "token": token,
            "apiKey": client.get_public_key()
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
    Finish passkey registration and save credential to database.
    
    After the frontend completes the WebAuthn ceremony, this endpoint
    saves the credential metadata to the database.
    
    Expected JSON payload:
        {
            "credentialId": "base64url-encoded credential ID",
            "authenticatorName": "User-friendly name for the authenticator"
        }
    """
    try:
        admin_id = session.get('admin_id')
        data = request.get_json()

        if not data or 'credentialId' not in data:
            return jsonify({"error": "Missing credential ID"}), 400
        
        # Get authenticator name (optional)
        authenticator_name = data.get('authenticatorName', 'Unnamed Passkey')

        # Decode credential ID from base64url
        credential_id = decode_credential_id(data['credentialId'])
        
        # Check if this credential already exists
        existing = AdminCredential.query.filter_by(credential_id=credential_id).first()
        if existing:
            return jsonify({"error": "This credential is already registered"}), 409
        
        # Create new credential record
        # Note: With passwordless.dev, we don't store the public key locally
        credential = AdminCredential(
            admin_id=admin_id,
            credential_id=credential_id,
            public_key=b'',  # Empty for passwordless.dev
            sign_count=0,
            authenticator_name=authenticator_name
            # created_at is set automatically by the model default
        )
        
        db.session.add(credential)
        db.session.commit()
        
        flash("Passkey registered successfully!", "success")
        return jsonify({"success": True, "message": "Passkey registered"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error finishing passkey registration: {e}")
        return jsonify({"error": "Failed to register passkey"}), 500


@admin_bp.route('/passkey/auth/start', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_start():
    """
    Start passkey authentication by providing the public API key.
    
    This is called from the login page when a teacher clicks "Sign in with Passkey".
    Returns the public API key needed for the frontend to initiate WebAuthn.
    
    Expected JSON payload:
        {
            "username": "teacher username"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'username' not in data:
            return jsonify({"error": "Missing username"}), 400
        
        username = data['username'].strip()
        
        # Look up admin by username
        admin = Admin.query.filter_by(username=username).first()
        if not admin:
            # Don't reveal if user exists
            return jsonify({"error": "Invalid credentials"}), 401

        # Check if user has any passkeys registered
        has_passkeys = AdminCredential.query.filter_by(admin_id=admin.id).first() is not None
        if not has_passkeys:
            # Use generic error message to prevent username enumeration
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Get passwordless.dev client
        client = get_passwordless_client()
        
        return jsonify({
            "apiKey": client.get_public_key(),
            "userId": f"admin_{admin.id}"
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
    Finish passkey authentication and create session.
    
    After the frontend completes the WebAuthn ceremony, this endpoint
    verifies the authentication token with passwordless.dev and creates
    a session for the teacher.
    
    Expected JSON payload:
        {
            "token": "token from passwordless.dev frontend"
        }
    
    Returns:
        {
            "success": true,
            "redirect": "/admin/dashboard"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'token' not in data:
            return jsonify({"error": "Missing token"}), 400
        
        token = data['token']
        
        # Verify token with passwordless.dev
        client = get_passwordless_client()
        verification = client.verify_signin(token)
        
        if not verification.get('success'):
            return jsonify({"error": "Authentication failed"}), 401
        
        # Extract user ID (format: "admin_{id}")
        user_id = verification.get('userId')
        if not user_id or not user_id.startswith('admin_'):
            return jsonify({"error": "Invalid user ID"}), 401
        
        # Parse admin ID with error handling for malformed IDs
        try:
            admin_id = int(user_id.replace('admin_', ''))
        except ValueError:
            current_app.logger.error(f"Invalid userId format from passwordless.dev: {user_id}")
            return jsonify({"error": "Invalid user ID format"}), 401
        
        # Verify admin exists
        admin = Admin.query.get(admin_id)
        if not admin:
            return jsonify({"error": "Admin not found"}), 401
        
        # Update credential last_used timestamp and admin last_login
        now = datetime.now(timezone.utc)
        credential_id_b64 = verification.get('credentialId')
        if credential_id_b64:
            credential_id = decode_credential_id(credential_id_b64)
            credential = AdminCredential.query.filter_by(credential_id=credential_id).first()
            if credential:
                credential.last_used = now
            else:
                # Log a warning if verification succeeds but no matching credential record is found
                current_app.logger.warning(
                    "Passwordless login for admin_id=%s used unknown credentialId=%s",
                    admin.id,
                    verification.get('credentialId'),
                )
        
        admin.last_login = now
        db.session.commit()
        session.clear()
        session['admin_id'] = admin.id
        session['is_admin'] = True
        session['username'] = admin.username
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        session.permanent = True
        
        return jsonify({
            "success": True,
            "redirect": url_for('admin.dashboard')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error finishing passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 401


@admin_bp.route('/passkey/list', methods=['GET'])
@admin_required
def passkey_list():
    """List all passkeys for the current teacher."""
    try:
        admin_id = session.get('admin_id')
        credentials = AdminCredential.query.filter_by(admin_id=admin_id).order_by(AdminCredential.created_at.desc()).all()
        
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
    """Delete a passkey for the current teacher."""
    try:
        admin_id = session.get('admin_id')
        credential = AdminCredential.query.filter_by(id=passkey_id, admin_id=admin_id).first()
        
        if not credential:
            return jsonify({"error": "Passkey not found"}), 404
        
        # Check if this is the only credential
        total_credentials = AdminCredential.query.filter_by(admin_id=admin_id).count()
        if total_credentials <= 1:
            # Still allow deletion - teacher can use TOTP as backup
            pass
        
        db.session.delete(credential)
        db.session.commit()
        
        flash("Passkey deleted successfully", "success")
        return jsonify({"success": True, "message": "Passkey deleted"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting passkey: {e}")
        return jsonify({"error": "Failed to delete passkey"}), 500


@admin_bp.route('/passkey/settings')
@admin_required
def passkey_settings():
    """Passkey management page for teachers."""
    admin_id = session.get('admin_id')
    admin = Admin.query.get_or_404(admin_id)
    
    # Get all passkeys for this teacher
    credentials = AdminCredential.query.filter_by(admin_id=admin_id).order_by(AdminCredential.created_at.desc()).all()
    
    return render_template('admin_passkey_settings.html',
                         admin=admin,
                         credentials=credentials)
