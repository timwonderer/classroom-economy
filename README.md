# Classroom Token Hub (CTH)

A classroom management platform that uses a simulated token economy to drive student engagement and participation. Built with Flask + SQLAlchemy + PostgreSQL, designed for multi-tenant deployment across multiple schools and class periods.

**Version:** 2.0 (Reconstruction in Progress)  
**Active Branch:** `CTH_v2.0` (never merge to main)  
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

---

## Features

### For Teachers

- **Two-Step Sign Up** — Username + authenticator (no PII required)
- **Admin Dashboard** — Class overview, pending actions, analytics
- **Roster Management** — Provision seats; students self-claim with credentials
- **Automated Payroll** — Configure hourly rates, pay schedule, overtime thresholds
- **Classroom Store** — Create items, bundles, expiration policies; track redemptions
- **Rent System** — Recurring payments with grace periods, waivers, late fees
- **Hall Passes** — Track when students leave/return; automatic status updates
- **Analytics** — Participation rate, money velocity, budget survivability trends
- **Support Tickets** — Student-submitted issues with admin resolution tracking

### For Students

- **Portal** — View balances, transaction history, store, attendance
- **Account Transfers** — Move funds between checking and savings
- **Seat Claim** — Self-provision using teacher-issued claim credentials
- **Account Recovery** — Restore access via teacher-verified process
- **Hall Pass Requests** — Request approval; see status in real-time

### For System Admins

- **Admin Portal** — Teacher overview, support tickets, system events, announcements
- **User Management** — Provision sysadmins, manage 2FA recovery

### Platform

- **Multi-Tenant** — Full class-period isolation; students share identity across teachers
- **Progressive Web App** — Installable on mobile; offline fallback included
- **Accessibility** — WCAG 2.1 AA design, keyboard nav, ARIA labels, screen readers
- **Security** — PII encryption at rest, TOTP 2FA, CSRF protection, bcrypt hashing, Cloudflare Turnstile, post-claim PII deletion
- **Observability** — OpenTelemetry instrumentation (Flask, SQLAlchemy) with OTLP export
- **Rate Limiting** — Flask-Limiter with Cloudflare IP detection; disabled in dev

> [!IMPORTANT]
>
> **Privacy First Design:** CTH minimizes PII collection (no email, phone, SSO). We do not ask for identities or physical locations. This reduces breach impact: data is meaningless without external reference.
>
> We do not support native SSO. If your district wants to self-host with SSO integration, fork this project and implement your own auth layer. We provide technical support for architecture; you retain full operational control.
>
> See [PRN-SNP-001](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md) for rationale.

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Virtual environment (recommended)

### Setup

```bash
# Clone and create venv
git clone <repo-url>
cd classroom-economy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cat > .env << 'EOF'
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://user:password@localhost:5432/classroom_economy
ENCRYPTION_KEY=$(openssl rand -base64 32)
PEPPER_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
CSRF_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
FLASK_ENV=development
EOF

# Initialize database
flask db upgrade
flask create-sysadmin  # Follow prompts; scan QR with authenticator

# Run
flask run  # Navigate to http://localhost:5000
```

### Running Tests

```bash
# All tests (requires TEST_DATABASE_URL set)
TEST_DATABASE_URL=postgresql://... pytest

# Specific domain
pytest tests/dom/obligations/ -v

# With coverage
pytest --cov=app tests/
```

### Database Migrations

```bash
flask db heads           # Must show exactly 1 head
flask db migrate -m "Description"
flask db upgrade         # Apply
flask db downgrade       # Rollback
```

All migrations must include idempotency helpers. See [.claude/rules/database-migrations.md](.claude/rules/database-migrations.md).

---

## Architecture

CTH v2 uses a three-layer architecture with strict domain boundaries:

1. **Identity Layer** — `User` (auth principal) → `Seat` (class-local actor) → `ClassEconomy` (tenant boundary via `class_id`)
2. **Domain Services** — 10 bounded domains (Identity, Class Config, Ledger, Payroll, Obligations, Store, Operations, Interpretation, Policies, Support) that own canonical tables and read queries
3. **FEAT Layer** — All state mutations go through Feature Execution Transactions; no direct `db.session.commit` in routes

All queries must be scoped by `class_id`, never by `teacher_id` alone.

---

## Documentation

| Document | Purpose |
| ---------- | --------- |
| **[.claude/CLAUDE.md](.claude/CLAUDE.md)** | AI assistant guidelines |
| **[.claude/rules/](.claude/rules/)** | Development rules (multi-tenancy, migrations, testing, security) |
| **[docs/INVARIANT/](docs/INVARIANT/)** | Core runtime invariants and architectural rules |
| **[docs/DOMAIN/](docs/DOMAIN/)** | Per-domain authority specs |
| **[docs/FEATURE-EXECUTION/](docs/FEATURE-EXECUTION/)** | FEAT mutation contracts |
| **[docs/TRACKING/](docs/TRACKING/)** | Domain progress and audit status |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Roadmap and current priorities |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history |

---

## Deployment

```bash
# Health check
curl http://localhost:5000/health  # Returns 200 if DB is reachable

# Production
gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000
```

See [SOP-DEP-023](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md) for the full runbook.

---

## Contributing

Read the invariants first, then domain specs, then tracking docs. Authority flows downward:

```
INV-CORE (what must be true) → INV-ARC (architectural rules) → DOM-* (domain authority) → FEAT-* (execution specs)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

**Permitted:** Classrooms, clubs, nonprofits, research, personal learning.  
**Prohibited:** Commercial products, SaaS, paid services, for-profit use.

See [LICENSE](LICENSE) for complete terms.

---

## Support

- **Questions about architecture?** Read [.claude/CLAUDE.md](.claude/CLAUDE.md) and the relevant domain spec
- **Found a bug?** Open an issue
- **Ready to contribute?** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Contact:** [dev@classroomtokenhub.com](mailto:dev@classroomtokenhub.com)

This project is developed, deployed, maintained, operated, and tested by a single full-time high school teacher who lives by the motto of *"fine, I'll build one myself."*
