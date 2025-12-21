import pytest
from app import db
from app.models import Student
from hash_utils import hash_username_lookup, hash_username, get_random_salt
from werkzeug.security import generate_password_hash

def test_login_with_username_lookup_hash(client):
    """Test that login works when username_lookup_hash is present."""
    username = "testuser123"
    pin = "1234"
    salt = get_random_salt()

    student = Student(
        first_name="Test",
        last_initial="U",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        username_lookup_hash=hash_username_lookup(username),
        pin_hash=generate_password_hash(pin),
        dob_sum=2020
    )
    db.session.add(student)
    db.session.commit()

    response = client.post(
        "/student/login",
        data={
            "username": username,
            "pin": pin,
            # Turnstile bypass in test env if configured, or mock it
        },
        follow_redirects=True
    )

    # Assuming turnstile is mocked or bypassed in test config
    # We check if login was successful (usually redirects to dashboard)
    # Or check session
    with client.session_transaction() as sess:
        assert sess.get("student_id") == student.id

def test_login_populates_lookup_hash(client):
    """Test that login populates username_lookup_hash if missing."""
    username = "legacyuser"
    pin = "1234"
    salt = get_random_salt()

    student = Student(
        first_name="Legacy",
        last_initial="U",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        username_lookup_hash=None, # Missing
        pin_hash=generate_password_hash(pin),
        dob_sum=2020
    )
    db.session.add(student)
    db.session.commit()

    response = client.post(
        "/student/login",
        data={
            "username": username,
            "pin": pin,
        },
        follow_redirects=True
    )

    with client.session_transaction() as sess:
        assert sess.get("student_id") == student.id

    # Check if DB was updated
    updated_student = Student.query.get(student.id)
    assert updated_student.username_lookup_hash == hash_username_lookup(username)
