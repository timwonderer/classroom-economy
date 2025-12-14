"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import secrets
import re
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from flask import Blueprint, redirect, url_for, flash, request, session, jsonify, current_app
from urllib.parse import urlparse
from sqlalchemy import or_, func, select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import pytz

from app.extensions import db, limiter
from app.models import (
    Student, Transaction, TapEvent, StoreItem, StudentItem,
    RentSettings, RentPayment, InsurancePolicy, StudentInsurance, InsuranceClaim,
    BankingSettings, UserReport, FeatureSettings
)
from app.auth import admin_required, login_required, get_logged_in_student, SESSION_TIMEOUT_MINUTES
from forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, InsuranceClaimForm, StudentCompleteProfileForm
)

# Import utility functions
from app.utils.helpers import is_safe_url, generate_anonymous_code, render_template_with_fallback as render_template
from app.utils.constants import THEME_PROMPTS
from app.utils.turnstile import verify_turnstile_token
from app.utils.demo_sessions import cleanup_demo_student_data
from app.utils.ip_handler import get_real_ip
from app.utils.claim_credentials import compute_primary_claim_hash, match_claim_hash
from app.utils.name_utils import hash_last_name_parts
from app.utils.help_content import HELP_ARTICLES
from hash_utils import hash_hmac, hash_username, hash_username_lookup
from attendance import get_all_block_statuses
from payroll import get_pay_rate_for_block

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')


# -------------------- PERIOD SELECTION HELPERS --------------------

def get_current_class_context():
    """Get the currently selected class context (join_code, teacher_id, block).

    CRITICAL: This function enforces proper multi-tenancy isolation by using
    join_code as the source of truth. Each join code represents a distinct
    class economy, even if they share the same teacher.

    Returns:
        dict with keys: join_code, teacher_id, block, seat_id
        None if no context available
    """
    from app.models import TeacherBlock

    student = get_logged_in_student()
    if not student:
        return None

    # Check if a join code is already selected in session
    current_join_code = session.get('current_join_code')

    # Get all claimed seats for this student
    claimed_seats = TeacherBlock.query.filter_by(
        student_id=student.id,
        is_claimed=True
    ).all()

    if not claimed_seats:
        return None

    # If no join code selected, default to first claimed seat
    if not current_join_code:
        first_seat = claimed_seats[0]
        current_join_code = first_seat.join_code
        # Store in session for future requests
        session['current_join_code'] = current_join_code

    # Find the seat matching current join code
    current_seat = next(
        (seat for seat in claimed_seats if seat.join_code == current_join_code),
        None
    )

    # If join code not found in student's seats, reset to first seat
    if not current_seat:
        current_seat = claimed_seats[0]
        session['current_join_code'] = current_seat.join_code

    # Return full class context
    return {
        'join_code': current_seat.join_code,
        'teacher_id': current_seat.teacher_id,
        'block': current_seat.block,
        'seat_id': current_seat.id
    }


def get_current_teacher_id():
    """DEPRECATED: Get teacher_id from current class context.

    This function is maintained for backward compatibility but should be
    replaced with get_current_class_context() for proper multi-tenancy.
    """
    context = get_current_class_context()
    return context['teacher_id'] if context else None


def get_current_join_code():
    """Get the currently selected join code from class context.

    Join code is the absolute source of truth for class association.
    Returns None if no class context is available.
    """
    context = get_current_class_context()
    return context['join_code'] if context else None


def get_feature_settings_for_student():
    """
    Get feature settings for the currently logged-in student.

    Returns the merged feature settings for the student's current teacher/period context.
    Settings cascade: period-specific > global > system defaults.

    Returns:
        dict: Feature settings dictionary with enabled/disabled flags
    """
    student = get_logged_in_student()
    if not student:
        # Return defaults if no student logged in
        return FeatureSettings.get_defaults()

    teacher_id = get_current_teacher_id()
    if not teacher_id:
        return FeatureSettings.get_defaults()

    # Get the student's current block/period
    current_block = session.get('current_period')
    if not current_block and student.block:
        # Default to first block, handling empty strings after split
        blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        current_block = blocks[0] if blocks else None

    # Try block-specific settings first
    if current_block:
        block_settings = FeatureSettings.query.filter_by(
            teacher_id=teacher_id,
            block=current_block
        ).first()
        if block_settings:
            return block_settings.to_dict()

    # Fall back to global settings for this teacher
    global_settings = FeatureSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None
    ).first()

    if global_settings:
        return global_settings.to_dict()

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
    settings = get_feature_settings_for_student()
    feature_key = f"{feature_name}_enabled"
    return settings.get(feature_key, True)  # Default to enabled


def calculate_scoped_balances(student: 'Student', join_code: str, teacher_id: int) -> tuple[float, float]:
    """Calculate checking and savings balances scoped to a specific class.
    
    This function ensures consistent balance calculation across the application
    by including transactions with matching join_code OR NULL join_code (legacy)
    with matching teacher_id.
    
    Args:
        student (Student): Student object whose balances to calculate
        join_code (str): The join code for the current class context
        teacher_id (int): The teacher ID for the current class context
    
    Returns:
        tuple[float, float]: (checking_balance, savings_balance) as rounded floats
    """
    checking_balance = round(sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'checking' and not tx.is_void and
        (tx.join_code == join_code or (tx.join_code is None and tx.teacher_id == teacher_id))
    ), 2)
    
    savings_balance = round(sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'savings' and not tx.is_void and
        (tx.join_code == join_code or (tx.join_code is None and tx.teacher_id == teacher_id))
    ), 2)
    
    return checking_balance, savings_balance


# -------------------- LEGACY PROFILE MIGRATION --------------------

@student_bp.before_request
def check_legacy_profile():
    """
    Check if logged-in student needs to complete legacy profile migration.
    
    Legacy students are those who:
    - have completed setup (has_completed_setup=True)
    - but are missing last_name_hash_by_part or dob_sum
    - and have not completed the migration (has_completed_profile_migration=False)
    """
    # Skip for non-student routes, login, logout, and profile completion itself
    excluded_endpoints = [
        'student.login', 'student.logout', 'student.complete_profile',
        'student.claim_account', 'student.create_username', 'student.setup_pin_passphrase',
        'student.demo_login', 'student.setup_complete', 'student.add_class'
    ]
    
    # Skip if endpoint is None or not in student blueprint
    if not request.endpoint or not request.endpoint.startswith('student.'):
        return
    
    if request.endpoint in excluded_endpoints:
        return
    
    # Only check for logged-in students
    student = get_logged_in_student()
    
    if not student:
        return
    
    # Check if this is a legacy student needing migration
    needs_migration = (
        student.has_completed_setup and
        not student.has_completed_profile_migration and
        (not student.last_name_hash_by_part or student.dob_sum is None)
    )
    
    if needs_migration:
        return redirect(url_for('student.complete_profile'))


