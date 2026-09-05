#!/usr/bin/env python3
"""Select invariant evidence families for a changed repository surface.

This is selection infrastructure only. It never converts missing evidence into
PASS. A configuration or change-discovery failure returns BLOCKED.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / ".ci" / "invariant_families.yml"
VALID_KINDS = {"static", "runtime", "persistence", "browser"}
REQUIRED_FIELDS = {
    "family_id", "governing_authority", "path_rules", "evidence_kind",
    "evidence_commands", "mandatory", "pass_contract", "known_limits",
}


class ClassifierError(ValueError):
    """Manifest or input cannot produce trustworthy selection output."""


def load_manifest(path: Path = DEFAULT_MANIFEST) -> list[dict[str, Any]]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ClassifierError(f"cannot load manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ClassifierError("manifest version must be 1")
    families = payload.get("families")
    if not isinstance(families, list) or not families:
        raise ClassifierError("manifest families must be a non-empty list")
    seen: set[str] = set()
    for family in families:
        if not isinstance(family, dict) or set(family) < REQUIRED_FIELDS:
            raise ClassifierError("each family must contain every required field")
        family_id = family["family_id"]
        if not isinstance(family_id, str) or not family_id or family_id in seen:
            raise ClassifierError(f"duplicate or invalid family_id: {family_id!r}")
        seen.add(family_id)
        if not isinstance(family["governing_authority"], list) or not family["governing_authority"]:
            raise ClassifierError(f"{family_id}: governing_authority must be non-empty")
        if not isinstance(family["path_rules"], list) or not family["path_rules"]:
            raise ClassifierError(f"{family_id}: path_rules must be non-empty")
        if not all(isinstance(rule, str) and rule for rule in family["path_rules"]):
            raise ClassifierError(f"{family_id}: path_rules must contain strings")
        kinds = family["evidence_kind"]
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= VALID_KINDS:
            raise ClassifierError(f"{family_id}: invalid evidence_kind")
        if not isinstance(family["evidence_commands"], list):
            raise ClassifierError(f"{family_id}: evidence_commands must be a list")
        auxiliary = family.get("auxiliary_evidence", [])
        if not isinstance(auxiliary, list) or not all(isinstance(item, str) and item for item in auxiliary):
            raise ClassifierError(f"{family_id}: auxiliary_evidence must contain string IDs")
        if not isinstance(family["mandatory"], bool):
            raise ClassifierError(f"{family_id}: mandatory must be boolean")
    return families


def changed_paths(base: str | None, head: str, explicit: list[str] | None = None) -> list[str]:
    if explicit is not None:
        paths = sorted({path.strip().lstrip("./") for path in explicit if path.strip()})
        if not paths:
            raise ClassifierError("explicit changed path list is empty")
        return paths
    if not base:
        raise ClassifierError("base revision or explicit changed paths is required")
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ClassifierError(f"cannot resolve changed paths: {result.stderr.strip()}")
    paths = sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})
    if not paths:
        raise ClassifierError("changed path discovery produced no paths")
    return paths


def matches_rule(path: str, rule: str) -> bool:
    return fnmatch.fnmatchcase(path, rule) or fnmatch.fnmatchcase(path, rule.rstrip("/") + "/**")


def tracked_paths(root: Path = ROOT) -> list[str]:
    """Every path tracked at the current revision.

    Used to prove that each manifest path rule still selects a real surface. A
    rule that matches nothing is indistinguishable from a satisfied gate, so it
    must be discoverable as a configuration defect rather than silently
    requiring no evidence.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ClassifierError(f"cannot list tracked paths: {result.stderr.strip()}")
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not paths:
        raise ClassifierError("tracked path discovery produced no paths")
    return paths


def select_families(paths: list[str], families: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = sorted({path.strip().lstrip("./") for path in paths if path.strip()})
    if not normalized:
        raise ClassifierError("cannot classify an empty path list")
    selected: dict[str, dict[str, Any]] = {}
    for family in families:
        matches = [path for path in normalized if any(matches_rule(path, rule) for rule in family["path_rules"])]
        if matches:
            selected[family["family_id"]] = {
                "family_id": family["family_id"],
                "mandatory": family["mandatory"],
                "governing_authority": family["governing_authority"],
                "evidence_kind": family["evidence_kind"],
                "evidence_commands": family["evidence_commands"],
                "matched_paths": matches,
                "selection_status": "SELECTED",
            }
    path_set = set(normalized)
    if any(path.startswith("migrations/") or path in {"app/models.py"} for path in path_set):
        for family in families:
            if family["family_id"] in {"CI-PERSIST", "CI-PII", "CI-VALIDATION"}:
                selected.setdefault(family["family_id"], {
                    "family_id": family["family_id"], "mandatory": family["mandatory"],
                    "governing_authority": family["governing_authority"], "evidence_kind": family["evidence_kind"],
                    "evidence_commands": family["evidence_commands"], "matched_paths": [],
                    "selection_status": "SELECTED_EVENT_WIDE",
                })
    if not selected:
        for family in families:
            if family["family_id"] in {"CI-ARC-EXEC", "CI-SCOPE", "CI-VALIDATION"}:
                selected.setdefault(family["family_id"], {
                    "family_id": family["family_id"], "mandatory": family["mandatory"],
                    "governing_authority": family["governing_authority"], "evidence_kind": family["evidence_kind"],
                    "evidence_commands": family["evidence_commands"], "matched_paths": [],
                    "selection_status": "SELECTED_UNKNOWN_PATH",
                })
    return [selected[key] for key in sorted(selected)]


def classify(paths: list[str], manifest: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    families = load_manifest(manifest)
    selected = select_families(paths, families)
    selected_ids = {family["family_id"] for family in selected}
    return {
        # Selection is not evidence execution and must never be reported as a
        # constitutional PASS. Family runners determine PASS/FAIL/
        # NOT_EVALUATED/BLOCKED after this output is consumed.
        "status": "SELECTED",
        "paths": sorted({path.strip().lstrip("./") for path in paths if path.strip()}),
        "selected_families": selected,
        "unselected_families": [
            {"family_id": family["family_id"], "status": "NOT_APPLICABLE"}
            for family in families if family["family_id"] not in selected_ids
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--path", action="append", dest="paths")
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        explicit = list(args.paths or [])
        if args.paths_file:
            explicit.extend(args.paths_file.read_text(encoding="utf-8").splitlines())
        paths = changed_paths(args.base, args.head, explicit if explicit else None)
        result = classify(paths, args.manifest)
    except (ClassifierError, OSError) as exc:
        result = {"status": "BLOCKED", "error": str(exc)}
        output = json.dumps(result, indent=2, sort_keys=True)
        print(output)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        return 2
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
