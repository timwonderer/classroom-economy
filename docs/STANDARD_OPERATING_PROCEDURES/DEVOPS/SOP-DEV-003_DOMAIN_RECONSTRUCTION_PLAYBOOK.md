# SOP-DEV-003: Domain Reconstruction Playbook

**Purpose:** Step-by-step guide for applying SOP-DEV-002 phases to any domain. Codifies the pattern discovered during obligations domain reconstruction so the next domain (INSURANCE_PREMIUM, FINE, FEE, or entirely new domain) can follow a deterministic playbook.

**Authority:** SOP-DEV-002, DOM-CORE-002, INV-ARC-009, MAP-UI-002, multi-tenancy.md, testing.md

**Scope:** Domains with recurring liabilities, multi-period aggregations, or per-seat financial state (obligations, productivity, entitlements, etc.)

**Related Documents:**
- `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md` — High-level 10-phase workflow
- `.claude/rules/qa_audit_domain_reconstruction.md` — Verification checklist for each phase
- `DOM-OBL-001_OBLIGATIONS_DOMAIN.md` — Concrete example (obligations domain)
- `MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md` — View model and route pipeline pattern

---

## I. Pre-Reconstruction Analysis

Before starting Phase 0, assess whether the domain is a good candidate for SOP-DEV-002 reconstruction.

### A. Domain Characteristics Checklist

**Answer yes to 3+ of these:**

- [ ] Domain has **immutable facts** (events, assessments, transactions) that should never be updated by users
- [ ] Domain tracks **recurring liability or state** that progresses over time or cycles
- [ ] Domain requires **multi-tenant scoping** (class_id isolation)
- [ ] Domain has **aggregation logic** currently scattered in routes or templates (e.g., status counts, history summaries)
- [ ] Domain has **multiple read surfaces** (student view, admin view, dashboard) consuming the same business facts
- [ ] Domain has **legacy denormalized columns** (mutable flags, counters, cached values) that duplicate derivable state
- [ ] Domain has **ad-hoc SQL or complex ORM queries** in routes that should be centralized

**If yes to 3+:** The domain is a good candidate. Proceed to Phase 0 Analysis.

**If no:** The domain may not benefit from full SOP-DEV-002 reconstruction. Consider lighter refactoring (e.g., FEAT boundary, view model for one read surface).

### B. Domain Scope Definition Template

Answer these questions about the domain you're reconstructing:

**1. What are the primary entities/actors?**
   - Example (obligations): Seat, Class, BillCycle, Assessment
   - Document each and its relationship to other domains

**2. What events/facts does this domain own?**
   - Example (obligations): ASSESSMENT (liability created), PAYMENT (liability satisfied), WAIVED (liability forgiven)
   - What is immutable? What must never be updated?

**3. What does NOT belong to this domain?**
   - Example (obligations): Ledger transactions, insurance lifecycle, class configuration
   - What upstream domains provide inputs?

**4. What are the read surfaces (pages/dashboards)?**
   - Example (obligations): Student rent view, admin rent dashboard, admin economy health summary
   - What data does each surface display?

**5. What aggregations are currently scattered?**
   - Example (obligations): status counts (up-to-date, behind-1, behind-2, behind-3+), payment history, overdue calculation
   - Where are they computed (routes, templates, models)?

**6. What are the current pain points?**
   - Example (obligations): 24-period walk for every student, duplicate status logic in multiple routes, legacy helper functions, mutable status flags
   - What makes the code hard to maintain?

---

## II. Phase 0: Boundary (Analysis & Scope Definition)

**Goal:** Clearly define and authorize the domain scope so the reconstruction targets the right work.

### A. What to Look For in the Codebase

**Find the domain's current extent:**

```bash
# 1. Identify models/tables
grep -r "class.*\(db.Model\)" app/models.py | grep -i "[domain_keyword]"
# Replace [domain_keyword] with "rent", "insurance", "fine", etc.

# 2. Find service functions
grep -r "^def.*rent\|^def.*insurance" app/services/

# 3. Find routes
grep -r "rent\|insurance" app/routes/ | grep "@.*bp.route"

# 4. Find legacy variables in templates
grep -r "rent_status_counts\|payment_log\|unpaid_.*_log" templates/

# 5. Find ad-hoc SQL
grep -r "db.session.execute.*SELECT" app/
grep -r "db.session.query.*text(" app/
```

### B. Decision Tree: Is This Scope Right?

```
START: Domain scope defined?
  ├─ YES, and it's GENERIC (not "just rent", but "any obligation type")
  │   └─ GOOD: Proceed to Phase 1
  ├─ NO, it's too BROAD (e.g., "all financial stuff")
  │   └─ ACTION: Split into smaller domains (separate Obligations, Entitlements, Ledger)
  └─ NO, it's too NARROW (e.g., "rent for one class size")
      └─ ACTION: Generalize to handle variations (all class sizes, all obligation types)
```

### C. Sign-Off Checklist

Before moving to Phase 1, verify:

- [ ] Domain specification document exists (DOM-* or INV-*)
- [ ] Scope is explicitly generic (not domain-specific)
- [ ] Multi-tenancy model specified (class_id scoping)
- [ ] Authority documents cite this domain's scope
- [ ] Current codebase extent identified (models, routes, services, templates)

---

## III. Phase 1: Truth (Canonical Facts & Immutability)

