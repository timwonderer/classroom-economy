#!/usr/bin/env python3
"""
Comprehensive migration validation script.

Validates migration files for:
1. Continuous revision chain (no gaps)
2. Single head (no multiple heads)
3. All migrations have upgrade/downgrade functions
4. Idempotency and production safety patterns

Usage:
    python scripts/validate-migrations.py

Returns:
    Exit code 0 if validation passes
    Exit code 1 if critical issues found
"""
import ast
import re
import sys
from pathlib import Path
from collections import defaultdict

# Adjust path for running from project root
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"


def extract_migration_info(filepath):
    """Extract revision info from a migration file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None

    # Extract revision
    revision_match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
    revision = revision_match.group(1) if revision_match else None

    # Extract down_revision (can be None, a string, or a tuple)
    down_rev_match = re.search(r"^down_revision\s*=\s*(.+)$", content, re.MULTILINE)
    if down_rev_match:
        down_rev_raw = down_rev_match.group(1).strip()
        if down_rev_raw == 'None':
            down_revision = None
        else:
            # Use ast.literal_eval for robust parsing (consistent with other scripts)
            try:
                down_revision = ast.literal_eval(down_rev_raw)
            except (ValueError, SyntaxError):
                # Fallback to regex extraction if literal_eval fails
                if down_rev_raw.startswith('('):
                    # Tuple case - merge migration
                    tuples = re.findall(r"['\"]([^'\"]+)['\"]", down_rev_raw)
                    down_revision = tuple(tuples) if tuples else None
                else:
                    # Single string case
                    single = re.search(r"['\"]([^'\"]+)['\"]", down_rev_raw)
                    down_revision = single.group(1) if single else None
    else:
        down_revision = "MISSING"

    if tree is not None:
        defined_functions = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        has_upgrade = 'upgrade' in defined_functions
        has_downgrade = 'downgrade' in defined_functions
    else:
        # Fallback for invalid syntax files
        has_upgrade = bool(re.search(r"^def upgrade\s*\(\s*\)\s*:", content, re.MULTILINE))
        has_downgrade = bool(re.search(r"^def downgrade\s*\(\s*\)\s*:", content, re.MULTILINE))

    return {
        'filepath': filepath,
        'filename': filepath.name,
        'revision': revision,
        'down_revision': down_revision,
        'has_upgrade': has_upgrade,
        'has_downgrade': has_downgrade,
    }


def check_idempotency(filepath):
    """
    Check if migration operations are guarded by existence checks.

    Returns a list of error strings.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [f"Syntax error parsing {filepath.name}"]

    errors = []
    
    # Helper to find if a node is inside an If block
    def is_guarded(node, parents):
        # Check parents in reverse order
        for parent in reversed(parents):
            if isinstance(parent, ast.If):
                return True
        return False

    # Walk the tree with parent tracking
    for node in ast.walk(tree):
        # We manually track parents by checking children, but ast.walk doesn't give context.
        # So we'll use a NodeVisitor instead.
        pass

    class IdempotencyVisitor(ast.NodeVisitor):
        def __init__(self):
            self.errors = []
            self.parents = []
            self.created_tables = set()

        def _extract_string_arg(self, node, position=0, keyword_name=None):
            if keyword_name:
                for keyword in node.keywords:
                    if keyword.arg == keyword_name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                        return keyword.value.value
            if len(node.args) > position:
                arg = node.args[position]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value
            return None

        def visit_Call(self, node):
            # Check for op.method calls
            if isinstance(node.func, ast.Attribute) and \
               isinstance(node.func.value, ast.Name) and \
               node.func.value.id == 'op':
                
                method = node.func.attr

                if method == 'create_table':
                    table_name = self._extract_string_arg(node, position=0)
                    if table_name:
                        self.created_tables.add(table_name)
                
                # Critical operations that need guards
                if method in ['add_column', 'create_foreign_key', 'create_index']:
                    if not self.is_guarded() and not self.is_safe_creation_call(method, node):
                        self.errors.append(f"❌ Unguarded {method}() in {filepath.name}. Must be inside an 'if' block checking existence.")
                
                # Warnings for raw execution
                if method == 'execute':
                    self.errors.append(f"⚠️  Manual SQL execution detected: op.execute() in {filepath.name}. Verify idempotency manually.")

            # Continue visiting children
            self.generic_visit(node)

        def is_guarded(self):
            for parent in reversed(self.parents):
                if isinstance(parent, ast.If):
                    return True
            return False

        def is_safe_creation_call(self, method, node):
            if method == 'create_index':
                table_name = self._extract_string_arg(node, position=1, keyword_name='table_name')
                return table_name in self.created_tables
            if method == 'create_foreign_key':
                source_table = self._extract_string_arg(node, position=1, keyword_name='source_table')
                return source_table in self.created_tables
            return False

        def visit_If(self, node):
            self.parents.append(node)
            self.generic_visit(node)
            self.parents.pop()

        def visit_FunctionDef(self, node):
            self.parents.append(node)
            self.generic_visit(node)
            self.parents.pop()

    visitor = IdempotencyVisitor()
    visitor.visit(tree)
    
    return visitor.errors