@student_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """
    One-time profile completion for legacy students missing last name and DOB.
    
    This route collects:
    - First name (editable, from existing)
    - Last name (new, required)
    - Date of birth (new, required)
    
    Then updates the student record with hashed values and regenerates credential hashes.
    """
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('student.login'))
    
    # Check if already completed migration
    if student.has_completed_profile_migration:
        flash("You have already completed your profile.", "info")
        return redirect(url_for('student.dashboard'))
    
    form = StudentCompleteProfileForm()
    
    # Handle form submission
    if form.validate_on_submit():
        step = request.form.get('step', 'confirm')
        
        # Get form data from WTForms
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()
        dob_month = form.dob_month.data
        dob_day = form.dob_day.data.strip()
        dob_year = form.dob_year.data.strip()
        
        # Validation
        if not all([first_name, last_name, dob_month, dob_day, dob_year]):
            flash("All fields are required.", "error")
            return redirect(url_for('student.complete_profile'))
        
        if not last_name:
            flash("Last name is required.", "error")
            return redirect(url_for('student.complete_profile'))
        
        try:
            month = int(dob_month)
            day = int(dob_day)
            year = int(dob_year)
            
            # Validate ranges
            current_year = datetime.now().year
            if not (1 <= month <= 12):
                flash("Invalid month.", "error")
                return redirect(url_for('student.complete_profile'))
            if not (1 <= day <= 31):
                flash("Invalid day.", "error")
                return redirect(url_for('student.complete_profile'))
            # Students should be born between 1900 and (current year - 5) for elementary/middle school
            if not (1900 <= year <= current_year - 5):
                flash(f"Invalid year. Students should be born between 1900 and {current_year - 5}.", "error")
                return redirect(url_for('student.complete_profile'))
            
            # Validate that the date is real
            try:
                datetime(year, month, day)
            except ValueError:
                flash("Invalid date. Please check the month and day.", "error")
                return redirect(url_for('student.complete_profile'))
            
            # Calculate DOB sum
            dob_sum = month + day + year
            
        except (ValueError, TypeError):
            flash("Invalid date format.", "error")
            return redirect(url_for('student.complete_profile'))
        
        if step == 'confirm':
            # Show confirmation page
            month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            dob_display = f"{month_names[month]} {day}, {year}"
            current_year = datetime.now().year
            max_birth_year = current_year - 5
            
            return render_template(
                'student_complete_profile.html',
                current_page='profile',
                page_title='Complete Profile',
                form=form,
                student=student,
                confirmed=True,
                max_birth_year=max_birth_year,
                confirm_data={
                    'first_name': first_name,
                    'last_name': last_name,
                    'dob_month': dob_month,
                    'dob_day': dob_day,
                    'dob_year': dob_year,
                    'dob_display': dob_display
                }
            )
        
        elif step == 'submit':
            # Final submission - update student record
            try:
                # Recalculate dob_sum for submit step (needed since it's only calculated in confirm step's try block)
                # This prevents NameError when submitting the form
                month = int(dob_month)
                day = int(dob_day)
                year = int(dob_year)
                dob_sum = month + day + year
                
                # Update first name (encrypted)
                student.first_name = first_name
                
                # Update last initial from last name (already validated to not be empty)
                student.last_initial = last_name[0].upper()
                
                # Calculate and store DOB sum
                student.dob_sum = dob_sum
                
                # Generate last_name_hash_by_part
                student.last_name_hash_by_part = hash_last_name_parts(last_name, student.salt)
                
                # Regenerate first_half_hash using first initial + dob_sum
                first_initial_char = first_name[0].upper() if first_name else ''
                student.first_half_hash = compute_primary_claim_hash(first_initial_char, dob_sum, student.salt)
                
                # Regenerate second_half_hash using just dob_sum
                dob_sum_str = str(dob_sum)
                student.second_half_hash = hash_hmac(dob_sum_str.encode('utf-8'), student.salt)
                
                # Mark migration as completed
                student.has_completed_profile_migration = True
                
                # Update all TeacherBlock entries for this student with new hashes
                from app.models import TeacherBlock
                teacher_blocks = TeacherBlock.query.filter_by(student_id=student.id).all()
                for block in teacher_blocks:
                    block.last_name_hash_by_part = student.last_name_hash_by_part
                    block.first_half_hash = student.first_half_hash
                    block.last_initial = student.last_initial
                
                db.session.commit()
                
                flash("Profile completed successfully! Thank you.", "success")
                return redirect(url_for('student.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error completing profile for student {student.id}: {str(e)}")
                flash("An error occurred. Please try again.", "error")
                return redirect(url_for('student.complete_profile'))
    
    # GET request - show form
    current_year = datetime.now().year
    max_birth_year = current_year - 5  # Students should be at least 5 years old
    
    return render_template(
        'student_complete_profile.html',
        current_page='profile',
        page_title='Complete Profile',
        form=form,
        student=student,
        confirmed=False,
        max_birth_year=max_birth_year
    )


# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
def claim_account():
    """
    PAGE 1: Claim Account - Verify identity using join code to begin setup.

    New join code-based flow:
    1. Student enters join code (identifies their teacher-period)
    2. Student enters name code + DOB sum
    3. System finds matching unclaimed seat in TeacherBlock
    4. Creates Student record (or finds existing if student has other classes)
    5. Links TeacherBlock seat to Student
    6. Creates StudentTeacher link
    """
    from app.models import TeacherBlock, StudentTeacher
    from app.utils.join_code import format_join_code

    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        join_code = format_join_code(form.join_code.data)
        first_initial = form.first_initial.data.strip().upper()
        last_name = form.last_name.data.strip()
        dob_sum_str = form.dob_sum.data.strip()

        if not dob_sum_str.isdigit():
            flash("DOB sum must be a number.", "claim")
            return redirect(url_for('student.claim_account'))

        dob_sum = int(dob_sum_str)

        # Find all unclaimed seats with this join code
        unclaimed_seats = TeacherBlock.query.filter_by(
            join_code=join_code,
            is_claimed=False
        ).all()

        if not unclaimed_seats:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "claim")
            return redirect(url_for('student.claim_account'))

        # Try to find a matching seat
        from app.utils.name_utils import verify_last_name_parts

        matched_seat = None
        for seat in unclaimed_seats:
            credential_matches, matched_primary, canonical_hash = match_claim_hash(
                seat.first_half_hash,
                first_initial,
                seat.last_initial,
                seat.dob_sum,
                seat.salt,
            )

            # Check last name with fuzzy matching
            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )

            if credential_matches and last_name_matches and seat.dob_sum == dob_sum:
                if canonical_hash and not matched_primary:
                    seat.first_half_hash = canonical_hash
                matched_seat = seat
                break

        if not matched_seat:
            flash("No matching account found. Please check your join code and credentials.", "claim")
            return redirect(url_for('student.claim_account'))

        # Check if this student already has an account (claiming from another teacher)
        # Look for existing students with same credentials across all teachers
        existing_student = None
        all_students = Student.query.filter_by(
            last_initial=matched_seat.last_initial,
            dob_sum=dob_sum
        ).all()

        for student in all_students:
            if student.first_name == matched_seat.first_name:
                credential_matches, student_primary_match, canonical_hash = match_claim_hash(
                    student.first_half_hash,
                    first_initial,
                    student.last_initial,
                    student.dob_sum,
                    student.salt,
                )

                last_name_valid = verify_last_name_parts(
                    last_name,
                    student.last_name_hash_by_part,
                    student.salt
                )

                if credential_matches and last_name_valid:
                    if canonical_hash and not student_primary_match:
                        student.first_half_hash = canonical_hash
                    existing_student = student
                    break

        if existing_student:
            # Student already exists - link this seat to existing student
            matched_seat.student_id = existing_student.id
            matched_seat.is_claimed = True
            matched_seat.claimed_at = datetime.now(timezone.utc)

            # Create StudentTeacher link
            existing_link = StudentTeacher.query.filter_by(
                student_id=existing_student.id,
                admin_id=matched_seat.teacher_id
            ).first()

            if not existing_link:
                link = StudentTeacher(
                    student_id=existing_student.id,
                    admin_id=matched_seat.teacher_id
                )
                db.session.add(link)

            db.session.commit()

            # Student already completed setup in another class, redirect to login
            if existing_student.has_completed_setup:
                flash("This seat has been linked to your existing account. Please log in.", "claim")
                return redirect(url_for('student.login'))
            else:
                # Continue setup process
                session['claimed_student_id'] = existing_student.id
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)
                return redirect(url_for('student.create_username'))

        # New student - create Student record
        # Generate second_half_hash (DOB hash) for backward compatibility
        second_half_hash = hash_hmac(str(dob_sum).encode(), matched_seat.salt)

        new_student = Student(
            first_name=matched_seat.first_name,
            last_initial=matched_seat.last_initial,
            block=matched_seat.block,
            salt=matched_seat.salt,
            first_half_hash=matched_seat.first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=matched_seat.dob_sum,
            last_name_hash_by_part=matched_seat.last_name_hash_by_part,
            has_completed_setup=False,
            teacher_id=None,  # DEPRECATED - no longer used
        )
        db.session.add(new_student)
        db.session.flush()  # Get student ID

        # Link seat to student
        matched_seat.student_id = new_student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = datetime.now(timezone.utc)

        # Create StudentTeacher link
        link = StudentTeacher(
            student_id=new_student.id,
            admin_id=matched_seat.teacher_id
        )
        db.session.add(link)
        db.session.commit()

        # Start setup flow
        session['claimed_student_id'] = new_student.id
        session.pop('generated_username', None)
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)

        return redirect(url_for('student.create_username'))

    return render_template('student_account_claim.html', form=form)


@student_bp.route('/create-username', methods=['GET', 'POST'])
def create_username():
    """PAGE 2: Create Username - Generate themed username."""
    # Only allow if claimed
    student_id = session.get('claimed_student_id')
    if not student_id:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student.claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
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
        dob_sum = student.dob_sum if student.dob_sum is not None else 0
        initials = f"{student.first_name[0].upper()}{student.last_initial.upper()}"
        username = f"{adjective}{write_in_word}{dob_sum}{initials}"
        # Save username plaintext in session for display
        session['generated_username'] = username
        # Hash and store in DB
        student.username_hash = hash_username(username, student.salt)
        student.username_lookup_hash = hash_username_lookup(username)
        db.session.commit()
        # Clear theme prompt from session
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)


@student_bp.route('/setup-pin-passphrase', methods=['GET', 'POST'])
def setup_pin_passphrase():
    """PAGE 3: Setup PIN & Passphrase - Secure the account."""
    # Only allow if claimed and username generated
    student_id = session.get('claimed_student_id')
    username = session.get('generated_username')
    if not student_id or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student.claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    form = StudentPinPassphraseForm()
    if form.validate_on_submit():
        pin = form.pin.data
        passphrase = form.passphrase.data
        if not pin or not passphrase:
            flash("PIN and passphrase are required.", "setup")
            return redirect(url_for('student.setup_pin_passphrase'))
        # Save credentials (store passphrase as hash)
        student.pin_hash = generate_password_hash(pin)
        student.passphrase_hash = generate_password_hash(passphrase)
        student.has_completed_setup = True
        db.session.commit()
        # Clear session onboarding keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('student.setup_complete'))
    return render_template('student_pin_setup.html', username=username, form=form)


# -------------------- ADD NEW CLASS --------------------

@student_bp.route('/add-class', methods=['GET', 'POST'])
@login_required
def add_class():
    """
    Allow logged-in students to add a new class by entering a join code.

    This enables students who are already registered to join additional classes
    taught by other teachers, creating multi-teacher/multi-class support.
    """
    from app.models import TeacherBlock, StudentTeacher
    from app.utils.join_code import format_join_code
    from forms import StudentAddClassForm
    from app.utils.name_utils import verify_last_name_parts

    student = get_logged_in_student()
    form = StudentAddClassForm()

    def _is_safe_url(target):
        """
        Returns True if the target is a local URL (preventing open redirect).
        """
        from urllib.parse import urlparse
        if not target:
            return False
        target = target.replace("\\", "")
        parsed = urlparse(target)
        # Only allow relative URLs with no scheme and no netloc, nor starting with double slashes
        if parsed.scheme or parsed.netloc:
            return False
        if target.startswith('//'):  # Prevent protocol-relative URLs
            return False
        return True

    def _get_return_target(default_endpoint='student.dashboard'):
        """
        Return the safest place to redirect back to after add-class attempts.

        Prioritize an explicit `next` value, fall back to referrer, then dashboard.

        Security: All redirect targets are validated with _is_safe_url() to ensure
        they are same-origin URLs, preventing open redirect vulnerabilities.
        """
        next_url = request.form.get('next') or request.args.get('next')
        if next_url and _is_safe_url(next_url):
            return next_url

        # Validate referrer to prevent open redirects (same-origin check)
        ref_url = request.referrer
        if ref_url and _is_safe_url(ref_url):
            return ref_url

        # Safe fallback: always use internal route
        return url_for(default_endpoint)

    if form.validate_on_submit():
        join_code = format_join_code(form.join_code.data)
        first_initial = form.first_initial.data.strip().upper()
        last_name = form.last_name.data.strip()
        dob_sum_str = form.dob_sum.data.strip()

        # Validate DOB sum is numeric
        if not dob_sum_str.isdigit():
            flash("DOB sum must be a number.", "danger")
            return redirect(_get_return_target())

        dob_sum = int(dob_sum_str)

        # Verify the credentials match the logged-in student
        if first_initial != student.first_name[:1].upper():
            flash("The first initial doesn't match your account. Please check and try again.", "danger")
            return redirect(_get_return_target())

        if dob_sum != student.dob_sum:
            flash("The DOB sum doesn't match your account. Please check and try again.", "danger")
            return redirect(_get_return_target())

        # Verify last name matches using the same fuzzy matching logic
        if not verify_last_name_parts(last_name, student.last_name_hash_by_part, student.salt):
            flash("The last name doesn't match your account. Please check and try again.", "danger")
            return redirect(_get_return_target())

        # Find all unclaimed seats with this join code
        unclaimed_seats = TeacherBlock.query.filter_by(
            join_code=join_code,
            is_claimed=False
        ).all()

        if not unclaimed_seats:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "danger")
            return redirect(_get_return_target())

        # Try to find a matching seat for this student
        matched_seat = None
        for seat in unclaimed_seats:
            credential_matches, matched_primary, canonical_hash = match_claim_hash(
                seat.first_half_hash,
                first_initial,
                seat.last_initial,
                seat.dob_sum,
                seat.salt,
            )

            # Check last name with fuzzy matching
            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )

            # Check if names match (encrypted first name comparison)
            name_matches = seat.first_name == student.first_name and seat.last_initial == student.last_initial

            if credential_matches and last_name_matches and name_matches and seat.dob_sum == dob_sum:
                if canonical_hash and not matched_primary:
                    seat.first_half_hash = canonical_hash
                matched_seat = seat
                break

        if not matched_seat:
            flash("No matching seat found for your account. Please verify your join code and credentials.", "danger")
            return redirect(_get_return_target())

        # Check if student is already linked to this teacher
        existing_link = StudentTeacher.query.filter_by(
            student_id=student.id,
            admin_id=matched_seat.teacher_id
        ).first()

        if existing_link:
            flash("You are already enrolled in this teacher's class.", "warning")
            return redirect(_get_return_target())

        # Normalize claim hash to canonical pattern
        canonical_claim_hash = compute_primary_claim_hash(first_initial, dob_sum, matched_seat.salt)
        if canonical_claim_hash:
            matched_seat.first_half_hash = canonical_claim_hash
            student.first_half_hash = canonical_claim_hash

        # Link the seat to the existing student
        matched_seat.student_id = student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = datetime.now(timezone.utc)

        # Create StudentTeacher link
        link = StudentTeacher(
            student_id=student.id,
            admin_id=matched_seat.teacher_id
        )
        db.session.add(link)

        # Update student's block to include the new block if not already there
        current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        new_block = matched_seat.block.strip().upper()

        if new_block not in current_blocks:
            current_blocks.append(new_block)
            student.block = ','.join(sorted(current_blocks))

        try:
            db.session.commit()
            flash(f"Successfully added to Block {new_block}! You can now access this class from your dashboard.", "success")
            return redirect(_get_return_target())
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding class for student {student.id}: {str(e)}")
            flash("An error occurred while adding the class. Please try again or contact your teacher.", "danger")
            return redirect(_get_return_target())

    return render_template('student_add_class.html', form=form)


