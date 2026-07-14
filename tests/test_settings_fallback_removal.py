"""Tests verifying settings helpers refuse to fall back to missing scoped rows."""
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, IdentityProfile, User, UserRole, BankingSettings, ClassFeature, FeatureSettings, RentSettings
from app.routes.student import (
    get_banking_settings_for_context,
    get_feature_settings_for_student,
    get_rent_settings_for_context,
)
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.context_factory import ClassroomContextFactory


@pytest.fixture
def two_class_ctx(client):
    """Two canonical classes under one teacher; settings only on the second class."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_fallback_setup"):
        ctx1 = ClassroomContextFactory(
            db,
            join_code="FALL01",
            teacher_username="teacher_fall01",
        ).build()
        ctx2 = ClassroomContextFactory(
            db,
            join_code="FALL02",
            teacher_username="teacher_fall02",
        ).build()

        # Add a student to ctx1 so we have a seat to test with
        student = ctx1.add_student("Fallback", "T")

        # Banking row for ctx2 only (ctx1 has none)
        db.session.add(BankingSettings(
            class_id=ctx2.class_id,
            overdraft_protection_enabled=True,
            savings_apy=5.0,
        ))
        # Rent row for ctx2 only (ctx1 has none)
        db.session.add(RentSettings(
            class_id=ctx2.class_id,
            rent_amount=100.0,
        ))

        db.session.flush()
    return {
        "ctx": ctx1,
        "student_seat": student.seat,
        "class_id": ctx1.class_id,
        "other_class_id": ctx2.class_id,
    }


# ---- Banking Settings ----

def test_banking_settings_ignores_other_class_row(client, two_class_ctx):
    """When no class-scoped BankingSettings exist for ctx1, helper returns None."""
    data = two_class_ctx
    context = {"class_id": data["class_id"]}

    result = get_banking_settings_for_context(context)
    assert result is None


def test_banking_settings_returns_scoped_row(client, two_class_ctx):
    """When a class-scoped BankingSettings exists for ctx1, helper returns it."""
    data = two_class_ctx
    db.session.add(BankingSettings(
        class_id=data["class_id"],
        overdraft_protection_enabled=False,
        savings_apy=0,
    ))
    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_banking_row"):
        db.session.flush()

    context = {"class_id": data["class_id"]}
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

def test_rent_settings_returns_scoped_row(client, two_class_ctx):
    """When a class-scoped RentSettings exists for ctx1, helper returns it."""
    data = two_class_ctx
    db.session.add(RentSettings(
        class_id=data["class_id"],
        rent_amount=50.0,
    ))
    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_rent_row"):
        db.session.flush()

    context = {"class_id": data["class_id"]}
    result = get_rent_settings_for_context(context)
    assert result is not None
    assert result.class_id == data["class_id"]
    assert float(result.rent_amount) == 50.0


# ---- Feature Settings ----

def test_feature_settings_returns_defaults_without_scoped_row(client, two_class_ctx):
    """When no class_features rows exist, helper returns defaults."""
    data = two_class_ctx
    seat = data["student_seat"]

    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_feature_defaults"):
        with client.application.test_request_context():
            from flask import session as flask_session
            set_canonical_context(
                flask_session,
                user_id=seat.user_id,
                class_id=data["class_id"],
                seat_id=seat.id,
                role="student",
            )

            result = get_feature_settings_for_student()

    defaults = FeatureSettings.get_defaults()
    assert result == defaults


def test_feature_settings_returns_scoped_row(client, two_class_ctx):
    """When class feature rows are removed, helper reflects disabled features."""
    data = two_class_ctx
    seat = data["student_seat"]

    for row in ClassFeature.query.filter(
        ClassFeature.class_id == data["class_id"],
        ClassFeature.feature_name.in_(["banking", "store", "insurance", "rent", "hall_pass", "payroll"]),
    ).all():
        db.session.delete(row)
    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_feature_rows"):
        db.session.flush()

    with FEATContext("FEAT-IDEN-001", idempotency_key="settings_feature_rows_session"):
        with client.application.test_request_context():
            from flask import session as flask_session
            set_canonical_context(
                flask_session,
                user_id=seat.user_id,
                class_id=data["class_id"],
                seat_id=seat.id,
                role="student",
            )

            result = get_feature_settings_for_student()

    assert result["banking_enabled"] is False
    assert result["store_enabled"] is False
