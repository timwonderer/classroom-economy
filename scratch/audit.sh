#!/bin/bash
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/classroom_economy_v2_test

echo "A1: Table Structure Validation"
psql $TEST_DATABASE_URL -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('attendance_sessions','hall_pass_logs','payroll_event') ORDER BY tablename;"

echo "A2: AttendanceSession Column Validation"
psql $TEST_DATABASE_URL -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='attendance_sessions' ORDER BY ordinal_position;"

echo "A3: HallPassLog Column Validation"
psql $TEST_DATABASE_URL -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='hall_pass_logs' ORDER BY ordinal_position;"

echo "A4: PayrollEvent Column Validation"
psql $TEST_DATABASE_URL -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='payroll_event' ORDER BY ordinal_position;"

echo "B1: FEAT-PROD-001 (record_attendance_session)"
grep -r "AttendanceSession(" app/routes/ app/services/ --include="*.py" | grep -v "FEAT\|record_attendance_session\|test" | grep -v "\.#"

echo "B3: FEAT-PROD-002 (record_hall_pass_log)"
grep -r "HallPassLog(" app/routes/ app/services/ --include="*.py" | grep -v "record_hall_pass_log\|test\|#"

echo "B5: FEAT-PROD-003 (record_payroll_event)"
grep -r "PayrollEvent(" app/routes/ app/services/ --include="*.py" | grep -v "record_payroll_event\|test" | grep -v "#"

echo "C1: Student Dashboard Template"
grep -i "student_blocks\|period_states\|data-period\|data-block" templates/student_dashboard.html

echo "E1: Class Scoping Verification"
echo "AttendanceSession queries:"
grep -r "AttendanceSession.query" app/ --include="*.py" | grep -v "test\|#" 
echo "HallPassLog queries:"
grep -r "HallPassLog.query" app/ --include="*.py" | grep -v "test\|#"
echo "PayrollEvent queries:"
grep -r "PayrollEvent.query" app/ --include="*.py" | grep -v "test\|#"

echo "E2: Verify No Teacher-Only Scoping"
grep -r "filter_by(teacher_id" app/routes/ app/feats/ --include="*.py" | grep -E "AttendanceSession|HallPassLog|PayrollEvent"

echo "E3: Block/Period Rejection"
grep -r "\.block\|period.*=\|data-block\|data-period" app/routes/ app/services/ --include="*.py" | grep -v "test\|#\|display\|section"

echo "F1: Student Dashboard Template matches"
grep -E "student_blocks|period_states|data-period|data-block|student.block" templates/student_dashboard.html
grep -E "attendance_state_json|hall_pass_balance|current_class_id" templates/student_dashboard.html

echo "F2: Student Payroll Template"
grep -E "student_blocks|period_states|unpaid_seconds_per_block" templates/student_payroll.html
grep -E "class_label|payroll_state|unpaid_seconds|attendance_events" templates/student_payroll.html

echo "F3: Admin Payroll Template"
grep -E "blocks|data-block|student.block|historyBlockFilter" templates/admin_payroll.html
grep -E "payroll_class_options|class_id|data-class-id" templates/admin_payroll.html

echo "F4: Hall-Pass Template"
grep -E "pending_requests.*approve|FEAT-PROD-002" templates/admin_hall_pass.html

echo "F5: Student Detail Template"
grep -E "student.first_name|student.display_first_name|student.tap_events|student.block" templates/student_detail.html
grep -E "identity_profile|attendance_events|payroll_event_history|hall_pass_balance" templates/student_detail.html

echo "G1: Test Suite Status"
pytest -q tests/dom/prod/ tests/dom/attendance/ --tb=line 

echo "G3: Stale Test Cleanup Verification"
ls tests/dom/attendance/test_*.py

echo "I1: Search for Deleted Models"
grep -r "SeatAttendanceState\|TapEvent\|StudentBlock" app/ --include="*.py" | grep -v "test\|#" | grep -v ".pyc"

echo "I2: Search for Deleted Functions"
grep -r "get_all_block_statuses\|batch_auto_tapout\|soft_delete" app/ --include="*.py" | grep -v "test\|#"

echo "I3: Search for Deleted Fields"
grep -r "\.seat_id\|\.started_at\|\.ended_at\|\.duration_seconds\|\.is_deleted" app/ --include="*.py" | grep -E "AttendanceSession|TapEvent" | grep -v "test\|#"

echo "I4: Search for Block/Period Scoping"
grep -r "filter.*block\|\.block\|period.*scope" app/routes/ app/services/ --include="*.py" | grep -v "test\|display\|section\|#"

echo "K2: Risk Zones Counts"
echo "canonical_temporal_resolver calls:"
grep -c "canonical_temporal_resolver" app/feats/prod.py app/routes/admin.py app/routes/api.py
echo "class_id scoping:"
grep -c "class_id ==" app/routes/admin.py | grep -E "AttendanceSession|HallPassLog|PayrollEvent"
echo "Immutability check:"
grep -r "\.update()\|\.delete()\|soft.delete\|is_deleted" app/ --include="*.py" | grep -E "AttendanceSession|HallPassLog|payroll"
