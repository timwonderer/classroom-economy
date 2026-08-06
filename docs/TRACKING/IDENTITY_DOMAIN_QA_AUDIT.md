# SOP-DEV-002a: Domain Reconstruction QA Audit

**Domain:** Identity (DOM-IDEN-001/002/003/006)
**Purpose:** Verification that a domain reconstruction follows all 10 SOP-DEV-002 phases and meets production readiness standards.
**Authority:** SOP-DEV-002, INV-CORE-000, INV-ARC-007, INV-ARC-016, INV-ARC-021, DOM-CORE-002

---

## Pre-Audit Checklist

### Repository State
- [x] All commits are on the feature branch (never on main)
- [ ] Branch is up-to-date with origin/codex/v2.0
- [ ] No uncommitted changes (`git status` is clean)
- [x] No merge conflicts

### Documentation
- [x] Memory file exists documenting the work
- [x] Certification audit document exists
- [x] Phase completion notes are clear and dated

---

## Phase 0: Boundary

**Goal:** Domain scope is clearly defined and authorized.

### Sign-Off Criteria

**MANDATORY:**
- [x] Domain specification document exists (DOM-* or INV-* authority) — *DOM-IDEN-001, DOM-IDEN-002, DOM-IDEN-003, DOM-IDEN-006*
- [x] Scope is explicitly generic (not tied to one obligation type, entity type, or feature)
- [x] Multi-tenancy model specified (class_id scoping for educational domains)

---

## Phase 1: Truth

**Goal:** Canonical facts are defined and immutable.

### Sign-Off Criteria

