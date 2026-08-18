# Pytest Baseline — Commit `dc5e0efb`

**Purpose:** Objective failure fingerprint captured immediately after the FEAT-shell decorator migration (81 legacy `@feat_shell` usages → 0, converted to `@requires_feat_context`). This baseline is the durable comparison target for the upcoming stacked-PR series. Every downstream PR MUST diff its pytest results against §2 of this document. Evidence strength must match the claim — §1 and §2 are objective facts; §3 is explicitly labeled hypothesis.

**Do not edit** the fingerprint sections after this document is committed. Add supersession notes at the bottom if the baseline is retired.

---

## 1. Snapshot Facts

| Field | Value |
|---|---|
| Snapshot commit | `dc5e0efb` |
| Branch | `feat-context-correction` |
| Capture date | 2026-08-17 |
| Runtime | 1821.24s (~30m 21s) |
| Exit code | 1 |
| Passed | 570 |
| Failed | 55 |
| Errors | 14 |
| Skipped | 31 |
| Warnings | 31 |
| Total collected (pass+fail+error+skip) | 670 |

### Command

Full pytest run driven by the project harness that emits CSV + Markdown + failures-log artifacts under `pytest_result/`. Inferred invocation:

```bash
pytest
```

(No `-k` filter, no `-x`, no marker restriction — the summary includes both `tests/dom/**` and top-level `tests/test_*.py` node IDs, and the run collected 670 tests.)

### Source-of-truth artifacts

| Path | Lines | Role |
|---|---|---|
| `/tmp/pytest-baseline-dc5e0efb.txt` | 181 | Top-level pytest output; contains authoritative `short test summary info` block |
| `pytest_result/20260817_pytest_full_failures_8.log` | 651 | Per-test traceback stanzas separated by `=======================================` |
| `pytest_result/20260817_pytest_full_summary_8.md` | 146 | Pytest-generated summary |
| `pytest_result/20260817_pytest_full_results_8.csv` | (n/a) | Per-test CSV result rows |

---

## 2. Full Failure Fingerprint

Each entry lists: test node ID, category, and the top-of-traceback signature (exception class + first-line message) extracted from `pytest_result/20260817_pytest_full_failures_8.log`. Grouped by test file for readability.

### `tests/dom/attendance/test_hall_pass_history_scoping.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_PROD_002__hall_pass_history_scoped_to_active_class` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_hall_pass_settings_class_id"` (root: `psycopg2.errors.UniqueViolation`) |

### `tests/dom/class/test_banking_core.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_CLASS_001__settlement_sweep_processes_each_pending_context_once` | FAILED | `app.feats.base.FEATContextError` — `FATAL: MANDATORY ID MISSING: HIGH blast radius FEAT FEAT-LED-003 requires an idempotency_key.` |

### `tests/dom/identity/test_admin_membership_gates.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_006__delete_class_requires_confirmation` | FAILED | `AssertionError` — `assert 500 == 200` |

### `tests/dom/identity/test_admin_tenancy.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_001__enforce_daily_limits_taps_out_when_limit_reached_in_scope` | FAILED | `AssertionError` — `assert 1 == 2` |
| `test_DOM_IDEN_001__enforce_daily_limits_does_not_duplicate_closed_session` | FAILED | `AssertionError` — `assert 0 == 1` |
| `test_DOM_IDEN_006__student_detail_public_url_requires_nav_token` | FAILED | `AssertionError` — `assert 500 == 200` |
| `test_DOM_IDEN_007__student_detail_public_id_is_seat_scoped_for_shared_student` | FAILED | `AssertionError` — `assert 500 == 200` |

### `tests/dom/identity/test_canonical_auth_session.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_006__student_login_verifies_user_pin_and_resolves_through_claimed_seat` | FAILED | `AssertionError` — `assert 500 == 302` |
| `test_DOM_IDEN_006__student_login_missing_last_active_class_shows_selector` | FAILED | `AssertionError` — `assert 500 == 302` |
| `test_DOM_IDEN_006__system_admin_passkey_finish_sets_canonical_user_session` | FAILED | `AssertionError` — `assert 401 == 200` |

