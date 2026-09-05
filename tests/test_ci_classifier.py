from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci_classifier import ClassifierError, classify, load_manifest, select_families


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".ci" / "invariant_families.yml"


def test_manifest_is_valid_and_family_ids_are_unique():
    families = load_manifest(MANIFEST)
    assert {family["family_id"] for family in families} == {
        "CI-ARC-EXEC", "CI-SCOPE", "CI-TEMPORAL", "CI-PERSIST", "CI-PII",
        "CI-XDOMAIN", "CI-RENDER", "CI-VALIDATION",
    }


def test_route_change_selects_execution_scope_and_validation():
    result = classify(["app/routes/admin.py"], MANIFEST)
    selected = {family["family_id"] for family in result["selected_families"]}
    # Routes are intentionally conservative: they can execute mutation,
    # class-scoped behavior, rendering, persistence, or cross-domain calls.
    assert selected == {"CI-ARC-EXEC", "CI-SCOPE", "CI-PERSIST", "CI-XDOMAIN", "CI-RENDER"}
    assert {item["family_id"] for item in result["unselected_families"]} == {
        "CI-TEMPORAL", "CI-PII", "CI-VALIDATION"
    }


def test_migration_change_event_wide_selects_persistence_pii_and_validation():
    result = classify(["migrations/versions/new_revision.py"], MANIFEST)
    selected = {family["family_id"] for family in result["selected_families"]}
    assert {"CI-PERSIST", "CI-PII", "CI-VALIDATION"} <= selected


def test_dotfile_paths_keep_their_leading_dot():
    """`lstrip("./")` strips a character set, so it ate the dot on dotfiles."""
    result = classify([".github/workflows/constitutional-ci.yml"], MANIFEST)
    assert result["paths"] == [".github/workflows/constitutional-ci.yml"]
    validation = next(
        family for family in result["selected_families"]
        if family["family_id"] == "CI-VALIDATION"
    )
    # Selected by its own path rule, not rescued by the unknown-path fallback.
    assert validation["selection_status"] == "SELECTED"


def test_the_invariant_manifest_is_itself_governed():
    """A change to the file defining every gate must select a family by rule."""
    result = classify([".ci/invariant_families.yml"], MANIFEST)
    selected = {family["family_id"] for family in result["selected_families"]}
    assert selected == {"CI-VALIDATION"}


def test_unknown_path_conservatively_selects_core_families():
    result = classify(["unclassified/new_surface.txt"], MANIFEST)
    selected = {family["family_id"] for family in result["selected_families"]}
    assert selected == {"CI-ARC-EXEC", "CI-SCOPE", "CI-VALIDATION"}


def test_empty_paths_fail_closed():
    with pytest.raises(ClassifierError, match="empty path"):
        classify([], MANIFEST)


def test_manifest_rejects_empty_path_rules(tmp_path):
    path = tmp_path / "manifest.yml"
    path.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-BAD\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: []\n"
        "    evidence_kind: [static]\n"
        "    evidence_commands: []\n"
        "    mandatory: true\n"
        "    pass_contract: bad\n"
        "    known_limits: bad\n",
        encoding="utf-8",
    )
    with pytest.raises(ClassifierError, match="path_rules"):
        load_manifest(path)


def test_selection_records_matching_paths():
    families = load_manifest(MANIFEST)
    selected = select_families(["templates/admin_login.html"], families)
    render = next(family for family in selected if family["family_id"] == "CI-RENDER")
    assert render["matched_paths"] == ["templates/admin_login.html"]
