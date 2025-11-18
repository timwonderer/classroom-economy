# AI Agent Instructions for Classroom Token Hub

**Last Updated:** 2025-11-18
**Purpose:** Guide for AI assistants working on this educational platform

---

## 🎯 Project Overview

**Classroom Token Hub** is an educational banking and classroom management platform that teaches students about money while tracking classroom participation. It features attendance tracking, automated payroll, transactions, a classroom store, insurance systems, hall passes, and more.

**License:** PolyForm Noncommercial 1.0.0 - Educational and nonprofit use only. No commercial applications.

**Production Status:** Active development for controlled classroom testing. This is a REAL application used by students, so code quality and security are critical.

---

## 📚 Essential Reading

Before starting any work, familiarize yourself with these files:

1. **README.md** - Project overview, setup instructions, current features
2. **TODO.md** - Comprehensive task list with priorities and effort estimates (UPDATE THIS REGULARLY!)
3. **docs/database_schema.md** - Complete database structure and model documentation
4. **docs/api_reference.md** - All API endpoints and their specifications
5. **docs/teacher_manual.md** - How teachers use the system (understand the user perspective)
6. **docs/MULTI_TENANCY_TODO.md** - Important upcoming feature (multi-teacher support)
7. **INSURANCE_SYSTEM_STATUS.md** - Insurance feature status (frontend done, backend partial)

---

## 🏗️ Architecture Overview

### Technology Stack

**Backend:**
- Flask 3.1.0 (Python web framework)
- SQLAlchemy 2.0.40 (ORM) + Alembic (migrations)
- PostgreSQL (production database)
- Gunicorn 23.0.0 with gevent workers

**Authentication:**
- Admins: TOTP (pyotp 2.9.0) - all admin accounts MUST use TOTP
- Students: PIN + passphrase (custom implementation)
- System Admins: TOTP with invite-based signup

**Security:**
- PII encryption using `cryptography` library and ENCRYPTION_KEY
- Credential hashing with PEPPER_KEY for additional security
- CSRF protection via Flask-WTF
- All student names are encrypted at rest

**Frontend:**
- Jinja2 3.1.6 templating
- Minimal JavaScript (attendance.js for real-time features)
- Bootstrap-based UI

**Testing:**
- pytest 8.4.0 + pytest-flask 1.3.0
- Tests located in `/tests/` directory

**Deployment:**
- Primary: Fly.io (configured via fly.toml)
- Docker support (Dockerfile)
- CI/CD via GitHub Actions (.github/workflows/)

### Project Structure

```
classroom-economy/
├── app.py                    # MAIN APPLICATION (4,583 lines - needs refactoring!)
├── forms.py                  # WTForms definitions for all forms
├── payroll.py                # Payroll calculation logic
├── attendance.py             # Attendance tracking logic
├── hash_utils.py             # Cryptographic utilities
├── create_admin.py           # CLI tool for creating admin accounts
├── manage_invites.py         # Admin invite management CLI
├── seed_dummy_students.py    # Test data seeding utility
├── reset_database*.py        # Database reset scripts (DEV ONLY - DANGEROUS!)
├── templates/                # Jinja2 HTML templates (55 files)
├── static/                   # Frontend assets
│   └── js/attendance.js      # Real-time attendance UI
├── migrations/versions/      # Alembic database migrations (23 files)
├── tests/                    # Pytest test suite
├── scripts/                  # Utility scripts
├── docs/                     # Comprehensive documentation
└── student_upload_template.csv  # Template for CSV roster uploads
```

---

## 🔑 Key Conventions & Patterns

### Database Models (SQLAlchemy)

All models are defined in `app.py`. Key models:

- `Student` - Student accounts with encrypted PII
- `Admin` - Teacher accounts with TOTP
- `SystemAdmin` - Super-user accounts
- `Transaction` - Financial transaction log
- `TapEvent` - Attendance tap in/out records
- `InsurancePolicy`, `StudentInsurance`, `InsuranceClaim` - Insurance system
- `StoreItem`, `StudentItem` - Classroom store
- `HallPassLog` - Hall pass tracking
- `RentSettings`, `RentPayment` - Rent system
- `ErrorLog` - System error logging

### Authentication Decorators

- `@login_required` - Requires student session
- `@admin_required` - Requires admin session
- `@system_admin_required` - Requires system admin session

### PII Encryption

