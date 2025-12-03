"""
Test that the enum merge migration correctly combines the fix branch with main.

This test verifies that the merge migration:
1. Merges the enum fix branch (9957794d7f45) with main (1e2f3a4b5c6d)
2. The comprehensive fix migration (5esz32blgjej) ensures lowercase enum values
"""
import os
import sys
import pytest

# Set up environment before imports
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_merge_migration_exists():
    """Verify that the merge migration file exists."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = 'nvlu271s3hgq_merge_enum_fix_with_main.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    assert os.path.exists(migration_path), (
        f"Merge migration file not found at {migration_path}"
    )


def test_merge_migration_has_correct_parents():
    """Verify the merge migration has both parent revisions."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = 'nvlu271s3hgq_merge_enum_fix_with_main.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    if not os.path.exists(migration_path):
        pytest.skip(f"Merge migration file not found at {migration_path}")
    
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Verify it has both parent revisions
    assert "down_revision = ('1e2f3a4b5c6d', '9957794d7f45')" in content, (
        "Merge migration should have both parent revisions: 1e2f3a4b5c6d (main) and 9957794d7f45 (enum fix)"
    )
    
    # Verify revision ID is correct
    assert "revision = 'nvlu271s3hgq'" in content, (
        "Merge migration should have revision = 'nvlu271s3hgq'"
    )


def test_comprehensive_enum_fix_exists():
    """Verify that the comprehensive enum fix migration exists."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '5esz32blgjej_ensure_enum_lowercase.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    assert os.path.exists(migration_path), (
        f"Comprehensive enum fix migration file not found at {migration_path}"
    )


def test_comprehensive_enum_fix_content():
    """Verify the comprehensive fix has proper error handling."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '5esz32blgjej_ensure_enum_lowercase.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    if not os.path.exists(migration_path):
        pytest.skip(f"Comprehensive enum fix migration file not found at {migration_path}")
    
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Verify it creates enum if it doesn't exist
    assert "if not enum_exists:" in content, (
        "Migration should create enum if it doesn't exist"
    )
    
    # Verify it checks for correct lowercase values
    assert "expected_lowercase = ['account', 'period']" in content, (
        "Migration should check for correct lowercase values"
    )
    
    # Verify it handles case conversion
    assert "LOWER(request_type::text)" in content, (
        "Migration should handle case-insensitive conversion"
    )
    
    # Verify it's idempotent
    assert "are already correct (lowercase), no action needed" in content, (
        "Migration should be idempotent and skip if already fixed"
    )


def test_comprehensive_enum_fix_follows_merge():
    """Verify the comprehensive fix comes after the merge."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '5esz32blgjej_ensure_enum_lowercase.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    if not os.path.exists(migration_path):
        pytest.skip(f"Comprehensive enum fix migration file not found at {migration_path}")
    
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Verify it comes after the merge
    assert "down_revision = 'nvlu271s3hgq'" in content, (
        "Comprehensive fix should come after the merge migration"
    )
    
    # Verify revision ID is correct
    assert "revision = '5esz32blgjej'" in content, (
        "Comprehensive fix should have revision = '5esz32blgjej'"
    )


def test_migration_chain_is_linear_after_merge():
    """Verify that after the merge, the migration chain is linear (single head)."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    import re
    
    # Read all migration files
    migrations = {}
    for filename in os.listdir(migrations_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(migrations_dir, filename)
            with open(filepath, 'r') as f:
                content = f.read()
                
            # Extract revision and down_revision
            revision_match = re.search(r"revision = '([^']+)'", content)
            down_revision_match = re.search(r"down_revision = (\(.*?\)|'[^']+'|None)", content, re.DOTALL)
            
            if revision_match:
                revision = revision_match.group(1)
                down_revision = None
                if down_revision_match:
                    down_str = down_revision_match.group(1)
                    if down_str == 'None':
                        down_revision = None
                    elif down_str.startswith('('):
                        # Tuple of multiple parents
                        down_revision = tuple(re.findall(r"'([^']+)'", down_str))
                    else:
                        down_revision = down_str.strip("'")
                
                migrations[revision] = {
                    'file': filename,
                    'down_revision': down_revision
                }
    
    # Find heads (revisions that are not down_revision of any other)
    all_down_revisions = set()
    for rev_info in migrations.values():
        down = rev_info['down_revision']
        if down:
            if isinstance(down, tuple):
                all_down_revisions.update(down)
            else:
                all_down_revisions.add(down)
    
    heads = [rev for rev in migrations if rev not in all_down_revisions]
    
    # There should be exactly one head after our merge
    assert len(heads) == 1, (
        f"Expected exactly one migration head after merge, found {len(heads)}: {heads}"
    )
    
    # The head should be one of our comprehensive enum fixes
    # Note: fa40lzegx5tq is the DeletionRequestStatus enum fix that comes after 5esz32blgjej
    expected_heads = ['5esz32blgjej', 'fa40lzegx5tq']
    assert heads[0] in expected_heads, (
        f"Expected head to be one of {expected_heads} (enum fix migrations), found {heads[0]}"
    )