# -------------------- STUDENT DASHBOARD --------------------

@student_bp.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard with balance, attendance, transactions, and quick actions."""
    student = get_logged_in_student()

    # CRITICAL FIX v2: Use join_code as source of truth (not just teacher_id)
    # This properly isolates same-teacher, different-period classes
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.login'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']
    current_block = context['block']  # Get current class block

    apply_savings_interest(student)  # Apply savings interest if not already applied

    # CRITICAL FIX: Filter transactions by join_code (not just teacher_id)
    # This ensures Period A and Period B with same teacher are isolated
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code  # FIX: Use join_code for proper isolation
    ).order_by(Transaction.timestamp.desc()).all()

    # FIX: Filter student items by current teacher's store
    student_items = student.items.join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        StoreItem.teacher_id == teacher_id
    ).order_by(StudentItem.purchase_date.desc()).all()

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    # CRITICAL FIX: Calculate balances using join_code scoping
    # Sum only transactions for THIS specific class (join_code)
    checking_balance = round(sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'checking' and not tx.is_void and tx.join_code == join_code
    ), 2)
    savings_balance = round(sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'savings' and not tx.is_void and tx.join_code == join_code
    ), 2)
    forecast_interest = round(savings_balance * (0.045 / 12), 2)

    # FIX: Only show tap in/out status for CURRENT class, not all classes
    # Get status for only the current block (not all blocks)
    period_states = get_all_block_statuses(student, join_code=join_code)
    # Filter to only current class block
    period_states = {current_block.upper(): period_states.get(current_block.upper(), {})}
    student_blocks = [current_block.upper()]  # Only current block
    period_states_json = json.dumps(period_states, separators=(',', ':'))

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: state.get("projected_pay", 0)
        for blk, state in period_states.items()
    }

    # Compute total unpaid seconds and format as HH:MM:SS for display
    total_unpaid_seconds = sum(unpaid_seconds_per_block.values())
    hours, remainder = divmod(total_unpaid_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    total_unpaid_elapsed = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    student_name = student.full_name

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
    context = get_current_class_context()
    teacher_id = context['teacher_id'] if context else None
    active_insurance = student.get_active_insurance(teacher_id)

    rent_status = None
    rent_settings = RentSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    if rent_settings and rent_settings.is_enabled and student.is_rent_enabled:
        now = datetime.now()
        due_date, grace_end_date = _calculate_rent_deadlines(rent_settings, now)

        preview_start_date = None
        if rent_settings.bill_preview_enabled and rent_settings.bill_preview_days:
            preview_start_date = due_date - timedelta(days=rent_settings.bill_preview_days)

        rent_is_active = True
        is_preview_period = False
        if rent_settings.first_rent_due_date and now < rent_settings.first_rent_due_date:
            if preview_start_date and now >= preview_start_date:
                rent_is_active = True
                is_preview_period = True
            else:
                rent_is_active = False
        elif preview_start_date and preview_start_date <= now < due_date:
            is_preview_period = True

        rent_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        current_month = now.month
        current_year = now.year

        all_paid = True
        for period in rent_blocks:
            all_payments_for_period = RentPayment.query.filter_by(
                student_id=student.id,
                period=period,
                period_month=current_month,
                period_year=current_year
            ).all()

            payments = []
            for payment in all_payments_for_period:
                txn = Transaction.query.filter(
                    Transaction.student_id == student.id,
                    Transaction.type == 'Rent Payment',
                    Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
                    Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
                    Transaction.amount == -payment.amount_paid
                ).first()

                if txn and not txn.is_void:
                    payments.append(payment)

            total_paid = sum(p.amount_paid for p in payments) if payments else 0.0
            late_fee = rent_settings.late_fee if rent_is_active and now > grace_end_date else 0.0
            total_due = rent_settings.rent_amount + late_fee if rent_is_active else 0.0
            is_paid = total_paid >= total_due if rent_is_active else False

            if rent_is_active and not is_paid:
                all_paid = False
                break

        rent_status = {
            'is_active': rent_is_active,
            'is_paid': all_paid if rent_is_active else False,
            'is_preview': is_preview_period
        }

    tz = pytz.timezone('America/Los_Angeles')
    local_now = datetime.now(tz)
    # --- DASHBOARD DEBUG LOGGING ---
    current_app.logger.info(f"📊 DASHBOARD DEBUG: Student {student.id} - Block states:")
    for blk, blk_state in period_states.items():
        active = blk_state.get("active")
        done = blk_state.get("done")
        seconds = blk_state.get("duration")
        current_app.logger.info(f"Block {blk} => DB Active={active}, Done={done}, Seconds (today)={seconds}, Total Unpaid Seconds={unpaid_seconds_per_block.get(blk, 0)}")


    # --- Calculate remaining session time for frontend timer ---
    login_time = datetime.fromisoformat(session['login_time'])
    expiry_time = login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    session_remaining_seconds = max(0, int((expiry_time - datetime.now(timezone.utc)).total_seconds()))

    # --- Get feature settings for this student ---
    feature_settings = get_feature_settings_for_student()

    # --- Check for pending recovery request ---
    from app.models import StudentRecoveryCode, RecoveryRequest
    pending_recovery_code = StudentRecoveryCode.query.join(
        RecoveryRequest
    ).filter(
        StudentRecoveryCode.student_id == student.id,
        StudentRecoveryCode.dismissed == False,
        StudentRecoveryCode.code_hash == None,  # Not yet verified
        RecoveryRequest.status == 'pending',
        RecoveryRequest.expires_at > datetime.now(timezone.utc)
    ).first()

    # --- Calculate weekly/monthly analytics ---
    from app.models import TapEvent
    now_utc = datetime.now(timezone.utc)
    week_start = now_utc - timedelta(days=now_utc.weekday())  # Monday of current week
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _as_utc(ts):
        if not ts:
            return None
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    # Days tapped in this week
    tap_events_this_week = TapEvent.query.filter(
        TapEvent.student_id == student.id,
        TapEvent.join_code == join_code,
        TapEvent.timestamp >= week_start,
        TapEvent.is_deleted == False
    ).all()

    # Calculate unique days and total minutes
    unique_days_tapped = len(set(_as_utc(event.timestamp).date() for event in tap_events_this_week if event.status == 'active'))

    # Calculate total minutes this week
    total_minutes_this_week = 0
    active_sessions = {}  # Track active tap-in per period

    for event in sorted(tap_events_this_week, key=lambda e: e.timestamp):
        period = event.period
        event_ts = _as_utc(event.timestamp)
        if event.status == 'active':
            active_sessions[period] = event_ts
        elif event.status == 'inactive' and period in active_sessions:
            duration = (event_ts - active_sessions[period]).total_seconds() / 60
            total_minutes_this_week += duration
            del active_sessions[period]

    # Add ongoing sessions (still active)
    for start_time in active_sessions.values():
        duration = (now_utc - start_time).total_seconds() / 60
        total_minutes_this_week += duration

    # Earnings this week/month
    earnings_this_week = sum(
        tx.amount for tx in transactions
        if tx.amount > 0 and tx.timestamp >= week_start and not tx.is_void
    )
    earnings_this_month = sum(
        tx.amount for tx in transactions
        if tx.amount > 0 and tx.timestamp >= month_start and not tx.is_void
    )

    # Spending this week/month
    spending_this_week = abs(sum(
        tx.amount for tx in transactions
        if tx.amount < 0 and tx.timestamp >= week_start and not tx.is_void
    ))
    spending_this_month = abs(sum(
        tx.amount for tx in transactions
        if tx.amount < 0 and tx.timestamp >= month_start and not tx.is_void
    ))

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
        forecast_interest=forecast_interest,
        recent_deposit=recent_deposit,
        active_insurance=active_insurance,
        rent_status=rent_status,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        student_name=student_name,
        total_unpaid_elapsed=total_unpaid_elapsed,
        feature_settings=feature_settings,
        # FIX: Pass scoped balances to template instead of using unscoped properties
        checking_balance=checking_balance,
        savings_balance=savings_balance,
        teacher_id=teacher_id,
        pending_recovery_code=pending_recovery_code,
        # Weekly/monthly analytics
        unique_days_tapped=unique_days_tapped,
        total_minutes_this_week=int(total_minutes_this_week),
        earnings_this_week=round(earnings_this_week, 2),
        earnings_this_month=round(earnings_this_month, 2),
        spending_this_week=round(spending_this_week, 2),
        spending_this_month=round(spending_this_month, 2),
    )


@student_bp.route('/payroll')
@login_required
def payroll():
    """Student payroll page with attendance record, productivity stats, and projected pay."""
    # Check if payroll feature is enabled
    if not is_feature_enabled('payroll'):
        flash("The payroll feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    current_block = (context.get('block') or '').upper()
    join_code = context.get('join_code')
    period_states = get_all_block_statuses(student, join_code=join_code)

    # Scope dashboard data to the selected class context only
    period_states = {current_block: period_states.get(current_block, {})}
    student_blocks = [current_block]

    # Determine the pay rate for the current block (per minute)
    pay_rate_per_second = get_pay_rate_for_block(current_block)
    pay_rate_per_minute = round(pay_rate_per_second * 60, 2)

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: round(state.get("projected_pay", 0), 2)
        for blk, state in period_states.items()
    }

    # Get all tap events grouped by block (scoped to the current class when available)
    # Limit to 20 most recent events to improve performance (template only displays 20)
    tap_query = TapEvent.query.filter_by(
        student_id=student.id,
        period=current_block,
        join_code=join_code
    )

    all_tap_events = tap_query.order_by(TapEvent.timestamp.desc()).limit(20).all()
    tap_events_by_block = {}
    for event in all_tap_events:
        # Normalize to the action labels used by the template
        event.action = 'tap_in' if event.status == 'active' else 'tap_out'
        if event.period not in tap_events_by_block:
            tap_events_by_block[event.period] = []
        tap_events_by_block[event.period].append(event)

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
        now=datetime.now(timezone.utc)
    )


# -------------------- FINANCIAL TRANSACTIONS --------------------

@student_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer funds between checking and savings accounts."""
    # Check if banking feature is enabled
    if not is_feature_enabled('banking'):
        flash("The banking feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context (join_code, teacher_id, block)
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        passphrase = request.form.get("passphrase")
        if not check_password_hash(student.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student.transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        amount = float(request.form.get('amount'))

        # CRITICAL FIX: Calculate balances using join_code scoping
        checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)

        if from_account == to_account:
            if is_json:
                return jsonify(status="error", message="Cannot transfer to the same account."), 400
            flash("Cannot transfer to the same account.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif amount <= 0:
            if is_json:
                return jsonify(status="error", message="Amount must be greater than 0."), 400
            flash("Amount must be greater than 0.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'checking' and amount > checking_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient checking funds."), 400
            flash("Insufficient checking funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'savings' and amount > savings_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient savings funds."), 400
            flash("Insufficient savings funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        else:
            # CRITICAL FIX v2: Add BOTH teacher_id AND join_code for proper isolation
            # Record the withdrawal side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=-amount,
                account_type=from_account,
                type='Withdrawal',
                description=f'Transfer to {to_account}'
            ))
            # Record the deposit side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=amount,
                account_type=to_account,
                type='Deposit',
                description=f'Transfer from {from_account}'
            ))
            try:
                db.session.commit()
                current_app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for student {student.id}"
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

    # CRITICAL FIX v2: Get transactions for display - scope by join_code
    # Include transactions with matching join_code OR NULL join_code (legacy) with matching teacher_id
    transactions = Transaction.query.filter(
        Transaction.student_id == student.id,
        Transaction.is_void == False,
        or_(
            Transaction.join_code == join_code,
            and_(Transaction.join_code.is_(None), Transaction.teacher_id == teacher_id)
        )
    ).order_by(Transaction.timestamp.desc()).all()
    checking_transactions = [t for t in transactions if t.account_type == 'checking']
    savings_transactions = [t for t in transactions if t.account_type == 'savings']

    # Get banking settings for interest rate display
    from app.models import BankingSettings
    settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    annual_rate = settings.savings_apy / 100 if settings else 0.045
    calculation_type = settings.interest_calculation_type if settings else 'simple'
    compound_frequency = settings.compound_frequency if settings else 'monthly'

    # Calculate forecast interest based on settings
    # CRITICAL FIX v3: Calculate BOTH checking and savings balances using join_code scoping
    checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)

    if calculation_type == 'compound':
        if compound_frequency == 'daily':
            periods_per_month = 30
            rate_per_period = annual_rate / 365
            forecast_interest = savings_balance * ((1 + rate_per_period) ** periods_per_month - 1)
        elif compound_frequency == 'weekly':
            periods_per_month = 4.33
            rate_per_period = annual_rate / 52
            forecast_interest = savings_balance * ((1 + rate_per_period) ** periods_per_month - 1)
        else:  # monthly
            forecast_interest = savings_balance * (annual_rate / 12)
    else:
        # Simple interest: calculate only on principal (excluding interest earnings)
        principal = sum(tx.amount for tx in savings_transactions if tx.type != 'Interest' and 'Interest' not in (tx.description or ''))
        forecast_interest = principal * (annual_rate / 12)

    # Calculate 12-month savings projection for graph
    projection_months = []
    projection_balances = []
    current_balance = savings_balance

    for month in range(13):  # 0 to 12 months
        projection_months.append(month)
        projection_balances.append(round(current_balance, 2))

        if month < 12:  # Don't calculate interest for the last point
            if calculation_type == 'compound':
                if compound_frequency == 'daily':
                    periods = 30
                    rate = annual_rate / 365
                    interest = current_balance * ((1 + rate) ** periods - 1)
                elif compound_frequency == 'weekly':
                    periods = 4.33
                    rate = annual_rate / 52
                    interest = current_balance * ((1 + rate) ** periods - 1)
                else:  # monthly
                    interest = current_balance * (annual_rate / 12)
                current_balance += interest
            else:  # simple interest
                interest = savings_balance * (annual_rate / 12)  # Simple interest on original principal
                current_balance += interest

    return render_template('student_transfer.html',
                         student=student,
                         transactions=transactions,
                         checking_transactions=checking_transactions,
                         savings_transactions=savings_transactions,
                         checking_balance=checking_balance,
                         savings_balance=savings_balance,
                         forecast_interest=forecast_interest,
                         settings=settings,
                         calculation_type=calculation_type,
                         compound_frequency=compound_frequency,
                         projection_months=projection_months,
                         projection_balances=projection_balances)


