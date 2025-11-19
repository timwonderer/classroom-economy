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