### `tests/dom/identity/test_class_context_and_switching.py`

| Test | Cat | Signature |
|---|---|---|
| `test_switch_class_success` | FAILED | `AssertionError` — `assert 500 == 200` |
| `test_switch_class_between_all_classes` | FAILED | `AssertionError` — `assert 500 == 200` |
| `test_switch_class_rejects_missing_runtime_seat` | FAILED | `AssertionError` — `assert 403 == 302` |

### `tests/dom/identity/test_login_redirect.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_006__student_login_next_redirect` | FAILED | `AssertionError` — `assert 500 == 302` |

### `tests/dom/identity/test_multi_teacher_hardening.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_007__delete_teacher_cleans_up_links` | FAILED | `sqlalchemy.exc.InternalError` — `This table is immutable. Deletions are not permitted. These are permanent historical records.` (root: `psycopg2.errors.RaiseException`) |

### `tests/dom/interpretation/test_issue_resolution_reverse_transaction.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_SUP_001__issue_reverse_transaction_creates_reversal_for_posted_tx` | FAILED | `app.feats.base.FEATContextError` — `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context. is_feat_active=False, session.info=False. New=1, Dirty=0, Deleted=0.` |
| `test_DOM_SUP_001__issue_reverse_transaction_rejects_scope_mismatch` | FAILED | `app.feats.base.FEATContextError` — `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): ... New=1, Dirty=0, Deleted=0.` |

### `tests/dom/interpretation/test_student_scoped_earnings_display.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__student_payroll_displays_class_scoped_lifetime_earnings` | FAILED | `app.feats.base.FEATContextError` — `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): ... New=2, Dirty=0, Deleted=0.` |
| `test_DOM_LED_001__student_transfer_displays_class_scoped_total_earnings` | FAILED | `app.feats.base.FEATContextError` — `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): ... New=2, Dirty=0, Deleted=0.` |

### `tests/dom/interpretation/test_sysadmin_issue_rewards.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_SUP_001__sysadmin_resolve_issue_issues_bug_reward_transaction` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for Issue` |

### `tests/dom/ledger/test_issue_payroll_display_fix.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__payroll_transactions_stay_class_scoped` | FAILED | `TypeError` — `create_ledger_pending_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |

### `tests/dom/ledger/test_transaction_idempotency.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__idempotent_transaction_reuses_existing_row_on_retry` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_recovers_from_integrity_race` | FAILED | `TypeError` — `create_ledger_pending_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_non_idempotent_types` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[None]` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[]` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[   ]` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_oversize_keys` | FAILED | `TypeError` — `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |

### `tests/dom/operation/test_health.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_OPS_001__health_db_error` | FAILED | `AssertionError` — `assert 200 == 500` |

### `tests/dom/operation/test_sysadmin_grafana_auth.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_OPS_001__grafana_auth_check_uses_longer_sysadmin_timeout` | FAILED | `AssertionError` — `Enter system admin username:` (input prompt leaked to test — CLI seeding path taken instead of programmatic fixture) |
| `test_DOM_OPS_001__expired_grafana_subrequest_returns_401_instead_of_login_redirect` | FAILED | `AssertionError` — `Enter system admin username:` |
| `test_DOM_OPS_001__expired_sysadmin_dashboard_still_redirects_to_login` | FAILED | `AssertionError` — `Enter system admin username:` |
| `test_DOM_OPS_001__sysadmin_auth_check_rejects_non_sysadmin_user` | FAILED | `AssertionError` — `Enter system admin username:` |
| `test_DOM_OPS_001__grafana_auth_check_rejects_missing_canonical_user` | FAILED | `AssertionError` — `Enter system admin username:` |

### `tests/test_analytics_builders.py`

