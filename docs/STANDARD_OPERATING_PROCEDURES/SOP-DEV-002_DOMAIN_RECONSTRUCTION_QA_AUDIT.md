# SOP-DEV-002: Domain Reconstruction QA Audit

**Purpose:** Verification that a domain reconstruction follows all 10 SOP-DEV-002 phases and meets production readiness standards.

**Authority:** SOP-DEV-002, INV-CORE-000, INV-ARC-007, INV-ARC-016, INV-ARC-021, DOM-CORE-002

**Scope:** Any domain reconstruction project following SOP-DEV-002 pattern.

**Reference Example:** DOM-OBL-001 (Obligations Domain) illustrates how to apply these criteria to a concrete domain.

---

## Criterion Classification

**MANDATORY:** Every mandatory criterion traces to constitutional authority (INV-*, DOM-CORE-*, FEAT-*). Failures on mandatory criteria block sign-off.

**GUIDANCE:** Recommendations without explicit authority backing. Failures on guidance criteria are noted but do not block sign-off.

---

## Pre-Audit Checklist

### Repository State
- [ ] All commits are on the feature branch (never on main)
- [ ] Branch is up-to-date with origin/codex/v2.0
- [ ] No uncommitted changes (`git status` is clean)
- [ ] No merge conflicts

### Documentation
- [ ] Memory file exists documenting the work
- [ ] Certification audit document exists
- [ ] Phase completion notes are clear and dated

---

## Phase 0: Boundary

**Goal:** Domain scope is clearly defined and authorized.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Domain specification document exists (DOM-* or INV-* authority) — *SOP-DEV-002 Phase 0*
- [ ] Scope is explicitly generic (not tied to one obligation type, entity type, or feature) — *DOM-CORE-002: Domains must define scopes that generalize across variations*
- [ ] Multi-tenancy model specified (class_id scoping for educational domains) — *INV-CORE-000: Multi-tenant isolation is foundational*

**GUIDANCE:**
- [ ] Domain examples show scope applies to multiple entity types or obligation types

---

## Phase 1: Truth

