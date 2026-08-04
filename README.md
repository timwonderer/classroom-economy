# Classroom Token Hub (CTH)

A classroom management platform that uses a simulated token economy to drive student engagement and participation. Built with Flask + SQLAlchemy + PostgreSQL, designed for multi-tenant deployment across multiple schools and class periods.

**Version:** 2.0 (Reconstruction in Progress)  
**Active Branch:** `CTH_v2.0` (never merge to main)  
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)  
**Status:** Architecture reconstruction underway via SOP-DEV-002a domain rebuild phases

---

## Current Status (2026-08-04)

Classroom Token Hub v2 is undergoing a comprehensive architectural reconstruction to achieve production readiness via the 10-phase SOP-DEV-002a domain rebuild workflow.

**Audit Baseline Established:** 2026-08-04 via complete code inspection of all 10 domains

- ✅ **5 domains** have Phases 0-5 complete (foundational architecture)
- ⚠️ **2 domains** have Phase 5 complete but Phase 6-7 blocked or unverified
- 🔄 **3 domains** at Phase 1 (not yet started)

### Critical Blockers (Must Resolve Before Production)

1. **Obligations domain Phase 6-7 FAILS** — Template uses undefined variables (priority: fix immediately)
2. **8 domains missing view models** — Blocks Phase 6-7 integration (15-25 hours to resolve)
3. **11 routes with direct DB mutations** — Phase 4 (Mutation Boundary) enforcement incomplete
4. **Zero Phase 10 audits completed** — No domain is production-certified yet

**Current Estimate to Production:** 160-240 hours (4-6 weeks at 40h/week) starting from this baseline.

See **[AUDIT_BASELINE_2026-08-04.md](docs/TRACKING/AUDIT_BASELINE_2026-08-04.md)** for detailed domain-by-domain findings.

---

## What This Means for Developers

### If You're Starting New Work

**Good News:** Phases 0-5 are largely complete for major domains (Identity, Ledger, Obligations, Store). You can:

- Build new services following the domain service pattern
- Create FEATs for state mutations
- Build tests that verify multi-tenancy scoping

**Blocked:** Do NOT start Phase 6-7 work (routes → view models) for domains without approved view models. Check the [domain status matrix](docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md) first.

### If You're Fixing a Route or Template

Check the [domain status matrix](docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md):

- ✅ **Green (Phase 6-7 pass):** Route should use view model; template should access fields via `view.*`
- ⚠️ **Yellow (Phase 6-7 unverified):** Verify with domain owner before starting changes
- ❌ **Red (Phase 6-7 blocked):** Route/template work is blocked; see audit report for why

### If You're Planning a Feature

Features that touch student data must flow through the 10-phase SOP-DEV-002a rebuild:

Phase 0: Define scope (domain spec)
Phase 1: Immutable fact tables
Phase 2: Migrations + indexes
Phase 3: Service layer queries
Phase 4: FEAT layer mutations
Phase 5: Immutable view models
Phase 6-7: Route + template integration
Phase 8: Test coverage + multi-tenancy
Phase 9: Remove legacy code
Phase 10: Production audit certification

Each phase is sequential and interdependent. Features skip no phases.

---

## Architecture Overview

### The Three Layers (v2)

#### 1. Identity Layer (Foundation)

- `User` — Authentication principal (global)
- `Seat` — Class-local actor (WHERE work happens)
- `ClassEconomy` (`class_id`) — Tenant boundary (SCOPING KEY)
- `IdentityProfile` — Display name and class-local identity
- `join_code` — Public alias for `class_id` (for student ingress)

#### 2. Domain Services (Read + Validation)

- 10 bounded domains: Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations, Store & Entitlements, Operations, Interpretation, Policies, Support
- Each domain owns canonical tables, facts, and read queries
- Domains **do not call each other**; cross-domain reads happen via FEATs
- Authority flows: Domain spec → Service layer → FEAT mutations → Ledger

#### 3. FEAT Layer (All Mutations)

- Every state change goes through a FEAT (Feature Execution Transaction)
- FEATs resolve identity, validate across domains, and commit atomically
- Examples: `FEAT-LED-000` (transfer), `FEAT-OBL-001` (assess obligation), `FEAT-STOR-001` (purchase)
- Pattern: Route → FEAT context → domain services → database commit

```plaintext
Student clicks "Pay Rent"
    ↓
Route calls FEAT-OBL-PAY (seat_id, class_id, amount)
    ↓
FEAT validates: (seat exists, rent is due, sufficient balance)
    ↓
FEAT calls: obligations_service.record_payment() + ledger_service.transfer()
    ↓
FEAT commits atomically
    ↓
Response: "Payment processed"
```

