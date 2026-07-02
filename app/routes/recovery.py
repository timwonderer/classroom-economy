from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, current_app
from datetime import timedelta
import secrets

from app.extensions import db, limiter
from app.models import ClassEconomy, IdentityProfile, Seat, User
from app.auth import admin_required
from app.utils.time import utc_now, ensure_utc

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')
RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _find_linked_user_for_seat(seat_id: int | None) -> User | None:
    if not seat_id:
        return None
    return (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(Seat.user_id.isnot(None), IdentityProfile.seat_id == seat_id)
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

@recovery_bp.route('/admin/generate-code/<int:seat_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-IDEN-002")
def generate_reset_code(*args, **kwargs):
    """FEAT-Shell for recovery code generation."""
    return _generate_reset_code_legacy(*args, **kwargs)

def _generate_reset_code_legacy(seat_id):
    """
    Step 1 — Teacher Initiates Reset (LEGACY).

    System must:
      - Set student status -> to_be_claimed
      - Invalidate any existing reset_code
      - Generate new 8-character mixed alphanumeric reset_code
      - Set reset_code_expires_at = now + 10 minutes
      - Log reset event
    """
    # Resolve the seat directly; recovery should not depend on scoped Student queries.
    seat = Seat.query.filter_by(id=seat_id).first()
    if not seat:
        flash("Seat not found.", "error")
        return redirect(url_for('admin.students'))

    student_identity = db.session.query(IdentityProfile).filter(IdentityProfile.seat_id == seat.id).first()
    if not student_identity:
        flash("Seat not found.", "error")
        return redirect(url_for('admin.students'))

    # Invalidate any existing reset_code, then generate new one.
    code = _generate_reset_code(8)

    student_identity.reset_code = code
    student_identity.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student_identity.recovery_status = 'to_be_claimed'

    db.session.flush()  # FEAT-LEGACY-WRAP: commit removed

    current_app.logger.info(
        f"Reset code generated for seat {seat.id} by user {g.canonical_context.user_id}"
    )

    flash(f"Reset code generated for {seat.display_first_name} "
          f"Code: {code} — Expires in 10 minutes.", "success")
    from app.routes.admin import _build_student_detail_url
    detail_url = _build_student_detail_url(seat.public_id)
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
 
        # Resolve class_id from user-provided join_code, then query by canonical class_id.
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        if not class_row:
            flash("Invalid join code.", "error")
            return redirect(url_for('recovery.account_lookup'))
        identity = (
            IdentityProfile.query
            .join(Seat, Seat.id == IdentityProfile.seat_id)
            .filter(
                Seat.class_id == class_row.class_id,
                IdentityProfile.reset_code == reset_code,
            )
            .first()
        )
        seat = None
        if identity:
            seat = db.session.get(Seat, identity.seat_id) if identity.seat_id else None
 
        # Validate all conditions — use a single generic error for security
        valid = True
 
        if not identity:
            valid = False
        elif not identity.reset_code_expires_at or ensure_utc(identity.reset_code_expires_at) < utc_now():
            valid = False
        elif identity.recovery_status != 'to_be_claimed':
            valid = False
 
        if not valid:
            session.pop('recovery_student_ref', None)
            flash("Invalid or expired recovery code.", "error")
            return redirect(url_for('recovery.account_lookup'))
 
        # Clear all credentials — forces fresh credential setup (username, PIN, passphrase).
        # first_name and last_initial are preserved; they are managed by the teacher.
        if seat and seat.claimed_at is None:
            seat.claimed_at = utc_now()

        linked_user = _find_linked_user_for_seat(seat.id if seat else None)
        if not linked_user:
            current_app.logger.error(
                "Recovery lookup failed closed: seat_id=%s has no canonical user principal",
                seat.id if seat else None,
            )
            flash("Account identity is incomplete. Contact support.", "error")
            return redirect(url_for('recovery.account_lookup'))

        identity.username_hash = None
        identity.username_lookup_hash = None
        identity.pin_hash = None
        identity.passphrase_hash = None
        identity.has_completed_setup = False
        linked_user.username_lookup_hash = None
        linked_user.pin_hash = None
        linked_user.passphrase_hash = None
        linked_user.has_completed_setup = False

        if seat and linked_user and seat.user_id != linked_user.id:
            seat.user_id = linked_user.id
 
        db.session.flush() # FEAT-LEGACY-WRAP: commit removed

        current_app.logger.info(
            f"Recovery lookup succeeded for seat {seat.id if seat else None}; credentials cleared."
        )

        # Set session for credential setup flow
        session['onboarding_student_ref'] = seat.id if seat else None
        session['onboarding_seat_ref'] = seat.id if seat else None
        session['onboarding_user_ref'] = linked_user.id if linked_user else None
        session.pop('recovery_student_ref', None)

        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/account_lookup.html')

