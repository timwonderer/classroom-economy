# Domain Tracking & Implementation — New Structure

**Effective:** 2026-08-04  
**Replaces:** Scattered tracking docs (archived as historical reference)  
**Goal:** Single canonical matrix + ephemeral domain plans for clarity

---

## The New System

### 1. Canonical Tracking: `DOMAIN_PROGRESS_MATRIX_2026.md`

**What it is:** Single source of truth showing all 11 domains progressing through 10 SOP-DEV-002 phases.

**Use when:**
- You need to see overall project status
- You're checking dependencies ("Can I start Wave 9?")
- You want to review a domain's audit results
- You're looking for blocking issues

**At a glance:**
```
| Domain | Phase 0-4 | Phase 5-7 | Phase 8-9 | Phase 10 |
|--------|-----------|-----------|-----------|----------|
| Identity | ✅ | ✅ | ✅ | ✅ | COMPLETE
| Obligations | ✅ | ✅ | ⚠️ FAILED | ❌ | IN PROGRESS (test failures)
| Store | ✅ | ✅ | ⚠️ FAILED | ❌ | IN PROGRESS (massive failures)
```

**Update frequency:** After each domain completes a phase or audit

---

### 2. Ephemeral Plans: `DOMAIN_[NAME]_IMPLEMENTATION_202X-XX-XX.md`

**What it is:** Temporary, focused implementation roadmap for ONE domain. Created when starting a domain, destroyed when it reaches Phase 10.

**Use when:**
- You're actively working on a domain (phases 1-10)
- You need to break down phases into concrete tasks
- You're assigning work to team members
- You're tracking phase-by-phase progress

**Lifecycle:**
1. Create when domain enters active work (copy template)
2. Update weekly with PR assignments and status
3. Delete when domain reaches Phase 10 (move to archive)

**Structure:**
- Phase assignments (which PR covers phases 0-1, 2-3, etc.)
- Checklist for each pending phase
- SOP-DEV-002a audit checklist
- Focused PR templates for consistent structure
- Blocker tracking

---

### 3. Historical Reference: Old Tracking Docs

**Old files still exist in `docs/TRACKING/`:**
- `V2_Full_compliance_migration_plan.md` — Wave context and historical status
- `OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md` — Obligations audit results
- `SOP-DEV-002a_STORE_20260731_AUDIT.md` — Store audit results (if exists)

**Why kept:** Historical context; not replaced by matrix because they contain detailed audit analysis

**How to use:** Reference for deep-dive into why a domain failed a phase

---

## Your First Time: How to Start

### Scenario 1: You're fixing Obligations Phase 8 tests

1. **Check the matrix:** `DOMAIN_PROGRESS_MATRIX_2026.md` → find Obligations row
2. **See it's in Phase 8, FAILED with 4 test failures**
3. **Read blocking issues:** `app/feats/assess_obligation_feat.py` passes removed columns
4. **Fix the code** in your branch
5. **Re-run tests** to verify pass
6. **Update the matrix** after merge: change Phase 8 from ⚠️ to ✅

---

### Scenario 2: You're starting Store domain work

1. **Check the matrix:** Store is Phase 8, FAILED with 79 failures + 40 errors
2. **Decide to tackle:** "I'll fix Store Phase 8 tests"
3. **Create implementation plan:**
   ```bash
   cp DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md \
      DOMAIN_STORE_IMPLEMENTATION_2026-08-04.md
   ```
4. **Fill in:** Current phase = 8, owner = you, blockers = massive test failures
5. **Investigate:** Run tests locally, identify root causes
6. **Create PRs:** Each PR tackles a subset of failures
7. **Track in plan:** Update "Phase Assignments" table as you complete PRs
8. **After Phase 10 audit:** Delete the plan, move to archive

---

### Scenario 3: You're starting a new domain (not yet in matrix)

1. **Read the domain spec:** `docs/DOMAIN/DOM-???-*.md`
2. **Create implementation plan:**
   ```bash
   cp DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md \
      DOMAIN_YOURDOMAIN_IMPLEMENTATION_2026-08-04.md
   ```
3. **Set current phase to 0** (boundary definition)
4. **Work through phases** in order
5. **Create PRs** following phase assignments
6. **Update matrix** after Phase 0 boundary is defined

---

## Common Workflows

### Workflow A: Advance one domain by one phase

```
1. Read matrix → find domain's current phase
2. Create/update implementation plan
3. Read SOP-DEV-002a criteria for next phase
4. Create focused PR advancing that phase
5. After merge, update matrix
```

**Time investment:** 1-3 days depending on phase complexity

