"""Tests verifying settings helpers refuse to fall back to missing scoped rows."""
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassFeature, FeatureSettings, RentSettings
from app.routes.student import (
    get_feature_settings_for_student,
    get_rent_settings_for_context,
)
from flask import session as flask_session
from tests.helpers.classroom_initializer import initialize, initialize_as_student


@pytest.fixture
def two_class_ctx(client):
    """Two canonical classes; settings only on the second class (ctx2).

    provision_classroom creates default EconomicEngine and RentSettings for both
    classes. This fixture removes ctx1's settings (so isolation tests can assert
    ctx1 returns None) and ensures ctx2 has the expected values (update-or-create).
    """
    ctx1 = initialize("chemistry_p1", client.application)
    ctx2 = initialize("ap_csp_p3", client.application)
    student = ctx1.students[0]

    with FEATContext("FEAT-IDEN-001", idempotency_key="test:two-class-ctx:setup"):
        for rs in RentSettings.query.filter_by(class_id=ctx1.class_id).all():
            db.session.delete(rs)
        db.session.flush()

        rs2 = RentSettings.query.filter_by(class_id=ctx2.class_id).first()
        if rs2:
            rs2.rent_amount = 100.0
        else:
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


# ---- Rent Settings ----

def test_DOM_IDEN_006__rent_settings_returns_scoped_row(client, two_class_ctx):
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

def test_DOM_IDEN_006__feature_settings_returns_defaults_without_scoped_row(client, two_class_ctx):
    """When no class_features rows exist, helper returns defaults."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    with client.session_transaction() as sess:
        snapshot = dict(sess)
    with client.application.test_request_context("/"):
        for key, value in snapshot.items():
            flask_session[key] = value
        result = get_feature_settings_for_student()

    defaults = FeatureSettings.get_defaults()
    assert result == defaults
