#!/usr/bin/env python3
"""Content-registry static validator.

Walks templates + Python source and ensures every referenced content
key exists in the registry. Detects:

  MISSING   — a template or route calls help/help_long/help_text with a
              string-literal key that has no matching entry
  DUPLICATE — the same key is declared in more than one source file
  ORPHAN    — an entry exists but no code path references it

Exits non-zero on any MISSING or DUPLICATE. Orphans are reported as
warnings only (they represent copy that outlived a template rename).

This is the mechanism that makes the runtime missing-key fallback
exceptional rather than routine. Wire it into CI.

Usage:
    python scripts/validate_content_keys.py
    python scripts/validate_content_keys.py --allow-orphans
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


REPO_ROOT = Path.cwd()
CONTENT_ROOT = REPO_ROOT / "content"
TEMPLATE_ROOT = REPO_ROOT / "templates"
APP_ROOT = REPO_ROOT / "app"

# Function names whose first string-literal argument is a content key.
KEY_FUNCTIONS = {"help", "help_long", "help_text"}

# Jinja pattern for `help('key')` / `help_long("key", ...)` / `help_text('key')`.
JINJA_CALL_RE = re.compile(
    r"\b(help|help_long|help_text)\s*\(\s*['\"]([a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+)['\"]",
)


def _load_registry_keys() -> dict[str, str]:
    """Return {key: source_file} declared in content/. Detects duplicates."""
    import yaml

    keys: dict[str, str] = {}
    yaml_dir = CONTENT_ROOT / "help"
    md_root = CONTENT_ROOT / "help" / "long"

    if yaml_dir.is_dir():
        for yml in sorted(yaml_dir.glob("*.yaml")):
            with yml.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            src = str(yml.relative_to(REPO_ROOT))
            for k in data:
                if k in keys:
                    print(f"DUPLICATE: {k!r} in {keys[k]} and {src}", file=sys.stderr)
                    _dup_hits.append((k, keys[k], src))
                keys[k] = src

    if md_root.is_dir():
        for path in sorted(md_root.rglob("*.md")):
            rel = path.relative_to(md_root).with_suffix("")
            key = str(rel).replace("/", ".")
            src = str(path.relative_to(REPO_ROOT))
            if key in keys:
                print(f"DUPLICATE: {key!r} in {keys[key]} and {src}", file=sys.stderr)
                _dup_hits.append((key, keys[key], src))
            keys[key] = src

    return keys


_dup_hits: list[tuple[str, str, str]] = []


def _find_python_references() -> list[tuple[str, str, int]]:
    """Return [(key, file, line), ...] found in .py sources via AST."""
    refs: list[tuple[str, str, int]] = []
    for py in APP_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        rel = str(py.relative_to(REPO_ROOT))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # match help(...), help_text(...), help_long(...) — attribute
            # access (obj.help(...)) is skipped to avoid false positives.
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name not in KEY_FUNCTIONS:
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                refs.append((first.value, rel, node.lineno))
    return refs


def _find_template_references() -> list[tuple[str, str, int]]:
    """Return [(key, file, line), ...] found in Jinja templates via regex."""
    refs: list[tuple[str, str, int]] = []
    if not TEMPLATE_ROOT.is_dir():
        return refs
    for tpl in TEMPLATE_ROOT.rglob("*.html"):
        rel = str(tpl.relative_to(REPO_ROOT))
        for lineno, line in enumerate(tpl.read_text(encoding="utf-8").splitlines(), start=1):
            for m in JINJA_CALL_RE.finditer(line):
                refs.append((m.group(2), rel, lineno))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-orphans",
        action="store_true",
        help="Do not treat orphan entries (declared but unreferenced) as errors",
    )
    args = parser.parse_args()

    keys = _load_registry_keys()
    py_refs = _find_python_references()
    tpl_refs = _find_template_references()
    all_refs = py_refs + tpl_refs

    missing = [(k, src, ln) for (k, src, ln) in all_refs if k not in keys]
    referenced = {k for (k, _, _) in all_refs}
    orphans = sorted(set(keys) - referenced)

    print(f"content-registry: {len(keys)} entries, {len(all_refs)} references "
          f"({len(py_refs)} py + {len(tpl_refs)} jinja)")

    if missing:
        print(f"\nMISSING ({len(missing)}):", file=sys.stderr)
        for k, src, ln in sorted(missing):
            print(f"  {src}:{ln}  {k}", file=sys.stderr)

    if _dup_hits:
        print(f"\nDUPLICATE ({len(_dup_hits)}):", file=sys.stderr)
        for k, a, b in _dup_hits:
            print(f"  {k}  ({a} + {b})", file=sys.stderr)

    if orphans:
        header = "ORPHAN" if args.allow_orphans else "ORPHAN (error — use --allow-orphans to warn only)"
        print(f"\n{header} ({len(orphans)}):", file=sys.stderr)
        for k in orphans:
            print(f"  {k}  ({keys[k]})", file=sys.stderr)

    if missing or _dup_hits or (orphans and not args.allow_orphans):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
