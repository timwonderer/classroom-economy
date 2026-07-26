# QA Audit: Domain Reconstruction (SOP-DEV-002)

**Purpose:** Strict verification that a domain reconstruction follows all 10 SOP-DEV-002 phases and meets production readiness standards.

**Authority:** SOP-DEV-002, INV-CORE, INV-ARC-016, INV-ARC-021, DOM-CORE-002, multi-tenancy.md, testing.md, database-migrations.md

**Scope:** Any domain reconstruction project (obligations, entitlements, etc.)

---

## Criterion Classification

**MANDATORY:** Every mandatory criterion cites authority documentation. Failures on mandatory criteria block sign-off.

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

### Verification Steps

```bash
# 1. Check domain specification document exists
ls docs/DOMAIN/[DOMAIN]_*.md
# Should show at least one authority spec file (e.g., OBL_001_v2.5.md)

# 2. Verify scope boundaries are explicit
grep -r "obligation_type" app/services/obligation_view_model.py
# Should show generic parameter handling (not rent-specific)

# 3. Check if domain works for multiple types
grep -E "RENT|INSURANCE_PREMIUM|FINE|FEE" docs/DOMAIN/*.md
# Should list multiple obligation types in scope
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Domain specification document exists (DOM-* or INV-* authority) — *SOP-DEV-002 Phase 0*
- [ ] Scope is explicitly generic (not domain-specific like "rent") — *DOM-OBL-001 defines multi-obligation-type scope; DOM-CORE-002 requires generic domain definitions*
- [ ] Multi-tenancy model specified (class_id scoping) — *multi-tenancy.md: "CRITICAL: Every query involving student/seat data MUST be scoped by `class_id`"*

**GUIDANCE:**
- [ ] Examples show domain works for 2+ obligation types

---

## Phase 1: Truth

**Goal:** Canonical facts are defined and immutable.

### Verification Steps

```bash
# 1. Identify canonical entity/event tables
grep -E "class.*\(db.Model\)" app/models.py | grep -E "Assessment|Obligation|Event"

# 2. Check immutability (events table should not update)
grep -A 20 "class ObligationAssessment" app/models.py
# Should show created_at/updated_at with no user-facing update columns

# 3. Verify foreign keys establish relationships
grep "ForeignKey\|backref" app/models.py
# Should show assessment_events → seats, assessment_events → transactions

# 4. Check ledger truth (Transaction amounts)
grep -A 10 "class Transaction" app/models.py
# Should show amount, status fields with numeric type
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Canonical fact table exists (assessment_events or similar) — *SOP-DEV-002 Phase 1, INV-ARC-016: Lawful Existence and Audit Lineage*
- [ ] Facts are immutable (no update-by-user columns) — *INV-ARC-016, DOM-OBL-001 Section VIII: "no mutable status flag"*
- [ ] Foreign keys link facts to ledger (Transaction) — *INV-ARC-021: Cross-Domain Reference and Coordination*
- [ ] Ledger (Transaction) has authoritative amounts (not denormalized) — *DOM-OBL-001 Section VI: Obligations does not own Ledger transactions*
- [ ] Multi-tenancy key (class_id) present on all fact tables — *multi-tenancy.md: CRITICAL rule; CLAUDE.md rule 2*
- [ ] Timestamps (created_at, updated_at) on fact table — *INV-ARC-016*

---

## Phase 2: Persistence

**Goal:** Database schema matches models with proper indexing.

### Verification Steps

```bash
# 1. Check migrations exist for new tables
ls migrations/versions/*.py | grep -i "assessment\|obligation"

# 2. Verify schema migration is idempotent
grep -E "if.*exists|table_exists|column_exists" migrations/versions/*.py
# Should show existence checks for all CREATE operations

# 3. Test migrations up and down
flask db upgrade
flask db downgrade
flask db upgrade
# All should succeed without errors

# 4. Verify indexes on query columns
# Connect to test DB and run:
# \d assessment_events
# Should show indexes on (class_id, seat_id), (event_type), etc.
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Migration files exist for all new tables — *SOP-DEV-002 Phase 2, database-migrations.md: "NEVER modify `app/models.py` without creating a migration"*
- [ ] Migrations include idempotency helpers (table_exists, column_exists, etc.) — *database-migrations.md: "ALWAYS include idempotency helpers"; "NEVER edit old migrations after they're merged"*
- [ ] Migration upgrade/downgrade tested successfully — *database-migrations.md: "ALWAYS test migrations before committing (upgrade AND downgrade)"*
- [ ] Foreign key constraints present and enforced — *INV-ARC-016, database-migrations.md*
- [ ] No hardcoded constraint names (discovered dynamically) — *database-migrations.md: "NEVER use hardcoded constraint names"*

**GUIDANCE:**
- [ ] Indexes created on query columns (class_id, seat_id, event_type)

---

## Phase 3: Primitives

**Goal:** Core operations are implemented in service layer, not ad-hoc.

### Verification Steps

```bash
# 1. Find service layer functions
grep -n "^def get_\|^def create_\|^def satisfy_" app/services/obligations_service.py

