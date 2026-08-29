"""Banking settings POST persists interest AND overdraft state onto the Economic Engine.

Banking has no standalone settings model: savings interest and overdraft (internal
fine) both live on the canonical ``EconomicEngine`` and are mutated only by evolving
a new immutable version via FEAT-CLASS-005. This regression proves the wired
``/admin/banking/settings`` surface persists the full field set — interest rate,
calculation type, compound frequency, payout frequency, overdraft protection, and the
flat overdraft fee — not just the two interest fields the old surface handled.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.class_configuration_query_service import get_effective_economic_engine
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _post_banking_settings(client, **form):
    return client.post("/admin/banking/settings", data=form)


def test_DOM_CLASS_001__banking_settings_persist_interest_and_overdraft(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="banking")

    response = _post_banking_settings(
        client,
        interest_apy="4.00",
        interest_calculation_type="compound",
        compound_frequency="weekly",
        interest_payout_frequency="monthly",
        overdraft_protection_enabled="on",
        flat_overdraft_fee="5.00",
    )

    assert response.status_code == 302, response.data
    assert response.headers["Location"].endswith("/admin/banking")

    engine = get_effective_economic_engine(class_id, "banking")
    assert engine is not None
    # Interest: APY 4% is stored as the 0..1 fraction 0.04.
    assert Decimal(str(engine.interest_rate)) == Decimal("0.040000")
    assert engine.interest_calculation_type == "compound"
    assert engine.compound_frequency == "weekly"
    assert engine.interest_payout_frequency == "monthly"
    # Overdraft state persisted on the same engine version.
    assert engine.overdraft_protection_enabled is True
    assert Decimal(str(engine.flat_overdraft_fee)) == Decimal("5.00")
    # Flat and progressive are mutually exclusive; setting flat clears progressive.
    assert engine.progressive_overdraft_fee is None


def test_DOM_CLASS_001__simple_interest_forces_never_compounding(client):
    """Choosing simple interest must persist compound_frequency='never' (SPEC §5.6)."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="banking")

    response = _post_banking_settings(
        client,
        interest_apy="2.50",
        interest_calculation_type="simple",
        # A stray compound_frequency must be ignored when type is simple.
        compound_frequency="daily",
        interest_payout_frequency="weekly",
    )

    assert response.status_code == 302
    engine = get_effective_economic_engine(class_id, "banking")
    assert engine.interest_calculation_type == "simple"
    assert engine.compound_frequency == "never"


def test_DOM_CLASS_001__blank_overdraft_fee_disables_the_fee(client):
    """A blank fee persists NULL, disabling the overdraft fee (SPEC §4.6.1)."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="banking")

    # First set a fee...
    _post_banking_settings(
        client,
        interest_apy="0",
        interest_calculation_type="simple",
        interest_payout_frequency="monthly",
        flat_overdraft_fee="8.00",
    )
    engine = get_effective_economic_engine(class_id, "banking")
    assert Decimal(str(engine.flat_overdraft_fee)) == Decimal("8.00")

    # ...then clear it.
    _post_banking_settings(
        client,
        interest_apy="0",
        interest_calculation_type="simple",
        interest_payout_frequency="monthly",
        flat_overdraft_fee="",
    )
    engine = get_effective_economic_engine(class_id, "banking")
    assert engine.flat_overdraft_fee is None


def test_DOM_CLASS_001__banking_settings_surface_renders_overdraft_and_interest_controls(client):
    """The wired Settings tab exposes overdraft + interest-type controls, not just APY."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="banking")

    response = client.get("/admin/banking")
    assert response.status_code == 200
    body = response.data
    # Interest calculation + compounding controls.
    assert b'name="interest_calculation_type"' in body
    assert b'name="compound_frequency"' in body
    # Overdraft controls (protection toggle + flat fee).
    assert b'name="overdraft_protection_enabled"' in body
    assert b'name="flat_overdraft_fee"' in body


def test_DOM_CLASS_001__interest_apy_over_100_is_rejected(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="banking")

    response = _post_banking_settings(
        client,
        interest_apy="150",
        interest_calculation_type="simple",
        interest_payout_frequency="monthly",
    )
    # Rejected with a redirect back to the banking surface; nothing persisted.
    assert response.status_code == 302
    engine = get_effective_economic_engine(class_id, "banking")
    # interest_rate remains at its default (unchanged) — not 1.5.
    assert engine is None or engine.interest_rate is None or Decimal(str(engine.interest_rate)) <= Decimal("1.0")
