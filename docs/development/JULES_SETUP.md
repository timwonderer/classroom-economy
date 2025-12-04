# Jules Environment Setup Guide

This guide explains how to set up a consistent development environment for the Classroom Economy platform using the automated setup script.

## Quick Start

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd classroom-economy

# Run the setup script
./setup_jules.sh
```

The setup script will:
1. ✓ Verify Python 3.10+ is installed
2. ✓ Check for PostgreSQL and Redis
3. ✓ Create a virtual environment (`venv/`)
4. ✓ Install all Python dependencies
5. ✓ Create `.env` file with secure generated keys
6. ✓ Initialize and migrate the database
7. ✓ (Optional) Create a system admin account
8. ✓ (Optional) Seed test data

## Prerequisites

### Required
- **Python 3.10+** - Required for the application
- **PostgreSQL** - Required for production (SQLite can be used for development)
- **Redis** - Required for rate limiting and caching

### Installation Commands

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3.10 python3.10-venv python3-pip
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install redis-server
```

**macOS:**
```bash
brew install python@3.10
brew install postgresql@14
brew install redis
brew services start postgresql
brew services start redis
```

**Docker (Alternative):**
```bash
# PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=jules_password \
  -e POSTGRES_USER=jules_user \
  -e POSTGRES_DB=classroom_economy_jules \
  -p 5432:5432 \
  postgres:14

# Redis
docker run -d --name redis -p 6379:6379 redis:alpine
```

## Environment Variables

The setup script creates a `.env` file from `.env.example` with the following variables:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session security key | Auto-generated 64-byte token |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://jules_user:jules_password@localhost:5432/classroom_economy_jules` |
| `FLASK_ENV` | Environment mode | `development`, `testing`, or `production` |
| `ENCRYPTION_KEY` | PII encryption key (32-byte base64) | Auto-generated with `openssl` |
| `PEPPER_KEY` | Additional credential hashing key | Auto-generated hex token |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TURNSTILE_SITE_KEY` | Cloudflare Turnstile CAPTCHA site key | Test key (auto-bypassed) |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret key | Test key |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FILE` | Log file path (production) | `app.log` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `RATELIMIT_STORAGE_URI` | Rate limit storage backend | `redis://localhost:6379` |

### Maintenance Mode Variables

Used to enable maintenance mode and display status pages:

| Variable | Description | Example |
|----------|-------------|---------|
| `MAINTENANCE_MODE` | Enable maintenance mode | `true`, `false` |
| `MAINTENANCE_BADGE_TYPE` | Badge category | `maintenance`, `bug`, `security` |
| `MAINTENANCE_STATUS_DESCRIPTION` | Description of maintenance | "Scheduled system updates" |
| `MAINTENANCE_SYSADMIN_BYPASS` | Allow sysadmin bypass | `true`, `false` |
| `MAINTENANCE_BYPASS_TOKEN` | Bypass token | Secure random token |
| `MAINTENANCE_EXPECTED_END` | Expected end time | "2025-12-05 14:00 UTC" |
| `MAINTENANCE_MESSAGE` | User-facing message | "Please check back soon" |
| `MAINTENANCE_CONTACT` | Support contact | `support@example.com` |
| `STATUS_PAGE_URL` | UptimeRobot status page | UptimeRobot URL |

## Manual Setup (Without Script)

If you prefer to set up manually:

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Create .env File
```bash
cp .env.example .env
```

Then generate secure keys:
```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# ENCRYPTION_KEY
openssl rand -base64 32

# PEPPER_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Update `.env` with the generated keys.

### 4. Create PostgreSQL Database
```bash
# Login to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE classroom_economy_jules;
CREATE USER jules_user WITH PASSWORD 'jules_password';
GRANT ALL PRIVILEGES ON DATABASE classroom_economy_jules TO jules_user;
\q
```

### 5. Initialize Database
```bash
export FLASK_APP=wsgi.py
flask db upgrade
```

### 6. Create System Admin
```bash
flask create-sysadmin
```

Follow the prompts and scan the QR code with your authenticator app (Google Authenticator, Authy, etc.).

### 7. (Optional) Seed Test Data
```bash
python seed_dummy_students.py
```

## Running the Application

### Development Server
```bash
# Activate virtual environment
source venv/bin/activate

# Run Flask development server
flask run

# Application available at http://localhost:5000
```

### Production Server (Gunicorn)
```bash
gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 wsgi:app
```

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run specific test file
pytest tests/test_payroll.py

# Run tests matching pattern
pytest -k "test_attendance"
```

## Useful Flask Commands

```bash
# Create system admin with TOTP
flask create-sysadmin

# Apply database migrations
flask db upgrade

# Create new migration
flask db migrate -m "Description of changes"

# Rollback migration
flask db downgrade

# Migrate legacy student data
flask migrate-legacy-students
```

## Database Snapshots

To create a snapshot of your Jules environment:

### PostgreSQL Snapshot
```bash
# Create backup
pg_dump -U jules_user -d classroom_economy_jules -F c -f jules_snapshot_$(date +%Y%m%d).dump

# Restore backup
pg_restore -U jules_user -d classroom_economy_jules -c jules_snapshot_20251204.dump
```

### SQLite Snapshot (Development)
```bash
# Create backup
cp classroom_economy.db classroom_economy_backup_$(date +%Y%m%d).db

# Restore backup
cp classroom_economy_backup_20251204.db classroom_economy.db
```

## Troubleshooting

### Database Connection Errors
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check credentials in `.env` match PostgreSQL user
- Verify database exists: `psql -U jules_user -l`

### Redis Connection Errors
- Ensure Redis is running: `redis-cli ping` (should return "PONG")
- Start Redis: `sudo systemctl start redis-server`

### Migration Errors
- Check migration status: `flask db current`
- Check for migration conflicts: `flask db heads`
- If stuck, see migration troubleshooting in `/docs/DEPLOYMENT.md`

### Permission Errors
- Ensure setup script is executable: `chmod +x setup_jules.sh`
- Check file ownership: `ls -la .env`

### Python Version Issues
- Verify Python version: `python3 --version`
- Ensure Python 3.10+: Required for this application
- Update Python or use pyenv to manage versions

## Security Notes

⚠️ **Important:**
- Never commit `.env` to version control (already in `.gitignore`)
- Keep `SECRET_KEY`, `ENCRYPTION_KEY`, and `PEPPER_KEY` secure
- Use strong, randomly generated keys in production
- Rotate keys periodically in production environments
- Use a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault) in production

## Next Steps

After setup:
1. Access the application at `http://localhost:5000`
2. Login with your system admin credentials
3. Enable TOTP authentication with your authenticator app
4. Create teacher accounts via the system admin panel
5. Review the documentation in `/docs/` for features and operations

## Additional Resources

- **Main README:** `/README.md` - Project overview
- **Deployment Guide:** `/docs/DEPLOYMENT.md` - Production deployment
- **Technical Reference:** `/docs/technical-reference/` - Architecture details
- **User Guides:** `/docs/user-guides/` - Student and teacher guides

## Support

For issues or questions:
- Check existing documentation in `/docs/`
- Review test files in `/tests/` for usage examples
- Open an issue on GitHub with detailed error messages