# 2. Verify no ad-hoc SQL in routes
grep -r "db.session.execute.*f\".*SELECT\|db.session.query.*text" app/routes/
# Should return nothing (no raw SQL in routes)

# 3. Check all queries use ORM
grep -r "db.session.query\|db.get\|db.filter" app/services/obligations_service.py
# Should show ORM-based queries

# 4. Verify multi-tenancy at query level
grep -A 5 "def get_assessment" app/services/obligations_service.py
# Should show .filter(class_id=class_id) on every query

# 5. Test primitives with unit tests
pytest tests/test_obligation_view_models.py -v
# All tests should pass
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Core operations in service layer (not routes) — *SOP-DEV-002 Phase 3, CLAUDE.md: "Route → FEAT → Domain Services"*
- [ ] All queries use SQLAlchemy ORM (no raw SQL) — *CLAUDE.md rule 5: "ALWAYS use parameterized queries (SQLAlchemy ORM, never raw SQL)"*
- [ ] Every query includes class_id filter (multi-tenancy enforcement) — *multi-tenancy.md: "CRITICAL: Every query involving student/seat data MUST be scoped by `class_id`"*
- [ ] Unit tests cover each primitive operation — *SOP-DEV-002 Phase 3, testing.md: MINIMUM required coverage*
- [ ] Tests verify multi-tenancy scoping (cross-class data leak prevention) — *testing.md: "ALWAYS test multi-tenancy scoping for student-related features"*

**GUIDANCE:**
- [ ] Service functions have docstrings explaining contract

---

## Phase 4: Mutation Boundary

**Goal:** All state changes go through FEAT layer with atomic semantics.

### Verification Steps

```bash
# 1. Find all FEATContext usages
grep -r "FEATContext\|@feat_shell" app/feats/

# 2. Verify routes never call db.session.commit() directly
grep -r "db.session.commit\|db.session.add" app/routes/
# Should return nothing (no direct mutations in routes)

# 3. Check FEAT implements idempotency
grep -A 10 "class.*FEAT" app/feats/
# Should show idempotency_key handling

# 4. Verify audit logging
grep -r "audit_log\|correlation_id" app/feats/
# Should show mutation events are logged

# 5. Test FEAT atomicity
# Run test that creates obligation and payment in same FEAT
pytest tests/test_obligation_view_models.py::test_build_student_obligation_view_with_payment -v
# Should succeed with single FEATContext
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] All mutations wrapped in FEATContext (FEAT-* layer) — *SOP-DEV-002 Phase 4, CLAUDE.md rule 3: "Mutate through FEATs. No direct `db.session.add/commit` in routes"*
- [ ] No direct db.session.add/commit in routes — *CLAUDE.md rule 3, SOP-DEV-002 Phase 4*
- [ ] FEAT implementations use idempotency_key (for exactly-once semantics) — *DOM-OBL-001 Section X rule 4: "Assessment creation must remain idempotent"*
- [ ] Audit events logged (correlation_id tracking) — *INV-ARC-016: Lawful Existence and Audit Lineage*
- [ ] FEAT boundary is enforced (tested by attempting direct mutation) — *SOP-DEV-002 Phase 4*

**GUIDANCE:**
- [ ] Transaction rollback tested on FEAT failure

---

## Phase 5: Read Models

**Goal:** View models are generic, immutable, and scoped.

### Verification Steps

```bash
# 1. Check view model dataclasses
grep -B 2 "class.*ObligationView\|class.*ObligationSummary" app/services/obligation_view_model.py
# Should show @dataclass(frozen=True)

# 2. Verify constructor functions
grep "^def build_.*obligation" app/services/obligation_view_model.py
# Should show functions that take obligation_type parameter