Student names use `PIIEncryptedType` custom SQLAlchemy type:
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
transaction = Transaction(
    student_id=student.id,
    amount=amount,
    account_type='checking',  # or 'savings'
    description='Description of transaction',
    type='payroll',  # or 'bonus', 'purchase', 'fee', etc.
    timestamp=datetime.utcnow()
)
db.session.add(transaction)
```

### Password/PIN Hashing

Use `hash_utils.py` functions:
- `hash_credential(value, salt, pepper)` - Hash with salt and pepper
- Never store plain text credentials
- Always use the PEPPER_KEY from environment

---

## ⚠️ Critical Security Rules

### ALWAYS:

1. **Validate user input** - Use WTForms validation, never trust client data
2. **Use parameterized queries** - SQLAlchemy ORM prevents SQL injection, but verify
3. **Check authorization** - Verify user has permission before any sensitive operation
4. **Log financial transactions** - Every balance change MUST have a Transaction record
5. **Encrypt PII** - Use PIIEncryptedType for any personally identifiable information
6. **Use CSRF tokens** - Flask-WTF handles this, ensure forms include csrf_token
7. **Hash credentials** - Use hash_utils.py with salt and pepper
8. **Test error cases** - Security bugs often hide in error paths

### NEVER:

1. **Commit secrets** - No API keys, passwords, or encryption keys in git
2. **Skip authentication checks** - Every route must verify user identity/role
3. **Trust client-side validation** - Always validate server-side
4. **Use string formatting for SQL** - Use SQLAlchemy ORM only
5. **Deploy reset_database.py scripts** - These are DEV ONLY utilities
6. **Modify transactions directly** - Use void flag instead of deleting
7. **Expose stack traces to users** - Use custom error pages (already implemented)
8. **Hard-code configuration** - Use environment variables

---

## 🔄 Git Workflow

### Branch Strategy

- Main branch: `main` (production)
- Feature branches: `claude/feature-name-SESSION_ID`
- Always develop on the designated branch provided in task context

### Commit Message Format

Use descriptive commit messages:
```
Add payroll settings UI for configurable pay rates

- Created PayrollSettings model
- Added admin interface at /admin/payroll/settings
- Updated payroll.py to read from database settings
- Added migration for new table
```

### Before Committing:

1. **Run tests:** `pytest tests/`
2. **Check for secrets:** Review .gitignore coverage
3. **Update TODO.md:** Move completed tasks to "Recently Completed"
4. **Add session notes:** Document what was done in TODO.md

### Pushing Changes:

- Use: `git push -u origin <branch-name>`
- Branch must start with 'claude/' and end with session ID
- Retry up to 4 times with exponential backoff (2s, 4s, 8s, 16s) on network errors

---

## 🛠️ Common Development Tasks

### Running the Application Locally

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

### Database Migrations

```bash
# Create new migration
flask db migrate -m "Description of changes"

# Review the generated migration in migrations/versions/
# Edit if necessary, then apply:
flask db upgrade

# Rollback if needed
flask db downgrade
```

### Running Tests

```bash
pytest tests/                    # Run all tests
pytest tests/test_payroll.py    # Run specific test file
pytest -v                        # Verbose output
pytest --cov=app                # With coverage report
```

### Seeding Test Data

```bash
python seed_dummy_students.py   # Creates sample students
```

### Creating Admin Accounts

```bash
python create_admin.py          # Interactive CLI
python manage_invites.py        # Manage invite codes
```

---

## 📝 Code Quality Standards

### Python Style

- Follow PEP 8 conventions
- Use descriptive variable names
- Add docstrings to functions
- Type hints are encouraged (see TODO.md - Technical Debt)

### Route Structure

```python
@app.route('/admin/feature', methods=['GET', 'POST'])
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
        return redirect(url_for('admin_feature'))
```

### Template Structure

- Extend base templates (`admin_base.html`, `student_base.html`)
- Use template inheritance to avoid duplication
- Include CSRF tokens in all forms: `{{ form.csrf_token }}`
- Use flash messages for user feedback

### Error Handling

```python
try:
    # ... operation ...
    db.session.commit()
    flash('Success message', 'success')
except Exception as e:
    db.session.rollback()
    app.logger.error(f"Error in operation: {str(e)}")
    flash('Error message', 'danger')
