"""Canonical v2 fixtures for creating test users and roles."""

import uuid
from dataclasses import dataclass
from app.extensions import db
from app.models import User, UserRole
from app.hash_utils import hash_username_lookup


@dataclass
class AdminSeed:
    """Seeded admin/teacher user."""
    user: User


def seed_canonical_admin(username: str, password: str = "test123") -> AdminSeed:
    """
    Create a canonical teacher (admin) user.

    Args:
        username: Unique username for teacher
        password: Plaintext password (unused in test context, but kept for API compatibility)

    Returns:
        AdminSeed with User instance
    """
    # Check if user already exists
    username_hash = hash_username_lookup(username)
    existing = User.query.filter_by(username_lookup_hash=username_hash).first()
    if existing:
        return AdminSeed(user=existing)

    # Create new user
    user = User(
        username_hash=username_hash,
        username_lookup_hash=username_hash,
        user_role=UserRole.TEACHER,
    )
    db.session.add(user)
    db.session.flush()  # Flush to get user.id

    return AdminSeed(user=user)


def seed_canonical_student(username: str, password: str = "test123") -> User:
    """
    Create a canonical student user.

    Args:
        username: Unique username for student
        password: Plaintext password (unused in test context, but kept for API compatibility)

    Returns:
        User instance
    """
    # Check if user already exists
    username_hash = hash_username_lookup(username)
    existing = User.query.filter_by(username_lookup_hash=username_hash).first()
    if existing:
        return existing

    # Create new user
    user = User(
        username_hash=username_hash,
        username_lookup_hash=username_hash,
        user_role=UserRole.STUDENT,
    )
    db.session.add(user)
    db.session.flush()

    return user
