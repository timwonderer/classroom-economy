#!/bin/bash
#
# Quick migration heads check for agents
# Run this BEFORE creating PRs to catch multiple heads early
#

set -e

echo "🔍 Checking migration heads..."
echo ""

python3 << 'PYTHON_SCRIPT'
import sys
import os

# Check if we're in the right directory
if not os.path.exists('migrations/alembic.ini'):
    print("❌ ERROR: Must run from project root directory")
    sys.exit(1)

from alembic.script import ScriptDirectory
from alembic.config import Config

config = Config('migrations/alembic.ini')
config.set_main_option('script_location', 'migrations')
script = ScriptDirectory.from_config(config)
heads = list(script.get_revisions('heads'))

print(f"📊 Migration Status:")
print(f"   Total heads: {len(heads)}")
print("")

if len(heads) > 1:
    print(f"❌ MULTIPLE HEADS DETECTED! ({len(heads)} heads)")
    print("")
    print("Migration heads:")
    for i, head in enumerate(heads, 1):
        print(f"  {i}. {head.revision}")
        print(f"     Message: {head.doc}")
        print(f"     File: [revision]_*.py")
    print("")
    print("⚠️  FIX REQUIRED BEFORE PUSHING:")
    print("")
    print("Option 1 - Create a merge migration:")
    print("  flask db merge heads -m 'Merge migration heads'")
    print("")
    print("Option 2 - If your migration was just created, delete and recreate:")
    print("  1. Delete your migration file from migrations/versions/")
    print("  2. git fetch origin main && git merge origin/main")
    print("  3. flask db migrate -m 'your description'")
    print("")
    sys.exit(1)
elif len(heads) == 1:
    print(f"✅ SINGLE HEAD - GOOD!")
    print(f"   Current head: {heads[0].revision}")
    print(f"   Message: {heads[0].doc}")
    print("")
    print("Safe to commit and push.")
    sys.exit(0)
else:
    print("⚠️  WARNING: No migration heads found")
    print("   This might indicate a problem with the migrations directory")
    sys.exit(1)

PYTHON_SCRIPT
