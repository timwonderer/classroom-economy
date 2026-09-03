"""FEAT-CLASS-003 tier-group rules (v1 parity): max 3 active tiers per group,
unique rank per group, grouped ranks are basic(1)/mid(2)/premium(3).

Enforced by the FEAT-CLASS-003 command guard (with a partial unique index backstop).
Definitions are immutable, so editing a tier = mint a new IN_USE row + retire the
old; the guard counts only IN_USE rows, so a retired rank can be re-added.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import InsurancePolicy
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
)
from app.feats.class_configuration.feat_class_003_insurance_policy_management import (
    InsuranceContractViolation,
)
from app.services import insurance_definition_service as defs
from tests.test_insurance_purchase_feat import _teacher_ctx, _submission
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import enable_class_feature
from uuid import uuid4


def _make_tier(classroom, group, level, **overrides):
    return configure_insurance_definition(
        class_id=classroom.class_id,
        submission=_submission(tier_group=group, tier_level=level, **overrides),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:tier:{uuid4().hex}",
    )


def _setup(app):
    classroom = initialize("chemistry_p1", app)
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    return classroom


def test_three_tiers_one_group_ok(app):
    """basic/mid/premium in one group all succeed."""
    classroom = _setup(app)
    with app.app_context():
        for level in (1, 2, 3):
            _make_tier(classroom, "Paycheck Protection", level)
        db.session.commit()
        active = InsurancePolicy.query.filter_by(
            class_id=classroom.class_id, tier_group="Paycheck Protection",
            availability_state=defs.IN_USE,
        ).count()
        assert active == 3


def test_duplicate_rank_in_group_rejected(app):
    """A second IN_USE policy at the same rank in a group is rejected (max-3 mechanism)."""
    classroom = _setup(app)
    with app.app_context():
        _make_tier(classroom, "Paycheck Protection", 1)
        db.session.commit()
        with pytest.raises(InsuranceContractViolation, match="already has an active tier at level 1"):
            _make_tier(classroom, "Paycheck Protection", 1)


def test_grouped_tier_requires_valid_rank(app):
    """A grouped policy must carry rank 1/2/3."""
    classroom = _setup(app)
    with app.app_context():
        with pytest.raises(InsuranceContractViolation, match="requires tier_level of 1"):
            _make_tier(classroom, "Paycheck Protection", 5)


def test_ungrouped_policy_has_no_tier_constraint(app):
    """A policy with no tier_group is unconstrained (SINGLE offering)."""
    classroom = _setup(app)
    with app.app_context():
        # No tier_group / tier_level at all.
        configure_insurance_definition(
            class_id=classroom.class_id,
            submission=_submission(),
            canonical_context=_teacher_ctx(classroom),
            correlation_id=f"corr_{uuid4().hex}",
            idempotency_key=f"FEAT-CLASS-003:single:{uuid4().hex}",
        )
        configure_insurance_definition(
            class_id=classroom.class_id,
            submission=_submission(),
            canonical_context=_teacher_ctx(classroom),
            correlation_id=f"corr_{uuid4().hex}",
            idempotency_key=f"FEAT-CLASS-003:single:{uuid4().hex}",
        )
        db.session.commit()  # two ungrouped policies coexist fine


def test_retired_rank_can_be_readded(app):
    """After retiring a tier, the same rank may be re-added (guard counts IN_USE only)."""
    classroom = _setup(app)
    with app.app_context():
        first = _make_tier(classroom, "Paycheck Protection", 2)
        db.session.commit()
        set_insurance_definition_availability(
            class_id=classroom.class_id, policy_uuid=first.policy_uuid,
            availability_state=defs.RETIRED, canonical_context=_teacher_ctx(classroom),
            correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"retire:{uuid4().hex}",
        )
        db.session.commit()
        # Re-add rank 2 — the retired one no longer occupies the slot.
        second = _make_tier(classroom, "Paycheck Protection", 2)
        db.session.commit()
        assert second.policy_uuid != first.policy_uuid


def test_same_rank_across_different_groups_ok(app):
    """Rank uniqueness is per group, not per class."""
    classroom = _setup(app)
    with app.app_context():
        _make_tier(classroom, "Paycheck Protection", 1)
        _make_tier(classroom, "Device Insurance", 1)
        db.session.commit()  # both basic tiers, different groups — fine
