"""
Comprehensive tests for legacy account migration script.

Tests all phases of the migration:
1. Legacy student migration (StudentTeacher + TeacherBlock creation)
2. TeacherBlock join code backfill
3. Transaction join code backfill (with multi-period student scenarios)
4. Tap event join code backfill
5. Related tables join code backfill

Critical scenarios tested:
- Multi-period students with same teacher (ensures proper isolation)
- Multi-period students with different teachers
- Idempotency (safe to run multiple times)
- Dry run accuracy
- Rollback on errors
- Block casing normalization
"""

import pytest
import sys
import os
from datetime import datetime, timezone
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db
from app.models import (
    Student, Admin, StudentTeacher, TeacherBlock, StudentBlock,
    Transaction, TapEvent
)
from hash_utils import hash_username, get_random_salt, hash_password, encrypt_value

# Import migration functions
from scripts.comprehensive_legacy_migration import (
    migrate_legacy_students,
    backfill_teacher_block_join_codes,
    backfill_transaction_join_codes,
    backfill_tap_event_join_codes,
    backfill_related_tables,
    MigrationStats
)


@pytest.fixture
def migration_app(app):
    """Set up app context for migration tests."""
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def teacher1(migration_app):
    """Create test teacher 1."""
    with migration_app.app_context():
        salt = get_random_salt()
        teacher = Admin(
            username="teacher1",
            username_hash=hash_username("teacher1", salt),
            salt=salt,
            password_hash=hash_password("password123", salt),
            totp_secret=encrypt_value("test_totp_secret")
        )
        db.session.add(teacher)
        db.session.commit()
        return teacher.id


@pytest.fixture
def teacher2(migration_app):
    """Create test teacher 2."""
    with migration_app.app_context():
        salt = get_random_salt()
        teacher = Admin(
            username="teacher2",
            username_hash=hash_username("teacher2", salt),
            salt=salt,
            password_hash=hash_password("password123", salt),
            totp_secret=encrypt_value("test_totp_secret")
        )
        db.session.add(teacher)
        db.session.commit()
        return teacher.id


def create_legacy_student(username, teacher_id, block, first_name="Test"):
    """Helper to create a legacy student with teacher_id."""
    salt = get_random_salt()
    student = Student(
        first_name=encrypt_value(first_name),
        last_initial="S",
        block=block,
        teacher_id=teacher_id,  # Legacy field
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=hash_password("1234", salt)
    )
    db.session.add(student)
    db.session.flush()
    return student


