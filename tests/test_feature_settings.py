"""
Tests for feature settings and teacher onboarding functionality.
"""
from tests.helpers.v2_fixtures import make_admin
import os
import pytest
import pyotp
from flask import g, session
from types import SimpleNamespace

from app import app, db
from app.models import ClassEconomy, ClassFeature, FeatureSettings, Seat, TeacherOnboarding, User, UserRole
from app.routes.admin import get_admin_feature_join_code_options, is_admin_feature_enabled
from tests.helpers.admin_context import login_teacher
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import create_class_scope
from app.utils.economy_policy import (
    get_class_feature_settings_for_class,
    resolve_feature_class_for_class,
)


def _create_class_scope(teacher, block='A', join_code='JOIN_A'):
    from tests.helpers.class_scope import create_class_scope as _create
    return _create(teacher_user=teacher, join_code=join_code, display_name=f'Period {block}', section=block)


@pytest.fixture
def test_admin():
    """Create a test admin for feature settings tests."""
    admin = make_admin('test_teacher')
    db.session.commit()
    return admin


class TestClassFeatures:
    """Tests for class feature row-existence semantics."""

    def test_class_feature_defaults(self, client, test_admin):
        """New classes start with payroll enabled and other features disabled."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.commit()

        enabled_names = ClassFeature.enabled_names_for_class(economy.class_id)
        assert enabled_names == {'payroll'}

    def test_feature_settings_to_dict_reads_class_features(self, client, test_admin):
        """Policy rows expose feature state from class_features."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        settings = FeatureSettings(
            class_id=economy.class_id,
        )
        db.session.add(settings)
        for row in ClassFeature.query.filter_by(class_id=economy.class_id).all():
            if row.feature_name in {"insurance", "rent"}:
                db.session.delete(row)
        db.session.commit()

        settings_dict = settings.to_dict()
        assert settings_dict['payroll_enabled'] is True
        assert settings_dict['insurance_enabled'] is False
        assert settings_dict['rent_enabled'] is False

    def test_class_features_per_period(self, client, test_admin):
        """Test that different periods can have different settings."""
        economy_a = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        economy_b = _create_class_scope(test_admin, block='B', join_code='JOIN_B')
        # Enable rent for class A only.
        db.session.add(ClassFeature(class_id=economy_a.class_id, feature_name='rent'))
        db.session.commit()

        settings_a = ClassFeature.feature_map_for_class(economy_a.class_id)
        settings_b = ClassFeature.feature_map_for_class(economy_b.class_id)
        assert settings_a['rent_enabled'] is True
        assert settings_b['rent_enabled'] is False
        assert settings_a['payroll_enabled'] is True
        assert settings_b['payroll_enabled'] is True

    def test_unique_constraint_class_feature(self, client, test_admin):
        """Duplicate feature rows for the same class are prevented."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name='payroll'))

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()

    def test_resolve_feature_class_for_class_is_class_scoped(self, client, test_admin):
        """Class-scoped feature resolution must not bleed across a teacher's classes."""
        economy_a = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        economy_b = _create_class_scope(test_admin, block='B', join_code='JOIN_B')
        db.session.add(ClassFeature(class_id=economy_a.class_id, feature_name='hall_pass'))
        db.session.commit()

        scope_a = resolve_feature_class_for_class(economy_a.class_id, 'hall_pass')
        scope_b = resolve_feature_class_for_class(economy_b.class_id, 'hall_pass')

        assert scope_a == {
            'class_id': economy_a.class_id,
            'enabled': True,
            'feature_name': 'hall_pass',
            'join_code': economy_a.join_code,
        }
        assert scope_b == {
            'class_id': economy_b.class_id,
            'enabled': False,
            'feature_name': 'hall_pass',
            'join_code': economy_b.join_code,
        }

    def test_get_class_feature_settings_for_class_reads_from_class_features(self, client, test_admin):
        """Class-scoped feature settings should read directly from class feature rows."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name='banking'))
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name='hall_pass'))
        db.session.commit()

        scoped = get_class_feature_settings_for_class(economy.class_id)

        assert scoped['class_id'] == economy.class_id
        assert scoped['features']['payroll_enabled'] is True
        assert scoped['features']['banking_enabled'] is True
        assert scoped['features']['hall_pass_enabled'] is True
        assert scoped['features']['insurance_enabled'] is False

    def test_explicit_class_feature_helpers_reject_unknown_class_id(self, client):
        """Canonical feature helpers must not synthesize scope for a missing class."""
        assert resolve_feature_class_for_class('missing-class', 'hall_pass') is None
        assert get_class_feature_settings_for_class('missing-class') is None

    def test_admin_feature_join_code_options_do_not_depend_on_teacher_section(self, client, test_admin):
        """Enabled class options should come from class scope, not seat-local metadata."""
        economy_a = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        economy_b = _create_class_scope(test_admin, block='B', join_code='JOIN_B')
        db.session.add(ClassFeature(class_id=economy_a.class_id, feature_name='hall_pass'))
        Seat.query.filter_by(class_id=economy_a.class_id).delete(synchronize_session=False)
        db.session.commit()

        options = get_admin_feature_join_code_options('hall_pass', canonical_context=SimpleNamespace(user_id=test_admin.id))

        assert options == [{
            'join_code': economy_a.join_code,
            'class_id': economy_a.class_id,
            'block': 'A',
            'label': economy_a.display_name,
        }]

    def test_admin_feature_gate_resolves_join_code_through_class_scope(self, client, test_admin):
        """Boundary join codes resolve through ClassEconomy without TeacherBlock authority."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name='insurance'))
        Seat.query.filter_by(class_id=economy.class_id).delete(synchronize_session=False)
        db.session.commit()

        with app.test_request_context('/admin/insurance'):
            canonical_context = SimpleNamespace(
                user_id=test_admin.id,
                class_id=economy.class_id,
                seat_id=None,
                actor_role="teacher",
            )
            assert is_admin_feature_enabled(canonical_context, 'insurance') is True

    def test_admin_feature_gate_prefers_active_class_id(self, client, test_admin):
        """An explicit active class must not be overridden by another class's join code."""
        economy_a = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        economy_b = _create_class_scope(test_admin, block='B', join_code='JOIN_B')
        db.session.add(ClassFeature(class_id=economy_a.class_id, feature_name='insurance'))
        db.session.commit()

        teacher_seat = Seat.query.filter_by(class_id=economy_b.class_id, role='teacher').first()
        assert teacher_seat is not None

        with app.test_request_context('/admin/insurance'):
            g.canonical_context = SimpleNamespace(
                user_id=test_admin.id,
                class_id=economy_b.class_id,
                seat_id=teacher_seat.id,
                actor_role="teacher",
            )
            set_canonical_context(
                session,
                user_id=test_admin.id,
                class_id=economy_b.class_id,
                seat_id=teacher_seat.id,
                role="teacher",
            )
            assert is_admin_feature_enabled(g.canonical_context, 'insurance') is False


