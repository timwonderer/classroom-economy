#!/usr/bin/env python3
"""Execute selected invariant evidence and aggregate truthful results."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

# When invoked as ``python scripts/ci_evidence_runner.py`` the repository root
# is not on sys.path. Preserve the same import path used by pytest/module mode.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci_classifier import (
    DEFAULT_MANIFEST,
    ClassifierError,
    changed_paths,
    classify,
    load_manifest,
    matches_rule,
    tracked_paths,
)


Result = dict[str, Any]
Runner = Callable[..., subprocess.CompletedProcess[str]]
ALLOWED_AUXILIARY = {
    "migration_validator": ["scripts/validate-migrations.py"],
    "policy_guardrails": ["scripts/policy_guardrails.py", "--strict", "--no-waivers"],
    "pii_storage_validator": ["scripts/validate-pii-storage.py"],
}


def aggregate_status(results: list[Result]) -> str:
    if not results:
        return "NOT_EVALUATED"
    statuses = {result["status"] for result in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "NOT_EVALUATED" in statuses:
        return "NOT_EVALUATED"
    return "PASS"


def _command_for(path: str, pytest_executable: str) -> list[str]:
    # Evidence paths are pytest modules and must be collected by pytest. Running
    # them as bare scripts executes no tests, so a file whose imports happen to
    # resolve would exit 0 and be recorded as evidence that never ran.
    return [pytest_executable, "-m", "pytest", "-q", path]


def manifest_self_check(*, root: Path, manifest: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Prove the manifest still describes surfaces and evidence that exist.

    Selection is driven entirely by path rules. A rule matching zero tracked
    files, an evidence command pointing at a deleted test, or an auxiliary
    evidence id with no backing script all produce a gate that cannot fail —
    which is indistinguishable from a gate that passed. Each is reported here as
    a configuration defect.
    """
    families = load_manifest(manifest)
    paths = tracked_paths(root)
    problems: list[dict[str, str]] = []
    for family in families:
        family_id = family["family_id"]
        for rule in family["path_rules"]:
            if not any(matches_rule(path, rule) for path in paths):
                problems.append({
                    "family_id": family_id,
                    "kind": "path_rule_matches_nothing",
                    "detail": rule,
                })
        for evidence_path in family.get("evidence_commands", []):
            if not (root / evidence_path).exists():
                problems.append({
                    "family_id": family_id,
                    "kind": "evidence_command_missing",
                    "detail": evidence_path,
                })
        for evidence_id in family.get("auxiliary_evidence", []):
            script = ALLOWED_AUXILIARY.get(evidence_id)
            if script is None:
                problems.append({
                    "family_id": family_id,
                    "kind": "auxiliary_evidence_unknown",
                    "detail": evidence_id,
                })
            elif not (root / script[0]).exists():
                problems.append({
                    "family_id": family_id,
                    "kind": "auxiliary_script_missing",
                    "detail": script[0],
                })
    return {
        "status": "PASS" if not problems else "FAIL",
        "tracked_path_count": len(paths),
        "problems": problems,
    }


def run_family(
    family: dict[str, Any],
    *,
    root: Path,
    pytest_executable: str,
    runner: Runner = subprocess.run,
) -> Result:
    commands = family.get("evidence_commands", [])
    auxiliary = family.get("auxiliary_evidence", [])
    base = {
        "family_id": family["family_id"],
        "mandatory": family["mandatory"],
        "governing_authority": family["governing_authority"],
    }
    if not commands and not auxiliary:
        return {**base, "status": "NOT_EVALUATED", "reason": "no sufficient evidence command is declared"}

    executions = []
    for evidence_path in commands:
        command = _command_for(evidence_path, pytest_executable)
        try:
            completed = runner(
                command,
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {**base, "status": "BLOCKED", "reason": str(exc), "executions": executions}
        execution = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        executions.append(execution)
        if completed.returncode != 0:
            return {**base, "status": "FAIL", "reason": "evidence command failed", "executions": executions}
    for evidence_id in auxiliary:
        script = ALLOWED_AUXILIARY.get(evidence_id)
        if script is None:
            return {**base, "status": "BLOCKED", "reason": f"unsupported auxiliary evidence: {evidence_id}", "executions": executions}
        command = [sys.executable, *script]
        try:
            completed = runner(command, cwd=root, text=True, capture_output=True, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return {**base, "status": "BLOCKED", "reason": str(exc), "executions": executions}
        executions.append({
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        })
        if completed.returncode != 0:
            return {**base, "status": "FAIL", "reason": "auxiliary evidence command failed", "executions": executions}
    return {**base, "status": "PASS", "executions": executions}


def execute_selection(
    selection: dict[str, Any],
    *,
    root: Path,
    pytest_executable: str,
    manifest: Path = DEFAULT_MANIFEST,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    if selection.get("status") != "SELECTED":
        raise ClassifierError("selection must have status SELECTED")
    families_by_id = {family["family_id"]: family for family in load_manifest(manifest)}
    results = []
    for selected in selection["selected_families"]:
        family = families_by_id.get(selected["family_id"])
        if family is None:
            results.append({"family_id": selected["family_id"], "status": "BLOCKED", "reason": "family missing from manifest"})
            continue
        results.append(run_family(family, root=root, pytest_executable=pytest_executable, runner=runner))
    return {
        "status": aggregate_status(results),
        "selection": selection,
        "family_results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--path", action="append", dest="paths")
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pytest", dest="pytest_executable", default=sys.executable)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Validate manifest path rules and evidence references, then exit.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.self_check:
        try:
            result = manifest_self_check(root=root, manifest=args.manifest)
        except (ClassifierError, OSError) as exc:
            result = {"status": "BLOCKED", "error": str(exc)}
        output = json.dumps(result, indent=2, sort_keys=True)
        print(output)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        return 0 if result["status"] == "PASS" else 1
    try:
        explicit = list(args.paths or [])
        if args.paths_file:
            explicit.extend(args.paths_file.read_text(encoding="utf-8").splitlines())
        paths = changed_paths(args.base, args.head, explicit if explicit else None)
        selection = classify(paths, args.manifest)
        result = execute_selection(
            selection,
            root=Path(__file__).resolve().parents[1],
            pytest_executable=args.pytest_executable,
            manifest=args.manifest,
        )
    except (ClassifierError, OSError) as exc:
        result = {"status": "BLOCKED", "error": str(exc)}
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
