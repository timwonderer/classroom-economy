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

If `flask db upgrade` fails during deployment to DigitalOcean with a "multiple heads" error, this means migration conflicts reached `main` branch (usually due to concurrent PR merges or bypassed hooks).

**CRITICAL: Follow this procedure carefully in production:**

1. **DO NOT rollback the deployment** - Fix forward instead
2. **SSH into your DigitalOcean droplet:**
   ```bash
   ssh user@your-droplet-ip
   cd /path/to/your/app
   source venv/bin/activate
   ```

3. **Check the current situation:**
   ```bash
   flask db current
   flask db heads
   ```

4. **Create a merge migration on main:**
   ```bash
   # On your local machine, on main branch:
   git checkout main
   git pull origin main
   flask db merge heads -m "Merge migration heads (production fix)"
   git add migrations/
   git commit -m "Fix production migration heads"
   git push origin main
   ```

5. **Deploy the merge migration:**
   - Push to main triggers new deployment
   - Or manually pull on server: `git pull && flask db upgrade`

6. **Verify success:**
   ```bash
   flask db current
   flask db heads  # Should show only 1 head
   ```

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
