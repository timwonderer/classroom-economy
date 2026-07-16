# Violation Remediation Plan

| Date | Authority | Trigger |
|---|---|---|
| 2026-07-16 | DOM-CORE-002 v1.6 + INV-IDEN-001 | Constitutional audit — all unauthorized model classes removed from `app/models.py` |

---

## Overview

As of 2026-07-16, all model classes for tables not authorized by DOM-CORE-002 have been removed from `app/models.py`. This intentionally breaks runtime imports to surface every illegal reference across the codebase. This document catalogs each removed model, its current code usage, and the canonical replacement path.

**Total illegal references:** 597 across 23 files  
**Migrations queued:** `6b2c3d4e5f6a` (deidentify issues, drop user_reports), `7c3d4e5f6a7b` (drop all 26 unauthorized tables)

---

## Removed Models — By Group

---

### Group A: Insurance System (4 models)

**Tables:** `insurance_policies`, `insurance_policy_blocks`, `insurance_enrollments`, `insurance_claims`  
**Prohibition:** No domain authority in DOM-CORE-002

#### `InsurancePolicy` — 50 refs in 5 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | CRUD for policy creation, editing, listing per class |
| `routes/student.py` | Policy browsing and enrollment UI |
| `feats/transaction_void_feat.py` | Check enrollment policy title during void |
| `utils/economy_rebalance.py` | Policy cost used in rebalance projection |
| `utils/economy_balance.py` | Policy premium factored into balance |

**Canonical replacement:** `policy_versions` with `domain='insurance'`. Policy content (premium, limits, rules) migrates to `policy_payload_json`. The active-projection question (is_active, current settings) maps to a future `insurance_settings` row analogous to `rent_settings`. All teacher-scoped CRUD routes rewrite against `policy_versions`.

---

#### `InsurancePolicyBlock` — 5 refs in 2 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Block-level visibility filter for policies |
| `utils/deletion.py` | Deleted on class deletion |

**Canonical replacement:** DOM-IDEN-007 prohibits block-scoped visibility tables. Block is display metadata only. If per-section policy visibility is needed it belongs as a field in `policy_payload_json`, not a separate table.

---

#### `InsuranceEnrollment` — 95 refs in 6 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Enrollment management, cancellation, payment tracking |
| `routes/student.py` | Student's active coverage display and enrollment flow |
| `services/obligations_service.py` | `enroll_student_in_policy()`, coverage state reads |
| `feats/transaction_void_feat.py` | Check active enrollment before voiding |
| `utils/student_deletion.py` | Delete enrollments on student removal |
| `utils/deletion.py` | Delete enrollments on class deletion |

**Canonical replacement:** `obligation_lifecycle` (DOM-OBL-001) tracks active obligation state for a seat. An insurance enrollment is an obligation with `obligation_type='INSURANCE_PREMIUM'`. The frozen policy snapshot fields migrate to `assessment_events.amount_snap` + `policy_payload_json` reference. All `obligations_service` methods rewrite against `assessment_events` → `obligation_lifecycle`.

---

#### `InsuranceClaim` — 95 refs in 8 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Claim review, approval, rejection |
| `routes/student.py` | Claim filing UI |
| `routes/api.py` | Claim status API |
| `routes/system_admin.py` | Claim oversight |
| `services/obligations_service.py` | `file_insurance_claim()`, `resolve_insurance_claim()` |
| `utils/student_deletion.py` | Delete claims on student removal |
| `utils/deletion.py` | Delete claims on class deletion |
| `utils/insurance_eligibility.py` | Eligibility checks against claim history |

**Canonical replacement:**
- Approved claim → `obligation_satisfaction` with `method='CLAIM_APPROVAL'` + `ledger_transaction` reference  
- Rejected claim → `obligation_reversal` with `reason='CLAIM_REJECTED'`  
- Pending claim metadata → `issues` table with `category='insurance_claim'` (teacher reviews via issue pipeline)  
- Claim history → query `obligation_satisfaction` filtered by `obligation_type='INSURANCE_PREMIUM'`

---

### Group B: Rent Derived State (4 models)

**Prohibition:** All expressed by DOM-OBL-001 satisfaction/reversal chain. Ledger is domain-blind — rent payment = `obligation_satisfaction(method=PAYMENT)` + `ledger_transaction` reference.

#### `RentPayment` — 15 refs in 7 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Payment history display, rent posting |
| `routes/student.py` | Student's rent payment history |
| `services/obligations_service.py` | `post_rent_payment()`, payment history queries |
| `routes/system_admin.py` | Rent oversight |
| `utils/student_deletion.py` | Delete on student removal |
| `utils/deletion.py` | Delete on class deletion |
| `scheduled_tasks.py` | Scheduled rent collection |

**Canonical replacement:** `obligation_satisfaction` with `method='PAYMENT'` + cross-reference to `ledger_transaction.id`. History queries filter `obligation_satisfaction` by `seat_id + class_id + obligation_type='RENT'`.

