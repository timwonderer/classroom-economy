# Obligation Domain & Policies Doctrine Follow-Up — 2026-08-16

**Session branch:** `fix/obligation-template-broken-urls` (merged into `feat/paste-staging-grid` at commit `31be25a3`)
**Trigger:** Emergency template crash on `/admin/rent-settings` → traced to Obligation Phase 10 certification gap → cascaded into Policies-domain doctrine clarification.
**Related docs updated in this session:**

- `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `docs/DOMAIN/DOM-POL-001_POLICIES_DOMAIN.md`
- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md` (user-authored, commit `00d00c8d`)
- `docs/DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md` (user-authored, commit `00d00c8d`)
- `docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md` (user-authored, commit `00d00c8d`)

---

## I. What was found

### 1. Obligation Phase 10 certification gap

**Symptom:** every teacher-facing template that touched the Obligation domain crashed on load with `werkzeug.routing.exceptions.BuildError` referencing `admin.reverse_cycle_penalties` and `admin.remove_rent_waiver`.

**Root cause:** two admin routes were intentionally deleted for FEAT-OBL-003 immutability compliance:

- `reverse_cycle_penalties` removed in commit `6c9c3857` (2026-07-18)
- `remove_rent_waiver` removed in commit `eeef3de7` (2026-07-25)

The corresponding UI in [`templates/admin_rent_settings.html`](../../templates/admin_rent_settings.html) was left in place. The Phase 10 audit (2026-07-26, `OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md`) certified the domain as production-ready **without performing a cross-layer reference check** — i.e., the audit verified backend contracts but did not verify that surviving templates still resolve to living endpoints.

**Fix (this branch):** template UI removed — Corrections tab and Active Waivers Action column both deleted. Emergency fix commit `053c20f4`.

**Verification (this branch):** Playwright headless browser traversal of every obligation-owned teacher-facing route under canonical test context. All routes render 200; no `BuildError` / `jinja2.exceptions` / console errors. Additional broken `url_for` targets: zero beyond the two already patched.

### 2. Constitutional-integrity gap in `rent_settings` (Scope B — not remediated in this branch)

Investigation into the tableplus observation of 7 `rent_settings` rows with `NULL` versioning columns exposed a deeper doctrine violation:

- `rent_settings` is designed as a **mutable singleton** per class (`class_id` unique, `updated_at` `onupdate=utc_now`).
- All mutation sites edit an existing row in place rather than inserting a new versioned row:
  - [`app/routes/admin.py:5817-5859`](../../app/routes/admin.py) — teacher save from admin UI
  - [`app/scheduled_tasks.py:302-306`](../../app/scheduled_tasks.py) — lazy `cycle_length_days` / `rent_effective_at` write on first cycle
  - [`app/utils/economy_rebalance.py:360`](../../app/utils/economy_rebalance.py) — rebalancer mutation
- The `policy_uuid` (which per `DOM-POL-001 §VI.0` **is** the version identifier) never rotates because there is no path that inserts a new row.

**Violations against doctrine:**

| Rule | Location |
| --- | --- |
| `DOM-POL-001 §VI` — "immutable after insert, no update in place" | all three mutation sites above |
| `DOM-CLASS-003 §XI.4` — no "singleton mutable settings blobs" | `RentSettings.class_id` `unique=True` + `updated_at` `onupdate` |
| `DOM-POL-001 §VI` — "each submission creates a new policy_uuid" | teacher save keeps the same `policy_uuid` across mutations |
| `DOM-CLASS-003 ECON-CONST-002` — activated policy versions immutable | in-place `rent_settings` edits mutate active policy |

The deleted "Corrections tab" existed to compensate for exactly this failure mode: mid-cycle rent-rate changes producing misapplied late fees. Under a compliant append-only mutation pattern the corrective UI would be unnecessary.

**Status:** documented, not fixed. See §III for the remediation scope.

### 3. Dead schema (Scope A — remediated in this branch)

Migration `c5459df99053` added `rent_settings.active_version_id` and `rent_settings.next_version_id` alongside a `rent_policy_versions` table. Migration `7c3d4e5f6a7b` (`drop_all_unauthorized_tables`) dropped `rent_policy_versions` and the FK constraints but left the columns behind. The `RentSettings` ORM model does not declare them, no code reads or writes them, every row holds `NULL`.

