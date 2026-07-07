"""
Tests for teacher announcement feature.

Tests the Announcement model, admin routes, and student display.
Ensures proper multi-tenancy scoping by join_code.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
import pyotp
from datetime import datetime, timedelta, timezone
from app import db
from app.models import User, UserRole, Admin, Announcement, ClassEconomy, Seat, IdentityProfile


@pytest.fixture
def test_teacher():
    """Create a test teacher with TOTP."""
    admin = make_admin('test_teacher_announcements', pyotp.random_base32(),
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def teacher_block(test_teacher):
    """Create a teacher block with join code."""
    # Create ClassEconomy first for FK constraint
    if not db.session.get(ClassEconomy, 'TEST123'):
        economy = ClassEconomy(
            user_id=test_teacher.id,
            display_name='Test Announcements Class',
            status='active',
        )
        db.session.add(economy)
        db.session.flush()
    
    block = Seat(block='A', block_identifier='A', role="student")
    
    db.session.add(block)
    
    db.session.flush()
    
    db.session.add(IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name='encrypted_test_name', last_name='T'))
    db.session.add(block)
    db.session.commit()
    return block


class TestAnnouncementModel:
    """Tests for the Announcement model."""

    def test_announcement_creation(self, client, test_teacher, teacher_block):
        """Test creating an announcement."""
        announcement = Announcement(
            teacher_id=test_teacher.id,
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
            title='Expired',
            message='This is expired',
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(expired_announcement)

        # Create active announcement
        active_announcement = Announcement(
            teacher_id=test_teacher.id,
            title='Active',
            message='This is active',
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(active_announcement)

        # Create announcement with no expiration
        no_expiry = Announcement(
            teacher_id=test_teacher.id,
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
            title='Visible',
            message='Should be visible',
            is_active=True
        )
        db.session.add(visible)

        # Inactive
        inactive = Announcement(
            teacher_id=test_teacher.id,
            title='Inactive',
            message='Should not be visible',
            is_active=False
        )
        db.session.add(inactive)

        # Expired
        expired = Announcement(
            teacher_id=test_teacher.id,
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
        expected_icons = ['push_pin', 'campaign', 'warning', 'error']

        for priority, expected_class, expected_icon in zip(priorities, expected_classes, expected_icons):
            announcement = Announcement(
                teacher_id=test_teacher.id,
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
        # Create ClassEconomies for FK constraints
        economy_a = ClassEconomy(
            user_id=test_teacher.id,
            display_name='Class A',
            status='active',
        )
        economy_b = ClassEconomy(
            user_id=test_teacher.id,
            display_name='Class B',
            status='active',
        )
        db.session.add(economy_a)
        db.session.add(economy_b)
        db.session.flush()
        
        # Create two different blocks with different join codes
        block_a = Seat(block='A', block_identifier='A', role="student")
        db.session.add(block_a)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block_a.id, profile_type='student_unclaimed', first_name='encrypted_test_name', last_name='T'))
        block_b = Seat(block='B', block_identifier='B', role="student")
        db.session.add(block_b)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block_b.id, profile_type='student_unclaimed', first_name='encrypted_test_name', last_name='T'))
        db.session.add(block_a)
        db.session.add(block_b)
        db.session.commit()

        # Create announcements for each block
        announcement_a = Announcement(
            teacher_id=test_teacher.id,
            title='Announcement for Block A',
            message='Only Block A should see this',
            is_active=True
        )
        announcement_b = Announcement(
            teacher_id=test_teacher.id,
            title='Announcement for Block B',
            message='Only Block B should see this',
            is_active=True
        )
        db.session.add(announcement_a)
        db.session.add(announcement_b)
        db.session.commit()

        # Query announcements for Block A
        announcements_a = Announcement.query.filter_by(
            is_active=True
        ).all()

        # Query announcements for Block B
        announcements_b = Announcement.query.filter_by(
            is_active=True
        ).all()

        # Verify proper scoping
        assert len(announcements_a) == 1
        assert announcements_a[0].title == 'Announcement for Block A'

        assert len(announcements_b) == 1
        assert announcements_b[0].title == 'Announcement for Block B'

    def test_announcement_cascade_delete(self, client_with_fk, test_teacher, teacher_block):
        """Test that announcements are deleted when teacher is deleted."""
        announcement = Announcement(
            teacher_id=test_teacher.id,
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

        # Verify announcement was CASCADE-deleted at the database level
        remaining = Announcement.query.filter_by(id=announcement_id).count()
        assert remaining == 0
