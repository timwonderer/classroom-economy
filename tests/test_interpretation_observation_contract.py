"""Contract tests for the ``observations_json`` serialization contract.

Exercises SPEC-ITR-001 v1.3 §15 via the pure validator in
``app/services/interpretation/observation_contract.py``. These are structural
contract tests only — they assert nothing about candidate *computation* (slice
8.2b) and touch no database. They prove the completeness gate (§15.8) is
serializer-derived and fails closed.
"""

import copy

import pytest

from app.services.interpretation.observation_contract import (
    ObservationContractError,
    REQUIRED_SET_V1,
    derive_coverage_complete,
    validate_for_materialization,
    validate_payload_structure,
)


# --- Fixture builders ------------------------------------------------------


def _fraction(num, den, val):
    return {"kind": "fraction", "numerator": num, "denominator": den, "value": val}


def _amount(val, unit="tokens", **extra):
    return {"kind": "amount", "value": val, "unit": unit, **extra}


def _distribution(*, below_zero=None, mean=None):
    d = {
        "kind": "distribution",
        "count": 20,
        "p10": "1.00", "p25": "5.00", "p50": "12.00", "p75": "20.00", "p90": "35.00",
        "iqr": "15.00",
    }
    if below_zero is not None:
        d["n_at_or_below_zero"] = below_zero
    if mean is not None:
        d["mean"] = mean
    return d


def _entry(candidate_id, value=None, *, applicability="computed", reason=None, norm=None, qualifiers=None):
    entry = {
        "candidate_id": candidate_id,
        "semantic_kind": "descriptive_observation",
        "subject": "class_id",
        "observation_basis": "seat_id",
        "aggregation": "class_aggregate_from_seat_observations",
        "reference_dependency": "none",
        "normalization_dependency": norm,
        "applicability": applicability,
        "not_applicable_reason": reason,
        "qualifiers": qualifiers,
        "value": value,
    }
    return entry


def _full_observations():
    """A structurally lawful, all-computed set of all 17 required candidates,
    sorted ascending by candidate_id (§15.9)."""
    return [
        _entry("Q1a-C1", _fraction(18, 20, "0.90")),
        _entry("Q1a-C2", _distribution(mean="8.40")),  # no n_at_or_below_zero
        _entry("Q1b-C1", _fraction(14, 20, "0.70")),
        _entry("Q2-C1", _amount("1234.00")),
        _entry("Q2-C2", _amount("102.83", unit="cwi"), norm="cwi"),
        _entry(
            "Q3-C1",
            {
                "kind": "category_fractions_by_type",
                "obligation_types": {
                    "RENT": {
                        "kind": "category_fractions",
                        "categories": [
                            {"category": "paid", "numerator": 30, "denominator": 40, "value": "0.75"},
                            {"category": "unsatisfied", "numerator": 10, "denominator": 40, "value": "0.25"},
                        ],
                    },
                    "NSF_FEE": {
                        "kind": "category_fractions",
                        "categories": [
                            {"category": "paid", "numerator": 5, "denominator": 5, "value": "1.00"},
                        ],
                    },
                },
            },
        ),
        _entry(
            "Q3-C2",
            {
                "kind": "coverage_by_type",
                "obligation_types": {
                    "RENT": {"assessed_cents": 1200, "student_paid_cents": 900,
                             "waived_cents": 100, "unmet_cents": 200},
                    "NSF_FEE": {"assessed_cents": 0, "student_paid_cents": 0,
                                "waived_cents": 0, "unmet_cents": 0},
                },
            },
        ),
        _entry(
            "Q3-C3",
            {
                "kind": "counts",
                "items": [
                    {"label": "paid", "count": 25},
                    {"label": "unsatisfied", "count": 5},
                    {"label": "waived", "count": 10},
                ],
                "total": 40,
            },
        ),
        _entry("Q4-C1", _fraction(12, 20, "0.60")),
        _entry("Q4-C2", _fraction(9, 20, "0.45")),
        _entry("Q4-C3", _amount("640.00")),
        _entry(
            "Q5-C1",
            {
                "kind": "category_fractions",
                "categories": [
                    {"category": "labor", "numerator": 800, "denominator": 1000, "value": "0.80"},
                    {"category": "transfer", "numerator": 200, "denominator": 1000, "value": "0.20"},
                ],
            },
        ),
        _entry("Q5-C2", _fraction(800, 1000, "0.80")),
        _entry("Q6-C1", _distribution(below_zero=3)),
        _entry("Q6-C2", _distribution(below_zero=1)),
        _entry("Q6-C3", _distribution(below_zero=2)),
        _entry(
            "Q9-C1",
            {
                "kind": "signal_set",
                "signals": [
                    {"signal_id": "obligation_outcomes", "applicability": "computed",
                     "value": {"kind": "counts", "items": [{"label": "paid", "count": 30}], "total": 30}},
                    {"signal_id": "resource_checking", "applicability": "computed",
                     "value": _distribution(below_zero=3)},
                ],
            },
        ),
    ]


