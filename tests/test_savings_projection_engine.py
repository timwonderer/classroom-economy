"""SPEC-ECON-001 conformance for the canonical savings accrual engine.

These are pure-function tests on the single authoritative accrual engine
(`app.services.economic_engine`) that both the runtime payout and the UI
projection consume. They pin:

  * §4.1 simple interest  = 1 + r·t
  * §4.2 compound interest = (1 + r/n)^(n·t)
  * §6 compound frequencies never / daily / weekly / monthly all honored
  * §9.2/§13 eligibility base is the POSTED balance the caller supplies
  * §10 projection == runtime (both derive from the same recurrence)
  * §11 no hidden default APY: an unset rate yields zero interest / a flat line
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.economic_engine import (
    savings_interest_for_payout_period,
    project_savings_balances,
)


def _q(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# §11 — no hidden default APY
# ---------------------------------------------------------------------------


def test_unconfigured_rate_yields_zero_interest():
    """An unset (None) rate must NOT fall back to a fabricated APY."""
    assert savings_interest_for_payout_period(
        posted_balance=Decimal("100.00"),
        annual_rate=None,
        calculation_type="compound",
        compound_frequency="daily",
        payout_frequency="monthly",
    ) == Decimal("0.00")


def test_unconfigured_rate_projects_flat_line():
    series = project_savings_balances(
        posted_balance=Decimal("50.00"),
        annual_rate=None,
        calculation_type="compound",
        compound_frequency="daily",
        payout_frequency="monthly",
        months=12,
    )
    assert series == [Decimal("50.00")] * 13


def test_zero_and_negative_balance_yield_zero():
    for bal in (Decimal("0.00"), Decimal("-25.00")):
        assert savings_interest_for_payout_period(
            posted_balance=bal,
            annual_rate=Decimal("0.05"),
            calculation_type="compound",
            compound_frequency="monthly",
            payout_frequency="monthly",
        ) == Decimal("0.00")


# ---------------------------------------------------------------------------
# §4.1 simple / §4.2 compound math
# ---------------------------------------------------------------------------


def test_simple_interest_one_monthly_window():
    """§4.1: simple interest over 1/12 year on a $100 posted balance @ 12%."""
    got = savings_interest_for_payout_period(
        posted_balance=Decimal("100.00"),
        annual_rate=Decimal("0.12"),
        calculation_type="simple",
        compound_frequency="never",
        payout_frequency="monthly",
    )
    # 100 * (1 + 0.12 * (1/12)) - 100 = 100 * 0.01 = 1.00
    assert got == Decimal("1.00")


def test_compound_never_equals_simple():
    """§4.1: compound_frequency 'never' collapses to simple math."""
    kwargs = dict(
        posted_balance=Decimal("250.00"),
        annual_rate=Decimal("0.09"),
        payout_frequency="monthly",
    )
    simple = savings_interest_for_payout_period(
        calculation_type="simple", compound_frequency="daily", **kwargs
    )
    never = savings_interest_for_payout_period(
        calculation_type="compound", compound_frequency="never", **kwargs
    )
    assert simple == never


def test_compound_daily_matches_closed_form():
    """§4.2: (1 + r/365)^(365 * 1/12) on a $1000 posted balance @ 18%."""
    r = Decimal("0.18")
    n = Decimal("365")
    years = Decimal("1") / Decimal("12")
    expected = _q(Decimal("1000.00") * ((Decimal("1") + r / n) ** (n * years) - Decimal("1")))
    got = savings_interest_for_payout_period(
        posted_balance=Decimal("1000.00"),
        annual_rate=r,
        calculation_type="compound",
        compound_frequency="daily",
        payout_frequency="monthly",
    )
    assert got == expected


@pytest.mark.parametrize("freq", ["daily", "weekly", "monthly"])
def test_all_compound_frequencies_supported(freq):
    """§6: daily / weekly / monthly must all be honored (not silently ignored)."""
    got = savings_interest_for_payout_period(
        posted_balance=Decimal("500.00"),
        annual_rate=Decimal("0.10"),
        calculation_type="compound",
        compound_frequency=freq,
        payout_frequency="monthly",
    )
    assert got > Decimal("0.00")


def test_unsupported_compound_frequency_raises():
    with pytest.raises(ValueError):
        savings_interest_for_payout_period(
            posted_balance=Decimal("500.00"),
            annual_rate=Decimal("0.10"),
            calculation_type="compound",
            compound_frequency="quarterly",
            payout_frequency="monthly",
        )


# ---------------------------------------------------------------------------
# §10 — projection == runtime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("calc,freq", [
    ("simple", "never"),
    ("compound", "daily"),
    ("compound", "weekly"),
    ("compound", "monthly"),
])
def test_projection_first_window_equals_runtime_payout(calc, freq):
    """The first projection step must equal exactly one runtime payout.

    This is the core anti-divergence guarantee (§10): the chart the student
    sees is produced by the same recurrence the ledger will execute.
    """
    posted = Decimal("300.00")
    rate = Decimal("0.15")
    payout = "monthly"

    runtime_interest = savings_interest_for_payout_period(
        posted_balance=posted,
        annual_rate=rate,
        calculation_type=calc,
        compound_frequency=freq,
        payout_frequency=payout,
    )
    series = project_savings_balances(
        posted_balance=posted,
        annual_rate=rate,
        calculation_type=calc,
        compound_frequency=freq,
        payout_frequency=payout,
        months=12,
    )
    # index 0 = now; index 1 = after the first monthly payout window
    assert series[1] - series[0] == runtime_interest


def test_projection_capitalizes_each_window():
    """Each monthly window compounds on the prior posted balance (capitalization)."""
    posted = Decimal("1000.00")
    rate = Decimal("0.12")
    series = project_savings_balances(
        posted_balance=posted,
        annual_rate=rate,
        calculation_type="compound",
        compound_frequency="monthly",
        payout_frequency="monthly",
        months=3,
    )
    # Recompute independently: monthly capitalization.
    bal = posted
    expected = [bal]
    for _ in range(3):
        interest = savings_interest_for_payout_period(
            posted_balance=bal,
            annual_rate=rate,
            calculation_type="compound",
            compound_frequency="monthly",
            payout_frequency="monthly",
        )
        bal = _q(bal + interest)
        expected.append(bal)
    assert series == expected
    # Strictly increasing while rate > 0.
    assert all(series[i + 1] > series[i] for i in range(len(series) - 1))


def test_payout_cadence_preserves_annual_yield():
    """§5/§7: payout cadence governs WHEN interest posts, not total yield.

    With a fixed compound_frequency, weekly and monthly payout both reconstruct
    (1+r/n)^n over the year, so the year-end balance is equal within cent-rounding.
    This guards against a bug where a shorter payout window silently earns a full
    period's interest (over-crediting).
    """
    common = dict(
        posted_balance=Decimal("1000.00"),
        annual_rate=Decimal("0.12"),
        calculation_type="compound",
        compound_frequency="monthly",
        months=12,
    )
    weekly = project_savings_balances(payout_frequency="weekly", **common)
    monthly = project_savings_balances(payout_frequency="monthly", **common)
    assert abs(weekly[-1] - monthly[-1]) <= Decimal("0.05")


def test_higher_compound_frequency_earns_more():
    """§4.2: for a fixed payout cadence, daily compounding beats monthly."""
    common = dict(
        posted_balance=Decimal("1000.00"),
        annual_rate=Decimal("0.12"),
        calculation_type="compound",
        payout_frequency="monthly",
        months=12,
    )
    daily = project_savings_balances(compound_frequency="daily", **common)
    monthly = project_savings_balances(compound_frequency="monthly", **common)
    assert daily[-1] > monthly[-1]
