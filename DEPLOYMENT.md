# Deployment Guide

## Digital Ocean Deployment

### Standard Deployment
Deployments happen automatically when you push to `main` branch via GitHub Actions.

### Fresh Database Reset (When Migrations Are Broken)

If you encounter migration errors like `KeyError: '<revision_id>'`, you can reset the database:

#### Option 1: Using the Reset Script (Recommended)

SSH into your DO server and run:

```bash
cd ~/classroom-economy
source venv/bin/activate
export DATABASE_URL='your_database_url_here'
python reset_database.py
```

The script will:
1. Ask for confirmation
2. Drop all tables
3. Run all migrations fresh from scratch

#### Option 2: Manual Reset

SSH into your DO server:

```bash
cd ~/classroom-economy
source venv/bin/activate

# Set your database URL
export DATABASE_URL='your_database_url_here'

# Connect to PostgreSQL and drop all tables
psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public;"

# Run migrations
flask db upgrade

# Restart the application
sudo systemctl restart gunicorn
```

#### Option 3: One-Line Reset

For a quick reset without confirmation prompts:

```bash
cd ~/classroom-economy && source venv/bin/activate && export DATABASE_URL='your_db_url' && psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public;" && flask db upgrade && sudo systemctl restart gunicorn
```

### After Database Reset

After resetting the database:

1. **Create a system admin account** (if your app requires it)
2. **Reload any necessary seed data**
3. **Test the application** to ensure everything works

### Common Migration Issues

- **Multiple heads**: Run `flask db heads` to see if there are multiple migration endpoints
- **Missing revision**: A migration file might be missing from the repo
- **Database out of sync**: The database has migrations applied that don't exist in code

All of these can be fixed with a fresh database reset.

### Deployment Workflow Location

The deployment workflow is defined in:
- `.github/workflows/deploy.yml` (for Digital Ocean)
- `.github/workflows/fly-deploy.yml` (for Fly.io staging)

### Environment Variables Required

Make sure these secrets are set in GitHub Actions:
- `DO_DEPLOY_KEY`: SSH key for Digital Ocean
- `PRODUCTION_DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Flask secret key
- `ENCRYPTION_KEY`: For encrypting sensitive data
- `PEPPER_KEY`: For password hashing
- `CSRF_SECRET_KEY`: CSRF protection key
