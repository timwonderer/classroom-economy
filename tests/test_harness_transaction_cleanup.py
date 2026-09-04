"""Regression: failed fixture/setup must leave the DB connection clean (C1).

A setup exception raised mid-flush (e.g. an IntegrityError from a duplicate
insert) previously left the session's transaction open and the DBAPI connection
"idle in transaction", holding locks that blocked the next test's
DROP SCHEMA CASCADE indefinitely.

These tests pin the two guarantees behind the C1 fix:
  1. provision_classroom seeds exactly one rent policy for a fresh class.
  2. After a setup exception + rollback, the session/connection is clean and
     immediately reusable (no lingering aborted transaction).

The IntegrityError used to provoke (2) is raised by a duplicate ``policy_uuid``.
It was previously a duplicate ``class_id``, but ``rent_settings`` is now an
append-only policy repository (DOM-POL-001 §VI.1) in which many rows per class
are the normal case, so that insert no longer violates anything. ``policy_uuid``
is the identity of a policy version and remains UNIQUE, which is the constraint
that actually still means something here. The subject of the test is connection
recovery, not the choice of constraint.
"""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import RentSettings
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import customize_rent_settings


def test_provision_seeds_exactly_one_canonical_rent_settings(app):
    """provision_classroom seeds exactly one RentSettings per class."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        assert (
            RentSettings.query.filter_by(class_id=classroom.class_id).count() == 1
        ), "provision_classroom must seed exactly one canonical rent policy"


def test_failed_setup_leaves_connection_clean_and_reusable(app):
    """A duplicate-insert setup failure must not leave an aborted transaction.

    After the exception and a defensive rollback, the session must be usable for
    fresh reads and writes (mirrors the conftest teardown cleanup fix).
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        class_id = classroom.class_id

        # Sanity: the canonical row already exists.
        assert RentSettings.query.filter_by(class_id=class_id).count() == 1
        seeded_uuid = get_rent_settings(class_id).policy_uuid

        # Simulate a faulty fixture that INSERTs a policy reusing an existing
        # policy_uuid, violating the version-identity unique constraint.
        with pytest.raises(IntegrityError):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="regr-dup-rent"):
                db.session.add(
                    RentSettings(
                        class_id=class_id,
                        policy_uuid=seeded_uuid,
                        rent_amount=Decimal("99.00"),
                    )
                )
                db.session.flush()

        # Defensive rollback (mirrors the conftest app/client teardown fix).
        db.session.rollback()

        # Connection must be reusable: a fresh query succeeds and executes,
        # proving the backend is no longer in an aborted-transaction state.
        assert db.session.execute(text("SELECT 1")).scalar() == 1

        # Nothing persisted from the aborted insert.
        assert RentSettings.query.filter_by(class_id=class_id).count() == 1

        # A fresh canonical write still works after the recovery. It supersedes
        # rather than edits, so the class now holds two versions and the current
        # policy is resolved through the canonical reader.
        customize_rent_settings(class_id, rent_amount=Decimal("123.00"))
        assert RentSettings.query.filter_by(class_id=class_id).count() == 2
        assert get_rent_settings(class_id).rent_amount == Decimal("123.00")
