# Classroom Token Hub

A classroom management platform that uses a simulated token economy to drive student engagement and participation.

**Version:** 2.0.0 (live-test candidate)  
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — Free for educational and nonprofit use.  
**Development branch:** `codex/v2.0`

---

## Overview

Classroom Token Hub gives teachers a token-based economy to manage their classroom. Students earn tokens for attendance and participation, then spend them in a class store, use them for hall passes, or save them — creating a feedback loop that reinforces positive classroom behavior. Teachers configure pay rates, rent, store items, and feature toggles per class period.

The platform is multi-tenant: a single deployment serves many teachers, each with multiple class periods. Students can belong to multiple classes with different teachers. All data is isolated by class.

---

## Architecture

The v2 architecture is built on three layers:

- **Identity:** `User` authenticates, `Seat` acts within a class, `ClassEconomy` (`class_id`) scopes all data. `join_code` is the public alias for `class_id`.
- **Domains:** Bounded services (`app/services/`) own read and validation logic. Domains do not call each other directly.
- **FEATs:** All state mutation flows through `app/feats/` — atomic execution units that resolve identity, validate across domains, and commit in a single transaction.

```
Routes → FEAT → Domain Services → Ledger
```

New code must route writes through FEATs; legacy routes that commit directly are being migrated. GET handlers must not trigger DB writes.

### Key Models

| Layer | Models | Purpose |
|-------|--------|---------|
| Identity | `User`, `Seat`, `IdentityProfile`, `ClassEconomy` | Auth, class-local actor, display name, class boundary |
| Financial | `Transaction`, `BalanceCache` | Ledger entries and cached balances (seat + class scoped) |
| Configuration | `PayrollSettings`, `RentSettings`, `BankingSettings`, `FeatureSettings` | Per-class economy settings |
| Obligations | `ObligationAssessment`, `ObligationLifecycle` | Rent, insurance, and fee lifecycle |
| Store | `StoreItem`, `StudentItem`, `RedemptionAuditLog` | Classroom store catalog and purchases |
| Attendance | `AttendanceSession`, `SeatAttendanceState`, `HallPassLog` | Start Work / Break Done tracking, current attendance gate state, hall passes |

55+ models total. Legacy tables (`Admin`, `Student`, `TeacherBlock`) still exist as compatibility shadows during the auth transition.

---

## Features

### For Teachers
- **At-a-Glance Dashboard** for quick class stats, activities, and pending approvals
- **Teacher-Provisioned Seats** that are created when teacher upload a roster for student to self-claim in class
- **Automated Payroll** for streamlined set-it-and-forget-it workflow. Configure rates, pay schedule, and overtime for your classroom needs
- **Classroom Store** for organizing and selling virtual and physical items with bundles, expirations, and redemption tracking
- **Recurring Rent** complete with with waivers, late fees, seat-scoped reversals, and immutable policy versioning to teach responsibility and planning
- **Insurance** with multiple claim type and limits to teach risk management
- **Simple Analytics** to quickly diagnose participation rate, money velocity, spending/hoarding behavior, budget survivability; weekly and monthly views
- **Hall Passes Management** so you always know where is your student going, when did they leave, and when are they coming back.
### For Students
- **Portal** — View balances, transaction history, store, and attendance
- **Account Transfers** — Move funds between checking and savings accounts
- **Account Recovery** — Student-assisted teacher recovery flow

### For System Admins
- **Admin Portal** — Teacher overview, support tickets, error/event logs, broadcast announcements
  > **v2 direction:** Invite-code gating replaced by open teacher self-signup; sysadmin role shifts to operational oversight.

### Platform
- **Multi-Tenant** — Full class-period isolation; shared students across teachers
- **Progressive Web App** — Installable on mobile with offline fallback
- **Accessibility** — WCAG 2.1 AA design guidelines, keyboard navigation, ARIA labels, screen reader support. Automated testing uses axe-core; no formal certification.
- **Security** — PII encryption at rest, TOTP 2FA for admins, CSRF protection, salted+peppered credential hashing, Cloudflare Turnstile bot protection, post-claim PII deletion

> [!IMPORTANT]
> Classroom Token Hub is designed to be privacy first. If we can design our app around minimizing PII, we would. We believe the only people that should know the human inside each classroom are the teachers and their students. That said, we find external identity anchor to be unneccessarily risky for our needs. 
> Because of that, we do not support SSO integration. Learn more about why we made that choice at [PRN-SNP-001 Why Classroom Token Hub Does Not Implement SSO](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md)

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL
- A virtual environment (recommended)

