# Contributing to Classroom Token Hub

Thank you for your interest in contributing to the Classroom Token Hub project!

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine.
3.  **Set up the development environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
4.  **Configure your environment variables:**
    Create a `.env` file and populate it with the required variables listed in `DEPLOYMENT.md`.
5.  **Run the database migrations:**
    ```bash
    flask db upgrade
    ```
6.  **Create a system admin account:**
    ```bash
    flask create-sysadmin
    ```
7.  **Run the application:**
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

A pre-push hook is installed at `.git/hooks/pre-push` that automatically checks for multiple migration heads before pushing. This prevents most migration conflicts from reaching the repository.

To bypass the check (not recommended):
```bash
git push --no-verify
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