**Goal:** Identify immutable facts and define which tables are the domain's canonical truth.

### A. Decision Tree: What's a Fact?

```
Is this an immutable record of something that happened?
  ├─ YES, a user/system action occurred (assessment, payment, waiver)
  │   └─ FACT TABLE: Record in assessment_events, transaction_events, etc.
  │       └─ Must have: timestamp, event_type, correlation_id, immutability
  ├─ NO, it's computed metadata (status, balance, days overdue)
  │   └─ DERIVED STATE: Compute from facts at read time
  │       └─ Must have: view model constructor function, no persistence
  └─ MAYBE, it's configuration (grace period, payment frequency)
      └─ UPSTREAM DOMAIN: Lives in Class Configuration, not this domain
          └─ Reference via policy_version_id or upstream FK
```

### B. Anti-Pattern Catalog: What NOT to Persist

| Anti-Pattern | Example | Why It's Wrong | What to Do Instead |
|---|---|---|---|
| Mutable status flag | `paid_status = 'unpaid' \| 'paid' \| 'waived'` | Status changes when ledger changes; flag gets out of sync | Derive from PAYMENT/WAIVED events at read time |
| Denormalized counter | `amount_paid_denorm`, `months_behind` | Cached value diverges from facts; requires backfill/reconciliation | Sum authoritative PAYMENT events; calculate from due_date vs now |
| Duplicate event log | `StudentPaymentLog` and `Transaction` both store payments | Two sources of truth; reconciliation nightmares | Reference Ledger transaction via correlation_id |
| Class-level aggregate | `class_total_owed` on ClassEconomy | Updates require lock; partial reads give stale answers | Compute at read time from per-seat facts |

### C. Implementation: Canonical Fact Tables

Create or identify fact tables for your domain:

**Template Structure (per domain):**

```python
# app/models.py — Immutable fact table

class [DomainName]AssessmentEvent(db.Model):
    __tablename__ = '[domain]_assessment_events'
    
    # Identity
    id = db.Column(db.UUID, primary_key=True, default=uuid4)
    
    # Relationships
    seat_id = db.Column(db.UUID, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.UUID, db.ForeignKey('classes.id'), nullable=False)
    
    # What happened (immutable facts)
    event_type = db.Column(db.String(50), nullable=False)  # ASSESSMENT, PAYMENT, WAIVED, etc.
    correlation_id = db.Column(db.UUID, nullable=False)    # Links events for same instance
    internal_ref = db.Column(db.String(255), nullable=False)  # Stable lineage key
    
    # When and where
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    
    # References to authoritative sources
    policy_version_id = db.Column(db.UUID, nullable=True)   # FK to upstream Config
    ledger_transaction_id = db.Column(db.UUID, nullable=True)  # FK to Transaction (for PAYMENT)
    
    # Indexes for queries
    __table_args__ = (
        db.Index('ix_[domain]_events_seat_class', 'seat_id', 'class_id'),
        db.Index('ix_[domain]_events_type', 'event_type'),
        db.UniqueConstraint('correlation_id', 'event_type', name='uq_[domain]_event_instance'),
    )
```

**Key Principles:**
- No `updated_at` (facts don't update; append new events instead)
- No mutable columns for status, amount, balance
- Foreign keys to upstream domains (Config, Ledger) by ID, not by denormalized copy
- Explicit `event_type` enum (ASSESSMENT, PAYMENT, WAIVED, etc.)
- `correlation_id` groups events for one liability instance
- `internal_ref` tracks recurring relationship (same obligation type, same seat, recurring)

### D. Sign-Off Checklist

- [ ] Canonical fact table(s) exist (e.g., [domain]_assessment_events)
- [ ] Facts are immutable (no update-by-user columns)
- [ ] Foreign keys link to upstream authoritative sources (Ledger, Config)
- [ ] class_id present on all fact tables
- [ ] Timestamps on fact table for audit lineage
- [ ] Unique constraint on (correlation_id, event_type) to prevent duplicate events

---

## IV. Phase 2: Persistence (Migrations & Schema)

**Goal:** Database schema matches models; proper indexing for queries.

### A. Checklist: Migration Tasks

For each fact table:

- [ ] Create Alembic migration file
- [ ] Include idempotency helpers (`table_exists`, `column_exists`, etc.) — copy from `migrations/migration_template.py.mako`
- [ ] Test migration upgrade: `flask db upgrade`
- [ ] Test migration downgrade: `flask db downgrade`
- [ ] Test re-upgrade: `flask db upgrade`
- [ ] Create indexes on query columns (class_id, seat_id, event_type, correlation_id)
- [ ] Add foreign key constraints (seat_id → seats, class_id → classes, ledger_transaction_id → transactions)
- [ ] Verify no hardcoded constraint names (use dynamic discovery via inspector)

### B. Common Schema Errors to Avoid

| Error | Fix |
|---|---|
| `CREATE TABLE IF NOT EXISTS` without helper | Wrap in `if not table_exists(...)` |
| `ALTER TABLE ADD COLUMN` without checking first | Wrap in `if not column_exists(...)` |
| Hardcoded FK constraint name `fk_my_table_parent` | Use dynamic discovery: `get_foreign_keys_by_column()` |
| Dropped migration from git history | Never delete migrations; create a new corrective migration instead |
| Downgrade doesn't clean up | Verify downgrade actually reverses the schema (don't just `pass`) |

