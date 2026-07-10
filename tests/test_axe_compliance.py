"""
Playwright + axe-core WCAG 2.1 Level AA Compliance Tests
=========================================================
These tests use a real Chromium browser (via Playwright) and the industry-standard
axe-core engine (by Deque Systems) to audit key application routes.

Run exclusively:
    venv/bin/pytest tests/test_axe_compliance.py -v

This provides a validated, third-party second opinion alongside our own
tests/test_accessibility.py BeautifulSoup-based suite.

axe-core version: 4.9.1 (pinned, stored at tests/assets/axe-core.min.js)
Standard enforced: WCAG 2.1 Level AA
"""

import socket
import threading
import pytest
from datetime import datetime, timezone
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler

from app.extensions import db
from app.models import (
    ClassEconomy,
    Seat, IdentityProfile, RentSettings, User, TeacherOnboarding, ClassFeature,
)
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import make_admin
from app.hash_utils import hash_username
from app.utils.auth_username import build_hashed_username_fields
from werkzeug.security import generate_password_hash
from tests.helpers.canonical_session import set_canonical_context

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AXE_SCRIPT_PATH = Path(__file__).parent / "assets" / "axe-core.min.js"

# WCAG 2.1 AA tags used by axe-core
WCAG_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]

# Impact levels to fail on — critical and serious block compliance claims.
# "moderate" and "minor" are tracked but not assertion failures.
FAIL_ON_IMPACT = {"critical", "serious"}


# ---------------------------------------------------------------------------
# Silent WSGI request handler (suppress noisy access logs during tests)
# ---------------------------------------------------------------------------

class _SilentHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