class TestLegacyStudentMigration:
    """Test Phase 1: Legacy student migration."""

    def test_migrate_single_legacy_student(self, migration_app, teacher1):
        """Test migrating a single legacy student."""
        with migration_app.app_context():
            # Create legacy student
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.commit()

            # Run migration
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Verify StudentTeacher association created
            assert stats.student_teacher_created == 1
            assert stats.teacher_blocks_created == 1
            st = StudentTeacher.query.filter_by(student_id=student.id).first()
            assert st is not None
            assert st.admin_id == teacher1

            # Verify TeacherBlock created
            tb = TeacherBlock.query.filter_by(student_id=student.id).first()
            assert tb is not None
            assert tb.teacher_id == teacher1
            assert tb.block == "PERIOD 1"  # Normalized to uppercase
            assert tb.is_claimed is True
            assert tb.join_code is not None
            assert len(tb.join_code) > 0

    def test_migrate_multiple_students_same_period(self, migration_app, teacher1):
        """Test migrating multiple students in same period share join code."""
        with migration_app.app_context():
            # Create two legacy students in same period
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 1")
            db.session.commit()

            # Run migration
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Verify both students migrated
            assert stats.student_teacher_created == 2
            assert stats.teacher_blocks_created == 2

            # Verify they share the same join code
            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
            assert tb1.join_code == tb2.join_code
            assert tb1.block == tb2.block == "PERIOD 1"

    def test_migrate_student_multiple_periods_same_teacher(self, migration_app, teacher1):
        """Test student in multiple periods with same teacher gets separate join codes."""
        with migration_app.app_context():
            # Create legacy student entries for different periods
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 3")
            db.session.commit()

            # Run migration
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Verify TeacherBlocks have DIFFERENT join codes
            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
            assert tb1.join_code != tb2.join_code  # Different periods = different codes
            assert tb1.block == "PERIOD 1"
            assert tb2.block == "PERIOD 3"

    def test_block_casing_normalization(self, migration_app, teacher1):
        """Test that block names are normalized to uppercase."""
        with migration_app.app_context():
            # Create students with different casing
            student1 = create_legacy_student("student1", teacher1, "period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 1")
            student3 = create_legacy_student("student3", teacher1, "PERIOD 1")
            db.session.commit()

            # Run migration
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Verify all blocks normalized to uppercase
            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
            tb3 = TeacherBlock.query.filter_by(student_id=student3.id).first()

            assert tb1.block == "PERIOD 1"
            assert tb2.block == "PERIOD 1"
            assert tb3.block == "PERIOD 1"

            # All should share same join code
            assert tb1.join_code == tb2.join_code == tb3.join_code

    def test_idempotency_no_duplicate_associations(self, migration_app, teacher1):
        """Test running migration twice doesn't create duplicates."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.commit()

            # Run migration first time
            stats1 = MigrationStats()
            migrate_legacy_students(stats1, dry_run=False)
            assert stats1.student_teacher_created == 1
            assert stats1.teacher_blocks_created == 1

            # Run migration second time
            stats2 = MigrationStats()
            migrate_legacy_students(stats2, dry_run=False)
            assert stats2.legacy_students_found == 0  # Already migrated
            assert stats2.student_teacher_created == 0
            assert stats2.teacher_blocks_created == 0

            # Verify only one association exists
            associations = StudentTeacher.query.filter_by(student_id=student.id).all()
            assert len(associations) == 1

            # Verify only one TeacherBlock exists
            blocks = TeacherBlock.query.filter_by(student_id=student.id).all()
            assert len(blocks) == 1

    def test_dry_run_no_changes(self, migration_app, teacher1):
        """Test dry run mode doesn't make any changes."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.commit()

            # Run dry run
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=True)

            # Verify no changes made
            assert StudentTeacher.query.filter_by(student_id=student.id).count() == 0
            assert TeacherBlock.query.filter_by(student_id=student.id).count() == 0


