# Contributing to Classroom Token Hub

Thank you for your interest in contributing to the Classroom Token Hub project!

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine.
3.  **Install git hooks** (required for migration safety checks):
    ```bash
    bash scripts/setup-hooks.sh
    ```
    This installs a pre-push hook that prevents migration conflicts.
4.  **Set up the development environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
5.  **Configure your environment variables:**
    Create a `.env` file and populate it with the required variables listed in `DEPLOYMENT.md`.
6.  **Run the database migrations:**
    ```bash
    flask db upgrade
    ```
7.  **Create a system admin account:**
    ```bash
    flask create-sysadmin
    ```
8.  **Run the application:**
    ```bash
    flask run
    ```

## Working with Database Migrations

**IMPORTANT:** Follow this workflow carefully to avoid migration conflicts (multiple heads).

### When Your Change REQUIRES a Database Migration:

1. **Create your branch and make code changes:**
   ```bash
   git checkout -b feature/my-feature
   # Make your model changes in app/models/...
   ```

2. **Sync with main BEFORE creating the migration:**
   ```bash
   git fetch origin main
   git merge origin/main  # or: git rebase origin/main
   ```

   ⚠️ **This is critical!** Always sync immediately before `flask db migrate`

3. **Create your migration:**
   ```bash
   flask db migrate -m "Add column X to table Y"
   ```

4. **Review the generated migration file:**
   - Check `migrations/versions/` for the new file
   - Verify the `down_revision` points to the latest head
   - Test both `upgrade()` and `downgrade()` functions

5. **Test the migration locally:**
   ```bash
   flask db upgrade
   flask db downgrade
   flask db upgrade
   ```

6. **Commit and push:**
   ```bash
   git add migrations/
   git commit -m "Add migration for feature X"
   git push origin feature/my-feature
   ```

### Migration Best Practices:

- ✅ **DO:** Sync with main immediately before `flask db migrate`
- ✅ **DO:** Merge migration PRs quickly (within 24 hours if possible)
- ✅ **DO:** Keep migrations small and focused (one change per migration)
- ✅ **DO:** Test both upgrade and downgrade paths
- ❌ **DON'T:** Create migrations without syncing first
- ❌ **DON'T:** Edit migration files after they're merged to main
- ❌ **DON'T:** Delete migration files (use `flask db downgrade` instead)

### If You Encounter Multiple Heads:

If the pre-push hook detects multiple heads:

```bash
# Option 1: Create a merge migration
flask db merge heads -m "Merge migration heads"
git add migrations/
git commit -m "Merge migration heads"

# Option 2: Recreate your migration (if not yet merged)
rm migrations/versions/YOUR_MIGRATION.py
git fetch origin main
git merge origin/main
flask db migrate -m "Your change description"
```

### Pre-Push Hook:

