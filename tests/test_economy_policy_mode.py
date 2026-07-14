from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
import json
from datetime import datetime, timezone
from decimal import Decimal

from app import db
from app.models import (
    ClassEconomy,
    FeatureSettings,
    IdentityProfile,
    InsurancePolicy,
    ObligationAssessment,
    ObligationSatisfaction,
    PolicyTransition,
    PolicyVersion,
    PayrollSettings,
    RentPayment,
    RentSettings,
    Seat,
    Transaction,
    User,
    UserRole,
)
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import make_student_identity
from app.routes.student import (
    _get_effective_rent_amount_for_coverage_period,
    _is_coverage_period_paid,
)
from app.feats.base import FEATContext
from app.utils.economy_balance import EconomyBalanceChecker, WarningLevel
from app.utils.economy_policy import (
    convert_weekly_amount_to_frequency,
    get_feature_settings_row_for_class,
    get_insurance_premium_recommendation,
    get_price_recommendation_context,
)
from app.utils.economy_rebalance import (
    REBALANCE_ACTIVATION_NEXT_RENEWAL,
    activate_due_rebalances,
    prepare_scheduled_rebalance_changes,
)
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, teacher_id, *, class_id=None):
    from tests.helpers.admin_context import login_teacher
    teacher = db.session.get(User, teacher_id)
    if teacher is None:
        return
    if not class_id:
        raise ValueError("economy-policy tests require an explicit canonical class scope")
    login_teacher(client, teacher, class_id=class_id)


def _create_admin_with_block(block, *, join_code):
    from tests.helpers.class_scope import create_class_scope
    teacher = seed_canonical_admin(f"policyadmin_{block.lower()}").user
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:create-admin:{block}:{teacher.id}"):
        economy = create_class_scope(
            teacher_user=teacher,
            join_code=join_code,
            display_name=f'Period {block}',
            section=block,
        )
        db.session.flush()
        admin = teacher

        payroll_settings = PayrollSettings(
            class_id=economy.class_id,
            pay_rate=Decimal('0.25'),
            expected_weekly_hours=5.0,
            payroll_frequency_days=14,
            settings_mode='simple',
            is_active=True,
        )
        rent_settings = RentSettings(
            class_id=economy.class_id,
            rent_amount=Decimal('500.00'),
            frequency_type='monthly',
        )
        db.session.add_all([payroll_settings, rent_settings])
        db.session.flush()
    return admin, payroll_settings, rent_settings, economy