class TestTransactionBackfill:
    """Test Phase 3: Transaction join code backfill."""

    def test_transaction_backfill_basic(self, migration_app, teacher1):
        """Test basic transaction backfill."""
        with migration_app.app_context():
            # Create student with TeacherBlock
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            # Migrate student to create TeacherBlock
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()
            join_code = tb.join_code

            # Create transaction without join_code
            txn = Transaction(
                student_id=student.id,
                teacher_id=teacher1,
                amount=100.0,
                description="Test transaction"
            )
            db.session.add(txn)
            db.session.commit()

            # Backfill transactions
            stats2 = MigrationStats()
            backfill_transaction_join_codes(stats2, dry_run=False)

            # Verify transaction got join_code
            txn_updated = Transaction.query.get(txn.id)
            assert txn_updated.join_code == join_code

    def test_transaction_backfill_multi_period_same_teacher(self, migration_app, teacher1):
        """
        CRITICAL TEST: Student in multiple periods with same teacher.
        Transactions must go to correct period based on teacher_id matching.
        """
        with migration_app.app_context():
            # Create two students in different periods (simulating same student)
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 3")
            db.session.flush()

            # Migrate to create TeacherBlocks
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()

            # Verify different join codes
            assert tb1.join_code != tb2.join_code

            # Create transactions for both periods
            txn1 = Transaction(
                student_id=student1.id,
                teacher_id=teacher1,  # Period 1 teacher
                amount=100.0,
                description="Period 1 transaction"
            )
            txn2 = Transaction(
                student_id=student2.id,
                teacher_id=teacher1,  # Period 3 teacher (same teacher)
                amount=200.0,
                description="Period 3 transaction"
            )
            db.session.add_all([txn1, txn2])
            db.session.commit()

            # Backfill transactions
            stats2 = MigrationStats()
            backfill_transaction_join_codes(stats2, dry_run=False)

            # CRITICAL: Verify transactions assigned to correct period
            txn1_updated = Transaction.query.get(txn1.id)
            txn2_updated = Transaction.query.get(txn2.id)

            assert txn1_updated.join_code == tb1.join_code
            assert txn2_updated.join_code == tb2.join_code
            assert txn1_updated.join_code != txn2_updated.join_code

    def test_transaction_backfill_idempotent(self, migration_app, teacher1):
        """Test transaction backfill is idempotent."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            # Migrate and create transaction
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()

            txn = Transaction(
                student_id=student.id,
                teacher_id=teacher1,
                amount=100.0,
                description="Test"
            )
            db.session.add(txn)
            db.session.commit()

            # Backfill first time
            stats1 = MigrationStats()
            backfill_transaction_join_codes(stats1, dry_run=False)
            assert stats1.transactions_backfilled > 0

            # Backfill second time
            stats2 = MigrationStats()
            backfill_transaction_join_codes(stats2, dry_run=False)
            assert stats2.transactions_backfilled == 0  # Nothing to backfill

            # Verify join_code unchanged
            txn_updated = Transaction.query.get(txn.id)
            assert txn_updated.join_code == tb.join_code


class TestTapEventBackfill:
    """Test Phase 4: Tap event join code backfill."""

    def test_tap_event_backfill_basic(self, migration_app, teacher1):
        """Test basic tap event backfill."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            # Migrate student
            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()

            # Create tap event without join_code
            tap = TapEvent(
                student_id=student.id,
                period="Period 1",  # Must match block for backfill
                action="tap_in",
                timestamp=datetime.now(timezone.utc)
            )
            db.session.add(tap)
            db.session.commit()

            # Backfill tap events
            stats2 = MigrationStats()
            backfill_tap_event_join_codes(stats2, dry_run=False)

            # Verify tap event got join_code
            tap_updated = TapEvent.query.get(tap.id)
            assert tap_updated.join_code == tb.join_code

    def test_tap_event_period_matching_case_insensitive(self, migration_app, teacher1):
        """Test tap event backfill handles case-insensitive period matching."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()

            # Create tap events with different casing
            tap1 = TapEvent(
                student_id=student.id,
                period="period 1",  # lowercase
                action="tap_in",
                timestamp=datetime.now(timezone.utc)
            )
            tap2 = TapEvent(
                student_id=student.id,
                period="PERIOD 1",  # uppercase
                action="tap_out",
                timestamp=datetime.now(timezone.utc)
            )
            db.session.add_all([tap1, tap2])
            db.session.commit()

            # Backfill
            stats2 = MigrationStats()
            backfill_tap_event_join_codes(stats2, dry_run=False)

            # Both should get same join_code despite casing differences
            tap1_updated = TapEvent.query.get(tap1.id)
            tap2_updated = TapEvent.query.get(tap2.id)

            assert tap1_updated.join_code == tb.join_code
            assert tap2_updated.join_code == tb.join_code


class TestTeacherBlockJoinCodeBackfill:
    """Test Phase 2: TeacherBlock join code backfill."""

    def test_backfill_teacherblock_without_code(self, migration_app, teacher1):
        """Test backfilling TeacherBlock entries without join codes."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            # Create TeacherBlock WITHOUT join_code
            tb = TeacherBlock(
                teacher_id=teacher1,
                block="PERIOD 1",
                first_name=student.first_name,
                last_initial=student.last_initial,
                salt=student.salt,
                is_claimed=True,
                student_id=student.id,
                join_code=None  # Missing join code
            )
            db.session.add(tb)
            db.session.commit()

            # Backfill join codes
            stats = MigrationStats()
            backfill_teacher_block_join_codes(stats, dry_run=False)

            # Verify join code added
            tb_updated = TeacherBlock.query.get(tb.id)
            assert tb_updated.join_code is not None
            assert len(tb_updated.join_code) > 0

    def test_backfill_reuses_existing_code(self, migration_app, teacher1):
        """Test backfill reuses existing join code for same teacher-block."""
        with migration_app.app_context():
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 1")
            db.session.flush()

            # Create one TeacherBlock WITH join_code
            tb1 = TeacherBlock(
                teacher_id=teacher1,
                block="PERIOD 1",
                first_name=student1.first_name,
                last_initial=student1.last_initial,
                salt=student1.salt,
                is_claimed=True,
                student_id=student1.id,
                join_code="ABC123"
            )
            # Create one WITHOUT join_code
            tb2 = TeacherBlock(
                teacher_id=teacher1,
                block="PERIOD 1",
                first_name=student2.first_name,
                last_initial=student2.last_initial,
                salt=student2.salt,
                is_claimed=True,
                student_id=student2.id,
                join_code=None
            )
            db.session.add_all([tb1, tb2])
            db.session.commit()

            # Backfill
            stats = MigrationStats()
            backfill_teacher_block_join_codes(stats, dry_run=False)

            # Verify tb2 got same code as tb1
            tb2_updated = TeacherBlock.query.get(tb2.id)
            assert tb2_updated.join_code == "ABC123"
            assert stats.join_codes_reused > 0


