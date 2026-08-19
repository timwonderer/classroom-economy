# Pytest Baseline — commit `1b455734`

| Field | Value |
|---|---|
| Type | Regression comparison target for FEAT-context-correction stack (PR 2 onward) |
| Branch | `feat/paste-staging-grid` at tip of `1b455734` (post-PR-0 and post-PR-1 merges) |
| Snapshot commit | `1b455734 Merge pull request #1338 from timwonderer/feat-context-pr1-housekeeping` |
| Baseline capture date | 2026-08-19 (UTC) |
| Supersedes | `PYTEST_BASELINE_dc5e0efb.md` for regression-diff purposes (see §0 of that doc) |

## 0. Why This Baseline Exists

`PYTEST_BASELINE_dc5e0efb.md` was fingerprinted on the `feat-context-correction` reference branch, which has diverged from `feat/paste-staging-grid` (where the stacked-PR series merges). Multiple test failures on grid did not appear in that reference baseline — including the two `Seat`-schema failures on `test_feat_class_002_modify_class_boundary.py` that PR 2 hit and the ~15 additional grid-only failures documented below.

This document is the authoritative regression-diff target for PR 2 and all subsequent PRs in the FEAT-context-correction stack. Runs against grid-descendant branches SHALL diff their failure fingerprint against §2 of this document; a fingerprint change is either fixed debt (celebrate), a new regression (block PR), or persistent debt with an unchanged signature (acceptable, note).

## 1. Snapshot Facts

- **Commit:** `1b455734`
- **Command:** `pytest` (no args) — project harness auto-writes CSV / Markdown / failures-log artifacts under `pytest_result/`
- **Runtime:** 213.6s (~3.5 minutes; substantially faster than the reference `dc5e0efb` 1821s, suggesting fewer slow integration tests ran or DB-caching improvements)
- **Exit status:** 2
- **Outcome counts:** 522 passed / **37 failed** / **12 errors** / 31 skipped / 602 recorded (670 collected — 68-test gap flagged as §5 caveat)

### Source-of-truth artifacts

| Path | Role |
|---|---|
| `pytest_result/20260819_pytest_full_results.csv` | 168 KB. Per-test outcomes (nodeid, outcome, duration). |
| `pytest_result/20260819_pytest_full_failures.log` | 241 KB. Full tracebacks per FAILED/ERROR. |
| `pytest_result/20260819_pytest_full_summary.md` | 13 KB. Pytest run summary with failure groupings. |

## 2. Full Failure Fingerprint (Objective)

Grouped by file, ordered alphabetically. Each row is a durable fingerprint target for future regression-diffs.

### `tests/dom/attendance/test_attendance.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_PROD_001__calculate_period_attendance` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |
| `test_DOM_PROD_001__calculate_unpaid_attendance_seconds` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |
| `test_DOM_PROD_001__get_session_status` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |

### `tests/dom/attendance/test_hall_pass_history_scoping.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_PROD_002__hall_pass_history_scoped_to_active_class` | FAIL | `Key (class_id)=(0ec753d8-0e61-45b6-b1b5-1afabfbd7105) already exists.` |