def _create_insurance_policy(user_id, title, premium, *, economy):
    teacher = db.session.get(User, user_id)
    if teacher is None:
        raise ValueError("economy-policy tests require an existing teacher user")
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:create-insurance:{economy.class_id}:{user_id}:{title}"):
        policy = InsurancePolicy(
            teacher_id=user_id,
            join_code=economy.join_code,
            class_id=economy.class_id,
            policy_code=f"{title[:3].upper()}{user_id}",
            title=title,
            premium=Decimal(str(premium)),
            charge_frequency='monthly',
            waiting_period_days=7,
            max_claim_amount=Decimal('100.00'),
            max_payout_per_period=Decimal('200.00'),
            claim_type='legacy_monetary',
            is_monetary=True,
            settings_mode='advanced',
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()
        policy.set_blocks([economy.section] if economy.section else [])
    return policy


def _create_pending_policy_transition(
    *,
    class_id,
    domain,
    change_payload,
    created_by,
    activation_mode='next_payroll',
    created_at=None,
):
    created_at = created_at or datetime.now(timezone.utc)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:create-transition:{class_id}:{domain}:{activation_mode}:{created_by}"):
        latest_version = (
            PolicyVersion.query.filter_by(class_id=class_id, domain=domain)
            .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
            .first()
        )
        next_version_number = (latest_version.version_number if latest_version else 0) + 1

        source_payload = {
            'type': change_payload.get('type'),
            'new_value': str(change_payload.get('current_value') or change_payload.get('new_value')),
        }
        if change_payload.get('policy_id') is not None:
            source_payload['policy_id'] = change_payload['policy_id']

        source_version = PolicyVersion(
            class_id=class_id,
            domain=domain,
            version_number=next_version_number,
            policy_payload_json=json.dumps(source_payload),
            is_active=True,
            created_at=created_at,
            activated_at=created_at,
        )
        db.session.add(source_version)
        db.session.flush()

        target_version = PolicyVersion(
            class_id=class_id,
            domain=domain,
            version_number=next_version_number + 1,
            policy_payload_json=json.dumps(change_payload),
            is_active=False,
            created_at=created_at,
        )
        db.session.add(target_version)
        db.session.flush()

        transition = PolicyTransition(
            class_id=class_id,
            domain=domain,
            source_policy_version_id=source_version.id,
            target_policy_version_id=target_version.id,
            activation_mode=activation_mode,
            status='pending',
            created_at=created_at,
            created_by=created_by,
        )
        db.session.add(transition)
        db.session.flush()
    return transition


def test_checker_uses_feature_policy_mode_for_recommendations(client):
    admin, payroll_settings, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')

    default_checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id, policy_mode='default')
    default_recommendations = default_checker.analyze_economy(payroll_settings).recommendations

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}"):
        db.session.add(FeatureSettings(class_id=economy.class_id, economy_policy_mode='tight'))
        db.session.flush()

    tight_checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id)
    tight_recommendations = tight_checker.analyze_economy(payroll_settings).recommendations

    assert tight_checker.policy_mode == 'tight'
    assert tight_recommendations['rent']['recommended'] > default_recommendations['rent']['recommended']
    assert tight_recommendations['utilities']['recommended'] > default_recommendations['utilities']['recommended']
    assert tight_recommendations['fine']['min'] > default_recommendations['fine']['min']
    assert tight_recommendations['store_tiers']['standard']['max'] < default_recommendations['store_tiers']['standard']['max']
    assert tight_recommendations['store_tiers']['premium']['max'] < default_recommendations['store_tiers']['premium']['max']
    assert tight_recommendations['store_tiers']['luxury']['max'] < default_recommendations['store_tiers']['luxury']['max']
    assert tight_recommendations['min_weekly_savings'] < default_recommendations['min_weekly_savings']


def test_comfortable_policy_uses_requested_ratio_profile(client):
    admin, payroll_settings, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')

    checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id, policy_mode='comfortable')
    recommendations = checker.analyze_economy(payroll_settings).recommendations

    cwi = float(payroll_settings.pay_rate) * payroll_settings.expected_weekly_hours * 60
    assert recommendations['utilities']['min'] == round(cwi * 0.04, 2)
    assert recommendations['utilities']['max'] == round(cwi * 0.08, 2)
    assert recommendations['fine']['max'] == round(cwi * 0.12, 2)
    assert recommendations['store_tiers']['basic']['min'] == round(cwi * 0.02, 2)
    assert recommendations['store_tiers']['basic']['max'] == round(cwi * 0.04, 2)
    assert recommendations['store_tiers']['standard']['min'] == round(cwi * 0.03, 2)
    assert recommendations['store_tiers']['standard']['max'] == round(cwi * 0.06, 2)
    assert recommendations['store_tiers']['premium']['min'] == round(cwi * 0.06, 2)
    assert recommendations['store_tiers']['premium']['max'] == round(cwi * 0.18, 2)
    assert recommendations['store_tiers']['luxury']['min'] == round(cwi * 0.18, 2)
    assert recommendations['store_tiers']['luxury']['max'] == round(cwi * 0.35, 2)
    assert recommendations['min_weekly_savings'] == round(cwi * 0.15, 2)
    assert recommendations['insurance_premium_weekly']['min'] == round(cwi * 0.04, 2)
    assert recommendations['insurance_premium_weekly']['max'] == round(cwi * 0.10, 2)
    assert recommendations['insurance_coverage']['multiplier_min'] == 4.0
    assert recommendations['insurance_coverage']['multiplier_max'] == 6.0
    assert recommendations['insurance_period_cap']['multiplier_min'] == 8.0
    assert recommendations['insurance_period_cap']['multiplier_max'] == 12.0
    assert recommendations['insurance_waiting_period_days']['min'] == 3
    assert recommendations['insurance_waiting_period_days']['max'] == 7


