from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, current_app
from datetime import timedelta
import secrets

from app.extensions import db, limiter
from app.models import ClassEconomy, IdentityProfile, Seat, Student, User
from app.auth import admin_required
from app.utils.time import utc_now, ensure_utc

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')
RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _find_linked_user_for_student(student_id: int | None) -> User | None:
    if not student_id:
        return None
    return (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(
            Student.id == student_id,
            Seat.user_id.isnot(None),
        )
        .order_by(Seat.id.asc())
        .first()
    )

def _recovery_rate_limit():
    """Use strict limits in runtime, relaxed limits in test environments."""
    if current_app.testing:
        return "1000 per minute"
    return "10 per minute"


def _generate_reset_code(length=8):
    """Generate an uppercase, unambiguous alphanumeric recovery code."""
    return ''.join(secrets.choice(RESET_CODE_ALPHABET) for _ in range(length))


from app.feats.base import feat_shell

# ----------------------------------------------------------------------
# TEACHER ROUTES
# ----------------------------------------------------------------------

@recovery_bp.route('/admin/generate-code/<int:student_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-IDEN-002")
def generate_reset_code(*args, **kwargs):
    """FEAT-Shell for recovery code generation."""
    return _generate_reset_code_legacy(*args, **kwargs)

def _generate_reset_code_legacy(student_id):
    """
    Step 1 — Teacher Initiates Reset (LEGACY).

    System must:
      - Set student status -> to_be_claimed
      - Invalidate any existing reset_code
      - Generate new 8-character mixed alphanumeric reset_code
      - Set reset_code_expires_at = now + 10 minutes
      - Log reset event
    """
    # Verify scoping: admin must have access to this student
    from app.routes.admin import _scoped_students
    student = _scoped_students().filter_by(id=student_id).first()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for('admin.students'))
 
    # Invalidate any existing reset_code, then generate new one
    code = _generate_reset_code(8)
 
    student.reset_code = code
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
 
    db.session.flush() # FEAT-LEGACY-WRAP: commit removed
 
    current_app.logger.info(
        f"Reset code generated for student {student.id} by user {g.canonical_context.user_id}"
    )

    flash(f"Reset code generated for {student.full_name} "
          f"Code: {code} — Expires in 10 minutes.", "success")
    from app.routes.admin import _build_student_detail_url
    detail_url = _build_student_detail_url(student.id, teacher_id=g.canonical_context.user_id)
    if not detail_url:
        return redirect(url_for('admin.students'))
    return redirect(detail_url)

# ----------------------------------------------------------------------
# STUDENT ROUTES — Single Recovery Flow
# ----------------------------------------------------------------------

@recovery_bp.route('/', methods=['GET'])
def landing():
    """Redirect to account recovery lookup (single flow)."""
    return redirect(url_for('recovery.account_lookup'))


@recovery_bp.route('/lookup', methods=['GET', 'POST'])
@limiter.limit(_recovery_rate_limit)
@feat_shell("FEAT-IDEN-002")
def account_lookup(*args, **kwargs):
    """FEAT-Shell for student account lookup."""
    return _account_lookup_legacy(*args, **kwargs)

def _account_lookup_legacy():
    """
    Step 2 — Student Enters Join Code + Reset Code (LEGACY).

    Validates:
      - reset_code exists
      - reset_code unexpired
      - student.recovery_status == to_be_claimed
      - join_code matches a claimed seat for this student

    On success: clears old credentials and redirects straight to username/credential
    setup. No PII re-entry is required — first name and last initial are managed by
    the teacher and remain unchanged through recovery.
    """
    if request.method == 'POST':
        join_code = request.form.get('join_code', '').strip().upper()
        reset_code = request.form.get('reset_code', '').strip().upper()
 
        if not join_code or not reset_code:
            flash("Both fields are required.", "error")
            return redirect(url_for('recovery.account_lookup'))
 
        # Resolve class_id from the ingress join code, then immediately switch to seat/class scope.
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if not class_row:
            flash("Invalid join code.", "error")
            return redirect(url_for('recovery.account_lookup'))
        seat = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .join(Student, Student.identity_id == IdentityProfile.id)
            .filter(
                Seat.class_id == class_row.class_id,
                Seat.role == "student",
                Student.reset_code == reset_code,
            )
            .first()
        )
        student = (
            db.session.query(Student)
            .join(IdentityProfile, IdentityProfile.id == Student.identity_id)
            .join(Seat, Seat.id == IdentityProfile.seat_id)
            .filter(Seat.id == seat.id)
            .first()
        ) if seat else None
 
        # Validate all conditions — use a single generic error for security
        valid = True
 
        if not student:
            valid = False
        elif not student.reset_code_expires_at or ensure_utc(student.reset_code_expires_at) < utc_now():
            valid = False
        elif student.recovery_status != 'to_be_claimed':
            valid = False
 
        if not valid:
            session.pop('recovery_student_ref', None)
            flash("Invalid or expired recovery code.", "error")
            return redirect(url_for('recovery.account_lookup'))
 
        # Clear all credentials — forces fresh credential setup (username, PIN, passphrase).
        # first_name and last_initial are preserved; they are managed by the teacher.
        if seat and seat.claimed_at is None:
            seat.claimed_at = utc_now()

        linked_user = _find_linked_user_for_student(student.id)
        if not linked_user:
            current_app.logger.error(
                "Recovery lookup failed closed: student_id=%s has no canonical user principal",
                student.id,
            )
            flash("Account identity is incomplete. Contact support.", "error")
            return redirect(url_for('recovery.account_lookup'))

        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False
        linked_user.username_lookup_hash = None
        linked_user.pin_hash = None
        linked_user.passphrase_hash = None
        linked_user.has_completed_setup = False

        if seat and linked_user and seat.user_id != linked_user.id:
            seat.user_id = linked_user.id
 
        db.session.flush() # FEAT-LEGACY-WRAP: commit removed

        current_app.logger.info(
            f"Recovery lookup succeeded for student {student.id}; credentials cleared."
        )

        # Set session for credential setup flow
        session['onboarding_student_ref'] = student.id
        session['onboarding_seat_ref'] = seat.id if seat else None
        session['onboarding_user_ref'] = linked_user.id if linked_user else None
        session.pop('recovery_student_ref', None)

        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/account_lookup.html')


@recovery_bp.route('/verify-identity', methods=['GET', 'POST'])
def verify_identity():
    """Deprecated — identity re-entry is no longer required for recovery.

    Redirects to account_lookup so students with bookmarked URLs land somewhere useful.
    """
    return redirect(url_for('recovery.account_lookup'))
