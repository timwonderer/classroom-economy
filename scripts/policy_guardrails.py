#!/usr/bin/env python3
"""Repository policy guardrails for v2 architecture compliance.

Usage:
  python scripts/policy_guardrails.py
  python scripts/policy_guardrails.py --strict
  python scripts/policy_guardrails.py --strict --no-waivers

Waiver format (same line or previous line):
  # CI-WAIVER:<RULE_ID> ticket=<TICKET> expires=YYYY-MM-DD reason="..."
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

WAIVER_RE = re.compile(
    r"CI-WAIVER:(?P<rule>[A-Z0-9_-]+)\\s+ticket=(?P<ticket>\\S+)\\s+expires=(?P<expires>\\d{4}-\\d{2}-\\d{2})(?:\\s+reason=.*)?"
)


@dataclass
class Finding:
    rule: str
    path: pathlib.Path
    line: int
    message: str


@dataclass
class Waiver:
    rule: str
    ticket: str
    expires: dt.date
    path: pathlib.Path
    line: int


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Reserved mode for future escalation; violations already fail by default",
    )
    ap.add_argument("--no-waivers", action="store_true", help="Disallow waivers entirely")
    ap.add_argument("--git-diff-base", help="Only scan files changed since this git ref/SHA")
    ap.add_argument("--git-diff-head", default="HEAD", help="Diff head ref/SHA (default: HEAD)")
    return ap.parse_args()


def load_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_py_files(diff_base: str | None, diff_head: str) -> list[pathlib.Path]:
    if not diff_base:
        return sorted(APP_DIR.rglob("*.py"))

    cmd = ["git", "diff", "--name-only", f"{diff_base}...{diff_head}"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(f"[policy-guardrails] failed to resolve git diff ({' '.join(cmd)}), scanning full app/", file=sys.stderr)
        return sorted(APP_DIR.rglob("*.py"))

    files: list[pathlib.Path] = []
    for raw in result.stdout.splitlines():
        if not raw.endswith(".py"):
            continue
        p = ROOT / raw
        if p.is_file() and p.is_relative_to(APP_DIR):
            files.append(p)
    return sorted(set(files))


def changed_line_map(diff_base: str | None, diff_head: str) -> dict[pathlib.Path, set[int]] | None:
    if not diff_base:
        return None
    cmd = ["git", "diff", "--unified=0", "--no-color", f"{diff_base}...{diff_head}", "--", "app/"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(f"[policy-guardrails] failed to read changed lines ({' '.join(cmd)}), using full-file checks", file=sys.stderr)
        return None

    line_map: dict[pathlib.Path, set[int]] = {}
    current_path: pathlib.Path | None = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")
    new_file_re = re.compile(r"^\+\+\+ b/(?P<path>.+)$")
    for line in result.stdout.splitlines():
        mfile = new_file_re.match(line)
        if mfile:
            path = ROOT / mfile.group("path")
            current_path = path if path.is_relative_to(APP_DIR) else None
            continue
        mhunk = hunk_re.match(line)
        if mhunk and current_path is not None:
            start = int(mhunk.group("start"))
            count = int(mhunk.group("count") or "1")
            if count <= 0:
                continue
            bucket = line_map.setdefault(current_path, set())
            bucket.update(range(start, start + count))
    return line_map


def collect_waivers(path: pathlib.Path, text: str) -> dict[int, Waiver]:
    by_line: dict[int, Waiver] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        m = WAIVER_RE.search(line)
        if not m:
            continue
        try:
            expires = dt.date.fromisoformat(m.group("expires"))
        except ValueError:
            continue
        by_line[i] = Waiver(
            rule=m.group("rule"),
            ticket=m.group("ticket"),
            expires=expires,
            path=path,
            line=i,
        )
    return by_line


def has_valid_waiver(f: Finding, waivers: dict[int, Waiver], no_waivers: bool) -> tuple[bool, str | None]:
    if no_waivers:
        return False, None
    today = dt.date.today()
    for ln in (f.line, f.line - 1):
        w = waivers.get(ln)
        if not w:
            continue
        if w.rule != f.rule:
            continue
        if w.expires < today:
            return False, f"expired waiver {w.ticket} ({w.expires.isoformat()})"
        return True, None
    return False, None


def route_functions_with_get_only(tree: ast.AST) -> set[str]:
    names: set[str] = set()

    def dec_is_route(dec: ast.expr) -> tuple[bool, bool]:
        # returns (is_route, get_only)
        if not isinstance(dec, ast.Call):
            return False, False
        f = dec.func
        if not (isinstance(f, ast.Attribute) and f.attr == "route"):
            return False, False
        methods_kw = None
        for kw in dec.keywords:
            if kw.arg == "methods":
                methods_kw = kw.value
                break
        if methods_kw is None:
            return True, True  # default GET
        if isinstance(methods_kw, (ast.List, ast.Tuple)):
            vals = []
            for elt in methods_kw.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    vals.append(elt.value.upper())
            return True, set(vals) <= {"GET"}
        return True, False

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        get_only = False
        any_route = False
        for dec in node.decorator_list:
            is_route, is_get_only = dec_is_route(dec)
            any_route = any_route or is_route
            get_only = get_only or (is_route and is_get_only)
        if any_route and get_only:
            names.add(node.name)
    return names


def call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        parts = []
        cur = call.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def line_of(node: ast.AST) -> int:
    return getattr(node, "lineno", 1)


def check_route_commit(path: pathlib.Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if "/routes/" not in str(path):
        return findings
    for i, line in enumerate(text.splitlines(), start=1):
        if "db.session.commit(" in line:
            findings.append(Finding("NO_ROUTE_COMMIT", path, i, "Route-level db.session.commit() detected"))
    return findings


def check_write_on_get(path: pathlib.Path, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    if "/routes/" not in str(path):
        return findings
    get_only = route_functions_with_get_only(tree)
    mutator_prefixes = (
        "db.session.add",
        "db.session.delete",
        "db.session.commit",
        "db.session.execute",
        "process_expired_collective_goals",
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in get_only:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                nm = call_name(sub)
                if any(nm.startswith(pref) for pref in mutator_prefixes):
                    findings.append(Finding(
                        "NO_WRITE_ON_GET",
                        path,
                        line_of(sub),
                        f"GET handler '{node.name}' calls mutator '{nm}'",
                    ))
    return findings


def check_scope_fallback(path: pathlib.Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if "/routes/" not in str(path):
        return findings
    patterns = [
        r"except\s+HTTPException[\s\S]{0,320}?_resolve_admin_class_context\(",
        r"except\s+HTTPException[\s\S]{0,320}?resolve_class_scope\(",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append(Finding("NO_SCOPE_FALLBACK", path, line, "Scope fallback detected in HTTPException path"))
    return findings


def check_student_context_fallback(path: pathlib.Path, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    if rel(path) != "app/routes/student.py":
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_current_class_context":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    nm = call_name(sub)
                    if nm == "session.get" and sub.args and isinstance(sub.args[0], ast.Constant) and sub.args[0].value == "current_join_code":
                        findings.append(Finding(
                            "NO_LEGACY_CONTEXT_FALLBACK",
                            path,
                            line_of(sub),
                            "get_current_class_context() reads session.current_join_code",
                        ))
    return findings




def check_tap_event_null_scope(path: pathlib.Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if rel(path) != "app/models.py":
        return findings
    if "class TapEvent" not in text:
        return findings
    lines = text.splitlines()
    in_tap_event = False
    for i, line in enumerate(lines, start=1):
        if line.startswith("class TapEvent"):
            in_tap_event = True
            continue
        if in_tap_event and line.startswith("class ") and not line.startswith("class TapEvent"):
            break
        if not in_tap_event:
            continue
        norm = line.replace(" ", "")
        if norm.startswith("class_id=db.Column(") and "nullable=True" in norm:
            findings.append(Finding("TAP_SCOPE_NONNULL", path, i, "TapEvent.class_id must not be nullable"))
        if norm.startswith("seat_id=db.Column(") and "nullable=True" in norm:
            findings.append(Finding("TAP_SCOPE_NONNULL", path, i, "TapEvent.seat_id must not be nullable"))
    return findings


_AUDIT_EVENT_MUTATE_RE = re.compile(r"\bAuditEvent\s*\.\s*query\s*\.\s*(update|delete)\s*\(")
_LINEAGE_TOKEN_ASSIGN_RE = re.compile(r"\blineage_token\s*=")
_EMIT_AUDIT_CALL_RE = re.compile(r"\bemit_audit_event\s*\(")

# Tables treated as class-scoped by the audit system
_CLASS_SCOPED_AUDIT_TABLES = {
    "transaction", "ledger_transaction", "payroll_settings", "rent_settings",
    "banking_settings", "feature_settings", "hall_pass_settings",
}
# Paths where direct lineage token assignment is legitimate
_LINEAGE_TOKEN_ALLOWLIST = {
    "app/feats/base.py",
    "app/services/audit_service.py",
}


def check_no_audit_update_delete(path: pathlib.Path, text: str) -> list[Finding]:
    """Detect AuditEvent.query.update/delete calls anywhere in app/."""
    if "app" not in path.parts:
        return []
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        if _AUDIT_EVENT_MUTATE_RE.search(line):
            findings.append(Finding(
                "NO_AUDIT_UPDATE_DELETE", path, i,
                "AuditEvent rows must never be updated or deleted via application code"
            ))
    return findings


def check_no_lineage_backfill_on_read(path: pathlib.Path, tree: ast.AST, text: str) -> list[Finding]:
    """Flag emit_audit_event() calls inside GET route handlers."""
    if not str(path).endswith(".py"):
        return []
    if "routes" not in path.parts:
        return []

    findings = []
    lines = text.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # Check for Flask GET method decorator
        is_get_only = False
        for dec in node.decorator_list:
            dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if "methods" in dec_src and "GET" in dec_src and "POST" not in dec_src:
                is_get_only = True
                break
            # route with no methods= defaults to GET only
            if ".route(" in dec_src and "methods" not in dec_src:
                is_get_only = True
                break

        if not is_get_only:
            continue

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                func_name = (
                    func.id if isinstance(func, ast.Name) else
                    func.attr if isinstance(func, ast.Attribute) else ""
                )
                if func_name == "emit_audit_event":
                    findings.append(Finding(
                        "NO_LINEAGE_BACKFILL_ON_READ", path, child.lineno,
                        "emit_audit_event must not be called inside a GET route handler"
                    ))
    return findings


def check_no_direct_lineage_token_assignment(path: pathlib.Path, text: str) -> list[Finding]:
    """Flag direct lineage_token = ... assignments outside allowlisted paths."""
    rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
    if any(rel_path.endswith(allowed) for allowed in _LINEAGE_TOKEN_ALLOWLIST):
        return []
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        # Skip SQLAlchemy column declarations (model definitions, not runtime assignments)
        if "db.Column" in line or "sa.Column" in line:
            continue
        if _LINEAGE_TOKEN_ASSIGN_RE.search(line):
            findings.append(Finding(
                "NO_DIRECT_LINEAGE_TOKEN_ASSIGNMENT", path, i,
                "lineage_token must only be written by audit_service.py or feats/base.py"
            ))
    return findings


def check_no_unscoped_audit_emit(path: pathlib.Path, tree: ast.AST, text: str) -> list[Finding]:
    """Flag emit_audit_event() calls for class-scoped tables that omit class_id=."""
    if "audit_service" in str(path):
        return []  # the service itself is exempt

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Call,)):
            continue
        func = node.func
        func_name = (
            func.id if isinstance(func, ast.Name) else
            func.attr if isinstance(func, ast.Attribute) else ""
        )
        if func_name != "emit_audit_event":
            continue

        # Check if table_name arg refers to a class-scoped table
        table_name_val: str | None = None
        if node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                table_name_val = arg0.value
        for kw in node.keywords:
            if kw.arg == "table_name" and isinstance(kw.value, ast.Constant):
                table_name_val = kw.value.value

        if table_name_val not in _CLASS_SCOPED_AUDIT_TABLES:
            continue

        # Verify class_id= keyword is present
        has_class_id = any(kw.arg == "class_id" for kw in node.keywords)
        if not has_class_id:
            findings.append(Finding(
                "NO_UNSCOPED_AUDIT_EMIT", path, node.lineno,
                f"emit_audit_event for class-scoped table '{table_name_val}' must include class_id="
            ))
    return findings


def run_checks(no_waivers: bool, diff_base: str | None, diff_head: str) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    warnings: list[str] = []
    line_map = changed_line_map(diff_base=diff_base, diff_head=diff_head)

    for path in collect_py_files(diff_base=diff_base, diff_head=diff_head):
        text = load_text(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append(Finding("PY_SYNTAX", path, exc.lineno or 1, f"SyntaxError: {exc.msg}"))
            continue

        path_findings = []
        path_findings.extend(check_route_commit(path, text))
        path_findings.extend(check_write_on_get(path, tree))
        path_findings.extend(check_scope_fallback(path, text))
        path_findings.extend(check_student_context_fallback(path, tree))
        path_findings.extend(check_tap_event_null_scope(path, text))
        path_findings.extend(check_no_audit_update_delete(path, text))
        path_findings.extend(check_no_lineage_backfill_on_read(path, tree, text))
        path_findings.extend(check_no_direct_lineage_token_assignment(path, text))
        path_findings.extend(check_no_unscoped_audit_emit(path, tree, text))

        waivers = collect_waivers(path, text)
        if line_map is not None:
            path_changed_lines = line_map.get(path, set())
        else:
            path_changed_lines = None
        for f in path_findings:
            if path_changed_lines is not None and f.line not in path_changed_lines:
                continue
            ok, waiver_msg = has_valid_waiver(f, waivers, no_waivers=no_waivers)
            if ok:
                warnings.append(f"WAIVED {f.rule} {rel(f.path)}:{f.line}")
                continue
            if waiver_msg:
                findings.append(Finding(f.rule, f.path, f.line, f"{f.message} ({waiver_msg})"))
            else:
                findings.append(f)

    return findings, warnings


def main() -> int:
    args = parse_args()
    findings, warnings = run_checks(
        no_waivers=args.no_waivers,
        diff_base=args.git_diff_base,
        diff_head=args.git_diff_head,
    )

    if warnings:
        print("Policy waivers:")
        for w in warnings:
            print(f"  - {w}")

    if findings:
        print("Policy violations:")
        for f in findings:
            print(f"  - [{f.rule}] {rel(f.path)}:{f.line} {f.message}")
        print(f"Total violations: {len(findings)}")
        return 1

    print("Policy guardrails: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