### C. Sign-Off Checklist

- [ ] Migration files exist for all new tables
- [ ] Migrations include idempotency helpers
- [ ] Migration upgrade/downgrade tested successfully
- [ ] Foreign key constraints present and enforced
- [ ] No hardcoded constraint names (discovered dynamically)

---

## V. Phase 3: Primitives (Service Layer Queries)

**Goal:** Core queries centralized in service layer; no ad-hoc SQL in routes.

### A. Identify Service Layer Functions Needed

For each read surface (student view, admin view, dashboard), list queries:

**Example (Obligations):**
- `get_assessment_events_for_seat_class(seat_id, class_id, obligation_type)`
- `get_satisfaction_events(correlation_id)`
- `get_bill_cycles_for_reference(internal_ref)`

**Template:**

```python
# app/services/[domain]_service.py

def get_[domain]_facts_for_seat_class(seat_id: UUID, class_id: UUID, **filters) -> List[dict]:
    """
    Fetch canonical facts for a seat in a class.
    
    CRITICAL: Returns facts scoped by class_id only.
    Multi-tenancy: Prevents cross-class data leak.
    
    Args:
        seat_id: Seat UUID
        class_id: Class UUID (multi-tenancy scoping)
        **filters: Optional event_type, correlation_id, etc.
    
    Returns:
        List of fact dicts (not ORM objects, to avoid session issues)
    """
    query = (
        [DomainName]AssessmentEvent.query
        .filter_by(seat_id=seat_id, class_id=class_id)  # MANDATORY: class_id filter
    )
    
    if 'event_type' in filters:
        query = query.filter_by(event_type=filters['event_type'])
    
    if 'correlation_id' in filters:
        query = query.filter_by(correlation_id=filters['correlation_id'])
    
    # Return dicts, not ORM objects (avoids SQLAlchemy session detachment in templates)
    return [
        {
            'id': row.id,
            'seat_id': row.seat_id,
            'event_type': row.event_type,
            'timestamp': row.timestamp,
            'correlation_id': row.correlation_id,
            # ... other fields
        }
        for row in query.all()
    ]
```

**Key Principles:**
- Every query filters by `class_id` (multi-tenancy enforcement)
- Use SQLAlchemy ORM (never raw SQL)
- Return dicts or dataclasses, not ORM objects (avoids session detachment)
- Docstring explains what the function returns and multi-tenancy constraints

### B. Decision Tree: ORM vs Raw SQL

```
Is the query simple enough for SQLAlchemy ORM?
  ├─ YES (query.filter, query.join, query.order_by)
  │   └─ USE ORM: Keep it readable and safe
  ├─ NO, need subquery or aggregation
  │   └─ USE ORM SUBQUERIES: Still safe, readable
  └─ NO, really complex (recursive, window function)
      └─ USE PARAMETERIZED RAW SQL: text() + bind params
          └─ NEVER string interpolation (f-strings = SQL injection)
```

### C. Sign-Off Checklist

- [ ] Core operations in service layer (not routes)
- [ ] All queries use SQLAlchemy ORM
- [ ] Every query includes class_id filter (multi-tenancy enforcement)
- [ ] Service functions have docstrings
- [ ] Unit tests cover each primitive operation (3+ tests minimum)
- [ ] Tests verify multi-tenancy scoping (cross-class data leak prevention)

---

## VI. Phase 4: Mutation Boundary (FEAT Layer)

**Goal:** All state changes go through FEAT layer with atomic semantics.

### A. Identify Mutations in Current Codebase

**Search for:**

```bash
# Routes that mutate state
grep -r "db.session.add\|db.session.commit" app/routes/

# Ad-hoc mutations outside FEAT
grep -r "\.create\(\|\.update\(\|\.delete\(" app/routes/

# State changes via form submission
grep -r "@.*_bp.route.*POST" app/routes/
```

### B. FEAT Wrapper Template

Create a FEAT for each domain mutation:

```python
# app/feats/[domain]_feats.py

from app.feats.base import requires_feat_context, FEATContext

@requires_feat_context("FEAT-[DOMAIN]-001")
def create_[domain]_assessment(
    seat_id: UUID,
    class_id: UUID,
    obligation_type: str,
    policy_version_id: UUID,
    idempotency_key: str,
) -> UUID:
    """
    Create an immutable assessment event.
    
    FEAT Contract:
    - Idempotent: Same idempotency_key always returns same result
    - Atomic: All-or-nothing (test rollback on failure)
    - Audit logged: correlation_id tracks the instance
    
    Args:
        seat_id: Seat being assessed
        class_id: Class context (multi-tenancy scoping)
        obligation_type: e.g., 'RENT', 'INSURANCE_PREMIUM'
        policy_version_id: Upstream policy config reference
        idempotency_key: UUID or string for exactly-once semantics
    
    Returns:
        correlation_id of the created assessment
    
    Raises:
        FeatureDisabledError: If domain feature disabled
        DuplicateAssessmentError: If duplicate idempotency_key detected
    """
    # Inside @requires_feat_context, you have access to FEATContext
    # Mutations are wrapped atomically
    
    # 1. Check idempotency
    existing = [DomainName]AssessmentEvent.query.filter_by(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        return existing.correlation_id  # Idempotent: return existing
    
    # 2. Create immutable fact
    correlation_id = uuid4()
    event = [DomainName]AssessmentEvent(
        seat_id=seat_id,
        class_id=class_id,
        event_type='ASSESSMENT',
        correlation_id=correlation_id,
        obligation_type=obligation_type,
        policy_version_id=policy_version_id,
        idempotency_key=idempotency_key,
        timestamp=utcnow(),
    )
    db.session.add(event)
    
    # 3. Optional: Create successor bill cycle if recurring
    if should_create_bill_cycle(...):
        bill_cycle = BillCycle(
            internal_ref=compute_internal_ref(...),
            cycle_number=1,
            cycle_boundary_at=compute_cycle_boundary(...),
            next_assessment_at=compute_next_assessment(...),
        )
        db.session.add(bill_cycle)
    
    # 4. Log mutation with audit trail
    audit_log(
        actor_id=...,
        action='CREATE_ASSESSMENT',
        correlation_id=correlation_id,
        details={...},
    )
    
    db.session.flush()  # Ensure database state is current
    return correlation_id
```

