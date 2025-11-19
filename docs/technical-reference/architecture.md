# Classroom Token Hub - Architecture Guide

**Last Updated:** 2025-11-19
**Purpose:** Comprehensive architecture guide for developers and AI assistants working on this educational platform

---

## Table of Contents

- [Project Overview](#project-overview)
- [Technology Stack](#technology-stack)
- [Current Architecture](#current-architecture)
- [Key Conventions & Patterns](#key-conventions--patterns)
- [Security Architecture](#security-architecture)
- [Database Architecture](#database-architecture)
- [Authentication System](#authentication-system)
- [Development Guidelines](#development-guidelines)

---

## Project Overview

**Classroom Token Hub** is an educational banking and classroom management platform that teaches students about money while tracking classroom participation. It features attendance tracking, automated payroll, transactions, a classroom store, insurance systems, hall passes, and more.

**License:** PolyForm Noncommercial 1.0.0 - Educational and nonprofit use only. No commercial applications.

**Production Status:** Active development for controlled classroom testing. This is a REAL application used by students, so code quality and security are critical.

### Essential Documentation

Before starting any work, familiarize yourself with these files:

1. **README.md** - Project overview, setup instructions, current features
2. **docs/development/TODO.md** - Comprehensive task list with priorities and effort estimates
3. **docs/technical-reference/database_schema.md** - Complete database structure and model documentation
4. **docs/technical-reference/api_reference.md** - All API endpoints and their specifications
5. **docs/user-guides/teacher_manual.md** - How teachers use the system (understand the user perspective)
6. **docs/development/MULTI_TENANCY_TODO.md** - Important upcoming feature (multi-teacher support)

---

## Technology Stack

### Backend

- **Flask 3.1.0** - Python web framework
- **SQLAlchemy 2.0.40** - Object-Relational Mapping (ORM)
- **Alembic** - Database migration tool
- **PostgreSQL** - Production database (Supabase for staging)
- **Gunicorn 23.0.0** - WSGI HTTP server with gevent workers

### Authentication & Security

**Admin Authentication:**
- TOTP (Time-Based One-Time Password) using pyotp 2.9.0
- All admin accounts MUST use TOTP
- System admins use invite-based signup

**Student Authentication:**
- PIN + passphrase (custom implementation)
- Hashed with salt and pepper using PEPPER_KEY

**Security Features:**
- PII encryption using `cryptography` library and ENCRYPTION_KEY
- Credential hashing with PEPPER_KEY for additional security
- CSRF protection via Flask-WTF
- All student names encrypted at rest

### Frontend

- **Jinja2 3.1.6** - Template engine
- **Bootstrap** - CSS framework for responsive UI
- **Material Symbols** - Icon library
- **Minimal JavaScript** - attendance.js for real-time features

### Testing

- **pytest 8.4.0** - Testing framework
- **pytest-flask 1.3.0** - Flask extensions for pytest
- Tests located in `/tests/` directory

### Deployment

- **Primary Production:** DigitalOcean (via SSH deployment)
- **Container Support:** Docker (Dockerfile with Python 3.10-slim)
- **CI/CD:** GitHub Actions (.github/workflows/deploy.yml)
- **WSGI Server:** Gunicorn on port 8080

---

## Current Architecture

### Modular Blueprint Architecture

The application has been successfully refactored from a monolithic `app.py` (4,583 lines) into a clean, modular structure:

```
classroom-economy/
├── wsgi.py                   # WSGI entry point for Gunicorn
├── forms.py                  # WTForms definitions for all forms
├── payroll.py                # Payroll calculation logic
├── attendance.py             # Attendance tracking logic
├── hash_utils.py             # Cryptographic utilities
├── create_admin.py           # CLI tool for creating admin accounts
├── manage_invites.py         # Admin invite management CLI
├── seed_dummy_students.py    # Test data seeding utility
│
├── app/                      # Main application package
│   ├── __init__.py           # Application factory (create_app)
│   ├── extensions.py         # Flask extensions (db, migrate, csrf)
│   ├── models.py             # All SQLAlchemy models
│   ├── auth.py               # Session decorators and auth helpers
│   │
│   ├── routes/               # Blueprint-based routes
│   │   ├── __init__.py
│   │   ├── admin.py          # Teacher portal routes
│   │   ├── student.py        # Student portal routes
│   │   ├── system_admin.py   # Super-user routes
│   │   ├── main.py           # Public/common routes
│   │   └── api.py            # REST API endpoints
│   │
│   └── utils/                # Shared utilities
│       ├── __init__.py
│       ├── encryption.py     # PII encryption
│       ├── constants.py      # Application constants
│       └── helpers.py        # Helper functions
│
├── templates/                # Jinja2 HTML templates (55 files)
│   ├── layout_admin.html     # Base template for admin portal
│   ├── layout_student.html   # Base template for student portal
│   ├── admin_*.html          # Admin portal templates
│   ├── student_*.html        # Student portal templates
│   └── error_*.html          # Custom error pages (400-503)
│
├── static/                   # Frontend assets
│   └── js/attendance.js      # Real-time attendance UI
│
├── migrations/               # Database migrations
│   ├── env.py
│   └── versions/             # 23 migration files
│
├── tests/                    # Pytest test suite (8 test files)
│   ├── conftest.py
│   ├── test_attendance.py
│   ├── test_payroll.py
│   └── ...
│
├── scripts/                  # Utility scripts
│   ├── update_packages.sh
│   └── dev-utilities/        # Development-only scripts
│       ├── README.md         # WARNING: DANGEROUS SCRIPTS
│       ├── reset_database.py
│       └── diagnose_migrations.py
│
└── docs/                     # Documentation
    ├── README.md             # Master documentation index
    ├── DEPLOYMENT.md         # Deployment guide
    ├── user-guides/
    ├── technical-reference/
    └── development/
```

### Application Factory Pattern

The application uses the factory pattern for initialization:

```python
# app/__init__.py
def create_app():
    app = Flask(__name__)

    # Load configuration
    # Initialize extensions (db, migrate, csrf)
    # Register blueprints
    # Configure logging
    # Register Jinja filters
    # Register error handlers

    return app

# wsgi.py
from app import create_app
app = create_app()
```

### Blueprint Organization

Routes are organized by user role:

- **student.py** - Student portal routes (prefix: `/student/`)
- **admin.py** - Teacher portal routes (prefix: `/admin/`)
- **system_admin.py** - System admin routes (prefix: `/sysadmin/`)
- **main.py** - Public routes (login, logout, setup, health)
- **api.py** - REST API endpoints (prefix: `/api/`)

---

## Key Conventions & Patterns

### Database Models

All models are defined in `app/models.py`. Key models:

**User Models:**
- `Student` - Student accounts with encrypted PII
- `Admin` - Teacher accounts with TOTP
- `SystemAdmin` - Super-user accounts

**Financial Models:**
- `Transaction` - Financial transaction log
- `StoreItem` - Classroom store items
- `StudentItem` - Student purchases

**Attendance Models:**
- `TapEvent` - Attendance tap in/out records
- `HallPassLog` - Hall pass tracking

**Feature Models:**
- `InsurancePolicy`, `StudentInsurance`, `InsuranceClaim` - Insurance system
- `RentSettings`, `RentPayment` - Rent system

**System Models:**
- `ErrorLog` - System error logging
- `AdminInvite` - Admin invitation system

### Authentication Decorators

Defined in `app/auth.py`:

- `@login_required` - Requires student session
- `@admin_required` - Requires admin session
- `@system_admin_required` - Requires system admin session

### PII Encryption

Student names use `PIIEncryptedType` custom SQLAlchemy type (in `app/utils/encryption.py`):
- Automatically encrypts on save
- Automatically decrypts on load
- Uses ENCRYPTION_KEY from environment

### Timezone Handling

- User timezones stored in session via `/api/set-timezone` endpoint
- Use `convert_to_user_timezone()` for all timestamps displayed to users
- Database stores all timestamps in UTC

### Transaction Logging

ALL financial changes must be logged to the `Transaction` table:

```python
from app.models import Transaction
from app.extensions import db
from datetime import datetime

transaction = Transaction(
    student_id=student.id,
    amount=amount,
    account_type='checking',  # or 'savings'
    description='Description of transaction',
    type='payroll',  # or 'bonus', 'purchase', 'fee', etc.
    timestamp=datetime.utcnow()
)
db.session.add(transaction)
db.session.commit()
```

### Password/PIN Hashing

Use `hash_utils.py` functions:
```python
from hash_utils import hash_credential

# Hash with salt and pepper
hashed = hash_credential(value, salt, pepper)
```

**Rules:**
- Never store plain text credentials
- Always use the PEPPER_KEY from environment
- Use unique salt per user

---

## Security Architecture

### Critical Security Rules

**ALWAYS:**

1. **Validate user input** - Use WTForms validation, never trust client data
2. **Use parameterized queries** - SQLAlchemy ORM prevents SQL injection
3. **Check authorization** - Verify user has permission before any sensitive operation
4. **Log financial transactions** - Every balance change MUST have a Transaction record
5. **Encrypt PII** - Use PIIEncryptedType for any personally identifiable information
6. **Use CSRF tokens** - Flask-WTF handles this, ensure forms include csrf_token
7. **Hash credentials** - Use hash_utils.py with salt and pepper
8. **Test error cases** - Security bugs often hide in error paths

**NEVER:**

1. **Commit secrets** - No API keys, passwords, or encryption keys in git
2. **Skip authentication checks** - Every route must verify user identity/role
3. **Trust client-side validation** - Always validate server-side
4. **Use string formatting for SQL** - Use SQLAlchemy ORM only
5. **Deploy dev scripts** - reset_database.py scripts are DEV ONLY
6. **Modify transactions directly** - Use void flag instead of deleting
7. **Expose stack traces** - Use custom error pages (already implemented)
8. **Hard-code configuration** - Use environment variables

### Error Handling & Logging

**Custom Error Pages:**
- 400 (Bad Request)
- 401 (Unauthorized)
- 403 (Forbidden)
- 404 (Not Found)
- 500 (Internal Server Error)
- 503 (Service Unavailable)

**Database Error Logging:**
All errors are automatically logged to the `ErrorLog` table with:
- Timestamp
- Error type and message
- Request details (URL, method)
- User agent and IP address
- Stack trace
- Last 50 lines of application logs

**System Admin Features:**
- View paginated, filterable error logs
- Test error pages safely
- Monitor system health

---

## Database Architecture

### Core Financial Flow

1. Student taps in → `TapEvent` created (status: 'in')
2. Student taps out → `TapEvent` updated (status: 'out', duration calculated)
3. Payroll runs → Calculates earnings from `TapEvent` records
4. Earnings deposited → `Transaction` created (type: 'payroll')
5. Student purchases item → `Transaction` created (type: 'purchase'), `StudentItem` created

### Important Relationships

- `Student.transactions` - All transactions for a student
- `Student.tap_events` - All attendance records
- `Student.student_items` - All purchased store items
- Future: `Student.teacher_id` - Multi-tenancy support (see docs/development/MULTI_TENANCY_TODO.md)

### Migration Management

```bash
# Create new migration
flask db migrate -m "Description of changes"

# Review the generated migration in migrations/versions/
# Edit if necessary, then apply:
flask db upgrade

# Rollback if needed
flask db downgrade
```

**Best Practices:**
- Always review generated migrations before applying
- Test migrations in development first
- Never edit migrations that have been applied to production
- Use descriptive migration messages

---

## Authentication System

### Three-Tier Authentication

**1. Student Authentication:**
- PIN (4-6 digits) + Passphrase (8+ characters)
- Custom implementation with salt and pepper
- Session-based with timeout
- First-time setup flow for new students

**2. Admin (Teacher) Authentication:**
- TOTP-based (Time-Based One-Time Password)
- QR code generation for authenticator apps
- Session-based with timeout
- Invite-based signup only

**3. System Admin Authentication:**
- TOTP-based (same as admins)
- Invite-based signup with special system admin invites
- Full access to all features
- Can manage teachers and view system logs

### Session Management

Sessions are stored server-side with the following keys:

**Student Sessions:**
- `student_id` - Student database ID
- `student_username` - Student username
- `user_timezone` - User's timezone (set via JavaScript)

**Admin Sessions:**
- `admin_id` - Admin database ID
- `admin_username` - Admin username
- `user_timezone` - User's timezone

**System Admin Sessions:**
- `system_admin_id` - System admin database ID
- `system_admin_username` - System admin username
- `user_timezone` - User's timezone

### Session Timeouts

- Student sessions: 60 minutes of inactivity
- Admin sessions: 60 minutes of inactivity
- System admin sessions: 60 minutes of inactivity

---

## Development Guidelines

### Git Workflow

**Branch Strategy:**
- Main branch: `main` (production)
- Feature branches: `claude/feature-name-SESSION_ID`
- Always develop on the designated branch

**Commit Message Format:**
```
Add payroll settings UI for configurable pay rates

- Created PayrollSettings model
- Added admin interface at /admin/payroll/settings
- Updated payroll.py to read from database settings
- Added migration for new table
```

**Before Committing:**
1. Run tests: `pytest tests/`
2. Check for secrets: Review .gitignore coverage
3. Update TODO.md: Move completed tasks to "Recently Completed"
4. Add session notes: Document what was done

**Pushing Changes:**
- Use: `git push -u origin <branch-name>`
- Branch must start with 'claude/' and end with session ID
- Retry up to 4 times with exponential backoff on network errors

### Code Quality Standards

**Python Style:**
- Follow PEP 8 conventions
- Use descriptive variable names
- Add docstrings to functions
- Type hints are encouraged

**Route Structure:**
```python
from app.routes.admin import admin_bp
from app.auth import admin_required
from flask import render_template, request, redirect, url_for, flash, session

@admin_bp.route('/feature', methods=['GET', 'POST'])
@admin_required
def admin_feature():
    """Brief description of what this route does."""
    admin_username = session.get('admin_username')

    # GET request - display form/data
    if request.method == 'GET':
        # ... logic ...
        return render_template('admin_feature.html', data=data)

    # POST request - process form
    if request.method == 'POST':
        # Validate input
        # Process data
        # Log transactions if financial
        # Flash success/error message
        # Redirect to appropriate page
        return redirect(url_for('admin.admin_feature'))
```

**Template Structure:**
- Extend base templates (`layout_admin.html`, `layout_student.html`)
- Use template inheritance to avoid duplication
- Include CSRF tokens in all forms: `{{ form.csrf_token }}`
- Use flash messages for user feedback

**Error Handling:**
```python
from app.extensions import db
from flask import flash
import logging

logger = logging.getLogger(__name__)

try:
    # ... operation ...
    db.session.commit()
    flash('Success message', 'success')
except Exception as e:
    db.session.rollback()
    logger.error(f"Error in operation: {str(e)}")
    flash('Error message', 'danger')
```

### Testing Guidelines

**Writing Tests:**
- Location: `/tests/test_*.py`
- Use pytest fixtures for setup/teardown
- Test both success and failure cases
- Include edge cases and boundary conditions

**Test Coverage Priorities:**
1. Authentication and authorization
2. Financial transactions (accuracy is critical!)
3. Payroll calculations
4. Data validation and input sanitization
5. PII encryption/decryption

**Running Tests:**
```bash
pytest tests/                    # Run all tests
pytest tests/test_payroll.py    # Run specific test file
pytest -v                        # Verbose output
pytest --cov=app                # With coverage report
```

### Common Development Tasks

**Running Locally:**
```bash
# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env file with required variables
# Run migrations
flask db upgrade

# Create first system admin
flask create-sysadmin

# Run application
flask run
```

**Seeding Test Data:**
```bash
python seed_dummy_students.py   # Creates sample students
```

**Creating Admin Accounts:**
```bash
python create_admin.py          # Interactive CLI
python manage_invites.py        # Manage invite codes
```

### Deployment

**Environment Variables Required:**
```bash
SECRET_KEY=<random-string>
DATABASE_URL=postgresql://user:password@host:port/dbname
FLASK_ENV=production
ENCRYPTION_KEY=<32-byte-base64-key>
PEPPER_KEY=<secret-pepper>
CSRF_SECRET_KEY=<random-string>
LOG_LEVEL=INFO
```

**Deployment Checklist:**
- [ ] All tests passing
- [ ] Migrations applied
- [ ] Environment variables configured
- [ ] ENCRYPTION_KEY and PEPPER_KEY backed up securely
- [ ] Error logging configured
- [ ] Health endpoint responding: `/health`

**Production Deployment:**
```bash
# DigitalOcean (automated via GitHub Actions on push to main)
# Manual deployment:
flask db upgrade
gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app
```

---

## Known Technical Debt

### Current Issues

1. **Hardcoded pay rates** - Should be configurable in admin panel (HIGH PRIORITY)
2. **No teacher data isolation** - All admins see all students (multi-tenancy planned)
3. **Limited pagination** - Performance issues with large datasets
4. **Minimal test coverage** - Need more comprehensive tests
5. **No audit logging** - Need to track admin actions for compliance

### Important Context

- **Multi-tenancy:** Planned but not yet implemented - will add `teacher_id` to students
- **Payroll schedule:** Hardcoded to 14 days, needs configuration UI
- **Insurance system:** Frontend complete, backend partially implemented

### Watch Out For

- **Timezone conversions:** Always use UTC in database, convert for display
- **Transaction voids:** Use `is_void` flag, don't delete transactions
- **Migration conflicts:** Review migrations carefully before applying
- **Session data:** Student/admin sessions are separate, can't mix
- **CSV uploads:** Use `student_upload_template.csv` format

---

## Best Practices for AI Agents

### Before Starting Any Task

1. Read the relevant documentation (especially docs/development/TODO.md)
2. Search the codebase for similar existing implementations
3. Review the database schema for affected tables
4. Check for related tests
5. Understand the user impact

### During Implementation

1. Follow existing code patterns and conventions
2. Test as you go (don't wait until the end)
3. Log important operations
4. Handle errors gracefully
5. Consider edge cases
6. Think about security implications

### Before Completing

1. Run the full test suite
2. Test manually in the UI (if applicable)
3. Update documentation (README.md, TODO.md, docstrings)
4. Review your code for security issues
5. Check for accidental commits of sensitive data
6. Write clear commit messages

---

## Domain Knowledge

### Educational Context

This is a **classroom economy simulation** where:

- Students earn "money" by attending class (tracked via tap in/out)
- They can spend on store items, hall passes, insurance, etc.
- Teachers (admins) manage the economy and set rules
- System admins oversee multiple teachers

### Key Concepts

- **Tap In/Out:** Students scan a code to mark attendance
- **Payroll:** Automated calculation based on attendance time
- **Transactions:** All money movements (deposits, withdrawals, transfers)
- **Store Items:** Virtual or physical items students can purchase
- **Hall Passes:** Time-based passes for leaving class
- **Insurance:** Optional protection against fines/fees
- **Rent/Property Tax:** Optional recurring charges

### User Roles

**1. Students:**
- Limited privileges
- Can view own data, make purchases, manage account
- Authenticate with PIN + passphrase

**2. Admins (Teachers):**
- Manage their classroom(s)
- Currently see ALL students (multi-tenancy will change this)
- Configure settings, run payroll, approve purchases
- Authenticate with TOTP

**3. System Admins:**
- Manage admin accounts
- View system logs and errors
- Generate invite codes
- Access all features
- Authenticate with TOTP

---

## Quick Reference Commands

```bash
# Development
flask run                          # Run development server
flask db upgrade                   # Apply migrations
flask db migrate -m "message"      # Create migration
flask create-sysadmin              # Create system admin
pytest tests/ -v                   # Run tests

# Database
python seed_dummy_students.py      # Seed test data
python scripts/dev-utilities/diagnose_migrations.py  # Check migration chain
python create_admin.py             # Create admin account
python manage_invites.py           # Manage invite codes

# Deployment
gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app

# Dependencies
./scripts/update_packages.sh       # Update and test packages
pip freeze > requirements.txt      # Update requirements

# Git
git status                         # Check status
git add .                          # Stage changes
git commit -m "message"            # Commit
git push -u origin branch-name     # Push changes
```

---

## Final Notes

### Remember:

- **Students are using this in real classrooms** - Quality and reliability matter
- **Security is paramount** - Student data must be protected
- **Document everything** - Future developers will thank you
- **Test thoroughly** - Financial accuracy is critical
- **Keep TODO.md updated** - It's the source of truth for project status

### Philosophy:

- Favor clarity over cleverness
- Prefer established patterns over new approaches
- Think about the teacher and student experience
- Consider scalability (multi-tenancy coming soon)
- Maintain the educational mission of the project

---

**Last Updated:** 2025-11-19
**Maintained by:** AI agents and project maintainers
**Questions?** Check docs/development/TODO.md or other documentation in `/docs/`
