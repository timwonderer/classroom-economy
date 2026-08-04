# Classroom Token Hub

A classroom management platform that uses a simulated token economy to drive student engagement and participation.

**Version:** 2.0.0 (live-test candidate)  
**Last Released:** 1.9.0 (2026-03-04)  
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)
**Active branch:** `codex/v2.0`

> [!IMPORTANT]
>
> Classroom Token Hub v1 is now deprecated. The current public deployment reflects **v1.9.0**. The v2.0 branch (`codex/v2.0`) is in live-test candidate state — full-suite validation passes (`744 passed, 19 skipped`) and store domain is complete, but the live-test and production transition gates are not yet finalized.
>
> For v1 legacy code, see branch [legacy_v1.10.0](https://github.com/timwonderer/classroom-token-hub/tree/legacy_v1.10.0)

---

## Overview

Classroom Token Hub gives teachers a token-based economy to manage their classroom. Students earn tokens for attendance and participation, then spend them in a class store, use them for hall passes, or save them. This system creates a feedback loop that reinforces positive classroom behavior. Teachers configure pay rates, rent, store items, and feature toggles per class period.

The platform is multi-tenant: a single deployment serves many teachers, each with multiple class periods. Students can belong to multiple classes with different teachers. All data is isolated by class.

---

## Architecture

The v2 architecture is built on three layers:

- **Identity:** `User` authenticates, `Seat` acts within a class, `ClassEconomy` (`class_id`) scopes all data. `join_code` is the public ingress alias for `class_id`.
- **Domains:** Bounded services (`app/services/`) own read and validation logic. Domains do not call each other directly.
- **FEATs:** All state mutation flows through `app/feats/` — atomic execution units that resolve identity, validate across domains, and commit in a single transaction.

```
Routes → FEAT → Domain Services → Ledger
```

New code must route writes through FEATs. GET handlers must not trigger DB writes.

### Key Models

| Layer | Models | Purpose |
|-------|--------|---------|
| Identity | `User`, `Seat`, `IdentityProfile`, `ClassEconomy`, `PasskeyCredential` | Auth, class-local actor, display name, class boundary, passkey credentials |
| Financial | `Transaction`, `LedgerBalanceSnapshot` | Ledger entries and cached balances (seat + class scoped) |
| Configuration | `PayrollSettings`, `RentSettings`, `BankingSettings`, `FeatureSettings`, `ClassFeature` | Per-class economy settings and feature toggles |
| Obligations | `ObligationAssessment`, `BillCycle`, `PolicyVersion`, `PolicyTransition` | Rent, insurance, and fee lifecycle with immutable policy versioning |
| Store | `StoreItem`, `StoreItemVisibility`, `StoreProduct`, `EntitlementEvent` | Classroom store catalog, product policies, and entitlement lifecycle |
| Attendance | `AttendanceSession`, `HallPassLog`, `HallPassSettings`, `PayrollEvent` | Attendance sessions, hall passes, and payroll events |
| Audit | `AuditEvent`, `ChainHead` | Append-only hash-chained audit log |
| Support | `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`, `TicketCorrelationPack` | Support ticket lifecycle |
| Recovery | `RecoveryRequest`, `StudentRecoveryCode` | Student account recovery flow |
| Operations | `PendingAction`, `ActorRequestTrace`, `Announcement` | Pending approvals, request traces, announcements |

40 domain models total. Legacy tables (`Admin`, `Student`, `TeacherBlock`, `ClassMembership`, `StudentTeacher`, `TapEvent`, `RentPayment`, `StudentInsurance`, `StudentItem`, `RedemptionAuditLog`, `BalanceCache`) have been retired and must not be treated as current architecture authority.

---

## Features

### For Teachers
- **Two-Step Sign Up** with just your username and authenticator. No more date of birth references
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
- **Seat Claim** — Self-claim a teacher-provisioned seat using claim credentials
- **Account Recovery** — Student-assisted teacher recovery flow

### For System Admins
- **Admin Portal** — Teacher overview, support tickets, error/event logs, broadcast announcements

### Platform
- **Multi-Tenant** — Full class-period isolation; shared students across teachers
- **Progressive Web App** — Installable on mobile with offline fallback
- **Accessibility** — WCAG 2.1 AA design guidelines, keyboard navigation, ARIA labels, screen reader support. Automated testing uses axe-core; no formal certification.
- **Security** — PII encryption at rest, TOTP 2FA for admins, CSRF protection, salted+peppered credential hashing, Cloudflare Turnstile bot protection, post-claim PII deletion
- **Observability** — OpenTelemetry instrumentation (Flask, SQLAlchemy, requests) with OTLP export; append-only hash-chained `AuditEvent` log
- **Rate Limiting** — Flask-Limiter with Cloudflare-aware IP detection; disabled in development by default

> [!IMPORTANT]
>
> Classroom Token Hub is designed to be privacy first. This means our platform only collects information that's necessary for the app to function as intended. This is why we do not ask teachers to provide their identities nor their physical locations. We also do not collect email addresses or phone numbers.
>
> Our justification for this is to reduce the blast radius should a breach happens. Our minimal PII collection approach means the data will be almost meaningless without external references. Integration of SSO on our server will fundamentally and permanently attach validated external identity to an actor in a simulated economy. This approach is the opposite of what we believe in.
>
> Because of that, we do not support SSO integration natively on our server. However, if district partners are interested in forking and internally hosting this project on their own infrastructure, they may implement whichever authentication or account provisioning mechanism as they see fit. We will be more than happy to provide technical support on architecture but the district will have full operational control over its fork, including authentication, infrastructure, identity management, security, deployment, and maintenance. Learn more about why we made that choice at [PRN-SNP-001 Why Classroom Token Hub Does Not Implement SSO](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md)

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

# Optional — rate limiting (disabled in development by default)
DEV_ENABLE_RATELIMIT=false

# Optional — maintenance mode
MAINTENANCE_MODE=false

# Optional — OpenTelemetry export (OTLP/HTTP)
OTEL_EXPORTER_OTLP_ENDPOINT=<otlp-endpoint>
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

---

## Project Structure

```
app/
├── __init__.py           # App factory
├── models.py             # SQLAlchemy models (40 domain models)
├── auth.py               # Auth decorators and scoped access helpers
├── access/               # Scope resolution and scope factory
├── feats/                # FEAT execution layer (all state mutation)
│   ├── ledger_resolution_feat.py   # FEAT-LED-000: canonical monetary resolution
│   ├── store_purchase_feat.py      # FEAT-STOR-001
│   ├── assess_obligation_feat.py   # FEAT-OBL-001
│   ├── rent_payment_feat.py        # FEAT-OBL (rent)
│   ├── insurance_claim_feat.py     # FEAT-STOR-003
│   ├── transfer_feat.py            # Account transfers
│   ├── transaction_void_feat.py    # Ledger reversals
│   └── ...                         # Additional FEATs
├── services/             # Domain-bounded read/validation services
│   ├── balance_service.py
│   ├── obligations_service.py
│   ├── store_service.py
│   ├── store_policy_resolver.py    # SPEC-STORE-001 policy resolution
│   ├── entitlement_read_service.py # Entitlement reads
│   ├── view_model_builders.py      # Obligation/class view models
│   └── ...                         # Additional services
├── routes/               # Blueprints: admin, student, system_admin, api, analytics, docs, main, recovery
├── utils/                # Helpers (encryption, seat scope, economy policy, analytics engine)
│   ├── economy_policy.py           # Centralized pricing recommendation logic
│   ├── analytics_engine.py
│   ├── encryption.py
│   └── ...
├── forms.py              # WTForms definitions
├── payroll.py            # Payroll automation
└── scheduled_tasks.py    # Background scheduler (APScheduler)

templates/                # Jinja2 templates
static/                   # CSS, JS, images, PWA assets
tests/                    # pytest suite (90 test files across 14 domain directories)
migrations/               # Alembic migrations (88 versions)
scripts/                  # Utility and seed scripts
docs/                     # v2 architecture, domain, and invariant specs
wsgi.py                   # WSGI entry point (gunicorn wsgi:app)
```

---

## Development

### Running Tests

Tests require a PostgreSQL test database. Set `TEST_DATABASE_URL` before running:

```bash
TEST_DATABASE_URL=postgresql://... pytest   # All tests
pytest tests/test_payroll.py               # Specific file
pytest -k "recovery"                       # Pattern match
pytest --cov=app tests/                    # With coverage (requires pytest-cov)
```

The validated branch state: `744 passed, 19 skipped`.

### Database Migrations

```bash
flask db heads                          # Verify single head
flask db migrate -m "Description"       # Generate migration
flask db upgrade                        # Apply
flask db downgrade                      # Rollback
```

All migrations must include idempotency helpers. See `.claude/rules/database-migrations.md` for the full workflow. A pre-push hook enforces single-head integrity; install it via:

```bash
./scripts/setup-hooks.sh
```

### Common Commands

```bash
flask run                               # Dev server
flask create-sysadmin                   # Create system admin
python scripts/seed_dummy_students.py   # Seed test data
```

---

## Documentation

- **[Architecture Foundation](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** — Core runtime invariants and system boundaries
- **[Authority Model](docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** — Capability-based INV → DOM → FEAT hierarchy
- **[Domain Specs](docs/DOMAIN/)** — Per-domain authority contracts
- **[FEAT Contracts](docs/FEATURE-EXECUTION/)** — Execution layer specifications
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** — REST API documentation
- **[Developer Vocabulary](docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md)** — Canonical v2 terminology and deprecated-term mappings
- **[Deployment Guide](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md)** — v2 production transition runbook
- **[Live-Test Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md)** — Internal validation workflow before live testing
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

See [CONTRIBUTING.md](CONTRIBUTING.md). Review the [Architecture Foundation](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) and [DEVELOPMENT.md](DEVELOPMENT.md) before starting.

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

**Permitted:** Classrooms, clubs, nonprofit educational settings, research, personal learning.  
**Prohibited:** Commercial products, SaaS platforms, paid services, for-profit internal use.

See [LICENSE](LICENSE) for complete terms. See [Third-Party Notices](docs/archive/v1-user-guides/legal/third-party-notices.md) for dependency attributions.

---

Built for educators who want a practical, engaging way to manage their classrooms.
