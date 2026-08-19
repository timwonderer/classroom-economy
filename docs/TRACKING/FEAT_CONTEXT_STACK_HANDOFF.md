# FEAT-Context-Correction Stack — Handoff for PR 3+

| Field | Value |
|---|---|
| Purpose | Continuity brief for PR 3 onward in the FEAT-context-correction stacked-PR series |
| Last updated | 2026-08-18 |
| Current position | PR 2 open, awaiting review |

---

## 1. Mental Model (Read Every Session)

**We are slicing an already-completed, already-investigated target state onto the integration branch. We are not independently reimplementing each PR.**

- **`feat-context-correction`** is the completed target state at commit `dc5e0efb`. All 96 `@feat_shell` sites are already migrated, ITR rebuild is done, audits are done, all fixes are done. This branch is the **source of truth**.
- **`feat/paste-staging-grid`** is the integration branch. It's the base for every PR in the stack.
- Each PR in the stack extracts a **slice of `feat-context-correction`** and applies it to a branch off `feat/paste-staging-grid`. After all 9 PRs merge, `feat/paste-staging-grid`'s content equals `feat-context-correction`'s content.
- Final step: merge `feat/paste-staging-grid` → `CTH_v2.0`.

**Baseline:** `docs/TRACKING/PYTEST_BASELINE_dc5e0efb.md` is the target-state fingerprint. Grid converges toward it as PRs land. Do NOT supersede it. Do NOT interpret pre-slice grid failures as baseline defects.

---

## 2. Methodology Rules (Non-Negotiable)

1. **Extract, don't reimplement.** For every file in a PR's slice:
   ```bash
   git checkout feat-context-correction -- <path>
   ```
   Then prove exact equivalence:
   ```bash
   git diff feat-context-correction HEAD -- <path>   # must be empty
   ```
2. **Partial extraction requires hunk-level equivalence proof.** If a file contains unrelated work in the target that shouldn't ride along, extract only the intended hunks and verify those hunks match the target's version of those hunks.
3. **If the target slice cannot be cleanly extracted, STOP and REPORT the conflict.** Do not independently redesign or reimplement. This is what happened with `feat_class_002_modify_class_boundary.py` in PR 2 — the file was excluded and the reassignment identified as a separately-scheduled slice.
4. **PRs are expected to have unresolved failures.** A failure exists on grid because its correcting slice hasn't landed. That's expected. The only regression to investigate is a failure whose signature CHANGES vs the baseline — not one that's just still-red.
5. **No dead-added code.** If the target adds a function that has no callers yet, don't land it as part of a slice — wait for its callers to be scheduled together.
6. **Use the repo PR template** at `.github/PULL_REQUEST_TEMPLATE.md`. Not a custom body.

---

## 3. Stack Status

