# 🎓 Classroom Token Hub

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

**Version:** 1.2.0

---

## Overview

**Classroom Token Hub** is an educational banking simulation that helps students learn financial literacy through hands-on experience. Students earn tokens by attending class, which they can spend in a classroom store, use for hall passes, or manage through savings and checking accounts.

**License:** [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) - Free for educational and nonprofit use, not for commercial applications.

**Project Status:** Version 1.2.0 Released! This major release introduces Progressive Web App (PWA) support, mobile-first experience, accessibility improvements following WCAG 2.1 AA guidelines, and modernized UI with accordion layouts. Install as a mobile app for faster, offline-capable access! See [RELEASE_NOTES_v1.2.0.md](docs/archive/releases/RELEASE_NOTES_v1.2.0.md) for full details.

---

## Features

### Core Features

- **System Admin Portal** — Manage teachers (including account recovery), review error logs, and adjust student ownership
- **Teacher Dashboard** — Manage students, run payroll, configure rent/insurance/banking settings
- **Student Portal** — View balances, redeem store items, track attendance, and manage hall passes
- **Join-Code Rosters** — Upload rosters and let students self-claim seats securely
- **Shared Students** — Link multiple teachers to the same student via `student_teachers`
- **Attendance Tracking** — Start Work/Break Done system with automatic time logging
- **Automated Payroll** — Configurable pay rates, schedules, and rewards/fines
- **Transaction Logging** — Complete audit trail of all financial activities scoped by teacher
- **Classroom Store** — Virtual/physical items with bundles, expirations, and redemption tracking
- **Hall Pass System** — Time-limited passes with automatic tracking
- **Insurance System** — Policies, enrollments, and claims managed in-app
- **Rent & Fees** — Optional recurring rent with waivers and late-fee configuration
- **TOTP Authentication** — Secure admin access with two-factor authentication

### Mobile & PWA Features ✨

- **Progressive Web App** — Install as mobile app on iOS and Android devices
- **Offline Support** — Intelligent caching with offline fallback page
- **Mobile-Optimized UI** — Dedicated mobile templates with responsive navigation
- **Touch-Friendly** — Larger buttons and improved touch targets throughout
- **Fast Performance** — Aggressive caching for quick load times
- **Home Screen Installation** — Add to home screen for app-like experience

### Accessibility Features ♿

- **Enhanced Accessibility** — Improvements following WCAG 2.1 AA guidelines
- **Screen Reader Support** — Optimized for NVDA, JAWS, and VoiceOver
- **Keyboard Navigation** — Full keyboard accessibility throughout
- **ARIA Labels** — Comprehensive labeling for assistive technologies
- **High Contrast** — Improved color contrast ratios for better readability
- **Responsive Design** — Works seamlessly across all device sizes

### Security Features

- **PII Encryption** — All student names encrypted at rest
- **TOTP for Admins** — Time-based one-time passwords required
- **Admin Account Recovery** — System admins can securely reset teacher 2FA
- **CSRF Protection** — Protection against cross-site request forgery
- **Credential Hashing** — Salted and peppered password hashing
- **Cloudflare Turnstile** — Bot protection on login forms
- **Database Error Logging** — Automatic error tracking and monitoring
- **Custom Error Pages** — User-friendly error handling (400, 401, 403, 404, 500, 503)

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

   # Cloudflare Turnstile (CAPTCHA) - Optional for development/testing
   # Leave unset to bypass Turnstile verification in testing environments
   TURNSTILE_SITE_KEY=<your-turnstile-site-key>
   TURNSTILE_SECRET_KEY=<your-turnstile-secret-key>

   # Optional maintenance mode banner (503 page)
   MAINTENANCE_MODE=false
   MAINTENANCE_MESSAGE="We're applying updates."
   MAINTENANCE_EXPECTED_END="Back online by <time>"
   MAINTENANCE_CONTACT="ops@example.com"
   ```

   **Getting Turnstile Keys (Optional):**

   Turnstile keys are optional for development and testing. If not configured, CAPTCHA verification will be automatically bypassed.

   For production deployment:
   1. Visit [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile)
   2. Create a new site widget
   3. Copy the Site Key and Secret Key

   For testing with CAPTCHA enabled, you can use Turnstile's test keys (always pass):
   - Site Key: `1x00000000000000000000AA`
   - Secret Key: `1x0000000000000000000000000000000AA`

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

- **[Student Guide](docs/user-guides/student_guide.md)** — How students use the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** — Comprehensive admin guide

### For Developers

- **[Architecture Guide](docs/technical-reference/architecture.md)** — System design and patterns
- **[Database Schema](docs/technical-reference/database_schema.md)** — Up-to-date database reference
- **[API Reference](docs/technical-reference/api_reference.md)** — REST API documentation
- **[Development Priorities](DEVELOPMENT.md)** — Current priorities, roadmap, and tasks
- **[Changelog](CHANGELOG.md)** — Version history and notable changes

### Deployment & Operations

- **[Deployment Guide](docs/DEPLOYMENT.md)** — Production deployment instructions
- **[Operations Guides](docs/operations/)** — Operational procedures and troubleshooting
- **[Contributing Guide](CONTRIBUTING.md)** — How to contribute to the project

---

## Technology Stack

**Backend:**
- Flask with blueprint architecture and application factory
- SQLAlchemy ORM with Alembic migrations
- PostgreSQL database
- Gunicorn WSGI server

**Frontend:**
- Jinja2 templates
- Bootstrap 5 with Material Symbols icons
- Minimal JavaScript for real-time attendance and admin UX

**Security:**
- Flask-WTF (CSRF protection)
- pyotp (TOTP authentication)
- cryptography (PII encryption)

**Testing:**
- pytest and pytest-flask

**Deployment:**
- Docker support with multi-stage builds
- GitHub Actions CI/CD pipeline
- Production-ready for Linux servers (tested on Ubuntu/Debian)
- Compatible with major cloud providers

---

## Project Structure

```
classroom-economy/
├── app/                      # Application package
│   ├── __init__.py           # Application factory and global filters
│   ├── extensions.py         # Flask extensions
│   ├── models.py             # Database models (students, tenancy, payroll, rent, insurance)
│   ├── auth.py               # Authentication decorators and scoped queries
│   ├── routes/               # Blueprint-based routes (admin, student, system_admin, api, main)
│   └── utils/                # Utilities (encryption, helpers, constants)
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

Active development priorities and the path to version 1.0 are tracked in [DEVELOPMENT.md](DEVELOPMENT.md).

**Version 1.0 Status:** All critical blockers (P0 and P1) have been resolved! The platform is ready for staging deployment and final validation before production release.

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
2. Check [DEVELOPMENT.md](DEVELOPMENT.md) for current priorities
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

**Last Updated:** 2025-12-18