**Key Principles:**
- Wrapped in `@requires_feat_context("FEAT-NAME")` decorator
- Takes `idempotency_key` parameter (for exactly-once semantics)
- Returns immutable result (ID, not object)
- Audit logged with `correlation_id`
- All mutations happen inside FEAT context (atomic)

### C. Sign-Off Checklist

- [ ] All mutations wrapped in FEATContext (FEAT-* layer)
- [ ] No direct db.session.add/commit in routes
- [ ] FEAT implementations use idempotency_key
- [ ] Audit events logged (correlation_id tracking)
- [ ] FEAT boundary is enforced (test attempting direct mutation fails)

---

## VII. Phase 5: Read Models (View Models & Builders)

**Goal:** View models are generic, immutable, and scoped.

### A. View Model Design Template

```python
# app/services/[domain]_view_model.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass(frozen=True)
class Student[Domain]View:
    """
    Immutable view model for a single student's [domain] state.
    
    Answers: "What does this student [do/owe/have] in [domain]?"
    
    Generic over domain concepts (not rent-specific).
    Multi-tenancy scoped by class_id.
    """
    
    # Identity
    seat_id: UUID
    class_id: UUID
    student_name: str
    
    # Domain concept (generic parameter)
    domain_type: str  # e.g., 'RENT', 'INSURANCE_PREMIUM', 'FINE'
    
    # Current state (computed at read time)
    current_period: Dict[str, any]  # {amount_due, amount_paid, balance, is_paid, is_waived, days_overdue}
    
    # History
    prior_periods: List[Dict[str, any]]
    payment_history: List[Dict[str, any]]  # [{timestamp, amount, event_type}]
    
    # Aggregates
    totals: Dict[str, float]  # {total_assessed, total_paid, total_outstanding}
    settings: Dict[str, any]  # grace_period, frequency, etc. from upstream
    
    def is_current(self) -> bool:
        """Derived: Student has no past-due liabilities."""
        return self.current_period.get('days_overdue', 0) <= 0


@dataclass(frozen=True)
class Class[Domain]Summary:
    """
    Immutable aggregation for a class's [domain] state.
    
    Answers: "Which students are current? Which are behind?"
    
    Generic over domain concepts.
    Multi-tenancy scoped to one class only.
    """
    
    class_id: UUID
    domain_type: str
    summary_date: datetime
    
    # Aggregation
    status_breakdown: Dict[str, int]  # {up_to_date, outstanding, past_due_grace, past_due_overdue}
    
    # Per-student roster
    student_rows: List[Dict[str, any]]  # [{seat_id, student_name, status, due_date, amount_due, ...}]
```

**Key Principles:**
- `@dataclass(frozen=True)` for immutability
- Generic over `domain_type` parameter (not rent-specific)
- `current_period` is a dict (computed, not persisted)
- `status_breakdown` computed at read time (not denormalized)
- All identity scoped by `class_id`

### B. View Model Builder Template