---

#### `RentWaiver` — 3 refs in 2 files

| File | Usage Pattern |
|---|---|
| `services/obligations_service.py` | `waive_rent()` |
| `utils/student_deletion.py` | Delete on student removal |

**Canonical replacement:** `obligation_satisfaction` with `method='WAIVER'`, `amount=0`, no ledger reference.

---

#### `RentItem` — 39 refs in 5 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Rent item configuration, CRUD |
| `routes/student.py` | Student rent item display |
| `routes/api.py` | Rent item API |
| `services/store_service.py` | Rent item stock/redemption |
| `utils/insurance_eligibility.py` | Item type checks |

**Canonical replacement:** `store_items` with a `category='rent'` tag + `rent_settings` for per-class rent policy. Item-level rent configuration belongs in `rent_settings.policy_payload_json` or as `store_items` with appropriate visibility.

---

#### `RentPolicyVersion` — 23 refs in 3 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Version history display, policy creation |
| `services/obligations_service.py` | Version resolution for rent assessments |
| `services/store_service.py` | Policy version lookup |

**Canonical replacement:** `policy_versions` with `domain='rent'`. The `rent_settings.active_version_id` and `next_version_id` FK columns must be repointed. `ObligationAssessment.rent_policy_version_id` must repoint to `policy_versions.id`.

---

### Group C: Legacy Identity Tables (8 models)

**Prohibition:** INV-IDEN-001 — no separate identity tables for roles.

#### `Admin` — 101 refs in 9 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Teacher profile reads (`db.get_or_404(Admin, user_id)`), TOTP, display name |
| `routes/main.py` | DB health check queries all Admin rows |
| `routes/student.py` | Teacher display name lookup |
| `routes/system_admin.py` | Teacher listing, account management |
| `routes/api.py` | Teacher auth context |
| `auth.py` | Login session validation |
| `__init__.py` | DB test health check |
| `feats/attendance.py` | Teacher context in attendance |
| `feats/base.py` | FEAT audit label |

**Canonical replacement:** `User` with `user_role=TEACHER`. All `Admin.query` → `User.query.filter_by(user_role=UserRole.TEACHER)`. TOTP secret, display name, hall_pass_verify_token, and tos fields migrate to `User` model columns (migration required). `Admin.id` references become `User.id`.

---

#### `SystemAdmin` — 7 refs in 1 file

| File | Usage Pattern |
|---|---|
| `routes/system_admin.py` | Login auth (`SystemAdmin.query.filter_by`), session management |

**Canonical replacement:** `User` with `user_role=SYSADMIN`. Login route rewrites to `User.query.filter_by(user_role=UserRole.SYSADMIN)`. TOTP secret migrates to `User.totp_secret`.

---

#### `AdminInviteCode` — 0 refs (already unused)

Dropped without replacement. Teacher signup is open (Turnstile-gated) in v2.

---

#### `UserInviteToken` / `UserRecoveryToken` — 0 refs

Both marked EXTINCT in DOM-CORE-002 §1. No code references remain.

---

### Group D: Persisted Compute Cache (1 model)

#### `PayrollCache` — 3 refs in 1 file

| File | Usage Pattern |
|---|---|
| `payroll.py` | Cache read/write around payroll calculation |

**Canonical replacement:** DOM-CORE-002 §2 explicitly prohibits persisted compute-result caches. Payroll is computed on read from authoritative event tables. The cache layer in `payroll.py` must be removed entirely — remove the read/write wrapper and call the computation function directly.

---

### Group E: Legacy Error Pipeline (2 models)

#### `ErrorLog` — 30 refs in 1 file

| File | Usage Pattern |
|---|---|
| `routes/system_admin.py` | Error log listing, detail view, search, pagination |

**Canonical replacement:** `operational_events` with `level='ERROR'` or `level='CRITICAL'` and structured JSONB `payload` containing `{request_path, error_type, stack_trace, log_output}`. The sysadmin error log UI rewrites to query `operational_events` filtered by level.

---

#### `ErrorEvent` — 20 refs in 2 files

| File | Usage Pattern |
|---|---|
| `__init__.py` | Error handler writes `ErrorEvent` rows on 500s |
| `services/tlcp.py` | TLCP snapshot includes recent error events |

**Canonical replacement:** `operational_events` with `level='ERROR'`. The `actor_public_id`, `endpoint`, `method`, `error_class`, `error_message` fields move to `payload` JSONB. `tlcp.py` rewrites its snapshot query to filter `operational_events`.

---

### Group F: Analytics / Interpretation (5 models)

#### `AnalyticsAlert` — 39 refs in 2 files

| File | Usage Pattern |
|---|---|
| `utils/analytics_engine.py` | Alert creation, threshold evaluation, acknowledge/resolve |
| `routes/analytics.py` | Alert listing, detail, status update UI |

