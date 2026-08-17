# V2 Canonical Schema Rebuild Plan

## Context

`docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` (Constitutional, 2026-04-25) declares the **only valid runtime tables** for v2. The current schema (`app/models.py`, ~60 models, 80+ migrations) diverges materially: `students`/`teachers` violate INV-IDEN-001; `transaction`/`balance_cache` violate INV-LED-001/010; the entire Obligations, Operations, and Interpretation domains are unimplemented; 33 tables have nullable `class_id`; 9 tables use `block`/`period` labels as scoping authorities. Full divergence inventory in `docs/TRACKING/V2_SCHEMA_COMPLIANCE_AUDIT.md` (compliance ~55/100).

V2 will launch on an empty database. There is no production data, no live users, and no upgrade path to preserve. This plan is a **clean-slate rebuild** to DOM-CORE-002 compliance with no transition scaffolding, no backfill logic, and no compatibility shims. Auxiliary capabilities not listed in DOM-CORE-002 §V (sysadmin role, invite codes, recovery flow, analytics caches) are folded into canonical tables and DOM-CORE-002 is amended to v1.1 to declare those composition rules. The Alembic chain is squashed to a single bootstrap migration.

Outcome: `app/models.py` matches DOM-CORE-002 exactly; one migration file; all routes/feats/services/templates/tests realigned to seat-anchored, class-scoped, domain-blind authority.

---

## Wave 0 — Constitutional Amendment & Lock

Before any code: lock the contract.