def test_insurance_premium_recommendation_matches_checker_output(client):
    admin, payroll_settings, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')

    checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id, policy_mode='default')
    analysis = checker.analyze_economy(payroll_settings)
    recommendation = get_insurance_premium_recommendation(
        'default',
        Decimal(str(analysis.cwi.cwi)),
        frequency='monthly',
    )

    assert recommendation is not None
    assert recommendation['min_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['min'])).quantize(Decimal('0.01'))
    assert recommendation['max_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['max'])).quantize(Decimal('0.01'))
    assert recommendation['recommended_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['recommended'])).quantize(Decimal('0.01'))
    assert recommendation['min'] == Decimal('16.31')
    assert recommendation['max'] == Decimal('39.13')
    assert recommendation['recommended'] == Decimal('26.09')


def test_price_recommendation_context_centralizes_policy_output(client):
    context = get_price_recommendation_context('comfortable', Decimal('50.00'))

    assert context is not None
    assert context['policy_mode'] == 'comfortable'
    assert context['rent_weekly']['recommended'] == 28.75
    assert context['rent']['recommended'] == 125.01
    assert context['insurance_premium_weekly']['recommended'] == 3.5
    assert context['insurance_coverage']['multiplier_recommended'] == 5.0
    assert context['store_tiers']['premium']['max'] == 9.0


def test_convert_weekly_amount_to_frequency_supports_custom_schedules(client):
    assert convert_weekly_amount_to_frequency(Decimal('10.00'), 'weekly') == Decimal('10.00')
    assert convert_weekly_amount_to_frequency(Decimal('10.00'), 'monthly') == Decimal('43.48')
    assert convert_weekly_amount_to_frequency(
        Decimal('10.00'),
        'custom',
        custom_frequency_value=2,
        custom_frequency_unit='weeks',
    ) == Decimal('20.00')


def test_edit_insurance_policy_renders_shared_recommendation_text(client):
    admin, _, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    policy = _create_insurance_policy(admin.id, 'Coverage', Decimal('40.00'), economy=economy)
    _login_admin(client, admin.id, class_id=economy.class_id)

    response = client.get(f'/admin/insurance/edit/{policy.id}')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Keep monthly premium costs in the $16.31-$39.13 range.' in html
    assert 'Ideal target: $26.09' in html


def test_update_economy_policy_creates_block_scoped_settings(client):
    admin, _, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    _login_admin(client, admin.id, class_id=economy.class_id)

    response = client.post('/admin/economy-policy', data={
        'policy_mode': 'comfortable',
        'block': 'A',
    })

    assert response.status_code == 302
    assert 'review_rebalance=1' in response.location

    settings_row = FeatureSettings.query.filter_by(class_id=economy.class_id).first()
    assert settings_row is not None
    assert settings_row.economy_policy_mode == 'comfortable'


def test_get_feature_settings_row_for_class_requires_explicit_class_scope(client):
    admin, _, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    read_row = get_feature_settings_row_for_class(economy.class_id, create=False)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:create-feature-settings:{economy.class_id}"):
        created_row = get_feature_settings_row_for_class(
            economy.class_id,
            create=True,
        )

    assert read_row is None
    assert created_row is not None
    assert created_row.class_id == economy.class_id


def test_rent_warnings_report_single_monthly_conversion(client):
    admin, payroll_settings, _, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id, policy_mode='default')
    cwi = checker.calculate_cwi(payroll_settings).cwi
    high_rent = RentSettings(
        class_id=economy.class_id,
        rent_amount=Decimal('600.00'),
        frequency_type='monthly',
    )

    warnings = checker.check_rent_balance(high_rent, cwi)

    rent_warning = next(w for w in warnings if w.feature == 'Rent' and w.level in (WarningLevel.WARNING, WarningLevel.CRITICAL))
    assert round(float(rent_warning.recommended_max), 2) == round(cwi * 0.75 * checker.AVERAGE_WEEKS_PER_MONTH, 2)


def test_immediate_rebalance_updates_rent_setting(client):
    admin, payroll_settings, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    _login_admin(client, admin.id, class_id=economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:immediate"):
        db.session.add(FeatureSettings(class_id=economy.class_id, economy_policy_mode='tight'))

    checker = EconomyBalanceChecker(admin.id, 'A', class_id=economy.class_id, policy_mode='tight')
    expected_rent = Decimal(str(checker.analyze_economy(payroll_settings).recommendations['rent']['recommended']))

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'immediate',
        'confirm_immediate': 'yes',
        'selected_changes': ['rent'],
    })

    assert response.status_code == 302
    scoped_rent = RentSettings.query.filter_by(
        class_id=economy.class_id,
    ).first()
    assert scoped_rent is not None
    assert scoped_rent.rent_amount == expected_rent


def test_rebalanced_rent_amount_does_not_backdate_current_coverage_due(client):
    _, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    rent_settings.rent_amount = Decimal('620.00')
    rent_settings.updated_at = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

    coverage_due_date = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    prior_cycle_payment = RentPayment(
        amount_paid=Decimal('500.00'),
        payment_date=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
    )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:coverage-paid:{economy.class_id}"):
        assessment = ObligationAssessment(
            seat_id=make_student_identity(class_id=economy.class_id, first_name="Coverage", last_name="Smith").id,
            class_id=economy.class_id,
            join_code=economy.join_code,
            obligation_type="RENT",
            amount_snap=Decimal("500.00"),
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            cycle_idempotency_key=f"coverage:{economy.class_id}:2026-03",
        )
        db.session.add(assessment)
        db.session.flush()
        db.session.add(ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=Decimal("500.00"),
            late_fee_charged=Decimal("0.00"),
            satisfied_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        ))
        db.session.flush()

        assert _is_coverage_period_paid(
            rent_settings,
            [assessment],
            coverage_due_date,
            include_late_fee=False,
        )


