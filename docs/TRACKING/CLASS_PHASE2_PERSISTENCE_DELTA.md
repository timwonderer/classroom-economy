# CLASS Phase 2: Persistence Reconstruction Delta (REVISED)

**Date:** 2026-08-08  
**Status:** Implementation in Progress (All Phases Delivered, Phase D Blocked by Phase 3 FEATs)  
**Authority:** DOM-CLASS-001, DOM-CLASS-002, SPEC-ECON-001, SPEC-ECON-002

## Implementation Status

**Phase 2a - ORM Layer:** ✅ COMPLETE  
**Phase 2b - Remove Surrogate ID:** ✅ COMPLETE  
**Phase 2c - Consumer Migration (Reads):** ✅ COMPLETE  
**Phase 2d - Test Infrastructure:** ⏳ BLOCKED by Phase 3 FEAT-ECON-001 implementation  
**Phase 2e - Drop FeatureSettings Table:** ⏳ Pending (awaiting Phase D completion)  

---

## I. Executive Summary

Class Configuration persistence is currently fragmented across six tables with unclear ownership and mutable singleton anti-patterns. This delta reconstructs persistence to match the canonical **three-table model**:

1. **`classes`** — class boundary and identity (retain, audit questionable columns)
2. **`economic-engine`** — immutable, versioned class-level economic configuration (create new, UUID-based)
3. **`class_features`** — append-only feature enablement timeline (retain, fix for immutability)

**Removed tables:**
- `feature_settings` (mutable singleton, migrated)
- `policy_versions`, `policy_transitions` (stale architecture, not part of CLASS Phase 2)

**Deprecated/legacy (Policy domain owns):**
- `payroll_settings` (extract `expected_weekly_hours` only; Payroll domain owns the rest)

**Absorbed into CLASS:**
- `banking_settings` (banking configuration is now CLASS-owned per Phase 0–1 decision; extract canonical interest rate and configuration into `economic-engine`)

---

## II. Current Structure

### 2.1 Classes Table

**Table:** `classes` (Model: `ClassEconomy`)  
**Record Count:** ~100–1000 (production varies)  
**Ownership:** Canonical per DOM-CLASS-001

| Column | Type | Current Use | Canonical? | Disposition |
|--------|------|-------------|-----------|-------------|
| `class_id` | UUID (String(36)) | PK, canonical boundary | ✅ | **Retain** |
| `class_public_id` | UUID (String(36)) | Public alias | ✅ | **Retain** |
| `join_code` | String(20) | Unique teacher/student access code | ✅ | **Retain** |
| `user_id` (FK users) | Integer | Teacher identity (sole owner/creator) | ✅ | **Rename to `teacher_user_id`** (clarity) |
| `section` | String(50) | Display metadata (mutable period label) | ✅ | **Retain as mutable** (unlike immutable timezone) |
| `block` (synonym) | — | Alias for `section` (legacy) | ✅ | **Remove synonym** (use `section` directly) |
| `display_name` | String(100) | Teacher-facing class label (mutable) | ✅ | **Retain** |
| `class_timezone` | String(64) | Immutable class-local time boundary | ✅ | **Retain** (immutable; temporal interpretation depends on it) |
| `created_at` | DateTime(UTC) | Class creation timestamp | ✅ | **Retain** (historical fact) |
| `updated_at` | DateTime(UTC) | Last row mutation timestamp | ❌ | **Remove** (generic ORM metadata, no architectural requirement) |
| `created_by_user_id` (FK users) | Integer | Audit trail (legacy) | ❌ | **Remove** (redundant; teacher_user_id already says sole owner) |

**Rationale for removals:**
- `updated_at`: Generic "last time any field changed" is ORM metadata, not Class Configuration truth. Current display_name is authoritative; no feature requires "when did display_name last change." Audit/Operations layer records execution provenance, not ORM timestamps.
- `created_by_user_id`: Only teacher_user_id owns class configuration and creation in this model. A second "creator" FK is redundant domain state. Only teacher creates classes; there is no other creator role to distinguish.

**Distinguishing Mutability:**
- `class_timezone` — **IMMUTABLE** (temporal interpretation depends on fixed boundary; cannot change after creation)
- `section`, `display_name` — **MUTABLE** (display metadata; can be renamed/reorganized without affecting class economy)

**Constraints:**
- `class_id` PRIMARY KEY ✅
- `class_public_id` UNIQUE ✅
- `join_code` UNIQUE ✅
- `teacher_user_id` FK(users.id, ondelete='CASCADE') ✅
- Immutability constraint on `class_timezone` (SQLAlchemy event listener) ✅

**Breaking Changes:**
- Rename `user_id` → `teacher_user_id` (callers update FK reference)
- Remove `block` synonym (use `section` directly)
- Remove `updated_at` column (callers stop reading)
- Remove `created_by_user_id` column (callers stop reading)

---

### 2.2 Feature Settings Table (TO BE REMOVED)

**Table:** `feature_settings` (Model: `FeatureSettings`)  
**Record Count:** ~100–1000 (one per class, mutable)  
**Ownership:** Currently stores class-level economic posture (violates clear separation)

| Column | Type | Current Use | Disposition |
|--------|------|-------------|-------------|
| `id` | Integer | PK | **DELETE TABLE** |
| `class_id` | String(36) | FK(classes) | (mutable row owner) |
| `economy_policy_mode` | String(20) | Economic posture (`tight`, `default`, `comfortable`) | **→ Move to `economic-engine`** |
| `economy_policy_updated_at` | DateTime | Timestamp of last mode mutation | **→ Delete (immutable versioning in economic-engine)** |
| `economy_policy_alignment_status` | String(32) | Status field (null/legacy) | **→ Delete** |
| `economy_last_rebalanced_at` | DateTime | Last teacher rebalance action | **→ Audit table (DOM-OPS)** |
| `economy_last_rebalanced_by` | Integer | Which user triggered rebalance | **→ Audit table (DOM-OPS)** |
| `created_at` | DateTime | Table creation | **→ Delete** |
| `updated_at` | DateTime | Mutable row update | **→ Delete** |