**MANDATORY:**
- [x] Canonical fact table(s) exist for domain entities (`users`, `seats`, `classes`, `identity_profiles`)
- [ ] Facts are immutable (no user-facing update columns; new facts append, don't mutate) — *Failed: Identity Profiles may still have mutable traits that need to be audited.*
- [x] Foreign keys link domain facts to authoritative sources in other domains
- [x] Domain does not duplicate authoritative amounts/values from other domains
- [x] Multi-tenancy key (class_id or equivalent) present on all fact tables (`seats`, `classes`, `identity_profiles`)
- [x] Timestamps (created_at or equivalent) on fact tables for audit lineage

---

## Phase 2: Persistence

**Goal:** Database schema matches models; migrations are idempotent; indexes support queries.

### Sign-Off Criteria

**MANDATORY:**
- [x] Migration files exist for all new tables
- [x] Migrations include idempotency helpers (table_exists, column_exists, etc.)
- [x] Migration upgrade/downgrade tested successfully
- [x] Foreign key constraints present and enforced at database level
- [x] No hardcoded constraint names; constraints discovered dynamically via schema inspection

---

## Phase 3: Primitives

**Goal:** Core domain queries centralized in service layer; all queries use ORM; multi-tenancy scoped.

### Sign-Off Criteria

**MANDATORY:**
- [x] Core domain queries implemented in service layer functions (`app/services/identity_service.py`)
- [x] All queries use SQLAlchemy ORM (no raw SQL in service layer)
- [x] Every query that involves domain entities scoped by class_id (multi-tenancy enforcement)
- [x] Unit tests verify each primitive operation works correctly
- [x] Tests include multi-tenancy verification (no cross-class data leakage)

---

## Phase 4: Mutation Boundary

**Goal:** All state changes go through FEAT layer; mutations are atomic and logged.

### Sign-Off Criteria

**MANDATORY:**
- [x] All domain state mutations wrapped in FEATContext (FEAT-* layer)
- [x] Routes never directly call db.session.add/commit
- [x] FEAT implementations use idempotency_key for exactly-once semantics
- [x] Mutation events logged with correlation_id for audit trail
- [x] FEAT boundary enforced (test verifies direct mutation blocked)

---

## Phase 5: Read Models

**Goal:** View models are immutable, generic, and scoped; they hide persistence shape from consumers.

### Sign-Off Criteria

**MANDATORY:**
- [x] View model dataclasses are frozen (immutable) — *COMPLETE: IdentityProfileView created with @dataclass(frozen=True)*
- [x] Constructor functions are generic (parameterized, not hardcoded to one entity type) — *build_identity_profile_view(seat_id, class_id)*
- [x] Derived state is computed at read time (status, balances, counts) — *full_name, last_initial computed properties*
- [x] All queries in view model constructors scoped by class_id — *Verified in build_identity_profile_view()*
- [x] View models tested with unit tests covering happy path, edge cases, multi-tenancy — *5 tests: happy path, properties, not found, scoping, immutability*

---

## Phase 6: Surface Inventory

**Goal:** Routes and templates consume view models; no legacy variables passed to templates.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Routes call view model constructors — *PENDING: Phase 5 unblocked; requires route rewiring*
- [ ] Routes pass view_model object to template
- [ ] No legacy aggregation variables in render_template context
- [ ] Templates access view_model fields directly (not persistence objects)

---

## Phase 7: Rewire

**Goal:** Ad-hoc aggregation logic replaced with canonical builders; routes become thin request handlers.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Manual entity queries moved to view model builders — *PENDING: Phase 5 unblocked; requires route migration*
- [ ] Status/aggregation computation moved from routes to view models
- [ ] No legacy helper functions imported in routes
- [ ] Route logic delegates to view model; routes are thin handlers
- [x] GET handlers are pure (no db.session.commit or side effects)

---

## Phase 8: Verify

**Goal:** Tests prove canonical model is correct and multi-tenant safe.

### Sign-Off Criteria

**MANDATORY:**
- [x] View model tests exist and pass covering: happy path, edge cases, multi-tenancy — *COMPLETE: 5 tests in tests/test_view_model_builders.py, all passing*
- [x] Multi-tenancy test verifies no cross-class data leakage — *test_build_identity_profile_view_scoped_by_class_id verifies class_id boundary*
- [ ] No regression in existing tests — *PENDING: tests/dom/identity/test_admin_membership_gates.py has pre-existing failures (unrelated to Phase 5)*
- [ ] Domain-specific operations tested (e.g., status derivation, payment application) — *PARTIAL: View model display operations tested; payment operations N/A for identity domain*

---

## Phase 9: Legacy Deletion

**Goal:** Dead code removed; only canonical code remains.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Legacy aggregation variables removed from render_template context
- [ ] Ad-hoc aggregation loops and helper functions removed from routes
- [ ] All tests pass after deletion
- [ ] No dangling references to deleted code

---

## Phase 10: Audit

**Goal:** All prior phases verified; domain is production-ready.

### Sign-Off Criteria

**MANDATORY:**
- [x] Audit document (certification) exists and is complete
- [x] Code compiles without errors
- [ ] All tests pass — *FAILED*
- [ ] No regressions in existing test suite — *FAILED*
- [x] Branch is pushed to remote
- [ ] Git status is clean

---

## Sign-Off Statement

**QA Reviewer:** Antigravity AI

**Date:** 2026-08-04 (Updated 2026-08-05)

**Status:** 🟡 CONDITIONAL (Phase 5 Complete; Phases 6-7 Pending)

**Mandatory Criteria Status:** Phase 5 criteria are met. Phases 6-7 are blocked on route rewiring work. Phases 9-10 pending test execution.

**Comments:**

```text
PHASE 5 RESOLUTION (2026-08-05):
✅ IdentityProfileView created and fully tested
✅ Builder function build_identity_profile_view(seat_id, class_id) implemented
✅ All Phase 5 MANDATORY criteria satisfied
✅ Unblocks Phase 6 (Surface Inventory) and Phase 7 (Rewire) for route migration

PHASE 6-7 NEXT STEPS:
⏳ Pending: Rewire identity routes to consume view models
⏳ Pending: Migrate manual IdentityProfile queries to view model builders
⏳ Pending: Template consumption of IdentityProfileView

PHASE 8+ STATUS:
⏳ Pending: Route-level test execution (tests/dom/identity/test_admin_membership_gates.py)
⏳ Pending: Phase 9-10 verification after route rewiring
```
