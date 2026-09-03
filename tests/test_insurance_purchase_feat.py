"""FEAT-OBL-004 — Insurance Policy Purchase / Enrollment (arc slice B).

The centerpiece is transaction-boundary behavior: the FEAT coordinates four
domains (Policies read, Obligations, Ledger, Store) under one atomic FEAT
transaction, so a failure anywhere before commit must leave zero state — and a
success must leave exactly one of each fact.

The old Store-based insurance purchase path is intentionally left intact and
unwired here (that removal is slice C); these tests prove the new path in
isolation.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.models import (
    EntitlementEvent, ObligationAssessment, BillCycle, Transaction, Seat,
)
from app.services.context_resolver import CanonicalContext
from app.feats.base import FEATContext
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
)
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.services import insurance_definition_service as insurance_defs
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import enable_class_feature


def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher",
    )


def _student_ctx(classroom, idx=0):
    s = classroom.students[idx]
    return CanonicalContext(
        user_id=s.user.id, class_id=classroom.class_id,
        seat_id=s.seat.id, actor_role="student",
    )


def _submission(**overrides):
    s = dict(
        insurance_type="TRANSACTION", premium="10.00", charge_frequency="WEEKLY",
        reimbursement_percentage="80", payout_multiple="3",
        claims_per_week_equivalent="1", claim_window_days="7",
        title="Basic Transaction Cover",
    )
    s.update(overrides)
    return s


def _make_policy(classroom, **overrides):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=_submission(**overrides),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
    )
    return row.policy_uuid


def _fund(seat, amount="100.00"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat.id}:{uuid4().hex}"):
        create_idempotent_transaction(
            idempotency_key=f"fund:{seat.id}:{uuid4().hex}",
            seat_id=seat.id, class_id=seat.class_id,
            target_seat_id=seat.id, actor_seat_id=seat.id, mechanism="self",
            user_id=seat.user_id, amount=Decimal(amount),
            account_type="checking", type="payroll", description="test funding",
        )
    db.session.commit()


def _setup(app, *, fund="100.00", availability=insurance_defs.IN_USE):
    classroom = initialize("chemistry_p1", app)
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    policy_uuid = _make_policy(classroom)
    if availability != insurance_defs.IN_USE:
        set_insurance_definition_availability(
            class_id=classroom.class_id, policy_uuid=policy_uuid,
            availability_state=availability,
            canonical_context=_teacher_ctx(classroom),
            correlation_id=f"corr_{uuid4().hex}",
            idempotency_key=f"avail:{uuid4().hex}",
        )
        db.session.commit()
    if fund is not None:
        _fund(classroom.students[0].seat, fund)
    return classroom, policy_uuid


def _counts(classroom, policy_uuid):
    seat_id = classroom.students[0].seat.id
    cid = classroom.class_id
    grants = EntitlementEvent.query.filter_by(
        class_id=cid, target_seat_id=seat_id,
        entitlement_type="INSURANCE", event_type="GRANTED").count()
    assessments = ObligationAssessment.query.filter_by(
        class_id=cid, seat_id=seat_id,
        obligation_type="INSURANCE_PREMIUM", event_type="ASSESSMENT").count()
    payments = ObligationAssessment.query.filter_by(
        class_id=cid, seat_id=seat_id, event_type="PAYMENT").count()
    cycles = BillCycle.query.filter(
        BillCycle.class_id == cid, BillCycle.policy_uuid == policy_uuid).count()
    premium_txns = Transaction.query.filter_by(
        class_id=cid, seat_id=seat_id, type="insurance_premium").count()
    return dict(grants=grants, assessments=assessments, payments=payments,
               cycles=cycles, premium_txns=premium_txns)


# --------------------------------------------------------------------------- #
# Success                                                                      #
# --------------------------------------------------------------------------- #


def test_successful_purchase_creates_exactly_one_of_each(app):
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        result = execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="buy:1",
        )
        db.session.commit()
        assert result.success
        assert result.entitlement_id
        assert result.premium_charged == Decimal("10.00")
        assert _counts(classroom, policy_uuid) == dict(
            grants=1, assessments=1, payments=1, cycles=1, premium_txns=1)


def test_orchestrating_feat_enters_exactly_one_feat_context(app, monkeypatch):
    """FEAT-OBL-004 orchestrates establish→assess→ledger→satisfy→grant by
    composing DOMAIN commands inside a SINGLE FEAT context. The whole request
    must open exactly one FEATContext — proving the composition uses plain
    domain commands, not nested FEAT executors (FEAT-CORE-000 §V.1)."""
    classroom, policy_uuid = _setup(app)

    entries = []
    real_enter = FEATContext.__enter__

    def counting_enter(self):
        entries.append(self.feat_name)
        return real_enter(self)

    monkeypatch.setattr(FEATContext, "__enter__", counting_enter)

    with app.app_context():
        result = execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="buy:solo",
        )
        db.session.commit()
        assert result.success
    # Exactly one FEAT context for the entire orchestration.
    assert entries == ["FEAT-OBL-004"], entries


def test_same_idempotency_key_retry_no_duplicates(app):
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        ctx = _student_ctx(classroom)
        r1 = execute_purchase_insurance(
            canonical_context=ctx, policy_uuid=policy_uuid, idempotency_key="buy:1")
        db.session.commit()
        r2 = execute_purchase_insurance(
            canonical_context=ctx, policy_uuid=policy_uuid, idempotency_key="buy:1")
        db.session.commit()
        assert r1.success and r2.success
        assert r2.already_enrolled is True
        assert r2.entitlement_id == r1.entitlement_id
        assert _counts(classroom, policy_uuid) == dict(
            grants=1, assessments=1, payments=1, cycles=1, premium_txns=1)


# --------------------------------------------------------------------------- #
# Rejections — nothing written                                                 #
# --------------------------------------------------------------------------- #


def test_insufficient_funds_writes_nothing(app):
    classroom, policy_uuid = _setup(app, fund="5.00")  # premium is 10.00
    with app.app_context():
        result = execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="buy:1")
        db.session.commit()
        assert not result.success
        assert result.error_code == "INSUFFICIENT_FUNDS"
        assert _counts(classroom, policy_uuid) == dict(
            grants=0, assessments=0, payments=0, cycles=0, premium_txns=0)


def test_unavailable_policy_writes_nothing(app):
    classroom, policy_uuid = _setup(app, availability=insurance_defs.HIDDEN)
    with app.app_context():
        result = execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="buy:1")
        db.session.commit()
        assert not result.success
        assert result.error_code == "INSURANCE_NOT_AVAILABLE_FOR_NEW_COVERAGE"
        assert _counts(classroom, policy_uuid) == dict(
            grants=0, assessments=0, payments=0, cycles=0, premium_txns=0)


def test_policy_not_found_writes_nothing(app):
    classroom, _ = _setup(app)
    with app.app_context():
        result = execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid="does-not-exist", idempotency_key="buy:1")
        db.session.commit()
        assert not result.success
        assert result.error_code == "POLICY_NOT_FOUND"


def test_different_key_after_success_is_policy_already_held(app):
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        ctx = _student_ctx(classroom)
        execute_purchase_insurance(
            canonical_context=ctx, policy_uuid=policy_uuid, idempotency_key="buy:1")
        db.session.commit()
        # A DIFFERENT command finds active coverage → rejected, nothing added.
        result = execute_purchase_insurance(
            canonical_context=ctx, policy_uuid=policy_uuid, idempotency_key="buy:2")
        db.session.commit()
        assert not result.success
        assert result.error_code == "POLICY_ALREADY_HELD"
        assert _counts(classroom, policy_uuid) == dict(
            grants=1, assessments=1, payments=1, cycles=1, premium_txns=1)


# --------------------------------------------------------------------------- #
# Atomicity — a late failure rolls back everything, including the Ledger post   #
# --------------------------------------------------------------------------- #


def test_failure_during_grant_rolls_back_everything(app, monkeypatch):
    """If the entitlement grant fails after the premium is charged, the whole
    transaction rolls back — no cycle, no assessment, no payment, no Ledger row."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        import app.feats.purchase_insurance_feat as feat

        def _boom(*args, **kwargs):
            raise RuntimeError("injected grant failure")

        monkeypatch.setattr(feat.entitlement_service, "grant_insurance_entitlement", _boom)

        with pytest.raises(RuntimeError, match="injected grant failure"):
            execute_purchase_insurance(
                canonical_context=_student_ctx(classroom),
                policy_uuid=policy_uuid, idempotency_key="buy:1")

        # The FEAT owns the transaction; the failure rolled it all back.
        assert _counts(classroom, policy_uuid) == dict(
            grants=0, assessments=0, payments=0, cycles=0, premium_txns=0)