# 3. Check immutability enforcement
python3 -c "
from app.services.obligation_view_model import StudentObligationView
view = StudentObligationView(...)
view.current_period = {}  # Should fail with FrozenInstanceError
" 2>&1 | grep -i "frozen\|immutable"
# Should show FrozenInstanceError

# 4. Verify class_id scoping in builders
grep -A 20 "def build_student_obligation_view" app/services/obligation_view_model.py
# Should show filter(class_id=class_id) early in function

# 5. Test view models work for multiple obligation types
pytest tests/test_obligation_view_models.py -v -k "RENT"
# Then verify same test pattern works for other types (in future)
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] View model dataclasses are frozen (immutable) — *SOP-DEV-002 Phase 5, MAP-UI-002 Section IX: Page view models must hide persistence shape from templates*
- [ ] Constructor functions are generic (take obligation_type parameter, not rent-specific) — *DOM-OBL-001 Section X (Canonical View Models): Generic over obligation_type*
- [ ] Status breakdown is computed (not just raw query results) — *DOM-OBL-001 Section VIII: "The following SHALL be derived and SHALL NOT be persisted"*
- [ ] All queries in view model constructors scoped by class_id — *multi-tenancy.md: CRITICAL rule*
- [ ] View models tested with unit tests (minimum 5) — *SOP-DEV-002 Phase 8, testing.md: MINIMUM required coverage*

**GUIDANCE:**
- [ ] View models include all necessary fields for display
- [ ] Student rows include seat_id, student_name, status, balance, days_overdue

---

## Phase 6: Surface Inventory

**Goal:** Routes and templates use view models, not legacy variables.

### Verification Steps

```bash
# 1. Find routes using view models
grep -r "build_.*obligation_view\|obligation_summary" app/routes/

# 2. Check render_template calls for legacy variables
grep -A 30 "render_template.*rent" app/routes/admin.py
# Should NOT include: rent_status_counts, unpaid_rent_log, payment_log, student_past_due_json

# 3. Verify templates receive view model
grep "obligation_summary\|StudentObligationView" templates/*.html
# Should show templates accessing view model fields

# 4. Check template uses view model.student_rows
grep "obligation_summary.student_rows\|view.payment_history" templates/*.html
# Should show direct consumption of view model properties

# 5. Verify no ad-hoc data in template context
grep "{% for.*in.*log\|{% for.*in.*counts" templates/*.html
# Should NOT show iteration over legacy collections
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Routes call view model constructors (build_*_obligation_view) — *SOP-DEV-002 Phase 6, MAP-UI-002 Section V*
- [ ] Routes pass view_model object to template — *MAP-UI-002: Template contract specifies routes pass shared context + exactly one page view model*
- [ ] No legacy aggregation variables in render_template context — *SOP-DEV-002 Phase 7: "Ad-hoc code replaced with canonical builders"*
- [ ] Templates access view_model fields directly (not persistence objects) — *MAP-UI-002 Section X: Preferred pattern uses view models*

**GUIDANCE:**
- [ ] Templates do NOT reference legacy variables (rent_status_counts, payment_log, unpaid_rent_log, etc.)
- [ ] Template logic is simple (no complex aggregation)

---

## Phase 7: Rewire

**Goal:** Ad-hoc code replaced with canonical builders.

### Verification Steps

```bash
# 1. Measure route complexity before/after
# Check git history for previous version:
git show HEAD~5:app/routes/admin.py | wc -l  # Before
git show HEAD:app/routes/admin.py | wc -l     # After
# Should show significant reduction (30%+ fewer lines)

# 2. Check for manual student queries
grep -n "Seat.query.*filter" app/routes/admin.py
# Should show minimal direct queries (only to fetch seat objects for form rendering)

# 3. Verify status computation moved to view model
grep -n "rent_status_counts\|months_behind\|past_due" app/routes/admin.py
# Should NOT appear (logic moved to view model)

# 4. Check for legacy helper usage
grep -n "_build_rent_coverage_context\|_is_student_coverage_period_paid" app/routes/admin.py
# Should NOT appear (only used in Phase 9 deletion audit)