### Multi-Tenancy (Critical)

**ALL queries must be scoped by `class_id`, never by `teacher_id` alone.**

```python
# ✅ CORRECT
students = (
    Student.query
    .filter_by(class_id=class_id)  # Multi-tenant isolation
    .all()
)

# ❌ WRONG (data leak risk)
students = Student.query.all()
```

`join_code` is a public alias for ingress only. All internal queries use `class_id`. This prevents same-teacher cross-period data leakage (P0 incident in v1).

### View Models (Phase 5-7 Integration)

View models are immutable (`@dataclass(frozen=True)`) and owned by domains. Routes build them, templates consume them.

```python
# Phase 5: Define view model
@dataclass(frozen=True)
class StudentObligationView:
    obligation_type: str
    current_period: dict  # {amount_due, days_until_due, is_paid, ...}
    payment_history: list

# Phase 6: Route builds and passes it
def rent():
    view = build_student_obligation_view(seat_id, class_id, 'RENT')
    return render_template('student_rent.html', view=view)

# Phase 7: Template accesses fields via view
# ✅ {{ view.current_period.days_until_due }}
# ❌ {{ days_until_due }}  (not in context)
```

Domains own the fields, not the templates. Templates are integration surfaces used by multiple domains.

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

## Project Structure

```plaintext
app/
├── models.py             # 40 domain models (Identity, Ledger, Obligations, Store, etc.)
├── auth.py               # Auth decorators (@admin_required, @student_required)
├── feats/                # State mutation layer
│   ├── base.py           # FEATContext, feat_shell decorator
│   ├── ledger_resolution_feat.py  # FEAT-LED-000
│   ├── assess_obligation_feat.py  # FEAT-OBL-001
│   ├── store_purchase_feat.py     # FEAT-STOR-001
│   └── ...
├── services/             # Read and validation layer (domain-bounded)
│   ├── obligations_service.py    # Obligations domain primitives
│   ├── ledger_service.py         # Ledger domain primitives
│   ├── store_service.py          # Store domain primitives
│   ├── obligation_view_model.py  # StudentObligationView builder (Phase 5)
│   ├── view_model_builders.py    # Store/Entitlements view models (Phase 5)
│   └── ...
├── routes/               # HTTP handlers (thin; call FEATs and view models)
│   ├── admin.py         # Teacher dashboard and settings
│   ├── student.py       # Student portal
│   ├── system_admin.py  # System admin endpoints
│   ├── api.py           # REST API
│   ├── analytics.py     # Analytics
│   └── ...
├── utils/                # Helpers
│   ├── economy_policy.py          # Pricing logic
│   ├── canonical_temporal_resolver.py  # Temporal context
│   ├── encryption.py             # PII encryption
│   └── ...

templates/                # Jinja2 templates (consume view models or context)
static/                   # CSS, JS, images, PWA assets
tests/                    # pytest suite (90+ test files)
migrations/               # Alembic migrations (88+ versions, all idempotent)
docs/                     # Architecture, domain, FEAT, and invariant specs
```

### Key Files

- `CLAUDE.md` — AI assistant guidelines; read before asking questions
- `.claude/rules/` — Development rules (multi-tenancy, migrations, testing, security, docs)
- `docs/INVARIANT/` — Core runtime invariants and architectural rules
- `docs/DOMAIN/` — Per-domain authority specs (e.g., DOM-LED-001, DOM-OBL-001)
- `docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md` — Current domain status by phase
- `docs/TRACKING/AUDIT_BASELINE_2026-08-04.md` — Complete audit findings

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

**Current test state:** Audit underway; see [AUDIT_BASELINE_2026-08-04.md](docs/TRACKING/AUDIT_BASELINE_2026-08-04.md) for status by domain.

### Database Migrations

```bash
flask db heads           # Must show exactly 1 head
flask db migrate -m "Description"
flask db upgrade         # Apply
flask db downgrade       # Rollback
```

All migrations must include idempotency helpers. See [.claude/rules/database-migrations.md](.claude/rules/database-migrations.md).

---

## Documentation

### Quick Navigation