def test_class_scope_cycle_locks_rent_rate_after_first_payment(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    join_code = "LOCKA1"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:lock-cycle:{economy.class_id}"):
        lock_class = ClassEconomy(
            join_code=join_code,
            user_id=admin.id,
            display_name='Period A Lock',
        )
        db.session.add(lock_class)
        db.session.flush()
        coverage_due_date = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

        seat = make_student_identity(first_name="Rate", last_name="Lock", class_id=lock_class.class_id)

        payment_date = datetime(2026, 3, 5, 8, 0, tzinfo=timezone.utc)
        assessment = ObligationAssessment(
            seat_id=seat.id,
            class_id=lock_class.class_id,
            join_code=join_code,
            obligation_type="RENT",
            amount_snap=Decimal("500.00"),
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            cycle_idempotency_key=f"lock-cycle:{lock_class.class_id}:2026-03",
        )
        db.session.add(assessment)
        db.session.flush()
        db.session.add(ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=Decimal("500.00"),
            late_fee_charged=Decimal("0.00"),
            satisfied_at=payment_date,
        ))
        db.session.add(Transaction(
            seat_id=seat.id,
            user_id=seat.user_id,
            class_id=lock_class.class_id,
            join_code=join_code,
            type="Rent Payment",
            amount=Decimal("-500.00"),
            timestamp=payment_date,
            description="Rent payment",
        ))

        rent_settings.rent_amount = Decimal("620.00")
        rent_settings.updated_at = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:lock-cycle-check:{economy.class_id}"):
        effective_amount = _get_effective_rent_amount_for_coverage_period(
            rent_settings,
            assessments=[assessment],
            coverage_due_date=coverage_due_date,
            class_id=lock_class.class_id,
        )

        assert effective_amount == Decimal("500.00")


def test_invalid_activation_mode_is_rejected(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    _login_admin(client, admin.id, class_id=economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:invalid-mode"):
        db.session.add(FeatureSettings(class_id=economy.class_id, economy_policy_mode='tight'))

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'later',
        'selected_changes': ['rent'],
    })

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('500.00')