```

---

## 🧪 Testing Guidelines

### Writing Tests

- Location: `/tests/test_*.py`
- Use pytest fixtures for setup/teardown
- Test both success and failure cases
- Include edge cases and boundary conditions

### Test Coverage Priorities

1. Authentication and authorization
2. Financial transactions (accuracy is critical!)
3. Payroll calculations
4. Data validation and input sanitization
5. PII encryption/decryption

### Running Tests Before Committing

```bash
pytest tests/ -v
# All tests must pass before pushing
```

---

## 📊 Database Schema Quick Reference

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
- `Admin.id` - Will become `Student.teacher_id` (see MULTI_TENANCY_TODO.md)

---

## 🚨 Known Issues & Gotchas

### Current Technical Debt

1. **app.py is 4,583 lines** - Desperately needs refactoring into modules
2. **No teacher data isolation** - All admins see all students (multi-tenancy coming)
3. **Hardcoded pay rates** - Should be configurable (see TODO.md priority #1)
4. **Limited pagination** - Performance issues with large datasets
5. **Minimal test coverage** - Need more comprehensive tests

### Important Context

- **Insurance system:** Frontend templates complete, backend routes partially implemented
- **Multi-tenancy:** Planned but not yet implemented - will add `teacher_id` to students
- **Payroll schedule:** Hardcoded to 14 days, needs configuration UI

### Watch Out For

- **Timezone conversions:** Always use UTC in database, convert for display
- **Transaction voids:** Use `is_void` flag, don't delete transactions
- **Migration conflicts:** Review migrations carefully before applying
- **Session data:** Student/admin sessions are separate, can't mix
- **CSV uploads:** Use `student_upload_template.csv` format

---

## 🎯 Working with TODO.md

### CRITICAL: Always Update TODO.md

1. **At session start:**
   - Review TODO.md for current priorities
   - Check "Next Session Priorities" section
   - Verify you understand the task context

2. **During development:**
   - Mark tasks as in-progress
   - Add new issues as discovered
   - Update effort estimates if significantly different

3. **At session end:**
   - Move completed tasks to "Recently Completed" with date
   - Add session notes with date and summary
   - Update "Next Session Priorities" for next developer

### TODO.md Structure

- 🔴 Critical Bugs - Fix immediately
- 🟠 High Priority - Core feature additions (30-42 hours estimated)
- 🟡 Medium Priority - Important features (32-44 hours estimated)
- 🟢 Lower Priority - Quality of life (18-26 hours estimated)
- 📋 Roadmap - Future features (50-70 hours estimated)
- 🔧 Technical Debt - Code quality and refactoring
- ✅ Recently Completed - Track what's done

---

## 🔍 Debugging & Troubleshooting

### Logs

Production logs are in application logs (configured via LOG_FILE env var)

```python
app.logger.info("Info message")
app.logger.warning("Warning message")
app.logger.error("Error message")
```

### Database Issues

```bash
# Check migration status
flask db current

# View migration history
flask db history

# Diagnose migration chain
python diagnose_migrations.py
```

### Common Issues

1. **Migration conflicts:** Run `diagnose_migrations.py`, may need to resolve manually
2. **TOTP issues:** Verify system clock is accurate (TOTP is time-based)
3. **Encryption errors:** Check ENCRYPTION_KEY is consistent across deployments
4. **Session issues:** Check SECRET_KEY is set and consistent

---

## 📦 Dependencies Management

### Updating Dependencies

```bash
# Review and update packages
./scripts/update_packages.sh

