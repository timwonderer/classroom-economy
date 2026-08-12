"""
Class Configuration Query Service — Phase 3 Primitives

Authority: DOM-CLASS-001, DOM-CLASS-002, DOM-CLASS-003
Implements: 16 read-only query functions for class configuration domain

Per SPEC-TIME-001: All temporal queries use canonical_temporal_resolver()
Per SPEC-ECON-002: effective_at parameter enables future-law visibility
Per multi-tenancy rules: All queries scoped by class_id (never teacher_id alone)
"""

from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import (
    BankingSettings,
    ClassEconomy,
    ClassFeature,
    EconomicEngine,
    HallPassSettings,
    PayrollSettings,
    RentSettings,
)
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


# Advisory thresholds for economic-mode guidance (student-hours per week)
_TIGHT_CAPACITY_CEILING = 500
_DEFAULT_CAPACITY_CEILING = 1500

# Payroll rate guardrails (dollars per hour)
_MAX_HOURLY_PAY_RATE = 100
_TIGHT_MODE_RATE_WARNING = 10
_COMFORTABLE_MODE_RATE_WARNING = 5


def _resolve_query_time(effective_at: Optional[datetime]) -> datetime:
    """Resolve the query timestamp via the canonical temporal resolver (SPEC-TIME-001).

    Args:
        effective_at: Explicit timezone-aware UTC datetime, or None to use canonical now.

    Returns:
        Timezone-aware UTC datetime for query scoping.
    """
    if effective_at is not None:
        return effective_at
    result = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time"
    )
    return result.canonical_now_utc


# ============================================================================
# 1. CLASS ENTITY QUERIES (1 function)
# ============================================================================


def get_class_economy(class_id: str) -> Optional[ClassEconomy]:
    """Get the ClassEconomy entity for a class.

    Args:
        class_id: The class to retrieve (UUID)

    Returns:
        ClassEconomy instance or None if not found

    Example:
        economy = get_class_economy("abc123-def456")
        if economy:
            print(f"Class: {economy.display_name}, Timezone: {economy.class_timezone}")
    """
    return ClassEconomy.query.filter_by(class_id=class_id).first()


# ============================================================================
# 2. ECONOMIC ENGINE QUERIES (3 functions)
# ============================================================================


def get_effective_economic_engine(
    class_id: str,
    feature: str,
    effective_at: Optional[datetime] = None,
) -> Optional[EconomicEngine]:
    """Get the EconomicEngine that governs a specific feature at a specific time.

    Returns the immutable economic policy version that is effective for the given
    feature and timestamp. This enables querying current, historical, and future
    policy across feature-scoped timelines.

    Args:
        class_id: The class (UUID)
        feature: Feature name ('store', 'rent', 'payroll', 'hall_pass', etc.) [REQUIRED]
        effective_at: Timezone-aware UTC datetime to query at (default: canonical now via SPEC-TIME-001)

    Returns:
        EconomicEngine instance that governs this (class, feature, time), or None if not found

    Example:
        # Current policy
        store_engine = get_effective_economic_engine(class_id, "store")
        # Returns Engine B if teacher switched on Day 5

        # Historical query (what governed rent on Day 10?)
        past_engine = get_effective_economic_engine(class_id, "rent", day_10)
        # Returns Engine A (if switch was scheduled for Day 20)

        # Future query (what will govern rent on Day 25?)
        future_engine = get_effective_economic_engine(class_id, "rent", day_25)
        # Returns Engine B (precomputed timeline)
    """
    query_time = _resolve_query_time(effective_at)

    # Find the most-recent-effective ClassFeature for this (class, feature) pair
    # where effective_at <= query_time and feature is enabled (has economic_version_id)
    class_feature = ClassFeature.query.filter(
        ClassFeature.class_id == class_id,
        ClassFeature.feature == feature,
        ClassFeature.effective_at <= query_time,
        ClassFeature.economic_version_id.isnot(None),
    ).order_by(
        ClassFeature.effective_at.desc()  # Most recent effective_at first
    ).first()

    if not class_feature:
        return None

    return db.session.get(EconomicEngine, class_feature.economic_version_id)


