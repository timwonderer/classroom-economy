#!/bin/bash
# Deploy store revamp updates

echo "=== Deploying Store Revamp Updates ==="

# Check if running from production directory
if [ -d "/root/classroom-economy" ]; then
    DEPLOY_DIR="/root/classroom-economy"
    echo "Deploying to production: $DEPLOY_DIR"
else
    DEPLOY_DIR="/home/user/classroom-economy"
    echo "Deploying to development: $DEPLOY_DIR"
fi

cd "$DEPLOY_DIR" || exit 1

echo ""
echo "Step 1: Pulling latest changes from git..."
git fetch origin
git pull origin claude/revamp-class-store-page-01HYq4SktP2xFB4bLTZXdCA7

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

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "✅ Changes Deployed:"
echo "  - New tabbed store layout (Overview, Manage Items, Purchase History)"
echo "  - Bundle items support (e.g., 5-pack items)"
echo "  - Bulk discount pricing"
echo "  - Hard delete option for items without purchase history"
echo ""
echo "🔒 P1 Security Fixes:"
echo "  - Form validation to prevent incomplete bundle/discount configurations"
echo "  - API guards to prevent crashes from malformed data"
echo "  - Hall pass purchase limit bypass fix (multi-quantity purchases)"
echo ""
echo "The store revamp is now live!"