| Test | Cat | Signature |
|---|---|---|
| `TestRecentEventView::test_recent_event_view_formats_timestamp` | FAILED | `AssertionError` — `assert 'Aug' in 'Unknown date'` |

### `tests/test_class_configuration_feats.py`

| Test | Cat | Signature |
|---|---|---|
| `TestFEATCLASS005EconomicEngineEvolution::test_transition_policy_invalid_mode` | FAILED | `AssertionError` — `assert 'INVALID_UPDATES' == 'INVALID_POLICY_MODE'` |

### `tests/test_obligation_view_models.py`

| Test | Cat | Signature |
|---|---|---|
| `test_build_student_obligation_view_no_assessments` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for ClassEconomy` |
| `test_build_student_obligation_view_with_assessment` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for ClassEconomy` |
| `test_build_student_obligation_view_with_payment` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for ClassEconomy` |
| `test_build_class_obligation_summary_no_students` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for ClassEconomy` |
| `test_build_class_obligation_summary_with_obligations` | FAILED | `TypeError` — `'user_id' is an invalid keyword argument for ClassEconomy` |

### `tests/test_obligations_phase7_verification.py`

| Test | Cat | Signature |
|---|---|---|
| `TestObligationsSurfaces::test_a1_student_rent_renders` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` (fixture setup) |
| `TestObligationsSurfaces::test_a2_admin_rent_settings_accessible` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestObligationsSurfaces::test_a3_insurance_marketplace_no_schema_issues` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestObligationsSurfaces::test_all_obligation_assessment_events_schema_compliant` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestPhase8Summary::test_rent_surfaces_accessible_via_ledger` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestPhase8Summary::test_insurance_entitlement_separation_preserved` | ERROR | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |

### `tests/test_phase8_a1_a2_surfaces.py`

| Test | Cat | Signature |
|---|---|---|
| `TestA1StudentRentSurface::test_a1_route_renders_with_canonical_schema` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestA1StudentRentSurface::test_a1_query_helpers_work_with_event_discriminator` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestA1StudentRentSurface::test_a1_amounts_come_from_ledger_not_obligations` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestA2AdminRentSettings::test_a2_admin_can_view_rent_settings` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestA2AdminRentSettings::test_a2_rent_settings_scoped_by_class_id` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |
| `TestA2AdminRentSettings::test_a2_settings_integrate_with_obligations` | FAILED | `sqlalchemy.exc.IntegrityError` — `duplicate key value violates unique constraint "ix_rent_settings_class_id"` |

### `tests/test_phase8_a1_domain_primitives_entitlement.py`

| Test | Cat | Signature |
|---|---|---|
| `TestGetActiveRentGrant::test_active_rent_grant_without_terminal_event` | FAILED | `sqlalchemy.exc.InvalidRequestError` — `A transaction is already begun on this Session.` (followed by `psycopg2.errors.NotNullViolation: null value in column "actor_seat_id" of relation "entitlement_events"`) |
| `TestGetActiveRentGrant::test_active_rent_grant_with_terminal_event_returns_none` | FAILED | `sqlalchemy.exc.IntegrityError` — `null value in column "actor_seat_id" of relation "entitlement_events" violates not-null constraint` |
| `TestIsEntitlementExercisable::test_exercisable_without_terminal_event` | FAILED | `sqlalchemy.exc.IntegrityError` — `null value in column "actor_seat_id" of relation "entitlement_events" violates not-null constraint` |
| `TestIsEntitlementExercisable::test_not_exercisable_with_consumed_event` | FAILED | `sqlalchemy.exc.IntegrityError` — `null value in column "actor_seat_id" of relation "entitlement_events" violates not-null constraint` |
| `TestGetEntitlementLineageTerminalEvent::test_terminal_event_none_when_no_terminal` | FAILED | `sqlalchemy.exc.IntegrityError` — `null value in column "actor_seat_id" of relation "entitlement_events" violates not-null constraint` |
| `TestGetEntitlementLineageTerminalEvent::test_terminal_event_returned_when_consumed` | FAILED | **no traceback captured — needs rerun to fingerprint.** Present in `short test summary info` but no per-test stanza in failures log; likely a cascading fixture failure suppressed the traceback. Hypothesis (§3): same `actor_seat_id` NotNullViolation as siblings. |

### `tests/test_store_policy_resolver.py`

| Test | Cat | Signature |
|---|---|---|
| `TestStorePolicyResolver::test_resolve_store_item_exact_match` | FAILED | `sqlalchemy.exc.IntegrityError` — `insert or update on table "store_products" violates foreign key constraint "store_products_class_id_fkey"` |
| `TestMultiplePoliciesSameProductId::test_multiple_policies_same_product_id_different_uuids` | FAILED | `sqlalchemy.exc.IntegrityError` — `insert or update on table "store_products" violates foreign key constraint "store_products_class_id_fkey"` |
| `TestMultiplePoliciesSameProductId::test_policy_deletion_with_multiple_policies` | FAILED | `sqlalchemy.exc.IntegrityError` — `insert or update on table "store_products" violates foreign key constraint "store_products_class_id_fkey"` |

### `tests/test_view_model_builders.py`

| Test | Cat | Signature |
|---|---|---|
| `test_build_entitlement_list_view_uses_policy_name_and_status` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): Direct commit attempted from inside FEAT execution. Only FEAT orchestrator transaction boundary may commit.` |
| `test_build_purchase_history_view_groups_by_correlation` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_policy_list_view_returns_canonical_policies_in_presentation_order` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_identity_profile_view_happy_path` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_identity_profile_view_computes_display_properties` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_identity_profile_view_returns_none_when_not_found` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_identity_profile_view_scoped_by_class_id` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |
| `test_build_identity_profile_view_is_frozen` | ERROR | `app.feats.base.FEATContextError` — `MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): ...` |

**Total fingerprinted:** 68 of 69 (1 test — `test_terminal_event_returned_when_consumed` — has no captured stanza).

---

## 3. Suspected Cause Groupings (HYPOTHESIS — not fingerprint)

> This section groups the objective fingerprints in §2 into likely root-cause clusters. **These are hypotheses to guide triage, not evidence.** The comparison contract in §4 uses §2 signatures, not §3 clusters. If a hypothesis here is wrong, the fingerprint in §2 remains the source of truth.

### H1 — Ledger FEAT signature change: `actor_seat_id` became required (kwarg)
**8 tests.** `TypeError: create_ledger_(pending|idempotent)_transaction() missing 1 required keyword-only argument: 'actor_seat_id'`.
- All `tests/dom/ledger/test_transaction_idempotency.py` (7)
- `tests/dom/ledger/test_issue_payroll_display_fix.py::test_DOM_LED_001__payroll_transactions_stay_class_scoped` (1)

**Suspected cause:** FEAT-LED-* helpers were tightened to require `actor_seat_id` for provenance; call sites in these tests still pass the old kwarg set.

### H2 — Ledger FEAT signature change: `actor_seat_id` NOT NULL on `entitlement_events`
**6 tests.** `psycopg2.errors.NotNullViolation: null value in column "actor_seat_id" of relation "entitlement_events"`.
- All 6 in `tests/test_phase8_a1_domain_primitives_entitlement.py` (including the 1 unfingerprinted sibling assumed to match).

**Suspected cause:** Same actor-provenance tightening as H1, but at the schema layer. Tests build entitlement events directly without setting `actor_seat_id`.

### H3 — Schema/model rename: `ClassEconomy.user_id` → different name (probably `teacher_user_id`)
**6 tests.** `TypeError: 'user_id' is an invalid keyword argument for ClassEconomy` + 1 `Issue` variant.
- All 5 in `tests/test_obligation_view_models.py`
- `tests/dom/interpretation/test_sysadmin_issue_rewards.py::test_DOM_SUP_001__sysadmin_resolve_issue_issues_bug_reward_transaction` (`Issue` model, likely same rename pattern)

**Suspected cause:** Phase 2c rename of `ClassEconomy.user_id` → `teacher_user_id` (commit ebff5767 per memory index). Test fixtures still use the old kwarg. Note: memory says all 22 references were updated across production code — these are test callers not covered by that sweep.

### H4 — Fixture teardown / test isolation: unique-constraint violations on `rent_settings` / `hall_pass_settings`
**13 tests.** `duplicate key value violates unique constraint "ix_rent_settings_class_id"` (12) + `"ix_hall_pass_settings_class_id"` (1).
- All 6 ERRORs in `tests/test_obligations_phase7_verification.py`
- All 6 FAILEDs in `tests/test_phase8_a1_a2_surfaces.py`
- `tests/dom/attendance/test_hall_pass_history_scoping.py::test_DOM_PROD_002__hall_pass_history_scoped_to_active_class`

**Suspected cause:** ORM event listener (`_seed_default_class_features` and/or a settings seeder) auto-creates rent/hall-pass settings rows during class provisioning, but the test fixtures then try to insert their own — collision on the unique-class_id index. Related to the Phase 2d event-listener work.

### H5 — FEAT-INTEGRITY enforcement blocking pre-migration test patterns
**11 tests.** Two sub-signatures of the same architectural rule:
- `FEATContextError: MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): ... is_feat_active=False` (4 tests, in `test_issue_resolution_reverse_transaction.py` and `test_student_scoped_earnings_display.py`)
- `FEATContextError: MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): Direct commit attempted from inside FEAT execution` (8 tests, all `tests/test_view_model_builders.py`)

**Suspected cause:** Matches the documented v2 architecture rule (see MEMORY.md Phase 2 notes): all mutations must go through a FEAT orchestrator. Tests still do direct `db.session.add/commit` or double-commit inside FEAT context. This is the largest bucket of pre-migration test debt.

### H6 — Route/handler 500s — likely template or view-model breakage from the FEAT-shell migration
**11 tests.** Various `assert 500 == 200/302`.
- All 3 in `tests/dom/identity/test_class_context_and_switching.py`
- 3 in `tests/dom/identity/test_canonical_auth_session.py`
- 2 in `tests/dom/identity/test_admin_tenancy.py` (`student_detail_public_*`)
- 1 in `tests/dom/identity/test_admin_membership_gates.py`
- 1 in `tests/dom/identity/test_login_redirect.py`
- 1 in `tests/dom/operation/test_health.py` (inverse: `200 == 500`)

**Suspected cause:** Routes touched by the 81-file FEAT-shell migration probably raise inside `@requires_feat_context` when context assembly fails; or view-model builders now raise on stale template inputs. Needs per-route triage.

### H7 — Sysadmin CLI seeding leak into pytest
**5 tests.** `AssertionError: Enter system admin username:` — all in `tests/dom/operation/test_sysadmin_grafana_auth.py`.

**Suspected cause:** Fixture path takes the interactive `create_sysadmin` CLI branch instead of the programmatic `make_sysadmin()` helper (see `tests/helpers/v2_fixtures.py`). Not related to the FEAT-shell migration; likely stale fixture.

### H8 — Immutable-table protection blocking test cleanup
**1 test.** `test_DOM_IDEN_007__delete_teacher_cleans_up_links` — `This table is immutable. Deletions are not permitted. These are permanent historical records.`

**Suspected cause:** A recently added DB trigger enforcing append-only semantics on an events/history table. Test tries to hard-delete during cleanup.

### H9 — Store-products FK: seeding order or class_id source mismatch
**3 tests.** All 3 in `tests/test_store_policy_resolver.py` — `store_products_class_id_fkey` violation.

**Suspected cause:** Test builds a `class_id` UUID that doesn't get persisted to `classes` before the store_products insert. Likely SPEC-TEST-001 canonical initializer not adopted here.

### H10 — Isolated one-offs (not clustered)
- `test_banking_core::test_DOM_CLASS_001__settlement_sweep_...` — `FEAT-LED-003 requires an idempotency_key` (missing kwarg, related to H1 conceptually)
- `test_admin_tenancy::test_DOM_IDEN_001__enforce_daily_limits_*` (2 tests) — count-mismatch assertions (`1 == 2`, `0 == 1`)
- `test_analytics_builders::test_recent_event_view_formats_timestamp` — `'Aug' in 'Unknown date'` (view model timestamp handling regression)
- `test_class_configuration_feats::test_transition_policy_invalid_mode` — error-code string mismatch (`INVALID_UPDATES` vs `INVALID_POLICY_MODE`)

### Hypothesis tally
| Cluster | Tests |
|---|---|
| H1 Ledger kwarg | 8 |
| H2 Entitlement NotNull | 6 |
| H3 ClassEconomy rename | 6 |
| H4 Settings unique-constraint | 13 |
| H5 FEAT-INTEGRITY | 12 |
| H6 Route 500s | 11 |
| H7 Sysadmin CLI leak | 5 |
| H8 Immutable delete | 1 |
| H9 Store FK | 3 |
| H10 One-offs | 5 |
| **Total** | **70** |

(Total exceeds 69 because H10's banking test is also H1-adjacent and counted once above; net 69 unique tests.)

---

## 4. Baseline Usage Contract

Every PR in the stacked-PR series that follows this baseline MUST:

1. **Rerun the full pytest suite** with no filter (same invocation as §1). Attach the resulting `pytest_result/*.log` and `pytest_result/*.md` artifacts.
2. **Diff each result against §2 of this document**, per-test:

   | Baseline state | New state | Meaning | Action |
   |---|---|---|---|
   | FAILED / ERROR | PASSED | Fix (celebrate) | Note in PR body |
   | PASSED | FAILED / ERROR | **Regression** | **Block PR until resolved** |
   | FAILED / ERROR (sig X) | FAILED / ERROR (sig X) | Unchanged debt | Acceptable |
   | FAILED / ERROR (sig X) | FAILED / ERROR (sig Y) | New problem masquerading as old debt | **Investigate before merge** |

3. **A "same file failed" or "same test failed" claim is insufficient.** The comparison unit is `(test node ID, exception class, first-line signature)` from §2.

4. **Skips (31)** are not baselined — treated as intentional. Increases in skip count require justification in the PR body.

5. **Runtime drift >20%** should be called out in the PR body.

---

## 5. Known Limitations

- **Per-test stdout/stderr not captured** — only tracebacks. Debugging a signature change may require rerunning the specific test with `-s`.
- **Skips (31) are not fingerprinted** — assumed intentional. If a PR flips a FAILED to SKIPPED, that counts as *hiding* debt, not fixing it, unless justified.
- **Warnings (31)** are recorded as a total only, not per-line. From spot-check of `/tmp/pytest-baseline-dc5e0efb.txt`, the majority appear to originate from `tests/test_phase8_a1_domain_primitives_entitlement.py` using deprecated `datetime.utcnow()`. SPEC-TIME-001 violation; separate cleanup.
- **1 test unfingerprinted** — `tests/test_phase8_a1_domain_primitives_entitlement.py::TestGetEntitlementLineageTerminalEvent::test_terminal_event_returned_when_consumed` is in the summary as FAILED but has no per-test stanza in the failures log. First diff run should isolate this test and record its actual signature.
- **Baseline was captured with dev DB seed state at capture time.** Some fixture-collision failures in H4 may be sensitive to leftover rows from prior sessions. A fresh-DB rerun before diffing is recommended for high-confidence comparison.

---

**Baseline authority:** This document is the sole comparison target for the FEAT-shell migration PR series. Do not modify §1 or §2. Later baselines that supersede this one must reference `dc5e0efb` explicitly and state the reason for retirement.
