from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ci_classifier import classify
from scripts.ci_evidence_runner import (
    aggregate_status,
    execute_selection,
    manifest_self_check,
    run_family,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".ci" / "invariant_families.yml"


def completed(returncode=0, stdout="ok", stderr=""):
    return subprocess.CompletedProcess(["pytest"], returncode, stdout, stderr)


def test_aggregate_fail_closed_precedence():
    assert aggregate_status([]) == "NOT_EVALUATED"
    assert aggregate_status([{"status": "PASS"}, {"status": "NOT_EVALUATED"}]) == "NOT_EVALUATED"
    assert aggregate_status([{"status": "BLOCKED"}, {"status": "NOT_EVALUATED"}]) == "BLOCKED"
    assert aggregate_status([{"status": "FAIL"}, {"status": "BLOCKED"}]) == "FAIL"


def test_family_without_evidence_is_not_evaluated():
    family = {
        "family_id": "CI-PII", "mandatory": True,
        "governing_authority": ["INV-ARC-018"], "evidence_commands": [],
    }
    result = run_family(family, root=ROOT, pytest_executable="pytest")
    assert result["status"] == "NOT_EVALUATED"


def test_family_command_success_is_pass():
    family = {
        "family_id": "CI-ARC-EXEC", "mandatory": True,
        "governing_authority": ["INV-ARC-006"], "evidence_commands": ["tests/example.py"],
    }
    result = run_family(
        family, root=ROOT, pytest_executable="pytest",
        runner=lambda *args, **kwargs: completed(),
    )
    assert result["status"] == "PASS"
    # Evidence must be collected by pytest, not executed as a bare script.
    assert result["executions"][0]["command"] == ["pytest", "-m", "pytest", "-q", "tests/example.py"]


def test_family_command_failure_is_fail():
    family = {
        "family_id": "CI-ARC-EXEC", "mandatory": True,
        "governing_authority": ["INV-ARC-006"], "evidence_commands": ["tests/example.py"],
    }
    result = run_family(
        family, root=ROOT, pytest_executable="pytest",
        runner=lambda *args, **kwargs: completed(returncode=1, stderr="failure"),
    )
    assert result["status"] == "FAIL"


def test_committed_manifest_passes_self_check():
    """Every path rule must select a real surface at the current revision.

    A rule that matches nothing selects no evidence, which the aggregator cannot
    distinguish from a satisfied gate. This test is the guard against that
    silent-pass failure mode.
    """
    result = manifest_self_check(root=ROOT, manifest=MANIFEST)
    assert result["status"] == "PASS", result["problems"]


def test_self_check_reports_a_path_rule_that_matches_nothing(tmp_path):
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-DEAD\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/nonexistent_surface/**]\n"
        "    evidence_kind: [static]\n"
        "    evidence_commands: []\n"
        "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n",
        encoding="utf-8",
    )
    result = manifest_self_check(root=ROOT, manifest=manifest)
    assert result["status"] == "FAIL"
    assert result["problems"] == [
        {
            "family_id": "CI-DEAD",
            "kind": "path_rule_matches_nothing",
            "detail": "app/nonexistent_surface/**",
        }
    ]


@pytest.mark.parametrize(
    ("field", "value", "kind", "detail"),
    [
        ("evidence_commands", "[tests/deleted_evidence.py]",
         "evidence_command_missing", "tests/deleted_evidence.py"),
        ("auxiliary_evidence", "[not_a_real_validator]",
         "auxiliary_evidence_unknown", "not_a_real_validator"),
    ],
)
def test_self_check_reports_dangling_evidence_references(tmp_path, field, value, kind, detail):
    manifest = tmp_path / "manifest.yml"
    extra = f"    {field}: {value}\n"
    manifest.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-DANGLING\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/models.py]\n"
        "    evidence_kind: [static]\n"
        + ("" if field == "evidence_commands" else "    evidence_commands: []\n")
        + extra
        + "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n",
        encoding="utf-8",
    )
    result = manifest_self_check(root=ROOT, manifest=manifest)
    assert result["status"] == "FAIL"
    assert {"family_id": "CI-DANGLING", "kind": kind, "detail": detail} in result["problems"]


def test_selection_with_missing_families_is_not_evaluated():
    selection = classify(["migrations/versions/new.py"], MANIFEST)
    result = execute_selection(selection, root=ROOT, pytest_executable="pytest", manifest=MANIFEST,
                               runner=lambda *args, **kwargs: completed())
    assert result["status"] == "NOT_EVALUATED"
    statuses = {item["family_id"]: item["status"] for item in result["family_results"]}
    assert statuses["CI-PII"] == "NOT_EVALUATED"
    assert statuses["CI-XDOMAIN"] == "NOT_EVALUATED"
