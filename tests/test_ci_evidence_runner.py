from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.ci_classifier import classify
from scripts.ci_evidence_runner import aggregate_status, execute_selection, run_family


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
    assert result["executions"][0]["command"] == ["pytest", "-q", "tests/example.py"]


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


def test_selection_with_missing_families_is_not_evaluated():
    selection = classify(["migrations/versions/new.py"], MANIFEST)
    result = execute_selection(selection, root=ROOT, pytest_executable="pytest", manifest=MANIFEST,
                               runner=lambda *args, **kwargs: completed())
    assert result["status"] == "NOT_EVALUATED"
    statuses = {item["family_id"]: item["status"] for item in result["family_results"]}
    assert statuses["CI-PII"] == "NOT_EVALUATED"
    assert statuses["CI-XDOMAIN"] == "NOT_EVALUATED"