# 5. Verify routes are thin request handlers
# Read route handler and count logical lines
# Should be <100 lines for GET handlers after view model integration
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Manual student/class queries moved to view model builders — *SOP-DEV-002 Phase 7*
- [ ] Status computation logic moved to view model — *SOP-DEV-002 Phase 7, MAP-UI-002: business logic is view model responsibility*
- [ ] No legacy helpers imported/used in routes — *SOP-DEV-002 Phase 7/9: Legacy deletion*
- [ ] Route delegates business logic to view model — *MAP-UI-002: routes are thin request handlers*
- [ ] GET handlers are pure (no side effects) — *CLAUDE.md rule 9: "No GET side effects"; INV-ARC-007*

**GUIDANCE:**
- [ ] Route complexity reduced 30%+ (measured by line count)

---

## Phase 8: Verify

**Goal:** Tests prove canonical model is correct and multi-tenant safe.

### Verification Steps

```bash
# 1. Run all obligation tests
pytest tests/test_obligation_view_models.py -v
# All tests should pass

# 2. Check test coverage
pytest tests/test_obligation_view_models.py --cov=app/services/obligation_view_model
# Should show 80%+ coverage

# 3. Verify multi-tenancy tests exist
grep -n "test.*multi_tenancy\|test.*cross.*class\|test.*scop" tests/test_obligation_view_models.py
# Should show at least one test verifying class isolation

# 4. Run multi-tenancy test specifically
pytest tests/test_obligation_view_models.py::test_view_model_respects_multi_tenancy -v
# Should pass and confirm data doesn't leak across classes

# 5. Check for edge case tests
grep -n "test.*no_assessments\|test.*no_students\|test.*empty" tests/test_obligation_view_models.py
# Should show tests for empty/null cases

# 6. Verify integration tests
pytest tests/test_obligation_view_rendering.py -v -k "multi_tenancy"
# Should pass, proving template rendering works
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Minimum 5 unit tests for view model (exist and pass) — *SOP-DEV-002 Phase 8, testing.md: MINIMUM required*
- [ ] Multi-tenancy test exists and passes (proves class_id scoping) — *testing.md: "ALWAYS test multi-tenancy scoping"; multi-tenancy.md: CRITICAL rule*
- [ ] Status breakdown computation tested — *DOM-OBL-001 Section VIII requires derivation validation*
- [ ] No regression in existing tests — *testing.md: Critical requirement*

**GUIDANCE:**
- [ ] Test coverage 80%+ for view model service
- [ ] Edge cases tested (no assessments, no students, empty data)
- [ ] Payment history aggregation tested (domain-specific)
- [ ] Integration tests with canonical test identity pass

---

## Phase 9: Legacy Deletion

**Goal:** Dead code is removed; only canonical code remains.

### Verification Steps

```bash
# 1. Check what was deleted
git diff HEAD~2 HEAD --stat | grep "app/routes/"
# Should show net reduction in lines (insertions < deletions for legacy cleanup)

# 2. Verify unused helpers are gone
grep -r "_build_rent_coverage_context\|_is_student_coverage_period_paid" app/routes/
# Should return nothing (completely removed)

# 3. Check legacy variables are gone from routes
grep -n "unpaid_rent_log\|payment_log\|student_past_due_json\|rent_status_counts" app/routes/admin.py
# Should NOT appear

# 4. Verify no dangling imports
python3 -m py_compile app/routes/admin.py
# Should compile without errors (all imports used)

# 5. Check for orphaned helper functions
grep -n "^def.*rent" app/routes/student.py | wc -l
# Count should be stable or decreased (no new legacy helpers added)

# 6. Verify dead code removal didn't break tests
pytest tests/test_obligation_view_models.py -v
# All tests should still pass
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] All legacy variables removed from render_template context — *SOP-DEV-002 Phase 9*
- [ ] No ad-hoc aggregation loops remain in routes — *SOP-DEV-002 Phase 7/9*
- [ ] All tests pass after deletion — *testing.md: verify no regressions*
- [ ] No dangling references to deleted code — *code quality, CLAUDE.md rule 1*

**GUIDANCE:**
- [ ] No unused imports
- [ ] No orphaned functions
- [ ] Code compiles without warnings

---

## Phase 9.2: Cleanup (Guidance, not Mandatory)

**Goal:** Code is polished; no dead imports or duplicate logic. This phase provides quality recommendations; failures do not block sign-off.

### Verification Steps

