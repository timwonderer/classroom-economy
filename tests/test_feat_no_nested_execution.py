"""Structural guard: a FEAT executor may not invoke another FEAT executor.

INV-ARC-000 §VIII.2 (exactly one command path per request) and INV-ARC-021 §V.2
(the FEAT is the sole composition layer, within a single execution path) forbid
FEAT-to-FEAT execution. A FEAT composes DOMAIN commands (services/guards/queries/
plain domain functions), never another FEAT. There is NO Core-FEAT allowlist.

Static/AST check so the violation is caught at author-time, before any
correlation-ID coincidence could hide it at runtime. Complements the runtime guard.

Rule: no module under app/feats/ (except package __init__.py re-exports) may IMPORT
a symbol from ANOTHER app.feats module when that symbol is a FEAT executor there (a
function decorated @requires_feat_context). You cannot call what you may not import.
"""

from __future__ import annotations

import ast
from pathlib import Path

FEATS_DIR = Path(__file__).resolve().parents[1] / "app" / "feats"


def _module_name(path: Path) -> str:
    rel = path.relative_to(FEATS_DIR.parents[1]).with_suffix("")
    return ".".join(rel.parts)


def _executor_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Name) and target.id == "requires_feat_context":
                    names.add(node.name)
                elif isinstance(target, ast.Attribute) and target.attr == "requires_feat_context":
                    names.add(node.name)
    return names


def test_no_feat_module_imports_another_feats_executor():
    files = [p for p in FEATS_DIR.rglob("*.py") if p.name != "__init__.py"]
    trees = {p: ast.parse(p.read_text()) for p in files}
    executors_by_module = {_module_name(p): _executor_names(t) for p, t in trees.items()}

    violations: list[str] = []
    for path, tree in trees.items():
        this_module = _module_name(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            src = node.module
            if not src.startswith("app.feats") or src == this_module:
                continue
            src_execs = executors_by_module.get(src, set())
            for alias in node.names:
                if alias.name in src_execs:
                    violations.append(
                        f"{path.relative_to(FEATS_DIR.parents[1])}: imports FEAT executor "
                        f"'{alias.name}' from '{src}' (FEAT->FEAT execution is forbidden; "
                        f"call the domain command instead)."
                    )

    assert not violations, (
        "FEAT-to-FEAT execution detected (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2):\n"
        + "\n".join(violations)
    )
