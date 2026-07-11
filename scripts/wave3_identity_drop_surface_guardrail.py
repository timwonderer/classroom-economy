#!/usr/bin/env python3
"""Guardrail for Wave 3 deferred identity-table drops.

Tracks where legacy auth symbols/session principals are still referenced and
fails when the reference surface expands beyond a checked-in baseline.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DEFAULT_BASELINE = ROOT / "docs/TRACKING/wave3_identity_drop_surface_baseline.json"

EXCLUDED_PATHS = {
    "app/models.py",
    "app/models_canonical.py",
}

LEGACY_IDENTITY_SYMBOLS = (
    "Admin",
    "Student",
    "TeacherBlock",
    "StudentTeacher",
    "StudentBlock",
    "RecoveryRequest",
    "StudentRecoveryCode",
    "TeacherOnboarding",
    "AdminInviteCode",
)

LEGACY_SESSION_KEYS = (
    "admin_id",
    "student_id",
    "is_admin",
    "is_system_admin",
)

SESSION_CALL_METHODS = {
    "get",
    "pop",
    "setdefault",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help=f"Baseline JSON path (default: {DEFAULT_BASELINE})",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write current surface to baseline path and exit 0.",
    )
    parser.add_argument(
        "--show-current",
        action="store_true",
        help="Print the current surface JSON to stdout.",
    )
    return parser.parse_args()


def relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _slice_to_key(node: ast.Subscript) -> str | None:
    raw = node.slice
    if isinstance(raw, ast.Constant) and isinstance(raw.value, str):
        return raw.value
    index_node_type = getattr(ast, "Index", None)
    if index_node_type and isinstance(raw, index_node_type):  # pragma: no cover (py<3.9)
        if isinstance(raw.value, ast.Constant) and isinstance(raw.value.value, str):
            return raw.value.value
    return None


def _first_arg_as_str(node: ast.Call) -> str | None:
    if not node.args:
        return None
    arg0 = node.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return arg0.value
    return None


class SurfaceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbol_hits: set[str] = set()
        self.session_key_hits: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module == "app.models":
            for alias in node.names:
                name = alias.name
                if name in LEGACY_IDENTITY_SYMBOLS:
                    self.symbol_hits.add(name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id in LEGACY_IDENTITY_SYMBOLS:
            self.symbol_hits.add(node.id)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        if isinstance(node.value, ast.Name) and node.value.id == "session":
            key = _slice_to_key(node)
            if key in LEGACY_SESSION_KEYS:
                self.session_key_hits.add(key)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "session" and node.func.attr in SESSION_CALL_METHODS:
                key = _first_arg_as_str(node)
                if key in LEGACY_SESSION_KEYS:
                    self.session_key_hits.add(key)
        self.generic_visit(node)


def _empty_surface() -> dict[str, dict[str, list[str]]]:
    return {
        "symbols": {name: [] for name in LEGACY_IDENTITY_SYMBOLS},
        "session_keys": {key: [] for key in LEGACY_SESSION_KEYS},
    }


def collect_surface() -> dict[str, dict[str, list[str]]]:
    surface = _empty_surface()
    symbol_files: dict[str, set[str]] = {name: set() for name in LEGACY_IDENTITY_SYMBOLS}
    session_files: dict[str, set[str]] = {key: set() for key in LEGACY_SESSION_KEYS}

    for path in sorted(APP_DIR.rglob("*.py")):
        rp = relpath(path)
        if rp in EXCLUDED_PATHS:
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rp)
        visitor = SurfaceVisitor()
        visitor.visit(tree)

        for symbol in visitor.symbol_hits:
            symbol_files[symbol].add(rp)
        for key in visitor.session_key_hits:
            session_files[key].add(rp)

    for symbol, files in symbol_files.items():
        surface["symbols"][symbol] = sorted(files)
    for key, files in session_files.items():
        surface["session_keys"][key] = sorted(files)
    return surface


def _load_baseline(path: Path) -> dict[str, dict[str, list[str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Baseline must be a JSON object")
    for section in ("symbols", "session_keys"):
        if section not in payload or not isinstance(payload[section], dict):
            raise ValueError(f"Baseline missing '{section}' mapping")
    return payload


def compare_surface(
    baseline: dict[str, dict[str, list[str]]],
    current: dict[str, dict[str, list[str]]],
) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    reductions: list[str] = []
    for section in ("symbols", "session_keys"):
        keys = sorted(set(baseline.get(section, {}).keys()) | set(current.get(section, {}).keys()))
        for key in keys:
            baseline_files = set(baseline.get(section, {}).get(key, []))
            current_files = set(current.get(section, {}).get(key, []))
            added = sorted(current_files - baseline_files)
            removed = sorted(baseline_files - current_files)
            if added:
                violations.append(f"{section}.{key} expanded into: {', '.join(added)}")
            if removed:
                reductions.append(f"{section}.{key} reduced from: {', '.join(removed)}")
    return violations, reductions


def main() -> int:
    args = parse_args()
    current = collect_surface()

    if args.show_current:
        print(json.dumps(current, indent=2, sort_keys=True))

    baseline_path = args.baseline
    if args.write_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote baseline: {baseline_path.relative_to(ROOT)}")
        return 0

    if not baseline_path.exists():
        print(
            f"Baseline not found: {baseline_path.relative_to(ROOT)}. "
            "Run with --write-baseline to create it.",
            file=sys.stderr,
        )
        return 1

    baseline = _load_baseline(baseline_path)
    violations, reductions = compare_surface(baseline=baseline, current=current)

    if violations:
        print("Wave 3 identity-drop surface guardrail violations:")
        for line in violations:
            print(f"  - {line}")
        if reductions:
            print("Observed reductions:")
            for line in reductions:
                print(f"  - {line}")
        return 1

    print("Wave 3 identity-drop surface guardrail: clean (no expansion)")
    if reductions:
        print("Observed reductions:")
        for line in reductions:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