**Canonical replacement:** `alert_events` (DOM-OPS-001) with states TRIGGERED → ACKNOWLEDGED → RESOLVED. Alert lifecycle already modeled; analytics engine rewrites to insert `alert_events` rows.

---

#### `AnalyticsSnapshot` — 35 refs in 3 files

| File | Usage Pattern |
|---|---|
| `utils/analytics_engine.py` | Snapshot creation, windowed rollup writes |
| `routes/admin.py` | Snapshot reads for dashboard analytics |
| `utils/deletion.py` | Delete on class deletion |

**Canonical replacement:** `interpretation_snapshots` (DOM-ITR-001). Snapshot content moves to `interpretation_snapshots.snapshot_payload`. Engine rewrites to write `interpretation_snapshots` rows; reads rewrite correspondingly.

---

#### `AnalyticsEvent` — 15 refs in 3 files

| File | Usage Pattern |
|---|---|
| `routes/analytics.py` | Event stream listing |
| `routes/admin.py` | Analytics event display |
| `utils/deletion.py` | Delete on class deletion |

**Canonical replacement:** `interpretation_annotations` for behavioral annotations (DOM-ITR-001) or `audit_events` for action-trail entries (DOM-OPS-001), depending on event semantics. Classify per event type during migration.

---

#### `EconomySnapshot` — 6 refs in 1 file

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Economy state snapshot reads for dashboard |

**Canonical replacement:** `interpretation_snapshots` with `snapshot_type='economy'`. Derived on read; no authoritative write path.

---

#### `IntegrityStatus` — 12 refs in 3 files

| File | Usage Pattern |
|---|---|
| `routes/main.py` | Health check endpoint reads integrity status |
| `utils/audit_verifier.py` | Writes integrity status after chain verification |
| `scheduled_tasks.py` | Scheduled integrity checks |

**Canonical replacement:** Recomputed from `chain_heads` + `audit_events`. The verifier writes a result row to `operational_events` with `domain='integrity'` and `level='INFO'` or `'ERROR'`. Health check queries most recent `operational_events` for domain='integrity'.

---

### Group G: Support (1 model)

#### `UserReport` — 24 refs in 2 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Teacher bug/feedback submission form and history |
| `routes/system_admin.py` | Sysadmin report inbox, detail view, status update |

**Canonical replacement:** `issues` table (DOM-SUP-001). Teacher submits via `create_issue()` with appropriate category. Sysadmin views/resolves via existing issue pipeline. The `help_support` route in `admin.py` rewrites to call `issue_helpers.create_issue()` and query `Issue` filtered by `actor_public_id`.

---

### Group H: Misc Unauthorized (2 models)

#### `SavedAdjustment` — 7 refs in 2 files

| File | Usage Pattern |
|---|---|
| `routes/admin.py` | Saved adjustment CRUD, apply to payroll |
| `routes/system_admin.py` | Adjustment overview |

**Canonical replacement:** `payroll_rewards` (positive) and `payroll_fines` (negative) defined in DOM-CLASS-001. The `saved_adjustments` seat-scope is a design error — rewards/fines are class-level templates, not seat-scoped. Routes rewrite to CRUD `payroll_rewards`/`payroll_fines`.

---

#### `TeacherOnboarding` — 0 direct model refs (already unused in routes)

Derived state — onboarding completion is inferrable from `class_features` + `feature_settings` presence. No replacement table needed.

---

## Remediation Priority Order

| Priority | Group | Blocking | Estimated Scope |
|---|---|---|---|
| P0 | `Admin` → `user`, `seat` (teacher) | App cannot boot | ~101 refs across 9 files + auth rewrite |
| P0 | `SystemAdmin` → `User` (sysadmin) | Sysadmin cannot log in | ~7 refs, 1 file |
| P1 | `UserReport` → `Issue` | Support broken | ~24 refs, 2 files |
| P1 | `ErrorLog` → `operational_events` | Error visibility lost | ~30 refs, 1 file |
| P1 | `PayrollCache` removal | Payroll errors | ~3 refs, 1 file |
| P2 | Insurance → obligation domain | Feature broken | ~245 refs, 8 files |
| P2 | Rent derived → obligation domain | Feature broken | ~80 refs, 7 files |
| P3 | Analytics → ITR/OPS tables | Analytics broken | ~100 refs, 4 files |
| P3 | `ErrorEvent` → `operational_events` | TLCP incomplete | ~20 refs, 2 files |
| P4 | `SavedAdjustment` → payroll presets | Minor feature | ~7 refs, 2 files |

---

## Files With Zero Illegal References (already clean)

- `app/models.py` ✅
- `app/services/context_resolver.py` ✅
- `app/services/ledger_service.py` ✅
- `app/services/identity_service.py` ✅
- `app/feats/base.py` — 2 refs (`Admin` in FEAT registry label strings only, not model usage) — low risk

---

*Generated 2026-07-16 from DOM-CORE-002 v1.6 constitutional audit.*