```python
def build_student_[domain]_view(
    seat_id: UUID,
    class_id: UUID,
    domain_type: str,
) -> Optional[Student[Domain]View]:
    """
    Build immutable view for a student in a specific domain.
    
    Multi-tenancy: Scoped by class_id; returns None if no data.
    Genericity: Works for any domain_type (RENT, INSURANCE_PREMIUM, FINE, etc.)
    
    Args:
        seat_id: Seat UUID
        class_id: Class UUID (multi-tenancy scoping)
        domain_type: e.g., 'RENT', 'INSURANCE_PREMIUM'
    
    Returns:
        Student[Domain]View or None if no assessments
    """
    
    # 1. Fetch facts scoped by class_id
    assessments = get_[domain]_facts_for_seat_class(
        seat_id=seat_id,
        class_id=class_id,
        event_type='ASSESSMENT',
        domain_type=domain_type,
    )
    
    if not assessments:
        return None  # No data in this domain
    
    # 2. Resolve identity (student name)
    seat = Seat.query.get(seat_id)
    if not seat:
        return None
    identity = IdentityProfile.query.filter_by(seat_id=seat_id).first()
    student_name = identity.display_name if identity else f"Seat {seat_id}"
    
    # 3. Compute current period
    current_assessment = assessments[0]  # Most recent ASSESSMENT event
    satisfaction_events = get_satisfaction_events(
        correlation_id=current_assessment['correlation_id']
    )
    
    amount_paid = sum(
        e['amount'] for e in satisfaction_events
        if e['event_type'] == 'PAYMENT'
    )
    is_waived = any(e['event_type'] == 'WAIVED' for e in satisfaction_events)
    
    # 4. Compute timing (derived from bill cycles, not persisted)
    grace_period_days = ... # from settings
    days_overdue = (now() - current_assessment['due_date']).days
    
    current_period = {
        'amount_due': 0,  # Per v2.5 schema: amounts in PolicyVersion, not here
        'amount_paid': amount_paid,
        'balance': 0 - amount_paid,  # Negative if overpaid
        'is_paid': amount_paid >= 0,  # Simplified; real logic varies
        'is_waived': is_waived,
        'days_until_due': max(0, (due_date - now()).days),
        'days_overdue': max(0, days_overdue),
    }
    
    # 5. Compute status breakdown (not persisted)
    if current_period['is_waived'] or current_period['is_paid']:
        status = 'up_to_date'
    elif current_period['days_overdue'] <= 0:
        status = 'outstanding'
    elif current_period['days_overdue'] <= grace_period_days:
        status = 'past_due_grace'
    else:
        status = 'past_due_overdue'
    
    # 6. Build immutable view
    return Student[Domain]View(
        seat_id=seat_id,
        class_id=class_id,
        student_name=student_name,
        domain_type=domain_type,
        current_period=current_period,
        prior_periods=[...],  # Similar logic for older assessments
        payment_history=[...],  # List of PAYMENT events
        totals={...},
        settings={...},
    )


def build_class_[domain]_summary(
    class_id: UUID,
    domain_type: str,
) -> Class[Domain]Summary:
    """
    Build aggregation for an entire class.
    
    Multi-tenancy: Only data for this class.
    Genericity: Works for any domain_type.
    """
    
    # 1. Get all seats in class
    seats = Seat.query.join(ClassEconomy).filter_by(class_id=class_id).all()
    
    # 2. Build per-student views
    student_rows = []
    status_counts = {'up_to_date': 0, 'outstanding': 0, 'past_due_grace': 0, 'past_due_overdue': 0}
    
    for seat in seats:
        view = build_student_[domain]_view(seat.id, class_id, domain_type)
        if view:
            # Aggregate status
            status = 'up_to_date' if view.is_current() else 'outstanding'
            status_counts[status] += 1
            
            # Add to roster
            student_rows.append({
                'seat_id': view.seat_id,
                'student_name': view.student_name,
                'status': status,
                'due_date': view.current_period['due_date'],
                'amount_due': view.current_period['amount_due'],
                'amount_paid': view.current_period['amount_paid'],
                'balance': view.current_period['balance'],
                'days_overdue': view.current_period['days_overdue'],
                'is_waived': view.current_period['is_waived'],
            })
    
    # 3. Sort for UI (alphabetical by student name)
    student_rows.sort(key=lambda r: r['student_name'])
    
    return Class[Domain]Summary(
        class_id=class_id,
        domain_type=domain_type,
        summary_date=now(),
        status_breakdown=status_counts,
        student_rows=student_rows,
    )
```

### C. View Model Tests Template

```python
# tests/test_[domain]_view_models.py

import pytest
from uuid import uuid4
from app.services.[domain]_view_model import (
    build_student_[domain]_view,
    build_class_[domain]_summary,
)


def test_student_view_no_assessments():
    """View returns None if no assessments for seat+class."""
    view = build_student_[domain]_view(
        seat_id=uuid4(),
        class_id=uuid4(),
        domain_type='RENT',
    )
    assert view is None


def test_student_view_with_assessment():
    """View builds correctly with one assessment, no payments."""
    # Setup
    with app.app_context():
        class_scope = create_class_scope()
        seat = make_student_seat(class_scope)
        
        # Create assessment
        with FEATContext('FEAT-[DOMAIN]-001'):
            create_[domain]_assessment(
                seat_id=seat.id,
                class_id=class_scope.class_id,
                domain_type='RENT',
                policy_version_id=uuid4(),
                idempotency_key='test-1',
            )
        
        # Build view
        view = build_student_[domain]_view(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            domain_type='RENT',
        )
        
        # Verify
        assert view is not None
        assert view.seat_id == seat.id
        assert view.class_id == class_scope.class_id
        assert view.domain_type == 'RENT'
        assert view.current_period['amount_paid'] == 0
        assert view.current_period['is_paid'] == False


def test_student_view_with_payment():
    """View correctly shows paid state with PAYMENT event."""
    # ... similar setup ...
    
    # Create payment via FEAT
    with FEATContext('FEAT-[DOMAIN]-003'):
        satisfy_[domain]_obligation(
            correlation_id=...,  # from assessment
            amount=50.00,
            ledger_transaction_id=...,
        )
    
    view = build_student_[domain]_view(...)
    assert view.current_period['amount_paid'] == 50.00


def test_class_summary_multi_tenancy():
    """Summary only includes data for specified class."""
    with app.app_context():
        class1 = create_class_scope()
        class2 = create_class_scope()
        
        # Create students in class1
        seat1_1 = make_student_seat(class1)
        seat1_2 = make_student_seat(class1)
        
        # Create students in class2
        seat2_1 = make_student_seat(class2)
        
        # Create assessments
        for seat in [seat1_1, seat1_2, seat2_1]:
            with FEATContext('FEAT-[DOMAIN]-001'):
                create_[domain]_assessment(
                    seat_id=seat.id,
                    class_id=seat.class_id,
                    domain_type='RENT',
                    policy_version_id=uuid4(),
                    idempotency_key=str(seat.id),
                )
        
        # Build summary for class1 only
        summary = build_class_[domain]_summary(
            class_id=class1.class_id,
            domain_type='RENT',
        )
        
        # Verify: only class1 students in rows
        assert len(summary.student_rows) == 2
        assert all(r['seat_id'] in [seat1_1.id, seat1_2.id] for r in summary.student_rows)
        assert not any(r['seat_id'] == seat2_1.id for r in summary.student_rows)


def test_class_summary_status_breakdown():
    """Status breakdown correctly categorizes students."""
    # ... create students with various states ...
    
    summary = build_class_[domain]_summary(...)
    assert summary.status_breakdown['up_to_date'] == 2
    assert summary.status_breakdown['outstanding'] == 1
    assert summary.status_breakdown['past_due_grace'] == 1
```