**Why Remove:**
- Mutable singleton anti-pattern (violates ECON-CONST-001: "Economic Policy Evolution Is Append-Only")
- Conflates configuration (`economy_policy_mode`) with audit state (who rebalanced, when)
- No unique constraint prevents edge-case multi-row duplication
- FEAT-layer consumers read this table to determine active policy, but read authority belongs to immutable `economic-engine` + `policy_transitions` lineage

**Data Migration:**
1. For each row in `feature_settings`:
   - Extract `economy_policy_mode` → write to new `economic-engine` row as `economy_policy_mode`
   - Capture `created_at` as `economic-engine.created_at` (initialization timestamp)
   - Discard `economy_policy_updated_at`, `economy_policy_alignment_status` (replaced by append-only versioning)
   - Rebalance audit events → migrate to `audit_events` table (DOM-OPS-001)
2. Drop `feature_settings` table after validation

---

### 2.3 Class Features Table (RETAIN + RESTRUCTURE FOR APPEND-ONLY)

**Table:** `class_features` (Model: `ClassFeature`)  
**Record Count:** ~600–6000+ (append-only timeline; multiple records per feature per class)  
**Ownership:** Canonical per DOM-CLASS-001

| Column | Type | Current Use | Disposition |
|--------|------|-------------|-------------|
| `id` | Integer | PK (surrogate) | **Remove** (no demonstrated requirement; composite PK is stronger) |
| `class_id` | String(36) | FK(classes) | **Retain** |
| `feature_name` | String(32) | Feature identifier | **Rename to `feature`** (clarity) |
| `created_at` | DateTime | Row insertion timestamp | **Retain** (when this config row was written) |
| `effective_at` | DateTime | NEW | When this feature state becomes/became active |

**New Columns:**
- `effective_at` (DateTime, required) — when feature state change takes effect (distinct from created_at)
  - Example: Created Aug 20, effective Sep 1 (future-law scheduling)
  - Example: Created Aug 20, effective Aug 20 (immediate activation)
- `economic_version_id` (UUID FK to `economic-engine`, nullable) — which version enabled/disabled this feature
  - **NOT NULL means feature enabled under that version**
  - **NULL means feature disabled** (no implicit default)

**Key Distinction: `created_at` vs `effective_at`**
- `created_at`: When the configuration decision was made (Aug 20)
- `effective_at`: When the decision takes/took effect (Sep 1)
- This distinction is essential for future-law visibility (SPEC-ECON-002 requirement)

**Removed Constraints:**
- ❌ `UNIQUE(class_id, feature_name)` — **DESTROYS append-only timeline**
- ❌ Surrogate `id` PK — **removed; natural PK is composite**

**New Primary Key & Constraints:**
- PRIMARY KEY: `(class_id, feature, effective_at)` — one state change per feature per instant
- `UNIQUE(class_id, feature, effective_at)` — prevents contradictory state at exact same instant
- `FK(economic_version_id)` → `economic-engine(economic_version_id)` with **`ON DELETE RESTRICT`**
  - **NOT `SET NULL`** — deleting version must not rewrite history by fabricating disablement
- `CHECK(feature IN (...))` — maintain feature name whitelist

**Immutability:**
- Rows are never updated after insertion
- Feature state changes through new appended rows, not mutation
- Future state visible before activation (future-law scheduling)

**Example Timeline:**
```
class_id | feature | economic_version_id | created_at         | effective_at
---------|---------|---------------------|--------------------|---------------------
A08      | rent    | V1                  | 2026-08-31 10:00   | 2026-08-31 00:00:00
A08      | rent    | V2                  | 2026-09-01 14:30   | 2026-09-02 00:00:00
A08      | rent    | NULL                | 2026-09-30 09:15   | 2026-10-01 00:00:00  (disabled)
A08      | rent    | V3                  | 2026-10-31 16:45   | 2026-11-01 00:00:00  (re-enabled)
```