### Workflow B: Investigate why a domain failed audit

```
1. Read matrix → note "FAILED" status and blocking issues
2. Read linked audit doc (e.g., OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md)
3. Identify root cause of test failures
4. Create PR fixing root cause
5. Re-run SOP-DEV-002a audit
6. Update matrix with new audit results
```

**Time investment:** 2-5 days depending on failure complexity

### Workflow C: Track cross-domain dependencies

```
1. Read matrix → find your domain's wave assignment
2. Check "Wave Progression Timeline" table
3. Verify all predecessor waves are complete (✅)
4. Check for BLOCKED status (⚠️ or ❌)
5. If blocked, read blocking issues and help unblock
6. After blocker cleared, proceed with your work
```

**Time investment:** 1 hour per week for dependency checks

---

## File Organization

```
docs/
├── TRACKING/
│   ├── DOMAIN_PROGRESS_MATRIX_2026.md  ← CANONICAL (always up-to-date)
│   ├── README_DOMAIN_TRACKING.md       ← This file
│   ├── DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md  ← Template (copy to create plans)
│   ├── DOMAIN_OBLIGATIONS_IMPLEMENTATION_202X-XX-XX.md  ← Current plans (ephemeral)
│   ├── DOMAIN_STORE_IMPLEMENTATION_202X-XX-XX.md
│   ├── ... (other active domain plans)
│   │
│   ├── OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md  ← Reference only
│   └── (other historical audit docs)
│
└── archive/
    └── domain-plans/
        ├── DOMAIN_OBLIGATIONS_IMPLEMENTATION_2026-07-31.md  ← Archived after Phase 10
        ├── DOMAIN_PRODUCTIVITY_IMPLEMENTATION_2026-06-15.md
        └── (other completed domain plans)
```

---

## Key Differences from Old System

| Aspect | Old System | New System |
|--------|-----------|-----------|
| **Central tracker** | Multiple tracking docs scattered | One matrix: `DOMAIN_PROGRESS_MATRIX_2026.md` |
| **Domain plans** | None; work tracked inline in PR discussions | Ephemeral plans; deleted after completion |
| **Wave context** | Historical migration plan (large, hard to navigate) | Wave timeline in matrix (concise table) |
| **Audit results** | Linked in giant plan document | Linked from matrix in domain row |
| **Status visibility** | Required reading multiple docs | One look at matrix shows all status |
| **Dependency tracking** | Implicit in text | Explicit in "Dependency Chain" sections |
| **Updates** | Large document edits | Single row update in matrix |

---

## Maintenance

### Weekly (Team Lead)
- Check matrix for new audit failures
- Verify no domain is stalled > 1 week without progress
- Update implementation plan if phase assignments change
- Post status update to team

### After each PR merge
- Author updates matrix (or asks reviewer to)
- Matrix row changes from phase N to phase N+1
- Commit message includes: `tracking: update domain-progress-matrix for [DOMAIN]`

### After each SOP-DEV-002a audit
- Audit reviewer updates matrix with result (PASS/FAIL)
- If FAIL, add blocking issue details from audit doc
- Update implementation plan with next steps

### After Phase 10 completion
- Move implementation plan to `docs/archive/domain-plans/`
- Update matrix: Phase 10 = ✅
- Archive any domain-specific issue discussions

---

## Questions?

**Q: My domain isn't in the matrix yet. What do I do?**  
A: Add it! Read the domain spec, create an implementation plan, start with Phase 0-1 boundary definition.

**Q: The matrix has outdated info about my domain.**  
A: That's your signal to update it. File a PR with the new status.

**Q: I need to coordinate across 3 domains. How?**  
A: Use the matrix "Dependency Chain" sections to see what must complete first. Update implementation plans to sync milestones.

**Q: Can I skip a phase?**  
A: No. SOP-DEV-002a requires all 10 phases for production readiness. Each phase depends on the prior one.

**Q: My domain failed Phase 8. Where do I start?**  
A: Read the "Blocking Issues" in the matrix row, then check the linked audit doc for test failure details.

---

## Next Steps

1. **Read the matrix:** `DOMAIN_PROGRESS_MATRIX_2026.md`
2. **Pick a domain to unblock:** Either Obligations or Store (both in Phase 8)
3. **Create implementation plan:** Copy the template
4. **Break work into PRs:** Use the "Focused PR" templates
5. **Track progress:** Update matrix and plan weekly

---

**Created:** 2026-08-04  
**Maintained By:** Development Team  
**Questions/Updates:** Update the matrix, then create a PR for review