| PR | Scope | Status | Notes |
|---|---|---|---|
| PR 0 | ITR canonicalization (DOM v1.2 + SPEC-ITR-001 v1.0) | ✅ merged as `42f28b7e` | [#1337](https://github.com/timwonderer/classroom-token-hub/pull/1337) |
| PR 1 | Housekeeping (dangling refs, dead code) | ✅ merged as `1b455734` | [#1338](https://github.com/timwonderer/classroom-token-hub/pull/1338) |
| PR 2 | Class-config decorator swap (3 exact-match files) | 🟡 open at `4813c4fd` | [#1339](https://github.com/timwonderer/classroom-token-hub/pull/1339). Branch: `feat-context-pr2-feat-shell-migration` |
| PR 3 | **NEXT — awaiting placement decision** | Not started | See §4 |
| PR 8 | `FEAT-ANLY-001` → `FEAT-ITR-001` code rename | Deferred | Authorized by DOM v1.2 §XIII.b |
| Final | Delete `@feat_shell` decorator from `app/feats/base.py` | Deferred | Only safe after all 96 sites migrated |

### Also identified (unscheduled)

- **CLASS → IDENTITY reassignment slice.** Full dependency trace in §5. Awaiting user placement.
- **PR #1340 (baseline supersession)** — was created off-plan; closed and branch deleted. Do not re-create.

---

## 4. Remaining `@feat_shell` Sites on Grid

Count as of `1b455734`:

```
50 sites in app/routes/
32 sites in app/feats/     (13 in class_configuration; PR 2 clears 8 of those from feat_class_001/004/005)
 5 sites in app/utils/
 3 sites in app/services/
```

Domain distribution of the 32 `app/feats/` sites (for tranche planning):

| Tranche candidate | Files | Sites |
|---|---|---|
| obligations | `advance_bill_cycle_feat.py`, `assess_obligation_feat.py`, `satisfy_obligation_feat.py` | 4 |
| insurance | `insurance_claim_feat.py` (`policy_reference_feat.py` already migrated in `e7d4764b`) | 2 |
| ledger | `ledger_resolution_feat.py`, `transaction_void_feat.py`, `direct_entitlement_grant_feat.py`, `entitlement_lifecycle_feat.py` | 6 |
| prod | `prod.py`, `attendance.py` | ~5 |
| store | `store_feat.py`, `store_purchase_feat.py` | 2 |
| class-config remainder | `feat_class_002_modify_class_boundary.py` (deferred to reassignment slice) | 6 |
| other | `admin_feat.py`, `identity_feat.py`, `operations_feat.py`, `support_feat.py` | 0 (already free of `@feat_shell`) |

Route-layer sites (50) are much bigger volume. They'll be batched by domain to match the FEAT-layer tranches.

**Recommended PR 3 candidate:** obligations tranche. Rationale:
- Small (4 FEAT files + related route sites)
- Clean domain boundary
- Doesn't depend on the CLASS→IDENTITY reassignment
- OBLIGATIONS is DOM-OBL-001 territory; recently-consolidated invariants make it low-risk

Before starting PR 3, verify with the user which tranche to take.

---

## 5. CLASS → IDENTITY Reassignment Slice (Identified, Not Placed)

Complete diff on `feat-context-correction`:

| File | Change | Nature |
|---|---|---|
| `app/feats/class_configuration/feat_class_002_modify_class_boundary.py` | -489 / +24 | Deletes `execute_modify_student`, `execute_provision_student_seat`, `execute_remove_student_seat` (+ impls). Adds new `execute_delete_class_boundary`. |
| `app/feats/identity_feat.py` | +700 / -1 | Moves the three roster fns verbatim from feat_class_002. **Also adds 9 dead-added deletion/bulk fns** (no callers). |
| `app/feats/class_configuration/__init__.py` | ±small | Update imports. **Reference has a bug**: `__all__` lists 6 symbols not imported after the move. |
| `tests/test_feat_class_002_modify_class_boundary.py` | ±15 | Update test imports: `class_configuration.feat_class_002_modify_class_boundary` → `identity_feat`. |
| `app/routes/admin.py:5040` | (unchanged path) | Depends on the broken `__init__.py` re-export. Slice must fix. |

**No doctrine changes required.** No schema/migration changes. No prerequisite commits.

**Recommended sub-slicing:**

- **R-A: minimal move + fix.** Move the three roster fns; fix `__init__.py`; update test imports. Zero net functionality change. Should resolve the two `test_feat_class_002_modify_class_boundary.py` `Seat`-schema failures currently on grid.
- **R-B: dead-added deletion/bulk fns in identity_feat.py.** Depends on route callers. Wait.
- **R-C: `execute_delete_class_boundary`.** Depends on route caller. Wait.

R-A is a natural PR-3-adjacent slice. R-B and R-C should land only when their route callers do.

---

## 6. How to Start PR 3 (Or Any Subsequent PR)

```bash
# 1. Ensure grid tip is current
git fetch origin feat/paste-staging-grid

# 2. Branch off latest grid
git checkout -b feat-context-prN-<domain>-tranche origin/feat/paste-staging-grid

# 3. Extract the slice
git checkout feat-context-correction -- <files>

# 4. Prove equivalence per file
for f in <files>; do
  d=$(git diff feat-context-correction HEAD -- "$f")
  [ -z "$d" ] && echo "$f EXACT MATCH" || echo "$f DIFFERS — investigate"
done

# 5. If any file differs, STOP and REPORT. Do not modify.

# 6. If all match, commit and push
git add <files>
git commit -m "..."
git push -u origin feat-context-prN-<domain>-tranche

# 7. Open PR using repo template
gh pr create --base feat/paste-staging-grid --head <branch> \
  --title "PR N: <scope>" --body "$(cat template-with-fill)"

# 8. Test approach: targeted pytest on domain-related files, compare failure
#    signatures against docs/TRACKING/PYTEST_BASELINE_dc5e0efb.md
```

---

## 7. Common Mistakes to Avoid

1. **Hand-editing files instead of extracting from target.** Even if the diff happens to match, this violates methodology and skips the equivalence proof.
2. **Creating a "fresh baseline" PR to supersede `dc5e0efb`.** The reference baseline IS the target end state. Grid converging toward it is the point. See closed PR #1340 for what this mistake looks like.
3. **Interpreting pre-slice grid failures as regressions in the current PR.** A failure that exists because its correcting slice hasn't landed is expected, not a regression.
4. **Bundling unrelated work into a slice.** The reference sometimes has restructuring mixed with decorator swaps (e.g., `feat_class_002` bundles roster reassignment with the swap). Extract only the intended scope; defer the rest.
5. **Landing dead-added code.** If a slice would introduce a function with no callers, defer it.
6. **Using a custom PR body instead of the repo template.** Always use `.github/PULL_REQUEST_TEMPLATE.md`.
7. **Modifying `PYTEST_BASELINE_dc5e0efb.md`.** It is the target-state fingerprint. Never edit it, never supersede it, never mark it superseded.

---

## 8. Session-Resume Checklist

When resuming this stack in a new session:

- [ ] Read this handoff file end-to-end.
- [ ] Read the PR 2 body (#1339) for the current methodology example.
- [ ] Read the CLAUDE.md project rules (baseline behavior, testing, git conventions).
- [ ] Read memory files:
  - `feedback_base_branch.md` (branches merge to codex/v2.0)
  - `feedback_dev_db_destructive_ops.md` (DB is protected)
  - `feedback_v2_database_only.md` (classroom_economy DB)
- [ ] Fetch latest: `git fetch --all`
- [ ] Confirm PR 2 status: `gh pr view 1339`
- [ ] Check whether the CLASS→IDENTITY reassignment slice has been placed yet (see §5).
- [ ] Ask the user which tranche is next (default recommendation: obligations).
- [ ] Do NOT re-derive the plan. It's here. Ask the user for corrections if any invariant seems wrong.

---

## 9. Reference Links

- Reference branch: `feat-context-correction` at `dc5e0efb`
- Integration branch: `feat/paste-staging-grid`
- Final merge target: `CTH_v2.0`
- Target-state baseline: `docs/TRACKING/PYTEST_BASELINE_dc5e0efb.md`
- Grid tip after PR 1: `1b455734`
- PR 2 tip: `4813c4fd`