def apply_savings_interest(student, annual_rate=0.045):
    """
    Apply savings interest for a student based on banking settings.
    Supports both simple and compound interest with configurable frequency.
    All time calculations are in UTC.
    """
    from app.models import BankingSettings

    now = datetime.now(timezone.utc)
    this_month = now.month
    this_year = now.year

    def _as_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Get banking settings for current teacher
    teacher_id = get_current_teacher_id()
    settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    if not settings:
        # Use default simple interest if no settings
        calculation_type = 'simple'
        compound_frequency = 'monthly'
    else:
        calculation_type = settings.interest_calculation_type or 'simple'
        compound_frequency = settings.compound_frequency or 'monthly'

    # Check if interest was already applied this month
    for tx in student.transactions:
        tx_timestamp = _as_utc(tx.timestamp)
        if (
            tx.account_type == 'savings'
            and tx.description == "Monthly Savings Interest"
            and tx_timestamp
            and tx_timestamp.month == this_month
            and tx_timestamp.year == this_year
        ):
            return  # Interest already applied this month

    for tx in student.transactions:
        if tx.account_type != 'savings' or "Transfer" not in (tx.description or ""):
            continue
        tx_timestamp = _as_utc(tx.timestamp)
        if tx_timestamp and tx_timestamp.date() == now.date():
            return

    # Calculate interest based on type
    if calculation_type == 'compound':
        # For compound interest, use current total balance (including previous interest)
        balance = student.savings_balance

        # Determine the rate based on compound frequency
        if compound_frequency == 'daily':
            # Daily compounding: rate = (1 + annual_rate/365)^365 - 1 ≈ annual_rate for small rates
            # For monthly payout with daily compounding: (1 + annual_rate/365)^30
            periods_per_year = 365
            periods_per_month = 30
            rate_per_period = annual_rate / periods_per_year
            interest = round(balance * ((1 + rate_per_period) ** periods_per_month - 1), 2)
        elif compound_frequency == 'weekly':
            # Weekly compounding: (1 + annual_rate/52)^4.33 (approx weeks per month)
            periods_per_year = 52
            periods_per_month = 4.33
            rate_per_period = annual_rate / periods_per_year
            interest = round(balance * ((1 + rate_per_period) ** periods_per_month - 1), 2)
        else:  # monthly
            # Monthly compounding
            monthly_rate = annual_rate / 12
            interest = round(balance * monthly_rate, 2)
    else:
        # Simple interest: only calculate on original deposits (not including previous interest)
        eligible_balance = 0
        for tx in student.transactions:
            if tx.account_type != 'savings' or tx.is_void or tx.amount <= 0:
                continue
            # Exclude interest transactions from principal calculation
            if tx.type == 'Interest' or 'Interest' in (tx.description or ''):
                continue
            available_at = _as_utc(tx.date_funds_available)
            if available_at and (now - available_at).days >= 30:
                eligible_balance += tx.amount

        monthly_rate = annual_rate / 12
        interest = round((eligible_balance or 0.0) * monthly_rate, 2)

    if interest > 0:
        # CRITICAL FIX v2: Add join_code to interest transactions
        # Interest must be scoped to specific class, not just teacher
        context = get_current_class_context()
        if context:
            interest_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=context['join_code'],  # CRITICAL: Add join_code for period isolation
                amount=interest,
                account_type='savings',
                type='Interest',
                description="Monthly Savings Interest"
            )
            db.session.add(interest_tx)
            db.session.commit()


# -------------------- INSURANCE --------------------

