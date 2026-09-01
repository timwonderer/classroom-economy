"""Deterministic builders for ``observations_json`` value shapes and entries.

Pure helpers shared by the slice 8.2b candidate compute modules. Every value
these produce is structurally lawful against the closed vocabulary in
SPEC-ITR-001 §15.6 and the determinism rules in §15.9 (canonical decimal
*strings*, never floats). Nothing here reads the database or mutates state.

Determinism is a hard requirement: immutable records from different cycles must
speak the same statistical language, so decimals are emitted at fixed scales and
percentiles use a single, pinned interpolation method.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

# Fixed scales (SPEC-ITR-001 §15.9). Fractions and ratios carry four places to
# preserve ratio precision; distribution statistics and monetary amounts carry
# two (amounts are token minor-unit magnitudes rendered as dollars).
FRACTION_SCALE = 4
RATIO_SCALE = 4
RATE_SCALE = 4
DISTRIBUTION_SCALE = 2
AMOUNT_SCALE = 2

_FRACTION_QUANT = Decimal(10) ** -FRACTION_SCALE
_RATIO_QUANT = Decimal(10) ** -RATIO_SCALE
_RATE_QUANT = Decimal(10) ** -RATE_SCALE
_DISTRIBUTION_QUANT = Decimal(10) ** -DISTRIBUTION_SCALE
_AMOUNT_QUANT = Decimal(10) ** -AMOUNT_SCALE

# Pinned percentile points for the distribution core (SPEC-ITR-001 §15.6.1).
_PERCENTILE_POINTS: tuple[tuple[str, int], ...] = (
    ("p10", 10),
    ("p25", 25),
    ("p50", 50),
    ("p75", 75),
    ("p90", 90),
)


def canonical_decimal(value: Decimal, quant: Decimal) -> str:
    """Quantize ``value`` to ``quant`` and render it as a canonical decimal string.

    Rounding is banker's rounding (ROUND_HALF_EVEN) for reproducibility. The
    result is a plain fixed-point string with no exponent (rejected by the
    contract validator, §15.9). Negative zero is normalized to ``0``.
    """
    quantized = value.quantize(quant, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = quantized.copy_abs()  # kill "-0.00"
    return f"{quantized:f}"


def fraction_value(numerator: int, denominator: int) -> dict[str, Any]:
    """Build a ``fraction`` value with integer provenance (SPEC-ITR-001 §15.6).

    The numerator/denominator counts live *inside* the value shape (the
    fraction is self-describing). A zero denominator (empty enrolled population)
    yields a value of ``0`` rather than raising — an empty class is a lawful,
    if degenerate, observation.
    """
    num = int(numerator)
    den = int(denominator)
    ratio = Decimal(num) / Decimal(den) if den else Decimal(0)
    return {
        "kind": "fraction",
        "numerator": num,
        "denominator": den,
        "value": canonical_decimal(ratio, _FRACTION_QUANT),
    }


def ratio_value(antecedent: int, consequent: int) -> dict[str, Any]:
    """Build a ``ratio`` value (SPEC-ITR-001 §15.6) from two observed magnitudes.

    ``antecedent`` / ``consequent`` are integer minor-unit magnitudes (e.g. cents).
    A zero consequent yields a value of ``0`` rather than raising — an empty
    denominator is a degenerate but lawful observation.
    """
    ant = int(antecedent)
    con = int(consequent)
    quotient = Decimal(ant) / Decimal(con) if con else Decimal(0)
    return {
        "kind": "ratio",
        "antecedent": ant,
        "consequent": con,
        "value": canonical_decimal(quotient, _RATIO_QUANT),
    }


def rate_value(numerator: int, denominator: int, *, unit: str) -> dict[str, Any]:
    """Build a ``rate`` value (SPEC-ITR-001 §15.6): a per-unit quantity.

    ``numerator`` / ``denominator`` are integer counts (e.g. transactions and
    active-seat-days). ``unit`` names the per-unit basis (e.g.
    ``transactions_per_active_seat_per_day``). A zero denominator yields ``0``.
    """
    num = int(numerator)
    den = int(denominator)
    quotient = Decimal(num) / Decimal(den) if den else Decimal(0)
    return {
        "kind": "rate",
        "numerator": num,
        "denominator": den,
        "unit": unit,
        "value": canonical_decimal(quotient, _RATE_QUANT),
    }


def amount_value(minor_units: int, *, unit: str = "tokens") -> dict[str, Any]:
    """Build an ``amount`` value (SPEC-ITR-001 §15.6) from integer minor units.

    ``minor_units`` is a signed cents magnitude; it is rendered as a two-place
    decimal in whole tokens. ``unit`` is ``"tokens"`` for raw magnitudes or
    ``"cwi"`` when CWI-normalized.
    """
    dollars = Decimal(int(minor_units)) / Decimal(100)
    return {
        "kind": "amount",
        "value": canonical_decimal(dollars, _AMOUNT_QUANT),
        "unit": unit,
    }


def category_fractions_value(
    category_numerators: dict[str, int], denominator: int
) -> dict[str, Any]:
    """Build a ``category_fractions`` value (SPEC-ITR-001 §15.6, §10.2).

    ``category_numerators`` maps each category id to its integer minor-unit
    magnitude; ``denominator`` is the shared total. Every supplied category is
    emitted (a zero share is lawful), sorted ascending by ``category`` id as
    §15.9 requires. Each category carries its own paired ``numerator`` /
    ``denominator`` provenance. A zero denominator yields ``0`` per category.
    """
    den = int(denominator)
    categories = []
    for label in sorted(category_numerators):
        num = int(category_numerators[label])
        share = Decimal(num) / Decimal(den) if den else Decimal(0)
        categories.append(
            {
                "category": label,
                "numerator": num,
                "denominator": den,
                "value": canonical_decimal(share, _FRACTION_QUANT),
            }
        )
    return {"kind": "category_fractions", "categories": categories}


def counts_value(counts: dict[str, int]) -> dict[str, Any]:
    """Build a ``counts`` value (SPEC-ITR-001 §15.6): a categorical count vector.

    ``counts`` maps each label id to its integer count. Every supplied label is
    emitted (an explicit zero is lawful and informative), sorted ascending by
    ``label`` as §15.9 requires; ``total`` is the sum of the counts. The caller
    must supply a non-empty mapping — the closed vocabulary forbids an empty
    ``items`` list, so a zero-observation window supplies an explicit zero-count
    baseline rather than an empty vector.
    """
    items = [{"label": label, "count": int(counts[label])} for label in sorted(counts)]
    return {"kind": "counts", "items": items, "total": sum(item["count"] for item in items)}


def category_fractions_by_type_value(
    type_category_numerators: dict[str, dict[str, int]],
    type_denominators: dict[str, int],
) -> dict[str, Any]:
    """Build a ``category_fractions_by_type`` value (SPEC-ITR-001 §15.6, §8.4).

    ``type_category_numerators`` maps each obligation type to its own
    ``{category: numerator}`` mapping; ``type_denominators`` maps each type to its
    shared denominator (e.g. that type's obligation count). Each type's payload is
    an ordinary :func:`category_fractions_value`, so per-type category arrays are
    sorted per §15.9. The ``obligation_types`` object is keyed by type and is
    order-independent; an empty input yields an empty (but lawful) map — the
    zero-observation state for a window with no obligations.
    """
    obligation_types = {
        obligation_type: category_fractions_value(
            type_category_numerators[obligation_type],
            type_denominators.get(obligation_type, 0),
        )
        for obligation_type in type_category_numerators
    }
    return {"kind": "category_fractions_by_type", "obligation_types": obligation_types}


def coverage_by_type_value(
    type_coverage: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Build a ``coverage_by_type`` value (SPEC-ITR-001 §15.6, §8.4 Q3-C2).

    ``type_coverage`` maps each obligation type to a dict carrying the four
    integer minor-unit fields ``assessed_cents``, ``student_paid_cents``,
    ``waived_cents``, ``unmet_cents`` (the three numerators partition assessed).
    The values are copied verbatim as integers; an empty input yields an empty
    lawful map (zero-observation window).
    """
    obligation_types = {
        obligation_type: {
            "assessed_cents": int(comp.get("assessed_cents", 0)),
            "student_paid_cents": int(comp.get("student_paid_cents", 0)),
            "waived_cents": int(comp.get("waived_cents", 0)),
            "unmet_cents": int(comp.get("unmet_cents", 0)),
        }
        for obligation_type, comp in type_coverage.items()
    }
    return {"kind": "coverage_by_type", "obligation_types": obligation_types}


def _percentile(sorted_vals: list[int], point: int) -> Decimal:
    """Linear-interpolation percentile on a pre-sorted list (pinned method).

    Uses the ``(n-1)`` rank convention with linear interpolation between the two
    nearest ranks — the single method SPEC-ITR-001 §15.6.1 pins for all cycles.
    """
    n = len(sorted_vals)
    if n == 0:
        return Decimal(0)
    if n == 1:
        return Decimal(sorted_vals[0])
    rank = (Decimal(n - 1) * Decimal(point)) / Decimal(100)
    lo = int(rank)  # floor for non-negative rank
    hi = min(lo + 1, n - 1)
    frac = rank - Decimal(lo)
    lo_v = Decimal(sorted_vals[lo])
    hi_v = Decimal(sorted_vals[hi])
    return lo_v + (hi_v - lo_v) * frac


def count_distribution_value(counts: list[int], *, include_mean: bool = True) -> dict[str, Any]:
    """Build a ``distribution`` value from per-seat integer counts.

    Emits the pinned core (``count``, ``p10``, ``p25``, ``p50``, ``p75``,
    ``p90``, ``iqr``) and, optionally, the ``mean`` secondary statistic
    (SPEC-ITR-001 §15.6.1). This helper does NOT attach ``n_at_or_below_zero``:
    it is for non-balance distributions (e.g. attendance-session counts) whose
    zero-crossing tail is not meaningful. ``count`` is the population size (n),
    not a sum.
    """
    ordered = sorted(int(c) for c in counts)
    n = len(ordered)
    value: dict[str, Any] = {"kind": "distribution", "count": n}
    for name, point in _PERCENTILE_POINTS:
        value[name] = canonical_decimal(_percentile(ordered, point), _DISTRIBUTION_QUANT)
    iqr = _percentile(ordered, 75) - _percentile(ordered, 25)
    value["iqr"] = canonical_decimal(iqr, _DISTRIBUTION_QUANT)
    if include_mean:
        total = sum(ordered)
        mean = Decimal(total) / Decimal(n) if n else Decimal(0)
        value["mean"] = canonical_decimal(mean, _DISTRIBUTION_QUANT)
    return value


def observation_entry(
    candidate_id: str,
    *,
    semantic_kind: str,
    subject: str,
    observation_basis: str,
    aggregation: str,
    reference_dependency: str,
    value: dict[str, Any],
    normalization_dependency: str | None = None,
    qualifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one ``computed`` observation entry (SPEC-ITR-001 §15.5).

    All slice-8.2b candidates are ``computed`` descriptive observations, so
    ``not_applicable_reason`` is fixed at ``None`` and the value is mandatory.
    Structural lawfulness is enforced by the contract validator, not asserted
    here.
    """
    return {
        "candidate_id": candidate_id,
        "semantic_kind": semantic_kind,
        "subject": subject,
        "observation_basis": observation_basis,
        "aggregation": aggregation,
        "reference_dependency": reference_dependency,
        "normalization_dependency": normalization_dependency,
        "applicability": "computed",
        "not_applicable_reason": None,
        "qualifiers": qualifiers,
        "value": value,
    }
