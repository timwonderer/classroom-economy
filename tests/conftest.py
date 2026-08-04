import os
import csv
import re
import statistics
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

# Phase 1 FEATBypass instrumentation (opt-in). When FEAT_BYPASS_AUDIT=1, the
# audit plugin is registered, which hooks SQLAlchemy `before_flush` to record
# every bypass-hidden mutation and emit a report at session end. See
# docs/TRACKING/V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md for context.
if os.environ.get("FEAT_BYPASS_AUDIT"):
    pytest_plugins = ["tests._feat_bypass_audit"]

# Load environment variables from the project root .env file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=DOTENV_PATH)

# Read TEST_DATABASE_URL directly from .env so tests can use the dedicated test DB
dotenv_config = dotenv_values(DOTENV_PATH)
test_database_url = (
    dotenv_config.get("TEST_DATABASE_URL")
    or os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")  # CI sets DATABASE_URL; accept it when TEST_DATABASE_URL is absent
)
if not test_database_url:
    raise RuntimeError("TEST_DATABASE_URL must be set in .env for tests.")

# Override env vars for testing
os.environ["SECRET_KEY"] = "test-secret"
os.environ["TEST_DATABASE_URL"] = test_database_url
os.environ["DATABASE_URL"] = test_database_url
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("PEPPER", "legacy-pepper")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# Ensure ENCRYPTION_KEY and PEPPER_KEY are set for tests, if not already in .env
# Use valid Fernet keys (32 url-safe base64-encoded bytes)
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("PEPPER_KEY", "tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=")
os.environ.setdefault("AUDIT_HMAC_KEY", "test-audit-hmac-key-for-tests-only-not-for-production")


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from flask_migrate import upgrade
from app import app as flask_app, db
from flask import current_app
from app.extensions import limiter
from app.models import Transaction, Seat, IdentityProfile


_TEST_REPORTS_BY_NODEID = {}
_TEST_MARKERS_BY_NODEID = {}

_CSV_COLUMNS = [
    "generated_utc",
    "git_commit",
    "pytest_label",
    "nodeid",
    "test_file",
    "test_class",
    "test_name",
    "outcome",
    "duration_ms",
    "exception_type",
    "exception_message",
    "first_project_frame",
    "markers",
]


def _sanitize_result_label(value: str) -> str:
    """Normalize label text to filesystem-safe characters."""
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in value)
    cleaned = cleaned.strip("_")
    return cleaned or "specific"


def _resolve_pytest_result_label(pytest_args, session_items) -> str:
    """Use full for suite runs and derive a file label for single-file runs."""
    # First preference: if all collected tests came from one file, use that file stem.
    file_parts = [str(item.nodeid).split("::", 1)[0] for item in session_items]
    unique_files = sorted({part for part in file_parts if part.endswith(".py")})
    if len(unique_files) == 1:
        return _sanitize_result_label(Path(unique_files[0]).stem)

    # Fallback: resolve from invocation args where available.
    positional = [str(arg) for arg in pytest_args if isinstance(arg, str) and not arg.startswith("-")]
    if not positional:
        return "full"

    first = positional[0]
    first_path = Path(first)
    if first_path.suffix == ".py":
        return _sanitize_result_label(first_path.stem)

    if first in ("tests", "tests/"):
        return "full"

    return "specific"


