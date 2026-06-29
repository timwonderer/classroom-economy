import os
import sys
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
from app import app as flask_app, db, Student
from flask import current_app
from app.extensions import limiter
from app.models import Transaction

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

            # Create all tables/types through the same connection.
            db.Model.metadata.create_all(bind=conn)
            conn.commit()

        # Ensure subsequent tests get fresh pooled connections.
        db.engine.dispose()
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


@pytest.fixture(autouse=True)
def _auto_bypass_feat(request, app):
    """
    Temporarily bypass FEAT enforcement for all tests, 
    so legacy code and fixtures can create Transactions/StudentItems.
    Tests that specifically test FEAT should be named with test_feat_enforcement
    or use a marker.
    """
    # Skip bypass for tests that explicitly test enforcement logic
    if "enforce_feat" in request.keywords or \
       "test_feat_enforcement" in request.node.name or \
       "test_feat_enforcement" in str(request.fspath):
        yield
        return
        
    from app.feats.base import FEATBypass
    with FEATBypass():
        yield


@pytest.fixture
def test_student():
    from app.hash_utils import hash_username, get_random_salt
    from app.feats.base import FEATBypass
    from app.models import User, UserRole, Seat
    from app.utils.auth_username import build_hashed_username_fields
    salt = get_random_salt()
    _, username_hash, username_lookup_hash = build_hashed_username_fields("test_student")
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    profile = IdentityProfile(
        profile_type='student',
        first_name='Test',
        last_name='Student',
    )
    db.session.add(profile)
    db.session.flush()
    stu = Student(
        identity_profile=profile,
        block="A",
        salt=salt,
        username_hash=hash_username("test", salt),
        pin_hash="fake-hash",
    )
    db.session.add(stu)
    seat = Seat(
        user_id=user.id,
        class_id=stu.class_id,
        join_code=stu.join_code or "TESTSTUDENT",
        role="student",
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id
    with FEATBypass():
        db.session.commit()
    return stu


@pytest.fixture
def classroom_context():
    """Create a fully-wired v2 classroom context.

    Returns a factory function. The context uses User/Seat/IdentityProfile
    as the primary identity chain. Legacy Admin/Student rows are created
    as hidden infrastructure for FK/auth compatibility only.

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
    from tests.helpers.context_factory import canonicalContextFactory

    def _factory(**kwargs):
        return canonicalContextFactory(db, **kwargs).build()

    return _factory


@pytest.fixture
def classroom_with_students():
    """Convenience: create a class with N students, committed.

    Usage:
        def test_something(classroom_with_students):
            ctx = classroom_with_students(3)
            ctx.students[0].login(client)
    """
    from tests.helpers.context_factory import canonicalContextFactory
    from app.feats.base import FEATBypass

    def _factory(n=1, **kwargs):
        ctx = canonicalContextFactory(db, **kwargs).with_students(n).build()
        with FEATBypass():
            db.session.commit()
        return ctx

    return _factory