**Fix (this branch):** migration [`2978fdba914a`](../../migrations/versions/2978fdba914a_drop_dead_rent_settings_version_columns.py) drops both columns. Idempotent (`column_exists` guards + defensive FK sweep), reversible, upgrade→downgrade→upgrade cycle green against dev DB, linter clean.

---

## II. Doctrine clarifications recorded

### 1. Ownership of `rent_settings` and sibling policy tables (`DOM-CORE-001`, `DOM-CORE-002`)

Prior state: `DOM-CORE-001 §2` and `DOM-CORE-002 §2` disagreed. `DOM-CORE-001` listed `rent_settings` under Class Configuration; `DOM-CORE-002` attributed it to `DOM-OBL-001`. Neither matched `DOM-CLASS-001 §II/§V` (disclaims ownership) or `DOM-OBL-001 §VI` (owns only `assessment_events`, `bill_cycles`).

Corrected state:

| Table | Owner (repository) | Consumer |
| --- | --- | --- |
| `rent_settings` | `DOM-POL-001` | `DOM-OBL-001` |
| `payroll_settings`, `payroll_rewards`, `payroll_fines` | `DOM-POL-001` | `DOM-PROD-001` |
| `hall_pass_settings` | `DOM-POL-001` | `DOM-PROD-001` |
| `store_items`, `store_item_visibility` | `DOM-POL-001` | `DOM-STORE-001` |
| Insurance policy definitions | `DOM-POL-001` | Insurance operational flow |
| `banking_settings` (savings APY, overdraft, interest) | **Class Configuration → `economic-engine`** (NOT Policies) | — |

**No Banking domain exists.** Any prior reference to one was retracted (commit `5f6c316b`).

### 2. Policies is a repository, not a mutator (`DOM-POL-001 §VI`)

`DOM-POL-001 §VI` renamed from "Mutation Contract" to "Insert and Availability Contract." Policies does not originate mutation flows; other domains submit definitions through Policies, which records each submission as a new immutable row keyed by a new `policy_uuid`. `Insert` and `Update` collapsed into a single `Insert` action since both produce new rows.

### 3. `policy_uuid` is the version (`DOM-POL-001 §VI.0`)

New subsection promotes `policy_uuid` to a first-class definitional statement: it **is** the version identifier for a policy definition. No separate version pointer or version-number column belongs on a Policies-repository table. Cross-references `DOM-CLASS-003 §11` and `§224`, which restrict `policy_versions` / `policy_transitions` to economic-policy lineage and explicitly delegate domain-specific versioning back to `DOM-POL-001`.

### 4. `DOM-PROD-001` coordination bullets rewired

`DOM-PROD-001 §XII` bullets for payroll and hall-pass previously asserted "owned by Class Configuration." Rewritten to reflect Policies-as-source with `DOM-PROD-001` as consumer.

---

## III. Scope B — remediation plan (NOT executed in this branch)

Rebuilding the `rent_settings` mutation path to comply with `DOM-POL-001 §VI` requires:

1. **Model changes** (`app/models.py`):
   - Drop `unique=True` on `RentSettings.class_id`.
   - Add composite index `(class_id, created_at DESC)` for "current row" lookup.
   - Remove `onupdate=utc_now` from `updated_at` (or drop `updated_at` entirely).
   - Remove or relocate `rent_effective_at` — either bake into the immutable row at insert time (computed from `rent_configured_at + cycle_length_days`) or lift the cycle-boundary concern into `bill_cycles` where `DOM-OBL-001` already owns `next_assessment_at`.

2. **Route changes** (`app/routes/admin.py:5817-5859`):
   - Rewrite teacher save to `INSERT` a new row with a fresh `policy_uuid` instead of mutating existing fields.
   - Any read path that assumed "the rent_settings row" now needs an explicit "latest by created_at" or availability-projection lookup.

3. **Scheduler changes** (`app/scheduled_tasks.py:302-306`):
   - Remove in-place `settings.cycle_length_days = ...` and `settings.rent_effective_at = ...` writes.
   - Boundary values must come from the immutable row at insert time or the `bill_cycles` operational projection.

4. **Rebalancer changes** (`app/utils/economy_rebalance.py:360`):
   - Replace in-place `rent_settings.rent_amount = ...` with insert of a new row.