### D. Sign-Off Checklist

- [ ] View model dataclasses are frozen (immutable)
- [ ] Constructor functions are generic (take domain_type parameter)
- [ ] Status breakdown is computed (not just raw query results)
- [ ] All queries in view model constructors scoped by class_id
- [ ] View models tested with unit tests (5+ tests minimum)

---

## VIII. Phase 6: Surface Inventory (Routes & Templates)

**Goal:** Routes and templates use view models, not legacy variables.

### A. Route Refactoring Template

**BEFORE (Legacy):**

```python
@student_bp.route('/rent')
@login_required
def student_rent():
    student = get_current_student()
    assessments = Rent.query.filter_by(student_id=student.id).all()
    
    # Ad-hoc aggregation in route
    rent_status = 'paid' if assessments[0].is_paid else 'unpaid'
    payment_log = []
    for assessment in assessments:
        for payment in assessment.payments:
            payment_log.append({
                'date': payment.created_at,
                'amount': payment.amount,
            })
    
    unpaid_rent_log = [a for a in assessments if not a.is_paid]
    current_coverage_due_date = assessments[0].due_date if assessments else None
    
    return render_template('student_rent.html',
        student=student,
        rent_status=rent_status,
        payment_log=payment_log,
        unpaid_rent_log=unpaid_rent_log,
        current_coverage_due_date=current_coverage_due_date,
        # ... 10+ more variables
    )
```

**AFTER (View Model):**

```python
@student_bp.route('/rent')
@login_required
def student_rent():
    context = resolve_canonical_context()
    
    # Single call to view model builder
    view = build_student_obligation_view(
        seat_id=context.seat_id,
        class_id=context.class_id,
        obligation_type='RENT',
    )
    
    if not view:
        return render_template('no_rent_obligations.html')
    
    return render_template('student_rent.html', view=view)
```