def check_redemption_audit_log_safety(filepath):
    """
    Enforce append-only migration guardrails for redemption_audit_logs.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lower_content = content.lower()
    errors = []

    # Block raw SQL touching redemption_audit_logs entirely.
    if "op.execute" in lower_content and "redemption_audit_logs" in lower_content:
        errors.append(
            f"❌ Forbidden raw SQL on redemption_audit_logs in {filepath.name}. "
            "Use structured Alembic operations and avoid op.execute for this table."
        )

    destructive_patterns = [
        r"op\.drop_table\(\s*['\"]redemption_audit_logs['\"]",
        r"op\.drop_column\(\s*['\"]redemption_audit_logs['\"]",
        r"op\.alter_column\(\s*['\"]redemption_audit_logs['\"]",
    ]
    for pattern in destructive_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(
                f"❌ Forbidden non-append migration operation on redemption_audit_logs in {filepath.name}."
            )

    return errors

# List of legacy migrations that are known to violate new idempotency rules
# (unguarded add_column/create_index). These are whitelisted to prevent CI failure.
LEGACY_MIGRATIONS = {
    '0002a_rename_class_economies.py',
    '02f217d8b08e_clean_initial_migration_ref.py',
    '1n7bslh69u6x_add_has_completed_profile_migration_to_.py',
    '2f3g4h5i6j7k_add_claim_type_and_transaction_link.py',
    '8961726a4544_add_audit_log_tables.py',
    'a1b2c3d4e5f7_add_student_blocks_and_tap_deletion.py',
    'aa5697e97c94_add_join_code_to_tap_events.py',
    'abc123def456_convert_transaction_amounts.py',
    'add_has_assigned_students_to_admin.py',
    'b2c3d4e5f6g7_add_insurance_monetary_toggle.py',
    'b4c5d6e7f8g9_add_deletion_request_model.py',
    'b73c4d92eadd_add_teacher_id_to_students.py',
    'c1c6f7e5e3a0_add_student_teacher_association.py',
    'c4d5e6f7a8b9_add_user_reports_table.py',
    'd1e2f3a4b5c6_add_block_association_tables.py',
    'd8e9f0a1b2c3_add_teacher_id_to_transactions.py',
    'e1f2a3b4c5d6_add_last_name_hash_by_part.py',
    'e5f6g7h8i9j0_add_missing_insurance_columns.py',
    'f2g3h4i5j6k7_add_teacher_blocks_table.py',
    'g1h2i3j4k5l6_add_max_payout_per_period_to_insurance.py',
    'm0n1o2p3q4r5_add_bundle_and_bulk_discount_to_store.py',
    'n1o2p3q4r5s6_add_interest_calculation_type.py',
    'o2p3q4r5s6t7_add_collective_goal_settings.py',
    'q4r5s6t7u8v9_add_user_reports_table.py',
    'x1y2z3a4b5c6_add_redemption_prompt_to_store_items.py',
    'z2a3b4c5d6e7_add_feature_settings_and_onboarding.py'
}



def validate_migrations():
    """Run all migration validations."""
    if not MIGRATIONS_DIR.exists():
        print(f"❌ Migrations directory not found: {MIGRATIONS_DIR}")
        return 1

    migrations = []
    errors = []
    warnings = []

    # Read all migration files
    for filepath in MIGRATIONS_DIR.glob("*.py"):
        if filepath.name.startswith("__"):
            continue
        try:
            info = extract_migration_info(filepath)
            if info['revision']:
                migrations.append(info)
            else:
                errors.append(f"❌ No revision found in: {filepath.name}")
            
            # Run idempotency checks
            if filepath.name in LEGACY_MIGRATIONS:
                # specific debug or ignored
                pass 
            else:
                idempotency_issues = check_idempotency(filepath)
                for issue in idempotency_issues:
                    if issue.startswith("❌"):
                        errors.append(issue)
                    else:
                        warnings.append(issue)

                safety_issues = check_redemption_audit_log_safety(filepath)
                for issue in safety_issues:
                    errors.append(issue)

        except Exception as e:
            errors.append(f"❌ Error parsing {filepath.name}: {e}")

    print("=" * 60)
    print("MIGRATION VALIDATION REPORT")
    print("=" * 60)
    print(f"\n📊 Found {len(migrations)} migration files\n")

    # Build revision maps
    revision_to_info = {m['revision']: m for m in migrations}
    down_to_up = defaultdict(list)

    for m in migrations:
        down_rev = m['down_revision']
        if down_rev is None:
            down_to_up[None].append(m['revision'])
        elif isinstance(down_rev, tuple):
            for parent in down_rev:
                down_to_up[parent].append(m['revision'])
        elif down_rev != "MISSING":
            down_to_up[down_rev].append(m['revision'])

    # Find roots
    roots = [m for m in migrations if m['down_revision'] is None]
    print(f"🌱 Root migrations: {len(roots)}")
    for r in roots:
        print(f"   - {r['revision'][:12]}... ({r['filename'][:40]})")

    # Find heads
    all_revisions = set(m['revision'] for m in migrations)
    all_down_revisions = set()
    for m in migrations:
        dr = m['down_revision']
        if dr is None:
            continue
        elif isinstance(dr, tuple):
            all_down_revisions.update(dr)
        elif dr != "MISSING":
            all_down_revisions.add(dr)

    heads = all_revisions - all_down_revisions
    print(f"\n🔝 Migration heads: {len(heads)}")
    for h in sorted(heads):
        info = revision_to_info.get(h, {})
        print(f"   - {h[:12]}... ({info.get('filename', 'unknown')[:40]})")

    # Check for multiple heads (CRITICAL)
    if len(heads) > 1:
        errors.append(f"❌ CRITICAL: Multiple heads detected ({len(heads)})")
        errors.append("   This will cause deployment failures!")
        errors.append("   Run: flask db merge heads -m 'Merge migration heads'")
    else:
        print("\n✅ Single head confirmed")

    # Check for orphaned revisions
    all_valid_revisions = all_revisions | {None}
    for m in migrations:
        dr = m['down_revision']
        if dr == "MISSING":
            errors.append(f"❌ Missing down_revision in: {m['filename']}")
        elif isinstance(dr, tuple):
            for parent in dr:
                if parent not in all_valid_revisions:
                    errors.append(f"❌ Orphan: {m['filename']} references missing: {parent[:12]}...")
        elif dr is not None and dr not in all_valid_revisions:
            errors.append(f"❌ Orphan: {m['filename']} references missing: {dr[:12]}...")

    # Check for missing functions
    for m in migrations:
        if not m['has_upgrade']:
            errors.append(f"❌ Missing upgrade() in: {m['filename']}")
        if not m['has_downgrade']:
            errors.append(f"❌ Missing downgrade() in: {m['filename']}")

    # Verify chain continuity
    visited = set()

    def walk_chain(rev):
        if rev in visited:
            return
        visited.add(rev)
        for child in down_to_up.get(rev, []):
            walk_chain(child)

    for root in roots:
        walk_chain(root['revision'])

    unreachable = all_revisions - visited
    if unreachable:
        errors.append(f"❌ {len(unreachable)} migrations unreachable from root")
        for rev in list(unreachable)[:3]:
            info = revision_to_info.get(rev, {})
            errors.append(f"   - {rev[:12]}... ({info.get('filename', 'unknown')})")
    else:
        print("✅ All migrations reachable from root")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if errors:
        print(f"\n🔴 ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   {e}")
        print("\n❌ VALIDATION FAILED - Fix errors before deploying!")
        return 1

    if warnings:
        print(f"\n🟡 WARNINGS ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"   {w}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more")

    print(f"\n✅ VALIDATION PASSED")
    print(f"   • {len(migrations)} migrations")
    print(f"   • {len(roots)} root(s)")
    print(f"   • {len(heads)} head(s)")
    print(f"   • {len(warnings)} warning(s)")
    print(f"   • Continuous chain verified")
    print("\n🟢 Safe to deploy migrations")
    return 0


if __name__ == "__main__":
    sys.exit(validate_migrations())
