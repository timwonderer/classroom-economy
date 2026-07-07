# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.


## [Unreleased]

### Changed
- **Admin class-delete helper boundary renamed to `owner_user_id`** — The class-delete helper now uses owner-user naming for its boundary and announcement purge, matching the rest of the admin cleanup. This is a focused cleanup slice; behavior remains unchanged.
- **Admin hard-delete account scope renamed to `owner_user_id`** — The admin account-deletion fan-out now names its owner boundary as `owner_user_id` and threads that naming through the class-deletion cascade. This is a focused cleanup slice; behavior remains unchanged.
- **Admin deletion-helper owner boundary renamed to `owner_user_id`** — The admin cleanup helpers now use owner-user naming for the deletion block instead of `teacher_id`, and the associated comments were tightened to match. This is a focused cleanup slice; behavior remains unchanged.
- **Admin issue-resolution wording and seed-script shadow rows removed** — The admin issue workflow now uses owner/admin wording in its local boundary names and messages without changing the FEAT/status contract, and `scripts/seed_canonical_v2.py` now seeds directly from `User`, `Seat`, and `IdentityProfile` instead of writing legacy shadow rows. This is a focused cleanup slice; behavior remains unchanged.
- **System-admin announcement and escalated-issue labels moved further toward owner-admin naming** — The system-admin announcement display and form copy now use owner-admin language, and the escalated-issue docstrings were tightened to match the canonical owner-user framing. This is a small cleanup slice; behavior is unchanged.
- **System-admin delete-admin reason string aligned to owner-user wording** — The delete-admin universe-collapse reason string now says owner-user instead of teacher, matching the canonical ownership language used elsewhere in the cleanup.
- **System-admin bug-reward bookkeeping boundary made explicit** — The system-admin issue-resolution flow now names the issue owner explicitly as `issue_owner_user_id` before issuing the bug-reward transaction. This keeps the reward path aligned with the canonical owner-user naming.
- **System-admin delete-admin boundary aligned to `owner_user`** — The system-admin delete-admin flow now names its resolved canonical account as `owner_user`, matching the owner-user terminology used elsewhere in the cleanup.
- **System-admin TOTP reset endpoint renamed** — The system-admin TOTP reset route helper is now named `reset_admin_totp`, matching the actual actor type that the route handles.
- **System-admin issue-resolution boundary made consistent** — The system-admin issue-resolution flow now uses `sysadmin_user_id` consistently for its record-status bookkeeping. This is a small runtime cleanup that removes the last local variable mismatch in the flow.
- **System-admin overview and issue-resolution boundaries aligned to canonical user naming** — The system-admin teacher-overview aggregation maps now use owner-user naming, and the issue-resolution flow now uses `sysadmin_user_id` internally. This keeps the system-admin surface moving toward the same canonical naming as the rest of the cleanup.
- **System-admin announcement create boundary aligned to `sysadmin_user_id`** — The system-admin announcement create flow now uses canonical user naming internally for the system admin actor while leaving the audience semantics unchanged.
- **Admin public student-detail route aligned to owner-user naming** — The public student-detail admin route now threads `owner_user_id` through its class-scoped reads instead of a teacher-shaped local name. Behavior is unchanged; the route now matches the canonical ownership language used elsewhere in the cleanup.
- **Redemption disposition FEAT actor boundary aligned to `actor_user_id`** — The redemption disposition FEAT now names its actor boundary explicitly as an owner-user identifier while keeping the underlying ledger write shape intact. This keeps the store approval/rejection path internally aligned with the rest of the canonical runtime naming.
- **Admin rent/store helpers aligned to owner-user naming** — The rent-to-store sync helper and the insurance tier namespace helper now use owner-user naming, and the stale internal callsite was rewired. This keeps the remaining admin-side provisioning path consistent with the canonical runtime ownership model.
- **Admin student-seat provisioning helper aligned to owner-user naming** — The admin helper that ensures the shadow student seat now uses owner-user naming, and the remaining internal callsites were rewired to the renamed helper. This keeps the admin class provisioning path consistent with the canonical ownership model.
- **Transfer and admin-adjustment FEAT boundaries aligned to `user_id`** — The account-transfer FEAT and admin-adjustment FEAT now name the owner-user boundary explicitly where they already operate on canonical user ownership. The ledger calls still pass `teacher_id` into legacy-shaped service APIs, but the FEAT layer itself now speaks the same runtime language as the rest of the cleanup.
- **Admin helper boundaries aligned to owner-user naming** — The top-of-file admin class-anchoring helpers now use `user_id` naming for class resolution and feature-settings lookup, matching the canonical owner-user boundary used elsewhere in the runtime.
- **API helper boundaries aligned to owner-user naming** — `app/routes/api.py` now uses owner-user naming for the redemption audit and hall-pass helper boundaries while preserving the existing outward payload shapes. This is a runtime-only cleanup that keeps the canonical class-owner model moving through the remaining API surface.
- **Economy-balance boundary aligned to `user_id`** — The economy balance checker now takes `user_id` instead of `teacher_id`, and the scheduled rent-cycle FEAT now uses owner-user naming at the boundary. This keeps the remaining class-scope helpers aligned with the canonical runtime ownership model.
- **Economy-policy helper boundary renamed** — Class-scope policy helpers now speak `user_id` instead of `teacher_id`, matching the canonical runtime actor boundary that was already active in scope resolution and student rent processing. The app startup check remained clean after the signature rename.
- **Identity cleanup checkpointed** — Removed the remaining bridge-service surface from the active admin/recovery identity paths, shifted the runtime access boundary from `Scope.teacher_id` to `Scope.user_id`, and reconciled the context-resolver tests to the current canonical session contract. The tracker docs were updated with the latest verified slice, and startup stayed clean under focused validation.
- **Wave 8 store domain cutover** — Canonical store tables `store_purchases`, `redemption_events`, and `store_item_visibility` replace `student_items`, `store_item_blocks`, and `redemption_audit_logs` as the store domain authority. DOM-STORE-001 v2.0 aligned with DOM-CORE-002. Migration `0009_store_domain.py` creates the canonical tables. `store_service.py` and `store_purchase_feat.py` rewritten to v2-only execution with no legacy fallback. Schema and behavioral tests in `tests/domain/test_store.py`. (#1244+)

- **Wave 7 closeout completed for the insurance obligations slice** — legacy `StudentInsurance` runtime usage was removed, all insurance runtime paths now use `InsuranceEnrollment`, and the focused insurance/decimal regressions were rewritten to the v2 seat-based architecture. The remaining table-drop cleanup is tracked separately and no longer blocks the Wave 7 exit gate.
- **Wave 7 admin rent read surfaces moved further onto canonical obligations** — the admin rent privilege cache and cycle reversal flow now read paid rent state from `obligations_service.get_paid_rent_assessments_for_cycle(...)` rather than direct `RentPayment` queries. The remaining legacy report/deletion surfaces are now isolated to non-1:1 maintenance paths.
- **Wave 7 student rent read path moved to canonical obligations helpers** — `student.rent` now renders payment status and history from `obligations_service.get_paid_rent_assessments_for_cycle(...)` and `get_rent_payment_history(...)` instead of reading `RentPayment` rows directly. The live rent route now stays on the v2 assessment/lifecycle model end-to-end.
- **Canonical auth hydration now fails closed only after seat-aware recovery** — Student login first validates persisted `last_active_class_id`, then falls back to explicit class selection when one or more valid class/seat options exist. If no valid option exists, the login flow now logs an invariant violation and returns the generic role-appropriate recovery message instead of treating missing persisted selection as a terminal session error.
- **Tuple-only runtime cutover checkpointed** — Admin, recovery, analytics, attendance, deletion, and shared seat-scope helpers now operate on canonical `User`/`Seat`/`class_id` boundaries instead of reconstructing runtime identity from `StudentTeacher` or `Seat.student_id`. The remaining migration work is test-corpus cleanup and `canonicalContextFactory` adoption.
- **Wave 7 / P0 remediation session** — Created `codex/wave7-closure-p0-remediation`, rewrote the v2 authority guardrail tests to assert canonical source-level behavior, and wrapped the touched dead-route mutation entrypoints in FEAT ownership (`admin.process_claim`, `admin.passkey_auth_finish`, `admin.resolve_issue`, `sysadmin.resolve_escalated_issue`). Focused validation: `pytest -q tests/test_v2_authority_guardrails.py -q`. Added regression coverage that pins those route surfaces to FEAT ownership and keeps the read-only admin GET guardrail source-checked.
- **Wave 6 attendance cutover completed** — Legacy `TapEvent` runtime usage has been removed in favor of canonical `AttendanceSession` + `SeatAttendanceState` flows. The Wave 6 migration chain now drops `tap_events`, the downgrade path recreates the retired schema shape for rehearsal, and attendance/admin/student/deletion paths all operate on canonical attendance tables.
- **Wave 6 authoritative docs aligned with runtime truth** — Updated the active migration tracker, attendance domain docs, schema ownership/index pages, recovery doc, README, and developer vocabulary so live documentation reflects that `tap_events` is retired and Wave 6 is complete.
- **Wave 7 rent-waiver actor cutover completed** — `ObligationReversal` now uses seat-scoped actor attribution (`reversed_by_seat_id`) instead of the legacy nullable user FK. Rent-waiver add/remove flows no longer emit legacy `AnalyticsEvent` compatibility rows; the follow-up analytics event will return only after the analytics schema is seat-scoped.
- **README rewritten for v2 architecture** — Corrected platform framing (classroom management tool, not financial literacy), updated key models table to reflect `Seat`/`IdentityProfile`/`ClassEconomy`, removed stale v1 references
- **Wave 11 bulk test refactoring: TeacherBlock→Seat** — ~60 test files migrated from `TeacherBlock` fixtures to canonical `Seat` + `IdentityProfile` + `ClassEconomy` constructs. Deleted `tests/helpers/mock_teacher_block.py` shim. 7 legacy-only test modules marked skipped for decommissioning. TeacherBlock test surface reduced from 71 to 27 files (62% reduction). (#1220)
- **Default branch switched to `codex/v2.0`** — CI workflows (actionlint, check-migrations, policy-guardrails) now trigger on `codex/v2.0` instead of `main`. Deploy to DigitalOcean workflow intentionally remains on `main` only.
- **Documentation reorganized for v2 canonical structure** — v2 restructure docs promoted from `docs/development/v2_restructure_doc/` to top-level canonical directories: `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/INVARIANT/`, `docs/MAP/`, `docs/TESTING/`. Development specs and tracking promoted to `docs/SPECS/` and `docs/TRACKING/`. All internal cross-references updated across 47 files.
- **v1 docs archived** — User guides moved to `docs/archive/v1-user-guides/`, GitHub Pages landing assets to `docs/archive/github-pages/`, superseded development artifacts to `docs/archive/v1-development/`.
- **Root-level cleanup** — Removed 24 scratch/debug/temp files (fix_*.py, debug_*.py, pytest output dumps, ephemeral assessment reports). Moved `student_upload_template.csv` to `app/data/`. Removed duplicate `app/data/random-words.txt`.

### Added
- **REFERENCE vocabulary standards** — `docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md` (normative developer terms) and `REF-TERM-002_USER_VOCABULARY.md` (normative user-facing terms) establish canonical v2 terminology with explicit deprecated-term mappings
- **Terminology audit** — `docs/TRACKING/TERMINOLOGY_AUDIT_V1.md` inventories 177 terms across the codebase with frequency analysis and v1→v2 migration status
- **Wave 7 canonical insurance-claim lifecycle coverage** —
  `tests/test_insurance_snapshots.py::test_admin_claim_approval_uses_frozen_claim_cap`
  now asserts that the live admin approval path emits canonical
  `assessment_events`, `obligation_lifecycle`, and `obligation_satisfaction`
  rows in addition to the reimbursement ledger entry.
- **`FEAT-STOR-006` (Redemption Disposition) FEAT** — registered in the canonical
  registry and implemented in `app/feats/redemption_disposition_feat.py`.
  Exposes `execute_redemption_approval(...)` and `execute_redemption_rejection(...)`,
  both `@requires_feat_context("FEAT-STOR-006")`-guarded. The FEAT is named for
  the business action so the Wave 8 `StudentItem` → `StorePurchase` +
  `RedemptionEvent` split will change the FEAT's internals without changing
  its contract.
- **Enforcement-active redemption tests** —
  `tests/test_redemption_disposition_feat.py` adds 5 tests under
  `@pytest.mark.enforce_feat`, exercising the redemption routes with the
  global `FEATBypass` opted out. `FEATBypass` is used only inside
  fixture-setup blocks, not around route calls. These tests would have
  caught the dead-route bug surfaced in the audit; they now lock the fix in.
- **`V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md`** —
  `docs/TRACKING/V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md` documents
  the audit findings, methodology note, and 5-phase plan for inverting the
  conftest FEAT-enforcement default so that production-shaped enforcement is
  the default in CI and bypass is explicit per-test. Master tracker updated
  to reference the plan under Wave 11 post-launch hardening.
- **Phase 1 (instrumentation) of the FEATBypass default-flip plan landed.**
  New pytest plugin `tests/_feat_bypass_audit.py` opts in via
  `FEAT_BYPASS_AUDIT=1` and hooks SQLAlchemy `before_flush` to record every
  flush that occurs while `FEATBypass` is the only thing keeping the
  constitution quiet. The dispatch discriminator uses the call stack
  (Flask's `wsgi_app`/`full_dispatch_request`/`dispatch_request`/
  `preprocess_request` frames) rather than `has_request_context()`, because
  pytest-flask leaves a dangling context around fixture code.
  `scripts/regenerate_feat_bypass_report.py` re-emits the markdown from the
  raw JSON without a fresh suite run. Findings written to
  `docs/TRACKING/V2_FEAT_BYPASS_DEPENDENCY_REPORT.md`:
  **4 unique mutating endpoints are dead in production**
  (`admin.process_claim`, `sysadmin.resolve_escalated_issue`,
  `admin.rent_settings`, `admin.passkey_auth_finish`), far below the
  pre-instrumentation ceiling of ~78. **Zero GET-side-effect bypass-hidden
  flushes** (INV-ARC-007 largely respected). 585 of 590 observed tests
  have fixture-only bypass dependency, concentrated on
  `tests/helpers/class_scope.py:create_class_scope` (~587 flushes). The
  raw JSON output is gitignored (it's regenerated by re-running the
  audited suite); the markdown report is the durable artifact.

### Changed
- **TeacherBlock test fallout reduced after the landed table drop** —
  `tests/test_feature_settings.py` and `tests/test_admin_membership_gates.py`
  now assert canonical `Seat` / `ClassEconomy` behavior directly instead of
  querying the removed `TeacherBlock` authority surface. Legacy add-student
  assertions that still depend on pre-v2 shadow-seat semantics are now
  explicitly skipped pending a canonical rewrite, rather than silently
  preserving `TeacherBlock`-era expectations.
- **Wave 8 obligation identity canonicalization** — all obligation domain
  identity references now use canonical v2 identifiers (`user_id`, `seat_id`,
  `enrollment_id`) exclusively. Migration `0008` renames
  `obligation_reversal.reversed_by_teacher_id` → `reversed_by_user_id` (FK →
  `users.id`), `insurance_claims.processed_by_teacher_id` →
  `processed_by_user_id` (FK → `users.id`), `insurance_claims.student_insurance_id`
  → `enrollment_id` (FK repointed from `student_insurance` to
  `insurance_enrollments`), and drops `insurance_claims.student_id`. FEAT layer
  and admin routes updated to pass `user_id` instead of `teacher_id`/`admin_id`.
  All 23 insurance/obligation tests pass with canonical fixtures.
- **Wave 7 insurance-claim resolution now dual-writes canonical obligation
  state** — `app/services/obligations_service.py` now emits
  canonical claim assessments using deterministic idempotency keys
  (`insurance-claim:{claim_id}`), advances `obligation_lifecycle` to `PAID`
  or `REVERSED` on claim resolution, and records `obligation_satisfaction`
  or `obligation_reversal` rows under the clean-cutover model.
- **Wave 7 rent-waiver analytics compatibility write removed** — `admin.add_rent_waiver` and `admin.remove_rent_waiver` no longer emit legacy `AnalyticsEvent` rows for waiver actions. The route now keeps waiver state canonical and leaves analytics reintroduction for a later seat-scoped schema pass.
- **`/api/approve-redemption` and `/api/reject-redemption` now route through
  `FEAT-STOR-006`** — both routes were dead in production runtime prior to
  this change: they performed `db.session.add(RedemptionAuditLog(...))` and
  mutated `StudentItem.status` without a `@feat_shell` decorator, so the
  `before_flush` constitutional enforcement raised `FEATContextError` and
  returned HTTP 500 with zero rows persisting. The breakage was invisible to
  CI because `tests/conftest.py` wraps every test in `FEATBypass`. Both
  routes now wear `@feat_shell("FEAT-STOR-006")`, delegate all mutation to
  the new FEAT module, and narrow their exception handling to
  `RedemptionDispositionError` (mapped to HTTP 409). Infrastructure errors
  propagate to the FEAT shell for rollback rather than being swallowed.
- **Cross-FEAT `Transaction` UPDATE enforcement corrected
  (`app/models.py:_enforce_transaction_integrity`)** — the "Mixed correlation
  in flush" check was firing on UPDATE as well as INSERT, making it
  impossible for any FEAT to mutate a `Transaction` created by a prior FEAT
  (refunds, voids, `reversal_transaction_id` linkage). Real production paths
  were affected. The bug was hidden because every test ran under a single
  `FEATBypass` correlation. The check is now gated on
  `_target_state.transient or pending` so it fires only on INSERT; on UPDATE
  the row's `correlation_id` is preserved as historical lineage and the
  active FEAT's identity is captured via `feat_code` (which is unconditionally
  set on both insert and update).
- **Wave 7 obligations schema contract corrected** — Added forward migration
  `0007` to create and backfill canonical `assessment_events` and
  `obligation_lifecycle`, repoint satisfaction/reversal/entitlement foreign
  keys, and preserve downgrade data in the transitional `0006` table. Runtime
  rent and insurance enrollment writes now emit canonical assessment and
  lifecycle state while legacy tables remain available for the later read
  cutover and parity validation.
- **Closed the next post-Wave 4 authority-reduction slices** — TLCP actor
  correlation now derives student/teacher `actor_public_id` from the active
  seat context instead of reconstructing it from legacy `student_id` or
  `admin_id`. Sysadmin auth probes and passkey-management endpoints now trust
  canonical resolver identity rather than raw `sysadmin_id` session checks.
  Payroll route entry, settings writes, and disabled-scope gating now resolve
  canonical admin identity first and use class-scoped seat data instead of
  `TeacherBlock.teacher_id` as the primary runtime authority.
- **Completed-surface feature gating now prefers canonical `class_id` helpers** —
  `app/utils/economy_policy.py` now exposes explicit
  `resolve_feature_class_for_class()` and
  `get_class_feature_settings_for_class()` helpers for class-authoritative
  feature reads. Active admin, student, API hall-pass, and attendance policy
  callers in already-completed Wave 4 surfaces now resolve feature enablement
  from `class_id` first instead of rebuilding scope from
  `teacher_id + block/join_code`. Focused regressions cover class-scoped helper
  behavior, admin join-code option discovery without `TeacherBlock` authority,
  insurance management feature gating from the active class, fail-closed
  handling for unknown class IDs, and canonical user/seat contexts in feature
  enforcement tests. The hall-pass legacy-scope migration now safely handles a
  missing table and restores its teacher foreign key on downgrade.
- **Wave 4 class-configuration canonicalization completed** — The active class
  configuration tables now align on `class_id` as the runtime and schema
  boundary: `class_features`, `feature_settings`, `hall_pass_settings`,
  `banking_settings`, `payroll_settings`, `payroll_cache`, and `rent_settings`
  no longer carry live `teacher_id` / `join_code` scope columns, and all seven
  now require non-null `class_id` in the database. This closes the legacy
  settings-column retirement lane for Wave 4.
- **PayrollSettings and PayrollCache moved further into canonical Wave 4 scope** —
  `payroll_settings` now treats `class_id + block` as its only runtime authority,
  and `payroll_cache` is now class-owned only. The model, payroll cache writer,
  payroll settings admin writes, and class-deletion cleanup path no longer depend
  on legacy `teacher_id` / `join_code` scope fields. Migration
  `2a4f6c8d0e21` drops those legacy columns from `payroll_settings` and
  `payroll_cache`, including dependent payroll-settings RLS policy cleanup.
  Focused payroll helper, cache, shared-student, and admin route tests were
  updated to assert class-scoped behavior directly.
- **BankingSettings moved further into canonical Wave 4 scope** — `banking_settings`
  now treats `class_id + block` as the runtime authority contract. The model and
  admin banking settings write path no longer create or depend on legacy
  `teacher_id` / `join_code` scope fields, and migration `1f6c2b8d4e90` drops
  those columns from the schema. Focused banking helper and admin route tests were
  updated to assert class-scoped behavior directly.
- **Canonical auth and roster-provisioning docs aligned** — Updated active v2
  identity, recovery, lifecycle, schema, session, README, and development docs so
  `User` owns authentication/recovery/passkey capability, `Seat` owns class-local
  actor authority and claim hashes, `IdentityProfile` remains display-only, and
  roster upload is documented as provisioning an inactive participant position
  rather than creating a student. Added `V2_CANONICAL_AUTH_RUNTIME_CUTOVER.md` to
  separate current bridge implementation facts from constitutional target docs, then
  updated the active migration tracker, development docs index, authority extraction
  plan, and Wave 3 risk doc to stop presenting pre-cutover v1 auth as current
  runtime guidance. Refreshed active teacher/student user guides that still described
  DOB-based claim or recovery flows.
- **Canonical identity foundation schema added** — Expanded `users` with unified
  auth, credential, session, role, and last-active-seat fields; added seat-owned
  claim verification hashes; made `identity_profiles` seat-bindable; and completed
  lifecycle fields for `user_invite_tokens` and `user_recovery_tokens`. Migration
  `a6d9c2e4f1b7` is additive and intentionally does not infer canonical bindings
  from deprecated `Student`, `Admin`, `TeacherBlock`, or class teacher ownership.
- **Fresh canonical database rebuild path repaired** — Hardened squash-era
  migrations that assumed historical `classes`, `transaction`, `users.username`,
  or `users.last_active_class_id` shapes even though `0001_bootstrap.py` creates
  live runtime metadata. The canonical seed no longer calls `db.create_all()` and
  now provisions canonical user, seat, seat-bound profile, and unclaimed-seat
  claim state before adding explicit legacy compatibility shadows.
- **Canonical identity principal backfill added** — Migration `b7e4c1d9a2f6`
  deterministically migrates credentialed legacy principals into `users`,
  normalizes existing bound-seat claim state, creates teacher seats for
  credentialed teachers' classes, and binds student display profiles to seats.
  The migration fails on username, role, or seat-binding ambiguity and does not
  derive authority from `TeacherBlock`. Successful login sessions now populate
  canonical `user_id` when a migrated user exists, and deprecated user-session
  aliases are no longer read or written.
- **Canonical User credential login activated for TOTP and PIN flows** — Teacher,
  student, and system-admin login now resolve and verify credentials from `users`
  before resolving deprecated principal rows as route compatibility shadows.
  Student claim/setup, teacher signup/reset, system-admin provisioning, and
  student recovery now keep canonical credentials synchronized; legacy-only
  principals and missing canonical recovery identities fail closed. Passkey
  external IDs remain a separate legacy-backed cutover.
- **Passkey credential ownership moved to canonical users** — Added migration
  `c8f1e2d3a4b5` to store canonical `user_id` owners on teacher and system-admin
  passkey metadata, backfill existing credentials, and fail closed on unmapped
  rows. Passwordless registration/authentication now uses `user_<User.id>`
  external IDs; legacy `admin_<id>` and `sysadmin_<id>` passkey principals are
  rejected.
- **Auth resolvers now require canonical user identity** — `get_current_admin()`,
  `get_current_system_admin()`, and `get_logged_in_student()` now resolve the
  canonical `User` first and only then hydrate deprecated `Admin`, `SystemAdmin`,
  or `Student` route shadows. Raw legacy session IDs alone no longer establish
  resolver identity.
- **Ledger Identity Severance Completed (Wave 5 / Phase 1C)** — Formally decommissioned `student_id` from the canonical ledger tables (`ledger_transaction` and `ledger_balance_snapshot`). All balances and financial histories are now strictly derived via `seat_id` + `class_id` joints. `Student.transactions` backrefs were replaced with explicit seat-proxied properties. `db.session.in_nested_transaction` support was formalized in the FEAT orchestrator to allow savepoints within top-level atomic feats without violating authority isolation.
- **Support issue actor reference now uses canonical public actor naming** — Support
  issue rows now expose the filing seat's UUID `Seat.public_id` as
  `issues.actor_public_id`, matching the same actor-public identity language as TLCP.
- **TLCP support correlation now uses seat public IDs at runtime** — Request traces,
  error events, support-ticket correlation packs, and student recent-error prompts now
  use the active class-scoped `Seat.public_id` value instead of generating a separate
  student-wide actor marker. Physical TLCP columns, indexes, log labels, tests, and
  sysadmin copy affordances now use `actor_public_id`.
- **Class-scoped teacher public lookups now use teacher-seat UUIDs** — New class anchors provision a teacher `Seat`, `/api/hall-pass/verification/active` now requires one explicit `class_id` plus that teacher seat's UUID `public_id`, and the obsolete `/student/switch-teacher/<teacher_public_id>` route now returns `404`. Hall-pass pass-type lookup rejects `teacher_public_id` input, and explicit invalid `join_code` aliases now fail closed instead of falling back to another claimed seat.
- **Seat public identity formalized as one UUID family** — Added the normative v2 identity ownership model: `users.id` authenticates, `seats.id` acts, `classes.class_id` scopes, and UUID-encoded `seats.public_id` is the single deidentified public actor identifier for both teacher and student seats. Role-specific public-ID fields and separate TLCP actor identity families are now classified as invalid v2 residue rather than supported identity alternatives.
- **Class-period metadata is being formalized as `section` on `classes`** — The v2 architecture docs now explicitly define `section` as the canonical metadata field for labels such as `2`, `Block A`, and `Period 1`, while `display_name` remains the human-facing class title such as `Honors Chemistry`. Remaining `block` fields are transitional naming debt and should not be treated as canonical identity or authority.
- **Teacher student-detail URLs now expose class-local seat public IDs only** — Numeric `/admin/students/<student_id>` detail URLs now return `404`. Teacher-facing student-detail links use signed, short-lived navigation URLs carrying `seats.public_id`, and route resolution requires the seat public ID, signed token class, teacher ownership, and active `current_class_id` to identify the same seat. This prevents cross-class seat selection for shared students, including when one teacher owns both classes.
- **Class-scoped feature authority and disabled-route behavior tightened** — Admin feature pages now enforce class-scoped feature toggles as the sole authority and render a dedicated disabled page with a direct link to feature settings; student feature-gated routes now return hard `404` when disabled. Feature settings UI is now per-period only.
- **Runtime settings normalization toward `class_id` authority** — Payroll, analytics, student banking settings, rebalance activation, and admin settings cleanup paths were updated to resolve class scope and query settings rows by `class_id`, reducing reliance on teacher/global settings reads in active runtime paths.
- **Class-scoped test fixtures aligned with clean-break semantics** — Rent waiver tests now seed canonical `RentSettings` scope (`class_id` + `join_code`) to match runtime authority.
- **Wave 2 bootstrap migration squash started** - Archived 196 legacy Alembic revisions into `migrations/archive/v1_196_migrations/`, introduced `migrations/versions/0001_bootstrap.py` as the new baseline head (`down_revision = None`) to idempotently co-create legacy and canonical tables, and added `scripts/verify_migration_squash.py` to assert head/table expectations.
- **V2 money authority model closed** — Student, admin, sysadmin, and redemption money paths now funnel through FEAT/domain services into `ledger_service`, with `Transaction(` construction restricted to `app/services/ledger_service.py` and enforced by structural guardrails.
- **Admin-side authority extraction completed for money workflows** — Payroll runs, manual payroll adjustments, bonus/fine flows, insurance claim reimbursement, transaction void, and bug-reward issuance no longer create money rows inline in route handlers.
- **Transfer zero-sum invariant is now explicit** — Added a class-scoped critical smoke test proving canonical transfer pairs net to zero within a `join_code` boundary and remain isolated from transfer activity in other class scopes.
- **District assurance brief page and trust-link rollout** — Added the district-facing `/district-assurance` page and linked it from privacy and authentication-related templates so the v2 branch exposes the current data-protection summary across key entry points.
- **Foundational v2 architecture corpus expanded** — Added execution-model, core-invariant, and capability-architecture foundation documents plus parked realignment drafts so the branch carries a clearer written baseline for the ongoing rebuild.
- **Architecture invariants now capture rebuild intent and downstream consequences** — Expanded each v2 architecture invariant with explicit "Rebuild Intent" and "Downstream Consequence" sections to formalize which migration constraints future work must preserve.
- **Collective goal reactivation strict scoping** — Added deterministic UUID-based instance mapping for collective goals using `collective_goal_instance_code` across `StoreItem` and `StudentItem` ensuring robust reactivation progress tracking preventing bleed across past purchase states. Replaced lazy overlaps with direct DB inner join references.
- **v2 launch-readiness checklist reconciled with current docs state** — Updated the readiness matrix, launch project checklist, reconciliation tracker, README, and documentation SOP references so branch-local launch planning stays aligned with the latest branch status.
- **v2.0 launch-readiness and rehearsal documentation finalized** — Refreshed the v2 tracking artifacts, rehearsal checklist, and final live-test report so `codex/v2.0` reflects the current branch state, readiness blockers, and production transition guidance.
- **Class-scoped admin and student onboarding workflow expansion** — Added join-code and class-ID aware admin context handling for student addition, store management, and rent item sync, then extended student claiming and class-membership flows to preserve class scope during teacher-managed onboarding.
- **Attendance, migration validation, and test date handling tightened** — Aligned attendance calculations and tests around timezone-consistent date handling, expanded migration upgrade/downgrade validation checks, and updated attendance status handling to recognize the "done for the day" completion path.
- **v2.0 live-test candidate documentation refresh** - Updated the living engineering docs to reflect the consolidated v2 branch, current PostgreSQL test evidence (`708 passed, 1 skipped`), resolved migration heads, and the v2 authority model where `ClassEconomy` and `ClassMembership` define class scope. Added explicit live-test and production transition runbooks, refreshed architecture/API/schema references, and updated user guides that previously implied numeric teacher IDs, teacher-global class behavior, or legacy fallback semantics.
- **ClassEconomy and ClassMembership data-integrity hardening** — Added SQLAlchemy `Enum` types for `ClassEconomy.status` (active, archived), `ClassMembership.role` (admin, student), and `ClassMembership.status` (active, archived). Aligned the membership XOR check constraint name with existing DB constraints and added migration `a11213ca4afb` to normalize invalid values and enforce strict DB check constraints for class economy status, membership status, and membership role consistency. (Addresses PR #1078 review comments)

### Fixed
- **Test database reset stability for v2 Postgres runs** — Improved the test reset path by disposing pooled connections before rebuilding the database state, reducing failures caused by lingering connections during repeated v2 test runs.
- **DB-level student ownership invariant enforcement** — Added migration `1adc6456ab0e` with deferrable PostgreSQL constraint triggers that reject commits where any `students` row exists without at least one `student_teachers` link. This hardens the "no global/orphan student state" rule at the database layer during join-code/class deletion workflows.
- **Student account claim failure when teachers upload roster with same name twice** — Fixed `_sync_identity_profile()` which was skipping `IdentityProfile` creation when `first_name` or `last_initial` was empty, leaving `identity_id` as NULL. This caused `TeacherBlock` inserts to fail with a NOT NULL constraint violation. Now uses placeholder values `"[Unknown]"` and `"?"` if identity fields are missing, ensuring the profile is always created. By-product: When multiple roster uploads or manual adds target the same student, the claim flow now handles partial-state records gracefully. Cleaned up one limbo student (Student#2) that was linked to multiple unclaimed seats due to duplicate add attempts.
- **Test: Removed false positive assertion for non-existent sysadmin teacher deletion** — The test `test_manage_teachers_hides_delete_actions` was asserting that "Teacher-managed" text appears in the sysadmin manage-teachers template, but this text doesn't exist. The assertion was removed since the actual intent of the test (verifying delete URLs are NOT present) is already correctly validated.
- **Foreign key violation when adding individual students** — Fixed `IntegrityError` in `add_individual_student` and `_link_student_to_admin` where `TeacherBlock` records were created without first ensuring the parent `ClassEconomy` record exists. Both functions now call `_ensure_join_code_anchors` before creating `TeacherBlock` records to satisfy the `fk_teacher_blocks_join_code_class_economies` foreign key constraint.
- **Rent validation recommendation mismatch for block-scoped API checks** — Updated `EconomyBalanceChecker.validate_rent_value()` so block-scoped rent validation uses AGENTS monthly multipliers (`2.0x-2.5x`, default `2.25x`) while global validation continues to honor policy-mode weekly burden conversion. This resolves incorrect minimum recommendations (for example `$733.76` instead of `$562.50`) in `/admin/api/economy/validate/rent` for class-selected flows.
- **Pre-merge fix: Missing ClassEconomy and ClassMembership models** — Added `ClassEconomy` and `ClassMembership` SQLAlchemy models to `app/models.py` to match the `class_economies` and `class_memberships` tables created in prior migrations. These models were referenced in `app/utils/deletion.py`, multiple test files, and `tmp_admin.py` but were absent from the model layer, causing `ImportError` at startup.
- **Pre-merge fix: Stale `admin_id` column name in test fixtures** — Updated 58 test files (121 occurrences) to use `teacher_id` instead of `admin_id` when constructing or querying `StudentTeacher`, `DeletionRequest`, and `RecoveryRequest` records, after migration `c4e1a2b3d4f6` renamed those columns.
- **Economy analytics/report class-scoping hardening** — Removed teacher-global fallback behavior for selected-class analytics windows and economy API checks. `analytics.py`, `analytics_engine.py`, and admin economy APIs now resolve class settings with join-code-first precedence (join-code scoped rows first, then legacy block-scoped compatibility rows), instead of falling through to `block=None` teacher-global rows during class-selected flows.
- **Join-code strict scoping for hall-pass availability** — `/api/hall-pass/available-types` now supports `join_code` and `teacher_public_id` identity inputs and enforces active class scope for student sessions; legacy numeric `teacher_id` fallback was removed.
- **Join-code strict scoping for student settings lookups** — Student banking/rent/feature settings resolution now uses current class context (`teacher_id` + `join_code`, block-preferred) across transfer, interest, insurance purchase, shop rent checks, and rent payment flows. Direct teacher-only settings queries were removed from these routes.
- **Legacy numeric student teacher-switch route disabled** — `/student/switch-period/<int:teacher_id>` no longer mutates class context; students are redirected to use join-code/public-id based class switching only.
- **Broken help/guide links after doc system revamp** — Updated all doc path references in `layout_admin.html`, `layout_student.html`, `admin_insurance.html`, `admin_store.html`, and `admin_payroll.html` from hyphenated paths (e.g., `teacher-students`) to the new slash-separated directory structure (e.g., `teacher/students`).
- **Passkey "Never used" always displayed** — Passkeys are tracked in our database without a `credential_id` (credentials are managed on the Passwordless.dev servers). The auth-finish handler was looking up credentials by `credential_id` (which is always `NULL`), so `last_used` was never updated. Fixed by updating `last_used` on all credentials for the authenticated admin/sysadmin when a successful passkey sign-in occurs.
- **Rent coverage month label off by one for end-of-month due dates** — The coverage month label was computed by building a datetime for the due date and adding 1 day, which caused due dates on the last day of the month (e.g., Jan 31) to roll into the next month (Feb). Coverage month is now derived directly from `payment.coverage_month` and `payment.coverage_year`, which already hold the correct billing period.
- **Docs: GitHub-style alert rendering** — `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, and `> [!CAUTION]` callouts in markdown files now render as styled alert boxes instead of displaying the raw `[!TYPE]` text inside a plain blockquote. A `preprocess_github_alerts()` pre-processor was added to `app/routes/docs.py` that converts alert blockquotes in the markdown source before the library renders them, circumventing a Python `markdown` library limitation where adjacent blockquotes are merged into one element. Each alert body is rendered through a dedicated markdown pass so inline and block markup (bold, code, links, lists) inside the alert body is fully processed. Five alert types are supported with on-brand colours and Material Symbols icons: Note (blue/info), Tip (teal/lightbulb), Important (purple/priority_high), Warning (amber/warning), Caution (red/dangerous).
- **Docs: Unordered list display** — Lists were sometimes rendering without bullets due to missing `list-style-type` declarations and Python markdown's "loose list" behaviour (wrapping each item's content in `<p>` tags, which some browser/CSS combinations display as block paragraphs). Added explicit `list-style-type: disc/decimal`, `display: list-item`, and compact `<p>`-inside-`<li>` margin rules to the documentation stylesheet.

## [1.9.0] - 2026-03-04

### Security
- **Class Deletion Audit** — Comprehensive audit of all four class/period deletion paths, identifying inconsistent semantics, a P1 BalanceCache orphaning bug, sysadmin use of the deprecated `Student.block` field, and missing data-loss warnings in sysadmin confirmation dialogs. See `docs/SECURITY/AUDITS/SEC-AUD-011_Class_Deletion_Audit.md`.
- **P1 fix: BalanceCache orphaning** — `_hard_delete_join_code_scope` now deletes `balance_cache` rows for the deleted `join_code`, preventing stale balance reads after class deletion.
- **P2 fix: Sysadmin period deletion scope** — `delete_period` now resolves the period name to its `join_code(s)` via `TeacherBlock` before finding enrolled students, replacing the deprecated `Student.block` field lookup.
- **P2 fix: Sysadmin confirmation UX** — Period and teacher account deletion dialogs now accurately describe what is preserved versus removed and note the action cannot be undone.
- **P3 fix: Orphaned settings cleanup** — `_hard_delete_join_code_scope` now deletes `PayrollSettings` and `RentSettings` for block names that have no remaining `TeacherBlock` entries after a join-code deletion.

### Changed
- **Post-claim PII minimisation** — `dob_sum` and `last_name_hash_by_part` are now deleted from both the `TeacherBlock` roster seat and the `Student` record immediately after a student completes account setup. These fields are only needed during the one-time claim verification; retaining them afterwards served no purpose and increased the sensitive-data footprint.
  - `TeacherBlock.dob_sum` and `TeacherBlock.last_name_hash_by_part` are nulled when `is_claimed` is set to `True` (all claim paths: initial claim, add-class, recovery).
  - `Student.dob_sum` and `Student.last_name_hash_by_part` are nulled in `setup_pin_passphrase` once credentials are established; `has_completed_profile_migration` is set to `True` at the same time to suppress the legacy migration prompt.
  - `TeacherBlock.dob_sum` and `TeacherBlock.last_name_hash_by_part` database columns made nullable via migration `a1b2c3d4e5f6`.
- **Simplified student account recovery** — The recovery flow no longer asks students to re-enter their name and date of birth. The new two-step flow is: enter join code + reset code → set up new username + credentials. First name and last initial are preserved from the teacher-managed roster and are not editable by the student.
  - `recovery.account_lookup` now clears credentials (username, PIN, passphrase) directly on successful code verification and redirects to `student.create_username`.
  - `recovery.verify_identity` is retired; the route now redirects to `recovery.account_lookup` so bookmarked URLs remain functional.
- **`add_class` credential verification scoped to target class** — When a student adds a new class, credentials (first initial, last name, DOB) are now verified exclusively against the target class's own unclaimed roster seat hashes. The previous pre-check against the student's stored `dob_sum` (which is null post-claim) has been removed. Each join_code is an independent verification universe; claiming one class does not expose or depend on hashes from another.
- **`claim_account` duplicate detection** — Finding an existing student during initial claim now uses `first_half_hash` lookup instead of `dob_sum` filter, which remains correct after post-claim PII cleanup.
- **Documentation system consolidation** — Migrated remaining loose markdown files into the canonical documentation taxonomy under `docs/LOGS/AUDITS`, updated references to the new locations, and refreshed the canonical docs index.

### Added
- **Collective Goal Expiration** — Teachers can now set an optional expiration date on collective goal store items.
  - If the goal is met before the deadline, the item unlocks normally (existing behavior unchanged).
  - If the deadline passes without the goal being reached, all pending purchases are automatically refunded, the item is deactivated, and a `voided` status is recorded for each affected `StudentItem`.
  - Expiration is processed lazily: triggered on admin store page load, student shop load, and at purchase time — no background scheduler required.
  - Teacher deactivating an active collective item also triggers automatic refund for all pending purchasers.
  - A reactivated collective goal always starts progress at zero because voided `StudentItem` records are excluded from the progress count.
  - New `collective_goal_expires_at` column on `StoreItem` with Alembic migration `e3f4g5h6i7j8`.
  - New `app/utils/store.py` module with `refund_pending_collective_purchases()` and `process_expired_collective_goals()` helpers.
  - 16 new tests in `tests/test_collective_goal_expiration.py` covering happy paths, edge cases, API blocking, and multi-tenancy scoping.
- **Admin Transaction Backfill** — One-time remediation page (`/admin/backfill-transactions`) that lets teachers fix student balances when past transactions lack a class-period `join_code`. Detected automatically on dashboard load; teachers select the correct period for each affected student and the system links all orphaned transactions to the right class context.
- **Interactive Project Timeline** — New `/docs/timeline` page showcasing the full development history of Classroom Token Hub
  - Visual vertical timeline organized into four eras: Genesis, Crisis Resolution, Feature Expansion, and Refinement
  - Filter bar: All / Features / Fixes & Crises / Security / Architecture / Philosophy
  - Expandable version cards with details on every release from v1.0.0 through current unreleased
  - Design Philosophy section with all ten anti-goals and core educational principles
  - Scroll-triggered entry animations with intersection observer
  - Linked from the Help & Support Center (`/docs/`) index and Quick Links section
  - Added `docs/LOGS/AUDITS/LOG-ARC-039_Project_Timeline.md` as the source timeline document

### Changed
- **System Admin interface redesigned** - Complete redesign matching teacher/student interface patterns
  - **Mobile-friendly layout** - Fixed sidebar with hamburger toggle on mobile, mobile bottom navigation bar with quick access to Dashboard, Teachers, Support, Logs, and Announcements
  - **Dashboard revamped** - Stat cards (Total Teachers, Total Students, Active Invites, Open Tickets), 6 quick-action buttons, recent teacher registrations and errors panels, system admins table
  - **Teacher Management consolidated** - Unified page combining invite code generation/voiding (with copy-to-clipboard and void button), teacher accounts with class badges, student counts, last login, status, and per-period/account deletion actions; pending deletion requests displayed in a dedicated table
  - **Logs consolidated** - New combined `/sysadmin/combined-logs` page with tabbed Error Logs and Network Activity views; raw system log viewer removed (Grafana available instead)
  - **Support Tickets unified** - New combined `/sysadmin/support` page showing both User Reports (teachers + students) and Escalated Issues in tabs; bug bounty reward workflow preserved; detail views link back to the unified page
- **Template Design System Unification** - Standardized template styling across teacher, student, and sysadmin views
  - Replaced legacy Bootstrap icon usage (`bi-*`) with Material Symbols in templates and JS-rendered button states
  - Removed legacy opacity utility patterns (`bg-opacity-*`) in favor of semantic subtle backgrounds (`bg-*-subtle`)
  - Replaced hardcoded inline color literals in template style contexts with token/semantic values
  - Normalized standalone and shell templates to use consistent token-driven theming behavior

### Added
- **`void_invite_code` route** (`/sysadmin/manage-teachers/void/<id>`) - Allows sysadmin to void unused invite codes directly from the Teacher Management page
- **`combined_logs` route** (`/sysadmin/combined-logs`) - New consolidated log viewer combining error logs and network activity
- **`support_tickets` route** (`/sysadmin/support`) - New consolidated support ticket view combining user reports and escalated issues
- **`open_tickets` stat** on dashboard - Shows sum of new user reports + pending/in-review escalated issues

### Performance
- **Read-Path Audit & Optimization** - Conducted comprehensive audit of student list rendering and admin dashboard performance
  - **Removed Write-on-Read Side Effects**: Refactored `Student.checking_balance`, `Student.savings_balance`, and `Student.total_earnings` properties to be read-only calculations. Moved legacy automated settlement logic (which triggered database writes during read operations) to explicit mutation endpoints (`/transfer`, `/pay-rent`). This eliminates race conditions and significantly improves read performance.
  - **Optimized Admin Dashboard internals**: Refactored daily limit enforcement (`auto_tapout`) to use batch processing instead of per-student iteration and moved dashboard balance calculations to batched, scoped queries. Stage 2 audit kept dashboard query totals unchanged at 402 (explicit dashboard query-count reduction remains out of scope for this stage).
  - **Optimized Student Roster**: Eliminated N+1 query patterns in the student management table by batch-fetching balances and rent privileges. Query count reduced from ~1225 to ~10 for a class of 60 students.
  - **Scoped Balance Calculations**: Fixed a critical multi-tenancy flaw where student balances were aggregated across all classes instead of being scoped to the current teacher's context. Dashboard and roster now correctly reflect class-specific financial state.

### Fixed
- **Student rent/shop regression follow-up** - Addressed review-driven cleanup after the rent/store hotfix
  - Added shared helper logic for determining whether a student's current rent coverage period is paid, and reused it across student rent/shop and API purchase flows to reduce duplicated validation code
  - Kept incremental rent payment form available when incremental mode is enabled (even when full remaining balance exceeds checking), so partial payments are not blocked in the UI
  - Corrected mixed rent-link behavior in student shop so privilege-only rent items are deactivated while per-use rent perks remain purchasable at `$0`
  - Made the mixed rent-link regression test time-independent by using a relative due date instead of a fixed calendar date
- **Student store block scoping** - Student shop and purchase APIs now enforce block visibility while preserving the existing "no block mapping = visible to all blocks" semantics for unscoped legacy items
- **Student markdown toolbar icons restored** - Reintroduced Font Awesome in the student layout so markdown editor toolbar icons render correctly on student issue forms
- **Student payroll rate lookup** - Student payroll page and status projections now pass teacher context into pay-rate resolution so block-specific teacher rates display correctly instead of defaulting
- **P0: Duplicate auto-tap-out events causing payroll overpayment** - Added idempotency check to prevent race conditions when multiple sources (student browser polling, scheduled job, admin dashboard) call auto-tap-out logic simultaneously. Previously, duplicate "Daily limit reached" tap-out events would be created, causing payroll to count the same session multiple times and resulting in massive overpayment. Now checks if a daily limit tap-out already exists before creating a new one. Includes cleanup script (`cleanup_duplicate_tapouts.py`) to fix existing duplicate records. See `docs/LOGS/AUDITS/LOG-ARC-038_Duplicate_Tapout_Bug_Report.md` for full details.
- **Void redemption creating transactions without join_code** - Fixed `/api/reject-redemption` endpoint creating refund transactions with `join_code=NULL` when voiding redemptions for legacy StudentItem records. Added fallback logic to resolve join_code from TeacherBlock or current session when StudentItem.join_code is NULL, preventing balance fix warnings for teachers. This resolves the "Fix Student Balances" alert appearing after voiding old redemptions.
- **Void transaction CSRF 400 error** - Fixed student detail page void transaction button failing with 400 error. Added missing X-CSRFToken header to fetch request in `voidTransaction()` JavaScript function. Teachers can now successfully void transactions from student detail pages.
- **P0: Rent payment applied to wrong period with bill preview enabled** - Fixed critical bug where students with unpaid overdue rent were allowed to pre-pay for future periods instead of paying overdue amounts first. When bill preview was enabled with a long preview period (e.g., 30 days), the system incorrectly classified overdue students as being in "preview period" for next month's rent. This caused payments to be recorded for the wrong coverage period (next month instead of current/overdue month), preventing students from receiving rent benefits even after paying. Now verifies current coverage period is fully paid before allowing preview period payments. Students must pay oldest overdue period first, and benefits are granted immediately when current period is paid. Also fixed rent page to display correct period being paid for with OVERDUE badge when applicable.
- **Rent transaction month label now matches the coverage period being paid** - Fixed rent payment transaction descriptions to use the selected coverage due date (e.g., January 2026 for overdue January rent paid on February 17) instead of the wall-clock payment month. This keeps late-fee transactions aligned with the actual rent period and avoids showing overdue January payments as February charges.
- **Recovery and Claim Page Styling Not Applying** - Fixed account claim/recovery pages that referenced design tokens but did not load `tokens.css`
  - Added missing `tokens.css` includes in standalone recovery/claim templates
  - Corrected student recovery layout shell class from `student-theme` to `student-shell`
  - Restored valid template syntax in `student_detail.html` that affected recovery-related page rendering/tests
- **Documentation site link integrity** - Corrected stale docs navigation paths, breadcrumb dead links, and release-note route resolution so technical docs render from the current taxonomy with validated internal/external links.

## [1.8.0] - 2026-02-09

### Added
- **Rent Item Types (Privilege / Per-Use / Hall Pass)** - Extended itemized rent with three distinct item types
  - **Privilege**: Shows as a badge on the roster when rent is paid; optionally listed in store for individual purchase
  - **Per-Use**: Grants free store redemptions when rent is paid (single-use by default, or limited uses when set); always listed in store with "Rent Perk" badge; cannot be deleted from store (only via rent settings)
  - **Hall Pass**: Tops off student hall passes when rent is paid using source-tracking model (rent-granted vs purchased passes tracked separately via `StudentBlock.rent_hall_passes`)
  - **Mid-period edit guardrail**: Once any student has paid rent for the current period, item type, use limits, and hall pass counts are locked; only cosmetic changes (name, description, price) are allowed
  - **Store integration**: Per-use items marked `is_rent_linked` on `StoreItem`, preventing accidental deletion; admin store shows "Rent Perk" badge with disabled delete buttons for linked items
  - **Multi-use item tracking**: Added `uses_remaining` to `StudentItem` for per-use rent items with limited uses
  - **Free uses from rent**: When rent is fully paid, per-use items grant a free `StudentItem` with `uses_remaining` set (default 1); students can redeem these at no cost via the store
  - **Free purchase flow**: Store purchase route checks for active rent-granted uses before charging; shows "Free use (rent perk)" message
  - **Student shop indicators**: Rent-linked items show free uses remaining badge; "Included in your rent!" only shown for privilege-type items
  - **Models**: Added `rent_item_type`, `use_limit`, `hall_pass_count` to `RentItem`; `is_rent_linked` to `StoreItem`; `rent_hall_passes` to `StudentBlock`; `uses_remaining` to `StudentItem`
  - **Migrations**: `c2d9cf951ddc`, `9b0e06f05fcf`, `2765a36d76ff` (all idempotent)
- **Pre-paid Rent Coverage Period Tracking** - Rent payments now explicitly track which period they cover
  - Added `coverage_month` and `coverage_year` columns to `RentPayment` model
  - Paying rent on the due date (e.g., 1/28) now covers the student from 1/29 to the next due date (2/28)
  - All rent privilege checks, purchase blocking, dashboard status, and shop indicators use coverage-based lookups
  - Itemized rent item purchases (`per_period` duration) follow the same coverage period
  - **Migration**: `a1b2c3d4e5f6` adds columns with backfill from existing `period_month`/`period_year`

### Fixed
- **Privilege Badges Showing Non-Privilege Rent Items** - Fixed roster badge display to only show privilege-type rent items, not per-use or hall pass items
  - **Issue**: `_build_rent_privileges_by_block()` and `_get_rent_privileges_for_student()` filtered by `purchase_duration='per_period'` but not `rent_item_type='privilege'`, causing per-use and hall pass items to incorrectly appear as roster badges
  - **Solution**: Added `rent_item_type='privilege'` filter to both functions and the student shop "Included in your rent!" indicator
- **Insurance Class Selector Not Filtering Data** - Fixed multi-tenancy scoping issue where insurance management page showed all classes' data regardless of selected class
  - **Issue**: The "Viewing Insurance For" dropdown on the Insurance Management page did not filter policies, enrollments, or claims. Teachers with multiple class periods saw all insurance data aggregated together instead of scoped to the selected period.
  - **Root Cause**:
    - `InsurancePolicy` queries filtered only by `teacher_id`, not by `InsurancePolicyBlock.block`
    - `StudentInsurance` enrollments were not filtered by `join_code`
    - `InsuranceClaim` queries did not include `join_code` filtering
  - **Solution**:
    - Added `InsurancePolicyBlock` join to filter policies by selected block (or show policies available to all blocks)
    - Added `join_code` lookup from `TeacherBlock` for the selected period
    - Added `join_code` filter to all `StudentInsurance` and `InsuranceClaim` queries
  - **Impact**: Teachers now see only the insurance policies, enrollments, and claims for the currently selected class period
- **Store Purchase Blocked After Rent Paid Across Month Boundary** - Fixed rent-check logic using wrong month/year when verifying rent payments
  - **Issue**: `purchase_item()` used `now.month`/`now.year` instead of `current_due.month`/`current_due.year` when querying `RentPayment`. When a rent due date fell in January but the purchase check ran in February (past the grace period), the query looked for February payments and found none, incorrectly blocking the student.
  - **Solution**: All rent lookups now use `coverage_month`/`coverage_year` derived from the due date, not the wall-clock time
- **Issue Ticket Filing Fails With "An error occurred"** - Fixed Decimal serialization error in issue context snapshots
  - **Issue**: `create_context_snapshot()` stored raw `Decimal` objects (balances, transaction amounts) in a dict destined for a `db.JSON` column. Python's `json` module cannot serialize `Decimal`, causing a `TypeError` caught by the generic exception handler.
  - **Solution**: Convert all `Decimal` values to `float` before storing in the context snapshot
- **Duplicate Store Items When Applying Rent to All Periods** - Fixed `_sync_rent_items_to_store` creating duplicate store items
  - **Issue**: When a teacher applied rent settings to multiple blocks, each block created its own store item copy instead of sharing one item with block visibility
  - **Solution**: Look up existing store items by `teacher_id` + `name` before creating new ones; use `StoreItemBlock` to add block visibility without replacing existing associations

### Changed
- **Redundant Check Removal** - Simplified `_add_period` utility function in `app/routes/api.py` by removing a redundant `isinstance` check.
- **Documentation Update Plan Retired** - Removed `docs/development/DOCUMENTATION_UPDATE_PLAN.md` after v1.7 documentation updates were completed and tracked.

### Security
- **Hardened Grafana Proxy XSS Protection** - Improved content-type filtering to prevent XSS attacks (#897)
  - **Issue**: Original implementation had case-sensitivity issues, missed dangerous MIME types (SVG), and could be bypassed
  - **Solution**:
    - Made Content-Type check case-insensitive per RFC 2045
    - Added `image/svg+xml`, `text/xsl`, and `application/xslt+xml` to blocked MIME types
    - Properly handles Content-Type parameters (e.g., "text/html; charset=utf-8")
  - Prevents reflected XSS attacks via Grafana proxy endpoint
- **Fixed Function Redefinition in Student Routes** - Removed duplicate `_is_safe_url` function definition (#897)
  - **Issue**: Two identical function definitions in `add_class()` route, causing code clarity issues
  - **Solution**: Removed redundant first definition, kept wrapper around shared `is_safe_url` helper
  - Improves code maintainability and prevents potential bugs from function shadowing

## [1.7.1] - 2026-01-22

### Fixed
- **CRITICAL: Decimal.InvalidOperation in Student Dashboard Earnings/Spending Calculations** - Fixed crash when calculating weekly/monthly analytics with NULL transaction amounts
  - **Issue**: Dashboard earnings and spending calculations compared `tx.amount > Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]` when corrupted transactions exist
  - **Affected Code**: Lines 1261-1283 in `app/routes/student.py` (earnings_this_week, earnings_this_month, spending_this_week, spending_this_month)
  - **Additional Fix**: Line 1697 in savings interest calculation also needed NULL check
  - **Solution**: Added null check (`tx.amount is not None`) before all Decimal comparisons in dashboard calculations
  - Completes the NULL handling fix from PR #885 which fixed the Student model properties
- **Duplicate Student Claim Handling** - Added IntegrityError handling for duplicate student account claims
  - **Issue**: Edge cases in deduplication logic could cause IntegrityError when claiming student accounts with duplicate `first_half_hash` values
  - **Solution**: Wrapped `db.session.flush()` in try-except block to catch IntegrityError and link to existing student accounts gracefully
  - Prevents crashes and provides better user experience when duplicate claims occur
- **NameError in Payroll Function** - Fixed import error for `calculate_payroll_breakdown` in admin routes
  - **Issue**: Admin payroll routes referenced `calculate_payroll_breakdown` without proper import
  - **Solution**: Added explicit import of `calculate_payroll_breakdown` from `app.payroll` module
- **Decimal.InvalidOperation in recent_deposits** - Fixed crash when accessing student dashboard with NULL transaction amounts
  - **Issue**: `Student.recent_deposits` property compared `tx.amount <= Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]`
  - **Solution**: Added null check (`tx.amount is None`) before comparison in both `recent_deposits` and `total_earnings` properties
  - Prevents crashes when database has corrupted transaction data with NULL amounts
- **CRITICAL: Float/Decimal Type Error in Savings Interest Calculation** - Fixed `TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` in `apply_savings_interest()` function
  - **Issue**: The `student.savings_balance` property returns a `float`, but interest calculations were using `Decimal` arithmetic. When the float balance was multiplied by a Decimal rate expression, Python raised a TypeError.
  - **Impact**: Student dashboard returned 500 errors when compound interest was enabled for the class
  - **Root Cause**: The Decimal refactoring (PR #882) updated the interest calculation logic to use Decimal, but the `savings_balance` property still returns float for backward compatibility with other parts of the codebase
  - **Solution**: Wrap `student.savings_balance` with `_quantize_currency()` to convert it to Decimal before performing Decimal arithmetic
  - **Location**: `app/routes/student.py` in `apply_savings_interest()` function, line 1621
- **Decimal JSON Serialization Error** - Fixed `TypeError: Object of type Decimal is not JSON serializable` in student dashboard and API endpoints
  - **Issue**: After Decimal refactoring, Decimal values in templates and JSON responses were not converted to serializable types
  - **Impact**: Student dashboard and `/api/student-status` endpoint returned 500 errors
  - **Solution**: Convert all Decimal values to float before passing to templates or JSON serialization:
    - `app/routes/student.py`: Dashboard variables (checking_balance, savings_balance, forecast_interest, earnings, spending, projected_pay_per_block)
    - `app/routes/student.py`: Student dashboard `period_states_json`
    - `app/routes/api.py`: `/student/start-work` and `/student/stop-work` endpoints (projected_pay)
    - `app/routes/api.py`: `/student/status` endpoint (period_states)
  - Maintains Decimal precision for calculations, converts only at template/serialization boundary
- **CRITICAL: Decimal Precision in All Financial Calculations** - Refactored all financial logic to use Python's `Decimal` type throughout, not just for database storage
  - **Issue**: PR #880 was a hotfix that converted `Decimal` to `float` to resolve TypeErrors, but introduced floating-point precision errors
  - **Impact**: Small residual balances accumulate over time, incorrect interest calculations, potential overdraft fee issues
  - **Solution**: Systematic refactoring of all financial calculations to use Decimal arithmetic
  - **Changes**:
    - Updated `Student.get_checking_balance()` and `Student.get_savings_balance()` to return Decimal instead of float
    - Updated `calculate_scoped_balances()` to return Decimal tuples
    - Refactored all interest calculations in `student.py` to use Decimal arithmetic with proper exponentiation
    - Updated `apply_savings_interest()` to use Decimal throughout for compound and simple interest
    - Refactored transfer route to convert form inputs to Decimal before validation
    - Updated rent payment processing to use Decimal for payment amounts
    - Updated `payroll.py` `get_pay_rate_for_block()` to return Decimal per-second rate
    - Refactored all `admin.py` financial form handling (rent, payroll, store items, rewards, fines) to use `_quantize_currency()`
    - Updated `api.py` demo session balance inputs to use Decimal
    - Updated `system_admin.py` reward amounts to use Decimal
    - Refactored `utils/economy_balance.py` CWI calculations and balance validators to use Decimal
    - Updated `_normalize_to_weekly()` helper to work with Decimal inputs/outputs
  - **Backward Compatibility**: Decimal objects convert to float only for JSON serialization and template rendering
  - **Testing**: All existing decimal precision tests pass; financial calculations now mathematically exact
- **Decimal.InvalidOperation in get_total_earnings** - Fixed crash when calculating student earnings with NULL transaction amounts
  - Added null check (`tx.amount is not None`) before comparison in `get_total_earnings()` method
  - Prevents `decimal.InvalidOperation` error on `/admin/students` page when database has corrupted transaction data
  - Handles edge case where historical data migrations or database inconsistencies result in NULL amounts
  - Fix applied to all three code paths (join_code, teacher_id, and no parameters)
- **CRITICAL: Floating-Point Rounding Errors in Financial Calculations** - Converted all financial amounts from Float to Decimal for exact precision
  - **Bug 1**: Transfers that zeroed out checking accounts incorrectly triggered $35 overdraft fees due to -0.00 balance representation
  - **Bug 2**: Partial rent payments left unpayable tiny balances (e.g., $0.0000001) due to float precision errors
  - **Fix**: Changed `Transaction.amount` from `Float` to `Numeric(12, 2)` in database for exact decimal representation
  - **Fix**: Updated all financial models (RentSettings, BankingSettings, PayrollSettings, StoreItem, InsurancePolicy, etc.) to use Numeric
  - **Fix**: Updated balance calculation methods to use Python's `Decimal` type instead of `float`
  - **Fix**: Added near-zero balance normalization (|balance| < $0.01 → $0.00) to prevent false overdraft fees
  - **Migration**: Created migration to convert all Float columns to Numeric(12, 2) without data loss
  - **Testing**: Added comprehensive test suite for edge cases (zero transfers, partial payments, near-zero balances)
- **Student Creation Without Deprecated teacher_id** - Removed deprecated `teacher_id` assignment when creating new students to prevent `TypeError: 'teacher_id' is an invalid keyword argument for Student`.
- **Scheduled Auto Tap-Out Transactions** - Avoided committing inside the scheduled auto tap-out loop to prevent closed-transaction errors during background checks.
- **Student Claim DOB Field** - Aligned the claim-account form field name with the templates to prevent 500 errors on /student/claim-account.
- **Student Transfer Banking Settings Import** - Removed a local import shadowing `BankingSettings` to prevent UnboundLocalError on /student/transfer.
- **Rent Calculation Accuracy** - Improved rent amount calculations for monthly display (#839)
  - Fixed daily rent calculation to use actual days in month (via `monthrange`) instead of approximating 30 days
  - Added support for 'custom' frequency type in rent calculation logic
  - Fixed timezone inconsistency by using timezone-aware `datetime.now(timezone.utc)` consistently
  - Added null checks for `grace_period_days` and `due_day_of_month` fields to prevent TypeError
  - Refactored duplicated late payment check logic into single code path
  - Optimized payments query using subquery instead of list comprehension for better performance
- **Rent Statistics Display** - Fixed incorrect student counts in rent overview cards (#839)
  - "Paid This Month" now correctly shows count of students who paid (not payment count)
  - "Unpaid This Month" now correctly shows count of students with outstanding balances
  - Both statistics use accurate `unpaid_students` calculation instead of payment count
- **Rent Period Display** - Fixed misleading "Period" column in unpaid students list (#839)
  - Now shows billing period (e.g., "January 2026") instead of class block/period
- **Hall Pass Queue Scoping** - Removed deprecated `students.teacher_id` filtering to prevent hall pass queue errors.

### Changed
- **Rent Calculation Helper** - Extracted rent amount calculation into reusable helper function (#839)
  - Created `_calculate_base_rent_amount()` helper to avoid code duplication
  - Used in both payroll warning calculation and unpaid students calculation
  - Follows DRY principle for better maintainability
- **CSP Headers for Public Hall Pass Pages** - Modified Content Security Policy to allow embedding for read-only hall pass display pages
  - `/hall-pass/verification` and `/hall-pass/queue` can now be embedded in external sites (e.g., Schoology, Canvas)
  - These pages are public, read-only displays with no state-changing actions
  - `/hall-pass/terminal` remains protected (not embeddable) as it performs state-changing check-in/check-out actions
  - Removed `X-Frame-Options` header for embeddable pages and added `frame-ancestors *` to CSP
  - All other pages remain protected with `X-Frame-Options: SAMEORIGIN` and `frame-ancestors 'self'`

## [1.7.0] - 2026-01-09

### Added
- **ToS Acknowledgment Modal** - Implemented a modal during admin sign-up that requires explicit acknowledgment of Terms of Service and Privacy Policy.
  - Modal blocks the sign-up process until the "I have read and agree" checkbox is checked.
  - `tos_accepted` status and timestamp are recorded in the `Admin` table.
  - Ensures compliance with legal requirements for teacher account creation.

### Fixed
- **Analytics Events Value Display** - Show zero-value economy changes in the analytics events timeline by checking for `None` instead of falsy values.
- **EasyMDE Form Submission** - Fixed issue where forms with EasyMDE markdown editors could not be submitted due to hidden required fields
  - EasyMDE markdown editor hides the underlying textarea, causing browser validation to fail on required fields
  - Removed HTML `required` attribute from hidden textareas after editor initialization
  - Server-side validation via `DataRequired()` still enforces required fields
  - Applied fix to insurance claim form (`student_file_claim.html`) and issue submission form (`student_submit_issue.html`)
  - Resolves console error: "An invalid form control with name='[field]' is not focusable"

### Added
- **Analytics Dashboard (Phase 1-3)** - System health observability dashboard per analytics specification
  - Three new database models: `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
  - Analytics computation engine with CWI-relative metrics (no absolute balances/rankings)
  - System health metrics: participation rate, money velocity, CWI deviation bands, budget survival pass rate
  - Trend analysis: tracks improving/stable/worsening patterns across periods
  - Visual alerts with explanations (what changed, why it matters, suggested actions)
  - Event annotation system for rent changes, wage changes, inflation events
  - Metrics precomputed and cached by time window for 5-second readability
  - Weekly and monthly time window views
  - All metrics properly scoped by `join_code` for multi-tenancy compliance
  - Dashboard route at `/admin/analytics`
  - API endpoints for snapshot data and alerts
  - Comprehensive test coverage for analytics engine
  - Database migration: `a7b8c9d0e1f2_add_analytics_models`
  - Per spec: no student names in default views, no leaderboards, no comparative rankings
  - Design principle: "Something is drifting — and I know what lever to pull"
- **Mobile Navigation Enhancement** - Full navigation menu now accessible on mobile devices and PWA
  - Added floating hamburger menu button that appears on mobile (<768px)
  - Sidebar slides in from left with smooth animation and backdrop overlay
  - Help buttons now visible as icon-only on mobile screens
  - Contextual help links show icon on mobile, hiding text to save space
  - Same template works for desktop, mobile, and PWA - no separate mobile templates needed
  - Sidebar automatically closes when clicking navigation links or backdrop
  - Resolves PWA limitation where full navigation menu was previously inaccessible
- **Rent Itemization Feature** - Teachers can now specify what rent pays for and offer items as store alternatives (MVP)
  - New `RentItem` model to track itemized rent components (e.g., Desk, Chair, Locker)
  - Teachers can add/remove/reorder rent items in Rent Settings page
  - Optional store integration: mark items as "Available in Store" with custom pricing
  - Automated sync: items marked for store availability automatically create/update StoreItem records
  - StoreItem created with `limit_per_student=1` to enforce single-purchase behavior
  - Store items inherit block visibility from rent settings
  - Student rent view displays itemized breakdown showing what rent includes
  - Students see store price comparison for items available separately
  - Pro tip message encourages rent payment by showing total value comparison
  - Manual pricing (teacher sets store price manually - automatic pricing calculator coming in future release)
  - Database migration: `6feaa660d6c3_add_rent_item_table`
- **Enhanced Purchase Restrictions** - "Prevent Purchase When Late" toggle now has dynamic behavior based on itemization
  - When rent itemization is disabled: blocks ALL store purchases when student is late on rent (original behavior)
  - When rent itemization is enabled: students late on rent can ONLY purchase items covered by rent (at à la carte prices), all other store items blocked
  - Creates strong incentive structure: pay rent to get everything, or buy individual rent items at higher prices while missing out on other store items
  - UI dynamically updates toggle label and description based on itemization status
  - JavaScript updates label when items are added/removed dynamically
  - Implemented in `/api/purchase-item` endpoint with proper rent late detection and item validation
- **Purchase Duration Options for Rent Items** - Teachers can now choose how long individually-purchased rent items last
  - New `purchase_duration` field on RentItem model: 'per_use' or 'per_period'
  - **Per Use**: Student must buy each time they want to use it (unlimited purchases allowed)
  - **Per Rent Period**: Student buys once and can use until next rent is due (limit 1, expires when rent comes due)
  - Radio button selector in rent itemization UI with clear explanations
  - Store items automatically configured with appropriate purchase limits based on duration type
  - Purchase API calculates expiration dates for "per_period" items based on rent frequency settings
  - Automated expiration when next rent payment is due
  - Database migration: `h7i8j9k0l1m2_add_purchase_duration_to_rent_items`
- **Rent Privilege Badges** - Visual indicators on student detail page showing active rent privileges
  - Displays all "per_period" rent items that students currently have access to
  - **Green badges**: Privileges covered by paid rent (automatic for rent-paying students)
  - **Blue badges**: Privileges purchased individually (shows "(Purchased)" label)
  - Badges only show for non-expired privileges
  - Rent-paying students automatically receive all per-period privilege badges
  - Teachers can quickly see which students have which privileges at a glance
  - Hover over badges to see item descriptions

## [1.6.0] - 2026-01-01

### Added
- **Documentation Organization** - Improved repository structure and documentation consistency
  - Consolidated duplicate script files into scripts/ directory
  - Standardized file paths and references across documentation
  - Removed obsolete root-level duplicates
  - Improved navigation and file organization

### Fixed
- **Getting Started Widget** - Fixed onboarding widget state persistence issues
  - Widget state now persists to database instead of browser localStorage
  - Widget dismissal and task completion now sync across logins and devices
  - Skipped tasks are now properly marked as complete in the widget
  - Added `widget_tasks_completed`, `widget_dismissed`, and `widget_dismissed_at` fields to `TeacherOnboarding` model
  - Updated `/admin/onboarding/status` endpoint to check both actual setup AND manually skipped tasks
  - Added `/admin/onboarding/dismiss-widget` endpoint to persist widget dismissal
  - Widget state is per-teacher (not per-block) for consistent onboarding experience
- **Multi-Tenancy Violation** - Fixed critical bug where `HallPassSettings` records were created without `teacher_id`, violating NOT NULL constraint and breaking multi-tenancy isolation
  - Fixed `/api/hall-pass/settings` endpoint to scope settings by `teacher_id` from session
  - Fixed hall pass creation in `/tap` endpoint to retrieve `teacher_id` from `join_code` via `TeacherBlock` lookup
  - All `HallPassSettings` queries now properly scoped by `teacher_id` and `block`
- **Content Security Policy** - Restored `'unsafe-eval'` directive to `script-src` CSP policy as it is required by passwordless.dev library's minified build (uses `new Function()` internally)
- **Passkey Authentication** - Fixed environment variables not loading by specifying explicit path to `.env` file in `load_dotenv()` call - ensures environment is loaded regardless of gunicorn working directory
- **Passkey Authentication** - Fixed token destructuring in `signinWithDiscoverable()` to properly handle error responses from passwordless.dev SDK
- **Deployment** - Added verification steps to confirm environment variables are properly written to `.env` and loaded by systemd service
- **File Organization** - Fixed inconsistent paths for student upload template and script references

### Changed
- Consolidated duplicate scripts into scripts/ directory (seed_dummy_students.py, create_admin.py, etc.)
- Removed duplicate nginx configuration file from root
- Updated documentation to reference correct file paths

### Documentation
- Improved repository organization and file structure
- Updated path references throughout documentation
- Removed obsolete duplicate files

## [1.5.0] - 2025-12-29

### Added
- **Attendance Issue Reporting** - Students can now report issues with specific attendance/tap events (clock in/out records) directly from the Work & Pay page
  - New route `/help-support/tap-event/<id>/report` for reporting attendance record issues
  - Report buttons added to all tap event tables in Work & Pay > Attendance Record tab
  - Uses same issue resolution workflow as transaction reporting
  - Students can report up to 20 most recent tap events per block
- **Issue Resolution & Escalation System** - Structured, teacher-mediated issue handling system
  - **Student Features**:
    - New Help & Support interface with 3 tabs: Knowledge Base, Report an Issue, My Issues
    - Submit general issues (clock-in problems, features not working, balance incorrect, etc.)
    - Report transaction-specific issues directly from transaction history
    - Help icons next to each transaction in Recent Activity for quick issue reporting
    - Character-limited submissions (1000 chars) to encourage concise reporting
    - Automatic context capture: balances, transaction history, system metadata
    - Status badges (Submitted, Teacher Review, Resolved, Elevated, Developer Review) - no messaging
    - View all submitted issues with status tracking
  - **Teacher Features**:
    - Issue review queue with pending/resolved/escalated tabs
    - Detailed issue view showing student explanation, context, and transaction details
    - Resolution actions:
      - Reverse/void transactions directly from issue interface
      - Manual adjustment (teacher handles offline)
      - Deny issue with required explanation
    - Escalate to developer with:
      - Required escalation reason
      - Diagnostic notes for investigation
      - Optional class name sharing checkbox (default: opaque reference only)
      - **"Student may receive reward"** checkbox for legitimate bug reports
    - Complete status history and resolution action audit trail
  - **Technical Implementation**:
    - 4 new database models: `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
    - Default categories: 6 transaction types + 6 general issue types
    - Opaque student references for sysadmin privacy (non-reversible hashes)
    - Multi-tenancy scoping by `join_code` for proper class isolation
    - Context snapshots preserve ledger state at time of submission
    - Complete audit trail with timestamps and attribution
    - Immutable student submissions after creation
  - **Design Principles**:
    - No direct student-to-sysadmin communication
    - Teachers are first-line decision makers
    - Evidence-based issue tracking (tied to concrete transactions/records)
    - Data minimization for sysadmin review
    - Status badges only (non-communicative design)
  - Routes:
    - Student: `/student/help-support`, `/student/help-support/submit-issue`, `/student/help-support/transaction/<id>/report`
    - Teacher: `/admin/issues`, `/admin/issues/<id>`, `/admin/issues/<id>/resolve`, `/admin/issues/<id>/escalate`

### Changed
- Improved `flask create-sysadmin` command to display TOTP secret and QR code during account creation
  - Shows scannable QR code in terminal for easy authenticator app setup
  - Displays plaintext secret for manual entry backup
  - Auto-clears terminal after user confirmation for security
  - Secret remains encrypted in database after initial display
- Issue resolution UI refresh and workflow refinements
- Issue management and reporting refactor
- Standardized UTC timestamp formatting

### Fixed
- **Store Item Creation** - Fixed critical bug where tier, collective_goal_type, collective_goal_target, and redemption_prompt fields were not being saved when creating new store items
  - Added `tier` field assignment to store creation route (app/routes/admin.py:3047)
  - Added `collective_goal_type` and `collective_goal_target` field assignments for collective goal items (app/routes/admin.py:3063-3064)
  - Added `redemption_prompt` field assignment for delayed-use items (app/routes/admin.py:3066)
  - These fields were already present in the form (forms.py) and model (models.py), but were not being passed to the StoreItem constructor
  - Edit functionality uses `populate_obj` rather than manually assigning these fields, so this bug specifically affected the creation route
- **Transaction Issue Reporting** - Added report buttons to all transaction tables in Banking/Finances page (Checking and Savings tabs), allowing students to report issues on any visible transaction (up to 50 most recent), not just the 5 shown on dashboard
- **Issue Resolution Display** - Fixed `developer_resolved` status showing as "Escalated" instead of "Resolved by Developer" in teacher view
- **Issue Context Snapshot** - Fixed incorrect balance calculation in context_snapshot by using Student model's `get_checking_balance()` and `get_savings_balance()` methods instead of non-existent `get_balances()` function
- **Passkey Authentication** - Fixed missing username parameter in passkey authentication start request causing 500 error
- **Passkey Registration** - Fixed credential ID extraction from passwordless.dev SDK response by using correct destructuring pattern `{ token, error }`
- **Content Security Policy** - Added `https://static.cloudflareinsights.com` to `connect-src` directive to allow Cloudflare analytics
- **Content Security Policy** - Added `worker-src 'self' blob:` directive to allow Web Workers used by passwordless.dev library
- Fixed `time.tzset()` Windows compatibility issue in wsgi.py - now only calls tzset() on Unix-like systems
- Fixed admin signup crash when using SQLite - handles datetime fields stored as strings
- System Admin announcements form `ValueError` by adding a custom `coerce` for the `target_teacher` field

### Security
- Enhanced privacy protection in issue resolution system through opaque student references
- Teacher-controlled data disclosure to sysadmins (optional class name sharing)
- **Content Security Policy** - Removed unnecessary `'unsafe-eval'` directive from `script-src` to strengthen XSS protection (passwordless.dev library does not require dynamic code execution)

### Documentation
- Reorganized documentation structure for improved navigation
- **Developer Documentation Updates** - Updated development tracking documentation to reflect current status
  - Updated `DEVELOPMENT.md` to reflect v1.6.0 status (was showing 1.4.0)
  - Added v1.5.0 and v1.6.0 release summaries to Recent Releases section
  - Updated target version from 1.5.0 to 1.7.0
  - Updated `IMPLEMENTATION_PROGRESS.md` to mark sysadmin routes and templates as completed (were incorrectly marked as pending)
  - Added detailed test coverage priorities and recommendations
  - Updated Next Steps with current implementation status (85% complete)
  - Added specific guidance for remaining work (tests, user docs, technical docs)
- **Comprehensive Documentation Accuracy Fixes** - Corrected 10 inaccuracies found in user-facing documentation
  - **Store Items (docs/user-guides/features/store/creating-items.md)**:
    - Fixed tier system documentation to reflect actual implementation (Basic/Standard/Premium/Luxury based on % of CWI, not Tier 1/2/3 with dollar amounts)
    - Corrected default state - items are created as active by default, not inactive
    - Removed non-existent image upload feature documentation
    - Removed non-existent daily purchase limit documentation
    - Updated terminology to match code (Immediate Use/Delayed Use instead of Virtual/Physical)
    - Added missing "Collective Goal" item type to documentation with full explanation
    - Corrected purchase limits documentation to reflect actual behavior (concurrent ownership, not daily limits)
    - Updated scenario examples to use correct field names and remove daily limits
    - Removed confusing "if available" language for collective goals (feature is fully available)
    - Removed misleading "Use images" tip from Tips for Success section (feature doesn't exist)
    - Fixed contradictory troubleshooting text about daily limits (clarified to use inventory and per-student limits)
  - **Payroll (docs/user-guides/features/payroll/running-payroll.md)**:
    - Removed non-existent automatic payroll feature documentation (entire section)
    - Added guidance for manual payroll scheduling and consistency
    - Clarified that break time IS paid (system does not exclude breaks from hours worked)
    - Added Q&A explaining how to handle unpaid breaks if desired
    - Updated all automatic payroll references to reflect manual-only operation
  - **Banking (docs/user-guides/features/banking/transferring-money.md)**:
    - Removed non-existent transfer limits documentation (daily limits, min/max transfer amounts)
    - Simplified to only document actual rules (no negative balances)

### Dependencies
- Bump `requests` from 2.32.4 to 2.32.5
- Bump `markdown` from 3.7 to 3.10
- Bump `webfactory/ssh-agent` from 0.9.0 to 0.9.1

## [1.4.0] - 2025-12-27

### Added
- **Announcement System** - Teachers can create and manage announcements for their class periods
  - Display announcements on student dashboards with dismiss capability
  - Filter announcements by class period
  - Toggle announcement visibility (active/inactive)
  - Create, edit, and delete announcements with rich formatting
  - System admins can create global announcements visible across all classes
  - Announcements link added to admin navigation under Classroom section
- **UI/UX Improvements** - Comprehensive redesign of dashboard and navigation interfaces
  - **Personalized Greetings**:
    - Teacher dashboard displays centered "Hi, [Display Name]" greeting with info icon tooltip linking to settings
    - Student dashboard shows dynamic time-based greeting with first name
    - Mid-day greetings randomize between friendly options: "Howdy", "Good day to you", "Good to see you again", "Great timing", "Let us get started"
    - Morning (5am-12pm): "Good morning"
    - Afternoon (12pm-5pm): Random friendly greeting
    - Evening (5pm-5am): "Good evening"
  - **Enhanced Student Dashboard**:
    - Removed redundant left navigation sidebar for cleaner layout
    - Added side-by-side account balance cards for Checking and Savings accounts
    - Light gray card backgrounds for better visibility
    - Savings account displays projected monthly interest when balance > 0
    - Encouragement message when savings balance is $0 to promote saving habits
    - Fully responsive design (side-by-side on desktop, stacked on mobile)
  - **Accordion-Style Admin Navigation**:
    - Reorganized sidebar navigation into collapsible accordion categories
    - Categories: Classroom, Economy, Bills, Settings
    - Bootstrap accordion ensures only one section open at a time for cleaner interface
    - Consolidated Settings section: Personalization, Passkey, Features, Help & Support
    - Removed non-functional "Mobile Site" link from navigation
    - Custom CSS styling for dark sidebar theme with smooth transitions
  - **Improved Sign Out Button**: Enhanced contrast with red filled button and white text
  - **Streamlined Authentication Flow**:
    - Login forms present two authentication method buttons upfront
    - "Use my authenticator" button reveals TOTP field with Back button
    - "Use my passkey" button triggers WebAuthn flow with automatic fallback to TOTP on failure
    - Applied to both admin and system admin login pages
    - Cleaner, more intuitive authentication experience with proper error handling

### Changed
- **Dependency Updates** - Updated key dependencies for security and stability
  - Updated `click` from 8.1.8 to 8.3.1
  - Updated `beautifulsoup4` from 4.13.4 to 4.14.3
  - Updated `requests` from 2.32.3 to 2.32.4

### Security
- **CodeQL Security Alerts Remediation** - Addressed 62 security alerts identified by CodeQL scanning (#737)
  - **Clear-text Logging of Sensitive Information**:
    - Remove TOTP secret printing from `create_admin.py`, `wsgi.py`, and seed scripts
    - TOTP secrets now encrypted in database with secure access only
    - Prevents TOTP secrets from appearing in logs, console output, or command history
  - **DOM XSS Vulnerabilities**:
    - Fixed `innerHTML` usage in `templates/student_transfer.html`
    - Fixed `innerHTML` usage in `static/js/attendance.js`
    - Replaced with safe DOM manipulation using `createElement` and `textContent`
    - Prevents XSS attacks via user-controlled data
  - **GitHub Actions Workflow Permissions**:
    - Added explicit permissions to `toggle-maintenance.yml`, `check-migrations.yml`, and `deploy.yml`
    - Follows principle of least privilege for workflow security
    - Reduces workflow attack surface
  - **Documentation**: Added `docs/LOGS/AUDITS/SECURITY_FIXES_SUMMARY.md` with complete analysis of all 62 alerts
  - **Summary**: Fixed 23+ real security issues, suppressed 2 false positives, reviewed 37 false positives (already mitigated)
- **Enhanced Open Redirect Protection** - Improved URL validation in student class enrollment redirects
  - Upgraded `_is_safe_url()` function to use same-origin validation
  - Now uses `urljoin()` to resolve relative URLs against application's base URL
  - Validates that redirect targets match the application's scheme and domain
  - Prevents protocol-relative URLs and external redirects
  - Added explicit security annotations (`# nosec`) with justification at all redirect points
  - Addresses all 9 CodeQL security scanner findings for URL redirection vulnerabilities
  - Affects student add-class flow redirect handling (`app/routes/student.py:710-877`)

### Fixed
- **Teacher Invite Code Validation** - Fixed critical bugs preventing teacher signup with invite codes (#738)
  - **Whitespace Handling**: Strip whitespace from invite codes during creation and validation
  - **Timezone Comparison Error**: Fixed TypeError when comparing invite code expiration dates (timezone-aware vs timezone-naive datetimes)
  - **TOTP Form Validation**: Properly handle TOTP confirmation form submission separate from initial signup form
  - **Form Field Population**: Use AdminTOTPConfirmForm for TOTP submissions instead of AdminSignupForm
  - **Date String Handling**: Pass date string instead of integer for dob_sum field in TOTP confirmation
  - Added comprehensive debug logging for invite code creation and validation
  - Added cleanup script (`cleanup_invite_codes.py`) for existing codes with whitespace
  - Ensures consistency between invite code creation and validation across system admin and CLI tools
- **TOTP Setup UI** - Updated TOTP setup page to match new brand theme
  - Replaced hardcoded colors with CSS variables (--primary, --secondary, etc.)
  - Updated gradient and logo to match refreshed brand
  - Added pattern background to match signup page design
  - Improved button hover states for consistency
- **Onboarding Templates** - Updated color scheme and text for better consistency with new brand theme
- **Admin Dashboard**: Removed duplicate greeting that was appearing in both page header and content section
- **Student Dashboard**: Improved account balance cards with clearer styling using light backgrounds instead of semi-transparent overlays for better readability
- **Mobile Responsiveness**: Enhanced responsive behavior with proper Bootstrap column classes (col-12 col-md-6)
- **Grafana Access Issue** - Fixed "connection refused" error when accessing Grafana from system admin dashboard
  - **Root Cause**: Nginx `proxy_pass` had trailing slash that stripped URL path, causing infinite redirects
  - **Dual-Layer Solution** for maximum reliability:
    - **Flask Proxy (Fallback)**: Added `/sysadmin/grafana` route that proxies to Grafana service
      - Works immediately without Nginx configuration changes
      - Maintains system admin authentication via `@system_admin_required`
      - Configurable via `GRAFANA_URL` environment variable (defaults to `http://localhost:3000`)
      - Rate-limit exempt for smooth dashboard operation
      - Graceful error handling with user-friendly messages
      - Added `requests==2.32.3` dependency
    - **Nginx Fix (Production)**: Corrected configuration provided in `nginx-grafana-fix.conf`
      - Remove trailing slash from `proxy_pass http://127.0.0.1:3000/` → `proxy_pass http://127.0.0.1:3000`
      - Nginx intercepts requests before Flask (faster performance)
      - Auto-fallback to Flask proxy if Nginx not configured
  - See `GRAFANA_FIX_GUIDE.md` for detailed implementation guide

## [1.3.0] - 2025-12-25

### Added
- **Passwordless Authentication for Teachers** - Implemented WebAuthn/FIDO2 passkey authentication for teacher admins
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/admin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Database model `AdminCredential` for storing passkey metadata
  - TOTP authentication remains available as backup option
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Passkey settings link added to teacher navigation sidebar
- **Passwordless Authentication for System Admins** - Implemented WebAuthn/FIDO2 passkey authentication using passwordless.dev
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/sysadmin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Frontend integration with passwordless.dev JavaScript SDK
  - Database model `SystemAdminCredential` for storing passkey metadata
  - TOTP authentication remains available alongside passkeys
  - Self-hosted ready: Infrastructure supports future migration to py-webauthn library
  - Requires environment variables: `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Tracks credential usage timestamps for security auditing
  - Uses official Bitwarden Passwordless SDK (`passwordless==2.0.0`) for type-safe API interactions
- **Security Remediation Tools and Documentation** - Complete implementation guides and fixed workflow files
  - Step-by-step remediation guide: `docs/security/SECURITY_REMEDIATION_GUIDE.md`
  - Fixed workflow files with SSH host key verification: `.github/workflows/*.FIXED`
  - Automated SSH security setup script: `scripts/setup-ssh-security.sh`
  - Includes fixes for: SSH MITM vulnerability, secrets management hardening, dependency updates
  - Ready-to-use workflow files with improved security posture

### Security
- **Encrypted TOTP Secrets at Rest** - TOTP 2FA secrets now encrypted in database using Fernet (AES-128-CBC)
  - Added `encrypt_totp()` and `decrypt_totp()` helper functions in `app/utils/encryption.py`
  - All new admin/system admin accounts store encrypted TOTP secrets (base64-encoded)
  - Backward compatible: `decrypt_totp()` handles both encrypted and legacy plaintext secrets transparently
  - **MIGRATION REQUIRED**: Column length expanded from VARCHAR(32) to VARCHAR(200) - See `docs/LOGS/AUDITS/MIGRATION_TOTP_ENCRYPTION.md`
  - Defense in depth: Database compromise alone no longer sufficient to generate valid 2FA codes
  - **Note:** Still requires `ENCRYPTION_KEY` security - future migration to AWS Secrets Manager/Vault recommended
  - Files changed: `app/utils/encryption.py`, `app/models.py`, `app/routes/admin.py`, `app/routes/system_admin.py`, `wsgi.py`, `create_admin.py`
- **Removed Sensitive Information from Application Logs** - Eliminated logging of usernames, hashes, and PII
  - Removed username logging from student login, admin login, admin signup, and admin recovery flows
  - Removed partial hash logging from student authentication
  - Removed student name and DOB sum logging from bulk upload process
  - Impact: Prevents accidental exposure of PII in development logs, log files, or screenshots
  - Note: Production deployments should configure `LOG_LEVEL=WARNING` or higher to minimize log output
- **CRITICAL: Fixed PromptPwnd AI Prompt Injection Vulnerability** - Disabled vulnerable `summary.yml` GitHub Actions workflow
  - Workflow used AI inference (`actions/ai-inference@v1`) with untrusted user input from issue titles/bodies
  - Attack vector: Any user could create an issue with malicious prompt injection to leak `GITHUB_TOKEN` or manipulate workflows
  - Remediation: Disabled workflow by renaming to `summary.yml.DISABLED`
  - Impact: No exploitation detected - vulnerability fixed proactively
  - Documentation: See `docs/security/PROMPTPWND_REMEDIATION.md` for full details
  - Reference: [Aikido Security PromptPwnd Disclosure](https://www.aikido.dev/blog/promptpwnd-ai-prompt-injection-in-github-actions) (December 2025)
- **Comprehensive Attack Surface Security Audit Completed** - Full security review of codebase, CI/CD, and infrastructure
  - Audited: GitHub Actions workflows, authentication, authorization, encryption, multi-tenancy, dependencies, and API security
  - Findings: 16 total findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
  - Critical issues: AI prompt injection (fixed), SSH host key verification disabled (open)
  - Strengths: Excellent CSRF protection, SQL injection prevention, XSS mitigation, PII encryption, multi-tenancy isolation
  - Recommendations: Enable SSH host key verification, update cryptography package, improve secrets management
  - Documentation: See `docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md` for complete report

## [1.2.1] - 2025-12-21

### Added
- **Comprehensive Legacy Account Migration Script** - Complete migration tool for transitioning all legacy accounts to new multi-tenancy system
  - Migrates students with `teacher_id` to claim-based enrollment system
  - Creates missing `StudentTeacher` associations and `TeacherBlock` entries
  - Backfills `join_code` for all TeacherBlock entries
  - Backfills `join_code` for transactions, tap events, and related tables with proper multi-tenancy isolation
  - **FIXED:** Transaction backfill now matches on BOTH `student_id` AND `teacher_id` to ensure correct period assignment for students in multiple periods with same teacher
  - **FIXED:** Block names normalized to uppercase for consistency across database
  - **OPTIMIZED:** Phase 5 backfill uses CTE with `DISTINCT ON` instead of correlated subqueries for significantly better performance on large datasets
  - Includes dry-run mode for safe preview before applying changes
  - Provides comprehensive verification and error reporting
  - Located at: `scripts/comprehensive_legacy_migration.py`
- **Comprehensive Test Suite for Legacy Migration** - Full test coverage for migration script
  - Tests all 5 migration phases including Phase 5 (related tables backfill)
  - Tests critical multi-period student scenarios
  - Tests idempotency and error handling
  - Tests block casing normalization
  - Tests rollback on errors
  - Tests CTE performance optimization for Phase 5
  - Tests tables with and without period columns
  - Located at: `tests/test_comprehensive_legacy_migration.py`
- **Legacy Account Migration Documentation** - Complete guide for migration process
  - Historical context and migration strategy
  - Step-by-step deployment instructions
  - Troubleshooting common issues
  - Post-migration verification procedures
  - Roadmap for deprecating `teacher_id` column
  - Located at: `docs/operations/LEGACY_ACCOUNT_MIGRATION.md`
- **Join Code Schema Audit Tool** - `scripts/inspect_join_code_columns.py` lists which tables have or are missing `join_code` to support multi-tenancy audits
- **StudentBlock Join Code Migration** - Added idempotent migration (`a1b2c3d4e5f8`) to create `join_code` column and index on `student_blocks`, with safeguards for partially applied schemas

### Changed
- Preparing for final deprecation of `teacher_id`-based linkage system
- All legacy data now ready for migration to `join_code`-based multi-tenancy
- Hardened migration best practices documentation for avoiding duplicate-column errors in `student_blocks` hotfix scenarios
- Refreshed maintenance page copy and styling for clearer outage messaging

### Fixed
- Closed multi-tenancy gaps by adding `join_code` propagation to overdraft fees, bonus/bulk payroll postings, insurance reimbursements, manual payments, and bug-report rewards
- Improved bonus join_code lookup performance to reduce N+1 queries during mass payouts

## [1.2.0] - 2025-12-18

### Added
- **Progressive Web App (PWA) Support** - Full PWA implementation for improved mobile experience
  - Web app manifest with app metadata and icon configuration
  - Service worker with intelligent caching strategies (cache-first for static assets, network-first for CDN resources)
  - Offline fallback page with user-friendly offline experience
  - PWA installation capability on mobile devices (Add to Home Screen)
  - Multi-tenancy-safe caching that excludes authenticated routes
  - Automatic cache cleanup and version management
- **Mobile Experience Enhancements** - Dedicated mobile templates for student portal with responsive navigation and improved touch targets
- **Accessibility Improvements** - Enhancements following WCAG 2.1 AA guidelines
  - Added ARIA labels to mobile navigation and interactive elements
  - Improved keyboard navigation support
  - Enhanced screen reader compatibility
  - Better color contrast ratios
- **UI Documentation** - Added `docs/PWA_ICON_REQUIREMENTS.md` and `TEMPLATE_REDESIGN_RECOMMENDATIONS.md`
  - PWA icon asset generation instructions
  - UI redesign patterns and guidelines
  - Best practices for accordion/collapsible patterns
  - Color scheme guidelines for consistent visual hierarchy

### Changed
- **Attendance Terminology** - Renamed "Tap In/Out" to "Start Work/Break Done" for clarity
  - Updated user-facing text throughout student portal
  - Updated frontend API actions and documentation
  - Maintained backward compatibility in database actions
- **Admin UI Redesigns** - Modernized admin templates with collapsible accordion sections
  - **Insurance Policy Edit Page** - Eliminated overflow issues with progressive disclosure layout
  - **Store Item Edit Page** - Reduced scrolling with accordion sections for Bundle, Bulk Discount, and Advanced settings
  - **Rent Settings Page** - Better organization with collapsible sections
  - **Feature Settings** - Simplified to single-column, collapsible cards
  - Added visual "Active" badges to accordion headers indicating when sections have configured settings
- **Mobile Dashboard** - Simplified single-column layout with attendance card and tap buttons
- **Mobile Store** - Improved item list layout with larger purchase buttons
- **Theme Consistency** - Aligned mobile templates with main application theme colors

### Fixed
- **Critical: Multi-Tenancy Payroll Bug** - Fixed payroll calculations leaking data across class periods (#664)
  - Ensured all payroll queries properly scoped by join_code
  - Added multi-tenancy tests for payroll system
- **Payroll JSON Error** - Fixed "Run Payroll Now" button returning HTML instead of JSON (#668)
  - Resolved "Unexpected token '<!DOCTYPE'" error
  - Properly returns JSON response for AJAX requests
- **Timezone Handling** - Fixed timezone comparison error in payroll calculation (#666)
  - Corrected UTC normalization for payroll scheduling
  - Fixed edge cases with daylight saving time transitions
- **PWA Icon Rendering** - Fixed Material Symbols icons not loading in PWA mode (#672, #676)
  - Root cause: Service Worker intercepting Google Fonts with incorrect caching strategy
  - Solution: Service Worker now bypasses Google Fonts, letting browser handle natively
  - Added font preload and fallback CSS for Material Symbols
- **Mobile PWA Navigation** - Restored icons and removed horizontal scrolling (#674)
  - Tightened bottom navigation layout for small screens
  - Added overflow-x protection and responsive media queries
- **Desktop PWA Rendering** - Added PWA support to desktop templates for mobile viewing (#675)
  - Added PWA meta tags (theme-color, apple-mobile-web-app-capable)
  - Added mobile bottom navigation when sidebar is hidden
- **Auto Tap-Out Regression** - Fixed test failures due to missing teacher_id context in auto tap-out logic (#670)

### Technical
- Service worker cache bumped to v5 to force updates
- Added comprehensive multi-tenancy tests for payroll
- Improved mobile responsiveness across all admin templates
- Enhanced documentation organization and clarity

## [1.1.1] - 2025-12-15

### Fixed
- Secured teacher recovery verification by hashing date-of-birth sums and migrating existing records to the new salted hash format (#637)
- Hardened student login redirects and UTC-normalized dashboard earnings/spending calculations to prevent redirect abuse and negative totals (#638)
- Applied the green theme to standalone admin/auth pages and corrected admin heading hierarchy to resolve styling regressions (#635, #639)
- Added cache-busting static asset helper defaults and fallback coverage to stop `static_url` undefined errors across templates (#628-633)
- Stopped insurance management and edit screens from crashing when legacy forms lack the tier grouping field (#640)
- Added one-time prompt for legacy insurance policies and supporting script to encourage migration to tiered plans (#641)

## [1.1.0] - 2024-12-13

### Added
- **Student Analytics Dashboard** - Weekly statistics showing days tapped in, minutes attended, earnings, and spending
- **Savings Projection Graph** - Interactive 12-month visualization of savings growth on bank page using Chart.js
- **Long-Term Goal Items** - Option to mark store items that should be exempt from CWI balance checks (for expensive class rewards)
- **Enhanced Economy Health Warnings** - Specific recommended ranges and actionable guidance for all economy settings
- **Weekly Analytics Calculations** - Backend logic to calculate unique days tapped, total minutes, and transaction summaries
- **Savings Projection Algorithm** - Respects simple/compound interest and compounding frequency settings

### Changed
- **Complete UI Redesign** - Modern interface with softer colors, improved navigation, and better layout
- **Color Scheme** - Reduced brightness and contrast for better eye comfort (primary: #1a4d47, secondary: #d4a574)
- **Student Dashboard Layout** - Added sticky left sidebar navigation for quick access to all features
- **Economy Health Messages** - Improved warnings with absolute values and specific dollar recommendations
- **Tab Navigation** - Fixed CSS scoping to restore visibility across 15+ multi-tab pages

### Fixed
- **Critical: Restored Pending Actions section** on admin dashboard (store approvals, hall passes, insurance claims were missing)
- **Critical: Fixed invisible tabs** on Student Management, Store Management, and other multi-tab pages
- **Fixed missing navigation links** on login screens (account setup, recovery, privacy/terms)
- **Fixed CSS scoping issue** where `.nav-link` styles were applied globally instead of scoped to sidebar
- **Added missing Bootstrap Icons CSS** imports to admin and student layouts
- **Added missing utility classes** (`.btn-white`, `.icon-circle`) for redesigned UI

### Technical
- Database migration `a7b8c9d0e1f2` adds `is_long_term_goal` column to `store_items` table
- Updated `economy_balance.py` to skip long-term goal items in CWI validation
- Added Chart.js (v4.4.0) for savings projection visualization
- Improved query performance for weekly analytics calculations
- Updated forms.py with `is_long_term_goal` BooleanField

## [1.0.0] - 2024-11-29

### Milestone
First stable release of Classroom Token Hub! All critical security issues resolved and production-ready.

## [Unreleased] - Version 0.9.0 (Pre-1.0 Candidate)

### Project Status
The project is ready for version 1.0 release. All critical blockers have been resolved:
- ✅ **P0 Critical Data Leak:** Fixed and deployed (2025-11-29) - See [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/SECURITY/INCIDENTS/SEC-INC-013_Critical_Same_Teacher_Leak.md)
- ✅ **P1 Deprecated Patterns:** All updated to Python 3.12+ and SQLAlchemy 2.0+ (2025-12-06)
- 🔄 **Backfill:** Legacy transaction data being backfilled with interactive verification

### Added (2025-12-11)
- **DEVELOPMENT.md** — Unified development priorities document consolidating all TODO files and roadmap
- **docs/technical-reference/economy-specification.md** — Financial system specification (moved from root)
- **docs/development/ECONOMY_BALANCE_CHECKER.md** — CWI implementation guide (moved from root)

### Changed (2025-12-11)
- **Major documentation consolidation:**
  - Merged `DEVELOPMENT.md`, `docs/development/MULTI_TENANCY_TODO.md`, and `ROADMAP_TO_1.0.md` into single `DEVELOPMENT.md`
  - Updated all references to point to new unified documentation structure
  - Updated README.md to reflect v1.0 readiness (all critical blockers resolved)
  - Moved implementation reports to `docs/LOGS/AUDITS/` for historical reference
- **Security documentation updates:**
  - Updated `CRITICAL_SAME_TEACHER_LEAK.md` status to RESOLVED (deployed with backfill in progress)
  - Updated `docs/README.md` to remove "P0 BLOCKER" label

### Removed (2025-12-11)
- `DEVELOPMENT.md` — Consolidated into DEVELOPMENT.md
- `docs/development/MULTI_TENANCY_TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/TECHNICAL_DEBT_ISSUES.md` — Superseded by DEPRECATED_CODE_PATTERNS.md
- `ROADMAP_TO_1.0.md` — Consolidated into DEVELOPMENT.md

### Added (2025-12-04)
- **PROJECT_HISTORY.md** — Comprehensive document capturing project philosophy, evolution, and key milestones
- **docs/development/DEPRECATED_CODE_PATTERNS.md** — Technical debt tracking for Python 3.12+ and SQLAlchemy 2.0+ compatibility
- Documentation index updated with new security and archive sections

### Changed (2025-12-04)
- **Major documentation reorganization:**
  - Moved security audits to `docs/security/` (CRITICAL_SAME_TEACHER_LEAK.md, MULTI_TENANCY_AUDIT.md)
  - Moved development guides to `docs/development/` (JULES_SETUP.md, SEEDING_INSTRUCTIONS.md, TESTING_SUMMARY.md, MIGRATION_STATUS_REPORT.md)
  - Moved operations docs to `docs/operations/` (MULTI_TENANCY_FIX_DEPLOYMENT.md)
  - Archived historical fix summaries to `docs/LOGS/AUDITS/` (FIXES_SUMMARY.md, JOIN_CODE_FIX_SUMMARY.md, MIGRATION_FIX_SUMMARY.md, STAGING_MIGRATION_FIX.md)
- Updated `docs/README.md` with comprehensive documentation map including security and archive sections
- Updated main README with version 0.9.0 status and platform-agnostic deployment language
- Removed hardcoded IP addresses from GitHub Actions workflows (now use `secrets.PRODUCTION_SERVER_IP`)

### Removed (2025-12-04)
- **scripts/cleanup_duplicates.py** — Obsolete duplicate cleanup script (superseded by cleanup_duplicates_flask.py)
- Debug print statement in `app/routes/api.py:1198` (replaced with proper logging)

### Fixed (2025-12-04)
- Security: Removed hardcoded production server IP from CI/CD workflows

### Fixed (2025-12-05)
- Student portal: Removed the non-functional class switch button from the class banner and eliminated hover animations to reduce UI confusion.
- Student portal: Scoped payroll attendance and projection data to the currently selected class so multi-class students only see the active class statistics.

### Previous Changes
- Continued repository organization and documentation cleanup
- Moved `PULSETIC_SETUP.md` to `docs/operations/` for better organization
- Moved additional PR-specific reports to `docs/LOGS/AUDITS/pr-reports/`
- Updated `docs/operations/README.md` with comprehensive guide listings
- Added migration to align `rent_settings` schema with application model by including the `block` column
- Added migration to bring the `banking_settings` table in sync with the model by introducing the missing `block` column

---

## [2025-11-25] - Maintenance & Bypass Enhancements

### Added
- Persistent maintenance mode across deploys (`deploy_updates.sh`) with `--end-maintenance` explicit exit flag
- System admin and token-based maintenance bypass with session persistence (`maintenance_global_bypass`)
- System admin login access during maintenance (`/sysadmin/login`) and login link on `maintenance.html`
- Badge icon/text server-side mapping and status description rendering fallback when JS disabled
- Documentation for maintenance variables and operational workflow (see `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md`)

### Changed
- `deploy_updates.sh` now detects existing maintenance state instead of resetting it
- Bypass logic promotes valid sysadmin/token to global session for teacher/student role testing
- Tests expanded for bypass persistence and login accessibility

### Security
- Bypass token now stored only in environment and session flag; recommends rotation post-window

## [2025-11-24] - Repository Housekeeping

### Added
- Archive directory for historical PR reports (`docs/LOGS/AUDITS/pr-reports/`)
- README documentation for scripts directory
- README documentation for archived PR reports
- CLI command `normalize-claim-credentials` to backfill student and roster claim hashes to the canonical format

### Changed
- Moved utility scripts to `scripts/` directory for better organization:
  - `check_migration.py`
  - `check_orphaned_insurance.py`
  - `cleanup_duplicates.py`
  - `cleanup_duplicates_flask.py`
- Updated script references in documentation to reflect new paths
- Removed hardcoded paths from `check_orphaned_insurance.py`
- Repository housekeeping: organized files, removed obsolete files, and updated documentation
- Improved repository structure for better maintainability and navigation

### Removed
- Duplicate file: `SECURITY_AUDIT_INSURANCE_OVERHAUL (1).md`
- Moved PR-specific reports to archive (no longer in root):
  - `PR_DESCRIPTION.md`
  - `PR_DESCRIPTION_SECURITY_FIXES.md`
  - `CODE_REVIEW_SECURITY_FIXES.md`
  - `CODE_REVIEW_TECHNICAL_ANALYSIS.md`
  - `FINAL_CODE_REVIEW_SUMMARY.md`
  - `MIGRATION_REPORT_STAGING.md`
  - `REGRESSION_TEST_REPORT_STAGING.md`
  - `SECURITY_FIXES_CONSOLIDATED.md`
  - `SECURITY_FIX_VERIFICATION.md`
  - `SECURITY_FIX_VERIFICATION_UPDATED.md`
  - `SECURITY_AUDIT_INSURANCE_OVERHAUL.md`
  - `PRODUCTION_DEPLOYMENT_INSTRUCTIONS.md`

## [2025-11-20] - Feature Updates

### Added
- Align tap projected pay with payroll settings (#235)
- Simple vs compound interest options with configurable frequency (#233)

### Fixed
- Savings rate input validation error for hidden fields (#231)
- Normalize tap event actions for payroll counts (#230)
- Hall pass network errors and missing status updates (#229)
- Student template redesign to match admin layout (#225, #227)

## [2025-11-19] - Architecture Refactor

### Added
- Comprehensive system architecture documentation
- System admin portal with error logging
- Custom error pages for all major HTTP errors
- GitHub Actions CI/CD to DigitalOcean

### Changed
- Refactored monolithic app.py to modular blueprint architecture

---

## Documentation Maintenance

This changelog tracks significant changes to the codebase. For:
- **Current development tasks**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Planned features**: See [DEVELOPMENT.md](DEVELOPMENT.md) Roadmap section
- **Technical details**: See [docs/technical-reference/architecture.md](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)

## Changelog Guidelines

When adding entries:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Reference PR/issue numbers where applicable
- Use present tense for entries
- Keep entries concise but informative
- Update the date when moving Unreleased to a version
- For any PR touching templates, shared UI shells/components, template CSS, or template-driven JS, record accessibility issues found and accessibility fixes made

**Last Updated:** 2026-01-09