def get_initial_economic_engine(class_id: str) -> Optional[EconomicEngine]:
    """Get the original (first) EconomicEngine created for a class.

    Returns the immutable economic policy version that was active when the class
    was created. Useful for analytics, baseline comparisons, or understanding
    the original economy design. This engine is never authoritative over current
    policy—it's simply the earliest immutable version in the timeline.

    Args:
        class_id: The class (UUID)

    Returns:
        EconomicEngine linked by the ClassFeature with earliest effective_at,
        or None if not found

    Example:
        # Show teacher the original economy they designed
        initial = get_initial_economic_engine(class_id)
        if initial:
            print(f"Original mode: {initial.economy_policy_mode}")
    """
    # Find the earliest ClassFeature (first feature ever created for this class)
    # Include all rows (even disabled) to find the true original engine
    class_feature = ClassFeature.query.filter(
        ClassFeature.class_id == class_id,
    ).order_by(
        ClassFeature.effective_at.asc()  # Earliest effective_at first
    ).first()

    if not class_feature:
        return None

    return db.session.get(EconomicEngine, class_feature.economic_version_id)


def get_economic_engine_history(class_id: str) -> list[EconomicEngine]:
    """Get all EconomicEngine versions for a class in chronological order.

    Ordered by created_at DESC (most recent first).

    Args:
        class_id: The class to retrieve history for (UUID)

    Returns:
        List of EconomicEngine instances, ordered by creation time (may be empty)

    Note:
        Use created_at (not effective_at, which does not exist on EconomicEngine).
        Traverse previous_version_id for audit lineage (INV-ARC-016).

    Example:
        history = get_economic_engine_history(classroom.class_id)
        for engine in history:
            print(f"Version created at {engine.created_at}: mode={engine.economy_policy_mode}")
    """
    return EconomicEngine.query.filter_by(
        class_id=class_id
    ).order_by(
        EconomicEngine.created_at.desc()
    ).all()


# ============================================================================
# 3. CLASS FEATURE QUERIES (3 functions)
# ============================================================================


def get_class_features(
    class_id: str,
    effective_at: Optional[datetime] = None,
) -> dict[str, ClassFeature]:
    """Get all enabled class features for a class, keyed by feature name.

    Returns the state of features as of effective_at (default: canonical now).
    Only features with a linked economic_version_id are considered enabled.

    Args:
        class_id: The class to retrieve features for (UUID)
        effective_at: Timezone-aware UTC datetime to query feature state at
            (default: canonical now via SPEC-TIME-001)

    Returns:
        Dict mapping feature name -> ClassFeature instance
        Empty dict if class has no enabled features

    Example:
        features = get_class_features(classroom.class_id)
        if 'payroll' in features:
            print(f"Payroll enabled since {features['payroll'].effective_at}")
    """
    query_time = _resolve_query_time(effective_at)

    # Query all ClassFeature rows for this class that are enabled at query_time
    # Enabled = has economic_version_id and effective_at <= query_time
    class_features = ClassFeature.query.filter(
        ClassFeature.class_id == class_id,
        ClassFeature.effective_at <= query_time,
        ClassFeature.economic_version_id.isnot(None),
    ).all()

    # Group by feature name, returning latest effective_at for each
    result_dict = {}
    for feature in class_features:
        current = result_dict.get(feature.feature)
        if current is None or feature.effective_at > current.effective_at:
            result_dict[feature.feature] = feature

    return result_dict


def get_class_feature(
    class_id: str,
    feature: str,
    effective_at: Optional[datetime] = None,
) -> Optional[ClassFeature]:
    """Get a specific class feature by name.

    Args:
        class_id: The class (UUID)
        feature: Feature name (e.g., 'payroll', 'hall_pass', 'rent')
        effective_at: Timezone-aware UTC datetime to query at
            (default: canonical now via SPEC-TIME-001)

    Returns:
        ClassFeature instance or None if not found/disabled

    Example:
        payroll_feature = get_class_feature(classroom.class_id, 'payroll')
        if payroll_feature:
            print(f"Payroll effective since {payroll_feature.effective_at}")
    """
    features = get_class_features(class_id, effective_at)
    return features.get(feature)


def get_class_feature_history(class_id: str, feature: str) -> list[ClassFeature]:
    """Get all versions of a specific class feature in chronological order.

    Ordered by effective_at DESC (most recent first). Includes all rows
    (enabled and disabled) for audit trail visibility.

    Args:
        class_id: The class (UUID)
        feature: Feature name

    Returns:
        List of ClassFeature instances (may be empty)

    Example:
        payroll_history = get_class_feature_history(classroom.class_id, 'payroll')
        for version in payroll_history:
            status = "enabled" if version.economic_version_id else "disabled"
            print(f"Payroll {status} from {version.effective_at}")
    """
    return ClassFeature.query.filter_by(
        class_id=class_id,
        feature=feature
    ).order_by(
        ClassFeature.effective_at.desc()
    ).all()


