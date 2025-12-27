"""
Tests for teacher announcement feature.

Tests the Announcement model, admin routes, and student display.
Ensures proper multi-tenancy scoping by join_code.
"""
import pytest
import pyotp
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Admin, Announcement, TeacherBlock, Student


@pytest.fixture
def test_teacher():
    """Create a test teacher with TOTP."""
    admin = Admin(
        username='test_teacher_announcements',
        totp_secret=pyotp.random_base32(),
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def teacher_block(test_teacher):
    """Create a teacher block with join code."""
    block = TeacherBlock(
        teacher_id=test_teacher.id,
        block='A',
        join_code='TEST123',
        first_name='encrypted_test_name',
        last_initial='T',
        last_name_hash_by_part=['hash1'],
        dob_sum=2000,
        salt=b'testsalt12345678',
        first_half_hash='testhash123',
    )
    db.session.add(block)
    db.session.commit()
    return block


class TestAnnouncementModel:
    """Tests for the Announcement model."""

    def test_announcement_creation(self, client, test_teacher, teacher_block):
        """Test creating an announcement."""
        announcement = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Test Announcement',
            message='This is a test message',
            priority='normal',
            is_active=True
        )
        db.session.add(announcement)
        db.session.commit()

        assert announcement.id is not None
        assert announcement.title == 'Test Announcement'
        assert announcement.message == 'This is a test message'
        assert announcement.priority == 'normal'
        assert announcement.is_active is True

    def test_announcement_defaults(self, client, test_teacher, teacher_block):
        """Test announcement model defaults."""
        announcement = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Test',
            message='Test message'
        )
        db.session.add(announcement)
        db.session.commit()

        assert announcement.is_active is True
        assert announcement.priority == 'normal'
        assert announcement.expires_at is None
        assert announcement.created_at is not None

    def test_announcement_expiration(self, client, test_teacher, teacher_block):
        """Test announcement expiration logic."""
        # Create expired announcement
        expired_announcement = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Expired',
            message='This is expired',
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(expired_announcement)

        # Create active announcement
        active_announcement = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Active',
            message='This is active',
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(active_announcement)

        # Create announcement with no expiration
        no_expiry = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='No Expiry',
            message='Never expires'
        )
        db.session.add(no_expiry)
        db.session.commit()

        assert expired_announcement.is_expired() is True
        assert active_announcement.is_expired() is False
        assert no_expiry.is_expired() is False

    def test_announcement_should_display(self, client, test_teacher, teacher_block):
        """Test should_display method."""
        # Active and not expired
        visible = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Visible',
            message='Should be visible',
            is_active=True
        )
        db.session.add(visible)

        # Inactive
        inactive = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Inactive',
            message='Should not be visible',
            is_active=False
        )
        db.session.add(inactive)

        # Expired
        expired = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Expired',
            message='Should not be visible',
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(expired)
        db.session.commit()

        assert visible.should_display() is True
        assert inactive.should_display() is False
        assert expired.should_display() is False

    def test_announcement_priority_classes(self, client, test_teacher, teacher_block):
        """Test priority CSS classes and icons."""
        priorities = ['low', 'normal', 'high', 'urgent']
        expected_classes = ['alert-secondary', 'alert-info', 'alert-warning', 'alert-danger']
        expected_icons = ['📌', '📢', '⚠️', '🚨']

        for priority, expected_class, expected_icon in zip(priorities, expected_classes, expected_icons):
            announcement = Announcement(
                teacher_id=test_teacher.id,
                join_code=teacher_block.join_code,
                title=f'{priority} priority',
                message='Test',
                priority=priority
            )
            db.session.add(announcement)
            db.session.commit()

            assert announcement.get_priority_class() == expected_class
            assert announcement.get_priority_icon() == expected_icon


class TestAnnouncementMultiTenancy:
    """Tests for announcement multi-tenancy scoping."""

    def test_announcements_scoped_by_join_code(self, client, test_teacher):
        """Test that announcements are properly scoped by join_code."""
        # Create two different blocks with different join codes
        block_a = TeacherBlock(
            teacher_id=test_teacher.id,
            block='A',
            join_code='CODE_A',
            first_name='encrypted_test_name',
            last_initial='T',
            last_name_hash_by_part=['hash1'],
            dob_sum=2000,
            salt=b'testsalt12345678',
            first_half_hash='testhash123',
        )
        block_b = TeacherBlock(
            teacher_id=test_teacher.id,
            block='B',
            join_code='CODE_B',
            first_name='encrypted_test_name',
            last_initial='T',
            last_name_hash_by_part=['hash1'],
            dob_sum=2000,
            salt=b'testsalt87654321',
            first_half_hash='testhash456',
        )
        db.session.add(block_a)
        db.session.add(block_b)
        db.session.commit()

        # Create announcements for each block
        announcement_a = Announcement(
            teacher_id=test_teacher.id,
            join_code='CODE_A',
            title='Announcement for Block A',
            message='Only Block A should see this',
            is_active=True
        )
        announcement_b = Announcement(
            teacher_id=test_teacher.id,
            join_code='CODE_B',
            title='Announcement for Block B',
            message='Only Block B should see this',
            is_active=True
        )
        db.session.add(announcement_a)
        db.session.add(announcement_b)
        db.session.commit()

        # Query announcements for Block A
        announcements_a = Announcement.query.filter_by(
            join_code='CODE_A',
            is_active=True
        ).all()

        # Query announcements for Block B
        announcements_b = Announcement.query.filter_by(
            join_code='CODE_B',
            is_active=True
        ).all()

        # Verify proper scoping
        assert len(announcements_a) == 1
        assert announcements_a[0].title == 'Announcement for Block A'

        assert len(announcements_b) == 1
        assert announcements_b[0].title == 'Announcement for Block B'

    def test_announcement_cascade_delete(self, client, test_teacher, teacher_block):
        """Test that announcements are deleted when teacher is deleted."""
        announcement = Announcement(
            teacher_id=test_teacher.id,
            join_code=teacher_block.join_code,
            title='Test Announcement',
            message='This should be deleted with teacher',
            is_active=True
        )
        db.session.add(announcement)
        db.session.commit()

        announcement_id = announcement.id

        # Delete teacher
        db.session.delete(test_teacher)
        db.session.commit()

        # Verify announcement is deleted
        deleted_announcement = Announcement.query.get(announcement_id)
        assert deleted_announcement is None
