"""Economic Engine — single authority for economic reference calculations.

This module is the canonical, in-code home of the economic reference math defined
by ``docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md``.

Design (per architectural direction, 2026-08-25):

- It is a *cohesive Economic Engine API with feature-specific resolution methods*
  backed by shared canonical CWI / mode / version state — **not** one monolithic
  ``resolve(class_id)`` that eagerly resolves every feature's numbers. Asking for an
  insurance recommendation MUST NOT cause the engine to resolve rent, store, or fines.

    Economic Engine
    ├── resolve_base(class_id)          # CWI, economic mode, canonical engine version
    ├── resolve_insurance(...)          # SPEC-ECON-003 §4.5 (this phase)
    ├── resolve_rent(...)               # (future — migrate individually, prove parity)
    ├── resolve_fines(...)              # (future)
    ├── resolve_store(...)              # (future)
    └── resolve_savings(...)            # (future)

- **INV-ARC-009 (Domain Authority for State).** CWI, economic mode, and the effective
  engine version are *domain-owned inputs* the engine READS via canonical domain
  queries (``get_effective_economic_engine``, ``get_payroll_settings``). This module
  computes *derived economic reference values* (insurance presets/selection) from those
  authoritative inputs. It does not recompute or persist domain state, and it never
  persists derived recommendations — the same authoritative inputs deterministically
  reproduce them (SPEC-ECON-003 determinism requirement).

Numerical values are sourced verbatim from SPEC-ECON-003 §4.5.3–§4.5.8. They MUST NOT
be invented or overridden here; any change is a normative amendment to the spec.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from app.services.class_configuration_query_service import (
    get_effective_economic_engine,
    get_payroll_settings,
)

# --------------------------------------------------------------------------- #
# Canonical constants (SPEC-ECON-003 §4.5)
# --------------------------------------------------------------------------- #

# Product taxonomy — CONSUMED from the insurance-definition boundary, which owns
# the canonical meaning of an insurance type (SPEC-ECON-003 §4.5, FEAT-STOR-003).
# The Economic Engine only *selects recommendations* for a given product; it is
# not the authority for the taxonomy itself. Re-exported here purely so existing
# ``resolve_insurance(product=TRANSACTION, ...)`` call sites keep a stable import.
from app.services.insurance_policy_service import (  # noqa: E402
    TRANSACTION,
    PRODUCTIVITY,
    NON_MONETARY,
    INSURANCE_TYPES as INSURANCE_PRODUCTS,
)

# Tier identifiers. ``single`` is an untiered offering (uses the mid position).
SINGLE = "single"
BASIC = "basic"
MID = "mid"
PREMIUM = "premium"
INSURANCE_TIERS = (SINGLE, BASIC, MID, PREMIUM)

DEFAULT_MODE = "default"

# Premium pricing envelope as a fraction of CWI, per economic mode (SPEC §4.5.2 /
# §4.5.8). ``midpoint`` is the arithmetic mean of the band bounds — this reproduces
# the ``Mid`` / ``Single`` preset column exactly (e.g. default (0.05 + 0.12)/2 = 0.085).
_PREMIUM_BANDS: dict[str, dict[str, Decimal]] = {
    "tight": {"lower": Decimal("0.06"), "upper": Decimal("0.14")},
    "default": {"lower": Decimal("0.05"), "upper": Decimal("0.12")},
    "comfortable": {"lower": Decimal("0.04"), "upper": Decimal("0.10")},
}

# Deterministic band position by tier (SPEC §4.5.8):
#   Basic → bottom, Mid → midpoint, Premium → top, Single → midpoint.
_TIER_BAND_POSITION: dict[str, str] = {
    BASIC: "lower",
    MID: "midpoint",
    PREMIUM: "upper",
    SINGLE: "midpoint",
}

# Per-tier coverage presets that are NOT derivable from the premium band.
# Sourced verbatim from SPEC §4.5.3 (TRANSACTION), §4.5.4 (PRODUCTIVITY),
# §4.5.5 (NON_MONETARY). Order of tuple columns in the spec: Single, Basic, Mid, Premium.
_TRANSACTION_PRESETS: dict[str, dict[str, object]] = {
    SINGLE: {"reimbursement_pct": Decimal("0.60"), "payout_multiple": Decimal("4"), "claims_per_week": 2, "claim_window_days": 7},
    BASIC: {"reimbursement_pct": Decimal("0.40"), "payout_multiple": Decimal("3"), "claims_per_week": 1, "claim_window_days": 3},
    MID: {"reimbursement_pct": Decimal("0.60"), "payout_multiple": Decimal("4"), "claims_per_week": 2, "claim_window_days": 7},
    PREMIUM: {"reimbursement_pct": Decimal("0.80"), "payout_multiple": Decimal("5"), "claims_per_week": 3, "claim_window_days": 14},
}

_PRODUCTIVITY_PRESETS: dict[str, dict[str, object]] = {
    SINGLE: {"reimbursement_pct": Decimal("0.60"), "payout_multiple": Decimal("4"), "claimable_days_per_week": 2},
    BASIC: {"reimbursement_pct": Decimal("0.40"), "payout_multiple": Decimal("3"), "claimable_days_per_week": 1},
    MID: {"reimbursement_pct": Decimal("0.60"), "payout_multiple": Decimal("4"), "claimable_days_per_week": 2},
    PREMIUM: {"reimbursement_pct": Decimal("0.80"), "payout_multiple": Decimal("5"), "claimable_days_per_week": 3},
}

_NON_MONETARY_PRESETS: dict[str, dict[str, object]] = {
    SINGLE: {"claims_per_week": 1, "waiting_period_days": 3},
    BASIC: {"claims_per_week": 1, "waiting_period_days": 7},
    MID: {"claims_per_week": 2, "waiting_period_days": 3},
    PREMIUM: {"claims_per_week": 3, "waiting_period_days": 0},
}

# Teacher-recommended ranges (advisory, not hard caps) — SPEC §4.5.3 / §4.5.4 / §4.5.5.
RECOMMENDED_RANGES = {
    "reimbursement_pct": (Decimal("0.30"), Decimal("0.90")),
    "payout_multiple": (Decimal("2"), Decimal("7")),
    "claims_per_week": (1, 3),
    "claimable_days_per_week": (1, 3),
    "transaction_claim_window_days": (1, 14),
    "non_monetary_waiting_period_days": (0, 7),
}

_CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _normalize_mode(mode: Optional[str]) -> str:
    normalized = (mode or DEFAULT_MODE).strip().lower()
    return normalized if normalized in _PREMIUM_BANDS else DEFAULT_MODE


def _normalize_tier(tier: Optional[str]) -> str:
    normalized = (tier or SINGLE).strip().lower()
    if normalized not in INSURANCE_TIERS:
        raise ValueError(f"Unknown insurance tier: {tier!r}")
    return normalized


def _normalize_product(product: str) -> str:
    normalized = (product or "").strip().upper()
    if normalized not in INSURANCE_PRODUCTS:
        raise ValueError(f"Unknown insurance product: {product!r}")
    return normalized


def recommended_premium_rate(mode: str, tier: str) -> Decimal:
    """Deterministic premium rate (fraction of CWI) per SPEC §4.5.8.

    Basic → band lower bound, Mid/Single → midpoint, Premium → upper bound.
    """
    band = _PREMIUM_BANDS[_normalize_mode(mode)]
    position = _TIER_BAND_POSITION[_normalize_tier(tier)]
    if position == "lower":
        return band["lower"]
    if position == "upper":
        return band["upper"]
    # midpoint
    return (band["lower"] + band["upper"]) / Decimal("2")


# --------------------------------------------------------------------------- #
# resolve_base — shared canonical CWI / mode / version state
# --------------------------------------------------------------------------- #

class EconomicEngineReadiness(str, Enum):
    """Lifecycle readiness of a class's Economic Engine base configuration.

    ``READY`` means the Engine can resolve its required base economic inputs —
    i.e. a CWI is resolvable from the authoritative payroll rate and
    ``expected_weekly_hours``. ``NOT_READY`` means a required base input is
    missing and CWI-dependent features must not operate.

    The Engine owns this definition. Downstream features consume the status;
    they must NOT re-derive readiness from field checks of their own.
    """

    READY = "READY"
    NOT_READY = "NOT_READY"


class EconomicEngineNotReady(Exception):
    """Raised when a CWI-dependent operation runs against a NOT_READY class.

    Carries a stable ``reason`` string suitable for generic surfacing by callers
    (feature-enablement refusal, execution fail-closed). ``class_id`` identifies
    the affected class.
    """

    def __init__(self, class_id: Optional[str], reason: str):
        self.class_id = class_id
        self.reason = reason
        super().__init__(reason)


# Features whose *normative economics require* a resolvable CWI (not merely take
# it as advisory context). Enabling any of these against a NOT_READY class would
# create an impossible ordinary state, so the lawful feature-enable boundary
# refuses the transition. This set is Engine-owned and intentionally narrow:
# ``insurance`` premiums/payout limits are defined off CWI. Features that treat
# CWI as an advisory recommendation only (e.g. store price hints) are NOT listed.
# Features whose normative economics involve PRICING and therefore require a
# resolvable Class Wage Index (CWI = payroll pay rate × expected weekly hours):
# insurance premiums, rent amounts, and store item prices all price against the
# CWI. A CWI-dependent feature cannot transition disabled -> enabled until the
# Economic Engine base is READY (payroll pay rate AND expected weekly hours set),
# and the feature-settings UI groups them together, gated behind that readiness.
#
# Non-pricing features (hall_pass) and the always-on core (payroll, which DEFINES
# the CWI, and banking) are not gated here.
CWI_DEPENDENT_FEATURES = frozenset({"insurance", "rent", "store"})


@dataclass(frozen=True)
class EconomicBase:
    """Authoritative economic inputs the engine reads for a class.

    ``cwi`` is ``None`` when the class has not configured the inputs required to
    define it (missing payroll pay rate or ``expected_weekly_hours``). Callers MUST
    handle ``None`` — pricing recommendations are undefined without a CWI.
    """

    class_id: str
    economic_version_id: Optional[str]
    economy_policy_mode: str
    expected_weekly_hours: Optional[Decimal]
    hourly_pay_rate: Optional[Decimal]
    cwi: Optional[Decimal]

    @property
    def has_cwi(self) -> bool:
        return self.cwi is not None and self.cwi > 0

    @property
    def status(self) -> EconomicEngineReadiness:
        """Readiness of the Engine base for CWI-dependent economics."""
        return (
            EconomicEngineReadiness.READY
            if self.has_cwi
            else EconomicEngineReadiness.NOT_READY
        )

    @property
    def is_ready(self) -> bool:
        return self.status is EconomicEngineReadiness.READY

    @property
    def readiness_reason(self) -> Optional[str]:
        """Human-facing reason the base is NOT_READY, or ``None`` when READY.

        Enumerates the missing base input(s) so callers can surface a stable,
        generic message without duplicating the Engine's readiness definition.
        """
        if self.is_ready:
            return None
        missing = []
        if self.hourly_pay_rate is None:
            missing.append("payroll pay rate")
        if self.expected_weekly_hours is None or self.expected_weekly_hours <= 0:
            missing.append("expected weekly hours")
        if not missing:
            return "Economic Engine base cannot resolve a CWI"
        return "Economic Engine not ready: missing " + " and ".join(missing)


def require_ready_base(class_id: str) -> EconomicBase:
    """Return the class's economic base, or fail closed if it is NOT_READY.

    The canonical fail-closed execution contract for CWI-dependent features:
    enablement should already guarantee readiness, but execution calls this to
    contain any impossible enabled-but-unready state (old/corrupt/migrated data,
    or a future path that bypasses the enablement gate).

    Raises:
        EconomicEngineNotReady: when the Engine base cannot resolve a CWI.
    """
    base = resolve_base(class_id)
    if not base.is_ready:
        raise EconomicEngineNotReady(class_id, base.readiness_reason)
    return base


def resolve_base(class_id: str) -> EconomicBase:
    """Read the canonical economic base (CWI, mode, engine version) for a class.

    Consumes domain authority (INV-ARC-009): the effective ``EconomicEngine``
    version supplies ``economy_policy_mode`` and ``expected_weekly_hours``; the
    canonical ``PayrollSettings`` row supplies the per-minute pay rate. CWI is the
    trivial arithmetic composition of those two authoritative inputs:

        CWI = pay_rate_per_minute × 60 × expected_weekly_hours
    """
    engine = get_effective_economic_engine(class_id, "payroll") if class_id else None
    payroll = get_payroll_settings(class_id) if class_id else None

    economic_version_id = getattr(engine, "economic_version_id", None) if engine else None
    mode = _normalize_mode(getattr(engine, "economy_policy_mode", None) if engine else None)

    expected_weekly_hours = None
    if engine is not None and getattr(engine, "expected_weekly_hours", None) is not None:
        expected_weekly_hours = Decimal(str(engine.expected_weekly_hours))

    pay_rate_per_minute = None
    if payroll is not None and getattr(payroll, "pay_rate", None) is not None:
        pay_rate_per_minute = Decimal(str(payroll.pay_rate))

    hourly_pay_rate = None
    cwi = None
    if pay_rate_per_minute is not None:
        hourly_pay_rate = _money(pay_rate_per_minute * Decimal("60"))
        if expected_weekly_hours is not None and expected_weekly_hours > 0:
            cwi = _money(pay_rate_per_minute * Decimal("60") * expected_weekly_hours)

    return EconomicBase(
        class_id=class_id,
        economic_version_id=economic_version_id,
        economy_policy_mode=mode,
        expected_weekly_hours=expected_weekly_hours,
        hourly_pay_rate=hourly_pay_rate,
        cwi=cwi,
    )


# --------------------------------------------------------------------------- #
# resolve_insurance — SPEC-ECON-003 §4.5
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class InsuranceResolution:
    """Deterministic insurance economic reference for one (product, tier, mode).

    Currency figures (``period_premium``, ``maximum_policy_payout``) are the primary
    presentation values per SPEC §4.5.7; ``recommended_premium_rate`` (fraction of
    CWI) is secondary context. Nothing here is persisted.
    """

    product: str
    tier: str
    mode: str
    cwi: Optional[Decimal]

    # Coverage-period normalization (SPEC §4.5.2 / §4.5.8).
    coverage_week_equivalent: Decimal

    # Premium (economic-mode axis).
    recommended_premium_rate: Decimal            # fraction of CWI (per week-equivalent)
    weekly_premium: Optional[Decimal]            # currency, per week-equivalent
    period_premium: Optional[Decimal]            # currency, scaled to the coverage interval

    # Coverage (tier axis). ``None`` where the product does not define the parameter.
    reimbursement_percentage: Optional[Decimal] = None
    payout_multiple: Optional[Decimal] = None
    maximum_policy_payout: Optional[Decimal] = None   # currency, period ceiling
    claims_allowance_period: Optional[int] = None
    claimable_days_period: Optional[int] = None
    claim_window_days: Optional[int] = None
    waiting_period_days: Optional[int] = None

    # Advisory context surfaced to teachers.
    recommended_ranges: dict = field(default_factory=dict)
    hard_bounds: tuple = ()
    notes: tuple = ()


def _coverage_week_equivalent(coverage_period: str, covered_calendar_days: Optional[int]) -> Decimal:
    """Compute the week-equivalent multiplier for the coverage interval (SPEC §4.5.2).

    ``coverage_week_equivalent = covered_class_local_calendar_days / 7`` over the
    half-open interval ``[coverage_start, next_renewal)``. Weekly coverage is exactly
    1. For monthly (or any non-weekly) coverage the caller MUST supply the actual
    covered class-local calendar-day count, because the renewal calendar is class-
    local temporal state the engine does not own.
    """
    period = (coverage_period or "weekly").strip().lower()
    if period == "weekly" and covered_calendar_days is None:
        return Decimal("1")
    if covered_calendar_days is None:
        raise ValueError(
            f"coverage_period={period!r} requires covered_calendar_days "
            "(dynamic week-equivalent normalization, SPEC §4.5.2)"
        )
    if covered_calendar_days <= 0:
        raise ValueError("covered_calendar_days must be positive")
    return Decimal(covered_calendar_days) / Decimal("7")


def resolve_insurance(
    *,
    class_id: Optional[str] = None,
    product: str,
    tier: str = SINGLE,
    coverage_period: str = "weekly",
    covered_calendar_days: Optional[int] = None,
    cwi: Optional[Decimal] = None,
    mode: Optional[str] = None,
) -> InsuranceResolution:
    """Resolve the canonical insurance economic reference (SPEC §4.5.3–§4.5.8).

    Args:
        class_id: canonical class scope. When ``cwi`` / ``mode`` are not supplied,
            they are read via ``resolve_base(class_id)``.
        product: one of ``TRANSACTION`` / ``PRODUCTIVITY`` / ``NON_MONETARY``.
        tier: ``single`` / ``basic`` / ``mid`` / ``premium``.
        coverage_period: ``"weekly"`` or ``"monthly"`` (or any non-weekly period,
            in which case ``covered_calendar_days`` is required).
        covered_calendar_days: class-local calendar-day span of the coverage interval
            (half-open ``[start, next_renewal)``); required for non-weekly coverage.
        cwi: optional CWI override (else resolved from ``class_id``).
        mode: optional economic-mode override (else resolved from ``class_id``).

    Returns:
        A deterministic, non-persisted ``InsuranceResolution``.
    """
    product = _normalize_product(product)
    tier = _normalize_tier(tier)

    if cwi is None or mode is None:
        base = resolve_base(class_id) if class_id else None
        if cwi is None:
            cwi = base.cwi if base else None
        if mode is None:
            mode = base.economy_policy_mode if base else DEFAULT_MODE
    mode = _normalize_mode(mode)
    cwi = Decimal(str(cwi)) if cwi is not None else None

    week_equiv = _coverage_week_equivalent(coverage_period, covered_calendar_days)
    premium_rate = recommended_premium_rate(mode, tier)

    weekly_premium = _money(cwi * premium_rate) if cwi is not None else None
    period_premium = _money(weekly_premium * week_equiv) if weekly_premium is not None else None

    if product == TRANSACTION:
        preset = _TRANSACTION_PRESETS[tier]
        payout_multiple = Decimal(preset["payout_multiple"])
        maximum_policy_payout = (
            _money(period_premium * payout_multiple) if period_premium is not None else None
        )
        return InsuranceResolution(
            product=product,
            tier=tier,
            mode=mode,
            cwi=cwi,
            coverage_week_equivalent=week_equiv,
            recommended_premium_rate=premium_rate,
            weekly_premium=weekly_premium,
            period_premium=period_premium,
            reimbursement_percentage=Decimal(preset["reimbursement_pct"]),
            payout_multiple=payout_multiple,
            maximum_policy_payout=maximum_policy_payout,
            claims_allowance_period=_scale_allowance(preset["claims_per_week"], week_equiv),
            claim_window_days=int(preset["claim_window_days"]),
            recommended_ranges={
                "reimbursement_pct": RECOMMENDED_RANGES["reimbursement_pct"],
                "payout_multiple": RECOMMENDED_RANGES["payout_multiple"],
                "claims_per_week": RECOMMENDED_RANGES["claims_per_week"],
                "claim_window_days": RECOMMENDED_RANGES["transaction_claim_window_days"],
                "premium_rate": (_PREMIUM_BANDS[mode]["lower"], _PREMIUM_BANDS[mode]["upper"]),
            },
            hard_bounds=(
                "reimbursement ≤ 100%",
                "one claim covers exactly one Ledger transaction",
                "eligibility gates per SPEC §4.5.3 are mechanical only; teacher approves",
            ),
        )

    if product == PRODUCTIVITY:
        preset = _PRODUCTIVITY_PRESETS[tier]
        payout_multiple = Decimal(preset["payout_multiple"])
        maximum_policy_payout = (
            _money(period_premium * payout_multiple) if period_premium is not None else None
        )
        return InsuranceResolution(
            product=product,
            tier=tier,
            mode=mode,
            cwi=cwi,
            coverage_week_equivalent=week_equiv,
            recommended_premium_rate=premium_rate,
            weekly_premium=weekly_premium,
            period_premium=period_premium,
            reimbursement_percentage=Decimal(preset["reimbursement_pct"]),
            payout_multiple=payout_multiple,
            maximum_policy_payout=maximum_policy_payout,
            claimable_days_period=_scale_allowance(preset["claimable_days_per_week"], week_equiv),
            recommended_ranges={
                "reimbursement_pct": RECOMMENDED_RANGES["reimbursement_pct"],
                "payout_multiple": RECOMMENDED_RANGES["payout_multiple"],
                "claimable_days_per_week": RECOMMENDED_RANGES["claimable_days_per_week"],
                "premium_rate": (_PREMIUM_BANDS[mode]["lower"], _PREMIUM_BANDS[mode]["upper"]),
            },
            hard_bounds=(
                "reimbursement ≤ 100%",
                "total validated claimed hours/week ≤ expected_weekly_hours",
                "PRODUCTIVITY payout ≤ 1 CWI per canonical class-local week",
                "unused weekly capacity does not carry forward",
                "actual_payout = min(gross_reimbursement, remaining_period_payout, remaining_weekly_CWI)",
            ),
            notes=(
                "payout_multiple belongs to the tier axis; economic mode never alters it",
                "worked hours do NOT consume claim-hour capacity (SPEC §4.5.4)",
            ),
        )

    # NON_MONETARY — premium is affordability guidance only; no monetary payout.
    preset = _NON_MONETARY_PRESETS[tier]
    return InsuranceResolution(
        product=product,
        tier=tier,
        mode=mode,
        cwi=cwi,
        coverage_week_equivalent=week_equiv,
        recommended_premium_rate=premium_rate,
        weekly_premium=weekly_premium,
        period_premium=period_premium,
        reimbursement_percentage=None,
        payout_multiple=None,
        maximum_policy_payout=None,
        claims_allowance_period=_scale_allowance(preset["claims_per_week"], week_equiv),
        waiting_period_days=int(preset["waiting_period_days"]),
        recommended_ranges={
            "claims_per_week": RECOMMENDED_RANGES["claims_per_week"],
            "waiting_period_days": RECOMMENDED_RANGES["non_monetary_waiting_period_days"],
            "premium_rate": (_PREMIUM_BANDS[mode]["lower"], _PREMIUM_BANDS[mode]["upper"]),
        },
        hard_bounds=(
            "no reimbursement percentage",
            "no payout multiple",
            "no monetary payout ceiling",
            "no actuarial / risk calculation",
        ),
        notes=(
            "premium is affordability guidance only; CTH cannot value the external benefit",
        ),
    )


def _scale_allowance(weekly_allowance: int, week_equiv: Decimal) -> int:
    """Scale an integer per-week-equivalent allowance to the coverage interval.

    ``period_allowance = ceil(weekly_allowance × coverage_week_equivalent)`` (SPEC
    §4.5.8). ``ceil`` governs how many separate claims may be filed, never how much
    may be paid; total exposure stays bounded by the simultaneous weekly and period
    payout ceilings.
    """
    return int(math.ceil(Decimal(weekly_allowance) * week_equiv))


# --------------------------------------------------------------------------- #
# Savings / interest constants (SPEC-ECON-003 §4.2, §5)
# --------------------------------------------------------------------------- #

# Weekly savings target as a fraction of CWI, per economic mode (SPEC §4.2 / §8).
_SAVINGS_RATES: dict[str, Decimal] = {
    "tight": Decimal("0.05"),
    "default": Decimal("0.10"),
    "comfortable": Decimal("0.15"),
}

# Minimum doubling time in years, per economic mode (SPEC §5.2). Interest rates and
# compounding MUST NOT let savings double faster than this.
_MIN_DOUBLING_YEARS: dict[str, Decimal] = {
    "tight": Decimal("6"),
    "default": Decimal("4"),
    "comfortable": Decimal("2"),
}

# Compounding frequency per year (SPEC §5.6). ``never`` is simple interest and is
# special-cased in the doubling-time rearrangement (no compound term).
_COMPOUND_FREQ_PER_YEAR: dict[str, int] = {
    "daily": 365,
    "weekly": 52,
    "monthly": 12,
}
_SUPPORTED_COMPOUND_FREQUENCIES = ("never", "daily", "weekly", "monthly")

# Internal-fine band as a fraction of CWI, per economic mode (SPEC §4.6 / §8).
_FINE_BANDS: dict[str, dict[str, Decimal]] = {
    "tight": {"lower": Decimal("0.07"), "upper": Decimal("0.18")},
    "default": {"lower": Decimal("0.05"), "upper": Decimal("0.15")},
    "comfortable": {"lower": Decimal("0.04"), "upper": Decimal("0.12")},
}

# Progressive (tiered) internal-fine schedule as fractions of CWI (SPEC §4.6.1).
_PROGRESSIVE_FINE_TIERS: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "tight": (Decimal("0.07"), Decimal("0.125"), Decimal("0.18")),
    "default": (Decimal("0.05"), Decimal("0.10"), Decimal("0.15")),
    "comfortable": (Decimal("0.04"), Decimal("0.08"), Decimal("0.12")),
}


def _max_lawful_annual_rate(mode: str, compound_frequency: str) -> Decimal:
    """Maximum lawful annual interest rate for a mode + compound frequency (SPEC §5.4).

    Compound (``daily`` / ``weekly`` / ``monthly``):

        r = n × (2^(1/(n×t)) − 1)

    Simple interest (``never``): doubling under ``A = P(1 + r·t)`` gives ``r = 1/t``.

    ``t`` is the mode's minimum doubling time in years; ``n`` is compounds/year. The
    result is the largest annual rate that does NOT double savings faster than ``t``.
    """
    t = _MIN_DOUBLING_YEARS[_normalize_mode(mode)]
    freq = (compound_frequency or "never").strip().lower()
    if freq == "never":
        # Simple interest: r = 1/t.
        return Decimal("1") / t
    if freq not in _COMPOUND_FREQ_PER_YEAR:
        raise ValueError(f"Unsupported compound_frequency: {compound_frequency!r}")
    n = Decimal(_COMPOUND_FREQ_PER_YEAR[freq])
    # r = n × (2^(1/(n×t)) − 1). Decimal ** supports fractional exponents.
    return n * (Decimal("2") ** (Decimal("1") / (n * t)) - Decimal("1"))


@dataclass(frozen=True)
class SavingsResolution:
    """Deterministic savings-interest economic reference for a class (SPEC §4.2, §5).

    ``max_annual_rate`` is a fraction (e.g. ``0.171`` = 17.1% APR); ``max_apy_percent``
    is the same value expressed as a percentage for teacher-facing display. Nothing is
    persisted — the same authoritative inputs deterministically reproduce these numbers.
    """

    mode: str
    cwi: Optional[Decimal]
    compound_frequency: str

    # Weekly savings target (SPEC §4.2).
    savings_rate: Decimal                       # fraction of CWI
    weekly_savings_target: Optional[Decimal]    # currency

    # Interest ceiling (SPEC §5).
    min_doubling_years: Decimal
    max_annual_rate: Decimal                    # fraction (APR)
    max_apy_percent: Decimal                    # percent, for display

    notes: tuple = ()


def resolve_savings(
    *,
    class_id: Optional[str] = None,
    compound_frequency: str = "never",
    cwi: Optional[Decimal] = None,
    mode: Optional[str] = None,
) -> SavingsResolution:
    """Resolve the canonical savings-interest reference (SPEC §4.2, §5).

    The maximum lawful interest rate depends on the compounding frequency, so the
    caller supplies the frequency they intend to configure. The engine returns the
    largest annual rate that respects the mode's minimum doubling time, alongside the
    weekly savings target. Read-only and non-persisted.
    """
    if cwi is None or mode is None:
        base = resolve_base(class_id) if class_id else None
        if cwi is None:
            cwi = base.cwi if base else None
        if mode is None:
            mode = base.economy_policy_mode if base else DEFAULT_MODE
    mode = _normalize_mode(mode)
    cwi = Decimal(str(cwi)) if cwi is not None else None

    freq = (compound_frequency or "never").strip().lower()
    if freq not in _SUPPORTED_COMPOUND_FREQUENCIES:
        raise ValueError(f"Unsupported compound_frequency: {compound_frequency!r}")

    savings_rate = _SAVINGS_RATES[mode]
    weekly_savings_target = _money(cwi * savings_rate) if cwi is not None else None

    max_annual_rate = _max_lawful_annual_rate(mode, freq)
    # Percent for display; quantize to 4 dp so the surfaced APY is stable/deterministic.
    max_apy_percent = (max_annual_rate * Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    return SavingsResolution(
        mode=mode,
        cwi=cwi,
        compound_frequency=freq,
        savings_rate=savings_rate,
        weekly_savings_target=weekly_savings_target,
        min_doubling_years=_MIN_DOUBLING_YEARS[mode],
        max_annual_rate=max_annual_rate,
        max_apy_percent=max_apy_percent,
        notes=(
            "max rate is the ceiling that respects the mode's minimum doubling time",
            "changing compound frequency changes the lawful maximum rate",
        ),
    )


# Payout capitalization periods per year (SPEC-ECON-001 §7.2). Weekly/monthly only.
_PAYOUT_FREQ_PER_YEAR: dict[str, int] = {
    "weekly": 52,
    "monthly": 12,
}


def _savings_period_factor(
    *,
    annual_rate: Decimal,
    calculation_type: str,
    compound_frequency: str,
    years: Decimal,
) -> Decimal:
    """Multiplicative growth factor over ``years`` (SPEC-ECON-001 §4).

    This is the single authoritative accrual formula. Both the runtime payout and
    the UI projection MUST derive from it so forecasts cannot diverge from execution
    (SPEC-ECON-001 §10, §11).

    - Simple interest (``calculation_type == 'simple'`` or ``compound_frequency ==
      'never'``): ``1 + r·t`` (§4.1). Previously credited interest never joins the
      earning base — but because payout capitalizes into the posted balance, the
      caller controls participation via the balance it passes.
    - Compound interest (§4.2): ``(1 + r/n)^(n·t)`` where ``n`` is the compound
      periods/year. Full ``Decimal`` precision is preserved here; rounding to cents
      happens only at the lawful payout boundary (§5.3).
    """
    freq = (compound_frequency or "never").strip().lower()
    calc = (calculation_type or "simple").strip().lower()
    if calc == "simple" or freq == "never":
        return Decimal("1") + annual_rate * years
    if freq not in _COMPOUND_FREQ_PER_YEAR:
        raise ValueError(f"Unsupported compound_frequency: {compound_frequency!r}")
    n = Decimal(_COMPOUND_FREQ_PER_YEAR[freq])
    return (Decimal("1") + annual_rate / n) ** (n * years)


def savings_interest_for_payout_period(
    *,
    posted_balance: Decimal,
    annual_rate: Decimal,
    calculation_type: str,
    compound_frequency: str,
    payout_frequency: str,
) -> Decimal:
    """Interest owed for one payout window on an eligible posted balance (§4, §7, §9).

    ``posted_balance`` is the authoritative posted savings balance — the sole eligible
    base (SPEC-ECON-001 §9.2/§13). No hidden default APY: the caller supplies the
    Class-Config rate, and a ``None``/non-positive rate or balance yields zero (§11).
    Result is quantized to cents at this payout boundary (§5.3).
    """
    if posted_balance is None or annual_rate is None:
        return Decimal("0.00")
    if posted_balance <= 0 or annual_rate <= 0:
        return Decimal("0.00")
    payout = (payout_frequency or "monthly").strip().lower()
    if payout not in _PAYOUT_FREQ_PER_YEAR:
        raise ValueError(f"Unsupported payout_frequency: {payout_frequency!r}")
    years = Decimal("1") / Decimal(_PAYOUT_FREQ_PER_YEAR[payout])
    factor = _savings_period_factor(
        annual_rate=annual_rate,
        calculation_type=calculation_type,
        compound_frequency=compound_frequency,
        years=years,
    )
    return _money(posted_balance * (factor - Decimal("1")))


def project_savings_balances(
    *,
    posted_balance: Decimal,
    annual_rate: Optional[Decimal],
    calculation_type: str,
    compound_frequency: str,
    payout_frequency: str,
    months: int = 12,
) -> list[Decimal]:
    """Monthly posted-balance forecast built from the runtime payout recurrence (§10).

    Returns ``months + 1`` cent-quantized points (index 0 = now). The forecast walks
    the SAME payout recurrence the runtime engine executes: each payout window credits
    ``savings_interest_for_payout_period`` and capitalizes it into the running balance,
    so the chart is exactly what will post. A ``None``/zero rate produces a flat line
    (no hidden default APY — §11).
    """
    balance = _money(posted_balance or Decimal("0.00"))
    if annual_rate is None or annual_rate <= 0:
        return [balance for _ in range(months + 1)]

    payout = (payout_frequency or "monthly").strip().lower()
    if payout not in _PAYOUT_FREQ_PER_YEAR:
        raise ValueError(f"Unsupported payout_frequency: {payout_frequency!r}")
    payouts_per_year = _PAYOUT_FREQ_PER_YEAR[payout]

    series: list[Decimal] = [balance]
    for month in range(1, months + 1):
        # Number of payout windows that close by the end of this month.
        windows_to_date = (payouts_per_year * month) // 12
        windows_prev = (payouts_per_year * (month - 1)) // 12
        for _ in range(windows_prev, windows_to_date):
            interest = savings_interest_for_payout_period(
                posted_balance=balance,
                annual_rate=annual_rate,
                calculation_type=calculation_type,
                compound_frequency=compound_frequency,
                payout_frequency=payout,
            )
            balance = _money(balance + interest)
        series.append(balance)
    return series


@dataclass(frozen=True)
class OverdraftFineResolution:
    """Deterministic overdraft / internal-fine reference for a class (SPEC §4.6).

    Overdraft (NSF) fees use the generic internal-fine band. The engine surfaces the
    recommended *range* (not a single price) plus a precomputed progressive tier
    schedule; the teacher chooses one, persisted under ``EconomicEngine.flat_overdraft_fee``
    or ``progressive_overdraft_fee``. Non-persisted here.
    """

    mode: str
    cwi: Optional[Decimal]

    # Flat-fee recommendation band (SPEC §4.6).
    fine_rate_lower: Decimal                    # fraction of CWI
    fine_rate_upper: Decimal
    flat_fee_lower: Optional[Decimal]           # currency
    flat_fee_upper: Optional[Decimal]

    # Progressive schedule recommendation (SPEC §4.6.1). Tier fractions are always
    # present; currency amounts require a CWI.
    progressive_rates: tuple                    # (t1, t2, t3) fractions of CWI
    progressive_fees: Optional[tuple] = None    # (t1, t2, t3) currency

    notes: tuple = ()


def resolve_overdraft_fine(
    *,
    class_id: Optional[str] = None,
    cwi: Optional[Decimal] = None,
    mode: Optional[str] = None,
) -> OverdraftFineResolution:
    """Resolve the canonical overdraft / internal-fine reference (SPEC §4.6, §4.6.1).

    Overdraft fees reuse the generic fine band × CWI. Returns the recommended flat-fee
    range and a precomputed progressive tier schedule. Read-only and non-persisted.
    """
    if cwi is None or mode is None:
        base = resolve_base(class_id) if class_id else None
        if cwi is None:
            cwi = base.cwi if base else None
        if mode is None:
            mode = base.economy_policy_mode if base else DEFAULT_MODE
    mode = _normalize_mode(mode)
    cwi = Decimal(str(cwi)) if cwi is not None else None

    band = _FINE_BANDS[mode]
    tiers = _PROGRESSIVE_FINE_TIERS[mode]

    flat_fee_lower = _money(cwi * band["lower"]) if cwi is not None else None
    flat_fee_upper = _money(cwi * band["upper"]) if cwi is not None else None
    progressive_fees = (
        tuple(_money(cwi * rate) for rate in tiers) if cwi is not None else None
    )

    return OverdraftFineResolution(
        mode=mode,
        cwi=cwi,
        fine_rate_lower=band["lower"],
        fine_rate_upper=band["upper"],
        flat_fee_lower=flat_fee_lower,
        flat_fee_upper=flat_fee_upper,
        progressive_rates=tiers,
        progressive_fees=progressive_fees,
        notes=(
            "overdraft/NSF fees reuse the generic internal-fine band (SPEC §4.6.1)",
            "recommendation is a range, not a single price; teacher chooses the value",
            "an overdraft fee is only active when its persisted value is not NULL",
        ),
    )
