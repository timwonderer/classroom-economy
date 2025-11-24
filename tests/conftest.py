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

# Ensure ENCRYPTION_KEY and PEPPER_KEY are set for tests, if not already in .env
# Use valid Fernet keys (32 url-safe base64-encoded bytes)
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("PEPPER_KEY", "tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=")


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import app, db, Student


@pytest.fixture
def client():
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
    )
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    client = app.test_client()
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