def test_rebalance_ignores_cross_teacher_selected_ids(client):
    admin_a, _, _, economy_a = _create_admin_with_block('A', join_code='JOINPOLA')
    admin_b, _, _, economy = _create_admin_with_block('B', join_code='JOINPOLB')
    policy_a = _create_insurance_policy(admin_a.id, 'Teacher A Policy', '20.00', economy=economy_a)
    policy_b = _create_insurance_policy(admin_b.id, 'Teacher B Policy', '99.00', economy=economy)
    _login_admin(client, admin_a.id, class_id=economy_a.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy_a.class_id}:cross-teacher"):
        db.session.add(FeatureSettings(class_id=economy_a.class_id, economy_policy_mode='tight'))

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'immediate',
        'confirm_immediate': 'yes',
        'selected_changes': [f'insurance_{policy_b.id}'],
    })

    assert response.status_code == 302
    db.session.refresh(policy_a)
    db.session.refresh(policy_b)
    assert policy_a.premium == Decimal('20.00')
    assert policy_b.premium == Decimal('99.00')


def test_economy_rebalance_context_uses_explicit_class_id_not_block_label(client):
    admin = seed_canonical_admin("policy_block_guard", "secret").user
    with FEATContext("FEAT-IDEN-001", idempotency_key="economy-policy:block-guard:a"):
        class_a = create_class_scope(
            teacher_user=admin,
            join_code="ECONA1",
            display_name="Period A One",
            section="A",
        )
        class_b = create_class_scope(
            teacher_user=admin,
            join_code="ECONA2",
            display_name="Period A Two",
            section="A",
        )
        payroll_a = PayrollSettings(
            class_id=class_a.class_id,
            pay_rate=Decimal('0.25'),
            expected_weekly_hours=5.0,
            payroll_frequency_days=14,
            settings_mode='simple',
            is_active=True,
        )
        payroll_b = PayrollSettings(
            class_id=class_b.class_id,
            pay_rate=Decimal('0.75'),
            expected_weekly_hours=5.0,
            payroll_frequency_days=14,
            settings_mode='simple',
            is_active=True,
        )
        rent_a = RentSettings(
            class_id=class_a.class_id,
            rent_amount=Decimal('500.00'),
            frequency_type='monthly',
        )
        rent_b = RentSettings(
            class_id=class_b.class_id,
            rent_amount=Decimal('900.00'),
            frequency_type='monthly',
        )
        db.session.add_all([payroll_a, payroll_b, rent_a, rent_b])
        db.session.flush()

    from app.routes.admin import _load_economy_rebalance_context

    class CanonicalContext:
        def __init__(self, user_id, class_id):
            self.user_id = user_id
            self.class_id = class_id

    effective_block, payroll_settings, rent_settings, insurance_policies, all_payroll_settings = _load_economy_rebalance_context(
        CanonicalContext(admin.id, class_a.class_id),
        class_a.class_id,
        "A",
    )

    assert effective_block == "A"
    assert payroll_settings is not None
    assert payroll_settings.class_id == class_a.class_id
    assert rent_settings is not None
    assert rent_settings.class_id == class_a.class_id
    assert all_payroll_settings is not None
    assert len(all_payroll_settings) >= 2
    assert insurance_policies == []