**Goal:** Canonical facts are defined and immutable.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Canonical fact table(s) exist for domain entities — *SOP-DEV-002 Phase 1, INV-ARC-016: Lawful Existence and Audit Lineage*
- [ ] Facts are immutable (no user-facing update columns; new facts append, don't mutate) — *INV-ARC-016, DOM-CORE-002: Facts are append-only*
- [ ] Foreign keys link domain facts to authoritative sources in other domains — *INV-ARC-021: Cross-Domain Reference and Coordination*
- [ ] Domain does not duplicate authoritative amounts/values from other domains (e.g., doesn't store Ledger amounts) — *INV-ARC-021*
- [ ] Multi-tenancy key (class_id or equivalent) present on all fact tables — *INV-CORE-000: Multi-tenant data isolation*
- [ ] Timestamps (created_at or equivalent) on fact tables for audit lineage — *INV-ARC-016*

**Reference:** DOM-OBL-001 Section V-VI defines assessment_events, bill_cycles, and event_type (ASSESSMENT, PAYMENT, WAIVED) as immutable facts.

---

## Phase 2: Persistence

**Goal:** Database schema matches models; migrations are idempotent; indexes support queries.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Migration files exist for all new tables — *SOP-DEV-002 Phase 2*
- [ ] Migrations include idempotency helpers (table_exists, column_exists, etc.) — *Standard practice for safe re-runnable migrations*
- [ ] Migration upgrade/downgrade tested successfully — *SOP-DEV-002 Phase 2*
- [ ] Foreign key constraints present and enforced at database level — *INV-ARC-021*
- [ ] No hardcoded constraint names; constraints discovered dynamically via schema inspection — *Standard practice to avoid naming collisions*

**GUIDANCE:**
- [ ] Indexes created on query columns (foreign keys, tenant keys, filter columns)

**Reference:** DOM-OBL-001 Section VI specifies table structure for assessment_events and bill_cycles with foreign keys to seats, classes, and transactions.

---

## Phase 3: Primitives

**Goal:** Core domain queries centralized in service layer; all queries use ORM; multi-tenancy scoped.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Core domain queries implemented in service layer functions — *SOP-DEV-002 Phase 3*
- [ ] All queries use SQLAlchemy ORM (no raw SQL in service layer) — *INV-CORE-000: Canonical architecture*
- [ ] Every query that involves domain entities scoped by class_id (multi-tenancy enforcement) — *INV-CORE-000: Multi-tenant data isolation*
- [ ] Unit tests verify each primitive operation works correctly — *SOP-DEV-002 Phase 3*
- [ ] Tests include multi-tenancy verification (no cross-class data leakage) — *INV-CORE-000*

**GUIDANCE:**
- [ ] Service functions have docstrings explaining contracts

**Reference:** DOM-OBL-001 Section IX defines canonical business operations: `create_obligation()`, `satisfy_obligation()`, `advance_bill_cycle()`.

---

## Phase 4: Mutation Boundary

**Goal:** All state changes go through FEAT layer; mutations are atomic and logged.

### Sign-Off Criteria

**MANDATORY:**
- [ ] All domain state mutations wrapped in FEATContext (FEAT-* layer) — *SOP-DEV-002 Phase 4, INV-ARC-009: Domain Authority for State*
- [ ] Routes never directly call db.session.add/commit — *INV-ARC-009*
- [ ] FEAT implementations use idempotency_key for exactly-once semantics — *DOM-CORE-002: Idempotency required*
- [ ] Mutation events logged with correlation_id for audit trail — *INV-ARC-016: Lawful Existence and Audit Lineage*
- [ ] FEAT boundary enforced (test verifies direct mutation blocked) — *SOP-DEV-002 Phase 4*

**GUIDANCE:**
- [ ] Transaction rollback tested on FEAT failure

---

## Phase 5: Read Models

**Goal:** View models are immutable, generic, and scoped; they hide persistence shape from consumers.

### Sign-Off Criteria

**MANDATORY:**
- [ ] View model dataclasses are frozen (immutable) — *SOP-DEV-002 Phase 5*
- [ ] Constructor functions are generic (parameterized, not hardcoded to one entity type) — *DOM-CORE-002*
- [ ] Derived state is computed at read time (status, balances, counts) — *DOM-CORE-002: Derived state SHALL NOT be persisted*
- [ ] All queries in view model constructors scoped by class_id — *INV-CORE-000*
- [ ] View models tested with unit tests covering happy path, edge cases, multi-tenancy — *SOP-DEV-002 Phase 8: "Tests prove canonical model is correct and multi-tenant safe"*

**GUIDANCE:**
- [ ] View models include all fields necessary for display
- [ ] Documentation explains what each view model answers

**Reference:** DOM-OBL-001 Section X defines StudentObligationView and ClassObligationSummary as canonical view models with computed current_period, status_breakdown, and payment_history.

---

## Phase 6: Surface Inventory

**Goal:** Routes and templates consume view models; no legacy variables passed to templates.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Routes call view model constructors — *SOP-DEV-002 Phase 6*
- [ ] Routes pass view_model object to template — *SOP-DEV-002 Phase 6*
- [ ] No legacy aggregation variables in render_template context — *SOP-DEV-002 Phase 6*
- [ ] Templates access view_model fields directly (not persistence objects) — *SOP-DEV-002 Phase 6*

---

## Phase 7: Rewire

**Goal:** Ad-hoc aggregation logic replaced with canonical builders; routes become thin request handlers.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Manual entity queries moved to view model builders — *SOP-DEV-002 Phase 7*
- [ ] Status/aggregation computation moved from routes to view models — *SOP-DEV-002 Phase 7*
- [ ] No legacy helper functions imported in routes — *SOP-DEV-002 Phase 7/9*
- [ ] Route logic delegates to view model; routes are thin handlers — *SOP-DEV-002 Phase 7*
- [ ] GET handlers are pure (no db.session.commit or side effects) — *INV-ARC-007*

**GUIDANCE:**
- [ ] Route complexity reduced compared to legacy implementation

---

## Phase 8: Verify

**Goal:** Tests prove canonical model is correct and multi-tenant safe.

### Sign-Off Criteria

**MANDATORY:**
- [ ] View model tests exist and pass covering: happy path, edge cases, multi-tenancy — *SOP-DEV-002 Phase 8*
- [ ] Multi-tenancy test verifies no cross-class data leakage — *INV-CORE-000*
- [ ] No regression in existing tests — *SOP-DEV-002 Phase 8*
- [ ] Domain-specific operations tested (e.g., status derivation, payment application) — *SOP-DEV-002 Phase 8*

**GUIDANCE:**
- [ ] Test coverage 80%+ for view model service
- [ ] Edge cases explicitly tested (no data, empty entities, etc.)

---

## Phase 9: Legacy Deletion

**Goal:** Dead code removed; only canonical code remains.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Legacy aggregation variables removed from render_template context — *SOP-DEV-002 Phase 9*
- [ ] Ad-hoc aggregation loops and helper functions removed from routes — *SOP-DEV-002 Phase 9*
- [ ] All tests pass after deletion — *SOP-DEV-002 Phase 9*
- [ ] No dangling references to deleted code — *SOP-DEV-002 Phase 9*

**GUIDANCE:**
- [ ] Unused imports removed
- [ ] Orphaned functions removed
- [ ] Code compiles without warnings

---

## Phase 9.2: Cleanup (Guidance, Non-Blocking)

**Goal:** Code is polished; no dead imports or duplicate logic.

**Guidance Criteria:**
- [ ] No unused imports
- [ ] No duplicate code blocks
- [ ] Related logic consolidated
- [ ] Code reads linearly

---

## Phase 10: Audit

**Goal:** All prior phases verified; domain is production-ready.

### Sign-Off Criteria

**MANDATORY:**
- [ ] Audit document (certification) exists and is complete — *SOP-DEV-002 Phase 10*
- [ ] Code compiles without errors — *SOP-DEV-002 Phase 10*
- [ ] All tests pass — *SOP-DEV-002 Phase 10*
- [ ] No regressions in existing test suite — *SOP-DEV-002 Phase 10*
- [ ] Branch is pushed to remote — *SOP-DEV-002 Phase 10*
- [ ] Git status is clean — *SOP-DEV-002 Phase 10*

**GUIDANCE:**
- [ ] All commits documented with phase labels
- [ ] Memory/documentation files updated

---

## Final Sign-Off Checklist

### Testing (MANDATORY)
- [ ] All new tests pass
- [ ] No regression in existing tests
- [ ] Multi-tenancy scoping tested

### Production Readiness (MANDATORY)
- [ ] Error handling is proper (no bare except)
- [ ] FEAT mutations are idempotent — *DOM-CORE-002*
- [ ] Multi-tenancy enforced throughout — *INV-CORE-000*
- [ ] No direct db.session mutations in routes — *INV-ARC-009*

### Documentation (MANDATORY)
- [ ] Domain spec document exists (DOM-* or INV-*) — *SOP-DEV-002*
- [ ] Certification audit document exists — *SOP-DEV-002*

### Git (MANDATORY)
- [ ] All commits are on feature branch — *SOP-DEV-002*
- [ ] Branch is up-to-date with origin/codex/v2.0 — *SOP-DEV-002*
- [ ] No merge conflicts
- [ ] Branch is pushed to remote

### Code Quality (GUIDANCE)
- [ ] All code follows Python style guide (PEP 8)
- [ ] No type errors (mypy if available)
- [ ] No obvious bugs or TODOs left in code
- [ ] Comments are clear and non-obvious logic is explained

### Testing (GUIDANCE)
- [ ] Coverage is 80%+ for new code
- [ ] Edge cases covered

### Documentation (GUIDANCE)
- [ ] Memory file documents the work
- [ ] Code comments explain non-obvious logic
- [ ] Phase completion documented

### Production Readiness (GUIDANCE)
- [ ] No dead code remaining
- [ ] No unused imports
- [ ] No temporary debugging code

### Git (GUIDANCE)
- [ ] Commit messages are clear and phase-labeled
- [ ] Docstrings present on public functions

---

## Sign-Off Statement

**QA Reviewer:** ___________________________

**Date:** ___________________________

**Status:** ☐ APPROVED (all MANDATORY criteria met) ☐ APPROVED WITH GUIDANCE GAPS (guidance items pending) ☐ REJECTED (MANDATORY criteria failures)

**Mandatory Criteria Status:** All MANDATORY criteria must be met for approval. Failures on MANDATORY criteria block sign-off.

**Guidance Criteria Status:** GUIDANCE criteria are recommendations for code quality. Gaps in guidance do not block sign-off but should be tracked for follow-up work.

**Comments:**

```
[Reviewer notes here, including any guidance gaps noted for follow-up]
```

---

## Approval Authority

This audit must be signed off by:
1. **Code Reviewer:** Verifies phases 5-7 (view models, routes, templates)
2. **QA Lead:** Verifies phase 8 (tests and coverage)
3. **Architecture Lead:** Verifies phases 0-4 (boundary, truth, persistence, primitives, mutation boundary)
4. **Tech Lead:** Final approval of MANDATORY criteria compliance and production readiness sign-off

---

**Last Updated:** 2026-07-25 (v1.2 — Domain-agnostic rewrite, canonical authority only)
**Authority:** SOP-DEV-002, INV-CORE-000, INV-ARC-007, INV-ARC-016, INV-ARC-021, DOM-CORE-002
**Applicable To:** Any domain reconstruction following SOP-DEV-002 pattern
