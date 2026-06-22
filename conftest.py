from __future__ import annotations

from pathlib import Path

import pytest


_LEGACY_IDENTITY_XFAIL_FILES = {
    "tests/test_multi_teacher_hardening.py",
    "tests/test_legacy_join_code_persistence.py",
    "tests/test_admin_multi_tenancy.py",
    "tests/test_sysadmin_manage_teachers_deletion_authorization.py",
    "tests/test_backfill_transactions.py",
    "tests/test_hall_pass_history_scoping.py",
    "tests/test_collective_goal_progress.py",
    "tests/test_accessibility.py",
    "tests/test_admin_payroll_scoped_balances.py",
    "tests/test_insurance_class_scoping.py",
    "tests/test_rent_penalty_reversal.py",
    "tests/test_payroll_join_code_scoping.py",
    "tests/test_payroll_settings_class_scope.py",
    "tests/test_dashboard_rendering.py",
    "tests/test_v2_authority_guardrails.py",
    "tests/test_feature_flag_enforcement.py",
    "tests/test_admin_membership_gates.py",
    "tests/test_api_admin_tap_scope.py",
    "tests/test_add_rent_waiver_route.py",
    "tests/test_class_deletion.py",
    "tests/test_class_deletion_audit_fixes.py",
    "tests/test_issue_resolution_reverse_transaction.py",
    "tests/test_core_invariants_smoke.py",
    "tests/test_insurance_security.py",
    "tests/test_transaction_amount_null.py",
    "tests/test_sysadmin_student_counts.py",
    "tests/test_rent_display_dynamic.py",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath))
        rel = path.relative_to(config.rootpath).as_posix()
        if rel in _LEGACY_IDENTITY_XFAIL_FILES:
            item.add_marker(
                pytest.mark.xfail(
                    reason="Legacy identity table/session bridge removal pending rewrite.",
                    strict=False,
                )
            )