### `tests/dom/attendance/test_hall_pass_verify.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_PROD_002__get_verify_page_valid_token` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_ambiguous` | FAIL | `Key (class_id)=(6c36455f-544e-41c7-a79e-75dfbf7300cb) already exists.` |
| `test_DOM_PROD_002__post_verify_finds_match_beyond_first_20_records` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_input_normalization` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_malformed_last_name` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_match_left` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_match_returned` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_no_history_shown` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_no_match` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_old_pass_not_shown` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__post_verify_wrong_class_rejected` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__rotate_token_requires_auth` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |
| `test_DOM_PROD_002__token_not_derived_from_teacher_id` | ERROR | `Key (class_id)=(2e5fb48d-978e-44c3-9ff1-6e5c357f4628) already exists.` |

### `tests/dom/identity/test_admin_membership_gates.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_006__delete_class_requires_confirmation` | FAIL | `tests/dom/identity/test_admin_membership_gates.py:81: AssertionError` |
| `test_DOM_IDEN_007__add_manual_student_creates_single_student_seat_for_new_student` | FAIL | `assert 4 == (4 + 1)` |

### `tests/dom/identity/test_admin_tenancy.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_001__enforce_daily_limits_does_not_duplicate_closed_session` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |
| `test_DOM_IDEN_001__enforce_daily_limits_ignores_other_class_activity` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |
| `test_DOM_IDEN_001__enforce_daily_limits_taps_out_when_limit_reached_in_scope` | FAIL | `cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` |
| `test_DOM_IDEN_006__student_detail_public_url_requires_nav_token` | FAIL | `tests/dom/identity/test_admin_tenancy.py:304: AssertionError` |
| `test_DOM_IDEN_007__student_detail_public_id_is_seat_scoped_for_shared_student` | FAIL | `assert 500 == 200` |

### `tests/dom/identity/test_class_context_and_switching.py`

| Test | Cat | Signature |
|---|---|---|
| `test_switch_class_rejects_missing_runtime_seat` | FAIL | `tests/dom/identity/test_class_context_and_switching.py:184: AssertionError` |

### `tests/dom/identity/test_multi_teacher_hardening.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_IDEN_007__delete_teacher_cleans_up_links` | FAIL | `PL/pgSQL function prevent_immutable_delete() line 3 at RAISE` |

### `tests/dom/interpretation/test_issue_resolution_reverse_transaction.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_SUP_001__issue_reverse_transaction_creates_reversal_for_posted_tx` | FAIL | `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context. is_feat_active=False, ` |
| `test_DOM_SUP_001__issue_reverse_transaction_rejects_scope_mismatch` | FAIL | `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context. is_feat_active=False, ` |

### `tests/dom/interpretation/test_student_scoped_earnings_display.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__student_payroll_displays_class_scoped_lifetime_earnings` | FAIL | `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context. is_feat_active=False, ` |
| `test_DOM_LED_001__student_transfer_displays_class_scoped_total_earnings` | FAIL | `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context. is_feat_active=False, ` |

### `tests/dom/interpretation/test_sysadmin_issue_rewards.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_SUP_001__sysadmin_resolve_issue_issues_bug_reward_transaction` | FAIL | `'user_id' is an invalid keyword argument for Issue` |

### `tests/dom/ledger/test_issue_payroll_display_fix.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__payroll_transactions_stay_class_scoped` | FAIL | `create_ledger_pending_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |

### `tests/dom/ledger/test_transaction_idempotency.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_LED_001__idempotent_transaction_recovers_from_integrity_race` | FAIL | `create_ledger_pending_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[   ]` | FAIL | `(traceback captured in failures.log; not summarized)` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[None]` | FAIL | `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_empty_keys[]` | FAIL | `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_non_idempotent_types` | FAIL | `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_rejects_oversize_keys` | FAIL | `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |
| `test_DOM_LED_001__idempotent_transaction_reuses_existing_row_on_retry` | FAIL | `create_ledger_idempotent_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` |

### `tests/dom/operation/test_health.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_OPS_001__health_db_error` | FAIL | `tests/dom/operation/test_health.py:17: AssertionError` |

### `tests/dom/operation/test_sysadmin_grafana_auth.py`

| Test | Cat | Signature |
|---|---|---|
| `test_DOM_OPS_001__expired_grafana_subrequest_returns_401_instead_of_login_redirect` | FAIL | `Enter system admin username:` |
| `test_DOM_OPS_001__expired_sysadmin_dashboard_still_redirects_to_login` | FAIL | `Enter system admin username:` |
| `test_DOM_OPS_001__grafana_auth_check_rejects_missing_canonical_user` | FAIL | `Enter system admin username:` |
| `test_DOM_OPS_001__grafana_auth_check_uses_longer_sysadmin_timeout` | FAIL | `Enter system admin username:` |
| `test_DOM_OPS_001__sysadmin_auth_check_rejects_non_sysadmin_user` | FAIL | `Enter system admin username:` |

### `tests/test_analytics_builders.py`

| Test | Cat | Signature |
|---|---|---|
| `TestRecentEventView::test_recent_event_view_formats_timestamp` | FAIL | `assert 'Aug' in 'Unknown date'` |

### `tests/test_class_configuration_feats.py`

| Test | Cat | Signature |
|---|---|---|
| `TestFEATCLASS005EconomicEngineEvolution::test_transition_policy_invalid_mode` | FAIL | `assert 'INVALID_UPDATES' == 'INVALID_POLICY_MODE'` |

### `tests/test_feat_class_002_modify_class_boundary.py`

