from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, current_app
from datetime import timedelta
import secrets

from app.extensions import db, limiter
from app.models import Seat, User
from app.auth import admin_required
from app.utils.canonical_temporal_resolver import utc_now, ensure_utc

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')
RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


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
def generate_reset_code(seat_id):
    """
    Step 1 — Teacher Initiates Reset (DOM-IDEN-002 §IX).

    Resolves the Seat to its bound User, then writes the recovery code directly
    to users.reset_code / reset_code_generated_at / reset_code_expires_at.
    Overwrites any existing code (single active code invariant).
    """
    seat = db.session.get(Seat, seat_id)
    if not seat:
        flash("Seat not found.", "error")
        return redirect(url_for('admin.students'))

    linked_user = db.session.get(User, seat.user_id) if seat.user_id else None
    if not linked_user:
        flash("Student has no linked account.", "error")
        return redirect(url_for('admin.students'))

    # Generate and overwrite any existing code (DOM-IDEN-002 §IX invariant 4).
    code = _generate_reset_code(8)
    now = utc_now()
    linked_user.reset_code = code
    linked_user.reset_code_generated_at = now
    linked_user.reset_code_expires_at = now + timedelta(minutes=10)

    db.session.flush()  # FEAT-LEGACY-WRAP: commit removed

    current_app.logger.info(
        "Reset code generated for seat %s (user %s) by user %s",
        seat.id, linked_user.id, g.canonical_context.user_id,
    )

    display_name = seat.identity_profile.first_name if seat.identity_profile else str(seat.id)
    flash(
        f"Reset code generated for {display_name}: {code} — Expires in 10 minutes. "
        f"Give this code to the student.",
        "success",
    )
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
def account_lookup():
    """
    Step 2 — Student Submits Reset Code (DOM-IDEN-002 §IX).

    Student submits only the reset code. Backend finds the matching users row
    directly (no join_code or PII required). On success: credentials are cleared
    and student is directed to the credential setup flow.
    """
    if request.method == 'POST':
        reset_code = request.form.get('reset_code', '').strip().upper()

        if not reset_code:
            flash("Reset code is required.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Query users row directly by reset_code (DOM-IDEN-002 §IX Step 2).
        linked_user = User.query.filter_by(reset_code=reset_code).first()

        # Validate all conditions — use a single generic error for security.
        valid = (
            linked_user is not None
            and linked_user.reset_code_expires_at is not None
            and ensure_utc(linked_user.reset_code_expires_at) >= utc_now()
        )

        if not valid:
            session.pop('recovery_student_ref', None)
            flash("Invalid or expired recovery code.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Find the seat to anchor the setup session.
        seat = (
            Seat.query
            .filter_by(user_id=linked_user.id)
            .order_by(Seat.id.asc())
            .first()
        )

        # Clear credentials — forces fresh credential setup.
        linked_user.username_lookup_hash = None
        linked_user.pin_hash = None
        linked_user.passphrase_hash = None
        # Clear the recovery code so it cannot be reused.
        linked_user.reset_code = None
        linked_user.reset_code_generated_at = None
        linked_user.reset_code_expires_at = None

        if seat and seat.claimed_at is None:
            seat.claimed_at = utc_now()

        db.session.flush()  # FEAT-LEGACY-WRAP: commit removed

        current_app.logger.info(
            "Recovery lookup succeeded for user %s (seat %s); credentials cleared.",
            linked_user.id, seat.id if seat else None,
        )

        # Set session for credential setup flow.
        session['onboarding_seat_ref'] = seat.id if seat else None
        session['onboarding_user_ref'] = linked_user.id
        session.pop('recovery_student_ref', None)

        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/account_lookup.html')