```bash
# 1. Check for unused imports
grep "^from.*import\|^import" app/routes/admin.py | sort | uniq -c
# Each import should be used 2+ times in file

# 2. Verify no duplicate code blocks
# Manually review route for patterns like:
#   - Same calculation appearing twice
#   - Same import appearing twice in different blocks
#   - Same query logic in multiple places

# 3. Check for consolidated logic
# Should see related functionality grouped together, not scattered

# 4. Verify helpers consolidation
grep -A 3 "from app.routes.student import" app/routes/admin.py
# Should show minimal imports (only used helpers)
```

### Guidance Criteria (Non-Blocking)
- [ ] No unused imports
- [ ] No duplicate code blocks
- [ ] Related logic consolidated
- [ ] Import consolidation (unnecessary redundancy removed)
- [ ] Code reads linearly (no scattered logic)

---

## Phase 10: Audit

**Goal:** All prior phases verified; domain is production-ready.

### Verification Steps

```bash
# 1. Check audit document exists
ls .claude/projects/*/memory/*certification*.md
# Should show audit document with all 10 phases checked

# 2. Verify all commits are documented
git log --oneline | head -10
# Should show phase-labeled commits

# 3. Check branch is clean
git status
# Should show "nothing to commit, working tree clean"

# 4. Verify branch is pushed
git branch -vv
# Should show "pushes to origin/[branch]" (no unpushed commits)

# 5. Compile and test one final time
python3 -m py_compile app/routes/admin.py app/routes/student.py
pytest tests/test_obligation_view_models.py -v
# All should succeed
```

### Sign-Off Criteria

**MANDATORY:**
- [ ] Audit document (certification) exists and is complete — *SOP-DEV-002 Phase 10*
- [ ] Code compiles without errors — *general code quality*
- [ ] All tests pass — *testing.md: MINIMUM requirement*
- [ ] No regressions in existing test suite — *testing.md: MINIMUM requirement*
- [ ] Branch is pushed to remote — *CLAUDE.md: "active branch: codex/v2.0"*
- [ ] Git status is clean (nothing to commit) — *git best practice*

**GUIDANCE:**
- [ ] All commits documented with phase labels
- [ ] Memory/documentation files updated

---

## Final Sign-Off Checklist

### Testing (MANDATORY)
- [ ] All new tests pass — *testing.md*
- [ ] No regression in existing tests — *testing.md: Critical requirement*
- [ ] Multi-tenancy scoping tested — *testing.md, multi-tenancy.md: CRITICAL rule*

### Production Readiness (MANDATORY)
- [ ] Error handling is proper (no bare except) — *testing.md, code quality*
- [ ] FEAT mutations are idempotent — *database-migrations.md, DOM-OBL-001*
- [ ] Multi-tenancy is enforced throughout — *multi-tenancy.md: CRITICAL rule; CLAUDE.md rule 2*
- [ ] No direct db.session mutations in routes — *CLAUDE.md rule 3*

### Documentation (MANDATORY)
- [ ] Domain spec document exists (DOM-* or INV-*) — *SOP-DEV-002*
- [ ] Certification audit document exists — *SOP-DEV-002 Phase 10*

### Git (MANDATORY)
- [ ] All commits are on feature branch — *CLAUDE.md: active branch is codex/v2.0*
- [ ] Branch is up-to-date with origin/codex/v2.0 — *CLAUDE.md: active branch*
- [ ] No merge conflicts — *git best practice*
- [ ] Branch is pushed to remote — *deployment practice*

### Code Quality (GUIDANCE)
- [ ] All code follows Python style guide (PEP 8)
- [ ] No type errors (run with mypy if available)
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
1. **Code Reviewer:** Verifies phases 5-7 (view models, routes, templates) — particularly MANDATORY criteria around view model construction, route delegation, and template contracts
2. **QA Lead:** Verifies phase 8 (tests and coverage) — particularly MANDATORY multi-tenancy test and regression verification
3. **Architecture Lead:** Verifies phases 0-4 (boundary, truth, persistence, primitives, mutation boundary) — particularly MANDATORY criteria around immutability, multi-tenancy scoping, and FEAT boundary
4. **Tech Lead:** Final approval of MANDATORY criteria compliance and production readiness sign-off

---

**Last Updated:** 2026-07-25 (v1.1 — Added MANDATORY/GUIDANCE classification with authority citations)
**Authority:** SOP-DEV-002, INV-CORE, INV-ARC-016, INV-ARC-021, DOM-CORE-002, multi-tenancy.md, testing.md, database-migrations.md, documentation.md
**Applicable To:** Any domain reconstruction following SOP-DEV-002 pattern
