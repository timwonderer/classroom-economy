#!/usr/bin/env python3
"""
Script to check migration files for issues:
1. Multiple heads
2. Missing migrations
3. Corrupted migration files
"""

import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

def parse_migration_file(filepath: Path) -> Optional[Dict]:
    """Parse a migration file to extract revision info."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Extract revision ID
        revision_match = re.search(r'^revision\s*=\s*[\'"]([^\'"]+)[\'"]', content, re.MULTILINE)
        # Extract down_revision - can be None or a string
        down_revision_match = re.search(r'^down_revision\s*=\s*(.+)$', content, re.MULTILINE)
        # Extract branch_labels
        branch_labels_match = re.search(r'^branch_labels\s*=\s*(.+)$', content, re.MULTILINE)
        # Extract depends_on
        depends_on_match = re.search(r'^depends_on\s*=\s*(.+)$', content, re.MULTILINE)

        if not revision_match:
            return None

        revision = revision_match.group(1)

        # Parse down_revision
        down_revision = None
        if down_revision_match:
            down_rev_str = down_revision_match.group(1).strip()
            if down_rev_str != 'None':
                # Could be a string, tuple, or list
                try:
                    down_revision = ast.literal_eval(down_rev_str)
                except:
                    # Try to extract string value
                    string_match = re.search(r'[\'"]([^\'"]+)[\'"]', down_rev_str)
                    if string_match:
                        down_revision = string_match.group(1)

        # Parse branch_labels
        branch_labels = None
        if branch_labels_match:
            branch_str = branch_labels_match.group(1).strip()
            if branch_str != 'None':
                try:
                    branch_labels = ast.literal_eval(branch_str)
                except:
                    pass

        # Parse depends_on
        depends_on = None
        if depends_on_match:
            depends_str = depends_on_match.group(1).strip()
            if depends_str != 'None':
                try:
                    depends_on = ast.literal_eval(depends_str)
                except:
                    pass

        return {
            'file': filepath.name,
            'revision': revision,
            'down_revision': down_revision,
            'branch_labels': branch_labels,
            'depends_on': depends_on
        }
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def analyze_migrations(migrations_dir: Path) -> Tuple[Dict, List[str]]:
    """Analyze all migration files and return issues found."""
    migrations = []
    issues = []

    # Parse all migration files
    for filepath in sorted(migrations_dir.glob('*.py')):
        if filepath.name == '__init__.py':
            continue

        migration_info = parse_migration_file(filepath)
        if migration_info:
            migrations.append(migration_info)
        else:
            issues.append(f"⚠️  CORRUPTED: Could not parse {filepath.name}")

    print(f"\n📊 Found {len(migrations)} migration files\n")

    # Build revision map
    revision_map = {m['revision']: m for m in migrations}

    # Find all revisions that are referenced as down_revision
    referenced_revisions = set()
    for m in migrations:
        down_rev = m['down_revision']
        if down_rev:
            if isinstance(down_rev, (list, tuple)):
                referenced_revisions.update(down_rev)
            else:
                referenced_revisions.add(down_rev)

    # Find heads (revisions not referenced as down_revision by any other migration)
    all_revisions = set(revision_map.keys())
    heads = all_revisions - referenced_revisions

    print(f"🔍 Migration Heads Found: {len(heads)}")
    for head in sorted(heads):
        head_file = revision_map[head]['file']
        print(f"   - {head[:12]} ({head_file})")

    if len(heads) > 1:
        issues.append(f"❌ MULTIPLE HEADS: Found {len(heads)} heads (should be 1)")
    elif len(heads) == 0:
        issues.append(f"❌ NO HEADS: No migration heads found (circular dependency?)")
    else:
        print("   ✅ Single head found\n")

    # Check for missing migrations (referenced but don't exist)
    missing_revisions = referenced_revisions - all_revisions - {None}
    if missing_revisions:
        issues.append(f"❌ MISSING MIGRATIONS: {len(missing_revisions)} referenced revisions not found")
        for missing in sorted(missing_revisions):
            issues.append(f"   - {missing[:12]}")
    else:
        print("✅ No missing migrations\n")

    # Check for orphaned migrations (no path to head)
    def get_descendants(revision: str, visited: Set[str] = None) -> Set[str]:
        """Get all migrations that depend on this revision."""
        if visited is None:
            visited = set()
        if revision in visited:
            return visited
        visited.add(revision)

        for m in migrations:
            down_rev = m['down_revision']
            if down_rev:
                down_revs = [down_rev] if not isinstance(down_rev, (list, tuple)) else list(down_rev)
                if revision in down_revs:
                    get_descendants(m['revision'], visited)
        return visited

    # Find orphaned migrations (not reachable from any head)
    reachable = set()
    for head in heads:
        # Traverse backwards from head
        queue = [head]
        visited = set()
        while queue:
            current = queue.pop(0)
            if current in visited or current is None:
                continue
            visited.add(current)
            reachable.add(current)

            if current in revision_map:
                down_rev = revision_map[current]['down_revision']
                if down_rev:
                    if isinstance(down_rev, (list, tuple)):
                        queue.extend(down_rev)
                    else:
                        queue.append(down_rev)

    orphaned = all_revisions - reachable
    if orphaned:
        issues.append(f"❌ ORPHANED MIGRATIONS: {len(orphaned)} migrations not reachable from heads")
        for orphan in sorted(orphaned):
            orphan_file = revision_map[orphan]['file']
            issues.append(f"   - {orphan[:12]} ({orphan_file})")
    else:
        print("✅ No orphaned migrations\n")

    # Check for circular dependencies
    def has_circular_dependency(start_rev: str, current_rev: str, path: List[str]) -> Optional[List[str]]:
        """Check if there's a circular dependency starting from start_rev."""
        if current_rev == start_rev and len(path) > 1:
            return path + [current_rev]
        if current_rev in path:
            return None
        if current_rev not in revision_map:
            return None

        down_rev = revision_map[current_rev]['down_revision']
        if not down_rev:
            return None

        down_revs = [down_rev] if not isinstance(down_rev, (list, tuple)) else list(down_rev)
        for dr in down_revs:
            result = has_circular_dependency(start_rev, dr, path + [current_rev])
            if result:
                return result
        return None

    for rev in all_revisions:
        circular = has_circular_dependency(rev, rev, [])
        if circular:
            issues.append(f"❌ CIRCULAR DEPENDENCY: {' -> '.join([r[:12] for r in circular])}")
            break
    else:
        print("✅ No circular dependencies\n")

    return revision_map, issues

def main():
    migrations_dir = Path('/home/user/classroom-economy/migrations/versions')

    print("=" * 70)
    print("🔍 MIGRATION ANALYSIS")
    print("=" * 70)

    revision_map, issues = analyze_migrations(migrations_dir)

    if issues:
        print("\n" + "=" * 70)
        print("⚠️  ISSUES FOUND")
        print("=" * 70)
        for issue in issues:
            print(issue)
        print("\n")
        return 1
    else:
        print("=" * 70)
        print("✅ ALL CHECKS PASSED - No migration issues found!")
        print("=" * 70)
        print("\n")
        return 0

if __name__ == '__main__':
    exit(main())
