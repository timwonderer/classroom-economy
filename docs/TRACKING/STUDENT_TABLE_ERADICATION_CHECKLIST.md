# Student Table Eradication Checklist

Scope: every remaining `Student` table touchpoint in `app/` and `tests/`, categorized as `remove`, `swap`, or `rewrite`.

Status legend:
- `[ ]` not started
- `[~]` in progress
- `[x]` complete

## Remove

- [ ] Delete legacy `Student` model and compatibility branches in [`app/models.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/models.py)
- [x] Delete legacy student bootstrap / shim logic in [`tests/conftest.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/conftest.py)
- [x] Delete dead legacy student-only helpers in [`app/routes/recovery.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/recovery.py)
- [ ] Delete legacy Student-table-only branches in [`app/routes/student.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/student.py)
- [x] Delete dead legacy query helpers in [`app/routes/admin.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py)
- [x] Delete legacy-compatibility-only tests in [`tests/test_multi_teacher_hardening.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_multi_teacher_hardening.py)
- [x] Delete legacy-compatibility-only tests in [`tests/test_admin_multi_tenancy.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_admin_multi_tenancy.py)
- [x] Delete legacy-compatibility-only tests in [`tests/test_query_inversion_guard.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_query_inversion_guard.py)

## Swap

- [x] Replace student lookup/display reads with `Seat` + `IdentityProfile` in [`app/routes/api.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/api.py)
- [x] Replace student-scoped roster/export reads with `Seat` + `IdentityProfile` in [`app/routes/admin.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py)
- [x] Replace student-period attendance resolution with `Seat` in [`app/attendance.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/attendance.py)
- [x] Replace student-period helper lookups with `Seat` in [`app/utils/attendance_helpers.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/attendance_helpers.py)
- [x] Replace student-scoped balance resolution with `Seat` / `ClassEconomy` in [`app/utils/banking.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/banking.py)
- [x] Replace student-scoped balance helper wrapper with canonical seat/class ids in [`app/routes/student.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/student.py)
- [x] Replace student aggregation with seat-derived mapping in [`app/utils/analytics_engine.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/analytics_engine.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_api_tenancy.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_api_tenancy.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_rent_penalty_reversal.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_rent_penalty_reversal.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_rent_display_dynamic.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_rent_display_dynamic.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_hall_pass_checkout.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_hall_pass_checkout.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_redemption_rejection.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_redemption_rejection.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_redemption_audit_log.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_redemption_audit_log.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_insurance_security.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_insurance_security.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_student_scoped_earnings_display.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_student_scoped_earnings_display.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_collective_goal_progress.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_collective_goal_progress.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_collective_goal_expiration.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_collective_goal_expiration.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_v2_authority_guardrails.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_v2_authority_guardrails.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_tap_flow.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_tap_flow.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_attendance.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_attendance.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_shared_student_attendance.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_shared_student_attendance.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_shared_student_payroll.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_shared_student_payroll.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_admin_export_students_scoping.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_admin_export_students_scoping.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_attendance_log_page.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_attendance_log_page.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_accessibility.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_accessibility.py)
- [x] Replace `student_id` session/login setup with canonical seat context in [`tests/test_feature_settings.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_feature_settings.py)

## Rewrite

- [~] Redesign schema-backed `student_id` columns/relationships in [`app/models.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/models.py)
- [~] Rewrite deletion pipeline around Seat/IdentityProfile ownership in [`app/utils/student_deletion.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/student_deletion.py)
- [~] Rewrite deletion orchestration around canonical identity in [`app/utils/deletion.py`](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/deletion.py)
- [ ] Rewrite student-contract tests that still depend on legacy schema semantics in [`tests/test_rent_item_types.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_rent_item_types.py)
- [x] Rewrite student-contract tests that still depend on `StudentBlock` in [`tests/test_class_deletion.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_class_deletion.py)
- [ ] Rewrite tests that still call `Student` methods directly in [`tests/test_transaction_amount_null.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_transaction_amount_null.py)
- [ ] Rewrite tests that still call `Student` methods directly in [`tests/test_decimal_type_errors.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_decimal_type_errors.py)
- [x] Rewrite tests that still call `Student` methods directly in [`tests/test_transaction_amount_null.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_transaction_amount_null.py)
- [x] Rewrite tests that still call `Student` methods directly in [`tests/test_decimal_type_errors.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_decimal_type_errors.py)
- [x] Rewrite tests that still use `student_id` as a runtime anchor in [`tests/test_tap_event_class_scope_invariant.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_tap_event_class_scope_invariant.py)
- [ ] Rewrite recovery flow tests that still assume student-centric behavior in [`tests/test_flow_credential_reset.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_flow_credential_reset.py)
- [ ] Rewrite student recovery flow tests in [`tests/test_student_recovery.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_student_recovery.py)
- [ ] Rewrite teacher recovery flow tests in [`tests/test_teacher_recovery.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_teacher_recovery.py)
- [ ] Rewrite sysadmin student counting tests in [`tests/test_sysadmin_student_counts.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_sysadmin_student_counts.py)
- [ ] Rewrite admin tenancy tests that still rely on student-shaped fixtures in [`tests/test_admin_tenancy.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_admin_tenancy.py)
- [ ] Rewrite attendance/history tests that still use legacy `student_id` contracts in [`tests/test_api_attendance_history.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_api_attendance_history.py)
- [x] Rewrite namespace-shared student tests that still encode multi-link semantics in [`tests/test_navigation_integrity.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_navigation_integrity.py)

## Progress Checks

- [x] Canonical student identity helper exists in [`tests/helpers/class_scope.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/helpers/class_scope.py)
- [x] Canonical context helper exists in [`tests/helpers/canonical_session.py`](/Users/timothychang/Documents/GitHub/classroom-economy/tests/helpers/canonical_session.py)
- [x] Touched tests now use canonical context helper instead of raw `current_*` writes
- [~] Repo-wide `Student` eradication in `app/` is still incomplete
- [~] Repo-wide `Student` eradication in `tests/` is still incomplete