@student_bp.route('/insurance', endpoint='student_insurance')
@login_required
def insurance_marketplace():
    """Insurance marketplace - browse and manage policies."""
    # Check if insurance feature is enabled
    if not is_feature_enabled('insurance'):
        flash("The insurance feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context (join_code is source of truth)
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']

    # FIX: Get student's active policies scoped to current class only
    my_policies = StudentInsurance.query.join(
        InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
    ).filter(
        StudentInsurance.student_id == student.id,
        StudentInsurance.status == 'active',
        InsurancePolicy.teacher_id == teacher_id  # FIX: Only show current class policies
    ).all()

    # FIX: Get available policies (only from current teacher)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.teacher_id == teacher_id  # FIX: Only current class
    ).all()

    # Check which policies can be purchased
    can_purchase = {}
    repurchase_blocks = {}

    for policy in available_policies:
        # Check if already enrolled
        existing = StudentInsurance.query.filter_by(
            student_id=student.id,
            policy_id=policy.id,
            status='active'
        ).first()

        if existing:
            can_purchase[policy.id] = False
            continue

        # Check repurchase restrictions
        if policy.no_repurchase_after_cancel:
            cancelled = StudentInsurance.query.filter_by(
                student_id=student.id,
                policy_id=policy.id,
                status='cancelled'
            ).order_by(StudentInsurance.cancel_date.desc()).first()

            if cancelled and cancelled.cancel_date:
                days_since_cancel = (datetime.now(timezone.utc) - cancelled.cancel_date).days
                if days_since_cancel < policy.repurchase_wait_days:
                    can_purchase[policy.id] = False
                    repurchase_blocks[policy.id] = policy.repurchase_wait_days - days_since_cancel
                    continue

        can_purchase[policy.id] = True

    # FIX: Get claims for my policies (scoped to current teacher)
    my_claims = InsuranceClaim.query.join(
        InsurancePolicy, InsuranceClaim.policy_id == InsurancePolicy.id
    ).filter(
        InsuranceClaim.student_id == student.id,
        InsurancePolicy.teacher_id == teacher_id  # FIX: Only current class claims
    ).all()

    # Group policies by tier for display
    tier_groups = {}
    ungrouped_policies = []
    for policy in available_policies:
        if policy.tier_category_id:
            if policy.tier_category_id not in tier_groups:
                tier_groups[policy.tier_category_id] = {
                    'name': policy.tier_name or f"Tier {policy.tier_category_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups[policy.tier_category_id]['policies'].append(policy)
        else:
            ungrouped_policies.append(policy)

    # Check which tier the student has already selected from
    enrolled_tiers = set()
    for enrollment in my_policies:
        if enrollment.policy.tier_category_id:
            enrolled_tiers.add(enrollment.policy.tier_category_id)

    return render_template('student_insurance_marketplace.html',
                          student=student,
                          my_policies=my_policies,
                          available_policies=ungrouped_policies,
                          tier_groups=tier_groups,
                          enrolled_tiers=enrolled_tiers,
                          can_purchase=can_purchase,
                          repurchase_blocks=repurchase_blocks,
                          my_claims=my_claims,
                          now=datetime.now(timezone.utc))


@student_bp.route('/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def purchase_insurance(policy_id):
    """Purchase insurance policy."""
    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context
    context = get_current_class_context()
    if not context:
        flash("No class selected.", "danger")
        return redirect(url_for('student.dashboard'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']

    policy = InsurancePolicy.query.get_or_404(policy_id)

    # FIX: Verify policy belongs to CURRENT teacher only
    if policy.teacher_id != teacher_id:
        flash("This insurance policy is not available in your current class.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Check if already enrolled
    existing = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='active'
    ).first()

    if existing:
        flash("You are already enrolled in this policy.", "warning")
        return redirect(url_for('student.student_insurance'))

    # Check repurchase restrictions
    cancelled = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='cancelled'
    ).order_by(StudentInsurance.cancel_date.desc()).first()

    if cancelled:
        # Check for permanent block (no repurchase allowed EVER)
        if policy.no_repurchase_after_cancel:
            flash("This policy cannot be repurchased after cancellation.", "danger")
            return redirect(url_for('student.student_insurance'))

        # Check for cooldown period (temporary restriction)
        if policy.enable_repurchase_cooldown and cancelled.cancel_date:
            days_since_cancel = (datetime.now(timezone.utc) - cancelled.cancel_date).days
            if days_since_cancel < policy.repurchase_wait_days:
                flash(f"You must wait {policy.repurchase_wait_days - days_since_cancel} more days before repurchasing this policy.", "warning")
                return redirect(url_for('student.student_insurance'))

    # Check tier restrictions - can only have one policy per tier (scoped to current class)
    if policy.tier_category_id:
        existing_tier_enrollment = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id == student.id,
            StudentInsurance.status == 'active',
            InsurancePolicy.tier_category_id == policy.tier_category_id,
            InsurancePolicy.teacher_id == teacher_id  # Scope to current class only
        ).first()

        if existing_tier_enrollment:
            flash(f"You already have a policy from the '{policy.tier_name or 'this'}' tier. You can only have one policy per tier.", "warning")
            return redirect(url_for('student.student_insurance'))

    # CRITICAL FIX v2: Check sufficient funds using join_code scoped balance
    checking_balance = round(sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'checking' and not tx.is_void and tx.join_code == join_code
    ), 2)
    if checking_balance < policy.premium:
        flash("Insufficient funds to purchase this insurance policy.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Create enrollment
    enrollment = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        status='active',
        purchase_date=datetime.now(timezone.utc),
        last_payment_date=datetime.now(timezone.utc),
        next_payment_due=datetime.now(timezone.utc) + timedelta(days=30),  # Simplified
        coverage_start_date=datetime.now(timezone.utc) + timedelta(days=policy.waiting_period_days),
        payment_current=True
    )
    db.session.add(enrollment)

    # CRITICAL FIX v2: Create transaction with join_code
    transaction = Transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,  # CRITICAL: Add join_code for period isolation
        amount=-policy.premium,
        account_type='checking',
        type='insurance_premium',
        description=f"Insurance premium: {policy.title}"
    )
    db.session.add(transaction)

    db.session.commit()
    flash(f"Successfully purchased {policy.title}! Coverage starts after {policy.waiting_period_days} day waiting period.", "success")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
