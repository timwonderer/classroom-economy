# Deployment Guide

This guide provides instructions for deploying the Classroom Token Hub application.

## General Deployment Steps

The application is a standard Flask application that can be deployed to any platform that supports Python and Gunicorn.

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Environment Variables:**
    Create a `.env` file or set the environment variables directly in your hosting environment. See the [Environment Variables](#environment-variables) section for a complete list.

3.  **Run Database Migrations:**
    Before starting the application for the first time, and after any database schema changes, run the following command:
    ```bash
    flask db upgrade
    ```

4.  **Start the Application Server:**
    Use Gunicorn to run the application in a production environment:
    ```bash
    gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app
    ```

## Environment Variables

The application requires the following environment variables to be set:

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | A long, random string used to secure sessions and sign cookies. | `super-secret-key` |
| `DATABASE_URL` | The full connection string for your PostgreSQL database. | `postgresql://user:password@host:port/dbname` |
| `FLASK_ENV` | The environment for Flask. Set to `production` for deployments. | `production` |
| `ENCRYPTION_KEY` | A 32-byte key for encrypting personally identifiable information (PII). You can generate one with `openssl rand -base64 32`. | `your-encryption-key` |
| `PEPPER_KEY` | A secret key used to add an additional layer of security to student credentials. | `your-pepper-key` |
| `CSRF_SECRET_KEY` | A secret key for CSRF protection. | `your-csrf-secret-key` |

The application also recognizes these optional variables for logging:

| Variable | Description | Default |
|---|---|---|
| `LOG_LEVEL` | The logging level. | `INFO` |
| `LOG_FORMAT` | The log message format. | `[%(asctime)s] %(levelname)s in %(module)s: %(message)s` |
| `LOG_FILE` | The file used for rotating logs when `FLASK_ENV=production`. | `app.log` |

### Maintenance Mode Variables

| Variable | Description | Example |
|---|---|---|
| `MAINTENANCE_MODE` | When `true/1/on/yes`, all non-bypassed requests render the maintenance page. | `true` |
| `MAINTENANCE_BADGE_TYPE` | Badge category displayed (maintenance, bug, security, update, feature, unavailable, error). | `update` |
| `MAINTENANCE_STATUS_DESCRIPTION` | Free-form description explaining current work. | `Applying security patches` |
| `MAINTENANCE_SYSADMIN_BYPASS` | Allow system admin sessions to bypass maintenance. | `true` |
| `MAINTENANCE_BYPASS_TOKEN` | Token that enables bypass via `?maintenance_bypass=<token>` query. | `MySecretToken123` |

### Persistence Behavior

Maintenance mode is intentionally PERSISTENT across code deployments. Pushing to `main` or running `deploy_updates.sh` does not clear `MAINTENANCE_MODE`. This prevents accidental reopening while iterative fixes are applied.

To end maintenance you must either:
1. Run the maintenance toggle workflow with mode off, OR
2. Manually edit `.env` and set `MAINTENANCE_MODE=false`, OR
3. Execute the deploy script with `--end-maintenance` (added safeguard).

### Testing While In Maintenance

During maintenance you can still exercise the application:
- Log in as a system admin (if `MAINTENANCE_SYSADMIN_BYPASS=true`).
- Use a normal teacher/student session with the bypass query: `https://yourdomain/app_path?maintenance_bypass=MySecretToken123` (token must match `MAINTENANCE_BYPASS_TOKEN`).
- A visible ribbon shows you are bypassing maintenance (`maintenance_bypass_active`).

Recommended workflow for an extended maintenance window:
1. Enable maintenance via workflow, set badge + description.
2. Set `MAINTENANCE_SYSADMIN_BYPASS=true` and a strong `MAINTENANCE_BYPASS_TOKEN`.
3. Deploy iterative code changes freely (mode persists).
4. Validate fixes using bypass sessions.
5. Disable maintenance via workflow or `deploy_updates.sh --end-maintenance` when satisfied.

Security tip: Rotate `MAINTENANCE_BYPASS_TOKEN` after major incidents or before ending maintenance to avoid token reuse.

## Database Reset

If you encounter migration errors that cannot be resolved, you can reset the database. **Warning: This will delete all data.**

1.  **Connect to PostgreSQL:**
    ```bash
    psql $DATABASE_URL
    ```

2.  **Drop and Recreate the Schema:**
    ```sql
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO public;
    ```

3.  **Run Migrations:**
    ```bash
    flask db upgrade
    ```

## CI/CD

The deployment workflow is defined in:
- `.github/workflows/deploy.yml` (for Digital Ocean)
- `.github/workflows/fly-deploy.yml` (for Fly.io staging)