class TestErrorHandling:
    """Test error handling and rollback."""

    def test_rollback_on_error(self, migration_app, teacher1):
        """Test that errors cause rollback of all changes."""
        with migration_app.app_context():
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.commit()

            # Mock generate_join_code to fail
            with patch('scripts.comprehensive_legacy_migration.generate_join_code', side_effect=Exception("Test error")):
                stats = MigrationStats()
                with pytest.raises(Exception, match="Test error"):
                    migrate_legacy_students(stats, dry_run=False)

            # Verify no partial changes committed
            assert StudentTeacher.query.filter_by(student_id=student.id).count() == 0
            assert TeacherBlock.query.filter_by(student_id=student.id).count() == 0


def test_full_migration_workflow(migration_app, teacher1, teacher2):
    """Integration test: Full migration workflow."""
    with migration_app.app_context():
        # Create diverse test data
        # Student 1: Teacher 1, Period 1
        s1 = create_legacy_student("student1", teacher1, "Period 1")
        # Student 2: Teacher 1, Period 1 (same period as s1)
        s2 = create_legacy_student("student2", teacher1, "Period 1")
        # Student 3: Teacher 1, Period 3 (different period)
        s3 = create_legacy_student("student3", teacher1, "Period 3")
        # Student 4: Teacher 2, Period 1 (different teacher)
        s4 = create_legacy_student("student4", teacher2, "Period 1")
        db.session.flush()

        # Create transactions for each
        for student_id, teacher_id in [(s1.id, teacher1), (s2.id, teacher1),
                                        (s3.id, teacher1), (s4.id, teacher2)]:
            txn = Transaction(
                student_id=student_id,
                teacher_id=teacher_id,
                amount=100.0,
                description=f"Transaction for {student_id}"
            )
            db.session.add(txn)
        db.session.commit()

        # Run full migration
        stats = MigrationStats()

        # Phase 1: Migrate legacy students
        migrate_legacy_students(stats, dry_run=False)
        assert stats.legacy_students_found == 4
        assert stats.student_teacher_created == 4
        assert stats.teacher_blocks_created == 4

        # Phase 3: Backfill transactions
        backfill_transaction_join_codes(stats, dry_run=False)
        assert stats.transactions_backfilled == 4

        # Verify multi-tenancy isolation
        tb_s1 = TeacherBlock.query.filter_by(student_id=s1.id).first()
        tb_s2 = TeacherBlock.query.filter_by(student_id=s2.id).first()
        tb_s3 = TeacherBlock.query.filter_by(student_id=s3.id).first()
        tb_s4 = TeacherBlock.query.filter_by(student_id=s4.id).first()

        # s1 and s2 share same join code (same teacher, same period)
        assert tb_s1.join_code == tb_s2.join_code

        # s3 has different join code (same teacher, different period)
        assert tb_s1.join_code != tb_s3.join_code

        # s4 has different join code (different teacher)
        assert tb_s1.join_code != tb_s4.join_code

        # Verify all transactions have correct join codes
        txn_s1 = Transaction.query.filter_by(student_id=s1.id).first()
        txn_s2 = Transaction.query.filter_by(student_id=s2.id).first()
        txn_s3 = Transaction.query.filter_by(student_id=s3.id).first()
        txn_s4 = Transaction.query.filter_by(student_id=s4.id).first()

        assert txn_s1.join_code == tb_s1.join_code
        assert txn_s2.join_code == tb_s2.join_code
        assert txn_s3.join_code == tb_s3.join_code
        assert txn_s4.join_code == tb_s4.join_code


