# Domain Implementation Plan Template

**STATUS:** Ephemeral — use this template to create domain-specific implementation plans  
**Scope:** Derived from `DOMAIN_PROGRESS_MATRIX_2026.md`; destroyed after domain completion  
**Purpose:** Break down a domain's pending SOP-DEV-002 phases into concrete implementation steps

---

## Quick Start

1. **Find your domain in the progress matrix** → note current phase
2. **Copy this template** → rename to `DOMAIN_[NAME]_IMPLEMENTATION_2026-0X-XX.md`
3. **Fill in sections below** for your domain
4. **Create PRs aligned with phase assignments** → each PR advances one or two phases
5. **Delete this plan** after domain reaches Phase 10 (audit certified)

---

## Template: [DOMAIN_NAME] Implementation Plan

**Domain:** [DOM-???-*]  
**Current Phase:** [0-10]  
**Owner:** [Your name]  
**Created:** 2026-08-04  
**Scope:** Advance from current phase to Phase 10 certification

---

### Phase Assignments

Assign one or two phases per PR to keep work focused and reviewable.

| PR # | Phases | Assigned To | Status | Blockers |
|------|--------|-------------|--------|----------|
| — | 0-1 | — | — | — |
| — | 2-3 | — | — | — |
| — | 4-5 | — | — | — |
| — | 6-7 | — | — | — |
| — | 8-9 | — | — | — |
| — | 10 | — | — | — |

---

### Pending Phases Breakdown

#### Phase N: [Phase Name]
**Goal:** [What this phase achieves]  
**Current Status:** [Complete/In Progress/Not Started]  
**Checklist:**
- [ ] [Specific task 1]
- [ ] [Specific task 2]
- [ ] [Specific task 3]

**Example Commits:**
```
phase-N: [description of change 1]
phase-N: [description of change 2]
```

**Review Criteria:**
- [Criterion from SOP-DEV-002a]
- [Criterion from SOP-DEV-002a]

**Verification Steps:**
1. Run: `[command to verify]`
2. Check: [What to verify in code/tests]
3. Assert: [Expected outcome]

---

### SOP-DEV-002a Audit Checklist

Use this checklist when you're ready for Phase 10 certification audit.

**Pre-Audit:**
- [ ] All commits are on feature branch
- [ ] Branch is up-to-date with origin/codex/v2.0
- [ ] No uncommitted changes
- [ ] No merge conflicts

**Phase 0: Boundary**
- [ ] Domain spec exists (DOM-* or INV-* authority)
- [ ] Scope is generic (not tied to one entity type)
- [ ] Multi-tenancy model specified (class_id scoping)

**Phase 1: Truth**
- [ ] Canonical fact tables exist
- [ ] Facts are immutable (append-only)
- [ ] Foreign keys link to authoritative sources
- [ ] No duplication of amounts/values from other domains
- [ ] Multi-tenancy key (class_id) present on fact tables
- [ ] Timestamps on fact tables for audit lineage

**Phase 2: Persistence**
- [ ] Migration files exist for all new tables
- [ ] Migrations include idempotency helpers
- [ ] Migration upgrade/downgrade tested
- [ ] Foreign key constraints present and enforced
- [ ] No hardcoded constraint names

**Phase 3: Primitives**
- [ ] Core queries implemented in service layer
- [ ] All queries use SQLAlchemy ORM
- [ ] Queries scoped by class_id (multi-tenancy)
- [ ] Unit tests verify operations work
- [ ] Tests include multi-tenancy verification

**Phase 4: Mutation Boundary**
- [ ] All mutations wrapped in FEATContext
- [ ] Routes never call db.session.add/commit
- [ ] FEAT uses idempotency_key
- [ ] Mutations logged with correlation_id
- [ ] FEAT boundary enforced (tested)

**Phase 5: Read Models**
- [ ] View model dataclasses are frozen
- [ ] Constructors are generic (parameterized)
- [ ] Derived state computed at read time
- [ ] Queries scoped by class_id
- [ ] View models tested (happy path, edge cases, multi-tenancy)

