# Security Remediation Implementation Guide

**Date:** 2025-12-22
**Purpose:** Step-by-step instructions to fix critical and high-severity security issues
**Reference:** COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md

---

## Quick Navigation

- [Critical: SSH Host Key Verification](#critical-ssh-host-key-verification-asa-002)
- [High: Update Cryptography Package](#high-update-cryptography-package-asa-004)
- [High: Improve Secrets Management](#high-improve-secrets-management-asa-003)
- [Medium: Add Rate Limiting](#medium-add-rate-limiting-asa-006)
- [Testing After Fixes](#testing-after-fixes)

---

## CRITICAL: SSH Host Key Verification (ASA-002)

### Priority: 🔥 URGENT - Must fix before next production deployment

### Current Problem

Both `deploy.yml` and `toggle-maintenance.yml` disable SSH host key verification:

```bash
ssh -o StrictHostKeyChecking=no root@$PRODUCTION_SERVER_IP
```

This allows Man-in-the-Middle attacks where an attacker can intercept deployment and steal secrets.

### Solution: Add Known Hosts Verification

You have **two options**. Option 1 is recommended for simplicity.

---

### Option 1: Add KNOWN_HOSTS Secret (RECOMMENDED)

#### Step 1: Get Your Server's SSH Host Key

Run this command **on your local machine** (not on the server):

```bash
# Replace with your actual production server IP
ssh-keyscan -H YOUR_PRODUCTION_SERVER_IP > known_hosts_temp

# View the contents
cat known_hosts_temp
```

You'll see output like:
```
|1|abc123...= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...
|1|def456...= ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB...
```

#### Step 2: Add to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Name: `KNOWN_HOSTS`
5. Value: Paste the **entire contents** of `known_hosts_temp`
6. Click **"Add secret"**

#### Step 3: Update deploy.yml

Replace the current deploy step with this:

```yaml
    - name: Set up SSH with host key verification
      run: |
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
        echo "${{ secrets.KNOWN_HOSTS }}" > ~/.ssh/known_hosts
        chmod 644 ~/.ssh/known_hosts

    - name: Deploy to DO Production Server
      run: |
        MAINT_MODE="${{ vars.MAINTENANCE_MODE || 'false' }}"
        MAINT_MESSAGE="${{ vars.MAINTENANCE_MESSAGE || 'We are performing scheduled maintenance.' }}"
        MAINT_END="${{ vars.MAINTENANCE_EXPECTED_END || '' }}"
        MAINT_CONTACT="${{ vars.MAINTENANCE_CONTACT || '' }}"
        TURNSTILE_SITE="${{ secrets.TURNSTILE_SITE_KEY || '' }}"
        TURNSTILE_SECRET="${{ secrets.TURNSTILE_SECRET_KEY || '' }}"

        SSH_ENV_VARS="MAINT_MODE=$(printf %q "$MAINT_MODE") MAINT_MESSAGE=$(printf %q "$MAINT_MESSAGE") MAINT_END=$(printf %q "$MAINT_END") MAINT_CONTACT=$(printf %q "$MAINT_CONTACT") TURNSTILE_SITE=$(printf %q "$TURNSTILE_SITE") TURNSTILE_SECRET=$(printf %q "$TURNSTILE_SECRET")"

        # Connect to the production server and deploy
        # NOTE: Removed -o StrictHostKeyChecking=no for security
        ssh root@${{ secrets.PRODUCTION_SERVER_IP }} "export ${SSH_ENV_VARS}; bash -s" << 'EOF'

          set -e  # Exit immediately if a command exits with a non-zero status

          echo 'Navigating to project directory...'
          cd ~/classroom-economy

          echo 'Fetching latest changes from main...'
          git fetch origin main

          echo 'Resetting to match remote main branch...'
          git reset --hard origin/main

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

          # Add updated variables from GitHub
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

        EOF
```

#### Step 4: Update toggle-maintenance.yml

Add the same host key setup step before the SSH command:

```yaml
    - name: Set up SSH
      uses: webfactory/ssh-agent@v0.9.0
      with:
        ssh-private-key: ${{ secrets.DO_DEPLOY_KEY }}

    - name: Set up SSH host key verification
      run: |
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
        echo "${{ secrets.KNOWN_HOSTS }}" > ~/.ssh/known_hosts
        chmod 644 ~/.ssh/known_hosts

    - name: Update maintenance mode on server
      run: |
        ENABLED="${{ inputs.enabled }}"
        MODE_VALUE="false"
        if [ "$ENABLED" = "true" ]; then
          MODE_VALUE="true"
        fi

        MESSAGE="${{ inputs.message }}"
        EXPECTED_END="${{ inputs.expected_end }}"
        CONTACT="${{ inputs.contact }}"
        BADGE_TYPE="${{ inputs.badge_type }}"
        STATUS_DESCRIPTION="${{ inputs.status_description }}"

        SSH_ENV_VARS="MODE_VALUE=$(printf %q "${MODE_VALUE}") MESSAGE=$(printf %q "${MESSAGE}") EXPECTED_END=$(printf %q "${EXPECTED_END}") CONTACT=$(printf %q "${CONTACT}") BADGE_TYPE=$(printf %q "${BADGE_TYPE}") STATUS_DESCRIPTION=$(printf %q "${STATUS_DESCRIPTION}")"

        # NOTE: Removed -o StrictHostKeyChecking=no for security
        ssh root@${{ secrets.PRODUCTION_SERVER_IP }} "export ${SSH_ENV_VARS}; bash -s" << 'EOF'
          set -e

          echo 'Navigating to project directory...'
          cd ~/classroom-economy

          echo 'Updating maintenance mode settings...'
          # Remove old maintenance mode variables
          sed -i '/^MAINTENANCE_MODE=/d' .env 2>/dev/null || true
          sed -i '/^MAINTENANCE_MESSAGE=/d' .env 2>/dev/null || true
          sed -i '/^MAINTENANCE_EXPECTED_END=/d' .env 2>/dev/null || true
          sed -i '/^MAINTENANCE_CONTACT=/d' .env 2>/dev/null || true
          sed -i '/^MAINTENANCE_BADGE_TYPE=/d' .env 2>/dev/null || true
          sed -i '/^MAINTENANCE_STATUS_DESCRIPTION=/d' .env 2>/dev/null || true

          # Add new maintenance mode variables
          echo "MAINTENANCE_MODE=$MODE_VALUE" >> .env
          echo "MAINTENANCE_MESSAGE=\"$MESSAGE\"" >> .env
          echo "MAINTENANCE_EXPECTED_END=\"$EXPECTED_END\"" >> .env
          echo "MAINTENANCE_CONTACT=\"$CONTACT\"" >> .env
          echo "MAINTENANCE_BADGE_TYPE=\"$BADGE_TYPE\"" >> .env
          echo "MAINTENANCE_STATUS_DESCRIPTION=\"$STATUS_DESCRIPTION\"" >> .env

          echo 'Restarting Gunicorn to apply changes...'
          sudo systemctl restart gunicorn

          echo "Maintenance mode updated: $MODE_VALUE"
          if [ "$MODE_VALUE" = "true" ]; then
            echo "Badge type: $BADGE_TYPE"
            echo "Message: $MESSAGE"
            echo "Expected end: $EXPECTED_END"
            echo "Contact: $CONTACT"
            echo "Status description: $STATUS_DESCRIPTION"
          fi
        EOF
```

#### Step 5: Test the Fix

1. Commit your workflow changes to a test branch
2. Trigger the workflow manually or via a test deployment
3. Check workflow logs for successful SSH connection
4. Verify it connects WITHOUT the insecure flag

**Expected Success Output:**
```
Setting up SSH with host key verification
Host key verification enabled
Connecting to server...
✓ Connection successful with verified host key
```

---

### Option 2: Use GitHub Actions SSH Action

Instead of manual SSH commands, use a pre-built action:

#### Step 1: Install appleboy/ssh-action

Add to `deploy.yml`:

```yaml
    - name: Deploy to Production Server
      uses: appleboy/ssh-action@v1.0.3
      env:
        MAINT_MODE: ${{ vars.MAINTENANCE_MODE || 'false' }}
        MAINT_MESSAGE: ${{ vars.MAINTENANCE_MESSAGE || 'We are performing scheduled maintenance.' }}
        MAINT_END: ${{ vars.MAINTENANCE_EXPECTED_END || '' }}
        MAINT_CONTACT: ${{ vars.MAINTENANCE_CONTACT || '' }}
        TURNSTILE_SITE: ${{ secrets.TURNSTILE_SITE_KEY || '' }}
        TURNSTILE_SECRET: ${{ secrets.TURNSTILE_SECRET_KEY || '' }}
      with:
        host: ${{ secrets.PRODUCTION_SERVER_IP }}
        username: root
        key: ${{ secrets.DO_DEPLOY_KEY }}
        envs: MAINT_MODE,MAINT_MESSAGE,MAINT_END,MAINT_CONTACT,TURNSTILE_SITE,TURNSTILE_SECRET
        script: |
          set -e
          echo 'Navigating to project directory...'
          cd ~/classroom-economy

          echo 'Fetching latest changes from main...'
          git fetch origin main

          echo 'Resetting to match remote main branch...'
          git reset --hard origin/main

          # ... rest of deployment script
```

**Pros:**
- Handles host key verification automatically
- Cleaner YAML syntax
- Better error handling

**Cons:**
- Depends on third-party action
- Requires testing and validation

---

## HIGH: Update Cryptography Package (ASA-004)

### Priority: ⚠️ HIGH - Fix this week

### Current Problem

```
requirements.txt: cryptography==41.0.4
Installed: cryptography==41.0.7
Latest: Check pypi.org
```

The cryptography package is used for:
- PII encryption (Fernet AES)
- TOTP 2FA generation
- Password hashing (via bcrypt)

### Solution

#### Step 1: Check for Known Vulnerabilities

```bash
# Install pip-audit (if not already installed)
pip install pip-audit

# Scan for vulnerabilities
pip-audit

# Or check specific package
pip-audit | grep cryptography
```

#### Step 2: Update Package

```bash
# Activate your virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Update cryptography
pip install --upgrade cryptography

# Check installed version
pip show cryptography
```

#### Step 3: Update requirements.txt

```bash
# Option 1: Freeze exact version
pip freeze | grep cryptography >> requirements_new.txt
# Then manually update requirements.txt with the new version

# Option 2: Use version range (recommended)
# Edit requirements.txt, change:
# FROM: cryptography==41.0.4
# TO:   cryptography>=43.0.0,<44.0.0  # Or latest major version
```

**Recommended requirements.txt entry:**
```txt
cryptography>=43.0.0,<44.0.0  # Allow minor updates, pin major version
```

#### Step 4: Test Thoroughly

```bash
# Run full test suite
pytest tests/

# Specifically test encryption/decryption
pytest tests/ -k "encryption"

# Test TOTP/2FA functionality
pytest tests/ -k "totp"

# Test password hashing
pytest tests/ -k "password"
```

#### Step 5: Test in Development Environment

```bash
# Start the application
flask run

# Test critical flows:
# 1. Student login/logout
# 2. Admin login with 2FA
# 3. View encrypted student names
# 4. Password reset flow
# 5. TOTP verification
```

#### Step 6: Update CHANGELOG

Add to `CHANGELOG.md`:

```markdown
### Security
- Updated `cryptography` package from 41.0.4 to [NEW_VERSION]
  - Addresses potential security vulnerabilities
  - Maintains compatibility with PII encryption and 2FA
  - All tests passing
```

#### Step 7: Deploy to Production

1. Commit changes:
   ```bash
   git add requirements.txt CHANGELOG.md
   git commit -m "SECURITY: Update cryptography package to [VERSION]"
   git push
   ```

2. Merge to main (after review)

3. Deployment workflow will automatically install new version

---

## HIGH: Improve Secrets Management (ASA-003)

### Priority: ⚠️ HIGH - Fix this month

### Current Problem

Secrets are written to `.env` file on production server:

```bash
echo "TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET}" >> .env
```

**Risks:**
- Plain text secrets on filesystem
- Potential log exposure
- No file permission hardening

### Solution Options

#### Option 1: Harden .env File Permissions (Quick Fix)

Update `deploy.yml` to set restrictive permissions:

```bash
echo 'Updating environment variables...'
# Set restrictive permissions before writing
touch .env
chmod 600 .env  # Only owner can read/write

# Remove old variables if they exist
sed -i '/^MAINTENANCE_MODE=/d' .env 2>/dev/null || true
# ... rest of sed commands ...

# Add updated variables from GitHub
echo "MAINTENANCE_MODE=${MAINT_MODE}" >> .env
echo "MAINTENANCE_MESSAGE=\"${MAINT_MESSAGE}\"" >> .env
echo "TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET}" >> .env

# Verify permissions
ls -la .env  # Should show -rw-------

# Ensure ownership
chown root:root .env
```

#### Option 2: Use Environment Variables in Systemd (Better)

1. **Edit your Gunicorn systemd service:**

```bash
# On production server
sudo nano /etc/systemd/system/gunicorn.service
```

2. **Add environment variables:**

```ini
[Service]
User=root
Group=root
WorkingDirectory=/root/classroom-economy
Environment="SECRET_KEY=your-secret-from-github-or-vault"
Environment="DATABASE_URL=your-db-url"
Environment="ENCRYPTION_KEY=your-encryption-key"
Environment="PEPPER_KEY=your-pepper-key"
Environment="TURNSTILE_SECRET_KEY=your-turnstile-secret"
ExecStart=/root/classroom-economy/venv/bin/gunicorn --workers 3 --bind unix:/root/classroom-economy/gunicorn.sock wsgi:app
```

3. **Update deploy.yml to NOT write secrets to .env:**

```bash
# Remove these lines from deploy.yml:
# echo "TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET}" >> .env

# Instead, update systemd service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

4. **Use Secrets Manager (Optional but Best):**

If using DigitalOcean:
- Store secrets in DigitalOcean Secrets Manager
- Reference them in your app configuration
- No secrets in code or config files

#### Option 3: Use dotenv with Encryption (Alternative)

Install `python-dotenv` with encryption support:

```bash
pip install python-dotenv[encryption]
```

Encrypt your .env file:

```python
from dotenv import load_dotenv, encrypt_dotenv

# Encrypt .env file
encrypt_dotenv('.env', 'your-encryption-password')

# Load encrypted env
load_dotenv('.env.encrypted', password='your-encryption-password')
```

---

## MEDIUM: Add Rate Limiting (ASA-006)

### Priority: 🟡 MEDIUM - Fix this month

### Current Problem

```python
@api_bp.route('/api/tips/<user_type>')
@limiter.exempt  # No rate limiting
def get_tips(user_type):
```

This endpoint can be abused for bandwidth attacks.

### Solution

#### Option 1: Add Generous Rate Limit

Edit `app/routes/api.py`:

```python
# BEFORE:
@api_bp.route('/tips/<user_type>')
@limiter.exempt
def get_tips(user_type):

# AFTER:
@api_bp.route('/tips/<user_type>')
@limiter.limit("100 per minute")  # Generous but prevents abuse
def get_tips(user_type):
    """
    Return tips for login loading screens as JSON.

    Rate limited to 100 requests per minute to prevent abuse
    while allowing legitimate high-frequency usage.
    """
```

#### Option 2: Add Caching (Recommended)

Install Flask-Caching:

```bash
pip install Flask-Caching
```

Update `app/extensions.py`:

```python
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379')
})
```

Initialize in `app/__init__.py`:

```python
from app.extensions import cache
cache.init_app(app)
```

Update `app/routes/api.py`:

```python
from app.extensions import cache

@api_bp.route('/tips/<user_type>')
@limiter.exempt
@cache.cached(timeout=300)  # Cache for 5 minutes
def get_tips(user_type):
    """
    Return tips for login loading screens as JSON.

    Cached for 5 minutes to reduce server load.
    Exempt from rate limiting due to caching.
    """
```

**Benefits:**
- Reduces server load
- Faster response times
- Still exempt from rate limiting (safe due to caching)

---

## Testing After Fixes

### 1. Local Testing

```bash
# Run full test suite
pytest tests/ -v

# Test specific security areas
pytest tests/ -k "csrf"
pytest tests/ -k "authentication"
pytest tests/ -k "encryption"
```

### 2. GitHub Actions Testing

```bash
# Trigger workflow manually
gh workflow run check-migrations.yml

# Or push to test branch
git checkout -b test/security-fixes
git push origin test/security-fixes
```

### 3. Production Deployment Testing

Before deploying to production:

1. **Test SSH connection locally:**
   ```bash
   ssh -i ~/.ssh/your-key root@YOUR_SERVER_IP "echo 'Connection test'"
   ```

2. **Test deployment workflow on staging (if available)**

3. **Monitor first production deployment:**
   - Watch GitHub Actions logs in real-time
   - Check for SSH connection success
   - Verify application starts correctly
   - Test critical user flows

---

## Verification Checklist

After implementing fixes, verify:

### SSH Host Key Verification
- [ ] `KNOWN_HOSTS` secret added to GitHub
- [ ] `deploy.yml` updated with host key setup
- [ ] `toggle-maintenance.yml` updated with host key setup
- [ ] `StrictHostKeyChecking=no` removed from all workflows
- [ ] Test deployment successful
- [ ] No MITM warnings in logs

### Cryptography Update
- [ ] Package updated to latest version
- [ ] `requirements.txt` updated
- [ ] All tests passing
- [ ] PII encryption/decryption working
- [ ] 2FA TOTP working
- [ ] Password hashing working
- [ ] Deployed to production successfully

### Secrets Management
- [ ] .env file permissions set to 600
- [ ] File ownership correct (root:root)
- [ ] OR systemd environment variables configured
- [ ] Secrets not visible in logs
- [ ] Application starts correctly with new config

### Rate Limiting
- [ ] Rate limit added to /api/tips
- [ ] OR caching implemented
- [ ] Tested: legitimate users not blocked
- [ ] Tested: excessive requests blocked

---

## Rollback Plan

If anything goes wrong:

### SSH Issues

```bash
# Temporarily add back StrictHostKeyChecking=no
# (Only for emergency deployments)
ssh -o StrictHostKeyChecking=no root@$SERVER "..."

# Then fix known_hosts issue
```

### Cryptography Issues

```bash
# Rollback to previous version
pip install cryptography==41.0.4

# Update requirements.txt
# Deploy
```

### Secrets Issues

```bash
# SSH to server
ssh root@$SERVER

# Check .env file
cat .env
ls -la .env

# Fix permissions if needed
chmod 600 .env

# Restart gunicorn
sudo systemctl restart gunicorn
```

---

## Support

If you encounter issues:

1. **Check GitHub Actions logs** for detailed error messages
2. **Review server logs:** `sudo journalctl -u gunicorn -f`
3. **Test locally first** before deploying to production
4. **Create issue** in repository with error details

---

## Summary

**Immediate Actions (Before Next Deploy):**
1. ✅ Add `KNOWN_HOSTS` secret to GitHub
2. ✅ Update `deploy.yml` and `toggle-maintenance.yml`
3. ✅ Test deployment on test branch
4. ✅ Deploy to production

**This Week:**
1. Update `cryptography` package
2. Test thoroughly
3. Deploy

**This Month:**
1. Harden .env file permissions
2. Add rate limiting or caching to /api/tips
3. Consider secrets manager for long-term

---

**Last Updated:** 2025-12-22
**Maintainer:** DevOps/Security Team
