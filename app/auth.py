"""
Authentication and authorization utilities for Classroom Token Hub.

Contains session management helpers, authentication decorators, and timeout logic.
"""

import urllib.parse
from datetime import datetime, timedelta, timezone
from functools import wraps

import sqlalchemy as sa
from flask import session, flash, redirect, url_for, request, current_app


# -------------------- SESSION CONFIGURATION --------------------

SESSION_TIMEOUT_MINUTES = 10


# -------------------- AUTHENTICATION DECORATORS --------------------

def login_required(f):
    """
    Decorator to require student authentication for a route.

    Enforces a strict 10-minute timeout from login time for students.
    Also allows admins in view-as-student mode to access student routes.
    Redirects to student.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow access if admin is viewing as student
        if is_viewing_as_student():
            # Enforce 10-minute timeout for demo sessions even in admin view
            if session.get('is_demo'):
                login_time_str = session.get('login_time')

                if not login_time_str:
                    session.pop('student_id', None)
                    session.pop('login_time', None)
                    session.pop('last_activity', None)
                    session['view_as_student'] = False
                    session.pop('is_demo', None)
                    session.pop('demo_session_id', None)
                    flash("Demo session is invalid. Please start a new demo session.")
                    return redirect(url_for('admin.dashboard'))

                login_time = datetime.fromisoformat(login_time_str)
                if (datetime.now(timezone.utc) - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    demo_session_id = session.get('demo_session_id')

                    try:
                        if demo_session_id:
                            from app.demo_cleanup import cleanup_demo_student_records
                            from app.extensions import db
                            from app.models import DemoStudent

                            demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
                            if demo_session:
                                cleanup_demo_student_records(demo_session)
                                db.session.commit()
                            else:
                                db.session.rollback()
                    except Exception:
                        current_app.logger.exception(
                            "Failed to clean up expired demo session %s during auth check",
                            demo_session_id,
                        )

                    session.pop('student_id', None)
                    session.pop('login_time', None)
                    session.pop('last_activity', None)
                    session.pop('is_demo', None)
                    session.pop('demo_session_id', None)
                    session['view_as_student'] = False
                    flash("Demo session expired. Please start a new demo session.")
                    return redirect(url_for('admin.dashboard'))

            # Admins must also have a student context when bypassing login_required
            if 'student_id' not in session:
                session['view_as_student'] = False
                flash("Select a student before viewing the student experience.")
                return redirect(url_for('admin.dashboard'))

            # Update admin's last activity
            session['last_activity'] = datetime.now(timezone.utc).isoformat()
            return f(*args, **kwargs)

        # Regular student authentication check
        if 'student_id' not in session:
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")

        # Enforce strict 10-minute timeout from login time
        login_time_str = session.get('login_time')
        if not login_time_str:
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            flash("Session is invalid. Please log in again.")
            return redirect(url_for('student.login'))

        login_time = datetime.fromisoformat(login_time_str)
        if (datetime.now(timezone.utc) - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            flash("Session expired. Please log in again.")
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")

        # Continue to update last_activity for other potential uses, but it no longer controls the timeout
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to admin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"🧪 Admin access attempt: session = {dict(session)}")
        if not session.get("is_admin"):
            flash("You must be an admin to view this page.")
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        admin = get_current_admin()
        if not admin:
            session.pop("is_admin", None)
            session.pop("admin_id", None)
            session.pop("last_activity", None)
            flash("Admin session is invalid. Please log in again.")
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        now = datetime.now(timezone.utc)
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_admin", None)
                flash("Admin session expired. Please log in again.")
                encoded_next = urllib.parse.quote(request.path, safe="")
                return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


def system_admin_required(f):
    """
    Decorator to require system admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to sysadmin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_system_admin"):
            flash("System administrator access required.")
            return redirect(url_for('sysadmin.login', next=request.path))
        last_activity = session.get('last_activity')
        now = datetime.now(timezone.utc)
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if now - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_system_admin", None)
                flash("Session expired. Please log in again.")
                return redirect(url_for('sysadmin.login', next=request.path))
        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


# -------------------- HELPER FUNCTIONS --------------------

def get_logged_in_student():
    """
    Get the currently logged-in student from the session.

    Returns:
        Student: The logged-in Student object, or None if not logged in.
    """
    # Import here to avoid circular imports
    from app.models import Student
    return Student.query.get(session['student_id']) if 'student_id' in session else None


def get_current_admin():
    """Return the logged-in admin based on the session state."""
    if not session.get("is_admin"):
        return None
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    from app.models import Admin  # Imported lazily to avoid circular import
    return Admin.query.get(admin_id)


def get_admin_student_query(include_unassigned=True):
    """Return a Student query scoped to the current admin's ownership.

    System admins are allowed to see all students. Regular admins only see
    students they own, with optional access to unassigned students during
    migration.
    """
    from app.models import Student, StudentTeacher  # Imported lazily to avoid circular import

    if session.get("is_system_admin"):
        return Student.query

    admin = get_current_admin()
    if not admin:
        return Student.query.filter(sa.text("0=1"))

    shared_student_ids = (
        StudentTeacher.query.with_entities(StudentTeacher.student_id)
        .filter(StudentTeacher.admin_id == admin.id)
        .subquery()
    )

    filters = [
        Student.teacher_id == admin.id,
        Student.id.in_(shared_student_ids),
    ]
    if include_unassigned:
        filters.append(Student.teacher_id.is_(None))
    return Student.query.filter(sa.or_(*filters))


def get_student_for_admin(student_id, include_unassigned=True):
    """Return a student the current admin can access, or None."""
    query = get_admin_student_query(include_unassigned=include_unassigned)
    return query.filter_by(id=student_id).first()


def is_viewing_as_student():
    """
    Check if the current user is an admin viewing as a student.

    Returns:
        bool: True if admin is in view-as-student mode, False otherwise.
    """
    return session.get("is_admin") and session.get("view_as_student", False)


def can_access_student_routes():
    """
    Check if the current user can access student routes.

    Returns True if:
    - User is a logged-in student, OR
    - User is an admin in view-as-student mode

    Returns:
        bool: True if user can access student routes, False otherwise.
    """
    return 'student_id' in session or is_viewing_as_student()
