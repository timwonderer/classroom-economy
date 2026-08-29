"""Schema/CHECK-constraint tests for the InsurancePolicy definition-of-record.

Covers the STOR-owned, POL-managed ``insurance_policies`` table (Step 1 of the
insurance-architecture refactor). These tests exercise the DB integrity
backstops directly — they do NOT test POL/FEAT wiring (a later step).

Verified:
* a valid row of each insurance_type persists (typed columns round-trip);
* the per-type structural CHECK rejects cross-type / missing economic fields;
* hard-domain invariant CHECKs reject negative values, reimbursement > 100,
  and an unknown charge_frequency;
* recommendation ranges are NOT enforced (a high-but-legal value persists).

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import InsurancePolicy
from tests.helpers.classroom_initializer import initialize


def _base(class_id, insurance_type, **overrides):
    """Minimal-valid kwargs for a given insurance_type, before overrides."""
    common = dict(
        policy_uuid=str(uuid4()),
        class_id=class_id,
        insurance_type=insurance_type,
        premium=Decimal("10.00"),
        charge_frequency="WEEKLY",
    )
    if insurance_type == "TRANSACTION":
        common.update(
            reimbursement_percentage=Decimal("80.00"),
            payout_multiple=Decimal("3.00"),
            claims_per_week_equivalent=Decimal("1.000"),
            claim_window_days=7,
        )
    elif insurance_type == "PRODUCTIVITY":
        common.update(
            reimbursement_percentage=Decimal("50.00"),
            payout_multiple=Decimal("2.00"),
            claimable_dates_per_week_equivalent=Decimal("2.000"),
        )
    elif insurance_type == "NON_MONETARY":
        common.update(
            claims_per_week_equivalent=Decimal("1.000"),
            waiting_period_days=3,
        )
    common.update(overrides)
    return common


def _insert(class_id, insurance_type, **overrides):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
        row = InsurancePolicy(**_base(class_id, insurance_type, **overrides))
        db.session.add(row)
        db.session.flush()
    return row


@pytest.mark.parametrize("insurance_type", ["TRANSACTION", "PRODUCTIVITY", "NON_MONETARY"])
def test_valid_row_persists_per_type(app, insurance_type):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _insert(classroom.class_id, insurance_type)
        fetched = db.session.get(InsurancePolicy, row.policy_uuid)
        assert fetched is not None
        assert fetched.insurance_type == insurance_type
        assert fetched.availability_state == "IN_USE"
        assert fetched.created_at is not None


def test_type_subset_rejects_forbidden_field(app):
    """A NON_MONETARY row may not carry TRANSACTION-only fields."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(
                classroom.class_id,
                "NON_MONETARY",
                claim_window_days=7,  # forbidden for NON_MONETARY
            )
        db.session.rollback()


def test_type_subset_rejects_missing_required_field(app):
    """A TRANSACTION row missing a required economic field is rejected."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(
                classroom.class_id,
                "TRANSACTION",
                claim_window_days=None,  # required for TRANSACTION
            )
        db.session.rollback()


def test_negative_premium_rejected(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, "TRANSACTION", premium=Decimal("-1.00"))
        db.session.rollback()


def test_reimbursement_over_100_rejected(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(
                classroom.class_id,
                "TRANSACTION",
                reimbursement_percentage=Decimal("100.01"),
            )
        db.session.rollback()


def test_biweekly_frequency_rejected(app):
    """Only WEEKLY and MONTHLY are lawful coverage periods; BIWEEKLY is not."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, "TRANSACTION", charge_frequency="BIWEEKLY")
        db.session.rollback()


def test_monthly_frequency_allowed(app):
    """MONTHLY persists (normalized downstream by covered class-local days / 7)."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _insert(classroom.class_id, "TRANSACTION", charge_frequency="MONTHLY")
        assert db.session.get(InsurancePolicy, row.policy_uuid).charge_frequency == "MONTHLY"


def test_unknown_frequency_rejected(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, "TRANSACTION", charge_frequency="DAILY")
        db.session.rollback()


def test_unknown_insurance_type_rejected(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(IntegrityError):
            _insert(classroom.class_id, "LIFE")  # not in the taxonomy
        db.session.rollback()


def test_recommendation_range_not_enforced(app):
    """A high-but-legal payout_multiple persists (ranges are advisory, not CHECKs)."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _insert(
            classroom.class_id,
            "TRANSACTION",
            payout_multiple=Decimal("50.00"),  # far above any recommendation
        )
        assert db.session.get(InsurancePolicy, row.policy_uuid) is not None