### Installation

```bash
git clone <repository-url>
cd classroom-token-hub
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
SECRET_KEY=<64-char-random-string>
DATABASE_URL=postgresql://user:password@host:port/dbname
FLASK_ENV=development
ENCRYPTION_KEY=<32-byte-base64-key>   # openssl rand -base64 32
PEPPER_KEY=<secret-pepper-string>
CSRF_SECRET_KEY=<random-string>

# Optional — leave unset to bypass in development
TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>

# Optional — maintenance mode
MAINTENANCE_MODE=false
```

### Database Setup

```bash
flask db upgrade
flask create-sysadmin   # Follow prompts, scan QR with authenticator app
```

### Run

```bash
flask run
```

Navigate to `http://localhost:5000`.

### Git Hooks

```bash
./scripts/setup-hooks.sh
```

Enables branch-aware database switching (`codex/v2.0` / `codex/v2-*` → `classroom_economy`, other branches → `production_dev`) and pre-push migration-head safety checks.

---

## Project Structure

```
app/
├── __init__.py           # App factory
├── models.py             # SQLAlchemy models (55+)
├── auth.py               # Auth decorators and scoped access helpers
├── feats/                # FEAT execution layer (all state mutation)
├── services/             # Domain-bounded read/validation services
├── routes/               # Blueprints: admin, student, system_admin, api, analytics, docs, main, recovery
├── utils/                # Helpers (encryption, seat scope, economy policy, analytics engine)
├── forms.py              # WTForms definitions
├── payroll.py            # Payroll automation
└── scheduled_tasks.py    # Background scheduler (APScheduler)

templates/                # Jinja2 templates
static/                   # CSS, JS, images, PWA assets
tests/                    # pytest suite (55+ test files)
migrations/               # Alembic migrations
scripts/                  # Utility and seed scripts
deploy/                   # Deployment config (nginx)
docs/                     # v2 architecture, domain, and invariant specs
wsgi.py                   # WSGI entry point (gunicorn wsgi:app)
```

---

## Development

### Running Tests

```bash
pytest                              # All tests
pytest tests/test_payroll.py        # Specific file
pytest -k "recovery"                # Pattern match
pytest --cov=app tests/             # With coverage (requires pytest-cov)
```

### Database Migrations

```bash
flask db heads                          # Verify single head
flask db migrate -m "Description"       # Generate migration
flask db upgrade                        # Apply
flask db downgrade                      # Rollback
```

All migrations must include idempotency helpers. See `.claude/rules/database-migrations.md` for the full workflow.

### Common Commands

```bash
flask run                               # Dev server
flask create-sysadmin                   # Create system admin
python scripts/seed_dummy_students.py   # Seed test data
```

---

## Documentation

- **[Architecture Foundation](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** — System design and domain boundaries
- **[Authority Model](docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** — INV → DOM → FEAT enforcement hierarchy
- **[Domain Specs](docs/DOMAIN/)** — Per-domain authority contracts
- **[FEAT Contracts](docs/FEATURE-EXECUTION/)** — Execution layer specifications
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** — REST API documentation
- **[Deployment Guide](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** — Production deployment
- **[Development Priorities](DEVELOPMENT.md)** — Roadmap and v2 launch readiness
- **[V2 Migration Tracker](docs/TRACKING/V2_Full_compliance_migration_plan.md)** — Active wave-by-wave execution status
- **[Changelog](CHANGELOG.md)** — Version history

---

## Monitoring

The `/health` endpoint returns HTTP 200 when the database is reachable. Deploy behind a production web server (e.g., NGINX + Gunicorn).

```bash
curl http://your-domain/health
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Review the [Architecture Foundation](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md) and [DEVELOPMENT.md](DEVELOPMENT.md) before starting.

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

**Permitted:** Classrooms, clubs, nonprofit educational settings, research, personal learning.  
**Prohibited:** Commercial products, SaaS platforms, paid services, for-profit internal use.

See [LICENSE](LICENSE) for complete terms. See [Third-Party Notices](docs/archive/v1-user-guides/legal/third-party-notices.md) for dependency attributions.

---

Built for educators who want a practical, engaging way to manage their classrooms.