- **Amend `DOM-CORE-002` to v1.1**, adding under §V:
  - DOM-IDEN-001: `users.user_role ∈ {STUDENT, TEACHER, SYSADMIN}` covers sysadmin; add `user_invite_tokens` (composition table for teacher provisioning) and `user_recovery_tokens` (composition table for credential recovery).
  - DOM-CLASS-001: declare `payroll_rewards` and `payroll_fines` as composition tables of `payroll_settings` (child rows expressing the parent's directive), not independent class-config tables.
  - DOM-OPS-001: replace `payroll_cache` and any read-side caches with snapshot derivations under `operational_events` or computed-on-read services. No persisted compute caches.
  - DOM-SUP-001: add `user_reports` as canonical (already domain-aligned).
  - DOM-ITR-001: explicitly subsume `economy_snapshots` semantics under `interpretation_snapshots.axis = STRUCTURAL`.
- Update `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md` to reflect v1.1 composition rules.
- Snapshot the final canonical table list as the single source of truth — every subsequent wave verifies against it.

**Critical files:**
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- New: `docs/TRACKING/V2_CANONICAL_REBUILD_PLAN.md` (this plan, summarized)

---

## Wave 1 — `app/models.py` Canonical Rewrite

Complete replacement of `app/models.py`. No incremental edits.

**Delete entirely:** `Admin`, `Student`, `StudentTeacher`, `ClassMembership`, `TeacherBlock`, `Transaction`, `BalanceCache`, `TapEvent`, `StudentBlock`, `RentPayment`, `RentWaiver`, `RentItem`, `InsurancePolicy`, `InsurancePolicyBlock`, `StudentInsurance`, `InsuranceClaim`, `StoreItemBlock`, `StudentItem`, `RedemptionAuditLog`, `ErrorLog`, `ErrorEvent`, `ActorRequestTrace`, `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`, `EconomySnapshot`, `SystemAdmin`, `AdminCredential`, `SystemAdminCredential`, `AdminInviteCode`, `RecoveryRequest`, `StudentRecoveryCode`, `TeacherOnboarding`, `PayrollCache`.

**Build per DOM-CORE-002 §V:**

1. **Identity** (DOM-IDEN-001): `User`, `Seat`, `Class` (renamed from `class_economies`), `IdentityProfile`, `UserInviteToken`, `UserRecoveryToken`. `User.user_role` ∈ {STUDENT, TEACHER, SYSADMIN}; `Seat.role` ∈ {STUDENT, TEACHER}. Drop all `block`/`block_identifier`/`period` columns. `Seat.class_id` NOT NULL. No `student_id`/`teacher_id`/`admin_id` foreign keys anywhere.
2. **Class Configuration**: `ClassFeature`, `FeatureSettings`, `HallPassSettings`, `RentSettings`, `PayrollSettings` (with composition children `PayrollReward`, `PayrollFine`), `BankingSettings`. `class_id` NOT NULL on every row; uniqueness on `(class_id)` alone; no `teacher_id` columns.
3. **Attendance** (DOM-ATT-001): `AttendanceSession` (renamed from `tap_events`, append-only, `seat_id` NOT NULL, no soft-delete fields), `HallPassLog` (`seat_id` NOT NULL), `SeatAttendanceState` (`seat_id` UNIQUE FK, `tap_enabled`, `done_for_day_date`).
4. **Obligations** (DOM-OBL-001): `AssessmentEvent`, `ObligationLifecycle`, `ObligationSatisfaction`, `ObligationReversal`, `EntitlementEvent`. All `seat_id` NOT NULL, `class_id` NOT NULL, `idempotency_key` NOT NULL. Insurance enrollment + claims expressed as `ObligationLifecycle` rows + `EntitlementEvent` streams; no separate `insurance_*` tables.
5. **Ledger** (DOM-LED-001): `LedgerTransaction` and `LedgerBalanceSnapshot` only. `LedgerTransaction`: `seat_id` NOT NULL, `amount_cents` signed Integer, `status ∈ {PENDING, POSTED, VOID}`, `category ∈ {SYSTEM, MANUAL, ADJUSTMENT}`, `correlation_id` NOT NULL, `idempotency_key` NOT NULL UNIQUE, `original_transaction_id` nullable FK. **No** `join_code`, `class_id`, `teacher_id`, `account_type`, `policy_id`, `type`, `is_void`, or `feat_code` columns. `LedgerBalanceSnapshot`: `seat_id` PK, single `posted_balance_cents`, `last_event_id` FK to `ledger_transaction`.
6. **Store** (DOM-STORE-001): `StoreItem` (`class_id` NOT NULL, no `teacher_id`), `StoreItemVisibility` (`store_item_id`, `seat_id`), `StorePurchase` (renamed from `student_items`, `seat_id` NOT NULL), `RedemptionEvent` (renamed from `redemption_audit_logs`, `initiated_by_user_id` FK → `users`).
7. **Operations** (DOM-OPS-001): All 8 tables — `operational_events`, `audit_log`, `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`, `health_check_events`. Each carries `correlation_id`, `domain`, `level`, optional `seat_id`/`class_id`. `actor_request_traces` retired into `operational_events` correlated rows.
8. **Interpretation** (DOM-ITR-001): `InterpretationSnapshot` (`class_id` NOT NULL, `axis ∈ {BEHAVIORAL, STRUCTURAL}`, `cycle_id`, `value_payload` JSONB), `InterpretationAnnotation`. Read-only domain — no FEAT writes outside scheduled snapshot jobs.
9. **Support** (DOM-SUP-001): `IssueCategory`, `Issue` (`seat_id` NOT NULL, `created_by_user_id` FK → users, no `student_id`/`teacher_id`), `IssueStatusHistory`, `IssueResolutionAction` (`performed_by_user_id`), `TicketCorrelationPack`, `UserReport`, `Announcement` (`created_by_user_id`, `target_user_id`).

**Critical files:**
- `app/models.py` — full rewrite

---

## Wave 2 — Single Bootstrap Migration

- Delete every file in `migrations/versions/` (80+ files).
- `alembic_version` table: drop and recreate empty.
- Run `flask db migrate -m "v2_canonical_schema"` against the new `app/models.py`.
- Apply DOM-CORE-002 invariants directly in the generated migration:
  - All `class_id`/`seat_id` columns NOT NULL.
  - Unique constraints anchored on `class_id` alone for class-config tables.
  - `idempotency_key` UNIQUE NOT NULL on every mutation table.
  - Append-only enforcement on `attendance_sessions`, `ledger_transaction`, all `_events` tables (no `is_deleted`/soft-delete columns).
- Add `migrations/migration_template.py.mako` idempotency helpers.
- Update `migrations/env.py` if the model registry import path changes.

**Critical files:**
- `migrations/versions/0001_v2_canonical_schema.py` (single new file)
- `migrations/env.py`

---

## Wave 3 — Auth & Identity Layer

`app/auth.py` is fundamentally incompatible with the canonical model and must be rewritten.

- Replace all `Admin`/`Student`/`SystemAdmin` lookups with `User` queries scoped by `user_role`.
- Replace `_find_admin_by_auth_username`, `get_admin_student_query`, `get_student_for_admin` with seat-resolving helpers: `get_user_by_username_lookup_hash`, `get_active_seat_for_user_in_class`, `get_class_seats(class_id, role)`.
- Login flow: authenticate `User` → resolve list of `Seat` rows (one per class user is bound to) → user picks active seat → session stores `user_id` + `active_seat_id` + `active_class_id`.
- Recovery flow: `UserRecoveryToken` table (composition under DOM-IDEN-001 v1.1), single `users.totp_secret_encrypted`, `users.passphrase_hash`. No `recovery_requests`/`student_recovery_codes` split.
- `@admin_required` / `@student_required` / `@sysadmin_required` decorators check `User.user_role` plus `Seat.role` for class-scoped routes.
- Reuse existing utilities in `hash_utils.py` (`hash_password`, `verify_password`, `encrypt_value`, `decrypt_value`, `hash_hmac`) — no rewrite needed there.

**Critical files:**
- `app/auth.py` — full rewrite
- `app/routes/recovery.py` — rewrite around `UserRecoveryToken`
- `app/routes/system_admin.py` — switch to `User` with `user_role=SYSADMIN`

---

## Wave 4 — Service Layer Realignment

All services in `app/services/` currently mix `student_id`, `teacher_id`, `join_code`, and `seat_id`. Rewrite to seat-anchored, class-scoped reads.

- `ledger_service.py`: read from `LedgerTransaction` by `seat_id` only; balances from `LedgerBalanceSnapshot` by `seat_id` PK. Remove all `account_type` logic — single posted balance per seat.
- `balance_service.py`: settlement engine writes to `LedgerBalanceSnapshot` keyed by `seat_id`.
- `attendance_service.py`: queries `AttendanceSession` by `seat_id`; mutates `SeatAttendanceState` only via FEAT.
- `obligations_service.py`: rewrite around the five obligation event tables. `EntitlementEvent` stream replaces scalar `rent_hall_passes`.
- `store_service.py`: catalog reads by `class_id`; visibility via `StoreItemVisibility` per-seat; purchases write `StorePurchase` + emit `LedgerTransaction` via FEAT.
- `identity_service.py`: rewrite to operate on `User`/`Seat`/`IdentityProfile`.
- `access_policy_service.py`: capability checks based on `User.user_role` + `Seat.role`.
- `tlcp.py`: realign correlation-pack inputs to `operational_events`.

**Critical files:** all of `app/services/*.py`.

---

## Wave 5 — FEAT Layer Audit

Every FEAT in `app/feats/` mutates one or more domains. Each must be rewritten to seat-anchored, idempotency-keyed, single-transaction execution per `FEAT-CORE-000`.

- `transfer_feat.py`: `from_seat_id` + `to_seat_id` (must share `class_id`); two `LedgerTransaction` rows with shared `correlation_id`; idempotency via composite key.
- `store_purchase_feat.py`: validates `StoreItemVisibility` for buyer's seat; writes `StorePurchase` + `LedgerTransaction` (category=SYSTEM); emits `EntitlementEvent` if item grants entitlement (e.g., hall passes).
- `rent_payment_feat.py`: writes `ObligationSatisfaction` + `LedgerTransaction`. Late/waiver paths express via `ObligationSatisfaction.method ∈ {PAYMENT, WAIVER}`.
- `transaction_void_feat.py`: writes new `LedgerTransaction` row with `original_transaction_id` set, `category=ADJUSTMENT`. Original row remains POSTED (immutability per INV-LED-002).
- `insurance_purchase_feat.py`: opens `ObligationLifecycle` (premium schedule) + writes initial `ObligationSatisfaction`.
- `insurance_claim_feat.py`: writes `EntitlementEvent` (claim issuance) + `LedgerTransaction` (payout, category=SYSTEM).
- `admin_adjustment_feat.py`: writes `LedgerTransaction` with `category=ADJUSTMENT`.
- `app/feats/base.py` (`requires_feat_context`): tighten to require `actor_user_id`, `actor_seat_id`, `class_id`, `idempotency_key`; emit a single `OperationalEvent` + `AuditLog` row per execution.

**Critical files:** all of `app/feats/*.py`.

---

## Wave 6 — Routes Sweep

Refactor every route to use the new identity/seat/class context. The largest blast radius:

- `app/routes/admin.py` (~3000 lines, primary refactor target): replace `_student_scope_subquery_for_join_code` with `get_class_seats(class_id, role=STUDENT)`. Every roster query, payroll trigger, store CRUD, settings page rewires from `teacher_id + join_code` to `class_id`.
- `app/routes/student.py`: session context becomes `(user_id, active_seat_id, active_class_id)` via `get_current_class_context()`. Balance/transactions read via seat. `select_class` chooses a `Seat` row.
- `app/routes/api.py`: every endpoint that returns student data is seat-anchored.
- `app/routes/main.py`: drop legacy hall-pass routes; landing pages stay.
- `app/routes/analytics.py`: read from `InterpretationSnapshot`.
- `app/routes/system_admin.py`: scope to `User.user_role=SYSADMIN`.
- `app/routes/docs.py`: no schema impact.
- `app/payroll.py`: rewrite payroll runner to iterate `Seat`s by `class_id`, write `LedgerTransaction` rows via `payroll_feat` (new FEAT to add). Remove `PayrollCache` reads — recompute on demand.
- `app/scheduled_tasks.py`: align nightly jobs to canonical tables; remove legacy `join_code` backfill stub.

**Critical files:**
- `app/routes/admin.py`, `app/routes/student.py`, `app/routes/api.py`, `app/routes/main.py`, `app/routes/analytics.py`, `app/routes/system_admin.py`, `app/routes/recovery.py`
- `app/payroll.py`
- `app/scheduled_tasks.py`
- `app/utils/seat_scope.py` — promote to single source of class/seat resolution

---

## Wave 7 — Templates & Forms

Templates currently reference `student.first_name`, `student.id`, `block`, `join_code`, etc. Rewire to seat-centric data shapes.

- All `student.*` template variables → `seat.identity_profile.*`.
- `block` / `period` displays remain (metadata only) but must not drive form `name=` attributes used as scoping keys.
- Forms in `app/forms.py`: drop `block` selectors as scoping keys (keep as display labels). Add `class_id` hidden fields where the active class isn't already in session.

**Critical files:**
- `templates/**/*.html`
- `app/forms.py`

---

## Wave 8 — Test Suite Rebuild

The 740+ existing tests are tightly coupled to the deprecated schema. Rewrite around canonical fixtures.

- New `tests/conftest.py` factories: `make_user(role)`, `make_class()`, `make_seat(user, class, role)`, `make_identity_profile(seat)`, `make_store_item(class)`, `post_ledger_transaction(seat, amount, ...)`. Drop all `make_admin`/`make_student` factories.
- Coverage targets per `.claude/rules/testing.md`: every FEAT, every route, every service. Multi-tenancy tests verify `class_id` scoping (cross-class isolation impossible via API). Idempotency tests verify FEAT replay safety.
- Run full suite green before marking the wave complete (current baseline `619/123 failed` is irrelevant — test files are being replaced).

**Critical files:**
- `tests/conftest.py` — full rewrite
- `tests/test_*.py` — replace as needed (delete tests for deprecated tables)

---

## Wave 9 — Documentation Sync

- Rewrite `docs/technical-reference/database_schema.md` from DOM-CORE-002 §V.
- Update `.claude/CLAUDE.md` "Database Models" section to list only canonical tables.
- Update `.claude/rules/multi-tenancy.md` examples to use `class_id` + `seat_id` exclusively (drop `join_code`-as-scope examples).
- Retire `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md`, `V2_Class_Scope_Normalization_Target.md`, `V2_STUDENT_BLOCKS_REDESIGN_NOTE.md`, `V2_ADMIN_ROUTE_REFACTOR.md` — all superseded by this rebuild. Move to `docs/archive/v1-development/`.
- Mark `V2_SCHEMA_COMPLIANCE_AUDIT.md` superseded; replace with a fresh post-rebuild audit confirming 100% DOM-CORE-002 compliance.
- Update `CHANGELOG.md` under `[Unreleased] — Version 2.0` with a single "BREAKING: Canonical schema rebuild per DOM-CORE-002" entry.

---

## Verification

End-to-end gates, in order:

1. **Schema lock**: `flask db upgrade` from empty → schema matches DOM-CORE-002 §V exactly. Run `python scripts/lint_migrations.py migrations/versions/0001*.py` (linter must pass). Run a custom audit script that lists every `Table.__tablename__` and asserts membership in the DOM-CORE-002 canonical set.
2. **Idempotency / append-only invariants**: write a smoke test that attempts to UPDATE/DELETE on `ledger_transaction`, `attendance_sessions`, and any `_events` table — must fail at the DB layer (CHECK constraint or trigger).
3. **Cross-class isolation**: integration test creates two classes with one shared user (two seats); verifies that data in class A is never visible from class B's session, even when same `user_id` is logged in.
4. **FEAT idempotency**: replay every FEAT with the same `idempotency_key` — second invocation must be a no-op with the original result returned.
5. **Domain blindness**: grep `app/services/ledger_service.py` and `app/feats/*` for forbidden tokens (`account_type`, `policy_id` on ledger row, `insurance_*` on `LedgerTransaction`, `join_code` on ledger queries) — all must be absent.
6. **Full pytest run**: target green from a fresh `flask db upgrade`. No xfails, no skips outside genuinely-platform-specific tests.
7. **Manual smoke**: `flask run` → teacher creates class → uploads roster → student claims seat → completes a transfer / store purchase / rent payment / hall-pass cycle. Inspect `operational_events` and `audit_log` for correct correlation_id propagation.
8. **Compliance re-audit**: regenerate `V2_SCHEMA_COMPLIANCE_AUDIT.md` against canonical schema; expected score 100/100 with zero MISSING / DEPRECATED / DIVERGENT entries.