def _resolve_git_commit() -> str:
    """Resolve short git commit once per session for artifact metadata."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return "unknown"


def _parse_nodeid(nodeid: str) -> tuple[str, str, str]:
    """Split nodeid into file/class/name components."""
    parts = nodeid.split("::")
    test_file = parts[0] if parts else ""
    if len(parts) <= 1:
        return test_file, "", ""
    if len(parts) == 2:
        return test_file, "", parts[1]
    return test_file, "::".join(parts[1:-1]), parts[-1]


def _first_project_frame(longreprtext: str) -> str:
    """Return first meaningful project frame (prefer app/, then tests/)."""
    if not longreprtext:
        return ""
    frame_pattern = re.compile(r"^\s*((?:app|tests|scripts|migrations)/[^:\n]+):(\d+):")
    matches = []
    for line in longreprtext.splitlines():
        match = frame_pattern.match(line)
        if match:
            matches.append(f"{match.group(1)}:{match.group(2)}")

    if not matches:
        return ""

    for frame in matches:
        if frame.startswith("app/"):
            return frame

    return matches[0]
    return ""


def _extract_exception(report) -> tuple[str, str]:
    """Extract compact exception type and first message line from pytest report."""
    if not report.failed:
        return "", ""

    text = getattr(report, "longreprtext", "") or ""
    if not text:
        return "", ""

    exc_re = re.compile(r"^\s*E\s+([A-Za-z_][\w\.]*)(?::\s*(.*))?$")
    for line in reversed(text.splitlines()):
        match = exc_re.match(line)
        if match:
            full_name = match.group(1)
            exc_type = full_name.split(".")[-1]
            exc_msg = (match.group(2) or "").strip()
            return exc_type, exc_msg

    message_line = ""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            message_line = stripped
            break

    if not message_line:
        return "", ""

    if ":" in message_line:
        exc_type, exc_msg = message_line.split(":", 1)
        exc_type = exc_type.strip()
        if "/" in exc_type:
            return "UnknownError", message_line
        return exc_type, exc_msg.strip()
    return "AssertionError", message_line


def _normalize_outcome(report) -> str:
    """Map pytest report outcome to stable artifact outcome vocabulary."""
    wasxfail = hasattr(report, "wasxfail")
    if wasxfail:
        if report.outcome == "passed":
            return "xpass"
        return "xfail"
    if report.outcome == "passed":
        return "pass"
    if report.outcome == "failed":
        return "fail"
    if report.outcome == "skipped":
        return "skip"
    return "error"


def _select_final_report(phase_reports: dict):
    """Choose one report that represents the executed test row."""
    setup_report = phase_reports.get("setup")
    call_report = phase_reports.get("call")
    teardown_report = phase_reports.get("teardown")

    if setup_report and setup_report.failed:
        return setup_report, "error"
    if call_report:
        return call_report, _normalize_outcome(call_report)
    if teardown_report and teardown_report.failed:
        return teardown_report, "error"
    if setup_report and setup_report.skipped:
        return setup_report, _normalize_outcome(setup_report)
    if teardown_report and teardown_report.skipped:
        return teardown_report, _normalize_outcome(teardown_report)
    return None, "notrun"


def _reserve_artifact_paths(result_dir: Path, date_str: str, label: str) -> tuple[Path, Path, Path]:
    """Reserve a collision-safe artifact name set with _1/_2 suffixing."""
    prefix = f"{date_str}_pytest_{label}"
    csv_path = result_dir / f"{prefix}_results.csv"
    md_path = result_dir / f"{prefix}_summary.md"
    log_path = result_dir / f"{prefix}_failures.log"

    if not csv_path.exists() and not md_path.exists() and not log_path.exists():
        return csv_path, md_path, log_path

    idx = 1
    while True:
        csv_candidate = result_dir / f"{prefix}_results_{idx}.csv"
        md_candidate = result_dir / f"{prefix}_summary_{idx}.md"
        log_candidate = result_dir / f"{prefix}_failures_{idx}.log"
        if not csv_candidate.exists() and not md_candidate.exists() and not log_candidate.exists():
            return csv_candidate, md_candidate, log_candidate
        idx += 1


def pytest_collection_modifyitems(items):
    """Cache marker names per nodeid once during collection."""
    for item in items:
        marker_names = sorted({marker.name for marker in item.iter_markers()})
        _TEST_MARKERS_BY_NODEID[item.nodeid] = "|".join(marker_names)


def pytest_runtest_logreport(report):
    """Capture phase reports in memory for canonical artifact emission."""
    nodeid = report.nodeid
    entry = _TEST_REPORTS_BY_NODEID.setdefault(nodeid, {})
    entry[report.when] = report


def pytest_sessionfinish(session, exitstatus):
    """Write canonical CSV + derived summary/failure artifacts once per run."""
    if getattr(session.config.option, "collectonly", False):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_line("pytest artifact generation skipped (collect-only run)")
        return

    result_dir = Path("pytest_result")
    result_dir.mkdir(parents=True, exist_ok=True)

    label = _resolve_pytest_result_label(session.config.invocation_params.args, session.items)
    generated_utc = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    git_commit = _resolve_git_commit()

    csv_path, md_path, failure_log_path = _reserve_artifact_paths(result_dir, date_str, label)

    rows = []
    failure_entries = []

    for item in session.items:
        phase_reports = _TEST_REPORTS_BY_NODEID.get(item.nodeid)
        if not phase_reports:
            continue

        report, outcome = _select_final_report(phase_reports)
        if report is None:
            continue

        test_file, test_class, test_name = _parse_nodeid(item.nodeid)
        duration_ms = int(round(float(getattr(report, "duration", 0.0)) * 1000))
        exc_type, exc_msg = _extract_exception(report)
        longreprtext = getattr(report, "longreprtext", "") or ""
        first_frame = _first_project_frame(longreprtext)
        markers = _TEST_MARKERS_BY_NODEID.get(item.nodeid, "")

        row = {
            "generated_utc": generated_utc,
            "git_commit": git_commit,
            "pytest_label": label,
            "nodeid": item.nodeid,
            "test_file": test_file,
            "test_class": test_class,
            "test_name": test_name,
            "outcome": outcome,
            "duration_ms": str(duration_ms),
            "exception_type": exc_type,
            "exception_message": exc_msg,
            "first_project_frame": first_frame,
            "markers": markers,
        }
        rows.append(row)

        if outcome in {"fail", "error"} and longreprtext:
            failure_entries.append(
                {
                    "nodeid": item.nodeid,
                    "exception_type": exc_type or "UnknownError",
                    "traceback": longreprtext,
                }
            )

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if failure_entries:
        sections = []
        for entry in failure_entries:
            sections.extend(
                [
                    "=" * 39,
                    entry["nodeid"],
                    entry["exception_type"],
                    entry["traceback"].rstrip(),
                    "=" * 39,
                    "",
                ]
            )
        failure_log_path.write_text("\n".join(sections), encoding="utf-8")
    else:
        failure_log_path.write_text("No failed tests in this run.\n", encoding="utf-8")

    parsed_rows = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed_rows.append(row)

    count_by_outcome = {}
    durations_ms = []
    for row in parsed_rows:
        outcome = row.get("outcome", "unknown")
        count_by_outcome[outcome] = count_by_outcome.get(outcome, 0) + 1
        try:
            durations_ms.append(float(row.get("duration_ms", 0) or 0))
        except ValueError:
            durations_ms.append(0.0)

    total_tests = len(parsed_rows)
    passed_count = count_by_outcome.get("pass", 0)
    success_pct = (passed_count / total_tests * 100.0) if total_tests else 0.0
    total_runtime_ms = sum(durations_ms)
    avg_runtime_ms = statistics.mean(durations_ms) if durations_ms else 0.0
    median_runtime_ms = statistics.median(durations_ms) if durations_ms else 0.0

    failure_groups = {}
    for row in parsed_rows:
        if row.get("outcome") not in {"fail", "error", "xpass"}:
            continue
        key = (
            row.get("exception_type") or "UnknownError",
            row.get("first_project_frame") or "(no project frame)",
        )
        bucket = failure_groups.setdefault(
            key,
            {
                "count": 0,
                "message": row.get("exception_message") or "",
                "tests": [],
            },
        )
        bucket["count"] += 1
        bucket["tests"].append(row.get("nodeid") or "")

    sorted_failure_groups = sorted(
        failure_groups.items(),
        key=lambda item: item[1]["count"],
        reverse=True,
    )

    slowest_rows = sorted(
        parsed_rows,
        key=lambda row: float(row.get("duration_ms", 0) or 0),
        reverse=True,
    )[:10]

    summary_lines = [
        f"# Pytest Run Summary ({label})",
        "",
        "## Run Metadata",
        "",
        f"- generated_utc: {generated_utc}",
        f"- git_commit: {git_commit}",
        f"- pytest_label: {label}",
        f"- exitstatus: {exitstatus}",
        f"- tests_recorded: {total_tests}",
        f"- csv: {csv_path.name}",
        f"- failures_log: {failure_log_path.name}",
        "",
        "## Outcome Counts",
        "",
    ]

    for outcome_name in sorted(count_by_outcome.keys()):
        summary_lines.append(f"- {outcome_name}: {count_by_outcome[outcome_name]}")

    summary_lines.extend(
        [
            "",
            "## Runtime Stats",
            "",
            f"- success_percentage: {success_pct:.2f}%",
            f"- total_runtime_ms: {total_runtime_ms:.0f}",
            f"- average_duration_ms: {avg_runtime_ms:.2f}",
            f"- median_duration_ms: {median_runtime_ms:.2f}",
            "",
            "## Slowest 10 Tests",
            "",
            "| duration_ms | outcome | nodeid |",
            "|---:|---|---|",
        ]
    )

    for row in slowest_rows:
        summary_lines.append(
            f"| {row.get('duration_ms', '0')} | {row.get('outcome', '')} | {row.get('nodeid', '')} |"
        )

    summary_lines.extend(
        [
            "",
            "## Failure Groups",
            "",
        ]
    )

    if not sorted_failure_groups:
        summary_lines.append("No failed/error/xpass outcomes in this run.")
    else:
        for (exception_type, first_frame), bucket in sorted_failure_groups:
            summary_lines.extend(
                [
                    f"### {exception_type}",
                    "",
                    f"- failures: {bucket['count']}",
                    f"- first_project_frame: {first_frame}",
                    f"- representative_message: {bucket['message']}",
                    "- affected_tests:",
                ]
            )
            for test_nodeid in bucket["tests"][:20]:
                summary_lines.append(f"  - {test_nodeid}")
            if bucket["count"] > 20:
                summary_lines.append(f"  - ... and {bucket['count'] - 20} more")
            summary_lines.append("")

    md_path.write_text("\n".join(summary_lines), encoding="utf-8")

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter:
        reporter.write_line(f"pytest CSV artifact: {csv_path}")
        reporter.write_line(f"pytest summary artifact: {md_path}")
        reporter.write_line(f"pytest failure log artifact: {failure_log_path}")

def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()





def _rebuild_database_state():
    """Rebuild the Postgres test database schema from scratch."""
    import app.models  # Ensure model metadata is registered before create_all().

    db.session.remove()
    
    # Determine dialect from config URL to avoid stale engine property access
    test_db_url = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    is_postgres = "postgresql" in test_db_url

    if is_postgres:
        # Dispose first to release any stale pooled connections.
        db.engine.dispose()

        with db.engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.execute(text("SET search_path TO public"))
            conn.commit()

        # Ensure subsequent tests get fresh pooled connections.
        db.engine.dispose()

        # Apply the migration chain so the test schema follows the same path
        # as the dev database instead of being created directly from ORM metadata.
        upgrade()
    else:
        # SQLite or other
        db.drop_all()
        db.create_all()

    db.session.remove()

@pytest.fixture
def app(request):
    """Provide the Flask app instance for tests."""

    test_db_url = os.environ.get("TEST_DATABASE_URL")

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=test_db_url,
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
        RATELIMIT_ENABLED=False,
    )

    with flask_app.app_context():
        lock_conn = None
        lock_key_primary = 0x435448  # "CTH"
        lock_key_secondary = 0x54455354  # "TEST"
        is_postgres = "postgresql" in (test_db_url or "")

        try:
            if is_postgres:
                # Serialize full test lifecycle (rebuild + execution) across
                # concurrent pytest processes sharing one test database.
                lock_conn = db.engine.connect()
                lock_conn.execute(
                    text("SELECT pg_advisory_lock(:k1, :k2)"),
                    {"k1": lock_key_primary, "k2": lock_key_secondary},
                )
                lock_conn.commit()

            _rebuild_database_state()
            yield flask_app
        finally:
            db.session.remove()
            if lock_conn is not None:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:k1, :k2)"),
                    {"k1": lock_key_primary, "k2": lock_key_secondary},
                )
                lock_conn.commit()
                lock_conn.close()


@pytest.fixture
def client(app):
    """
    Test client that creates a fresh database for each test.
    Ensures isolation between tests.
    """
    ctx = app.app_context()
    ctx.push()
    
    limiter.reset()
    
    client = flask_app.test_client()
    yield client
    
    limiter.reset()
    db.session.remove()
    ctx.pop()


@pytest.fixture
def client_with_fk(client):
    """
    Enable foreign key enforcement for tests that rely on CASCADE behavior.
    SQLite requires PRAGMA foreign_keys=ON per connection; PostgreSQL enforces by default.
    """
    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        event.listen(db.engine, "connect", _set_sqlite_pragma)

        # Also enable on the current connection
        db.session.execute(text("PRAGMA foreign_keys=ON"))

    yield client
    if dialect == 'sqlite':
        event.remove(db.engine, "connect", _set_sqlite_pragma)


@pytest.fixture
def test_student(app):
    from tests.helpers.classroom_initializer import initialize

    classroom = initialize("chemistry_p1", app)
    return classroom.students[0]


@pytest.fixture
def classroom_context(app):
    """Create a fully-wired v2 classroom context.

    Returns a factory function. The context uses User/Seat/IdentityProfile
    as the primary identity chain. No legacy bridge rows are created.

    Usage in tests:
        def test_something(classroom_context):
            ctx = classroom_context()
            student = ctx.add_student("Alice", "A")
            ctx.commit()

            # Access v2 objects:
            ctx.teacher_user      # User instance
            ctx.teacher_seat      # Seat instance
            ctx.teacher_profile   # IdentityProfile instance
            student.user          # User instance
            student.seat          # Seat instance
            student.profile       # IdentityProfile instance
    """
    from tests.helpers.classroom_initializer import initialize

    def _factory(**kwargs):
        classroom_key = kwargs.pop("classroom_key", "chemistry_p1")
        classroom = initialize(classroom_key, app)
        if kwargs:
            raise TypeError(f"Unsupported classroom_context kwargs: {sorted(kwargs)}")
        return classroom

    return _factory


@pytest.fixture
def classroom_with_students(app):
    """Convenience: create a class with N students, committed.

    Usage:
        def test_something(classroom_with_students):
            ctx = classroom_with_students(3)
            ctx.students[0].login(client)
    """
    from tests.helpers.classroom_initializer import initialize

    def _factory(n=1, **kwargs):
        classroom_key = kwargs.pop("classroom_key", "chemistry_p1")
        classroom = initialize(classroom_key, app)
        if kwargs:
            raise TypeError(f"Unsupported classroom_with_students kwargs: {sorted(kwargs)}")
        classroom.students = classroom.students[:n]
        return classroom

    return _factory


@pytest.fixture
def create_class_scope(app):
    """Create a canonical class scope with User, Seat, ClassEconomy, IdentityProfile.

    Returns a factory function that creates a class and automatically a student seat.
    Returns a dict with 'seat_id', 'class_id', 'class_row', 'student' keys.

    Usage:
        def test_something(create_class_scope):
            context = create_class_scope()
            seat_id = context['seat_id']
            class_id = context['class_id']
    """
    from tests.helpers.classroom_initializer import initialize

    def _factory(**kwargs):
        classroom_key = kwargs.pop("classroom_key", "chemistry_p1")
        classroom = initialize(classroom_key, app)
        if kwargs:
            raise TypeError(f"Unsupported create_class_scope kwargs: {sorted(kwargs)}")
        return {
            'seat_id': classroom.students[0].seat_id,
            'class_id': classroom.class_id,
            'class_row': classroom.economy,
            'student_seat': classroom.students[0].seat,
        }

    return _factory
