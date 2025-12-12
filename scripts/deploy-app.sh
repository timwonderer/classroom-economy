#!/bin/bash
set -e

# Deployment script for Classroom Economy
# Expects the following environment variables to be set:
# - DEPLOY_BRANCH (optional, defaults to main)
# - MAINT_MODE
# - MAINT_MESSAGE
# - MAINT_END
# - MAINT_CONTACT
# - TURNSTILE_SITE (optional)
# - TURNSTILE_SECRET (optional)

TARGET_BRANCH="${DEPLOY_BRANCH:-main}"

echo 'Navigating to project directory...'
cd ~/classroom-economy

echo "Fetching latest changes from ${TARGET_BRANCH}..."
git fetch origin "${TARGET_BRANCH}"

echo "Resetting to match remote ${TARGET_BRANCH} branch..."
git reset --hard "origin/${TARGET_BRANCH}"

echo 'Activating virtual environment...'
source venv/bin/activate

echo 'Updating environment variables...'
# Remove old variables if they exist
sed -i '/^MAINTENANCE_MODE=/d' .env 2>/dev/null || true
sed -i '/^MAINTENANCE_MESSAGE=/d' .env 2>/dev/null || true
sed -i '/^MAINTENANCE_EXPECTED_END=/d' .env 2>/dev/null || true
sed -i '/^MAINTENANCE_CONTACT=/d' .env 2>/dev/null || true
sed -i '/^TURNSTILE_SITE_KEY=/d' .env 2>/dev/null || true
sed -i '/^TURNSTILE_SECRET_KEY=/d' .env 2>/dev/null || true

# Add updated variables from Environment
echo "MAINTENANCE_MODE=${MAINT_MODE}" >> .env
echo "MAINTENANCE_MESSAGE=\"${MAINT_MESSAGE}\"" >> .env
echo "MAINTENANCE_EXPECTED_END=\"${MAINT_END}\"" >> .env
echo "MAINTENANCE_CONTACT=\"${MAINT_CONTACT}\"" >> .env

# Add Turnstile keys if provided
if [ -n "${TURNSTILE_SITE}" ]; then
  echo "TURNSTILE_SITE_KEY=${TURNSTILE_SITE}" >> .env
  echo "✓ Turnstile site key configured"
fi
if [ -n "${TURNSTILE_SECRET}" ]; then
  echo "TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET}" >> .env
  echo "✓ Turnstile secret key configured"
fi

echo 'Installing dependencies...'
pip install -r requirements.txt

# Ensure DATABASE_URL is set for migrations
echo 'Exporting DATABASE_URL for production migrations...'

echo '🔍 Running migration safety checks...'
bash scripts/check-migrations.sh || {
  echo "❌ Migration safety check failed - deployment aborted"
  echo "This usually means there are multiple migration heads."
  echo "Fix this by creating a merge migration locally and pushing to main."
  exit 1
}

echo 'Running database migrations...'
flask db upgrade

echo 'Restarting Gunicorn...'
sudo systemctl restart gunicorn

echo 'Deployment completed successfully.'