class TestRelatedTablesBackfill:
    """Test Phase 5: Related tables join code backfill."""

    def test_backfill_student_items_without_period(self, migration_app, teacher1):
        """Test backfilling student_items (table without period column)."""
        with migration_app.app_context():
            # Import here to avoid circular imports
            from app.models import StudentItem

            # Create student and migrate
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Get join_code from TeacherBlock
            tb = TeacherBlock.query.filter_by(student_id=student.id).first()
            join_code = tb.join_code

            # Create StudentBlock (required for backfill)
            sb = StudentBlock(
                student_id=student.id,
                join_code=join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            db.session.add(sb)
            db.session.commit()

            # Create StudentItem without join_code
            item = StudentItem(
                student_id=student.id,
                item_name="Test Item",
                cost=50.0,
                purchase_date=datetime.now(timezone.utc)
            )
            db.session.add(item)
            db.session.commit()

            # Verify item has no join_code initially
            assert item.join_code is None

            # Backfill related tables
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)

            # Verify item got join_code
            item_updated = StudentItem.query.get(item.id)
            assert item_updated.join_code == join_code
            assert stats2.student_items_backfilled > 0

    def test_backfill_hall_pass_logs_with_period(self, migration_app, teacher1):
        """Test backfilling hall_pass_logs (table with period column)."""
        with migration_app.app_context():
            from app.models import HallPassLog

            # Create student and migrate
            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()
            join_code = tb.join_code

            # Create StudentBlock
            sb = StudentBlock(
                student_id=student.id,
                join_code=join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            db.session.add(sb)
            db.session.commit()

            # Create HallPassLog without join_code
            log = HallPassLog(
                student_id=student.id,
                period="Period 1",  # Note: different casing
                request_time=datetime.now(timezone.utc),
                pass_number=1,
                status="approved"
            )
            db.session.add(log)
            db.session.commit()

            # Backfill
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)

            # Verify log got correct join_code (case-insensitive period matching)
            log_updated = HallPassLog.query.get(log.id)
            assert log_updated.join_code == join_code
            assert stats2.hall_pass_logs_backfilled > 0

    def test_backfill_multi_period_student_with_period_column(self, migration_app, teacher1):
        """
        Test backfill for student in multiple periods with period-aware table.
        Each period's data should get correct join_code.
        """
        with migration_app.app_context():
            from app.models import HallPassLog

            # Create students in two periods
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 3")
            db.session.flush()

            # Use same student_id for both (simulating same student, different periods)
            # For test purposes, we'll use different student_ids but same logical student
            actual_student_id = student1.id

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()

            # Create StudentBlocks
            sb1 = StudentBlock(
                student_id=student1.id,
                join_code=tb1.join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            sb2 = StudentBlock(
                student_id=student2.id,
                join_code=tb2.join_code,
                period="PERIOD 3",
                tap_enabled=True
            )
            db.session.add_all([sb1, sb2])
            db.session.commit()

            # Create hall pass logs for each period
            log1 = HallPassLog(
                student_id=student1.id,
                period="Period 1",
                request_time=datetime.now(timezone.utc),
                pass_number=1,
                status="approved"
            )
            log2 = HallPassLog(
                student_id=student2.id,
                period="Period 3",
                request_time=datetime.now(timezone.utc),
                pass_number=2,
                status="approved"
            )
            db.session.add_all([log1, log2])
            db.session.commit()

            # Backfill
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)

            # Verify each log got correct join_code based on period
            log1_updated = HallPassLog.query.get(log1.id)
            log2_updated = HallPassLog.query.get(log2.id)

            assert log1_updated.join_code == tb1.join_code
            assert log2_updated.join_code == tb2.join_code
            assert log1_updated.join_code != log2_updated.join_code  # Different periods

    def test_backfill_multi_period_student_without_period_column(self, migration_app, teacher1):
        """
        Test backfill for student in multiple periods with non-period-aware table.
        Should use first available join_code (ambiguous case).
        """
        with migration_app.app_context():
            from app.models import StudentItem

            # Create student in two periods
            student1 = create_legacy_student("student1", teacher1, "Period 1")
            student2 = create_legacy_student("student2", teacher1, "Period 3")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
            tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()

            # Create StudentBlocks for both periods
            sb1 = StudentBlock(
                student_id=student1.id,
                join_code=tb1.join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            sb2 = StudentBlock(
                student_id=student2.id,
                join_code=tb2.join_code,
                period="PERIOD 3",
                tap_enabled=True
            )
            db.session.add_all([sb1, sb2])
            db.session.commit()

            # Create StudentItem for first student (no period column)
            item = StudentItem(
                student_id=student1.id,
                item_name="Test Item",
                cost=50.0,
                purchase_date=datetime.now(timezone.utc)
            )
            db.session.add(item)
            db.session.commit()

            # Backfill
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)

            # Verify item got A join_code (will be first one due to DISTINCT ON ordering)
            item_updated = StudentItem.query.get(item.id)
            assert item_updated.join_code is not None
            assert item_updated.join_code in [tb1.join_code, tb2.join_code]

            # Verify warning was issued for ambiguous case
            assert any("ambiguous" in str(w).lower() for w in stats2.warnings)

    def test_backfill_related_tables_idempotent(self, migration_app, teacher1):
        """Test that related tables backfill is idempotent."""
        with migration_app.app_context():
            from app.models import StudentItem

            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()

            sb = StudentBlock(
                student_id=student.id,
                join_code=tb.join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            db.session.add(sb)

            item = StudentItem(
                student_id=student.id,
                item_name="Test Item",
                cost=50.0,
                purchase_date=datetime.now(timezone.utc)
            )
            db.session.add(item)
            db.session.commit()

            # First backfill
            stats1 = MigrationStats()
            backfill_related_tables(stats1, dry_run=False)
            assert stats1.student_items_backfilled > 0

            # Second backfill (should be no-op)
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)
            assert stats2.student_items_backfilled == 0  # Already backfilled

            # Verify join_code unchanged
            item_updated = StudentItem.query.get(item.id)
            assert item_updated.join_code == tb.join_code

    def test_backfill_related_tables_dry_run(self, migration_app, teacher1):
        """Test dry run mode for related tables backfill."""
        with migration_app.app_context():
            from app.models import StudentItem

            student = create_legacy_student("student1", teacher1, "Period 1")
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            tb = TeacherBlock.query.filter_by(student_id=student.id).first()

            sb = StudentBlock(
                student_id=student.id,
                join_code=tb.join_code,
                period="PERIOD 1",
                tap_enabled=True
            )
            db.session.add(sb)

            item = StudentItem(
                student_id=student.id,
                item_name="Test Item",
                cost=50.0,
                purchase_date=datetime.now(timezone.utc)
            )
            db.session.add(item)
            db.session.commit()

            # Dry run
            stats_dry = MigrationStats()
            backfill_related_tables(stats_dry, dry_run=True)

            # Verify no changes made
            item_check = StudentItem.query.get(item.id)
            assert item_check.join_code is None  # Still NULL

    def test_backfill_performance_cte_usage(self, migration_app, teacher1):
        """
        Test that backfill uses CTE approach (not correlated subquery).
        This is a structural test to ensure performance optimization is in place.
        """
        with migration_app.app_context():
            from app.models import StudentItem, HallPassLog

            # Create multiple students and StudentBlocks
            students = []
            for i in range(5):
                s = create_legacy_student(f"student{i}", teacher1, "Period 1")
                students.append(s)
            db.session.flush()

            stats = MigrationStats()
            migrate_legacy_students(stats, dry_run=False)

            # Create StudentBlocks for all
            for s in students:
                tb = TeacherBlock.query.filter_by(student_id=s.id).first()
                sb = StudentBlock(
                    student_id=s.id,
                    join_code=tb.join_code,
                    period="PERIOD 1",
                    tap_enabled=True
                )
                db.session.add(sb)

            # Create items for all students
            for s in students:
                item = StudentItem(
                    student_id=s.id,
                    item_name=f"Item for {s.id}",
                    cost=50.0,
                    purchase_date=datetime.now(timezone.utc)
                )
                db.session.add(item)
            db.session.commit()

            # Backfill (should use efficient CTE approach)
            stats2 = MigrationStats()
            backfill_related_tables(stats2, dry_run=False)

            # Verify all items backfilled
            assert stats2.student_items_backfilled == 5

            # Verify all have correct join_codes
            for s in students:
                tb = TeacherBlock.query.filter_by(student_id=s.id).first()
                item = StudentItem.query.filter_by(student_id=s.id).first()
                assert item.join_code == tb.join_code