**Breaking Changes:**
- Remove `id` PK (callers can't use integer row identifier)
- Rename `feature_name` → `feature` (callers update column reference)
- Add required `effective_at` column (callers must provide)
- Change FK behavior from `ON DELETE SET NULL` to `ON DELETE RESTRICT`

**Data Migration:**
- Existing `class_features` rows become initial timeline (effective_at = created_at for immediate activation)
- Keep both columns (created_at and effective_at)
- future feature state changes append new rows with different effective_at
- economic_version_id initially NULL (until version migration)

---

### 2.4 Payroll Settings Table (NOT RECONSTRUCTED IN PHASE 2)

**Table:** `payroll_settings` (Model: `PayrollSettings`)  
**Record Count:** ~100–1000 (class-scoped; legacy block-scoped rows)  
**Ownership:** **Payroll is Policy-owned.** CLASS Phase 2 extracts CLASS-owned fields only.

| Column | Type | Current Use | Disposition in Phase 2 |
|--------|------|-------------|------------------------|
| `id` | Integer | PK | Leave unchanged |
| `class_id` | String(36) | FK(classes) | Leave unchanged |
| `block` | String(10) | NULL = global (legacy) | Leave for Payroll Phase to handle |
| `pay_rate` | Numeric | $/minute | **Policy-owned; do not reconstruct** |
| `payroll_frequency_days` | Integer | Interval | **Policy-owned; do not reconstruct** |
| `next_payroll_date` | DateTime | Scheduler state | **Leave; audit responsibility** |
| `is_active` | Boolean | Active toggle | **Leave; Policy domain owns** |
| `expected_weekly_hours` | Float | Class capacity (for CWI math) | **Extract to `economic-engine`** |
| `(other scheduling)` | various | Detailed scheduling | **Leave; Policy-owned** |

**ACTION FOR PHASE 2:**
1. During data migration, extract `expected_weekly_hours` (non-NULL values) from PayrollSettings
2. Write to `economic-engine` (see §3.1 for handling NULL values)
3. **Do NOT** reconstruct payroll_settings itself
4. **Do NOT** migrate pay rates, frequencies, or scheduler state (Policy domain handles this in later phase)
5. Leave payroll_settings table intact for backward compat; Payroll Phase will reconstruct it

**Breaking Changes:**
- None in Phase 2 (payroll_settings untouched except data extraction)

---

### 2.5 Banking Settings Table (ABSORBED INTO CLASS; EXTRACT TO ECONOMIC-ENGINE)

**Table:** `banking_settings` (Model: `BankingSettings`)  
**Record Count:** ~100–1000 (class-scoped; legacy block-scoped rows)  
**Ownership:** **Banking is CLASS-owned per Phase 0–1 decision.** Extract teacher-selected configuration into `economic-engine`.

**Test:** Is this a teacher-selected, reusable class economic configuration fact, or derived/runtime state?

Per SPEC-ECON-001, the following are explicitly independent behavioral choices and belong in immutable Economic Engine snapshots:

| Legacy Column | Target Column | Disposition |
|---------|--------|-------------|
| `savings_apy` | `economic-engine.interest_rate` | **EXTRACT** |
| `interest_calculation_type` | `economic-engine.interest_calculation_type` | **EXTRACT** (teacher choice per SPEC) |
| `compound_frequency` | `economic-engine.compound_frequency` | **EXTRACT** (teacher choice per SPEC) |
| `interest_schedule_type` | `economic-engine.interest_payout_frequency` | **EXTRACT** (teacher choice; rename for clarity per SPEC) |
| (inferred) — | `economic-engine.interest_accrual_frequency` | **EXTRACT** (teacher choice per SPEC-ECON-001 separation) |

**Do NOT migrate in Phase 2 (unresolved/blocked):**

| Column | Reason | Disposition |
|--------|--------|-------------|
| `savings_monthly_rate` | Derived from APY; re-compute as needed | Delete |
| `interest_payout_start_date` | May be derivable from feature effective_at + payout cadence; product behavior unestablished | **BLOCKED** — preserve in legacy table, pending canonical classification |
| `overdraft_fee_*` (all) | SPEC-ECON-001 contains no overdraft semantics; no canonical authority | **BLOCKED** — preserve in legacy table, pending canonical classification of Banking overdraft policy |
| `is_active` | Runtime state, not configuration truth | Leave in legacy table |
| `block` | Legacy per-block partitioning | Ignore per-block; migrate only NULL/global rows |

**ACTION FOR PHASE 2:**

1. **Extract CLASS-canonical fields to `economic-engine`:**
   - `savings_apy` → `interest_rate`
   - `interest_calculation_type` → `interest_calculation_type`
   - `compound_frequency` → `compound_frequency`
   - `interest_schedule_type` → `interest_payout_frequency` (rename)
   - Infer `interest_accrual_frequency` if not explicitly in legacy banking_settings

2. **Preserve unresolved fields in banking_settings:**
   - Do NOT delete banking_settings table
   - Mark BLOCKED columns with migration comments documenting canonical classification requirement
   - Document that Phase 3+ must resolve these before further schema changes

3. **Bootstrap strategy: Explicit NULL**
   - If `savings_apy` is NULL or missing: write NULL to `economic-engine.interest_rate` (not configured)
   - If interest_calculation_type missing: write NULL (not configured)
   - If compound_frequency missing: write NULL (not configured)
   - If interest_payout_frequency missing: write NULL (not configured)
   - Runtime consuming unconfigured field must fail explicitly with clear error message
   - Do NOT fabricate defaults (0.0, 'simple', etc.)

**Breaking Changes:**
- Column name change: `interest_schedule_type` → `interest_payout_frequency` (clarity/spec alignment)

---

### 2.6 Policy Versions & Policy Transitions Tables (NOT PART OF PHASE 2)

**Tables:** `policy_versions`, `policy_transitions`  
**Status:** **Explicitly out of scope for CLASS Phase 2**

These tables were part of earlier architecture proposals but are **not part of the canonical CLASS domain**. As established in Phase 0–1:
- Economic versioning happens through `economic-engine` immutable records + `class_features` append-only timeline
- Policy governance (rent, insurance, payroll detail, banking detail if any) will have **domain-specific persistence** when those domains reconstruct
- **Do NOT** use generic `policy_versions` / `policy_transitions` tables in CLASS Phase 2

**Disposition:** **Leave untouched** if they exist from prior phases; they will be owned by relevant domains during their reconstruction phases. CLASS Phase 2 does not depend on them.

---

## III. New Structure: Economic Engine

### 3.1 Economic Engine Table (CREATE)

**Table Name:** `economic_engine` (following DOM-CLASS-001 naming convention: hyphenated domain concept, underscored table name)  
**Model Name:** `EconomicEngine`  
**Record Count:** ~100–1000+ (immutable versioned history; one+ per class)  
**Ownership:** DOM-CLASS-001 (Class Configuration)

**Canonical Fields:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `economic_version_id` | UUID (String(36)) | NO | uuid.uuid4() | Immutable version identity (UUID, not auto-increment) |
| `class_id` | String(36) | NO | — | FK(classes.class_id, ondelete='CASCADE') |
| `previous_version_id` | UUID (String(36)) | YES | NULL | FK(economic_engine.economic_version_id, ondelete='RESTRICT'); forms version chain |
| **Class Capacity** | — | — | — | — |
| `expected_weekly_hours` | Float | YES | NULL | Class workload estimate for CWI; **NULL = not specified** |
| **Banking Configuration** | — | — | — | — |
| `interest_rate` | Numeric(8,6) | YES | NULL | Annual savings interest rate (APY); **NULL = not specified** |
| `interest_calculation_type` | String(20) | YES | NULL | Compounding method (`simple` or `compound`); **NULL = not specified** |
| `compound_frequency` | String(20) | YES | NULL | How often accrued interest joins principal (`daily`, `weekly`, `monthly`); **NULL = not specified** |
| `interest_accrual_frequency` | String(20) | YES | NULL | How often interest is earned (per SPEC-ECON-001); **NULL = not specified** |
| `interest_payout_frequency` | String(20) | YES | NULL | How often interest is posted to ledger (`weekly`, `monthly`); **NULL = not specified** |
| **Economic Policy** | — | — | — | — |
| `economy_policy_mode` | String(20) | NO | `default` | Economic mode: `tight`, `default`, or `comfortable` |
| **Audit** | — | — | — | — |
| `created_at` | DateTime(UTC) | NO | utc_now | Immutable creation timestamp (when this version was recorded) |

**Constraints:**
- PRIMARY KEY: `economic_version_id` (UUID)
- UNIQUE: `(class_id, economic_version_id)` — one record per version (explicit)
- FK: `class_id` → `classes.class_id` (ondelete='CASCADE')
- FK: `previous_version_id` → `economic_engine.economic_version_id` (ondelete='RESTRICT')
  - Forms immutable linked-list lineage (version chain, not tree)
  - **RESTRICT prevents accidental orphaning** — deleting intermediate version breaks history
- CHECK: `economy_policy_mode IN ('tight', 'default', 'comfortable')`
- CHECK: `expected_weekly_hours IS NULL OR expected_weekly_hours > 0` (positive if specified)
- CHECK: `interest_rate IS NULL OR (interest_rate >= 0 AND interest_rate <= 1.0)` (valid APY 0–100% if specified)
- CHECK: `interest_calculation_type IS NULL OR interest_calculation_type IN ('simple', 'compound')`
- CHECK: `compound_frequency IS NULL OR compound_frequency IN ('daily', 'weekly', 'monthly')`
- CHECK: `interest_accrual_frequency IS NULL OR interest_accrual_frequency IN ('daily', 'weekly', 'monthly')` (or per SPEC)
- CHECK: `interest_payout_frequency IS NULL OR interest_payout_frequency IN ('weekly', 'monthly')` (or per SPEC)
- INDEX: `(class_id, created_at DESC)` — latest version per class query
- INDEX: `(class_id)` — class isolation reads

**Immutability:**
- Rows are never updated after insertion (enforced by ORM/FEAT layer)
- Version evolution happens through new immutable rows + `previous_version_id` chain
- Prevents accidental mutation of active configuration

**NULL Semantics:**
- `expected_weekly_hours = NULL` means the value was not configured (not "0 hours")
- `interest_rate = NULL` means the value was not configured (not "0% APY")
- Do NOT fabricate defaults during migration using `COALESCE(..., 5.0)`; carry forward actual canonical truth

**Rationale:**
- Immutable versioned design aligns with DOM-CLASS-002/SPEC-ECON-001 (append-only evolution)
- UUID identity enables portable configuration identity across distributed systems
- Explicit `previous_version_id` chain provides audit trail and replay capability
- Single row per version per class (not multi-row per policy domain)
- Fields chosen from DOM-CLASS-002 and SPEC-ECON-001 authority:
  - `expected_weekly_hours`: Required for CWI calculation (class capacity)
  - `interest_rate`: Required by savings accrual math (SPEC-ECON-001)
  - `economy_policy_mode`: Required to determine class operating posture
- No automatic defaults — configuration truth is explicit

---

## IV. Breaking Changes & Downstream Impact

### 4.1 Model Code Changes

| Model | Change | Impact | Mitigation |
|-------|--------|--------|-----------|
| `ClassEconomy` | Rename `user_id` → `teacher_user_id` | FK reference updates | Update all callers in routes, services, migrations |
| `ClassEconomy` | Remove `block` synonym | Direct `.section` usage now required | Search/replace `block` → `section` in templates/routes |
| `ClassFeature` | Rename `feature_name` → `feature` | Column reference updates | Update all callers |
| `ClassFeature` | Add `economic_version_id`, `effective_at` | New columns in queries | Optional fields for backward compat |
| `FeatureSettings` | Delete entire model | Model no longer exists | Migrate reads to `economic-engine` + `class_features` |
| (New) `EconomicEngine` | Create new model | New model class needed | Implement model with immutability validation |
| `PayrollSettings` | Deprecate `pay_rate`, frequency fields | Reads must migrate | FEAT layer will handle gradual migration |
| `BankingSettings` | Deprecate `savings_apy`, fee fields | Reads must migrate | FEAT layer will handle gradual migration |

---

### 4.2 FEAT Layer & Route Layer Changes

**Affected FEAT files:**
- `app/feats/class_config/` — create if not exists, refactor to read from `economic-engine`
- `app/feats/payroll/` — migrate pay-rate reads to `policy_versions`
- `app/feats/banking/` — migrate interest-rate reads to `policy_versions`

**Affected routes:**
- `/admin/settings` — class configuration view/mutation
- `/admin/payroll-settings` — payroll management (migrate to policy version UI)
- `/admin/banking-settings` — banking management (migrate to policy version UI)
- `/admin/rebalance` — economic rebalancing workflow

**Affected tests:**
- 63 test references to `ClassEconomy`, `PayrollSettings`, `BankingSettings`, `FeatureSettings`, `PolicyVersion`/`PolicyTransition`
- Tests will need updates to:
  - Use `economic_engine` for configuration reads
  - Use `policy_versions` for domain-specific policy reads
  - Eliminate direct `feature_settings` queries

---

### 4.3 Data Migration Plan

**Phase 1: Create new tables & copy data**
1. Create `economic-engine` table with immutability constraints
2. For each `feature_settings` row:
   - Create `economic-engine` row: `(class_id, economy_policy_mode, expected_weekly_hours='5.0', interest_rate='0.0')`
   - Set `previous_version_id=NULL` (first version)
3. For each `class_features` row:
   - Add `economic_version_id=NULL` (not yet bound to version)
   - Add `effective_at=created_at`

**Phase 2: Migrate reads (FEAT layer)**
1. Update FEAT layer to read from `economic-engine` instead of `feature_settings`
2. Update policy version reads to prefer `policy_versions` for domain config
3. Gradual rollout: use feature flags to test new paths

**Phase 3: Deprecate writes**
1. Stop writing to `feature_settings` (mutable singleton)
2. Routes redirect mutation requests to version-creation workflow
3. Existing `payroll_settings` / `banking_settings` rows remain for backward compat (read-only)

**Phase 4: Drop obsolete tables**
1. After all dependencies migrated, drop `feature_settings`
2. Mark `payroll_settings` / `banking_settings` as legacy (policy domain owns going forward)

---

## V. Canonical Schema Definition

### 5.1 classes Table (Canonical)

```sql
CREATE TABLE classes (
    class_id VARCHAR(36) PRIMARY KEY,
    class_public_id VARCHAR(36) UNIQUE NOT NULL,
    join_code VARCHAR(20) UNIQUE NOT NULL,
    teacher_user_id INTEGER NOT NULL,
    display_name VARCHAR(100),  -- Mutable class label
    section VARCHAR(50),  -- Mutable period/section label
    class_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_classes_teacher_user_id FOREIGN KEY (teacher_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_classes_timezone CHECK (class_timezone IN (/* valid IANA timezones */))
);

CREATE INDEX ix_classes_teacher_user_id ON classes(teacher_user_id);
CREATE INDEX ix_classes_class_public_id ON classes(class_public_id);
CREATE INDEX ix_classes_join_code ON classes(join_code);
```

**Removed columns:**
- `updated_at` (generic ORM metadata; no architectural requirement)
- `created_by_user_id` (redundant; teacher_user_id is sole owner)

### 5.2 economic_engine Table (Immutable Configuration Snapshots)

```sql
CREATE TABLE economic_engine (
    economic_version_id VARCHAR(36) PRIMARY KEY,  -- UUID, not auto-increment
    class_id VARCHAR(36) NOT NULL,
    previous_version_id VARCHAR(36),  -- NULL for first version; RESTRICT prevents orphaning
    
    -- Class Capacity
    expected_weekly_hours FLOAT,  -- NULL if not specified
    
    -- Banking Configuration (per SPEC-ECON-001 independent behavioral choices)
    interest_rate NUMERIC(8,6),  -- NULL if not specified
    interest_calculation_type VARCHAR(20),  -- 'simple' or 'compound'; NULL if not specified
    compound_frequency VARCHAR(20),  -- 'daily', 'weekly', 'monthly'; NULL if not specified
    interest_accrual_frequency VARCHAR(20),  -- How often interest earned; NULL if not specified
    interest_payout_frequency VARCHAR(20),  -- 'weekly' or 'monthly'; NULL if not specified
    
    -- Economic Policy
    economy_policy_mode VARCHAR(20) NOT NULL DEFAULT 'default',  -- 'tight', 'default', 'comfortable'
    
    -- Audit
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_economic_engine_class_id FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE,
    CONSTRAINT fk_economic_engine_previous_version_id FOREIGN KEY (previous_version_id) REFERENCES economic_engine(economic_version_id) ON DELETE RESTRICT,
    CONSTRAINT ck_economic_engine_mode CHECK (economy_policy_mode IN ('tight', 'default', 'comfortable')),
    CONSTRAINT ck_economic_engine_hours CHECK (expected_weekly_hours IS NULL OR expected_weekly_hours > 0),
    CONSTRAINT ck_economic_engine_rate CHECK (interest_rate IS NULL OR (interest_rate >= 0 AND interest_rate <= 1.0)),
    CONSTRAINT ck_economic_engine_calc_type CHECK (interest_calculation_type IS NULL OR interest_calculation_type IN ('simple', 'compound')),
    CONSTRAINT ck_economic_engine_compound_freq CHECK (compound_frequency IS NULL OR compound_frequency IN ('daily', 'weekly', 'monthly')),
    CONSTRAINT ck_economic_engine_accrual_freq CHECK (interest_accrual_frequency IS NULL OR interest_accrual_frequency IN ('daily', 'weekly', 'monthly')),
    CONSTRAINT ck_economic_engine_payout_freq CHECK (interest_payout_frequency IS NULL OR interest_payout_frequency IN ('weekly', 'monthly'))
);

CREATE INDEX ix_economic_engine_class_version ON economic_engine(class_id, created_at DESC);
CREATE INDEX ix_economic_engine_class_id ON economic_engine(class_id);
CREATE INDEX ix_economic_engine_previous_version_id ON economic_engine(previous_version_id);
```

**NULL Semantics:**
- All interest_* fields: NULL = "not specified" (teacher did not configure)
- expected_weekly_hours: NULL = "not specified" (teacher did not configure)
- Runtime consuming unconfigured field must fail explicitly

### 5.3 class_features Table (Append-Only Timeline)

```sql
CREATE TABLE class_features (
    class_id VARCHAR(36) NOT NULL,
    feature VARCHAR(32) NOT NULL,
    economic_version_id VARCHAR(36),  -- NULL means disabled; NOT NULL means enabled under that version
    effective_at TIMESTAMP NOT NULL,  -- When this state became/becomes active
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- When this decision was made
    
    CONSTRAINT pk_class_features PRIMARY KEY (class_id, feature, effective_at),
    CONSTRAINT fk_class_features_class_id FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE,
    CONSTRAINT fk_class_features_economic_version_id FOREIGN KEY (economic_version_id) REFERENCES economic_engine(economic_version_id) ON DELETE RESTRICT,
    CONSTRAINT ck_class_features_feature CHECK (feature IN ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store'))
);

CREATE INDEX ix_class_features_class_id ON class_features(class_id);
CREATE INDEX ix_class_features_feature ON class_features(feature);
CREATE INDEX ix_class_features_effective_at ON class_features(effective_at);
CREATE INDEX ix_class_features_class_feature_effective ON class_features(class_id, feature, effective_at DESC);  -- Latest state per feature
```

**Two Timestamps:**
- `created_at`: When this configuration decision was recorded (decision time)
- `effective_at`: When this feature state becomes/became active (state change time)
- Distinct to support future-law visibility (SPEC-ECON-002)

**No surrogate ID:**
- Natural PK is `(class_id, feature, effective_at)` — one state change per feature per instant
- Stronger and more semantically correct than arbitrary integer ID

---

## VI. Data Migration Strategy

### 6.1 Bootstrap Strategy for Missing Configuration

**Principle:** Preserve historical truth. If configuration was never set, the historical truth is NULL.

**Approach: Explicit NULL**

- If `expected_weekly_hours` missing/NULL in legacy data: Write NULL to `economic-engine.expected_weekly_hours`
- If `interest_rate` missing/NULL in legacy data: Write NULL to `economic-engine.interest_rate`
- If `interest_calculation_type` missing/NULL: Write NULL (not configured)
- If `compound_frequency` missing/NULL: Write NULL (not configured)
- If `interest_accrual_frequency` missing/NULL: Write NULL (not configured)
- If `interest_payout_frequency` missing/NULL: Write NULL (not configured)

**Runtime Behavior:**
- Any calculation requiring unconfigured field MUST fail explicitly with clear error message
- Do NOT silently default to 5.0 hours, 0.0% APY, etc.
- Fail fast: "Expected weekly hours not configured for class {class_id}"

**Rationale:**
- Migration's purpose is preserve historical truth, not invent configuration
- NULL semantics are explicit: "teacher never chose this value"
- Strict failure at runtime prevents silent nonsense
- Cleaner than pressure-filling values just to pass migration

---

### 6.2 Create economic_engine Table

```python
# In migration upgrade():

if not table_exists('economic_engine'):
    op.create_table(
        'economic_engine',
        sa.Column('economic_version_id', sa.String(36), primary_key=True),  # UUID
        sa.Column('class_id', sa.String(36), nullable=False, index=True),
        sa.Column('previous_version_id', sa.String(36), nullable=True),
        sa.Column('expected_weekly_hours', sa.Float, nullable=True),  # NO DEFAULT
        sa.Column('interest_rate', sa.Numeric(precision=8, scale=6), nullable=True),  # NO DEFAULT
        sa.Column('economy_policy_mode', sa.String(20), nullable=False, server_default='default'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], name='fk_economic_engine_class_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_version_id'], ['economic_engine.economic_version_id'], name='fk_economic_engine_prev', ondelete='RESTRICT'),
        sa.CheckConstraint("economy_policy_mode IN ('tight', 'default', 'comfortable')", name='ck_economic_engine_mode'),
        sa.CheckConstraint('expected_weekly_hours IS NULL OR expected_weekly_hours > 0', name='ck_economic_engine_hours'),
        sa.CheckConstraint('interest_rate IS NULL OR (interest_rate >= 0 AND interest_rate <= 1.0)', name='ck_economic_engine_rate'),
    )
    op.create_index('ix_economic_engine_class_version', 'economic_engine', ['class_id', 'created_at'], unique=False)
    op.create_index('ix_economic_engine_previous_version_id', 'economic_engine', ['previous_version_id'])
    print("✅ Created economic_engine table")
else:
    print("⚠️ economic_engine table already exists, skipping...")
```

### 6.3 Migrate Data (Explicit NULL Strategy)

```python
# In migration upgrade():

import uuid

if table_exists('feature_settings'):
    # MIGRATE: Extract configuration from legacy tables
    # Preserve historical truth: NULL means "never configured"
    
    rows_to_insert = op.get_bind().execute("""
        SELECT 
            fs.class_id,
            ps.expected_weekly_hours,  -- NULL if never configured
            bs.savings_apy,  -- NULL if never configured
            bs.interest_calculation_type,  -- NULL if never configured
            bs.compound_frequency,  -- NULL if never configured
            fs.economy_policy_mode,
            fs.created_at
        FROM feature_settings fs
        LEFT JOIN payroll_settings ps ON fs.class_id = ps.class_id AND ps.block IS NULL
        LEFT JOIN banking_settings bs ON fs.class_id = bs.class_id AND bs.block IS NULL
        WHERE NOT EXISTS (SELECT 1 FROM economic_engine WHERE economic_engine.class_id = fs.class_id)
    """).fetchall()
    
    inserted_count = 0
    for row in rows_to_insert:
        class_id, hours, rate, calc_type, compound_freq, mode, created_at = row
        version_id = str(uuid.uuid4())
        op.execute("""
            INSERT INTO economic_engine 
            (economic_version_id, class_id, previous_version_id, expected_weekly_hours, interest_rate, 
             interest_calculation_type, compound_frequency, interest_accrual_frequency, interest_payout_frequency,
             economy_policy_mode, created_at)
            VALUES (:version_id, :class_id, NULL, :hours, :rate, :calc_type, :compound_freq, NULL, NULL, :mode, :created_at)
        """, {
            'version_id': version_id,
            'class_id': class_id,
            'hours': hours,  # NULL if not configured; do NOT fabricate
            'rate': rate,  # NULL if not configured; do NOT fabricate
            'calc_type': calc_type,  # NULL if not configured
            'compound_freq': compound_freq,  # NULL if not configured
            'mode': mode,
            'created_at': created_at
        })
        inserted_count += 1
    
    print(f"✅ Migrated {inserted_count} classes to economic_engine")
    print("   Note: NULL configuration fields mean 'not specified' (teacher did not configure)")
    print("   Runtime must fail explicitly if consuming unconfigured field")
else:
    print("⚠️ feature_settings table not found; skipping migration")
```

### 6.4 Migrate class_features to Append-Only Timeline

```python
# In migration upgrade():

if table_exists('class_features'):
    # Step 1: Rename feature_name to feature (if exists)
    if column_exists('class_features', 'feature_name'):
        op.alter_column('class_features', 'feature_name', new_column_name='feature')
        print("✅ Renamed feature_name → feature")
    
    # Step 2: Add economic_version_id column (initially NULL)
    if not column_exists('class_features', 'economic_version_id'):
        op.add_column('class_features', sa.Column('economic_version_id', sa.String(36), nullable=True))
        op.create_foreign_key('fk_class_features_economic_version_id', 'class_features', 'economic_engine', ['economic_version_id'], ['economic_version_id'], ondelete='RESTRICT')
        print("✅ Added economic_version_id to class_features")
    
    # Step 3: Add effective_at column (backfill with created_at for immediate activation)
    if not column_exists('class_features', 'effective_at'):
        op.add_column('class_features', sa.Column('effective_at', sa.DateTime(timezone=True), nullable=True))
        # Backfill: assume existing rows were immediately activated at created_at
        op.execute("UPDATE class_features SET effective_at = created_at WHERE effective_at IS NULL")
        # Make NOT NULL
        op.alter_column('class_features', 'effective_at', nullable=False)
        op.create_index('ix_class_features_effective_at', 'class_features', ['effective_at'])
        op.create_index('ix_class_features_class_feature_effective', 'class_features', ['class_id', 'feature', 'effective_at'], unique=False)
        print("✅ Added effective_at to class_features (backfilled from created_at)")
    
    # Step 4: Drop old id PK (if exists) - use composite PK instead
    # Note: This is complex in migration; may need to recreate table or use PostgreSQL-specific commands
    # For safety, we document this but leave detailed implementation to the actual migration
    # Option: Keep id temporarily during Phase 2, complete removal in Phase 2b
    print("⚠️ Note: Remove id surrogate key in Phase 2b (requires table recreation or DB-specific commands)")
    
    # Step 5: Remove old UNIQUE(class_id, feature) constraint
    if constraint_exists('class_features', 'uq_class_features_class_feature'):
        op.drop_constraint('uq_class_features_class_feature', 'class_features')
        print("⚠️ Dropped old UNIQUE(class_id, feature) constraint")
else:
    print("⚠️ class_features table not found; skipping restructuring")
```

**Note on surrogate key removal:**
Dropping the `id` column and changing the PK from an auto-increment integer to a composite UUID-based key requires table recreation or database-specific syntax (PostgreSQL `ALTER TABLE` with ADD CONSTRAINT PRIMARY KEY). This may be deferred to a separate migration or Phase 2b for operational safety.

### 6.5 Downgrade Steps

```python
# In migration downgrade():

# Step 1: Revert class_features
if table_exists('class_features'):
    if constraint_exists('class_features', 'uq_class_features_event'):
        op.drop_constraint('uq_class_features_event', 'class_features')
        print("❌ Dropped UNIQUE(class_id, feature, effective_at)")
    
    if constraint_exists('class_features', 'fk_class_features_economic_version_id'):
        op.drop_constraint('fk_class_features_economic_version_id', 'class_features')
        print("❌ Dropped FK economic_version_id")
    
    if column_exists('class_features', 'economic_version_id'):
        op.drop_column('class_features', 'economic_version_id')
        print("❌ Dropped economic_version_id")
    
    if column_exists('class_features', 'effective_at'):
        op.drop_index('ix_class_features_effective_at', table_name='class_features')
        op.drop_column('class_features', 'effective_at')
        print("❌ Dropped effective_at")
    
    if column_exists('class_features', 'feature'):
        op.alter_column('class_features', 'feature', new_column_name='feature_name')
        print("❌ Renamed feature → feature_name")

# Step 2: Drop economic_engine
if table_exists('economic_engine'):
    op.drop_index('ix_economic_engine_class_version')
    op.drop_index('ix_economic_engine_previous_version_id')
    op.drop_table('economic_engine')
    print("❌ Dropped economic_engine table")
```

---

## VII. Test Impact Analysis

### 7.1 Affected Test Files

| Test File | Affected Model(s) | Test Count | Migration Status |
|-----------|-------------------|-----------|------------------|
| `conftest.py` | `ClassEconomy`, `FeatureSettings` | ~10 fixtures | Update to use `economic-engine` |
| `test_admin_signup_first_class.py` | `ClassEconomy` | 2 | Rename `user_id` → `teacher_user_id` |
| `test_banking_settings_class_scope.py` | `BankingSettings` | 1 | Migrate to `policy_versions` (Phase 3) |
| `test_payroll_settings_class_scope.py` | `PayrollSettings`, `ClassFeature` | 3 | Migrate to `policy_versions`; rename `feature_name` → `feature` |
| `test_settings_fallback_removal.py` | `PayrollSettings`, `BankingSettings`, `FeatureSettings` | 6 | Refactor to read from `economic-engine` |
| `test_admin_membership_gates.py` | `ClassEconomy` | 16 | Rename `user_id` → `teacher_user_id` |
| `test_admin_multi_tenancy.py` | `ClassEconomy` | 2 | Rename `user_id` → `teacher_user_id` |
| `test_admin_tenancy.py` | `ClassEconomy` | 4 | Rename `user_id` → `teacher_user_id` |
| (Other test files) | — | ~15 | Minor updates (model reference cleanup) |

**Total Test Impact:** ~59 tests will need updates

---

### 7.2 Test Repair Strategy

**Phase 2 (Persistence):** 
1. Create `economic-engine` table & model
2. Rename `ClassEconomy.user_id` → `teacher_user_id`
3. Rename `ClassFeature.feature_name` → `feature`
4. Add `ClassFeature.economic_version_id`, `effective_at` (optional for now)
5. Migrate data from `feature_settings` to `economic-engine`
6. **Update tests** to use new model names & tables

**Phase 3 (FEAT Migration):**
- Create FEAT layer to read from `economic-engine`
- Update routes to use FEAT instead of direct model access
- Remove `feature_settings` model & table after validation

**Phase 4+ (Policy Migration):**
- Migrate policy configuration to `policy_versions`
- Update tests to read from policy lineage instead of settings tables

---

## VIII. Design Decisions (APPROVED)

All design questions resolved per user feedback. **No further audit required.**

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| Remove `policy_versions` / `policy_transitions`? | ✅ **YES** | Economic versioning via `economic-engine` (immutable) + `class_features` timeline (append-only); policies domain-owned later |
| Move payroll/banking to generic policy tables? | ✅ **NO** | Payroll stays Policy-owned. Banking absorbed into CLASS; extract canonical config to `economic-engine`. |
| Treat Banking as Policy-owned? | ✅ **NO** | Banking configuration is CLASS-owned per Phase 0–1. Extract teacher-selected config to `economic-engine`. |
| Keep `feature_settings` temporarily? | ✅ **NO** | Drop in Phase 2. Compatibility shims defeat reconstruction. Callers must migrate to `economic-engine` + `class_features` reads. |
| Banking fields to extract? | ✅ **YES** | Per SPEC-ECON-001, extract teacher-selected behavioral choices: `interest_rate`, `interest_calculation_type`, `compound_frequency`, `interest_accrual_frequency`, `interest_payout_frequency` |
| Banking fields to BLOCK (not migrate)? | ✅ **YES** | `interest_payout_start_date` (may be derivable), `overdraft_*` fields (no SPEC support). Mark BLOCKED in legacy table pending canonical classification. |
| `UNIQUE(class_id, feature)` on `class_features`? | ✅ **NO** | Destroys append-only timeline. Use `UNIQUE(class_id, feature, effective_at)` for event-level uniqueness. |
| Use `economic_version_id` UUID auto-increment? | ✅ **NO** | Use UUID (String(36)) for portable immutable identity. Auto-increment fails for replayability. |
| Retain `class_features.id` surrogate? | ✅ **NO** | Remove it. Natural PK `(class_id, feature, effective_at)` is stronger and semantically correct. |
| Use `ON DELETE SET NULL` for economic version FK? | ✅ **NO** | Dangerous. NULL means "disabled feature"; deleting version must not fabricate disablement. Use `ON DELETE RESTRICT`. |
| Fabricate missing config values in migration? | ✅ **NO** | Use **Explicit NULL strategy**. NULL = "teacher never configured." Runtime must fail explicitly if consuming unconfigured field. |
| Keep `classes.created_by_user_id`? | ✅ **NO** | Remove. Redundant; `teacher_user_id` is sole owner. Audit/Operations layer records execution provenance. |
| Keep `classes.updated_at`? | ✅ **NO** | Remove. Generic ORM metadata; no architectural requirement. Current values are authoritative. |
| Immutable `section` column? | ✅ **NO** | `section` is mutable display metadata (like `display_name`). Only `class_timezone` is immutable (temporal interpretation depends on it). |
| Keep both `created_at` and `effective_at`? | ✅ **YES** | Distinct timestamps essential for future-law visibility: `created_at` = decision time, `effective_at` = activation time. |

### 8.2 Pre-Implementation Final Checklist

- [x] Banking configuration fields confirmed → `economic-engine`
- [x] Bootstrap strategy decided → Explicit NULL
- [x] Classes columns audited → remove `updated_at`, `created_by_user_id`; keep `created_at`
- [x] Section immutability decided → mutable (unlike timezone)
- [x] ClassFeature.id removal confirmed
- [x] Schema reviewed against DOM-CLASS-001, SPEC-ECON-001, SPEC-ECON-002
- [ ] **READY TO PROCEED TO IMPLEMENTATION**

---

## IX. Removed Tables & Blocked Columns

### 9.1 Removed Tables

**`feature_settings`** → Migrated to `economic-engine`
- Mutable singleton replaced by immutable versioning
- Drop table entirely after migration
- Do NOT create compatibility view (forces fast consumer migration)
- Callers migrate to read from `economic-engine` + `class_features` timeline

**`policy_versions` & `policy_transitions`** → Not part of CLASS Phase 2
- Out of scope (will be owned by domain-specific phases when they reconstruct)
- Leave untouched if present from earlier phases
- CLASS Phase 2 does NOT depend on them

### 9.2 Removed Columns (from `classes`)

| Column | Reason | Disposition |
|--------|--------|-------------|
| `updated_at` | Generic ORM metadata; no architectural requirement | **DROP** |
| `created_by_user_id` | Redundant; `teacher_user_id` is sole owner | **DROP** |
| `block` (synonym) | Prefer canonical `section` name | **REMOVE SYNONYM** |

### 9.3 Blocked Columns (Legacy `banking_settings` → Pending Canonical Classification)

These columns exist in legacy `banking_settings` but are **NOT migrated** to `economic-engine` in Phase 2. They remain in `banking_settings` table pending explicit canonical classification.

| Column | Status | Why Blocked |
|--------|--------|-----------|
| `interest_payout_start_date` | BLOCKED | May be derivable from `effective_at` + payout cadence; product behavior unestablished |
| `overdraft_fee_enabled` | BLOCKED | SPEC-ECON-001 has no overdraft semantics; no canonical authority yet |
| `overdraft_fee_type`, `overdraft_fee_flat_amount`, `overdraft_fee_progressive_*` | BLOCKED | Same; no SPEC authority |
| `overdraft_protection_enabled` | BLOCKED | Same |
| `savings_monthly_rate` | N/A | Derived field; delete (recompute from APY if needed) |

**Migration action:** Preserve legacy table and blocked columns unchanged. Annotate migration code documenting which fields remain unresolved. Phase 3+ must resolve before further evolution.

### 9.4 NOT Touched (Policy-Owned, Out of Scope)

**`payroll_settings`** (Policy domain owns full reconstruction; CLASS Phase 2 extracts only `expected_weekly_hours`)
- All other payroll fields remain untouched
- Policy Phase handles full payroll persistence reconstruction later

### 9.5 Architectural Constraints

**PROHIBITED:**
- Generic `policy_versions` / `policy_transitions` tables for policy lineage
- Mutable singleton settings rows
- Fabricated configuration defaults (`COALESCE(..., 5.0)`)
- Compatibility views/bridges (defeat reconstruction purpose)

**REQUIRED:**
- Immutable `economic_engine` with explicit `previous_version_id` versioning chain
- Append-only `class_features` timeline with event-level uniqueness
- Explicit NULL semantics: "not configured" rather than default fabrication
- Clear documentation of BLOCKED columns pending canonical classification

---

## X. Final Canonical Schema (Phase 2 Target)

```
classes
-------
class_id (UUID, PK)
class_public_id (UUID, UNIQUE)
join_code (String, UNIQUE)
teacher_user_id (Integer, FK users.id)
display_name (String, mutable)
section (String, mutable)
class_timezone (String, immutable)
created_at (DateTime)

economic_engine
---------------
economic_version_id (UUID, PK)
class_id (String, FK classes.class_id)
previous_version_id (UUID, FK RESTRICT, nullable)

expected_weekly_hours (Float, nullable)

interest_rate (Numeric, nullable)
interest_calculation_type (String, nullable)
compound_frequency (String, nullable)
interest_accrual_frequency (String, nullable)
interest_payout_frequency (String, nullable)

economy_policy_mode (String, required, default 'default')

created_at (DateTime)

class_features
--------------
class_id (String, FK)
feature (String)
economic_version_id (UUID, FK RESTRICT, nullable)
effective_at (DateTime)
created_at (DateTime)

PK (class_id, feature, effective_at)
```

**No surrogate ID on class_features.** Composite PK is natural and stronger.

**Unresolved Blocked Fields** (remain in legacy `banking_settings`, not migrated):
- `interest_payout_start_date`
- `overdraft_*` (all overdraft fields)

---

## XI. References

- `DOM-CLASS-001` — Class Configuration Domain (v3.2)
- `DOM-CLASS-002` — Class Economy Governance (v2.0)
- `DOM-CLASS-003` — Economic Policy (v2.1)
- `SPEC-ECON-001` — Savings Interest Accrual and Disbursement (v1.0)
- `SPEC-ECON-002` — Economic Policy Visibility and Disclosure
- `INV-CORE-000` — Core Invariants
- `INV-ARC-015` — Temporal Interpretation
- `.claude/CLAUDE.md` — Multi-tenancy and FEAT layer guidance

---

**Document Status:** Ready for review  
**Next Step:** Present to user, resolve questions 6–7, proceed to implementation
