# Classroom Token Hub v1.0.0

**Release Date:** December 2025
**License:** [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

---

## Overview

We're pleased to announce the first stable release of **Classroom Token Hub**, an educational banking simulation platform designed to teach students financial literacy through hands-on classroom experience. Version 1.0 represents a significant milestone in the project's evolution, delivering a secure, feature-complete system ready for production classroom use.

Classroom Token Hub enables teachers to create simulated classroom economies where students earn tokens through attendance, manage checking and savings accounts, purchase items from a classroom store, and interact with financial products like insurance and rent—all within a safe, educational environment.

---

## What's New in v1.0

### Core Platform Features

**Multi-Tenancy Support**
- Full support for students enrolled in multiple class periods
- Proper data isolation between different class sections taught by the same teacher
- Join-code-based class isolation ensures accurate per-period balances and transactions
- Seamless class switching for students participating in multiple classroom economies

**Teacher Administration**
- System admin portal for platform-wide management and monitoring
- Teacher dashboard with comprehensive student, financial, and attendance management
- Bulk roster uploads via CSV with secure join-code claiming system
- Shared student management across multiple teachers
- Customizable display names and class labels for personalized branding

**Student Experience**
- Intuitive student portal with real-time balance tracking
- Attendance tracking via tap in/out system with automatic time logging
- Classroom store with support for virtual/physical items, bundles, and expiration dates
- Hall pass system with time tracking and automatic status updates
- Student-to-student token transfers

**Financial Systems**
- Automated payroll with configurable schedules, rates, and block-specific settings
- Dual account system: checking and savings with interest calculations
- Insurance policies with enrollment, claims, and reimbursement workflows
- Optional rent collection with waivers and late-fee configuration
- Complete transaction audit trails scoped by class period

**Security & Authentication**
- TOTP (Time-based One-Time Password) two-factor authentication for all admin accounts
- PII encryption at rest for all student names
- CSRF protection on all forms
- Salted and peppered password hashing
- Cloudflare Turnstile integration for bot protection
- Comprehensive error logging and user reporting systems

---

## Critical Fixes

### P0: Same-Teacher Multi-Period Data Leak (Fixed 2025-11-29)

**Issue:** Students enrolled in multiple periods with the same teacher were seeing aggregated data across all periods instead of period-specific information.

**Resolution:** Implemented join-code-based scoping across all transaction and financial tables. The system now uses `join_code` as the absolute source of truth for class isolation, ensuring proper data boundaries between different class periods.

**Migration:** Interactive backfill process guides administrators through associating legacy transactions with the correct class period. New transactions automatically inherit the correct join code.

**Status:** Deployed to production with ongoing backfill validation.

### P1: Deprecated Code Patterns (Completed 2025-12-06)

**Updated for Python 3.12+ and SQLAlchemy 2.0+ compatibility:**
- Replaced all 52 occurrences of deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`
- Migrated all `Query.get()` calls to modern `db.session.get(Model, id)` pattern
- Resolved SQLAlchemy subquery coercion warnings

**Result:** Full compatibility with current Python and SQLAlchemy standards.

---

## Technical Improvements

**Architecture**
- Modular Flask Blueprint structure (refactored from 4,500-line monolithic `app.py`)
- 34 SQLAlchemy models with comprehensive relationship mapping
- 73 Alembic migrations managing schema evolution
- Scoped query helpers for tenant-aware data access

**Testing**
- 47 comprehensive test files covering core functionality
- Foreign key constraint testing enabled
- Multi-tenancy validation tests
- Legacy compatibility regression tests

**Deployment**
- GitHub Actions CI/CD pipeline
- PostgreSQL database with migration automation
- Gunicorn WSGI server with gevent workers
- Redis for rate limiting and caching
- Cloudflare DNS and DDoS protection
- UptimeRobot monitoring integration
- Maintenance mode with bypass tokens for administrative access

**Documentation**
- Comprehensive user guides for students and teachers
- Technical reference documentation (architecture, database schema, API)
- Operations guides for deployment and maintenance
- Security audit reports and validation documentation
- Historical reference documents preserving project evolution

---

## Installation

### Prerequisites
- Python 3.10 or higher
- PostgreSQL database
- Redis (for production deployments)

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/classroom-economy.git
   cd classroom-economy
   ```

2. **Set up virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   Create a `.env` file with required configuration:
   ```bash
   SECRET_KEY=<long-random-string>
   DATABASE_URL=postgresql://user:password@host:port/dbname
   FLASK_ENV=production
   ENCRYPTION_KEY=<32-byte-base64-key>  # Generate: openssl rand -base64 32
   PEPPER_KEY=<secret-pepper-string>
   CSRF_SECRET_KEY=<random-string>
   ```

4. **Initialize the database:**
   ```bash
   flask db upgrade
   ```

5. **Run the application:**
   ```bash
   # Development
   flask run

   # Production (with Gunicorn)
   gunicorn -c gunicorn_config.py wsgi:app
   ```

For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Upgrade Instructions

If upgrading from a pre-1.0 version:

1. **Backup your database** before proceeding
2. Pull the latest code and activate your virtual environment
3. Update dependencies: `pip install -r requirements.txt`
4. Run migrations: `flask db upgrade`
5. **Interactive backfill:** If you have legacy transactions without join codes, administrators will be prompted during normal operation to verify which class period those transactions belong to
6. Review the [CHANGELOG.md](CHANGELOG.md) for breaking changes

---

## Known Limitations

- **Backfill in progress:** Legacy transactions created before the v1.0 join-code scoping update require interactive verification. Administrators will see occasional prompts to confirm which class period historical transactions belong to.
- **Browser compatibility:** Optimized for modern browsers (Chrome, Firefox, Safari, Edge). Internet Explorer is not supported.
- **Mobile experience:** Basic responsive design implemented. Full mobile optimization planned for v1.2.

---

## What's Next

Development continues with planned features for future releases:

**v1.1 - Analytics & Insights**
- Enhanced dashboard visualizations
- Class economy health metrics
- CSV export capabilities for reports

**v1.2 - Mobile Experience**
- Progressive Web App (PWA) support
- Improved touch interfaces
- Offline attendance tracking

**v1.5+ - Extended Features**
- In-app communication and announcements
- Jobs feature (classroom job market)
- Custom condition builder for advanced rules
- Parent portal (optional, privacy-controlled)

See [DEVELOPMENT.md](DEVELOPMENT.md) for the complete roadmap.

---

## License & Usage

Classroom Token Hub is released under the **PolyForm Noncommercial License 1.0.0**. This software is free for educational and nonprofit use. Commercial use is not permitted under this license.

For questions about licensing, please see [LICENSE.md](LICENSE.md).

---

## Acknowledgments

This project was developed to serve real classrooms and real students learning financial literacy. Special thanks to the educators who have provided feedback and testing throughout development.

For technical questions, bug reports, or feature requests, please open an issue on GitHub or consult the documentation at [docs/README.md](docs/README.md).

---

## Resources

- **Documentation:** [docs/README.md](docs/README.md)
- **Student Guide:** [docs/user-guides/student_guide.md](docs/user-guides/student_guide.md)
- **Teacher Manual:** [docs/user-guides/teacher_manual.md](docs/user-guides/teacher_manual.md)
- **Development Priorities:** [DEVELOPMENT.md](DEVELOPMENT.md)
- **Security Audits:** [docs/security/](docs/security/)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **Project History:** [PROJECT_HISTORY.md](PROJECT_HISTORY.md)

---

**Version 1.0.0** - Stable Release
Built for educators, designed for students, committed to financial literacy education.