def cancel_insurance(enrollment_id):
    """Cancel insurance policy."""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    enrollment.status = 'cancelled'
    enrollment.cancel_date = datetime.now(timezone.utc)

    db.session.commit()
    flash(f"Insurance policy '{enrollment.policy.title}' has been cancelled.", "info")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def file_claim(policy_id):
    """File insurance claim."""
    student = get_logged_in_student()

    # Get student's enrollment for this policy
    enrollment = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy_id,
        status='active'
    ).first()

    if not enrollment:
        flash("You are not enrolled in this policy.", "danger")
        return redirect(url_for('student.student_insurance'))

    policy = enrollment.policy
    form = InsuranceClaimForm()
    if policy.claim_type == 'transaction_monetary' and not form.incident_date.data:
        form.incident_date.data = datetime.now(timezone.utc).date()

    # Validation errors
    errors = []

    def _get_period_bounds():
        now = datetime.now(timezone.utc)
        if policy.max_claims_period == 'year':
            return (
                now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                now.replace(month=12, day=31, hour=23, minute=59, second=59),
            )
        if policy.max_claims_period == 'semester':
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

    # Check if coverage has started
    if not enrollment.coverage_start_date or enrollment.coverage_start_date > datetime.now(timezone.utc):
        errors.append(f"Coverage has not started yet. Please wait until {enrollment.coverage_start_date.strftime('%B %d, %Y') if enrollment.coverage_start_date else 'coverage starts'}.")

    # Check if payment is current
    if not enrollment.payment_current:
        errors.append("Your premium payments are not current. Please contact the teacher.")

    period_start, period_end = _get_period_bounds()

    # Check max claims per period
    if policy.max_claims_count:
        claims_count = InsuranceClaim.query.filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['pending', 'approved', 'paid']),
            InsuranceClaim.filed_date >= period_start,
            InsuranceClaim.filed_date <= period_end,
        ).count()

        if claims_count >= policy.max_claims_count:
            errors.append(f"You have reached the maximum number of claims ({policy.max_claims_count}) for this {policy.max_claims_period}.")

    period_payouts = None
    remaining_period_cap = None
    if policy.max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start,
            InsuranceClaim.processed_date <= period_end,
            InsuranceClaim.approved_amount.isnot(None),
        ).scalar() or 0.0
        remaining_period_cap = max(policy.max_payout_per_period - period_payouts, 0)

    eligible_transactions = []
    if policy.claim_type == 'transaction_monetary':
        claimed_tx_subq = db.session.query(InsuranceClaim.transaction_id).filter(
            InsuranceClaim.transaction_id.isnot(None)
        )
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.claim_time_limit_days)
        tx_query = (
            Transaction.query
            .filter(Transaction.student_id == student.id)
            .filter(Transaction.is_void == False)
            .filter(Transaction.timestamp >= cutoff_date)
            .filter(~Transaction.id.in_(claimed_tx_subq))
            .filter(Transaction.amount < 0)
        )
        if policy.teacher_id:
            tx_query = tx_query.filter(Transaction.teacher_id == policy.teacher_id)
        if enrollment.coverage_start_date:
            tx_query = tx_query.filter(Transaction.timestamp >= enrollment.coverage_start_date)

        eligible_transactions = tx_query.order_by(Transaction.timestamp.desc()).all()
        form.transaction_id.choices = [
            (
                tx.id,
                f"{tx.timestamp.strftime('%Y-%m-%d')} — {tx.description or 'No description'} (${abs(tx.amount):.2f})",
            )
            for tx in eligible_transactions
        ]
    else:
        form.transaction_id.choices = []

    if request.method == 'POST' and form.validate_on_submit():
        selected_transaction = None
        claim_amount_value = None
        claim_item_value = None
        incident_date_value = None
        transaction_id_value = None

        if policy.claim_type == 'transaction_monetary':
            if not form.transaction_id.data:
                flash("You must select a transaction for this claim type.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            selected_transaction = next((tx for tx in eligible_transactions if tx.id == form.transaction_id.data), None)
            if not selected_transaction:
                flash("Selected transaction is not eligible for claims.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            bind = db.session.get_bind()
            use_row_locking = bind and bind.dialect.name != 'sqlite'
            if use_row_locking:
                transaction_already_claimed = db.session.execute(
                    select(InsuranceClaim)
                    .where(InsuranceClaim.transaction_id == selected_transaction.id)
                    .with_for_update()
                ).scalar_one_or_none()
            else:
                transaction_already_claimed = InsuranceClaim.query.filter(
                    InsuranceClaim.transaction_id == selected_transaction.id
                ).first()

            if transaction_already_claimed:
                flash("This transaction already has a claim. Each transaction can only be claimed once.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            incident_date_value = selected_transaction.timestamp
            claim_amount_value = abs(selected_transaction.amount)
            transaction_id_value = selected_transaction.id

            days_since_incident = (datetime.now(timezone.utc) - incident_date_value).days
        else:
            incident_date_value = datetime.combine(form.incident_date.data, datetime.min.time())
            days_since_incident = (datetime.now(timezone.utc) - incident_date_value).days

        if policy.claim_type == 'non_monetary':
            if not form.claim_item.data:
                flash("Claim item is required for non-monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))
            claim_item_value = form.claim_item.data
        elif policy.claim_type == 'legacy_monetary':
            if not form.claim_amount.data:
                flash("Claim amount is required for monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))
            claim_amount_value = form.claim_amount.data

            if policy.max_claim_amount and claim_amount_value > policy.max_claim_amount:
                flash(f"Claim amount cannot exceed ${policy.max_claim_amount:.2f}.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

        if days_since_incident > policy.claim_time_limit_days:
            flash(f"Claims must be filed within {policy.claim_time_limit_days} days of the incident.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        if remaining_period_cap is not None and policy.claim_type != 'non_monetary' and remaining_period_cap <= 0:
            flash("You have reached the maximum payout limit for this period.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        claim = InsuranceClaim(
            student_insurance_id=enrollment.id,
            policy_id=policy.id,
            student_id=student.id,
            incident_date=incident_date_value,
            description=form.description.data,
            claim_amount=claim_amount_value if policy.claim_type != 'non_monetary' else None,
            claim_item=claim_item_value if policy.claim_type == 'non_monetary' else None,
            comments=form.comments.data,
            status='pending',
            transaction_id=transaction_id_value,
        )
        db.session.add(claim)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("This transaction already has a claim. Each transaction can only be claimed once.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Something went wrong while submitting your claim. Please try again.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        flash("Claim submitted successfully! It will be reviewed by your teacher.", "success")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this period
    claims_this_period = InsuranceClaim.query.filter_by(
        student_insurance_id=enrollment.id
    ).all()

    return render_template('student_file_claim.html',
                          student=student,
                          policy=policy,
                          enrollment=enrollment,
                          form=form,
                          errors=errors,
                          claims_this_period=claims_this_period,
                          eligible_transactions=eligible_transactions,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


@student_bp.route('/insurance/policy/<int:enrollment_id>')
@login_required
def view_policy(enrollment_id):
    """View policy details and claims history."""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this policy
    claims = InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    return render_template('student_view_policy.html',
                          student=student,
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          claims=claims,
                          now=datetime.now(timezone.utc))


# -------------------- SHOPPING --------------------

@student_bp.route('/shop')
@login_required
def shop():
    """Student shop - browse and purchase items."""
    # Check if store feature is enabled
    if not is_feature_enabled('store'):
        flash("The store feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']

    now = datetime.now(timezone.utc)
    items = StoreItem.query.filter(
        StoreItem.teacher_id == teacher_id,
        StoreItem.is_active == True,
        or_(StoreItem.auto_delist_date == None, StoreItem.auto_delist_date > now)
    ).order_by(StoreItem.name).all()

    # FIX: Fetch student's purchased items scoped to current teacher's store
    student_items = student.items.join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        StoreItem.teacher_id == teacher_id  # FIX: Only current class items
    ).order_by(StudentItem.purchase_date.desc()).all()

    return render_template('student_shop.html', student=student, items=items, student_items=student_items)


# -------------------- RENT --------------------

def _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=None, join_code=None):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, 0.0

    current_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)

    # Only charge if balance is negative
    if current_balance >= 0:
        return False, 0.0

    fee_amount = 0.0

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = banking_settings.overdraft_fee_flat_amount
    elif banking_settings.overdraft_fee_type == 'progressive':
        # Count how many overdraft fees charged this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        fee_filters = [
            Transaction.student_id == student.id,
            Transaction.type == 'overdraft_fee',
            Transaction.timestamp >= month_start
        ]
        if join_code:
            fee_filters.append(Transaction.join_code == join_code)
        elif teacher_id:
            fee_filters.append(Transaction.teacher_id == teacher_id)

        overdraft_fee_count = Transaction.query.filter(*fee_filters).count()

        # Determine which tier to use (1st, 2nd, 3rd, or cap)
        if overdraft_fee_count == 0:
            fee_amount = banking_settings.overdraft_fee_progressive_1 or 0.0
        elif overdraft_fee_count == 1:
            fee_amount = banking_settings.overdraft_fee_progressive_2 or 0.0
        elif overdraft_fee_count >= 2:
            fee_amount = banking_settings.overdraft_fee_progressive_3 or 0.0

        # Check if cap is exceeded
        if banking_settings.overdraft_fee_progressive_cap:
            total_filters = [
                Transaction.student_id == student.id,
                Transaction.type == 'overdraft_fee',
                Transaction.timestamp >= month_start
            ]
            if join_code:
                total_filters.append(Transaction.join_code == join_code)
            elif teacher_id:
                total_filters.append(Transaction.teacher_id == teacher_id)

            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                *total_filters
            ).scalar() or 0.0

            # total_fees_this_month is negative, so we negate it
            if abs(total_fees_this_month) + fee_amount > banking_settings.overdraft_fee_progressive_cap:
                # Don't charge more than the cap
                fee_amount = max(0, banking_settings.overdraft_fee_progressive_cap - abs(total_fees_this_month))

    if fee_amount > 0:
        # Charge the fee
        overdraft_fee_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=-fee_amount,
            account_type='checking',
            type='overdraft_fee',
            description=f'Overdraft fee (balance: ${current_balance:.2f})'
        )
        db.session.add(overdraft_fee_tx)
        db.session.flush()  # Update the balance calculation
        return True, fee_amount

    return False, 0.0


def _calculate_rent_deadlines(settings, reference_date=None):
    """Return the due date and grace end date for the active month."""
    reference_date = reference_date or datetime.now()

    # If first_rent_due_date is set and we haven't reached it yet, return it
    if settings.first_rent_due_date:
        first_due = settings.first_rent_due_date
        # If we're before the first due date, return the first due date
        if reference_date < first_due:
            grace_end_date = first_due + timedelta(days=settings.grace_period_days)
            return first_due, grace_end_date

        # Calculate due date based on frequency from first_rent_due_date
        if settings.frequency_type == 'monthly':
            # Calculate how many months have passed since first due date
            months_diff = (reference_date.year - first_due.year) * 12 + (reference_date.month - first_due.month)
            # Calculate the due date for the current period
            target_year = first_due.year + (first_due.month + months_diff - 1) // 12
            target_month = (first_due.month + months_diff - 1) % 12 + 1
            last_day_of_month = monthrange(target_year, target_month)[1]
            due_day = min(first_due.day, last_day_of_month)
            due_date = datetime(target_year, target_month, due_day)
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
                    months_diff = (reference_date.year - first_due.year) * 12 + (reference_date.month - first_due.month)

                    # Calculate the number of full periods passed
                    # We use integer division to find the start of the current cycle
                    periods = months_diff // settings.custom_frequency_value
                    total_months_add = periods * settings.custom_frequency_value

                    target_year = first_due.year + (first_due.month + total_months_add - 1) // 12
                    target_month = (first_due.month + total_months_add - 1) % 12 + 1

                    last_day_of_month = monthrange(target_year, target_month)[1]
                    due_day = min(first_due.day, last_day_of_month)
                    due_date = datetime(target_year, target_month, due_day)
                    # Preserve timezone if first_due had one
                    if first_due.tzinfo:
                        due_date = due_date.replace(tzinfo=first_due.tzinfo)

            if freq_delta:
                # Calculate periods passed for fixed time deltas
                time_diff = reference_date - first_due
                periods = time_diff // freq_delta
                due_date = first_due + (periods * freq_delta)

            if not freq_delta and settings.frequency_type != 'custom':
                # Fallback for unknown frequency types
                use_fallback = True
            elif settings.frequency_type == 'custom' and settings.custom_frequency_unit not in ['days', 'weeks', 'months']:
                 # Fallback for unknown custom units
                use_fallback = True
            else:
                use_fallback = False

            if use_fallback:
                current_year = reference_date.year
                current_month = reference_date.month
                last_day_of_month = monthrange(current_year, current_month)[1]
                due_day = min(settings.due_day_of_month, last_day_of_month)
                due_date = datetime(current_year, current_month, due_day)
                # Preserve timezone if first_due had one
                if first_due.tzinfo:
                    due_date = due_date.replace(tzinfo=first_due.tzinfo)

    else:
        # No first_rent_due_date set, use traditional monthly logic
        current_year = reference_date.year
        current_month = reference_date.month
        last_day_of_month = monthrange(current_year, current_month)[1]
        due_day = min(settings.due_day_of_month, last_day_of_month)
        due_date = datetime(current_year, current_month, due_day)

    grace_end_date = due_date + timedelta(days=settings.grace_period_days)
    return due_date, grace_end_date


@student_bp.route('/rent')
@login_required
def rent():
    """View rent status and payment history (per period)."""
    # Check if rent feature is enabled
    if not is_feature_enabled('rent'):
        flash("The rent feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context.get('teacher_id')
    join_code = context.get('join_code')
    current_block = (context.get('block') or '').strip().upper()
    settings = RentSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "info")
        return redirect(url_for('student.dashboard'))

    if not current_block:
        flash("No class period found for this class.", "error")
        return redirect(url_for('student.dashboard'))

    # Get student's periods (scoped to the current class only)
    student_blocks = [current_block]

    # Calculate rent status for each period
    now = datetime.now()

    # Calculate due dates
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)

    # Calculate preview start date if preview is enabled
    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = due_date - timedelta(days=settings.bill_preview_days)

    # Check if rent is active (due date has arrived or preview period has started)
    rent_is_active = True
    is_preview_period = False
    if settings.first_rent_due_date and now < settings.first_rent_due_date:
        # Check if we're in preview period before first due date
        if preview_start_date and now >= preview_start_date:
            rent_is_active = True
            is_preview_period = True
        else:
            rent_is_active = False
    elif preview_start_date and now >= preview_start_date and now < due_date:
        is_preview_period = True
    current_month = now.month
    current_year = now.year

    period_status = {}

    # Get all payments for the current period this month (supports incremental payments)
    all_payments_for_period = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.period == current_block,
        RentPayment.period_month == current_month,
        RentPayment.period_year == current_year,
        or_(RentPayment.join_code == join_code, RentPayment.join_code.is_(None)),
    ).all()

    # Filter out payments where the corresponding transaction was voided
    payments = []
    for payment in all_payments_for_period:
        txn = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.type == 'Rent Payment',
            or_(Transaction.join_code == join_code, Transaction.join_code.is_(None)),
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
            Transaction.amount == -payment.amount_paid
        ).first()

        if txn and not txn.is_void:
            payments.append(payment)

    total_paid = sum(p.amount_paid for p in payments) if payments else 0.0

    late_fee = 0.0
    if rent_is_active and now > grace_end_date:
        late_fee = settings.late_fee

    total_due = settings.rent_amount + late_fee if rent_is_active else 0.0
    is_paid = total_paid >= total_due if rent_is_active else False
    is_late = now > grace_end_date and not is_paid if rent_is_active else False
    remaining_amount = max(0, total_due - total_paid) if rent_is_active else 0.0

    period_status[current_block] = {
        'is_paid': is_paid,
        'is_late': is_late,
        'payments': payments,
        'total_paid': total_paid,
        'total_due': total_due,
        'remaining_amount': remaining_amount,
        'late_fee': late_fee,
        'rent_is_active': rent_is_active,
        'is_preview_period': is_preview_period
    }

    # Get scoped balances for this class only
    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)

    # Get payment history for the current class only
    payment_history = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        or_(RentPayment.join_code == join_code, RentPayment.join_code.is_(None)),
    ).order_by(
        RentPayment.payment_date.desc()
    ).limit(24).all()  # Increased to show more history with multiple periods

    return render_template('student_rent.html',
                          student=student,
                          settings=settings,
                          student_blocks=student_blocks,
                          period_status=period_status,
                          current_block=current_block,
                          join_code=join_code,
                          checking_balance=checking_balance,
                          savings_balance=savings_balance,
                          due_date=due_date,
                          grace_end_date=grace_end_date,
                          preview_start_date=preview_start_date,
                          payment_history=payment_history)