def _full_payload():
    return {
        "schema_version": 1,
        "spec": {"ref": "SPEC-ITR-001", "version": "1.3"},
        "coverage": {"required_set_version": 1, "complete": True},
        "observations": _full_observations(),
    }


# --- Sanity: the fixture itself is complete --------------------------------


def test_full_valid_payload_is_complete():
    result = validate_payload_structure(_full_payload())
    assert result.errors == ()
    assert result.complete is True
    assert result.present_ids == REQUIRED_SET_V1
    assert result.missing_ids == frozenset()
    # Should not raise.
    validate_for_materialization(_full_payload())


def test_required_set_has_exactly_17():
    assert len(REQUIRED_SET_V1) == 17


# --- Completeness gate: exact set equality (§15.8) -------------------------


def test_missing_candidate_fails_closed():
    payload = _full_payload()
    payload["observations"] = [e for e in payload["observations"] if e["candidate_id"] != "Q3-C3"]
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert "Q3-C3" in result.missing_ids
    with pytest.raises(ObservationContractError):
        validate_for_materialization(payload)


def test_duplicate_candidate_fails():
    payload = _full_payload()
    payload["observations"].append(_entry("Q1b-C1", _fraction(1, 2, "0.50")))
    payload["observations"].sort(key=lambda e: e["candidate_id"])
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert "Q1b-C1" in result.duplicate_ids


def test_extra_candidate_fails():
    payload = _full_payload()
    payload["observations"].append(_entry("Q8-C1", _fraction(1, 2, "0.50")))
    payload["observations"].sort(key=lambda e: e["candidate_id"])
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert "Q8-C1" in result.extra_ids


# --- Applicability model (§15.3) -------------------------------------------


def test_computed_without_value_fails():
    payload = _full_payload()
    payload["observations"][0]["value"] = None
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("must carry a non-null 'value'" in e for e in result.errors)


def test_not_applicable_requires_reason_and_no_value():
    payload = _full_payload()
    # Turn Q6-C2 into a lawful not_applicable (savings disabled) — should stay complete.
    idx = next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == "Q6-C2")
    payload["observations"][idx] = _entry(
        "Q6-C2", value=None, applicability="not_applicable",
        reason={"feature": "savings", "state": "disabled"},
    )
    assert validate_payload_structure(payload).complete is True

    # not_applicable without a reason is unlawful.
    payload["observations"][idx]["not_applicable_reason"] = None
    assert validate_payload_structure(payload).complete is False


def test_not_applicable_with_value_fails():
    payload = _full_payload()
    idx = next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == "Q6-C2")
    payload["observations"][idx] = _entry(
        "Q6-C2", value=_distribution(below_zero=1), applicability="not_applicable",
        reason={"feature": "savings", "state": "disabled"},
    )
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("must not carry a 'value'" in e for e in result.errors)


# --- Value-kind vocabulary (§15.6) -----------------------------------------


def test_unknown_value_kind_fails():
    payload = _full_payload()
    payload["observations"][0]["value"] = {"kind": "gini_coefficient", "value": "0.4"}
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("closed v1 vocabulary" in e for e in result.errors)


def test_distribution_missing_core_stat_fails():
    payload = _full_payload()
    idx = next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == "Q6-C1")
    del payload["observations"][idx]["value"]["iqr"]
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("missing required core key 'iqr'" in e for e in result.errors)


def test_balance_distribution_requires_n_at_or_below_zero():
    payload = _full_payload()
    idx = next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == "Q6-C3")
    del payload["observations"][idx]["value"]["n_at_or_below_zero"]
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("n_at_or_below_zero" in e for e in result.errors)


def test_distribution_rejects_non_vocabulary_statistic():
    payload = _full_payload()
    idx = next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == "Q6-C1")
    payload["observations"][idx]["value"]["gini"] = "0.4"
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("non-vocabulary statistic 'gini'" in e for e in result.errors)


# --- Per-obligation-type value kinds (§15.6, §8.4) -------------------------


def _q3_idx(payload, cid):
    return next(i for i, e in enumerate(payload["observations"]) if e["candidate_id"] == cid)