| Document | Purpose |
| ---------- | --------- |
| **[AUDIT_BASELINE_2026-08-04.md](docs/TRACKING/AUDIT_BASELINE_2026-08-04.md)** | ⭐ START HERE: Domain audit findings, blockers, next steps |
| **[DOMAIN_PROGRESS_MATRIX_2026.md](docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md)** | Domain status by phase; view model coverage map |
| **[Architecture Foundation](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** | Core runtime invariants and system boundaries |
| **[Domain Specs](docs/DOMAIN/)** | Per-domain authority (Identity, Ledger, Obligations, Store, etc.) |
| **[FEAT Contracts](docs/FEATURE-EXECUTION/)** | Execution layer mutation specifications |
| **[.claude/CLAUDE.md](.claude/CLAUDE.md)** | Guidelines for working with AI assistants on this codebase |
| **[.claude/rules/](..claude/rules/)** | Development rules (multi-tenancy, migrations, testing, security) |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Roadmap and current priorities |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history |

### For Specific Tasks

- **Adding a domain:** Read [DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md](docs/TRACKING/DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md)
- **Writing a FEAT:** Read relevant domain spec + [FEAT contract template](docs/FEATURE-EXECUTION/)
- **Multi-tenancy:** Read [.claude/rules/multi-tenancy.md](.claude/rules/multi-tenancy.md)
- **Migrations:** Read [.claude/rules/database-migrations.md](.claude/rules/database-migrations.md)
- **Testing:** Read [.claude/rules/testing.md](.claude/rules/testing.md)

---

## Deployment

### Health Check

```bash
curl http://localhost:5000/health  # Returns 200 if DB is reachable
```

### Production Deployment

Deploy behind a production WSGI server:

```bash
gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000
```

See [SOP-DEP-023](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md) for full runbook.

---

## Contributing: Start with Authority, Not Tracking

**CRITICAL:** Invariants define what must be true. Tracking docs describe current progress. Always read invariants first; never let tracking docs constrain design.

### Authority Hierarchy

The project has a strict documentation hierarchy that governs what you build:

```
INV-CORE-000 (Core invariants)
    ↓
    The system must be multi-tenant, must use class_id for scoping,
    must separate identity from claims, must route mutations through FEAT.
    These are non-negotiable—they define correctness.

INV-ARC-019 (Architectural invariants)
    ↓
    The identity model MUST use User→Seat→ClassEconomy. The FEAT layer
    MUST enforce all mutations. View models MUST be immutable. 
    These apply to all domains.

DOM-{ID}-* (Domain specs)
    ↓
    Ledger owns transaction recording. Obligations owns rent assessment.
    Store owns purchase logic. Each domain's authority limits what it owns
    and what it depends on.

FEAT-{ID}-* (Execution specifications)
    ↓
    A FEAT defines one atomic business transaction: its inputs, preconditions,
    outputs, and ledger effects. Built atop domain services.

docs/TRACKING/* (Descriptive, not prescriptive)
    ↓
    These documents describe current implementation progress. They answer
    "What phase is each domain in?" NOT "What should I build?"
    Tracking docs are always behind reality and must never constrain design.
```

### Correct Workflow

**Step 1: Read Invariants**

Start with [INV-CORE-000](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) and [INV-ARC-019](docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_MODEL.md). These define what the system MUST be. Non-negotiable.

```
Takes 20 minutes. Learn:
- What makes the system correct (invariants, not implementation)
- Why class_id is the scoping boundary
- How identity model works (User→Seat→ClassEconomy)
```

**Step 2: Read Domain Specs**

Find the domain(s) your work affects. [Obligations](docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md)? [Ledger](docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md)? [Store](docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md)?

```
Takes 30-45 minutes. Learn:
- What this domain owns (its fields, tables, services)
- What it depends on (other domains)
- What constraints it has (e.g., Obligations must track period-scoped rent)
```

**Step 3: Understand the Problem Architecturally**

Frame your work in terms of the invariants and domain specs you just read. What MUST be true? What does this domain authority say?

```
Example:
- Need to fix rent calculation? Read DOM-OBL-001 to understand
  what rent fields the Obligations domain must own. Determine if
  the fix requires a FEAT change or just a view model fix.
```

**Step 4: Check Current Progress** (Now it's safe)

Only now check [AUDIT_BASELINE_2026-08-04.md](docs/TRACKING/AUDIT_BASELINE_2026-08-04.md) and [DOMAIN_PROGRESS_MATRIX_2026.md](docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md).

```
Takes 10 minutes. Learn:
- Which phases are complete for your domain
- What blockers exist
- What the audit found (context for known issues)
```

**Step 5: Design Your FEAT**

Using domain authority and invariants, design your mutation as a FEAT. See [FEAT contract template](docs/FEATURE-EXECUTION/).

**Step 6: Implement**

Follow the phase-based structure and the golden rules below.

### Why This Order?

- **Invariants define correctness.** If you read tracking first, you might build something "within current progress" that violates an invariant. Then it blocks downstream work.
- **Domain specs define boundaries.** They prevent you from moving fields between domains or creating cross-domain dependencies.
- **Tracking docs describe current state.** They're not authority. They say "Obligations phase 6-7 is blocked" but they don't say "and you can't fix it"—invariants say whether the fix is possible.

### Common Scenarios

#### If You're Adding a Feature

1. Read [INV-CORE-000](docs/INVARIANT/CORE/) — understand system constraints
2. Identify which domain(s) own the new fields
3. Read that domain's spec (e.g., [DOM-STORE-001](docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md))
4. Check audit baseline — which phase is that domain in?
5. Follow SOP-DEV-002a phases for that domain

#### If You're Fixing a Route or Template

1. Identify the domain (which data does this route work with?)
2. Read the domain spec
3. Read [INV-ARC-019](docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_MODEL.md) to understand class_id scoping
4. Check tracking matrix to see if Phase 6-7 is complete for that domain
5. If Phase 6-7 complete: route should build a view model, template should consume it
6. If Phase 6-7 blocked: check audit baseline for why; don't try to work around it

#### If You're Designing a FEAT

1. Read the relevant domain spec (e.g., [DOM-LED-001](docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) for transfers)
2. Understand what services exist (Phase 3)
3. Understand the multi-tenancy boundary (always class_id)
4. See [FEAT-LED-000](docs/FEATURE-EXECUTION/FEAT-LED-000_TRANSFER_AND_LEDGER_POSTING.md) for pattern
5. Write your FEAT following the pattern

### Golden Rules

- ✅ **Read before writing** — Always understand invariants first
- ✅ **Invariants are non-negotiable** — If code violates them, redesign the code, not the invariants
- ✅ **Scope by class_id** — Never use `teacher_id` alone for queries
- ✅ **Mutate through FEAT layer only** — No direct `db.session.add/commit` in routes
- ✅ **Create/update tests** — Every change needs test coverage
- ✅ **Use canonical helpers** — `resolve_canonical_context()`, `get_current_class_scope()`, view model builders
- ✅ **Update CHANGELOG.md** — Every change, no exceptions
- ✅ **Phase 6-7 is field ownership** — Domains own fields in view models; templates don't own anything

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines and [CLAUDE.md](.claude/CLAUDE.md) for AI assistant workflows.

---

## Architecture Phases (SOP-DEV-002a)

Every domain must progress through 10 sequential phases to be production-ready:

| Phase | Name | Purpose | Example Blocker |
| ------- | ------ | --------- | ----------------- |
| **0** | Boundary | Scope defined | "Obligations domain scope unclear" |
| **1** | Truth | Immutable facts | "ObligationAssessment not append-only" |
| **2** | Persistence | Migrations idempotent | "Migration has no existence checks" |
| **3** | Primitives | Service queries exist | "obligations_service missing get_assessment()" |
| **4** | Mutation Boundary | All writes via FEAT | "Route calls db.session.add directly" |
| **5** | Read Models | View models defined | ❌ Identity, Class Config, Ledger missing view models |
| **6** | Surface Inventory | Routes use view models | ❌ Obligations Phase 6-7 template fails |
| **7** | Rewire | Templates via view models | ❌ 8 domains blocked (no view models) |
| **8** | Verify | Tests pass + multi-tenancy | Requires Phases 0-7 complete |
| **9** | Legacy Deletion | Dead code removed | Requires Phase 8 pass |
| **10** | Audit | Production certified | Requires Phases 0-9 complete |

Current status by domain: See [DOMAIN_PROGRESS_MATRIX_2026.md](docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md).

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

**Permitted:** Classrooms, clubs, nonprofits, research, personal learning.  
**Prohibited:** Commercial products, SaaS, paid services, for-profit use.

See [LICENSE](LICENSE) for complete terms and [Third-Party Notices](docs/archive/v1-user-guides/legal/third-party-notices.md) for dependencies.

---

## Support

- **Questions about architecture?** Read [CLAUDE.md](.claude/CLAUDE.md) and the relevant domain spec
- **Found a bug?** Check the audit baseline; may be a known blocker before opening an issue
- **Ready to contribute?** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Need to contact the human behind the project?** Reach out to [dev@classroomtokenhub.com](mailto:dev@classroomtokenhub.com)

This project is developed, deployed, maintained, operated, and tested by a single full-time high school teacher who live by the motto of *"fine, I'll build one myself."*

Last updated: 2026-08-04 — Audit baseline established
