#!/usr/bin/env bash
set -euo pipefail

# Show outdated Python packages
echo "Checking for outdated packages..."
OUTDATED=$(python3 -m pip list --outdated --format=freeze | cut -d= -f1 | tr '\n' ' ')

if [ -z "$OUTDATED" ]; then
  echo "All dependencies are up to date."
  exit 0
fi

echo "Upgrading: $OUTDATED"
python3 -m pip install -U $OUTDATED

# Freeze exact versions back to requirements.txt
python3 -m pip freeze > requirements.txt

echo "Running tests after upgrade..."
python3 -m pytest

