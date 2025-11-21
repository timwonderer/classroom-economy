"""
Main routes for Classroom Token Hub.

Contains public-facing utility routes including health checks, legal pages,
debug endpoints, and hall pass terminals (no authentication required).
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Admin

# Create blueprint
main_bp = Blueprint('main', __name__)


# -------------------- HOME AND LEGAL PAGES --------------------

@main_bp.route('/')
def home():
    """Redirect to student login page."""
    return redirect(url_for('student.login'))


@main_bp.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        current_app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500


@main_bp.route('/privacy')
def privacy():
    """Render the Privacy & Data Handling Policy page."""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Render the Terms of Service page."""
    return render_template('tos.html')


# -------------------- HALL PASS TERMINALS (NO AUTH REQUIRED) --------------------

@main_bp.route('/hall-pass/terminal')
def hall_pass_terminal():
    """Hall Pass Check in/out terminal page (no login required)."""
    return render_template('hall_pass_terminal.html')


@main_bp.route('/hall-pass/verification')
def hall_pass_verification():
    """Hall Pass Verification page for display (no login required)."""
    return render_template('hall_pass_verification.html')


@main_bp.route('/hall-pass/queue')
def hall_pass_queue():
    """Hall Pass Queue display page (no login required)."""
    return render_template('hall_pass_queue.html')


# -------------------- DEBUG ROUTES --------------------

@main_bp.route('/debug/filters')
def debug_filters():
    """List all available Jinja2 filters for debugging."""
    return jsonify(list(current_app.jinja_env.filters.keys()))


@main_bp.route('/debug/admin-db-test')
def debug_admin_db_test():
    """
    Temporary route to confirm admin and invite codes tables are accessible.
    """
    try:
        admins = Admin.query.all()
        invite_codes_count = db.session.execute(text('SELECT COUNT(*) FROM admin_invite_codes')).scalar()
        return jsonify({
            "admin_count": len(admins),
            "invite_codes_count": invite_codes_count,
            "status": "success"
        }), 200
    except Exception as e:
        current_app.logger.exception("Admin DB test failed")
        return jsonify({"status": "error", "error": str(e)}), 500