**Phase 6: View Model Wiring**
- [ ] Routes construct canonical view models
- [ ] Every field owned by this domain exists in the view model
- [ ] Templates consume only those owned fields
- [ ] No domain-owned field bypasses the view model

**Phase 7: Surface Integration**
- [ ] Every consumer template uses the canonical field
- [ ] Legacy field sources removed
- [ ] Cross-domain dependencies documented
- [ ] Missing dependencies explicitly tracked

**Phase 8: Verify**
- [ ] View model tests pass (happy path, edge cases, multi-tenancy)
- [ ] Multi-tenancy test verifies no cross-class leakage
- [ ] No regression in existing tests
- [ ] Domain operations tested

**Phase 9: Legacy Deletion**
- [ ] Legacy aggregation variables removed
- [ ] Ad-hoc aggregation removed from routes
- [ ] All tests pass after deletion
- [ ] No dangling references

**Phase 10: Audit**
- [ ] Audit document exists
- [ ] Code compiles
- [ ] All tests pass
- [ ] No regressions
- [ ] Branch pushed
- [ ] Git status clean

---

## View Model Contribution Contract

This domain does not own templates. This domain owns the canonical fields that it contributes to shared view models.

A domain reaches Phase 6-7 when every field it owns:
- Is produced from canonical services (Phase 3)
- Is exposed through canonical view models (Phase 5)
- Is consumed by templates exclusively through those view models (Phase 6)
- Has all legacy field sources removed (Phase 7)

Templates are integration surfaces and are never owned by a single domain. A domain can legitimately reach Phase 7 even if consuming templates are incomplete — what matters is that YOUR fields are wired correctly.

---

### Domain Dependencies

**Architectural Dependencies:**

Depends on:
- [List domains whose services this domain queries]