# ---------------------------------------------------------------------------
# Session-scoped live server fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def axe_live_server(app):
    """
    Start the Flask app as a real HTTP server in a background thread.
    The same app instance (and SECRET_KEY) is used, so session cookies
    created by the Flask test client are valid here.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    httpd = make_server("127.0.0.1", port, app, handler_class=_SilentHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url

    httpd.shutdown()


# ---------------------------------------------------------------------------
# axe-core script fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def axe_script():
    """Load the pinned axe-core script from local cache."""
    if not AXE_SCRIPT_PATH.exists():
        raise FileNotFoundError(
            f"axe-core script not found at {AXE_SCRIPT_PATH}. "
            "Run: python -c \"import urllib.request; urllib.request.urlretrieve("
            "'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js', "
            "'tests/assets/axe-core.min.js')\""
        )
    return AXE_SCRIPT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def browser():
    """
    Launch a real Chromium browser without relying on pytest-playwright.
    Skip cleanly when Playwright or its browser binaries are not installed.
    """
    sync_api = pytest.importorskip(
        "playwright.sync_api",
        reason="Playwright is not installed; axe browser audits are optional until that dependency is added.",
    )

    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            yield browser
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright Chromium is unavailable: {exc}")


# ---------------------------------------------------------------------------
# Core audit helper
# ---------------------------------------------------------------------------

def run_axe_audit(page, axe_script_content, url):
    """
    Navigate to `url`, inject axe-core, run a WCAG 2.1 AA audit,
    and return the full results dict.
    """
    page.goto(url, wait_until="networkidle")
    page.add_script_tag(content=axe_script_content)
    results = page.evaluate(
        """async (tags) => {
            const r = await axe.run(document, {
                runOnly: { type: 'tag', values: tags }
            });
            return {
                violations: r.violations,
                passes: r.passes.length,
                inapplicable: r.inapplicable.length,
                incomplete: r.incomplete.length
            };
        }""",
        WCAG_AA_TAGS,
    )
    return results


def assert_no_blocking_violations(results, url, route_label):
    """
    Assert that no critical/serious axe violations are present.
    Logs all violations (including moderate/minor) for full transparency.
    """
    violations = results.get("violations", [])

    # Partition by impact
    blocking = [v for v in violations if v.get("impact") in FAIL_ON_IMPACT]
    advisory = [v for v in violations if v.get("impact") not in FAIL_ON_IMPACT]

    if advisory:
        advisory_summary = "\n".join(
            f"  [{v['impact'].upper()}] {v['id']}: {v['help']}"
            for v in advisory
        )
        print(f"\n[ADVISORY] {route_label} — {len(advisory)} moderate/minor violations "
              f"(not blocking):\n{advisory_summary}")

    if blocking:
        lines = [
            f"\n{'='*70}",
            f"axe-core WCAG 2.1 AA — BLOCKING violations on: {route_label}",
            f"URL: {url}",
            f"{'='*70}",
        ]
        for v in blocking:
            lines.append(f"\n[{v['impact'].upper()}] Rule: {v['id']}")
            lines.append(f"  Description: {v['description']}")
            lines.append(f"  Help: {v['help']}")
            lines.append(f"  More info: {v['helpUrl']}")
            lines.append(f"  WCAG criteria: {', '.join(v.get('tags', []))}")
            for node in v.get("nodes", [])[:3]:
                snippet = node.get("html", "")[:200]
                lines.append(f"  Failing node: {snippet}")
                for failure in node.get("failureSummary", "").split("\n")[:2]:
                    if failure.strip():
                        lines.append(f"    → {failure.strip()}")

        raise AssertionError("\n".join(lines))


# ---------------------------------------------------------------------------
# Cookie injection helper — bridges Flask test client auth ↔ Playwright
# ---------------------------------------------------------------------------

def inject_session_cookie(page, client, axe_live_server_url, trigger_path="/"):
    """
    Extract the Flask session cookie created by the test client and inject
    it into the Playwright browser context.

    This works because the live server and test client share the same app
    instance (same SECRET_KEY = 'test-secret'), so cookies are mutually valid.
    """
    session_cookie = None
    cookie = client.get_cookie("session")
    if cookie is not None:
        session_cookie = cookie.value

    if not session_cookie:
        # Fall back to a harmless public request so Flask emits the session cookie.
        client.get("/privacy", follow_redirects=False)
        cookie = client.get_cookie("session")
        if cookie is not None:
            session_cookie = cookie.value

    if not session_cookie:
        raise RuntimeError("No session cookie found in test client — auth fixture may have failed.")

    # Parse host from the live test-server URL for the cookie domain
    host = axe_live_server_url.replace("http://", "").split(":")[0]

    page.context.add_cookies([
        {
            "name": "session",
            "value": session_cookie,
            "domain": host,
            "path": "/",
            "httpOnly": True,
            "secure": False,
        }
    ])


# ---------------------------------------------------------------------------
# Auth fixtures (mirror test_accessibility.py but for Playwright)
# ---------------------------------------------------------------------------

@pytest.fixture
def teacher_page(app, client, axe_live_server, browser, axe_script):
    """
    A Playwright page authenticated as a teacher.
    Yields (page, live_server_url, axe_script).
    """
    with app.app_context():
        user = make_admin("axe_teacher_t")
        db.session.flush()

        join_code = "AXET01"
        class_row = create_class_scope(
            teacher_user=user,
            join_code=join_code,
            display_name="Axe Test Period",
        )

        user.last_active_class_id = class_row.class_id

        onboarding = TeacherOnboarding(
            user_id=user.id,
            is_completed=True,
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(onboarding)

        for feat in ClassFeature.feature_names():
            if not ClassFeature.query.filter_by(class_id=class_row.class_id, feature_name=feat).first():
                db.session.add(ClassFeature(class_id=class_row.class_id, feature_name=feat))
        db.session.commit()

        class_id = class_row.class_id
        user_id = user.id

    # Set session on test client
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = user_id
        sess["user_id"] = user_id
        sess["current_join_code"] = join_code
        sess["current_class_id"] = str(class_id)
        sess["is_system_admin"] = False
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    # Create Playwright page and inject session cookie
    context = browser.new_context()
    page = context.new_page()
    inject_session_cookie(page, client, axe_live_server)

    yield page, axe_live_server, axe_script

    context.close()


@pytest.fixture
def student_page(app, client, axe_live_server, browser, axe_script):
    """
    A Playwright page authenticated as a student.
    Yields (page, live_server_url, axe_script).
    """
    with app.app_context():
        teacher_user = make_admin("axe_teacher_s")
        db.session.flush()

        _, student_username_hash, student_username_lookup_hash = build_hashed_username_fields("axe_student")
        user = User(
            username_hash=student_username_hash,
            username_lookup_hash=student_username_lookup_hash,
            password_hash=generate_password_hash("secret"),
            pin_hash=generate_password_hash("1234"),
            user_role="student",
            has_completed_setup=True,
        )
        db.session.add(user)
        db.session.flush()
        profile = IdentityProfile(profile_type="student", first_name="AxeTest", last_name="S")
        db.session.add(profile)
        db.session.flush()

        join_code = "AXES01"
        class_row = create_class_scope(
            teacher_user=teacher_user,
            join_code=join_code,
            display_name="Axe Student Period",
        )
        seat = Seat(
            user_id=user.id,
            class_id=class_row.class_id,
            block="A",
            block_identifier="A",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(seat)
        db.session.flush()
        profile.seat_id = seat.id
        teacher_user.last_active_class_id = class_row.class_id
        user.last_active_class_id = class_row.class_id

        seat = Seat.query.filter_by(user_id=user.id, class_id=class_row.class_id).first()
        if seat:
            seat.claimed_at = datetime.now(timezone.utc)
            db.session.flush()
            user.last_active_seat_id = seat.id
            db.session.flush()

        db.session.add(RentSettings(class_id=class_row.class_id))
        for feat in ClassFeature.feature_names():
            if not ClassFeature.query.filter_by(class_id=class_row.class_id, feature_name=feat).first():
                db.session.add(ClassFeature(class_id=class_row.class_id, feature_name=feat))
        db.session.commit()

        student_id = seat.id if seat else None
        class_id = class_row.class_id
        user_id = user.id
        seat_id = seat.id if seat else None

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=str(class_id),
            seat_id=seat_id or 0,
            role="student",
            join_code=join_code,
        )
        sess["last_activity"] = sess["login_time"]

    context = browser.new_context()
    page = context.new_page()
    inject_session_cookie(page, client, axe_live_server)

    yield page, axe_live_server, axe_script

    context.close()


# ===========================================================================
# PUBLIC ROUTE TESTS
# ===========================================================================

def test_axe_privacy_page(axe_live_server, browser, axe_script):
    """WCAG 2.1 AA — /privacy"""
    page = browser.new_page()
    results = run_axe_audit(page, axe_script, f"{axe_live_server}/privacy")
    assert_no_blocking_violations(results, f"{axe_live_server}/privacy", "Privacy Policy")
    page.close()


def test_axe_district_page(axe_live_server, browser, axe_script):
    """WCAG 2.1 AA — /district"""
    page = browser.new_page()
    results = run_axe_audit(page, axe_script, f"{axe_live_server}/district")
    assert_no_blocking_violations(results, f"{axe_live_server}/district", "District Page")
    page.close()


def test_axe_offline_page(axe_live_server, browser, axe_script):
    """WCAG 2.1 AA — /offline"""
    page = browser.new_page()
    results = run_axe_audit(page, axe_script, f"{axe_live_server}/offline")
    assert_no_blocking_violations(results, f"{axe_live_server}/offline", "Offline Page")
    page.close()


def test_axe_docs_page(axe_live_server, browser, axe_script):
    """WCAG 2.1 AA — /docs/"""
    page = browser.new_page()
    results = run_axe_audit(page, axe_script, f"{axe_live_server}/docs/")
    assert_no_blocking_violations(results, f"{axe_live_server}/docs/", "Documentation Index")
    page.close()


# ===========================================================================
# STUDENT ROUTE TESTS
# ===========================================================================

def test_axe_student_dashboard(student_page):
    """WCAG 2.1 AA — /student/dashboard"""
    page, base, axe = student_page
    url = f"{base}/student/dashboard"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Dashboard")


def test_axe_student_transfer(student_page):
    """WCAG 2.1 AA — /student/transfer"""
    page, base, axe = student_page
    url = f"{base}/student/transfer"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Transfer")


def test_axe_student_rent(student_page):
    """WCAG 2.1 AA — /student/rent"""
    page, base, axe = student_page
    url = f"{base}/student/rent"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Rent")


def test_axe_student_shop(student_page):
    """WCAG 2.1 AA — /student/shop"""
    page, base, axe = student_page
    url = f"{base}/student/shop"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Shop")


def test_axe_student_insurance(student_page):
    """WCAG 2.1 AA — /student/insurance"""
    page, base, axe = student_page
    url = f"{base}/student/insurance"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Insurance Marketplace")


def test_axe_student_help_support(student_page):
    """WCAG 2.1 AA — /student/help-support"""
    page, base, axe = student_page
    url = f"{base}/student/help-support"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Student Help & Support")


# ===========================================================================
# TEACHER/ADMIN ROUTE TESTS
# ===========================================================================

def test_axe_teacher_dashboard(teacher_page):
    """WCAG 2.1 AA — /admin/"""
    page, base, axe = teacher_page
    url = f"{base}/admin/"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Dashboard")


def test_axe_teacher_students(teacher_page):
    """WCAG 2.1 AA — /admin/students"""
    page, base, axe = teacher_page
    url = f"{base}/admin/students"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Students Page")


def test_axe_teacher_rent_settings(teacher_page):
    """WCAG 2.1 AA — /admin/rent-settings"""
    page, base, axe = teacher_page
    url = f"{base}/admin/rent-settings"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Rent Settings")


def test_axe_teacher_store(teacher_page):
    """WCAG 2.1 AA — /admin/store"""
    page, base, axe = teacher_page
    url = f"{base}/admin/store"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Store Management")


def test_axe_teacher_insurance(teacher_page):
    """WCAG 2.1 AA — /admin/insurance"""
    page, base, axe = teacher_page
    url = f"{base}/admin/insurance"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Insurance Management")


def test_axe_teacher_payroll(teacher_page):
    """WCAG 2.1 AA — /admin/payroll"""
    page, base, axe = teacher_page
    url = f"{base}/admin/payroll"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Payroll Settings")


def test_axe_teacher_banking(teacher_page):
    """WCAG 2.1 AA — /admin/banking"""
    page, base, axe = teacher_page
    url = f"{base}/admin/banking"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Banking Settings")


def test_axe_teacher_analytics(teacher_page):
    """WCAG 2.1 AA — /admin/analytics"""
    page, base, axe = teacher_page
    url = f"{base}/admin/analytics"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Analytics Dashboard")


def test_axe_teacher_hall_pass(teacher_page):
    """WCAG 2.1 AA — /admin/hall-pass"""
    page, base, axe = teacher_page
    url = f"{base}/admin/hall-pass"
    results = run_axe_audit(page, axe, url)
    assert_no_blocking_violations(results, url, "Teacher Hall Pass")