# ============================================================================
# 4. SETTINGS QUERIES (4 functions)
# ============================================================================


def get_payroll_settings(class_id: str) -> Optional[PayrollSettings]:
    """Get payroll configuration for a class.

    Includes pay_rate ($/minute), expected_weekly_hours.

    Args:
        class_id: The class (UUID)

    Returns:
        PayrollSettings instance or None

    Example:
        payroll = get_payroll_settings(classroom.class_id)
        if payroll:
            hourly = float(payroll.pay_rate) * 60
            print(f"Rate: ${hourly}/hr, Expected hours: {payroll.expected_weekly_hours}")
    """
    return PayrollSettings.query.filter_by(
        class_id=class_id,
        is_active=True,
    ).order_by(
        PayrollSettings.block.is_(None).desc(),
        PayrollSettings.id.desc(),
    ).first()


def get_rent_settings(class_id: str) -> Optional[RentSettings]:
    """Get rent configuration for a class.

    Includes rent_amount, due_day_of_month, first_rent_due_date, grace period.

    Args:
        class_id: The class (UUID)

    Returns:
        RentSettings instance or None

    Example:
        rent = get_rent_settings(classroom.class_id)
        if rent:
            print(f"Students owe ${rent.rent_amount} on day {rent.due_day_of_month}")
    """
    return RentSettings.query.filter_by(class_id=class_id).first()


def get_banking_settings(class_id: str) -> Optional[BankingSettings]:
    """Get banking configuration for a class.

    Includes savings_apy, interest_calculation_type, interest_schedule_type.

    Args:
        class_id: The class (UUID)

    Returns:
        BankingSettings instance or None

    Example:
        banking = get_banking_settings(classroom.class_id)
        if banking:
            print(f"Savings APY: {banking.savings_apy}%, Schedule: {banking.interest_schedule_type}")
    """
    return BankingSettings.query.filter_by(
        class_id=class_id,
        is_active=True,
    ).order_by(
        BankingSettings.block.is_(None).desc(),
        BankingSettings.id.desc(),
    ).first()


def get_hall_pass_settings(class_id: str) -> Optional[HallPassSettings]:
    """Get hall pass configuration for a class.

    Includes queue_enabled, queue_limit, pass_types.

    Args:
        class_id: The class (UUID)

    Returns:
        HallPassSettings instance or None

    Example:
        hp = get_hall_pass_settings(classroom.class_id)
        if hp:
            print(f"Queue enabled: {hp.queue_enabled}, Limit: {hp.queue_limit}")
    """
    return HallPassSettings.query.filter_by(class_id=class_id).first()


# ============================================================================
# 5. CWI & ECONOMIC DERIVED VALUES (2 functions)
# ============================================================================


def calculate_cwi(class_id: str) -> Optional[float]:
    """Calculate the current Classroom Wage Index (CWI) for a class.

    CWI = (pay_rate * 60) * expected_weekly_hours

    pay_rate is stored as $/minute; we convert to $/hour before multiplying
    by expected_weekly_hours to produce the weekly earning reference value.

    The expected_weekly_hours is a teacher-configured reference value representing
    the expected number of hours a student should be active in a week. Actual weekly
    payout varies based on day-to-day student activity, not this reference value.

    Args:
        class_id: The class (UUID)

    Returns:
        CWI as a float ($/week), or None if payroll settings not found

    Example:
        cwi = calculate_cwi(classroom.class_id)
        if cwi:
            print(f"CWI: ${cwi}/week")
    """
    payroll = get_payroll_settings(class_id)
    if not payroll:
        return None

    # CWI combines teacher-configured pay rate with teacher-configured expected weekly hours
    # pay_rate is $/minute → convert to $/hour first
    if payroll.expected_weekly_hours is None:
        return None

    hourly_rate = float(payroll.pay_rate) * 60
    return hourly_rate * float(payroll.expected_weekly_hours)