Blocks:
- [List domains that depend on this domain's canonical fields]

**View Model Contributions:**

This domain owns the following fields in these view models:

| View Model | Field | Authority | Current Status |
|------------|-------|-----------|-----------------|
| [ViewModelName] | [field_name] | [This Domain] | 🔄 [Phase 0-7] |
| [ViewModelName] | [field_name] | [This Domain] | ✅ [Phase 7 complete] |

Example:
| StudentDashboardView | balance | Ledger | ✅ Phase 7 |
| StudentDashboardView | current_rent_due | Obligations | 🔄 Phase 6 (wired, not yet template-verified) |
| StudentDashboardView | next_payday | Payroll | ⏳ Phase 0 (not started) |

**Unresolved View Model Dependencies:**

(Track which fields from OTHER domains this domain depends on, and their completion status)

| View Model | Field | Authority | Status | Impact |
|------------|-------|-----------|--------|--------|
| [MyViewModelName] | [field] | [Other Domain] | 🔄 | [What breaks if missing] |

Example:
| StudentPayrollView | class_timezone | Class Config | ✅ | Payroll calculation accuracy |
| StudentPayrollView | current_period_number | Obligations | 🔄 | Payroll cycle alignment |

---

### View Model Field Ownership

This table is the authoritative tracking for Phase 6-7 completion. A domain reaches Phase 7 when ALL owned fields are ✅.

| View Model | Field | Service (Phase 3) | View Model (Phase 5) | Route Passes (Phase 6) | Template Uses (Phase 7) | Notes |
|------------|-------|-------------------|----------------------|------------------------|------------------------|-------|
| [ModelName] | [field] | ✅ | ✅ | ✅ | ✅ | Complete |
| [ModelName] | [field] | ✅ | ✅ | ✅ | 🔄 | Template work in progress |
| [ModelName] | [field] | ✅ | ✅ | ⏳ | ⏳ | Route wiring pending |

**What each column means:**
- **Service (Phase 3):** Canonical service method exists and returns data
- **View Model (Phase 5):** Field is defined in view model; constructor sets it from canonical service
- **Route Passes (Phase 6):** Route constructs view model and passes to template
- **Template Uses (Phase 7):** Template accesses field through view model, legacy sources removed

**Phase 7 Verification:** For each row, verify template code uses ONLY `{{ view_model.field }}`, not `{{ legacy_variable }}` or `{{ computed_inline }}`

---

**Known Blockers:**
- [List any known issues from matrix]

**Risk Areas:**
- [List potential issues or complex areas]

---

### Work in Progress Tracking

Update this section as you work through phases.

**2026-08-04:**
- Started Phase 0-1 boundary definition
- Created domain spec at DOM-???-*

**2026-08-XX:**
- [Update with progress]

---

### How to Create Focused PRs

**Phase 0-1 PR:** Boundary + Truth
```
Title: [DOMAIN] Phase 0-1: Canonical fact tables and domain scope

Changes:
- Add/update DOM-???-* spec in docs/DOMAIN/
- Create canonical fact table models (immutable)
- Add foreign keys to authoritative sources
- No migrations yet, just models and specs
```

**Phase 2-3 PR:** Persistence + Primitives
```
Title: [DOMAIN] Phase 2-3: Migration and service layer queries

Changes:
- Create migration for canonical tables (idempotent)
- Implement service layer queries in app/services/
- All queries use ORM, scoped by class_id
- Add unit tests for service queries
```

**Phase 4-5 PR:** Mutation Boundary + Read Models
```
Title: [DOMAIN] Phase 4-5: FEAT mutations and view models

Changes:
- Create FEAT-???-* mutations in app/feats/
- Create immutable view model dataclasses
- View models computed at read time (no persistence)
- Routes start calling view model constructors
```

**Phase 6-7 PR:** View Model Wiring + Surface Integration
```
Title: [DOMAIN] Phase 6-7: View model field ownership and template integration

Changes:
- Routes construct and pass canonical view models to templates
- Every field owned by this domain is in the view model (no bypasses)
- Templates consume ONLY those owned fields (legacy sources removed)
- Cross-domain field dependencies documented
- All owned fields verified in consumer templates
```

**Phase 8 PR:** Verify
```
Title: [DOMAIN] Phase 8: Comprehensive test coverage

Changes:
- Add view model tests (happy path, edge cases, multi-tenancy)
- Add integration tests with other domains
- Verify no cross-class data leakage
- Ensure all existing tests still pass
```

**Phase 9 PR:** Legacy Deletion
```
Title: [DOMAIN] Phase 9: Remove dead code

Changes:
- Delete legacy aggregation variables
- Delete ad-hoc helper functions
- Clean up imports
- Verify all tests pass
```

**Phase 10 PR:** Audit
```
Title: [DOMAIN] Phase 10: SOP-DEV-002a certification audit

Changes:
- Run SOP-DEV-002a audit against all phases
- Document any manual verification steps
- Update DOMAIN_PROGRESS_MATRIX_2026.md with new status
```

---

### Rollback Plan

**If a phase fails:**
1. Identify which PR introduced the failure
2. Run `git revert [PR-commit]`
3. Diagnose root cause
4. Fix and re-test locally
5. Create new PR with fix
6. Update this plan with lessons learned

---

### Resources

- **SOP-DEV-002a Audit:** `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002a_DOMAIN_RECONSTRUCTION_QA_AUDIT.md`
- **Progress Matrix:** `docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md`
- **Domain Spec:** `docs/DOMAIN/DOM-???-*.md`
- **Previous Domain Example:** See Obligations domain in matrix for similar work

---

## Using This Plan

### For Team Leads
- Assign phases to developers
- Track PR completion in the "Phase Assignments" table
- Monitor blockers
- Update progress matrix weekly

### For Developers
- Focus on one PR at a time (1-2 phases per PR)
- Follow the "Focused PR" templates for consistent structure
- Run verification steps before opening PR
- Update blockers if you hit issues

### For Reviewers
- Check PR against "Review Criteria" for the phase(s)
- Verify checklist items completed
- Ask for verification steps to be shown
- Don't approve phase 8 until tests pass

---

## Cleanup

**When domain reaches Phase 10:**
1. Move this file to `docs/archive/domain-plans/` with final status
2. Update `DOMAIN_PROGRESS_MATRIX_2026.md` with Phase 10 audit result
3. Celebrate! 🎉

---

**Created:** 2026-08-04  
**This plan will be deleted after domain completion.**
