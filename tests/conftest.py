import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Override env vars for testing
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("PEPPER", "legacy-pepper")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# Ensure ENCRYPTION_KEY and PEPPER_KEY are set for tests, if not already in .env
# Use valid Fernet keys (32 url-safe base64-encoded bytes)
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("PEPPER_KEY", "tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=")


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import app as flask_app, db, Student


@pytest.fixture
def app():
    """Provide the Flask app instance for tests."""
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    yield flask_app


@pytest.fixture
def client(app):
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    client = flask_app.test_client()
    yield client
    db.drop_all()
    ctx.pop()


# SQLite pragma event listener for foreign key constraints
# Registered at module level and persists across all tests
from sqlalchemy import event
from sqlalchemy.engine import Engine

def _enable_sqlite_foreign_keys(dbapi_conn, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    if 'sqlite' in str(type(dbapi_conn)):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Register event listener once at module load time
# Only applies to SQLite connections, so won't affect other databases
event.listen(Engine, "connect", _enable_sqlite_foreign_keys)


@pytest.fixture
def client_with_fk():
    """
    Test client with foreign key constraints enabled.
    Use this fixture for tests that need to verify CASCADE behavior.
    """
    
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    ctx = flask_app.app_context()
    ctx.push()
    
    db.create_all()
    
    # Foreign key constraints are enabled by the event listener.
    
    client = flask_app.test_client()
    yield client
    
    db.drop_all()
    ctx.pop()


@pytest.fixture
def test_student():
    from hash_utils import hash_username, get_random_salt
    salt = get_random_salt()
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("test", salt),
        pin_hash="fake-hash",
    )
    db.session.add(stu)
    db.session.commit()
    return stu