A pre-push hook is automatically installed via `scripts/setup-hooks.sh` (see [Getting Started](#getting-started) step 3) that checks for multiple migration heads before pushing. This prevents most migration conflicts from reaching the repository.

If you haven't run the setup script yet:
```bash
bash scripts/setup-hooks.sh
```

To bypass the check (not recommended):
```bash
git push --no-verify
```

### Production Deployment Failures:

If deployment fails with a "multiple heads" error, follow this procedure carefully.

#### Scenario A: Deployment Check Catches Multiple Heads (Before flask db upgrade runs)

**This is the good scenario** - the deployment check caught the issue before it affected the database.

1. **SSH into your DigitalOcean droplet to verify:**
   ```bash
   ssh root@your-droplet-ip
   cd ~/classroom-economy
   source venv/bin/activate
   flask db heads
   ```

2. **Create merge migration locally:**
   ```bash
   # On your local machine:
   git checkout main
   git pull origin main
   source venv/bin/activate
   flask db merge heads -m "Merge migration heads (production fix)"
   ```

3. **Review the merge migration file:**
   ```bash
   # Check migrations/versions/ for the new merge file
   # Verify it references both heads in down_revision
   ```

4. **Commit and push to trigger redeployment:**
   ```bash
   git add migrations/
   git commit -m "Fix production migration heads"
   git push origin main
   ```

5. **Wait for automatic redeployment** or manually deploy on server:
   ```bash
   # On server:
   git pull origin main
   flask db upgrade
   ```

6. **Verify success:**
   ```bash
   flask db heads  # Should show only 1 head
   flask db current  # Shows the merge migration was applied
   ```

---

#### Scenario B: Multiple Heads Already on Production Server (After flask db upgrade ran)

**This is the problematic scenario** - somehow multiple heads were already applied to production database.

1. **SSH into production server:**
   ```bash
   ssh root@your-droplet-ip
   cd ~/classroom-economy
   source venv/bin/activate
   ```

2. **Check current database state:**
   ```bash
   flask db current  # May show error or multiple revisions
   flask db heads    # Shows all head revisions
   ```

   Example output:
   ```
   abc123 (head)  # Head 1
   def456 (head)  # Head 2
   ```

3. **IMPORTANT: Create merge migration DIRECTLY ON SERVER**
   ```bash
   # This must be done on the server to match the actual database state
   flask db merge heads -m "Emergency merge migration heads on production"
   ```

   This creates a merge migration that references both heads.

4. **Apply the merge migration:**
   ```bash
   flask db upgrade
   ```

5. **Verify the merge worked:**
   ```bash
   flask db heads    # Should show only 1 head now
   flask db current  # Should show the merge revision
   ```

6. **Copy the merge migration back to your repo:**
   ```bash
   # On server, find the new migration file:
   ls -lt migrations/versions/ | head -5

   # Copy its contents (e.g., via cat or scp)
   cat migrations/versions/YOUR_MERGE_MIGRATION.py
   ```

7. **On your local machine, commit this merge migration:**
   ```bash
   # Create the same merge migration file locally
   # (paste the content from the server)
   git checkout main
   git pull origin main
   # Create migrations/versions/YOUR_MERGE_MIGRATION.py with the content
   git add migrations/
   git commit -m "Add emergency merge migration from production"
   git push origin main
   ```

8. **Verify everything is in sync:**
   ```bash
   # On server:
   git pull origin main
   flask db heads  # Should still show 1 head
   flask db current  # Should match local
   ```

---

#### When to Use Which Scenario:

- **Use Scenario A** if: Deployment check failed, `flask db upgrade` never ran
- **Use Scenario B** if: `flask db upgrade` ran and failed, or database already has multiple heads

**Prevention is key:** The 3-layer safety system should prevent Scenario B from ever happening!

**Prevention:**
- GitHub Actions automatically checks for multiple heads on all PRs
- Run pre-deployment check: `bash scripts/check-migrations.sh`
- Never use `git push --no-verify` when pushing to main
- Merge migration PRs one at a time, not concurrently

### Automated Safety Checks:

This repository has **three layers** of migration protection:

1. **Pre-Push Hook (Developer)** - Installed via `scripts/setup-hooks.sh`
   - Blocks pushes with multiple heads
   - Runs on every `git push`
   - Can be bypassed with `--no-verify` (not recommended)

2. **GitHub Actions (CI/CD)** - Workflow: `.github/workflows/check-migrations.yml`
   - Runs on every PR to main
   - Blocks merging if multiple heads detected
   - Validates migration file syntax
   - **Cannot be bypassed** - PR cannot merge if check fails

3. **Pre-Deployment Script (Manual)** - Run before deploying
   ```bash
   bash scripts/check-migrations.sh
   ```
   - Run this before deploying to production
   - Checks migration heads and file validity
   - Returns exit code 1 if unsafe to deploy
   - Integrate into your deployment pipeline

**Recommendation:** Add the pre-deployment check to your DigitalOcean deployment script:
```bash
# In your deployment script, before flask db upgrade:
bash scripts/check-migrations.sh || exit 1
flask db upgrade
```

## Submitting Changes

1.  **Create a new branch** for your feature or bug fix.
2.  **Make your changes** and commit them with a clear and descriptive commit message.
3.  **If your changes require a database migration**, follow the [migration workflow](#working-with-database-migrations) above.
4.  **Push your branch** to your fork on GitHub.
5.  **Create a pull request** from your branch to the `main` branch of the original repository.

## Running Tests

Before submitting a pull request, please run the test suite to ensure that your changes have not introduced any regressions.

```bash
python -m pytest
```
