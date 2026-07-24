#!/bin/bash
# scripts/check-student-id-quarantine.sh
# 
# Enforces the student_id quarantine policy.
# Fails the build if `student_id` is found in files outside the approved legacy zones.

set -e

echo "Running student_id quarantine check..."

# Files where student_id is currently load-bearing and allowed for now.
# These will be removed wave-by-wave as we sever legacy dependencies.
ALLOWED_FILES=(
    "app/models.py"
    "app/routes/student.py"
    "app/routes/analytics.py"
    "app/routes/recovery.py"
    "app/routes/system_admin.py"
    "app/routes/admin.py"
    "app/feats/attendance.py"
    "app/feats/admin_adjustment_feat.py"
    "app/__init__.py"
    "app/access/scope_factory.py"
    "app/routes/api.py"
    "app/attendance.py"
    "app/auth.py"
    "app/forms.py"
    "app/scheduled_tasks.py"
    "app/services/attendance_service.py"
    "app/services/balance_service.py"
    "app/services/identity_service.py"
    "app/services/recovery_bridge_service.py"
    "app/services/store_service.py"
    "app/services/tlcp.py"
    "app/utils/analytics_engine.py"
    "app/utils/attendance_helpers.py"
    "app/utils/banking.py"
    "app/utils/deletion.py"
    "app/utils/insurance_eligibility.py"
    "app/utils/issue_helpers.py"
    "app/utils/seat_scope.py"
    "app/utils/student_deletion.py"
    "app/utils/transaction_idempotency.py"
    "tests/.*"
    "migrations/.*"
    "scripts/.*"
    "docs/.*"
    "student_id_audit.md"
    "task.md"
    "cleanup_duplicate_tapouts.py"
    "debug_students.py"
    "delete_faulty_students.py"
    "fix_limbo_students.py"
)

# Build a grep exclusion pattern
EXCLUDE_PATTERN=$(IFS="|"; echo "${ALLOWED_FILES[*]}")

# Find occurrences of 'student_id' in Python files, excluding the allowed ones
VIOLATIONS=$(git grep -n -E 'student_id' -- '*.py' | grep -v -E "($EXCLUDE_PATTERN)" || true)

if [ -n "$VIOLATIONS" ]; then
    echo "ERROR: QUARANTINE VIOLATION DETECTED"
    echo "The following files reference 'student_id' outside the approved legacy zones:"
    echo "$VIOLATIONS"
    echo ""
    echo "Per INV-CORE-000 (Identity Resolution and Student Quarantine), student_id is quarantined."
    echo "New FEATs and routes must use 'class_id' + 'seat_id' as their anchors."
    echo "If you are fixing legacy code, please add the file to ALLOWED_FILES in scripts/check-student-id-quarantine.sh."
    exit 1
fi

echo "Quarantine check passed. No new student_id violations found."
exit 0
