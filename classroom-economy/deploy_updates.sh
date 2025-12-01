#!/bin/bash
# Unified deployment script with maintenance-mode persistence awareness.

echo "=== Deploying Updates ==="

# Argument parsing (optional):
#   --end-maintenance : explicitly turn off maintenance mode after deploy
END_MAINTENANCE=0
for arg in "$@"; do
    if [ "$arg" = "--end-maintenance" ]; then
        END_MAINTENANCE=1
    fi
done

# Check if running from production directory
if [ -d "/root/classroom-economy" ]; then
    DEPLOY_DIR="/root/classroom-economy"
    echo "Deploying to production: $DEPLOY_DIR"
else
    DEPLOY_DIR="/home/user/classroom-economy"
    echo "Deploying to development: $DEPLOY_DIR"
fi

cd "$DEPLOY_DIR" || exit 1

# Detect existing maintenance state (from .env or current environment)
MAINT_FILE=".env"
CURRENT_MAINT=""
if [ -f "$MAINT_FILE" ]; then
    # Grep exact beginning of line to avoid commented copies
    if grep -q "^MAINTENANCE_MODE=" "$MAINT_FILE"; then
        CURRENT_MAINT=$(grep "^MAINTENANCE_MODE=" "$MAINT_FILE" | head -n1 | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')
    fi
fi

IS_MAINT_ACTIVE=0
case "$CURRENT_MAINT" in
    true|1|yes|on) IS_MAINT_ACTIVE=1 ;; 
esac

if [ $IS_MAINT_ACTIVE -eq 1 ]; then
    echo "⚙️  Maintenance mode currently ACTIVE (MAINTENANCE_MODE=$CURRENT_MAINT)."
else
    echo "ℹ️  Maintenance mode currently inactive or not set."
fi

if [ $END_MAINTENANCE -eq 1 ] && [ $IS_MAINT_ACTIVE -eq 1 ]; then
    echo "--end-maintenance requested: disabling maintenance mode post-deploy."
    # Update .env in-place (preserve other content). Use sed portable form.
    if [ -f "$MAINT_FILE" ]; then
        # If variable exists, replace; else append.
        if grep -q "^MAINTENANCE_MODE=" "$MAINT_FILE"; then
            sed -i.bak 's/^MAINTENANCE_MODE=.*/MAINTENANCE_MODE=false/' "$MAINT_FILE" && rm -f "$MAINT_FILE.bak"
        else
            echo "MAINTENANCE_MODE=false" >> "$MAINT_FILE"
        fi
        IS_MAINT_ACTIVE=0
    else
        echo "(No .env found to modify MAINTENANCE_MODE)"
    fi
elif [ $END_MAINTENANCE -eq 1 ] && [ $IS_MAINT_ACTIVE -eq 0 ]; then
    echo "--end-maintenance requested but maintenance was not active; nothing to change."
else
    if [ $IS_MAINT_ACTIVE -eq 1 ]; then
        echo "🔐 Persisting maintenance mode across this deploy (will NOT auto-disable)."
    fi
fi

echo ""
echo "Step 1: Pulling latest changes from git..."
git fetch origin
git pull origin main

echo ""
echo "Step 2: Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo ""
echo "Step 3: Running database migration..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    flask db upgrade
else
    echo "Warning: venv not found, attempting system python..."
    python -m flask db upgrade
fi

echo ""
echo "Step 4: Reloading application..."
touch wsgi.py

# Optional: surface final maintenance state after code + migrations
FINAL_STATE="inactive"
if [ $IS_MAINT_ACTIVE -eq 1 ]; then FINAL_STATE="active"; fi

echo ""
echo "=== Deployment Complete ==="
echo "Maintenance mode: $FINAL_STATE"
if [ $FINAL_STATE = "active" ]; then
    echo "(Bypass available for system admin or using MAINTENANCE_BYPASS_TOKEN)"
fi
echo ""
echo "✅ Deployment executed (branch: main)."
echo "To end maintenance later: rerun with --end-maintenance or toggle workflow."
