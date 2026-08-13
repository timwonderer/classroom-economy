from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, current_app

from app.extensions import db, limiter
from app.models import Seat
from app.auth import admin_required
from app.feats.base import feat_shell

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')


def _recovery_rate_limit():
    """Use strict limits in runtime, relaxed limits in test environments."""
    if current_app.testing:
        return "1000 per minute"
    return "10 per minute"

# ----------------------------------------------------------------------
# TEACHER ROUTES
# ----------------------------------------------------------------------

@recovery_bp.route('/admin/generate-code/<int:seat_id>', methods=['POST'])
@admin_required
@feat_shell("FEAT-IDEN-003")
def generate_reset_code(seat_id):
    """
    Step 1 — Teacher Initiates Reset (DOM-IDEN-002 §IX).

    Delegates to FEAT-IDEN-003 for reset code generation.
    """
    from app.feats.identity_feat import generate_teacher_reset_code

    result = generate_teacher_reset_code(
        seat_id=seat_id,
        teacher_user_id=g.canonical_context.user_id,
    )

    if not result.success:
        flash(result.error_message, "error")
        return redirect(url_for('admin.students'))

    flash(
        f"Reset code generated for {result.display_name}: {result.code} — Expires in 10 minutes. "
        f"Give this code to the student.",
        "success",
    )
    from app.routes.admin import _build_student_detail_url
    seat = db.session.get(Seat, seat_id)
    detail_url = _build_student_detail_url(seat.public_id) if seat else None
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
@feat_shell("FEAT-IDEN-004")
def account_lookup():
    """
    Step 2 — Student Submits Reset Code (DOM-IDEN-002 §IX).

    Delegates to FEAT-IDEN-004 for recovery code validation and credential clearing.
    """
    if request.method == 'POST':
        reset_code = request.form.get('reset_code', '').strip().upper()

        if not reset_code:
            flash("Reset code is required.", "error")
            return redirect(url_for('recovery.account_lookup'))

        from app.feats.identity_feat import validate_recovery_code

        result = validate_recovery_code(reset_code=reset_code)

        if not result.success:
            session.pop('recovery_student_ref', None)
            flash(result.error_message, "error")
            return redirect(url_for('recovery.account_lookup'))

        # Set session for credential setup flow.
        session['onboarding_seat_ref'] = result.seat_id
        session['onboarding_user_ref'] = result.user_id
        session.pop('recovery_student_ref', None)

        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/account_lookup.html')