def test_run_payroll_applies_scheduled_rebalance(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    _login_admin(client, admin.id, class_id=economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:run-payroll"):
        db.session.add(FeatureSettings(
            class_id=economy.class_id,
            economy_policy_mode='tight',
        ))
        _create_pending_policy_transition(
            class_id=economy.class_id,
            domain='rent',
            change_payload={
                'type': 'rent',
                'block': 'A',
                'join_code': 'JOINPOLA',
                'current_value': '500.00',
                'new_value': '610.00',
            },
            created_by=admin.id,
            activation_mode='next_payroll',
        )

    response = client.post('/admin/run_payroll', data={'block': 'A'})

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('610.00')


def test_next_renewal_rebalance_schedules_rent_for_next_cycle(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    _login_admin(client, admin.id, class_id=economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:next-renewal"):
        db.session.add(FeatureSettings(class_id=economy.class_id, economy_policy_mode='tight'))

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'next_renewal',
        'selected_changes': ['rent'],
    })

    pending_transition = PolicyTransition.query.filter_by(
        class_id=economy.class_id,
        status='pending',
        domain='rent',
    ).first()
    target_version = db.session.get(PolicyVersion, pending_transition.target_policy_version_id) if pending_transition else None
    target_payload = json.loads(target_version.policy_payload_json) if target_version else {}

    assert response.status_code == 302
    assert pending_transition is not None
    assert pending_transition.activation_mode == REBALANCE_ACTIVATION_NEXT_RENEWAL
    assert target_version is not None
    assert target_payload['type'] == 'rent'
    assert target_payload.get('effective_at') is not None
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('500.00')


def test_activate_due_rebalances_applies_past_due_rent_change(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:past-due"):
        db.session.add(FeatureSettings(
            class_id=economy.class_id,
            economy_policy_mode='tight',
        ))
        _create_pending_policy_transition(
            class_id=economy.class_id,
            domain='rent',
            change_payload={
                'type': 'rent',
                'block': 'A',
                'join_code': 'JOINPOLA',
                'current_value': '500.00',
                'new_value': '610.00',
                'effective_at': '2026-03-01T00:00:00+00:00',
            },
            created_by=admin.id,
            activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:activate-due:{economy.class_id}:past-due"):
        activated, labels = activate_due_rebalances(
            admin.id,
            reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.session.refresh(rent_settings)
        assert activated == 1
        assert labels == ['Rent']
        assert rent_settings.rent_amount == Decimal('610.00')


def test_activate_due_rebalances_explicit_class_scope_applies_due_transition(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy.class_id}:explicit-scope"):
        db.session.add(FeatureSettings(
            class_id=economy.class_id,
            economy_policy_mode='tight',
        ))
        _create_pending_policy_transition(
            class_id=economy.class_id,
            domain='rent',
            change_payload={
                'type': 'rent',
                'block': 'A',
                'join_code': 'JOINPOLA',
                'current_value': '500.00',
                'new_value': '615.00',
                'effective_at': '2026-03-01T00:00:00+00:00',
            },
            created_by=admin.id,
            activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:activate-due:{economy.class_id}:explicit"):
        activated, labels = activate_due_rebalances(
            admin.id,
            class_id=economy.class_id,
            reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.session.refresh(rent_settings)
        assert activated == 1
        assert labels == ['Rent']
        assert rent_settings.rent_amount == Decimal('615.00')


def test_activate_due_rebalances_keeps_rent_mutation_in_settings_row_class(client):
    admin, _, rent_settings_a, economy_a = _create_admin_with_block('A', join_code='JOINPOLA')

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:create-cross-class:{economy_a.class_id}"):
        economy_b = ClassEconomy(
            join_code='JOINPOLB',
            user_id=admin.id,
            display_name='Period B',
        )
        db.session.add(economy_b)
        db.session.flush()
        db.session.add(Seat(
            class_id=economy_b.class_id,
            role="teacher",
        ))

        rent_settings_b = RentSettings(
            class_id=economy_b.class_id,
            rent_amount=Decimal('700.00'),
            frequency_type='monthly',
        )
        db.session.add(FeatureSettings(
            class_id=economy_a.class_id,
            economy_policy_mode='tight',
        ))
        _create_pending_policy_transition(
            class_id=economy_a.class_id,
            domain='rent',
            change_payload={
                'type': 'rent',
                # Malicious/mismatched payload scope should not redirect class mutation.
                'block': 'B',
                'join_code': 'JOINPOLB',
                'current_value': '500.00',
                'new_value': '610.00',
            },
            created_by=admin.id,
            activation_mode='next_payroll',
        )
        db.session.add(rent_settings_b)

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:activate-due:{economy_a.class_id}:cross-class"):
        activated, labels = activate_due_rebalances(
            admin.id,
            reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.session.refresh(rent_settings_a)
        db.session.refresh(rent_settings_b)
        assert activated == 1
        assert labels == ['Rent']
        assert rent_settings_a.rent_amount == Decimal('610.00')
        assert rent_settings_b.rent_amount == Decimal('700.00')


def test_activate_due_rebalances_does_not_mutate_cross_class_insurance_policy(client):
    admin, _, _, economy_a = _create_admin_with_block('A', join_code='JOINPOLA')
    economy_b = create_class_scope(
        teacher_user=db.session.get(User, admin.id),
        join_code='JOINPOLB',
        display_name='Period B',
        section='B',
    )
    policy_b = _create_insurance_policy(admin.id, 'Cross Class Policy', '99.00', economy=economy_b)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:set-tight:{economy_a.class_id}:insurance"):
        db.session.add(FeatureSettings(
            class_id=economy_a.class_id,
            economy_policy_mode='tight',
        ))
        _create_pending_policy_transition(
            class_id=economy_a.class_id,
            domain='insurance',
            change_payload={
                'type': 'insurance',
                # Policy from another class for the same teacher.
                'policy_id': policy_b.id,
                'current_value': '99.00',
                'new_value': '130.00',
            },
            created_by=admin.id,
            activation_mode='next_payroll',
        )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:activate-due:{economy_a.class_id}:insurance"):
        activated, labels = activate_due_rebalances(
            admin.id,
            reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.session.refresh(policy_b)
        assert activated == 0
        assert labels == []
        assert policy_b.premium == Decimal('99.00')


def test_prepare_scheduled_rebalance_changes_sets_rent_effective_at(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')

    changes = prepare_scheduled_rebalance_changes(
        [{
            'type': 'rent',
            'block': 'A',
            'join_code': 'JOINPOLA',
            'current_value': '500.00',
            'new_value': '610.00',
        }],
        rent_settings=rent_settings,
        reference_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
    )

    assert len(changes) == 1
    assert changes[0]['effective_at'] is not None


def test_activate_due_rebalances_applies_pending_policy_transition_without_legacy_payload(client):
    admin, _, rent_settings, economy = _create_admin_with_block('A', join_code='JOINPOLA')
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:legacy-payload:{economy.class_id}"):
        settings_row = FeatureSettings.query.filter_by(class_id=economy.class_id).first()
        if settings_row is None:
            settings_row = FeatureSettings(
                class_id=economy.class_id,
                economy_policy_mode='default',
            )
            db.session.add(settings_row)
            db.session.flush()

        source_version = PolicyVersion(
            class_id=economy.class_id,
            domain='rent',
            version_number=1,
            policy_payload_json=json.dumps({'type': 'rent', 'new_value': '500.00'}),
            is_active=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            activated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        db.session.add(source_version)
        db.session.flush()

        target_version = PolicyVersion(
            class_id=economy.class_id,
            domain='rent',
            version_number=2,
            policy_payload_json=json.dumps({
                'type': 'rent',
                'new_value': '650.00',
                'effective_at': '2026-03-15T00:00:00+00:00',
            }),
            is_active=False,
            created_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        db.session.add(target_version)
        db.session.flush()

        transition = PolicyTransition(
            class_id=economy.class_id,
            domain='rent',
            source_policy_version_id=source_version.id,
            target_policy_version_id=target_version.id,
            activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL,
            status='pending',
            created_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            created_by=admin.id,
        )
        db.session.add(transition)

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"economy-policy:activate-due:{economy.class_id}:legacy"):
        activated, labels = activate_due_rebalances(
            admin.id,
            reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.session.refresh(rent_settings)
        db.session.refresh(source_version)
        db.session.refresh(target_version)
        db.session.refresh(transition)

        assert activated == 1
        assert labels == ['Rent']
        assert rent_settings.rent_amount == Decimal('650.00')
        assert source_version.is_active is False
        assert target_version.is_active is True
        assert transition.status == 'applied'
