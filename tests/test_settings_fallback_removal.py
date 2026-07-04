"""Tests verifying settings helpers refuse to fall back to missing scoped rows."""
from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest

from app.extensions import db
from app.models import Seat, IdentityProfile, User, UserRole, Admin, BankingSettings, ClassFeature, ClassEconomy, ClassMembership, FeatureSettings, RentSettings, StudentTeacher
from app.routes.student import (
    get_banking_settings_for_context,
    get_feature_settings_for_student,
    get_rent_settings_for_context,
)
from tests.helpers.canonical_session import set_canonical_context


@pytest.fixture
def teacher_with_legacy_and_scoped_settings(client):
    """Create a teacher with no scoped settings rows for the active class."""
    teacher = make_admin("fallback_test_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    join_code = "FALL01"
    economy = ClassEconomy(join_code=join_code, user_id=teacher.id, created_by_admin_id=teacher.id)
    other_economy = ClassEconomy(join_code="FALL02", user_id=teacher.id, created_by_admin_id=teacher.id)
    db.session.add_all([economy, other_economy])
    db.session.flush()
    db.session.add(ClassMembership(join_code=join_code, admin_id=teacher.id, role="admin"))
    db.session.add(ClassMembership(join_code="FALL02", admin_id=teacher.id, role="admin"))
    student_user = User(username_hash="fallback_student_hash", username_lookup_hash="fallback_student_lookup", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    profile = IdentityProfile(profile_type='student', first_name="Fallback", last_initial="T")
    db.session.add(profile)
    db.session.flush()
    _tb_seat = Seat(user_id=student_user.id, join_code=join_code, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    profile.seat_id = _tb_seat.id
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))

    # Banking is now strictly class-scoped; keep only an unrelated-class row.
    db.session.add(BankingSettings(
        class_id=other_economy.class_id,
        overdraft_protection_enabled=True,
        savings_apy=5.0,
    ))
    # Rent is also strictly class-scoped now; keep only an unrelated-class row.
    db.session.add(RentSettings(
        class_id=other_economy.class_id,
        block=None,
        is_enabled=True,
        rent_amount=100.0,
    ))

    db.session.commit()
    return {
        "teacher": teacher,
        "student": _tb_seat,
        "join_code": join_code,
        "class_id": economy.class_id,
        "other_class_id": other_economy.class_id,
    }


# ---- Banking Settings ----

def test_banking_settings_ignores_other_class_row(client, teacher_with_legacy_and_scoped_settings):
    """When no class-scoped BankingSettings exist, helper returns None, not another class's row."""
    data = teacher_with_legacy_and_scoped_settings
    context = {"class_id": data["class_id"], "block": "A"}

    result = get_banking_settings_for_context(context)
    # Only another class's row exists; helper must not return it.
    assert result is None


def test_banking_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When a class-scoped BankingSettings exists, helper returns it."""
    data = teacher_with_legacy_and_scoped_settings
    db.session.add(BankingSettings(
        class_id=data["class_id"],
        block="A",
        overdraft_protection_enabled=False,
        savings_apy=0,
    ))
    db.session.commit()

    context = {"class_id": data["class_id"], "block": "A"}
    result = get_banking_settings_for_context(context)
    assert result is not None
    assert result.class_id == data["class_id"]
    assert result.overdraft_protection_enabled is False


def test_banking_settings_returns_none_for_missing_context(client):
    """Helper returns None when context is None or missing class_id."""
    assert get_banking_settings_for_context(None) is None
    assert get_banking_settings_for_context({}) is None
    assert get_banking_settings_for_context({"teacher_id": 999}) is None


# ---- Rent Settings ----

def test_rent_settings_ignores_legacy_global_row(client, teacher_with_legacy_and_scoped_settings):
    """When no class-scoped RentSettings exist, helper returns None — not the legacy row."""
    data = teacher_with_legacy_and_scoped_settings
    context = {"class_id": data["class_id"], "block": "A"}

    result = get_rent_settings_for_context(context)
    assert result is None


def test_rent_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When a class-scoped RentSettings exists, helper returns it."""
    data = teacher_with_legacy_and_scoped_settings
    db.session.add(RentSettings(
        class_id=data["class_id"],
        block="A",
        is_enabled=True,
        rent_amount=50.0,
    ))
    db.session.commit()

    context = {"class_id": data["class_id"], "block": "A"}
    result = get_rent_settings_for_context(context)
    assert result is not None
    assert result.class_id == data["class_id"]
    assert float(result.rent_amount) == 50.0


# ---- Feature Settings ----

def test_feature_settings_returns_defaults_without_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When no join-code-scoped FeatureSettings exist, helper returns defaults."""
    data = teacher_with_legacy_and_scoped_settings

    with client.application.test_request_context():
        from flask import session as flask_session
        set_canonical_context(
            flask_session,
            user_id=data["student"].user_id,
            class_id=data["class_id"],
            seat_id=data["student"].id,
            role="student",
            join_code=data["join_code"],
        )

        result = get_feature_settings_for_student()

    # Should return system defaults, NOT the legacy teacher-global row
    defaults = FeatureSettings.get_defaults()
    assert result == defaults


def test_feature_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When class feature rows are removed, helper reflects the disabled features."""
    data = teacher_with_legacy_and_scoped_settings
    for row in ClassFeature.query.filter(
        ClassFeature.class_id == data["class_id"],
        ClassFeature.feature_name.in_(["banking", "store", "insurance", "rent", "hall_pass", "payroll"]),
    ).all():
        db.session.delete(row)
    db.session.commit()

    with client.application.test_request_context():
        from flask import session as flask_session
        set_canonical_context(
            flask_session,
            user_id=data["student"].user_id,
            class_id=data["class_id"],
            seat_id=data["student"].id,
            role="student",
            join_code=data["join_code"],
        )

        result = get_feature_settings_for_student()

    # Should return the scoped row with all features disabled
    assert result["banking_enabled"] is False
    assert result["store_enabled"] is False