class TestTeacherOnboarding:
    """Tests for the TeacherOnboarding model."""

    def test_onboarding_model_defaults(self, client, test_admin):
        """Test that TeacherOnboarding has correct defaults."""
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        assert onboarding.is_completed is False
        assert onboarding.is_skipped is False
        assert onboarding.current_step == 1
        assert onboarding.total_steps == 5
        assert onboarding.steps_completed == {}

    def test_mark_step_completed(self, client, test_admin):
        """Test marking steps as completed."""
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.mark_step_completed('welcome')
        onboarding.mark_step_completed('features')
        db.session.commit()

        assert onboarding.is_step_completed('welcome') is True
        assert onboarding.is_step_completed('features') is True
        assert onboarding.is_step_completed('periods') is False

    def test_complete_onboarding(self, client, test_admin):
        """Test completing onboarding."""
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.complete_onboarding()
        db.session.commit()

        assert onboarding.is_completed is True
        assert onboarding.completed_at is not None

    def test_skip_onboarding(self, client, test_admin):
        """Test skipping onboarding."""
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.skip_onboarding()
        db.session.commit()

        assert onboarding.is_skipped is True
        assert onboarding.skipped_at is not None

    def test_needs_onboarding_property(self, client, test_admin):
        """Test the needs_onboarding property."""
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        # Initially needs onboarding
        assert onboarding.needs_onboarding is True

        # After completion, onboarding should be marked complete
        onboarding.complete_onboarding()
        db.session.commit()
        assert onboarding.needs_onboarding is False

    def test_unique_teacher_onboarding(self, client, test_admin):
        """Test that each teacher can only have one onboarding record."""
        onboarding1 = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding1)
        db.session.commit()

        # Try to add another onboarding for the same teacher
        onboarding2 = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()


class TestFeatureSettingsRoutes:
    """Tests for feature settings routes."""

    def test_feature_settings_page_requires_login(self, client):
        """Test that feature settings page requires admin login."""
        response = client.get('/admin/feature-settings')
        assert response.status_code == 302  # Redirect to login

    def test_feature_settings_page_accessible_when_logged_in(self, client, test_admin):
        """Test that feature settings page is accessible when logged in."""
        economy = create_class_scope(
        teacher_user=test_admin,
            display_name="Feature Settings",
        )
        db.session.commit()
        login_teacher(client, test_admin, class_id=economy.class_id, join_code=economy.join_code)

        response = client.get('/admin/feature-settings')
        assert response.status_code == 200


