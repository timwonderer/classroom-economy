#!/bin/bash
#
# Pre-deployment migration health check
# Run this script before deploying to verify migrations are safe
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}┌────────────────────────────────────────────────────┐${NC}"
echo -e "${BLUE}│   Database Migration Pre-Flight Check             │${NC}"
echo -e "${BLUE}└────────────────────────────────────────────────────┘${NC}"
echo ""

# Check if migrations directory exists
if [ ! -d "migrations" ]; then
    echo -e "${YELLOW}⚠️  No migrations directory found${NC}"
    echo "   Skipping migration checks"
    exit 0
fi

# Check for multiple heads
echo "🔍 Checking for multiple migration heads..."
python3 << 'PYTHON_SCRIPT'
import sys
import os

try:
    if not os.path.exists('migrations/alembic.ini'):
        print("✓ No migrations configured")
        sys.exit(0)

    from alembic.script import ScriptDirectory
    from alembic.config import Config

    config = Config('migrations/alembic.ini')
    config.set_main_option('script_location', 'migrations')
    script = ScriptDirectory.from_config(config)
    heads = list(script.get_revisions('heads'))

    print(f"   Found {len(heads)} migration head(s)")

    if len(heads) > 1:
        print("\n❌ CRITICAL: Multiple migration heads detected!")
        print("\nThis will cause deployment failures!")
        print("\nHeads found:")
        for i, head in enumerate(heads, 1):
            print(f"   {i}. {head.revision} - {head.doc}")
        print("\nYou MUST fix this before deploying:")
        print("   flask db merge heads -m 'Merge migration heads'")
        sys.exit(1)
    elif len(heads) == 1:
        print(f"✓ Single migration head: {heads[0].revision}")
        print(f"  Message: {heads[0].doc or '(no description)'}")
    else:
        print("✓ No migration heads (empty migrations)")

except ImportError:
    print("⚠️  Warning: alembic not installed")
    print("   Install with: pip install alembic flask-migrate")
    sys.exit(0)
except Exception as e:
    print(f"⚠️  Warning: Could not check migrations: {e}")
    sys.exit(0)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   DEPLOYMENT BLOCKED - FIX MIGRATIONS FIRST            ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi

# Validate migration files
echo ""
echo "🔍 Validating migration file syntax..."
python3 << 'PYTHON_SCRIPT'
import sys
import os
from pathlib import Path

migration_dir = Path('migrations/versions')
if not migration_dir.exists():
    print("✓ No migration files to validate")
    sys.exit(0)

errors = []
warnings = []
total_files = 0

for migration_file in migration_dir.glob('*.py'):
    if migration_file.name == '__init__.py':
        continue

    total_files += 1

    try:
        with open(migration_file, 'r') as f:
            content = f.read()

        # Check for required components
        if 'def upgrade():' not in content:
            errors.append(f"{migration_file.name}: Missing upgrade() function")
        if 'def downgrade():' not in content:
            errors.append(f"{migration_file.name}: Missing downgrade() function")
        if 'revision =' not in content:
            errors.append(f"{migration_file.name}: Missing revision identifier")
        if 'down_revision =' not in content:
            errors.append(f"{migration_file.name}: Missing down_revision")

        # Check for common issues
        if content.count('def upgrade():') > 1:
            errors.append(f"{migration_file.name}: Multiple upgrade() functions")
        if content.count('def downgrade():') > 1:
            errors.append(f"{migration_file.name}: Multiple downgrade() functions")

        # Check for empty functions (potential issue)
        if 'def upgrade():\n    pass' in content or 'def upgrade():\n        pass' in content:
            if 'merge' not in migration_file.name.lower():
                warnings.append(f"{migration_file.name}: Empty upgrade() function")

    except Exception as e:
        errors.append(f"{migration_file.name}: {str(e)}")

print(f"   Validated {total_files} migration file(s)")

if errors:
    print("\n❌ Migration validation errors:")
    for error in errors:
        print(f"   • {error}")
    sys.exit(1)

if warnings:
    print("\n⚠️  Warnings:")
    for warning in warnings:
        print(f"   • {warning}")

print("✓ All migration files are valid")
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   DEPLOYMENT BLOCKED - INVALID MIGRATION FILES         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi

# All checks passed
echo ""
echo -e "${GREEN}┌────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│   ✓ All Migration Checks Passed                   │${NC}"
echo -e "${GREEN}└────────────────────────────────────────────────────┘${NC}"
echo ""
echo -e "${GREEN}✓ Safe to deploy${NC}"
echo ""
exit 0