@student_bp.route('/rent/pay/<period>', methods=['POST'])
@login_required
def rent_pay(period):
    """Process rent payment for a specific period."""
    student = get_logged_in_student()
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context.get('teacher_id')
    join_code = context.get('join_code')
    current_block = (context.get('block') or '').upper()
    settings = RentSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student.dashboard'))

    if not student.is_rent_enabled:
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student.dashboard'))

    # Validate period for the current class context only
    period = period.upper()
    student_blocks = [current_block]
    if period != current_block:
        flash("Invalid period.", "error")
        return redirect(url_for('student.rent'))

    now = datetime.now()

    # Calculate due dates and preview period
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = due_date - timedelta(days=settings.bill_preview_days)

    # Check if rent is even due yet (if first_rent_due_date is in the future and not in preview period)
    if settings.first_rent_due_date and now < settings.first_rent_due_date:
        # Allow payment if we're in the preview period
        if not (preview_start_date and now >= preview_start_date):
            flash(f"Rent is not due yet. First payment due on {settings.first_rent_due_date.strftime('%B %d, %Y')}.", "info")
            return redirect(url_for('student.rent'))

    current_month = now.month
    current_year = now.year

    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)

    # Get all existing payments for this period this month
    all_payments = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.period == period,
        RentPayment.period_month == current_month,
        RentPayment.period_year == current_year,
        or_(RentPayment.join_code == join_code, RentPayment.join_code.is_(None)),
    ).all()

    # Filter out payments where the corresponding transaction was voided
    existing_payments = []
    for payment in all_payments:
        # Find the transaction for this payment
        txn = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.type == 'Rent Payment',
            or_(Transaction.join_code == join_code, Transaction.join_code.is_(None)),
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
            Transaction.amount == -payment.amount_paid
        ).first()

        # Only include if transaction exists and is not voided
        if txn and not txn.is_void:
            existing_payments.append(payment)

    total_paid_so_far = sum(p.amount_paid for p in existing_payments) if existing_payments else 0.0

    # Calculate if late and total amount due
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    is_late = now > grace_end_date

    # Calculate late fee if applicable
    late_fee = 0.0
    if is_late:
        late_fee = settings.late_fee

    # Total amount due (rent + late fee if applicable)
    total_due = settings.rent_amount + late_fee

    # Calculate remaining amount to pay
    remaining_amount = total_due - total_paid_so_far

    # Check if already fully paid
    if remaining_amount <= 0:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    # Get payment amount from form (supports incremental payments)
    payment_amount_input = request.form.get('amount', '').strip()

    # Determine payment amount based on incremental setting
    if settings.allow_incremental_payment and payment_amount_input:
        try:
            payment_amount = float(payment_amount_input)
            # Validate payment amount
            if payment_amount <= 0:
                flash("Payment amount must be greater than 0.", "error")
                return redirect(url_for('student.rent'))
            if payment_amount > remaining_amount:
                flash(f"Payment amount (${payment_amount:.2f}) exceeds remaining balance (${remaining_amount:.2f}). Paying exact remaining amount.", "info")
                payment_amount = remaining_amount
        except ValueError:
            flash("Invalid payment amount.", "error")
            return redirect(url_for('student.rent'))
    else:
        # Full payment required (or no amount specified with incremental disabled)
        payment_amount = remaining_amount

    # Get banking settings for overdraft handling (reuse teacher_id from above)
    banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None

    # Check if student has enough funds for this payment
    if checking_balance < payment_amount:
        # Check if overdraft protection is enabled (savings can cover the difference)
        if banking_settings and banking_settings.overdraft_protection_enabled:
            shortfall = payment_amount - checking_balance
            if savings_balance >= shortfall:
                # Allow transaction - overdraft protection will transfer from savings
                pass
            else:
                flash(f"Insufficient funds in both checking and savings. You need ${payment_amount:.2f} but have ${checking_balance + savings_balance:.2f}.", "error")
                return redirect(url_for('student.rent'))
        # Check if overdraft fees are enabled (allows negative balance)
        elif banking_settings and banking_settings.overdraft_fee_enabled:
            # Allow transaction - will charge overdraft fee after transaction
            pass
        else:
            # No overdraft options - reject transaction
            flash(f"Insufficient funds. You need ${payment_amount:.2f} but only have ${checking_balance:.2f}.", "error")
            return redirect(url_for('student.rent'))

    # FIX: Process payment with teacher_id
    # Deduct from checking account
    is_partial = payment_amount < remaining_amount
    payment_description = f'Rent for Period {period} - {now.strftime("%B %Y")}'
    if is_partial and settings.allow_incremental_payment:
        payment_description += f' (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})'
    elif late_fee > 0:
        payment_description += f' (includes ${late_fee:.2f} late fee)'

    projected_balance = checking_balance - payment_amount

    transaction = Transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,  # CRITICAL: Add join_code for period isolation
        amount=-payment_amount,
        account_type='checking',
        type='Rent Payment',
        description=payment_description
    )
    student.transactions.append(transaction)
    db.session.add(transaction)

    # Calculate late fee portion for this payment (proportional if partial payment)
    late_fee_for_this_payment = 0.0
    if is_late and late_fee > 0:
        # If this is a partial payment, allocate late fee proportionally
        if is_partial:
            late_fee_for_this_payment = (payment_amount / total_due) * late_fee
        else:
            late_fee_for_this_payment = late_fee

    # Record rent payment
    payment = RentPayment(
        student_id=student.id,
        period=period,
        join_code=join_code,
        amount_paid=payment_amount,
        period_month=current_month,
        period_year=current_year,
        was_late=is_late,
        late_fee_charged=late_fee_for_this_payment
    )
    db.session.add(payment)

    db.session.flush()  # Flush to update balances without committing yet

    # Handle overdraft protection and fees
    # Check if overdraft protection should transfer funds from savings
    if banking_settings and banking_settings.overdraft_protection_enabled and projected_balance < 0:
        shortfall = abs(projected_balance)
        if savings_balance >= shortfall:
            # CRITICAL FIX v2: Transfer from savings to checking with join_code
            transfer_tx_withdraw = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=-shortfall,
                account_type='savings',
                type='Withdrawal',
                description='Overdraft protection transfer to checking'
            )
            transfer_tx_deposit = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=shortfall,
                account_type='checking',
                type='Deposit',
                description='Overdraft protection transfer from savings'
            )
            db.session.add(transfer_tx_withdraw)
            db.session.add(transfer_tx_deposit)
            db.session.flush()  # Flush to update balances

    # Check if overdraft fee should be charged (after overdraft protection)
    fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=teacher_id, join_code=join_code)

    # Commit all transactions together
    db.session.commit()

    # Calculate new totals after this payment
    new_total_paid = total_paid_so_far + payment_amount
    new_remaining = total_due - new_total_paid

    # Success message
    if is_partial and settings.allow_incremental_payment:
        if new_remaining > 0:
            flash(f"Partial payment of ${payment_amount:.2f} successful! Remaining balance: ${new_remaining:.2f}", "success")
        else:
            flash(f"Final payment of ${payment_amount:.2f} successful! Rent for Period {period} is now fully paid.", "success")
    else:
        flash(f"Rent payment for Period {period} (${payment_amount:.2f}) successful!", "success")

    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
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
        
        current_app.logger.info(f"🔍 LOGIN ATTEMPT - Username: {username}, PIN length: {len(pin)}")
        
        lookup_hash = hash_username_lookup(username)
        student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()

        current_app.logger.info(f"🔍 Lookup hash: {lookup_hash[:16]}... | Student found: {student is not None}")
        if student:
            current_app.logger.info(f"🔍 Student ID: {student.id} | Has PIN hash: {student.pin_hash is not None}")

        try:
            # Fallback for legacy accounts without deterministic lookup hashes
            if not student:
                current_app.logger.info(f"🔍 No student found via lookup_hash, trying legacy fallback...")
                legacy_students_missing_lookup_hash = Student.query.filter(
                    Student.username_lookup_hash.is_(None),
                    Student.username_hash.isnot(None),
                )

                # Short-circuit if there are no legacy rows to scan
                if legacy_students_missing_lookup_hash.limit(1).first():
                    for s in legacy_students_missing_lookup_hash.yield_per(50):
                        candidate_hash = hash_username(username, s.salt)
                        if candidate_hash == s.username_hash:
                            student = s
                            current_app.logger.info(f"🔍 Found via legacy lookup! Student ID: {s.id}")
                            break

            # Validate PIN
            pin_valid = False
            if student:
                pin_valid = check_password_hash(student.pin_hash or '', pin)
                current_app.logger.info(f"🔍 PIN check result: {pin_valid}")
            
            if not student or not pin_valid:
                current_app.logger.warning(f"❌ LOGIN FAILED - Student found: {student is not None}, PIN valid: {pin_valid if student else 'N/A'}")
                if is_json:
                    return jsonify(status="error", message="Invalid credentials"), 401
                flash("Invalid credentials", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))

            if not student.username_lookup_hash:
                student.username_lookup_hash = lookup_hash
                db.session.commit()
                current_app.logger.info(f"✅ Updated username_lookup_hash for student {student.id}")
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during student login authentication: {str(e)}")
            if is_json:
                return jsonify(status="error", message="An error occurred during login. Please try again."), 500
            flash("An error occurred during login. Please try again.", "error")
            return redirect(url_for('student.login'))

        current_app.logger.info(f"✅ LOGIN SUCCESS - Student {student.id} ({username})")

        # --- Set session timeout ---
        # Clear old student-specific session keys without wiping the CSRF token
        session.pop('student_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        # Explicitly clear other potential student-related session keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)


        session['student_id'] = student.id
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['last_activity'] = session['login_time']


        # Removed redirect to student_setup for has_completed_setup; new onboarding flow uses claim → username → pin/passphrase.

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            return redirect(url_for('student.dashboard'))
        return redirect(next_url or url_for('student.dashboard'))

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)


