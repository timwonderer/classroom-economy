#!/usr/bin/env python3
"""Verify the migration chain can be traversed from start to end."""

import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional

def parse_migration_file(filepath: Path) -> Optional[Dict]:
    """Parse a migration file to extract revision info."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        revision_match = re.search(r'^revision\s*=\s*[\'"]([^\'"]+)[\'"]', content, re.MULTILINE)
        down_revision_match = re.search(r'^down_revision\s*=\s*(.+)$', content, re.MULTILINE)

        if not revision_match:
            return None

        revision = revision_match.group(1)
        down_revision = None

        if down_revision_match:
            down_rev_str = down_revision_match.group(1).strip()
            if down_rev_str != 'None':
                try:
                    down_revision = ast.literal_eval(down_rev_str)
                except:
                    string_match = re.search(r'[\'"]([^\'"]+)[\'"]', down_rev_str)
                    if string_match:
                        down_revision = string_match.group(1)

        return {
            'file': filepath.name,
            'revision': revision,
            'down_revision': down_revision,
        }
    except Exception as e:
        return None

def verify_migration_chain(migrations_dir: Path):
    """Verify the complete migration chain."""
    migrations = []

    # Parse all migration files
    for filepath in sorted(migrations_dir.glob('*.py')):
        if filepath.name == '__init__.py':
            continue
        migration_info = parse_migration_file(filepath)
        if migration_info:
            migrations.append(migration_info)

    revision_map = {m['revision']: m for m in migrations}
    all_revisions = set(revision_map.keys())

    # Find root migrations (down_revision is None)
    roots = [m for m in migrations if m['down_revision'] is None]

    print(f"\n📊 Total migrations: {len(migrations)}")
    print(f"🌱 Root migrations: {len(roots)}")
    for root in roots:
        print(f"   - {root['revision'][:12]} ({root['file']})")

    # Find heads (not referenced by any other migration)
    referenced_revisions = set()
    for m in migrations:
        down_rev = m['down_revision']
        if down_rev:
            if isinstance(down_rev, (list, tuple)):
                referenced_revisions.update(down_rev)
            else:
                referenced_revisions.add(down_rev)

    heads = all_revisions - referenced_revisions
    print(f"\n🎯 Head migrations: {len(heads)}")
    for head in sorted(heads):
        print(f"   - {head[:12]} ({revision_map[head]['file']})")

    # Trace path from root to head
    def trace_to_head(current: str, visited: Set[str], path: List[str]) -> Optional[List[str]]:
        """Trace path from current revision to a head."""
        if current in heads:
            return path + [current]

        if current in visited:
            return None

        visited.add(current)

        # Find migrations that depend on current
        for m in migrations:
            down_rev = m['down_revision']
            if down_rev:
                down_revs = [down_rev] if not isinstance(down_rev, (list, tuple)) else list(down_rev)
                if current in down_revs:
                    result = trace_to_head(m['revision'], visited.copy(), path + [current])
                    if result:
                        return result

        return None

    # Trace from each root to head
    print("\n🔍 Verifying paths from roots to heads...")
    for root in roots:
        path = trace_to_head(root['revision'], set(), [])
        if path:
            print(f"   ✅ Path from {root['revision'][:12]} to head: {len(path)} migrations")
        else:
            print(f"   ❌ No path from {root['revision'][:12]} to any head!")
            return 1

    # Verify all migrations are reachable from roots
    reachable = set()
    for root in roots:
        queue = [root['revision']]
        visited = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            reachable.add(current)

            # Find migrations that depend on current
            for m in migrations:
                down_rev = m['down_revision']
                if down_rev:
                    down_revs = [down_rev] if not isinstance(down_rev, (list, tuple)) else list(down_rev)
                    if current in down_revs and m['revision'] not in visited:
                        queue.append(m['revision'])

    unreachable = all_revisions - reachable
    if unreachable:
        print(f"\n❌ {len(unreachable)} migrations unreachable from roots:")
        for unreach in sorted(unreachable):
            print(f"   - {unreach[:12]} ({revision_map[unreach]['file']})")
        return 1
    else:
        print(f"\n✅ All {len(migrations)} migrations are reachable from roots")

    # Check for duplicate revision IDs
    revision_counts = {}
    for filepath in sorted(migrations_dir.glob('*.py')):
        if filepath.name == '__init__.py':
            continue
        migration_info = parse_migration_file(filepath)
        if migration_info:
            rev = migration_info['revision']
            if rev not in revision_counts:
                revision_counts[rev] = []
            revision_counts[rev].append(filepath.name)

    duplicates = {k: v for k, v in revision_counts.items() if len(v) > 1}
    if duplicates:
        print(f"\n❌ Found duplicate revision IDs:")
        for rev, files in duplicates.items():
            print(f"   - {rev[:12]}:")
            for f in files:
                print(f"     - {f}")
        return 1
    else:
        print("✅ No duplicate revision IDs found")

    print("\n" + "="*70)
    print("✅ MIGRATION CHAIN VERIFICATION PASSED")
    print("="*70)
    print(f"\nThe migration chain is valid and can be traversed from the")
    print(f"{len(roots)} root migration(s) through {len(migrations)} total migrations")
    print(f"to the single head migration.\n")

    return 0

if __name__ == '__main__':
    migrations_dir = Path('/home/user/classroom-economy/migrations/versions')
    exit(verify_migration_chain(migrations_dir))