def test_category_fractions_by_type_empty_map_is_lawful():
    # A window with no obligations yields an empty per-type map — the lawful
    # zero-observation state — and must not fail structural validation.
    payload = _full_payload()
    payload["observations"][_q3_idx(payload, "Q3-C1")]["value"] = {
        "kind": "category_fractions_by_type", "obligation_types": {},
    }
    result = validate_payload_structure(payload)
    assert result.errors == ()
    assert result.complete is True


def test_category_fractions_by_type_nested_must_be_category_fractions():
    payload = _full_payload()
    payload["observations"][_q3_idx(payload, "Q3-C1")]["value"] = {
        "kind": "category_fractions_by_type",
        "obligation_types": {"RENT": {"kind": "amount", "value": "1.00", "unit": "tokens"}},
    }
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("must be a 'category_fractions' value" in e for e in result.errors)


def test_category_fractions_by_type_propagates_nested_sort_rule():
    payload = _full_payload()
    payload["observations"][_q3_idx(payload, "Q3-C1")]["value"] = {
        "kind": "category_fractions_by_type",
        "obligation_types": {
            "RENT": {
                "kind": "category_fractions",
                "categories": [
                    {"category": "unsatisfied", "numerator": 1, "denominator": 2, "value": "0.50"},
                    {"category": "paid", "numerator": 1, "denominator": 2, "value": "0.50"},
                ],
            },
        },
    }
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("must be sorted by 'category'" in e for e in result.errors)


def test_coverage_by_type_requires_integer_components():
    payload = _full_payload()
    payload["observations"][_q3_idx(payload, "Q3-C2")]["value"] = {
        "kind": "coverage_by_type",
        "obligation_types": {
            "RENT": {"assessed_cents": "1200", "student_paid_cents": 900,
                     "waived_cents": 100, "unmet_cents": 200},
        },
    }
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("'assessed_cents' must be an integer" in e for e in result.errors)


def test_coverage_by_type_rejects_non_vocabulary_field():
    payload = _full_payload()
    payload["observations"][_q3_idx(payload, "Q3-C2")]["value"] = {
        "kind": "coverage_by_type",
        "obligation_types": {
            "RENT": {"assessed_cents": 1200, "student_paid_cents": 900,
                     "waived_cents": 100, "unmet_cents": 200, "teacher_paid_cents": 50},
        },
    }
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("non-vocabulary coverage field 'teacher_paid_cents'" in e for e in result.errors)


# --- Determinism (§15.9) ----------------------------------------------------


def test_float_decimal_rejected():
    payload = _full_payload()
    payload["observations"][0]["value"]["value"] = 0.90  # float, not string
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("canonical decimal string" in e for e in result.errors)


def test_unsorted_observations_fails():
    payload = _full_payload()
    payload["observations"].reverse()
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("sorted ascending by candidate_id" in e for e in result.errors)


# --- Serializer-derived coverage.complete (§15.8) --------------------------


def test_coverage_complete_is_serializer_derived_not_trusted():
    # Payload lies that it is incomplete; serializer derives True from content.
    payload = _full_payload()
    payload["coverage"]["complete"] = False
    assert derive_coverage_complete(payload) is True

    # Payload lies that it is complete; serializer derives False (missing one).
    payload2 = _full_payload()
    payload2["coverage"]["complete"] = True
    payload2["observations"] = [e for e in payload2["observations"] if e["candidate_id"] != "Q9-C1"]
    assert derive_coverage_complete(payload2) is False


def test_coverage_rejects_compute_supplied_candidate_lists():
    payload = _full_payload()
    payload["coverage"]["candidates_present"] = sorted(REQUIRED_SET_V1)
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("compute-supplied candidate lists" in e for e in result.errors)


# --- Q6-C3 basis-note qualifier (§15.7, §11.5) -----------------------------


def test_q6c3_checking_only_basis_note_is_lawful():
    """Savings disabled: Q6-C2 not_applicable, Q6-C3 falls back to checking-only
    with a declared basis note (§11.5) — the whole payload stays complete."""
    payload = _full_payload()
    for e in payload["observations"]:
        if e["candidate_id"] == "Q6-C2":
            e.update(applicability="not_applicable", value=None,
                     not_applicable_reason={"feature": "savings", "state": "disabled"})
        if e["candidate_id"] == "Q6-C3":
            e["qualifiers"] = {"basis_note": {"code": "checking_only_savings_disabled",
                                              "excluded_component": "savings"}}
    result = validate_payload_structure(payload)
    assert result.errors == ()
    assert result.complete is True


# --- Envelope identity (§15.1) ---------------------------------------------


def test_wrong_spec_version_fails():
    payload = _full_payload()
    payload["spec"]["version"] = "1.2"
    result = validate_payload_structure(payload)
    assert result.complete is False
    assert any("spec must be" in e for e in result.errors)