# This will:
# 1. Upgrade packages
# 2. Run tests
# 3. Update requirements.txt if tests pass
```

### Adding New Dependencies

1. Install in virtual environment: `pip install package-name`
2. Add to requirements.txt: `pip freeze > requirements.txt`
3. Document why the dependency is needed
4. Test thoroughly
5. Commit requirements.txt changes

---

## 🚀 Deployment

### Environment Variables Required

```bash
SECRET_KEY=<random-string>
DATABASE_URL=postgresql://user:password@host:port/dbname
FLASK_ENV=production
ENCRYPTION_KEY=<32-byte-base64-key>
PEPPER_KEY=<secret-pepper>
LOG_LEVEL=INFO
```

### Deployment Checklist

- [ ] All tests passing
- [ ] Migrations applied
- [ ] Environment variables configured
- [ ] ENCRYPTION_KEY and PEPPER_KEY backed up securely
- [ ] Error logging configured
- [ ] Health endpoint responding: `/health`

### Deployment Platforms

- **Fly.io (Primary):** Configured in `fly.toml`
- **Heroku (Supported):** Configured in `Procfile`
- **Docker:** `Dockerfile` available

---

## 💡 Best Practices for AI Agents

### Before Starting Any Task

1. Read the relevant documentation (especially TODO.md)
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

### Communication

- Be specific about file names and line numbers
- Explain WHY changes are needed, not just WHAT
- Point out potential issues or risks
- Suggest testing strategies
- Document assumptions

---

## 🎓 Domain Knowledge

### Educational Context

This is a **classroom economy simulation** where:

- Students earn "money" by attending class (tracked via tap in/out)
- They can spend on store items, hall passes, insurance, etc.
- Teachers (admins) manage the economy and set rules
- System admins oversee multiple teachers (future: multi-tenancy)

### Key Concepts

- **Tap In/Out:** Students scan a code to mark attendance
- **Payroll:** Automated calculation based on attendance time
- **Transactions:** All money movements (deposits, withdrawals, transfers)
- **Store Items:** Virtual or physical items students can purchase
- **Hall Passes:** Time-based passes for leaving class
- **Insurance:** Optional protection against fines/fees
- **Rent/Property Tax:** Optional recurring charges

### User Roles

1. **Students:**
   - Limited privileges
   - Can view own data, make purchases, manage account
   - Authenticate with PIN + passphrase

2. **Admins (Teachers):**
   - Manage their classroom(s)
   - Currently see ALL students (multi-tenancy will change this)
   - Configure settings, run payroll, approve purchases
   - Authenticate with TOTP

3. **System Admins:**
   - Manage admin accounts
   - View system logs and errors
   - Generate invite codes
   - Access all features
   - Authenticate with TOTP

---

## 📞 Getting Help

### Documentation Resources

1. `/docs/` directory - Comprehensive technical docs
2. `README.md` - Setup and overview
3. `TODO.md` - Current priorities and session notes
4. `MIGRATION_GUIDE.md` - Database migration help
5. `DEPLOYMENT.md` - Deployment instructions
6. `CODE_REVIEW.md` - Code review checklist
7. `CONTRIBUTING.md` - Contribution guidelines

### Code Navigation

- **Search for similar features:** Use grep/search to find existing implementations
- **Follow the data:** Trace from database model → route → template
- **Check git history:** `git log` and `git blame` can show why things were done

### When Stuck

1. Search for error messages in the code
2. Check error logs in database (`ErrorLog` model)
3. Review related tests for expected behavior
4. Look for similar implementations elsewhere in codebase
5. Check TODO.md for known issues or planned work

---

## ✅ Pre-Commit Checklist

Before committing code, verify:

- [ ] Code follows project conventions and style
- [ ] All tests pass (`pytest tests/`)
- [ ] No secrets or sensitive data in commits
- [ ] Relevant documentation updated (README.md, TODO.md, docstrings)
- [ ] Database migrations created and tested (if schema changed)
- [ ] Error handling implemented
- [ ] Security considerations addressed
- [ ] Transaction logging added (if financial changes)
- [ ] User feedback messages added (flash messages)
- [ ] Edge cases considered and tested
- [ ] No debug print statements or commented-out code
- [ ] .gitignore covers any new file types
- [ ] Session notes added to TODO.md

---

## 🎯 Quick Reference Commands

```bash
# Development
flask run                          # Run development server
flask db upgrade                   # Apply migrations
flask db migrate -m "message"      # Create migration
flask create-sysadmin              # Create system admin
pytest tests/ -v                   # Run tests

# Database
python seed_dummy_students.py      # Seed test data
python diagnose_migrations.py      # Check migration chain
python create_admin.py             # Create admin account
python manage_invites.py           # Manage invite codes

# Deployment
gunicorn --bind=0.0.0.0 --timeout 600 app:app

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

## 🏁 Final Notes

### Remember:

- **Students are using this in real classrooms** - Quality and reliability matter
- **Security is paramount** - Student data must be protected
- **Document everything** - Future developers (AI or human) will thank you
- **Test thoroughly** - Financial accuracy is critical
- **Keep TODO.md updated** - It's the source of truth for project status

### Philosophy:

- Favor clarity over cleverness
- Prefer established patterns over new approaches
- Think about the teacher and student experience
- Consider scalability (multi-tenancy coming soon)
- Maintain the educational mission of the project

---

**Last Updated:** 2025-11-18
**Maintained by:** AI agents and project maintainers
**Questions?** Check TODO.md session notes or documentation in `/docs/`