5. **Template changes**:
   - Any template that assumes stable identity of "the rent_settings row" needs to consume the current-in-force row through the view model, not by direct model access.

6. **Migration**:
   - Drop `unique=True` constraint on `class_id`, add the composite index.
   - Backfill: existing rows keep their `policy_uuid`; new inserts start creating additional rows per submission.

7. **Corrections-tab permanent obsolescence**:
   - The deleted "Reverse Misapplied Late Fees" UI stays deleted. Under append-only rent settings the failure mode it compensated for cannot occur — a mid-cycle rate change becomes a new row that takes effect prospectively, leaving the current cycle's rate untouched for already-assessed obligations.

---

## IV. Impact on domain matrix and audits

### Obligations Domain (`DOM-OBL-001`)

Status downgraded from **PRODUCTION READY** to **PRODUCTION READY with known Phase 10 audit gap**:

- The 2026-07-26 audit missed cross-layer reference verification (backend routes deleted, templates not swept).
- The audit also did not surface the `rent_settings` mutation-pattern violation because `rent_settings` is Policies-domain territory and was out of the Obligations-domain audit scope — a boundary confusion enabled by the pre-existing `DOM-CORE-001` / `DOM-CORE-002` ownership contradiction (now corrected).

**Recommendation:** re-run Phase 10 for Obligations after Scope B lands, with an explicit cross-layer template sweep and an explicit joint audit with Policies for any table Obligations consumes.

### Policies Domain (`DOM-POL-001`)

Status: **doctrine substantially advanced this session, phase progression unchanged** (still 0-1 Spec review).

Doctrine now covered in DOM-POL-001:

- ✅ `policy_uuid` = version (`§VI.0`)
- ✅ Insert and Availability Contract, no in-place mutation (`§VI`)
- ✅ Full table scope: rent, payroll, hall-pass, store, insurance (`§X` boundary table)
- ✅ Explicit exclusion of `banking_settings` (routed to `economic-engine`)
- ✅ Cross-references to `DOM-CLASS-003 §11 / §224` for the economic-policy vs domain-policy distinction

Still to do for phase progression: standard SOP-DEV-002 sequence (Phase 2 persistence audit, Phase 3 primitives, Phase 4 FEAT-INTEGRITY wiring, etc.). Blocked by the same domain sequencing constraints noted in the matrix.

### Class Configuration Domain (`DOM-CLASS-001`)

No status change, but confirmation for the ongoing Phase 7 work:

- `class_features` and `economic-engine` are the only Class-Configuration primary schema tables.
- `banking_settings` content is a Class-Configuration → `economic-engine` concern.
- All other `*_settings` tables are routed through `DOM-POL-001`.

---

## V. Commits (session record)

Fast-forwarded into `feat/paste-staging-grid`:

| Commit | Purpose |
| --- | --- |
| `053c20f4` | Emergency template fix: remove UI for deleted Obligation routes |
| `1b028b37` | Correct `rent_settings` ownership; add DOM-POL-001 to core summaries |
| `eee6e37b` | Rename DOM-POL-001 §VI; extend Policies repo scope to all `*_settings` |
| `5f6c316b` | Retract Banking domain; `banking_settings` → economic-engine |
| `841957b2` | Delegate payroll_* and hall_pass_settings to DOM-POL-001 |
| `e6f10734` | Promote `policy_uuid` to first-class in DOM-POL-001 §VI.0 |
| `31be25a3` | Drop dead `rent_settings.active_version_id` / `next_version_id` |

---

## VI. Follow-up incidents to prevent

1. **Cross-layer reference verification is now a mandatory Phase 10 gate.** No domain may be certified without a Playwright (or equivalent real-browser) traversal of every route the domain owns, under canonical test context, with zero `BuildError` / `jinja2.exceptions` / console errors.

2. **Ownership contradictions in `DOM-CORE-001` / `DOM-CORE-002`** must be resolved by cross-checking against the owning domain's constitutional doc. `DOM-CORE-*` summaries are subordinate to `DOM-*` domain specs — when they disagree, the domain spec wins and the summary is corrected.

3. **Dev DB destructive-op protection** (recorded 2026-08-15 after subagent incident): treat dev DB the same as prod — no schema drops, truncations, or migration resets without explicit user confirmation, even to unblock automation.

---

**Author:** Claude Opus 4.7 (session assistant, under user direction)
**Session date:** 2026-08-16