def get_policy_mode(class_id: str, feature: str = 'payroll') -> Optional[str]:
    """Get the current economic policy mode for a class via a feature anchor.

    Looks up the EconomicEngine linked to the specified feature to determine
    the active policy mode. Defaults to the 'payroll' feature as the canonical
    anchor, since payroll is the most commonly enabled feature.

    Args:
        class_id: The class (UUID)
        feature: Feature to use as the engine anchor (default: 'payroll')

    Returns:
        Policy mode string ('tight', 'default', 'comfortable') or None
        if the feature is not enabled

    Example:
        mode = get_policy_mode(classroom.class_id)
        if mode == 'tight':
            print("Restricted economy")
    """
    engine = get_effective_economic_engine(class_id, feature)
    if not engine:
        return None

    return engine.economy_policy_mode


# ============================================================================
# 6. CONFIGURATION STATE QUERIES (2 functions)
# ============================================================================


def is_feature_enabled(class_id: str, feature: str) -> bool:
    """Check if a specific feature is enabled for a class.

    Returns True if feature has an active ClassFeature row with
    economic_version_id set and effective_at <= canonical now.

    Args:
        class_id: The class (UUID)
        feature: Feature name

    Returns:
        True if enabled, False otherwise

    Example:
        if is_feature_enabled(classroom.class_id, 'payroll'):
            print("Payroll is active")
    """
    return get_class_feature(class_id, feature) is not None


def get_all_classes_by_teacher(teacher_user_id: int) -> list[ClassEconomy]:
    """Get all classes owned by a teacher.

    Ordered by created_at DESC (most recent first).

    Args:
        teacher_user_id: The teacher's User.id

    Returns:
        List of ClassEconomy instances (may be empty)

    Example:
        classes = get_all_classes_by_teacher(teacher_user.id)
        for cls in classes:
            print(f"{cls.display_name} ({cls.join_code})")
    """
    return ClassEconomy.query.filter_by(
        teacher_user_id=teacher_user_id
    ).order_by(
        ClassEconomy.created_at.desc()
    ).all()


# ============================================================================
# 7. TEACHER-FACING CONFIGURATION GUIDANCE (2 functions)
# ============================================================================


def suggest_economic_mode(class_size: int, weekly_hours: float) -> str:
    """Suggest a policy mode based on class context.

    Returns advisory suggestion ("tight", "default", or "comfortable").
    Teachers can override the suggestion.

    Args:
        class_size: Number of students in class
        weekly_hours: Expected earning hours per week

    Returns:
        Suggested policy mode string

    Note:
        This is advisory only. Teachers retain full authority over policy selection.
        Suggestion algorithm considers class size and weekly earning potential.

    Example:
        suggested = suggest_economic_mode(class_size=25, weekly_hours=50)
        print(f"Suggested mode: {suggested}")
    """
    # Simple heuristic: larger classes with more earning hours → more generous economy
    weekly_capacity = class_size * weekly_hours

    if weekly_capacity < _TIGHT_CAPACITY_CEILING:
        return "tight"
    if weekly_capacity < _DEFAULT_CAPACITY_CEILING:
        return "default"
    return "comfortable"


def validate_payroll_rate(hourly_pay_rate: float, policy_mode: str) -> tuple[bool, Optional[str]]:
    """Validate a proposed hourly pay rate for reasonableness.

    Returns (is_valid, warning_message).
    - is_valid=True: rate accepted (may still have advisory warning)
    - is_valid=False: rate violates hard constraint

    Args:
        hourly_pay_rate: Proposed rate
        policy_mode: Class policy mode ('tight', 'default', 'comfortable')

    Returns:
        Tuple of (is_valid: bool, warning: str | None)

    Example:
        is_valid, warning = validate_payroll_rate(hourly_pay_rate=15.0, policy_mode='default')
        if not is_valid:
            print("Rate rejected")
        elif warning:
            print(f"Warning: {warning}")
    """
    # Hard constraints: hourly rate must be positive and reasonable
    if hourly_pay_rate <= 0:
        return False, "Hourly rate must be positive"

    if hourly_pay_rate > _MAX_HOURLY_PAY_RATE:
        return False, f"Hourly rate exceeds ${_MAX_HOURLY_PAY_RATE}/hour maximum"

    # Advisory warnings based on policy mode
    if policy_mode == "tight" and hourly_pay_rate > _TIGHT_MODE_RATE_WARNING:
        return True, f"Tight mode with rate > ${_TIGHT_MODE_RATE_WARNING}/hr may create imbalance"

    if policy_mode == "comfortable" and hourly_pay_rate < _COMFORTABLE_MODE_RATE_WARNING:
        return True, f"Comfortable mode with rate < ${_COMFORTABLE_MODE_RATE_WARNING}/hr may feel restrictive"

    return True, None