**Key Changes:**
- 1 view model builder call (replaces all ad-hoc queries and aggregation)
- No complex template variables (just `view`)
- No business logic in route (it's in the builder)
- Purely GET, no side effects

### B. Template Contract

**BEFORE (Legacy):**

```jinja
Current status: {{ rent_status }}
Due date: {{ current_coverage_due_date | format_date }}

<h3>Payment History</h3>
{% for payment in payment_log %}
  {{ payment.date }}: {{ payment.amount }}
{% endfor %}

<h3>Unpaid Obligations</h3>
{% for unpaid in unpaid_rent_log %}
  {{ unpaid.due_date }}: ${{ unpaid.amount }} unpaid
{% endfor %}
```

**AFTER (View Model):**

```jinja
Current status: {% if view.current_period.is_paid %}Paid{% else %}Unpaid{% endif %}
Due date: {{ view.current_period.due_date | format_date }}

<h3>Payment History</h3>
{% for payment in view.payment_history %}
  {{ payment.timestamp }}: {{ payment.amount }}
{% endfor %}

<h3>Current Period</h3>
{% if view.current_period.is_waived %}
  Waived
{% elif view.current_period.is_paid %}
  Paid ({{ view.current_period.amount_paid }})
{% else %}
  Outstanding ({{ view.current_period.days_overdue }} days overdue)
{% endif %}
```

**Key Changes:**
- Template receives `view` object (frozen dataclass)
- No additional aggregation in template (Jinja2 `{% for %}` only iterates pre-built lists)
- Fields are pre-computed (e.g., `is_paid`, `days_overdue`)
- No raw persistence objects (no `student.payments`, no `assessment.due_date`)

### C. Admin Surface Template

```python
@admin_bp.route('/rent-settings')
@admin_required
def rent_settings():
    context = resolve_canonical_context()
    selected_class_id = request.args.get('class_id', context.class_id)
    
    # Verify teacher can access this class
    if not can_teacher_access_class(context.user_id, selected_class_id):
        abort(403)
    
    # Single call to class summary
    summary = build_class_obligation_summary(
        class_id=selected_class_id,
        obligation_type='RENT',
    )
    
    return render_template('admin_rent_settings.html',
        summary=summary,
        class_name=get_class_display_name(selected_class_id),
    )
```

### D. Sign-Off Checklist

- [ ] Routes call view model constructors (build_*_view)
- [ ] Routes pass view_model object to template
- [ ] No legacy aggregation variables in render_template context
- [ ] Templates access view_model fields directly
- [ ] No raw persistence objects passed to templates

---

## IX. Phase 7: Rewire (Eliminate Ad-Hoc Logic)

**Goal:** Ad-hoc code replaced with canonical builders; routes become thin request handlers.

### A. Refactoring Checklist

For each route using the domain:

- [ ] Find all ad-hoc queries and move to service layer
- [ ] Find all business logic (status computation, aggregation) and move to view model
- [ ] Remove direct object references (e.g., `student.property` → `view.current_period['property']`)
- [ ] Remove legacy helper function calls
- [ ] Verify route is <100 lines for GET handlers
- [ ] Verify GET handler has no side effects (no db.session.commit)

### B. Common Patterns to Eliminate

| Pattern | Example | Fix |
|---|---|---|
| 24-period walk | `for period in range(24): balance += ...` | Move to view model constructor |
| Manual status calculation | `if paid_amount >= amount: status = 'paid'` | Compute in view model |
| Denormalized column access | `student.rent_status_flag` | Derive from facts in view model |
| Ad-hoc joins | `assessments[0].payments[0].amount` | Fetch via service primitives |
| Legacy helper calls | `_build_rent_coverage_context()` | Replace with view model call |

### C. Sign-Off Checklist

- [ ] Manual student/class queries moved to view model builders
- [ ] Status computation logic moved to view model
- [ ] No legacy helpers imported/used in routes
- [ ] Route delegates business logic to view model
- [ ] GET handlers are pure (no side effects)

---

## X. Phase 8: Verify (Testing & Coverage)

**Goal:** Tests prove canonical model is correct and multi-tenant safe.

### A. Test Strategy by Phase

| Phase | What to Test | Minimum Tests |
|---|---|---|
| Phase 1 | Immutability (can't mutate facts after creation) | 1 |
| Phase 2 | Migration up/down; schema matches model | 1 (manual verification) |
| Phase 3 | Service primitives; multi-tenancy scoping | 3 (1 happy path, 1 multi-tenancy, 1 edge case) |
| Phase 4 | FEAT idempotency; atomicity; rollback | 2 (1 idempotent, 1 rollback) |
| Phase 5 | View model construction; derivation correctness; multi-tenancy | 5 (1 no data, 1 with data, 1 payment, 1 status, 1 multi-tenancy) |
| Phase 6 | Route returns view model; template renders | 2 (1 student, 1 admin) |
| Phase 7 | Legacy code removed; routes are thin | 1 (inspection) |
| Phase 8 | Full integration test with canonical identity | 1 |

### B. Multi-Tenancy Test Template

```python
def test_view_model_respects_multi_tenancy():
    """View model only returns data scoped to its class."""
    with app.app_context():
        # Create two classes
        class1 = create_class_scope()
        class2 = create_class_scope()
        
        # Create students in each class
        seat1 = make_student_seat(class1)
        seat2 = make_student_seat(class2)
        
        # Create assessments
        with FEATContext('FEAT-[DOMAIN]-001'):
            create_[domain]_assessment(
                seat_id=seat1.id, class_id=class1.class_id, ...
            )
            create_[domain]_assessment(
                seat_id=seat2.id, class_id=class2.class_id, ...
            )
        
        # Query for class1 only
        view1 = build_student_[domain]_view(
            seat_id=seat1.id,
            class_id=class1.class_id,  # ← scoping key
            domain_type='RENT',
        )
        
        # Verify: only sees class1 data
        assert view1 is not None
        assert view1.class_id == class1.class_id
        
        # Try to leak: query class1 seat with class2 context
        view_leaked = build_student_[domain]_view(
            seat_id=seat1.id,
            class_id=class2.class_id,  # ← wrong class
            domain_type='RENT',
        )
        
        # Verify: data does NOT leak
        assert view_leaked is None  # No assessments in class2 for seat1
```

### C. Edge Case Tests

```python
def test_view_handles_empty_class():
    """View model returns valid structure even for class with no data."""
    summary = build_class_[domain]_summary(
        class_id=uuid4(),  # Empty class
        domain_type='RENT',
    )
    assert summary is not None
    assert summary.status_breakdown == {'up_to_date': 0, ...}
    assert summary.student_rows == []


def test_view_handles_overpayment():
    """View model correctly handles amount_paid > amount_due."""
    # Create assessment for $50
    # Create payments totaling $75
    view = build_student_[domain]_view(...)
    assert view.current_period['balance'] == -25.0  # Overpaid by $25
    assert view.current_period['is_paid'] == True
```

### D. Sign-Off Checklist

- [ ] Minimum 5 unit tests for view model (exist and pass)
- [ ] Multi-tenancy test exists and passes (proves class_id scoping)
- [ ] Status breakdown computation tested
- [ ] No regression in existing tests

---

## XI. Phase 9: Legacy Deletion (Dead Code Removal)

**Goal:** Dead code is removed; only canonical code remains.

### A. Identification Checklist

Find and remove:

- [ ] Mutable status flag columns (`is_paid`, `status_flag`, etc.)
- [ ] Denormalized counter columns (`amount_paid_denorm`, `months_behind`, etc.)
- [ ] Legacy helper functions (`_build_*_context`, `_is_*_period_paid`, etc.)
- [ ] Ad-hoc query functions (replaced by service primitives)
- [ ] Legacy aggregation loops in routes
- [ ] Template variables that duplicated view model fields

### B. Deletion Verification

```bash
# 1. Verify no references remain
grep -r "_build_[domain]_context" app/
grep -r "[domain]_status_flag" app/
grep -r "[domain]_denorm" app/

# 2. Verify imports are used
python3 -m py_compile app/routes/admin.py
python3 -m py_compile app/routes/student.py

# 3. Verify tests still pass
pytest tests/test_[domain]_view_models.py -v

# 4. Verify no dangling code
grep -r "TODO.*legacy\|FIXME.*[domain]" app/
```

### C. Sign-Off Checklist

- [ ] All legacy variables removed from render_template context
- [ ] No ad-hoc aggregation loops remain in routes
- [ ] All tests pass after deletion
- [ ] No dangling references to deleted code

---

## XII. Phase 10: Audit (Sign-Off)

**Goal:** All prior phases verified; domain is production-ready.

Use the checklist in `.claude/rules/qa_audit_domain_reconstruction.md`. Every MANDATORY criterion must be verified; GUIDANCE criteria are recommended but do not block approval.

### Key Verification Steps

```bash
# 1. Run full test suite for the domain
pytest tests/test_[domain]_view_models.py -v

# 2. Check for any regression in other tests
pytest tests/ -v --tb=short

# 3. Verify schema is correct
flask db current
flask db heads  # Should show exactly 1 head

# 4. Verify code compiles
python3 -m py_compile app/routes/admin.py
python3 -m py_compile app/services/[domain]_view_model.py

# 5. Check git status
git status
git log --oneline | head -10  # Should show phase-labeled commits
```

### Sign-Off Checklist

- [ ] Audit document (certification) exists and is complete
- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No regressions in existing test suite
- [ ] Branch is pushed to remote
- [ ] Git status is clean

---

## XIII. Anti-Pattern Catalog

Reference this when reviewing code to identify what NOT to do.

| Anti-Pattern | Red Flag | What to Do Instead |
|---|---|---|
| Mutable status column | `status ENUM('paid', 'unpaid', 'waived')` on assessment table | Derive status from PAYMENT/WAIVED events in view model |
| Denormalized amount | `amount_paid` on assessment row (copies Ledger) | Reference Ledger transaction via correlation_id |
| Cached counter | `uses_remaining INT` on entitlement row | Compute as `grant_count - consumption_count` at read time |
| Ad-hoc aggregation in route | `for period in range(24): ...` 40-line loop | Move to view model constructor function |
| Complex Jinja2 logic | `{% if x and (y or z) and not w %}...{% endif %}` repeated | Pre-compute in view model, pass boolean flag |
| Raw SQL in route | `db.session.execute("SELECT * FROM ... WHERE ...")` | Use SQLAlchemy ORM (query.filter, query.join) |
| Direct object mutation | `assessment.is_paid = True; db.session.commit()` | Append PAYMENT event; never mutate facts |
| Cross-domain fact storage | Obligations table has Ledger amount columns | Facts stored in Ledger; Obligations references via FK |
| Per-domain-type code path | `if domain == 'RENT': ... elif domain == 'INSURANCE': ...` | Generic builders; logic parameterized by domain_type |
| Legacy helper with side effects | `_build_rent_context()` writes to db | Pure functions only; return immutable results |

---

## XIV. Glossary & Terms

| Term | Meaning | Example |
|---|---|---|
| **Fact** | Immutable record of something that happened | ASSESSMENT event, PAYMENT event |
| **Event** | Type of fact | ASSESSMENT, PAYMENT, WAIVED |
| **Correlation ID** | UUID linking events for one instance | All events for one loan/obligation share correlation_id |
| **Internal Ref** | Stable key for recurring relationship | Same seat+obligation_type shares internal_ref across cycles |
| **Derived State** | Computed at read time, not persisted | is_paid, balance, days_overdue |
| **Immutable** | Cannot be updated after creation; only append new events | Facts must be immutable; new events append, not update |
| **View Model** | Frozen dataclass built from facts; passed to templates | StudentObligationView, ClassObligationSummary |
| **Builder Function** | Creates view model from facts via read service | build_student_obligation_view() |
| **Multi-Tenancy** | Data isolation by class_id; no cross-class leakage | Every query filters by class_id |
| **Idempotency** | Same input always produces same output; safe to retry | FEAT with idempotency_key ensures exactly-once semantics |

---

## XV. Recommended Reading Order

For an agent implementing a new domain:

1. **SOP-DEV-002** — Overview of the 10 phases
2. **This playbook (SOP-DEV-003)** — Step-by-step guidance for each phase
3. **DOM-OBL-001** — Reference concrete example (obligations)
4. **MAP-UI-002** — View model and route pipeline pattern
5. **qa_audit_domain_reconstruction.md** — Verification checklist
6. **.claude/rules/multi-tenancy.md** — Multi-tenancy enforcement rules
7. **.claude/rules/testing.md** — Test requirements and patterns

---

**Last Updated:** 2026-07-25
**Authority:** SOP-DEV-002, DOM-CORE-002, INV-ARC-009, MAP-UI-002, multi-tenancy.md, testing.md
**Applicable To:** Any domain reconstruction following SOP-DEV-002 pattern

**Status:** Ready for agent implementation of new domains (INSURANCE_PREMIUM, FINE, FEE, etc.)
