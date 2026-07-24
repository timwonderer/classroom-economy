# Obligations Domain End-to-End Audit Instruction

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-OBL-001 | 1.0 | 2026-07-24 | QA/Review | [TBD] |

---

## Purpose

This audit validates that the Obligations domain surfaces have been rewired to the canonical v2 architecture with correct event-based schema (event_type discriminator), Ledger-backed amounts, and FEAT-enforced mutation boundaries.

This is a strict checklist. Treat the route/template audit as the checklist source. Do not use discovery to invent new scope.

**Outcome:** either `AUDIT PASS` or `AUDIT FAIL` with explicit findings, evidence, and missing items.

---

## Pre-Audit Setup

### 1. Branch and Environment
- [ ] Checked out the target audit branch
- [ ] Database migrated to current head
- [ ] Test database initialized and accessible
- [ ] Working tree clean before audit begins

### 2. Read Authoritative Documents
Read these in order before starting the audit:

- [ ] `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- [ ] `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- [ ] `docs/DOMAIN/DOM-LED-001_LEDGER_AND_FINANCIAL_DOMAIN.md` (if exists)
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-002_ADVANCE_BILL_CYCLE.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-003_SATISFY_OBLIGATION.md`
- [ ] `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- [ ] `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_REQUEST_HANDLER_AUTHORITY_AND_SIDE_EFFECT_BOUNDARIES.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

## Part A: Schema and Data Model Audit

### A1: Canonical Obligation Tables
Verify the domain owns ONLY the two canonical tables per DOM-OBL-001 §VI and no retired persistence is treated as authority.

**Canonical (owned):**
- [ ] `assessment_events` (immutable obligation event log)
- [ ] `bill_cycles` (recurring reminder state, identity-blind)

**Not canonical (do not own):**
- [ ] `obligation_lifecycle` is NOT a canonical domain table (may exist for status caching but is not authority)
- [ ] No separate `obligation_satisfaction` table (events in assessment_events only)
- [ ] No separate `obligation_reversal` table (reversal is not authorized per contract)

Check for retired or forbidden authority-bearing fields/patterns:

- [ ] no `paid_amount` column on assessment_events
- [ ] no `satisfied` mutable flag on assessment_events
- [ ] no `lifecycle_status` field duplicating derived state
- [ ] no direct store of assessment amount (read from Ledger via ledger_transaction_id)

### A2: Event-Type Discriminator Schema
Verify event_type correctly discriminates obligation event types per DOM-OBL-001 §VII.

**Authorized event types:**
- [ ] `ASSESSMENT` events only (exactly one per individual liability)
- [ ] `PAYMENT` events (multiple allowed per assessment, linked to Ledger via ledger_transaction_id)
- [ ] `WAIVED` events (rent-only, no Ledger movement)

**Not authorized:**
- [ ] `REVERSED` events do NOT exist (reversal is not part of domain contract)
- [ ] No other event_type values

Check for derived state only (no flags):
- [ ] No mutable status flags; all state derived from event sequence
- [ ] No cached `paid`, `satisfied`, or `overdue` columns

### A3: Class Configuration Integration
Verify Class Configuration domain owns rent/insurance policy terms.

- [ ] `rent_settings` owned by Class Configuration (not Obligations)
- [ ] Obligations reads `rent_settings` for contract terms only (no writes)
- [ ] No direct mutation of rent_settings from Obligations routes
- [ ] Bill cycles do not encode business meaning (identity-blind)

### A4: Ledger Integration
Verify Ledger (Financial domain) owns amounts and Obligations only references.

- [ ] `ledger_transaction_id` present on PAYMENT events (nullable, required for PAYMENT)
- [ ] Amount read from Transaction.amount, never cached in assessment_events
- [ ] No duplicate amount storage across domains
- [ ] get_total_paid_for_assessment() sums from Ledger, not obligation fields

### A5: Required Table Checks
Use schema inspection against the current database to confirm the two canonical tables:

- [ ] `assessment_events` is append-only event history (event_type: ASSESSMENT|PAYMENT|WAIVED only)
- [ ] `bill_cycles` contains ONLY temporal reminder state (no seat/class identity, no amount, no business meaning)
- [ ] `rent_settings` is class-scoped configuration (not per-seat; owned by Class Configuration domain)

**DO NOT verify:**
- [ ] `obligation_lifecycle` is NOT a canonical domain authority table (if it exists, it's a cache, not authority)

---

## Part B: FEAT Layer Audit

### B1: FEAT-OBLI-001 (Assessment/Create Obligation)
Audit the assessment creation path.

- [ ] `FEAT-OBLI-001` is the only lawful writer for `ASSESSMENT` events
- [ ] Assessment creates exactly one immutable record per liability instance
- [ ] internal_ref and correlation_id are set and stable
- [ ] Assessment does not store amount; amount supplied by upstream contract or provided caller
- [ ] Rent assessment uses rent_settings terms from Class Configuration

### B2: FEAT-OBL-002 (Advance Bill Cycle)
Audit recurring bill cycle progression.

- [ ] `FEAT-OBL-002` is the only lawful writer for `bill_cycles` rows
- [ ] Bill cycle is identity-blind (internal_ref only, no seat/class)
- [ ] Bill cycle creates successor reminder only when upstream relationship still legal
- [ ] Cycle boundary does not mutate canonical obligation truth

### B3: FEAT-OBL-003 (Satisfy Obligation)
Audit payment and waiver paths.

- [ ] `FEAT-OBL-003` is the only lawful writer for `PAYMENT` and `WAIVED` events
- [ ] PAYMENT requires lawful Ledger transaction reference (ledger_transaction_id)
- [ ] PAYMENT may be repeated for partial payment (multiple events per assessment)
- [ ] WAIVED is rent-only; creates no Ledger movement
- [ ] Satisfaction is immutable once recorded
- [ ] Multiple satisfaction events allowed for single assessment

### B4: Mutation Boundary Enforcement
Verify FEAT context enforcement.

- [ ] All create/update operations in services call db.session.add() within FEAT context
- [ ] Direct route-level db.session.commit() on obligations tables fails with FEATContextError
- [ ] Tests wrap all mutations in FEATContext() manager
- [ ] No bypass paths exist that skip FEAT wrapper

---

## Part C: Route Wiring Audit

Use `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` as the checklist source. For each row marked `REWIRED` or `VERIFIED`, verify the actual code and template contract.

### C1: Student Rent View
File: `app/routes/student.py` (GET /student/rent) and `templates/student_rent.html`

- [ ] route calls canonical query helpers (get_rent_assessments_for_cycle, get_total_paid_for_assessment, get_rent_waivers_for_seat)
- [ ] GET handler is pure (no mutations, per INV-ARC-007)
- [ ] payment_history derived from assessments + PAYMENT events + Ledger amounts
- [ ] period_status reflects derived state (satisfied/outstanding) without mutable flags
- [ ] template fields match the route view model
- [ ] no access to removed .satisfactions relationship
- [ ] no direct amount access from obligation table

### C2: Admin Rent Settings
File: `app/routes/admin.py` (GET|POST /admin/rent-settings) and `templates/admin_rent_settings.html`

- [ ] GET handler reads from canonical sources (RentSettings, query helpers)
- [ ] GET handler is pure (no mutations)
- [ ] POST handler calls FEAT for updates (if mutating rent_settings)
- [ ] payment_log built from canonical get_rent_payment_history() helper
- [ ] payment_log amounts read from Ledger via ledger_transaction_id
- [ ] unpaid_rent_log shows only assessment events without paid_amount cached field
- [ ] template renders payment and unpaid tables from canonical sources
- [ ] no access to removed .satisfactions
- [ ] class_id scoping enforced in all queries

### C3: Admin Dashboard
File: `app/routes/admin.py` (GET /admin/) and `templates/admin_dashboard.html`

- [ ] GET handler is pure (no mutations)
- [ ] Dashboard uses canonical read helpers for rent/insurance pending counts
- [ ] No schema field access violations (no removed .satisfactions, no .paid_amount)
- [ ] Pending actions derived from current state only
- [ ] Recent activity uses obligations_service queries only

### C4: Admin Economy Health
File: `app/routes/admin.py` (GET /admin/economy-health) and `templates/admin_economy_health.html`

- [ ] GET handler is pure (no mutations)
- [ ] Economy health reads rent_settings via class configuration domain
- [ ] Insurance counts derived from canonical sources
- [ ] No direct obligation field access violations
- [ ] CWI/payroll calculations independent of obligation mutations

### C5: Rent Settings Integration
Files: All surfaces touching rent configuration

- [ ] All routes read rent_settings via RentSettings.query.filter_by(class_id=...).first()
- [ ] No direct obligation field lookups for rent amount
- [ ] Settings scoped by class_id, never global or teacher-scoped alone
- [ ] Late penalty, grace period applied at view time, not persisted in obligation

---

## Part D: Template Audit

For each audited surface, confirm that the rendered template only dereferences fields that exist on the current view model.

- [ ] `student_rent.html`
- [ ] `admin_rent_settings.html`
- [ ] `admin_dashboard.html`
- [ ] `admin_economy_health.html`

Required checks:

- [ ] no template reads of removed fields (paid_amount, satisfied, lifecycle_status)
- [ ] no template access to .satisfactions relationship
- [ ] no template reliance on stale row shapes
- [ ] no template-side reconstruction of obligation state
- [ ] all action forms point at the current route surface
- [ ] payment_log and unpaid_rent_log templates only access provided fields

---

## Part E: Query Helper Audit

Verify canonical query helpers implement DOM-OBL-001 correctly.

### E1: get_rent_assessments_for_cycle()
- [ ] Filters by event_type='ASSESSMENT' only
- [ ] Scoped by class_id, month, year
- [ ] Returns only ASSESSMENT events (no PAYMENT or WAIVED)
- [ ] Optional seat_ids filtering

### E2: get_payment_events_for_assessment()
- [ ] Filters by event_type='PAYMENT'
- [ ] Filters by internal_ref matching assessment
- [ ] Scoped by class_id
- [ ] Returns multiple events (partial payment support)

### E3: get_total_paid_for_assessment()
- [ ] Sums Ledger amounts via ledger_transaction_id
- [ ] Ignores obligation table amounts
- [ ] Handles null ledger_transaction_id gracefully
- [ ] Scoped by class_id

### E4: get_rent_payment_history()
- [ ] Returns (assessment, state_events) tuples
- [ ] Scoped by seat_id and class_id
- [ ] State events include PAYMENT and WAIVED only (no REVERSED)
- [ ] Ordered by coverage period (descending)

### E5: get_rent_waivers_for_seat()
- [ ] Filters by event_type='WAIVED'
- [ ] Scoped by seat_id and class_id
- [ ] Returns WAIVED events only
- [ ] Includes coverage_start_time and coverage_end_time for period matching

---

## Part F: Completion Criteria

The audit passes only if all of the following are true:

- [ ] the MAP checklist rows for A1-A8 surfaces are either `REWIRED` or `VERIFIED`, not `NEEDS_REWIRE`
- [ ] the current code matches the authority and persistence model in DOM-OBL-001
- [ ] no stale template field access remains on audited surfaces
- [ ] no direct domain boundary violations remain in the audited paths
- [ ] all event_type discriminator usage is correct (ASSESSMENT|PAYMENT|WAIVED only; NO REVERSED)
- [ ] all amount reads use Ledger via ledger_transaction_id, never obligation fields
- [ ] all FEAT mutation boundaries are enforced (FEATContext required)
- [ ] get_rent_payment_history() or equivalent helper used for complex reads
- [ ] all findings are documented with exact file, route, template references, and line numbers

If any requirement is not proven by current evidence, mark `AUDIT FAIL` and record the specific missing proof.

---

## Audit Sign-Off

**Audit Date:** [To be filled]  
**Auditor:** [To be filled]  
**Result:** [ ] PASS / [ ] FAIL  
**Blocking Findings:** [List if any]  
**Notes:** [Space for auditor observations]

---

## Reference Materials

- **DOM-OBL-001**: Obligations domain authority (canonical truth, persistence, operations)
- **OBLIGATIONS_DOMAIN_REWIRE_CHECKLIST.md**: Surface inventory and status
- **OBLIGATIONS_DOMAIN_CERTIFICATION_AUDIT.md**: Phase 10 certification evidence
- **test_phase8_a1_a2_surfaces.py**: Verification tests for A1-A8
- **SOP-DEV-002**: Reconstruction workflow reference
