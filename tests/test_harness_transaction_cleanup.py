"""Regression: failed fixture/setup must leave the DB connection clean (C1).

A setup exception raised mid-flush (e.g. an IntegrityError from a duplicate
insert) previously left the session's transaction open and the DBAPI connection
"idle in transaction", holding locks that blocked the next test's
DROP SCHEMA CASCADE indefinitely.

These tests pin the two guarantees behind the C1 fix:
  1. Fixtures/tests must not INSERT a second RentSettings — the canonical row
     seeded by provision_classroom is the single one-per-class policy.
  2. After a setup exception + rollback, the session/connection is clean and
     immediately reusable (no lingering aborted transaction).
"""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import RentSettings
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

        # Simulate a faulty fixture that INSERTs a duplicate rent policy,
        # violating the one-rent-policy-per-class unique constraint.
        with pytest.raises(IntegrityError):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="regr-dup-rent"):
                db.session.add(
                    RentSettings(class_id=class_id, rent_amount=Decimal("99.00"))
                )
                db.session.flush()

        # Defensive rollback (mirrors the conftest app/client teardown fix).
        db.session.rollback()

        # Connection must be reusable: a fresh query succeeds and executes,
        # proving the backend is no longer in an aborted-transaction state.
        assert db.session.execute(text("SELECT 1")).scalar() == 1

        # No duplicate persisted; the invariant still holds.
        assert RentSettings.query.filter_by(class_id=class_id).count() == 1

        # A fresh canonical write still works after the recovery.
        customize_rent_settings(class_id, rent_amount=Decimal("123.00"))
        assert (
            RentSettings.query.filter_by(class_id=class_id).first().rent_amount
            == Decimal("123.00")
        )