class TestOnboardingRoutes:
    """Tests for onboarding routes."""

    def test_onboarding_page_requires_login(self, client):
        """Test that onboarding page requires admin login."""
        response = client.get('/admin/onboarding')
        assert response.status_code == 302  # Redirect to login

    def test_onboarding_skip(self, client, test_admin):
        """Test skipping onboarding via API."""
        # Create onboarding record
        onboarding = TeacherOnboarding(user_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        economy = create_class_scope(
        teacher_user=test_admin,
            display_name="Onboarding",
        )
        db.session.commit()
        login_teacher(client, test_admin, class_id=economy.class_id, join_code=economy.join_code)

        response = client.post('/admin/onboarding/skip',
                               content_type='application/json')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'success'

        # Verify onboarding was skipped
        onboarding = TeacherOnboarding.query.filter_by(
            user_id=test_admin.id
        ).first()
        assert onboarding.is_skipped is True


class TestTeacherDeletionCascade:
    """Tests for CASCADE deletion when a teacher is deleted."""

    def test_class_features_cascade_on_teacher_delete(self, client_with_fk):
        """Class features are removed when their teacher-owned class is deleted."""
        admin = make_admin('cascade_test_teacher')
        db.session.flush()
        teacher_user = admin
        teacher_id = admin.id

        economy_a = _create_class_scope(admin, block='A', join_code='TESTA1')
        economy_b = _create_class_scope(admin, block='B', join_code='TESTB1')
        db.session.commit()

        assert ClassFeature.query.join(ClassEconomy, ClassFeature.class_id == ClassEconomy.class_id).filter(
            ClassEconomy.user_id == teacher_id
        ).count() == 2

        # Delete the teacher
        db.session.delete(teacher_user)
        db.session.commit()

        assert ClassFeature.query.join(ClassEconomy, ClassFeature.class_id == ClassEconomy.class_id).filter(
            ClassEconomy.user_id == teacher_id
        ).count() == 0

    def test_teacher_onboarding_cascade_on_teacher_delete(self, client_with_fk):
        """Test that TeacherOnboarding is CASCADE deleted when teacher is deleted."""
        admin = make_admin('onboarding_cascade_test')
        db.session.flush()
        teacher_user = admin
        teacher_id = admin.id

        # Create onboarding record for the teacher
        onboarding = TeacherOnboarding(user_id=teacher_id)
        db.session.add(onboarding)
        db.session.commit()

        # Verify onboarding exists
        assert TeacherOnboarding.query.filter_by(user_id=teacher_id).first() is not None

        # Delete the teacher
        db.session.delete(teacher_user)
        db.session.commit()

        # Verify onboarding was CASCADE deleted
        assert TeacherOnboarding.query.filter_by(user_id=teacher_id).first() is None

    def test_class_scoped_seats_cascade_on_teacher_delete(self, client_with_fk):
        """Test that class-scoped seats are removed when the teacher's classes are deleted."""
        from app.models import ClassEconomy

        admin = make_admin('blocks_cascade_test')
        db.session.flush()
        teacher_user = admin
        teacher_id = admin.id

        # Ensure ClassEconomy exists for FK constraints
        if not ClassEconomy.query.filter_by(class_id='TEST123').first():
            db.session.add(ClassEconomy(class_id='TEST123', join_code='TEST123', user_id=teacher_id, created_by_user_id=teacher_id, display_name='Class TEST123'))
        if not ClassEconomy.query.filter_by(class_id='TEST456').first():
            db.session.add(ClassEconomy(class_id='TEST456', join_code='TEST456', user_id=teacher_id, created_by_user_id=teacher_id, display_name='Class TEST456'))
        db.session.commit()

        block1 = Seat(class_id='TEST123', role='student')
        block2 = Seat(class_id='TEST456', role='student')
        db.session.add(block1)
        db.session.add(block2)
        db.session.commit()

        # Verify seats exist
        assert Seat.query.filter(Seat.class_id.in_(['TEST123', 'TEST456'])).count() == 2

        # Delete the teacher
        db.session.delete(teacher_user)
        db.session.commit()

        # Verify class-scoped seats were CASCADE deleted via class deletion.
        assert Seat.query.filter(Seat.class_id.in_(['TEST123', 'TEST456'])).count() == 0
