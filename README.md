# 🎓 Classroom Token Hub

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

⚠️ **Note:** This repository is currently private and under active development for controlled classroom testing.

---

## Overview

**Classroom Token Hub** is an educational banking simulation that helps students learn financial literacy through hands-on experience. Students earn tokens by attending class, which they can spend in a classroom store, use for hall passes, or manage through savings and checking accounts.

**License:** [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) - Free for educational and nonprofit use, not for commercial applications.

---

## Features

### Core Features

- **System Admin Portal** - Manage teachers, view logs, monitor errors
- **Teacher Dashboard** - Manage students, run payroll, configure settings
- **Student Portal** - View balance, make purchases, track attendance
- **Attendance Tracking** - Tap in/out system with automatic time logging
- **Automated Payroll** - Calculate and distribute earnings based on attendance
- **Transaction Logging** - Complete audit trail of all financial activities
- **Classroom Store** - Virtual and physical items for purchase
- **Hall Pass System** - Time-limited passes with automatic tracking
- **Insurance System** - Optional protection against fines and fees
- **Rent & Property Tax** - Optional recurring charges for advanced economics
- **TOTP Authentication** - Secure admin access with two-factor authentication

### Security Features

- **PII Encryption** - All student names encrypted at rest
- **TOTP for Admins** - Time-based one-time passwords required
- **CSRF Protection** - Protection against cross-site request forgery
- **Credential Hashing** - Salted and peppered password hashing
- **Database Error Logging** - Automatic error tracking and monitoring
- **Custom Error Pages** - User-friendly error handling (400, 401, 403, 404, 500, 503)

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL database
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd classroom-economy
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in the root directory:
   ```bash
   SECRET_KEY=<long-random-string>
   DATABASE_URL=postgresql://user:password@host:port/dbname
   FLASK_ENV=development
   ENCRYPTION_KEY=<32-byte-base64-key>  # Generate with: openssl rand -base64 32
   PEPPER_KEY=<secret-pepper-string>
   CSRF_SECRET_KEY=<random-string>
   ```

4. **Initialize the database**
   ```bash
   flask db upgrade
   ```

5. **Create your first system admin**
   ```bash
   flask create-sysadmin
   ```
   Follow the prompts and scan the QR code with your authenticator app.

6. **Run the application**
   ```bash
   flask run
   ```
   Navigate to `http://localhost:5000`

### Testing with Sample Data

- Use `student_upload_template.csv` as a reference for CSV roster uploads
- Run `python seed_dummy_students.py` to seed the database with sample students

---

## Documentation

📚 **[Complete Documentation →](docs/README.md)**

### For Users

- **[Student Guide](docs/user-guides/student_guide.md)** - How students use the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** - Comprehensive admin guide

### For Developers

- **[Architecture Guide](docs/technical-reference/architecture.md)** - System design and patterns
- **[Database Schema](docs/technical-reference/database_schema.md)** - Complete database reference
- **[API Reference](docs/technical-reference/api_reference.md)** - REST API documentation
- **[Development TODO](docs/development/TODO.md)** - Current tasks and priorities

### Deployment

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project

---

## Technology Stack

**Backend:**
- Flask 3.1.0 (Python web framework)
- SQLAlchemy 2.0.40 (ORM)
- PostgreSQL (Database)
- Gunicorn (WSGI server)

**Frontend:**
- Jinja2 templates
- Bootstrap 5
- Material Symbols icons
- Minimal JavaScript

**Security:**
- Flask-WTF (CSRF protection)
- pyotp (TOTP authentication)
- cryptography (PII encryption)

**Testing:**
- pytest
- pytest-flask

**Deployment:**
- Docker support
- GitHub Actions CI/CD
- DigitalOcean production hosting

---

## Project Structure

```
classroom-economy/
├── app/                      # Main application package
│   ├── __init__.py           # Application factory
│   ├── extensions.py         # Flask extensions
│   ├── models.py             # Database models
│   ├── auth.py               # Authentication decorators
│   ├── routes/               # Blueprint-based routes
│   │   ├── admin.py          # Teacher portal
│   │   ├── student.py        # Student portal
│   │   ├── system_admin.py   # System admin portal
│   │   ├── main.py           # Public routes
│   │   └── api.py            # REST API
│   └── utils/                # Utilities
├── templates/                # Jinja2 templates
├── static/                   # CSS, JS, images
├── tests/                    # Test suite
├── migrations/               # Database migrations
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── wsgi.py                   # WSGI entry point
└── requirements.txt          # Python dependencies
```

---

## Development

### Running Tests

```bash
pytest tests/                 # Run all tests
pytest tests/test_payroll.py  # Run specific test
pytest -v                     # Verbose output
```

### Database Migrations

```bash
flask db migrate -m "Description"  # Create migration
flask db upgrade                   # Apply migrations
flask db downgrade                 # Rollback
```

### Common Commands

```bash
flask run                     # Run development server
flask create-sysadmin         # Create system admin
python create_admin.py        # Create teacher account
python manage_invites.py      # Manage admin invites
python seed_dummy_students.py # Seed test data
```

---

## Roadmap

### High Priority
- [ ] Configurable payroll settings (rates, schedule)
- [ ] Account recovery system for students
- [ ] Multi-tenancy (teacher data isolation)
- [ ] Comprehensive test coverage

### Medium Priority
- [ ] Email notifications
- [ ] Audit logging for admin actions
- [ ] CSV export functionality
- [ ] Mobile-responsive redesign

### Future Features
- [ ] Stock market simulation
- [ ] Loan system with interest
- [ ] Student-to-student transfers
- [ ] Leaderboards and achievements

See [docs/development/TODO.md](docs/development/TODO.md) for complete task list with estimates.

---

## Monitoring

Deploy behind a production web server (e.g., NGINX). The `/health` endpoint returns a 200 status when the database is reachable.

```bash
curl http://your-domain/health
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Before contributing:**
1. Review the [Architecture Guide](docs/technical-reference/architecture.md)
2. Check [TODO.md](docs/development/TODO.md) for current priorities
3. Ensure all tests pass
4. Follow the existing code style

---

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

### ✅ You CAN:
- Use in classrooms, clubs, and nonprofit educational settings
- Modify for school use, assignments, or personal learning
- Share with students or other educators
- Use for research or academic presentations (non-commercial)

### ❌ You CANNOT:
- Use as part of a commercial product or SaaS platform
- Host a paid service or subscription
- Incorporate into revenue-generating offerings
- Use internally within for-profit businesses

---

## Support

**Documentation:** [docs/README.md](docs/README.md)
**Issues:** Use GitHub Issues for bug reports and feature requests
**Security:** Report security issues privately to project maintainers

---

## Acknowledgments

Built for educators and students to make learning about finance engaging and practical.

**Last Updated:** 2025-11-19
