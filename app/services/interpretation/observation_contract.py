"""Canonical ``observations_json`` serialization contract (SPEC-ITR-001 §15).

This module is the executable counterpart of SPEC-ITR-001 v1.3 §15. It defines
the required v1 candidate manifest, the closed value-kind vocabulary, and a
**pure, DB-free structural validator** for the ``observations_json`` payload that
is persisted in an ``interpretation_cycle_record`` (``DOM-ITR-001`` §IX).

Scope discipline (slice 8.2a):
* This is the *contract + validator* only. It performs **no** candidate
  computation, reads **no** domain facts, and touches **no** database. Candidate
  math is slice 8.2b; the materialization write is slice 8.2c.
* ``coverage.complete`` is **serializer-derived** here, never trusted from the
  payload (SPEC-ITR-001 §15.8). The 8.2c writer calls
  :func:`validate_for_materialization`, which re-derives completeness and fails
  closed, so a partial payload can never become an immutable record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# --- Contract identity (SPEC-ITR-001 §15.1) --------------------------------

SCHEMA_VERSION = 1
SPEC_REF = "SPEC-ITR-001"
SPEC_VERSION = "1.3"
REQUIRED_SET_VERSION = 1

# --- Required v1 candidate manifest (SPEC-ITR-001 §15.2) --------------------

REQUIRED_SET_V1: frozenset[str] = frozenset(
    {
        "Q1a-C1", "Q1a-C2",
        "Q1b-C1",
        "Q2-C1", "Q2-C2",
        "Q3-C1", "Q3-C2", "Q3-C3",
        "Q4-C1", "Q4-C2", "Q4-C3",
        "Q5-C1", "Q5-C2",
        "Q6-C1", "Q6-C2", "Q6-C3",
        "Q9-C1",
    }
)

# Balance-distribution candidates that MUST carry the ``n_at_or_below_zero``
# extension on their top-level ``distribution`` value (SPEC-ITR-001 §15.6.1).
BALANCE_DISTRIBUTION_CANDIDATES: frozenset[str] = frozenset({"Q6-C1", "Q6-C2", "Q6-C3"})

# --- Closed enumerations (SPEC-ITR-001 §15.3, §15.5, §15.6) -----------------

SEMANTIC_KINDS: frozenset[str] = frozenset({"descriptive_observation", "interpretive_signal"})
REFERENCE_DEPENDENCIES: frozenset[str] = frozenset(
    {"none", "class_configuration_observational_reference", "interpretation_declared_reference"}
)
NORMALIZATION_DEPENDENCIES: frozenset[str] = frozenset({"cwi"})  # nullable; only value used in v1
APPLICABILITY_STATES: frozenset[str] = frozenset({"computed", "not_applicable"})

VALUE_KINDS: frozenset[str] = frozenset(
    {
        "fraction",
        "category_fractions",
        "category_fractions_by_type",
        "ratio",
        "rate",
        "amount",
        "distribution",
        "counts",
        "coverage_by_type",
        "signal_set",
    }
)

# The four integer fields carried per obligation type by a ``coverage_by_type``
# value (SPEC-ITR-001 §15.6, §8.4 Q3-C2). All are integer minor units (cents).
COVERAGE_BY_TYPE_FIELDS: tuple[str, ...] = (
    "assessed_cents",
    "student_paid_cents",
    "waived_cents",
    "unmet_cents",
)

DISTRIBUTION_CORE_KEYS: tuple[str, ...] = ("count", "p10", "p25", "p50", "p75", "p90", "iqr")
DISTRIBUTION_DECIMAL_CORE: tuple[str, ...] = ("p10", "p25", "p50", "p75", "p90", "iqr")


# --- Result type -----------------------------------------------------------


@dataclass(frozen=True)
class ContractValidationResult:
    """Outcome of validating an ``observations_json`` payload.

    ``complete`` is serializer-derived (SPEC-ITR-001 §15.8): it is ``True`` iff
    the present candidate set exactly equals :data:`REQUIRED_SET_V1` with no
    duplicates or extras and every entry is structurally lawful.
    """

    complete: bool
    errors: tuple[str, ...] = ()
    present_ids: frozenset[str] = frozenset()
    missing_ids: frozenset[str] = frozenset()
    extra_ids: frozenset[str] = frozenset()
    duplicate_ids: frozenset[str] = frozenset()

    @property
    def ok(self) -> bool:
        return self.complete and not self.errors


class ObservationContractError(ValueError):
    """Raised by :func:`validate_for_materialization` when the payload is not a
    lawful, complete materialization payload (fail-closed gate, §15.8)."""


# --- Internal helpers ------------------------------------------------------


def _is_canonical_decimal_string(raw: Any) -> bool:
    """A canonical decimal is a plain string parseable as a finite Decimal.

    Floats are rejected (§15.9 requires string decimals); scientific notation
    and non-finite values are rejected.
    """
    if not isinstance(raw, str):
        return False
    stripped = raw.strip()
    if stripped == "" or "e" in stripped.lower():
        return False
    try:
        dec = Decimal(stripped)
    except (InvalidOperation, ValueError):
        return False
    return dec.is_finite()


def _is_int(raw: Any) -> bool:
    # bool is an int subclass; exclude it explicitly.
    return isinstance(raw, int) and not isinstance(raw, bool)


def _validate_distribution(value: dict, *, require_below_zero: bool, path: str, errors: list[str]) -> None:
    for key in DISTRIBUTION_CORE_KEYS:
        if key not in value:
            errors.append(f"{path}: distribution missing required core key '{key}' (§15.6.1)")
    if "count" in value and not _is_int(value["count"]):
        errors.append(f"{path}: distribution 'count' must be an integer (§15.9)")
    for key in DISTRIBUTION_DECIMAL_CORE:
        if key in value and not _is_canonical_decimal_string(value[key]):
            errors.append(f"{path}: distribution '{key}' must be a canonical decimal string (§15.9)")
    if require_below_zero:
        if "n_at_or_below_zero" not in value:
            errors.append(
                f"{path}: balance distribution missing required 'n_at_or_below_zero' extension (§15.6.1)"
            )
        elif not _is_int(value["n_at_or_below_zero"]):
            errors.append(f"{path}: 'n_at_or_below_zero' must be an integer (§15.9)")
    if "mean" in value and not _is_canonical_decimal_string(value["mean"]):
        errors.append(f"{path}: optional 'mean' must be a canonical decimal string (§15.9)")
    allowed = set(DISTRIBUTION_CORE_KEYS) | {"kind", "n_at_or_below_zero", "mean"}
    for key in value:
        if key not in allowed:
            errors.append(f"{path}: distribution carries non-vocabulary statistic '{key}' (§15.6.1)")


def _validate_value(value: Any, *, candidate_id: str, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: 'value' must be an object with a 'kind' discriminator (§15.6)")
        return
    kind = value.get("kind")
    if kind not in VALUE_KINDS:
        errors.append(f"{path}: value.kind '{kind}' is not in the closed v1 vocabulary (§15.6)")
        return

    if kind == "fraction":
        for k in ("numerator", "denominator"):
            if not _is_int(value.get(k)):
                errors.append(f"{path}: fraction '{k}' must be an integer (§14.2, §15.6)")
        if not _is_canonical_decimal_string(value.get("value")):
            errors.append(f"{path}: fraction 'value' must be a canonical decimal string (§15.9)")
    elif kind == "category_fractions":
        cats = value.get("categories")
        if not isinstance(cats, list) or not cats:
            errors.append(f"{path}: category_fractions 'categories' must be a non-empty list (§15.6)")
        else:
            labels = [c.get("category") for c in cats if isinstance(c, dict)]
            if labels != sorted(labels):
                errors.append(f"{path}: category_fractions.categories must be sorted by 'category' (§15.9)")
            for i, cat in enumerate(cats):
                cp = f"{path}.categories[{i}]"
                if not isinstance(cat, dict):
                    errors.append(f"{cp}: category entry must be an object (§15.6)")
                    continue
                for k in ("numerator", "denominator"):
                    if not _is_int(cat.get(k)):
                        errors.append(f"{cp}: '{k}' must be an integer (§14.2, §15.6)")
                if not _is_canonical_decimal_string(cat.get("value")):
                    errors.append(f"{cp}: 'value' must be a canonical decimal string (§15.9)")
    elif kind == "category_fractions_by_type":
        by_type = value.get("obligation_types")
        if not isinstance(by_type, dict):
            errors.append(
                f"{path}: category_fractions_by_type 'obligation_types' must be an object "
                "keyed by obligation type (§15.6, §8.4)"
            )
        else:
            # An empty map is the lawful zero-observation state (no obligations in
            # the window). Keys are obligation types; the map is order-independent
            # (§15.9 — no object-key ordering requirement). Each value is a nested
            # per-type category_fractions, validated with the same rules.
            for type_key, nested in by_type.items():
                tp = f"{path}.obligation_types[{type_key!r}]"
                if not isinstance(type_key, str) or not type_key:
                    errors.append(f"{tp}: obligation type key must be a non-empty string (§15.6)")
                if not isinstance(nested, dict) or nested.get("kind") != "category_fractions":
                    errors.append(f"{tp}: per-type value must be a 'category_fractions' value (§15.6)")
                    continue
                _validate_value(nested, candidate_id=candidate_id, path=tp, errors=errors)
    elif kind == "coverage_by_type":
        by_type = value.get("obligation_types")
        if not isinstance(by_type, dict):
            errors.append(
                f"{path}: coverage_by_type 'obligation_types' must be an object "
                "keyed by obligation type (§15.6, §8.4)"
            )
        else:
            for type_key, comp in by_type.items():
                tp = f"{path}.obligation_types[{type_key!r}]"
                if not isinstance(type_key, str) or not type_key:
                    errors.append(f"{tp}: obligation type key must be a non-empty string (§15.6)")
                if not isinstance(comp, dict):
                    errors.append(f"{tp}: per-type coverage must be an object (§15.6)")
                    continue
                for field in COVERAGE_BY_TYPE_FIELDS:
                    if not _is_int(comp.get(field)):
                        errors.append(f"{tp}: '{field}' must be an integer minor-unit count (§15.6, §15.9)")
                for extra in comp:
                    if extra not in COVERAGE_BY_TYPE_FIELDS:
                        errors.append(f"{tp}: carries non-vocabulary coverage field '{extra}' (§15.6)")
    elif kind in ("ratio", "rate"):
        if not _is_canonical_decimal_string(value.get("value")):
            errors.append(f"{path}: {kind} 'value' must be a canonical decimal string (§15.9)")
        if kind == "rate" and not isinstance(value.get("unit"), str):
            errors.append(f"{path}: rate 'unit' must be a string unit identifier (§15.6)")
    elif kind == "amount":
        if not _is_canonical_decimal_string(value.get("value")):
            errors.append(f"{path}: amount 'value' must be a canonical decimal string (§15.9)")
        if not isinstance(value.get("unit"), str):
            errors.append(f"{path}: amount 'unit' must be a string unit identifier (§15.6)")
    elif kind == "distribution":
        _validate_distribution(
            value,
            require_below_zero=candidate_id in BALANCE_DISTRIBUTION_CANDIDATES,
            path=path,
            errors=errors,
        )
    elif kind == "counts":
        items = value.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}: counts 'items' must be a non-empty list (§15.6)")
        else:
            labels = [it.get("label") for it in items if isinstance(it, dict)]
            if labels != sorted(labels):
                errors.append(f"{path}: counts.items must be sorted by 'label' (§15.9)")
            for i, item in enumerate(items):
                if not isinstance(item, dict) or not isinstance(item.get("label"), str) or not _is_int(
                    item.get("count")
                ):
                    errors.append(f"{path}.items[{i}]: each item needs a string 'label' and integer 'count' (§15.6)")
        if not _is_int(value.get("total")):
            errors.append(f"{path}: counts 'total' must be an integer (§15.6)")
    elif kind == "signal_set":
        signals = value.get("signals")
        if not isinstance(signals, list) or not signals:
            errors.append(f"{path}: signal_set 'signals' must be a non-empty list (§15.6, §13.3)")
        else:
            ids = [s.get("signal_id") for s in signals if isinstance(s, dict)]
            if ids != sorted(ids):
                errors.append(f"{path}: signal_set.signals must be sorted by 'signal_id' (§15.9)")
            for i, sig in enumerate(signals):
                sp = f"{path}.signals[{i}]"
                if not isinstance(sig, dict):
                    errors.append(f"{sp}: signal entry must be an object (§15.6)")
                    continue
                if not isinstance(sig.get("signal_id"), str):
                    errors.append(f"{sp}: 'signal_id' must be a string (§15.6)")
                sig_app = sig.get("applicability")
                if sig_app not in APPLICABILITY_STATES:
                    errors.append(f"{sp}: signal 'applicability' must be 'computed' or 'not_applicable' (§15.3)")
                if sig_app == "computed":
                    # Nested signals reuse the value-kind vocabulary. The
                    # ``n_at_or_below_zero`` requirement is not enforced on nested
                    # signals because SPEC-ITR-001 does not enumerate Q9 signal
                    # ids; core distribution structure is still checked.
                    _validate_value(sig.get("value"), candidate_id=candidate_id, path=f"{sp}.value", errors=errors)
                elif sig_app == "not_applicable":
                    if sig.get("value") not in (None,) and "value" in sig:
                        errors.append(f"{sp}: not_applicable signal must not carry a 'value' (§15.3)")


def _validate_entry(entry: Any, *, index: int, errors: list[str]) -> str | None:
    """Validate one observation entry. Returns its ``candidate_id`` (or None)."""
    path = f"observations[{index}]"
    if not isinstance(entry, dict):
        errors.append(f"{path}: entry must be an object (§15.5)")
        return None

    candidate_id = entry.get("candidate_id")
    if not isinstance(candidate_id, str):
        errors.append(f"{path}: 'candidate_id' must be a string (§15.5)")
        candidate_id = None

    if entry.get("semantic_kind") not in SEMANTIC_KINDS:
        errors.append(f"{path}: 'semantic_kind' invalid (§15.5)")
    for prop in ("subject", "observation_basis", "aggregation"):
        if not isinstance(entry.get(prop), str) or not entry.get(prop):
            errors.append(f"{path}: '{prop}' must be a non-empty string (§15.5, INV-ITR-012)")
    if entry.get("reference_dependency") not in REFERENCE_DEPENDENCIES:
        errors.append(f"{path}: 'reference_dependency' invalid (§15.5, INV-ITR-012)")

    norm = entry.get("normalization_dependency", None)
    if norm is not None and norm not in NORMALIZATION_DEPENDENCIES:
        errors.append(f"{path}: 'normalization_dependency' must be null or 'cwi' (§3.1, §15.5)")

    applicability = entry.get("applicability")
    if applicability not in APPLICABILITY_STATES:
        errors.append(f"{path}: 'applicability' must be 'computed' or 'not_applicable' (§15.3)")
    elif applicability == "computed":
        if entry.get("not_applicable_reason") not in (None,):
            errors.append(f"{path}: computed entry must not carry 'not_applicable_reason' (§15.3)")
        if "value" not in entry or entry.get("value") is None:
            errors.append(f"{path}: computed entry must carry a non-null 'value' (§15.3)")
        else:
            _validate_value(entry["value"], candidate_id=candidate_id or "", path=f"{path}.value", errors=errors)
    elif applicability == "not_applicable":
        if entry.get("value") is not None:
            errors.append(f"{path}: not_applicable entry must not carry a 'value' (§15.3)")
        if not isinstance(entry.get("not_applicable_reason"), dict):
            errors.append(f"{path}: not_applicable entry must carry a structured 'not_applicable_reason' (§15.3)")

    quals = entry.get("qualifiers", None)
    if quals is not None and not isinstance(quals, dict):
        errors.append(f"{path}: 'qualifiers' must be null or a structured object (§15.7)")

    return candidate_id


# --- Public API ------------------------------------------------------------


def validate_payload_structure(payload: Any) -> ContractValidationResult:
    """Structurally validate an ``observations_json`` payload against §15.

    Pure and side-effect free. Derives ``complete`` per §15.8; never trusts a
    payload-supplied ``coverage.complete``.
    """
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ContractValidationResult(complete=False, errors=("payload must be a JSON object (§15.4)",))

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION} (§15.1)")

    spec = payload.get("spec")
    if not isinstance(spec, dict) or spec.get("ref") != SPEC_REF or spec.get("version") != SPEC_VERSION:
        errors.append(f"spec must be {{ref: '{SPEC_REF}', version: '{SPEC_VERSION}'}} (§15.1)")

    coverage = payload.get("coverage")
    if not isinstance(coverage, dict) or coverage.get("required_set_version") != REQUIRED_SET_VERSION:
        errors.append(f"coverage.required_set_version must be {REQUIRED_SET_VERSION} (§15.1)")
    elif "candidates_present" in coverage or "candidates_missing" in coverage:
        errors.append("coverage must not carry compute-supplied candidate lists (§15.4)")

    observations = payload.get("observations")
    if not isinstance(observations, list):
        return ContractValidationResult(complete=False, errors=tuple(errors) + ("observations must be a list (§15.4)",))

    seen: list[str] = []
    for i, entry in enumerate(observations):
        cid = _validate_entry(entry, index=i, errors=errors)
        if cid is not None:
            seen.append(cid)

    present = frozenset(seen)
    duplicates = frozenset({cid for cid in seen if seen.count(cid) > 1})
    extras = present - REQUIRED_SET_V1
    missing = REQUIRED_SET_V1 - present

    if duplicates:
        errors.append(f"duplicate candidate_id(s): {sorted(duplicates)} (§15.2, §15.8)")
    if extras:
        errors.append(f"candidate_id(s) outside required-set-v1: {sorted(extras)} (§15.2, §15.8)")
    if missing:
        errors.append(f"missing required candidate_id(s): {sorted(missing)} (§15.2, §15.8)")

    # Determinism: observations sorted ascending by candidate_id (§15.9).
    if seen != sorted(seen):
        errors.append("observations must be sorted ascending by candidate_id (§15.9)")

    complete = (present == REQUIRED_SET_V1) and not duplicates and not extras and not missing and not errors

    return ContractValidationResult(
        complete=complete,
        errors=tuple(errors),
        present_ids=present,
        missing_ids=missing,
        extra_ids=extras,
        duplicate_ids=duplicates,
    )


def derive_coverage_complete(payload: Any) -> bool:
    """Serializer-derived ``coverage.complete`` (§15.8). Ignores any boolean the
    payload asserts; recomputes from ``observations`` + the manifest."""
    return validate_payload_structure(payload).complete


def validate_for_materialization(payload: Any) -> ContractValidationResult:
    """Fail-closed gate for the slice 8.2c writer (§15.8).

    Raises :class:`ObservationContractError` unless the payload is a lawful,
    exactly-complete materialization payload. The writer calls this and only
    writes an immutable record when it returns without raising.
    """
    result = validate_payload_structure(payload)
    if not result.complete:
        raise ObservationContractError(
            "observations_json is not a complete, lawful materialization payload (§15.8): "
            + "; ".join(result.errors)
        )
    return result