@student_bp.route('/demo-login/<string:session_id>')
@admin_required
def demo_login(session_id):
    """Auto-login for demo student sessions created by admins.

    SECURITY: This route requires the user to already be logged in as the admin
    who created the demo session. Demo links cannot be used by anonymous users
    or other admins.
    """
    from app.models import DemoStudent, Admin

    try:
        # Find the demo session
        demo_session = DemoStudent.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()

        if not demo_session:
            flash("Demo session not found or has expired.", "error")
            return redirect(url_for('admin.dashboard'))

        # Check if session has expired
        now = datetime.now(timezone.utc)
        expires_at = demo_session.expires_at
        if not isinstance(expires_at, datetime):
            # If missing or invalid, refresh expiry to 10 minutes from now to avoid false immediate expiry
            expires_at = now + timedelta(minutes=10)
            demo_session.expires_at = expires_at
            db.session.commit()
        elif expires_at.tzinfo is None:
            # Treat naive timestamps as being in the admin's timezone (or fallback to UTC), then normalize to UTC
            tz_name = session.get('timezone') or 'UTC'
            try:
                local_tz = pytz.timezone(tz_name)
                expires_at = local_tz.localize(expires_at).astimezone(timezone.utc)
            except Exception:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            demo_session.expires_at = expires_at
            db.session.commit()

        if expires_at and now > expires_at:
            # Mark as inactive and cleanup
            cleanup_demo_student_data(demo_session)
            db.session.commit()
            flash("Demo session has expired (10 minute limit).", "error")
            return redirect(url_for('admin.dashboard'))

        # SECURITY: Verify the user is logged in as the admin who created this demo
        # This prevents privilege escalation via demo links
        if not session.get('is_admin') or session.get('admin_id') != demo_session.admin_id:
            current_app.logger.warning(
                f"Unauthorized demo login attempt for session {session_id}. "
                f"Current admin_id={session.get('admin_id')}, required={demo_session.admin_id}"
            )
            flash("You must be logged in as the admin who created this demo session.", "error")
            return redirect(url_for('admin.login'))

        # Set up student session (preserving admin authentication)
        student = demo_session.student

        # Clear student-specific keys only, preserve admin session
        session.pop('student_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        session.pop('is_demo', None)
        session.pop('demo_session_id', None)

        # Set student session variables
        session['student_id'] = student.id
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['last_activity'] = session['login_time']
        session['is_demo'] = True
        session['demo_session_id'] = session_id
        session['view_as_student'] = True
        # Ensure class context is set for dashboard queries
        demo_seat = student.roster_seats[0] if student.roster_seats else None
        if demo_seat:
            session['current_join_code'] = demo_seat.join_code

        current_app.logger.info(
            f"Admin {demo_session.admin_id} accessed demo session {session_id} "
            f"(student_id={student.id})"
        )

        flash("Demo session started! Session will expire in 10 minutes.", "success")
        return redirect(url_for('student.dashboard'))

    except Exception as e:
        current_app.logger.error(f"Error during demo login: {e}", exc_info=True)
        flash("An error occurred starting the demo session.", "error")
        return redirect(url_for('student.login'))


@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    # Check if this is a demo session
    is_demo = session.get('is_demo', False)
    demo_session_id = session.get('demo_session_id')

    if is_demo and demo_session_id:
        # Clean up demo session
        from app.models import DemoStudent
        try:
            demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
            if demo_session:
                demo_session.is_active = False
                demo_session.ended_at = datetime.now(timezone.utc)

                cleanup_demo_student_data(demo_session)

                db.session.commit()
                current_app.logger.info(f"Demo session {demo_session_id} ended and cleaned up")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cleaning up demo session: {e}", exc_info=True)

    session.clear()
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


@student_bp.route('/switch-class/<join_code>', methods=['POST'])
@login_required
def switch_class(join_code):
    """Switch to a different class using join_code for proper multi-tenancy isolation."""
    from app.models import TeacherBlock, Admin

    student = get_logged_in_student()

    # Verify student has a claimed seat for this join_code
    seat = TeacherBlock.query.filter_by(
        student_id=student.id,
        join_code=join_code,
        is_claimed=True
    ).first()

    if not seat:
        return jsonify(status="error", message="You don't have access to that class."), 403

    # Update session with new join code
    session['current_join_code'] = join_code

    # Get teacher name for response
    teacher = Admin.query.get(seat.teacher_id)
    teacher_name = teacher.username if teacher else "Unknown"

    # Get block/period info
    block_display = f"Block {seat.block.upper()}" if seat.block else "Unknown Block"

    return jsonify(
        status="success",
        message=f"Switched to {teacher_name}'s class ({block_display})",
        teacher_name=teacher_name,
        block=seat.block
    )


@student_bp.route('/switch-period/<int:teacher_id>', methods=['POST'])
@login_required
def switch_period(teacher_id):
    """DEPRECATED: Use switch_class instead. Kept for backwards compatibility."""
    student = get_logged_in_student()

    # Verify student has access to this teacher
    teacher_ids = [t.id for t in student.get_all_teachers()]
    if teacher_id not in teacher_ids:
        flash("You don't have access to that class.", "error")
        return redirect(url_for('student.dashboard'))

    # Update session with new teacher (old method)
    session['current_teacher_id'] = teacher_id

    # Get teacher name for flash message
    from app.models import Admin
    teacher = Admin.query.get(teacher_id)
    if teacher:
        flash(f"Switched to {teacher.username}'s class")

    return redirect(url_for('student.dashboard'))


# -------------------- SETUP COMPLETE --------------------
# Note: This route is not prefixed with /student for backward compatibility

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html', student_name=student.first_name)


# -------------------- HELP AND SUPPORT --------------------

@student_bp.route('/help-support', methods=['GET', 'POST'])
@login_required
def help_support():
    """Help and Support page with bug reporting, suggestions, and documentation."""
    student = get_logged_in_student()

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
            return redirect(url_for('student.help_support'))

        # Generate anonymous code derived from a secret to prevent reversal by admins
        anonymous_code = generate_anonymous_code(f"student:{student.id}")

        # Create report
        try:
            report = UserReport(
                anonymous_code=anonymous_code,
                user_type='student',
                report_type=report_type,
                error_code=error_code if error_code else None,
                title=title,
                description=description,
                steps_to_reproduce=steps_to_reproduce if steps_to_reproduce else None,
                expected_behavior=expected_behavior if expected_behavior else None,
                page_url=page_url if page_url else None,
                ip_address=get_real_ip(),
                user_agent=request.headers.get('User-Agent'),
                _student_id=student.id,  # Hidden from sysadmin, used only for rewards
                status='new'
            )
            db.session.add(report)
            db.session.commit()

            flash("Thank you for your report! If it's a legitimate bug, you may receive a reward.", "success")
            return redirect(url_for('student.help_support'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting report: {str(e)}")
            flash("An error occurred while submitting your report. Please try again.", "error")
            return redirect(url_for('student.help_support'))

    # Get student's previous reports (last 10)
    my_reports = UserReport.query.filter_by(_student_id=student.id).order_by(UserReport.submitted_at.desc()).limit(10).all()

    return render_template('student_help_support.html',
                         current_page='help',
                         page_title='Help & Support',
                         my_reports=my_reports,
                         help_content=HELP_ARTICLES['student'])


# ================== TEACHER ACCOUNT RECOVERY ==================

@student_bp.route('/verify-recovery/<int:code_id>', methods=['GET', 'POST'])
@login_required
def verify_recovery(code_id):
    """
    Student verification page for teacher account recovery.
    Student authenticates with passphrase, then gets a 6-digit code to give to teacher.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    from app.models import StudentRecoveryCode, RecoveryRequest
    recovery_code = StudentRecoveryCode.query.get_or_404(code_id)

    # Verify this is for the logged-in student
    if recovery_code.student_id != student.id:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Check if already verified
    if recovery_code.code_hash:
        flash("You have already verified this recovery request.", "info")
        return redirect(url_for('student.dashboard'))

    # Check if expired
    if recovery_code.recovery_request.expires_at < datetime.now(timezone.utc):
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
        if not student.passphrase_hash or not check_password_hash(student.passphrase_hash, passphrase):
            current_app.logger.warning(f"🛑 Recovery verification failed: incorrect passphrase for student {student.id}")
            flash("Incorrect passphrase. Please try again.", "error")
            return render_template('student_verify_recovery.html',
                                 recovery_code=recovery_code,
                                 student=student)

        # Generate 6-digit recovery code using cryptographically secure randomness
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Hash and store the code
        recovery_code.code_hash = hash_hmac(code.encode(), b'')
        recovery_code.verified_at = datetime.now(timezone.utc)
        db.session.commit()

        current_app.logger.info(f"🔐 Student {student.id} verified recovery request {recovery_code.recovery_request_id}")

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
def dismiss_recovery(code_id):
    """
    Dismiss the recovery notification banner.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    from app.models import StudentRecoveryCode
    recovery_code = StudentRecoveryCode.query.get_or_404(code_id)

    # Verify this is for the logged-in student
    if recovery_code.student_id != student.id:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Mark as dismissed
    recovery_code.dismissed = True
    db.session.commit()

    flash("Recovery notification dismissed. You can still verify later from your notifications.", "info")
    return redirect(url_for('student.dashboard'))
