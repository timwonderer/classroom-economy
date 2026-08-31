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

# Fixed scales (SPEC-ITR-001 §15.9). Fractions carry four places to preserve
# ratio precision; distribution statistics carry two.
FRACTION_SCALE = 4
DISTRIBUTION_SCALE = 2

_FRACTION_QUANT = Decimal(10) ** -FRACTION_SCALE
_DISTRIBUTION_QUANT = Decimal(10) ** -DISTRIBUTION_SCALE

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
