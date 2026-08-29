"""Regression tests for the canonical insurance claim_type taxonomy.

SPEC-ECON-003 §4.5 defines exactly three canonical insurance products:
``TRANSACTION``, ``PRODUCTIVITY``, ``NON_MONETARY``. This module locks in the
legacy→canonical cutover so the old lowercase vocabulary
(``transaction_monetary`` / ``non_monetary`` / ``legacy_monetary``) can never
silently reappear, and so the retirement of ``legacy_monetary`` (a generic
monetary product with NO defined reimbursement architecture per ARC-OPS-001)
into ``TRANSACTION`` — rather than a bogus reinterpretation as lost-wage
``PRODUCTIVITY`` — stays enforced.
"""

import pytest

from app.services.insurance_policy_service import (
    NON_MONETARY,
    PRODUCTIVITY,
    TRANSACTION,
    normalize_insurance_type,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Legacy monetary product → canonical TRANSACTION.
        ("transaction_monetary", TRANSACTION),
        # RETIRED "Variable Monetary" — generic monetary product, NOT lost-wage.
        # It collapses into TRANSACTION, never PRODUCTIVITY.
        ("legacy_monetary", TRANSACTION),
        # External-benefit product → canonical NON_MONETARY.
        ("non_monetary", NON_MONETARY),
        # Canonical values are idempotent.
        ("TRANSACTION", TRANSACTION),
        ("NON_MONETARY", NON_MONETARY),
        ("PRODUCTIVITY", PRODUCTIVITY),
        # Whitespace tolerance.
        ("  transaction_monetary  ", TRANSACTION),
    ],
)
def test_normalize_known_tokens(raw, expected):
    assert normalize_insurance_type(raw) == expected


def test_legacy_monetary_is_never_reinterpreted_as_productivity():
    """The retired 'Variable Monetary' label must not become lost-wage insurance."""
    assert normalize_insurance_type("legacy_monetary") != PRODUCTIVITY
    assert normalize_insurance_type("legacy_monetary") == TRANSACTION


@pytest.mark.parametrize("bad", [None, "", "unknown", 123, object()])
def test_unknown_or_missing_defaults_to_transaction(bad):
    """Unknown/missing tokens default to the generic monetary product, never
    inventing a PRODUCTIVITY reinterpretation."""
    assert normalize_insurance_type(bad) == TRANSACTION


def test_migration_mapping_matches_canonical_taxonomy():
    """The data migration's inlined mapping must agree with the canonical taxonomy."""
    from migrations.versions.d4e5f6a7b8c9_normalize_insurance_claim_type_taxonomy import (
        _TO_CANONICAL,
    )

    for token, expected in _TO_CANONICAL.items():
        assert normalize_insurance_type(token) == expected