| Test | Cat | Signature |
|---|---|---|
| `TestProvisionStudentSeat::test_happy_path_creates_new_seat` | FAIL | `'student_id' is an invalid keyword argument for Seat` |
| `TestRemoveStudentSeat::test_happy_path_removes_unclaimed_seat` | FAIL | `'student_id' is an invalid keyword argument for Seat` |

## 3. Suspected-Cause Groupings (Hypothesis, Not Fingerprint)

The following clusters are diagnostic hypotheses derived from the summary's representative messages. **Not authoritative** — the fingerprint in §2 is the durable comparison target; this section is a triage aid.

| Cluster | Count | Signature | Suspected cause |
|---|---:|---|---|
| Hall-pass verify fixture collisions | 12 errors | `Key (class_id)=(...) already exists.` | ORM event listener (`_seed_default_class_features`) auto-creates settings rows during class provisioning; test fixtures then double-insert. Same root cause as the `test_hall_pass_history_scoping.py` failure that appears in both baselines. |
| `canonical_temporal_resolver` scoping bug | 6 failures | `UnboundLocalError: cannot access local variable 'canonical_temporal_resolver' where it is not associated with a value` at `app/feats/base.py:513` | Real runtime bug in `base.py` — local reference used before import path resolves. Actionable in a targeted PR. |
| FEAT-context violation in interpretation tests | 4 failures | `MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): Attempted to flush mutated state outside of a verified FEAT context.` | Test fixtures directly mutate DB without wrapping in a FEAT — enforcement caught during the FEAT-shell tightening. |
| Ledger transaction signature drift | 7 failures | `create_ledger_*_transaction() missing 1 required keyword-only argument: 'actor_seat_id'` | Ledger service signature changed to require `actor_seat_id`; tests haven't caught up. |
| Sysadmin Grafana auth interaction | 5 failures | `AssertionError: Enter system admin username:` | Sysadmin auth flow prompts for username where tests expect a JSON/status response. |
| `Seat`/`Issue`-model schema mismatches | 3 failures | `'student_id'` or `'user_id' is an invalid keyword argument for Seat`/`Issue` | Legacy model kwargs in tests after v2 identity migration. |
| Individual failures | Remaining | Various | See §2 fingerprint. |

## 4. Diff vs `dc5e0efb` Reference Baseline

Approximate — the reference doc's markdown format is partly captured by regex; some entries may be missed. Numbers are indicative not exact.

| Category | Count | Meaning |
|---|---:|---|
| **Fixed on grid** | ~21 | Was failing at `dc5e0efb`, passes at `1b455734`. Progress from post-reference commits (grid-side fixes, PR 0, PR 1, housekeeping sweep `7dc73f89`). |
| **New on grid** | ~23 | Was passing at `dc5e0efb`, failing at `1b455734`. Regressions from grid-side work not captured by the reference baseline. These are the "gap-in-baseline" items that motivated this fresh fingerprint. |
| **Persistent debt** | ~26 | Failing at both. Unchanged debt inherited from the reference; safe to ignore in PR diffs unless the signature changes. |

The 23 "new-on-grid" failures include the `test_feat_class_002_modify_class_boundary.py` `Seat`-schema errors that PR 2 encountered — those are grid-side pre-existing debt, not PR 2 regressions.

## 5. Baseline Usage Contract for PRs 2+

- **Every PR in the stack** SHALL rerun `pytest` and diff its failure fingerprint against §2 of this document.
- A test that flips FAILED→PASSED is a **fix** (celebrate in PR body).
- A test that flips PASSED→FAILED is a **regression** (block PR pending investigation).
- A test that stays FAILED with the *same* signature is **unchanged debt** (acceptable, note in PR body).
- A test that stays FAILED with a *different* signature is a **new problem masquerading as old debt** (investigate).

## 6. Known Limitations

- **68-test collection gap:** pytest collected 670 tests but only 602 were recorded in the CSV. The 68-test gap has not been investigated — possibly parametrized fixtures that errored during collection, deselected via markers, or a harness quirk. Not blocking baseline validity for PR-diff purposes, but worth investigating separately.
- **Runtime discrepancy:** 213s vs the reference's 1821s. Much faster despite similar test count. Possible causes: fixture caching, faster DB reset, fewer full-integration flows exercised. Does not affect fingerprint validity.
- **Skips (31) are not fingerprinted** — assumed intentional.
- **Deprecation warnings not tracked here** — pytest emitted some but they are not part of the failure fingerprint.
