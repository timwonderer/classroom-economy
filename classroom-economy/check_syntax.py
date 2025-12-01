#!/usr/bin/env python3
"""Check syntax of all migration files."""

import py_compile
import sys
from pathlib import Path

def check_migration_syntax(migrations_dir: Path):
    """Check syntax of all migration files."""
    issues = []
    checked = 0

    for filepath in sorted(migrations_dir.glob('*.py')):
        if filepath.name == '__init__.py':
            continue

        try:
            py_compile.compile(str(filepath), doraise=True)
            checked += 1
        except py_compile.PyCompileError as e:
            issues.append(f"❌ SYNTAX ERROR in {filepath.name}: {e}")

    print(f"\n✅ Checked {checked} migration files")

    if issues:
        print("\n⚠️  SYNTAX ERRORS FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return 1
    else:
        print("✅ All migration files have valid Python syntax\n")
        return 0

if __name__ == '__main__':
    migrations_dir = Path('/home/user/classroom-economy/migrations/versions')
    exit(check_migration_syntax(migrations_dir))
