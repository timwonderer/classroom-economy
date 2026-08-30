"""
Economy Balance Checker - Centralized CWI Calculator and Balance Validator

This module implements the economic-calculation authority SPEC-ECON-003 for
the Classroom Economy App. It provides tools to:
- Calculate CWI (Classroom Wage Index) dynamically
- Validate economy settings against standard ratios
- Generate teacher recommendations for balanced configurations
- Warn when settings deviate from CWI guidelines

Reference: SPEC-ECON-003 (Economic Engine Calculation & Reference Specification).
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from app.utils.economy_policy import (
    get_active_policy_mode,
    get_active_policy_mode_for_class,
    get_policy_profile,
    get_price_recommendation_context,
    normalize_policy_mode,
)


class WarningLevel(Enum):
    """Severity levels for economy balance warnings"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PricingTier(Enum):
    """Store item pricing tiers per SPEC-ECON-003 §4.8 (store tier reference)."""
    BASIC = "basic"           # 0.02-0.05 * CWI
    STANDARD = "standard"     # 0.05-0.10 * CWI
    PREMIUM = "premium"       # 0.10-0.25 * CWI
    LUXURY = "luxury"         # 0.25-0.50 * CWI


@dataclass
class CWICalculation:
    """Result of CWI calculation with breakdown"""
    cwi: float                          # Weekly expected income
    pay_rate: float                     # Pay rate per unit
    time_unit: str                      # Unit type (seconds, minutes, hours, days)
    pay_rate_per_minute: float         # Normalized to per-minute
    expected_weekly_minutes: float     # Expected attendance per week
    payroll_frequency_days: int        # How often payroll runs
    notes: List[str]                   # Calculation notes


@dataclass
class BalanceWarning:
    """A warning about economy imbalance"""
    feature: str                # Feature name (e.g., "Rent", "Insurance Premium")
    level: WarningLevel         # Severity level
    message: str               # Human-readable warning
    current_value: Optional[float]     # Current setting
    recommended_min: Optional[float]   # Recommended minimum
    recommended_max: Optional[float]   # Recommended maximum
    cwi_ratio: Optional[float]         # Ratio relative to CWI


@dataclass
class EconomyBalance:
    """Complete economy balance analysis"""
    cwi: CWICalculation
    is_balanced: bool
    warnings: List[BalanceWarning]
    recommendations: Dict[str, Any]
    budget_survival_test_passed: bool
    weekly_savings: Optional[float]


class EconomyBalanceChecker:
    """
    Centralized tool for calculating CWI and validating economy balance.

    All monetary values in the Classroom Economy must scale from CWI per SPEC-ECON-003 §4.1 (CWI derivation) and §6.2 (Class-Relative Comparison).
    This class provides the single source of truth for:
    - CWI calculation
    - Ratio-based validation
    - Teacher recommendations
    - Balance warnings
    """

    # Standard ratios; canonical reference per SPEC-ECON-003 §4 and §8 (Canonical Economic Reference Table)
    RENT_MIN_RATIO = 2.0
    RENT_MAX_RATIO = 2.5
    RENT_DEFAULT_RATIO = 2.25

    UTILITIES_MIN_RATIO = 0.20
    UTILITIES_MAX_RATIO = 0.30
    UTILITIES_DEFAULT_RATIO = 0.25

    # NOTE (SPEC-ECON-003 migration): insurance CWI-band and coverage/period-cap
    # multiplier constants were removed. Insurance economics are owned by the
    # Economic Engine (app/services/economic_engine.resolve_insurance).

    FINE_MIN_RATIO = 0.05
    FINE_MAX_RATIO = 0.15
    FINE_DEFAULT_RATIO = 0.10

    # Store item tier ratios
    STORE_TIERS = {
        PricingTier.BASIC: (0.02, 0.05),
        PricingTier.STANDARD: (0.05, 0.10),
        PricingTier.PREMIUM: (0.10, 0.25),
        PricingTier.LUXURY: (0.25, 0.50),
    }

    # Budget survival minimum
    MIN_WEEKLY_SAVINGS_RATIO = 0.10

    # Conversion helpers
    AVERAGE_WEEKS_PER_MONTH = 365.25 / 12 / 7

    # Conservative weekly store spending estimate
    ESTIMATED_WEEKLY_STORE_SPENDING_RATIO = 0.15

    # Thresholds for warnings
    MINOR_DEVIATION_THRESHOLD = 0.15  # 15% deviation = warning
    MAJOR_DEVIATION_THRESHOLD = 0.30  # 30% deviation = critical

    def __init__(
        self,
        user_id: int,
        policy_mode: Optional[str] = None,
        class_id: Optional[str] = None,
    ):
        """Initialize checker for a specific class owner.

        Args:
            user_id: The owning user ID
            policy_mode: Optional explicit policy mode (else resolved from class_id)
            class_id: The class scope for policy-mode resolution
        """
        self.user_id = user_id
        self.class_id = class_id
        resolved_mode_source = policy_mode
        if resolved_mode_source is None and class_id:
            resolved_mode_source = get_active_policy_mode_for_class(class_id)
        if resolved_mode_source is None:
            resolved_mode_source = get_active_policy_mode(user_id, class_id=class_id)
        resolved_mode = normalize_policy_mode(resolved_mode_source)
        self.policy_mode = resolved_mode
        self.policy_profile = get_policy_profile(resolved_mode)

    def _ratio_band(self, key: str, fallback_min: float, fallback_max: float, fallback_recommended: float) -> Tuple[float, float, float]:
        ratios = self.policy_profile.get("ratios", {}).get(key, {})
        return (
            float(ratios.get("min", fallback_min)),
            float(ratios.get("max", fallback_max)),
            float(ratios.get("recommended", fallback_recommended)),
        )

    def _minimum_ratio(self, key: str, fallback_value: float) -> float:
        ratios = self.policy_profile.get("ratios", {}).get(key, {})
        return float(ratios.get("min", fallback_value))

    def _store_tiers(self) -> Dict[PricingTier, Tuple[float, float]]:
        tiers = dict(self.STORE_TIERS)
        configured_tiers = self.policy_profile.get("ratios", {}).get("store_tiers", {})
        for tier in PricingTier:
            tier_config = configured_tiers.get(tier.value, {})
            tiers[tier] = (
                float(tier_config.get("min", self.STORE_TIERS[tier][0])),
                float(tier_config.get("max", self.STORE_TIERS[tier][1])),
            )
        return tiers

    def _normalize_to_weekly(
        self,
        value: Decimal,
        frequency: str,
        custom_frequency_value: Optional[Decimal] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> Decimal:
        """Normalize a value to its weekly equivalent based on frequency."""
        from app.models import _quantize_currency

        # Ensure value is Decimal for consistent arithmetic
        if not isinstance(value, Decimal):
            value = Decimal(str(value))

        if frequency == 'monthly':
            return _quantize_currency(value / Decimal(str(self.AVERAGE_WEEKS_PER_MONTH)))
        if frequency == 'weekly':
            return value
        if frequency == 'biweekly':
            return _quantize_currency(value / Decimal('2'))
        if frequency == 'daily':
            return _quantize_currency(value * Decimal('7'))
        if frequency == 'custom':
            # Default to days when unit is unspecified
            unit = (custom_frequency_unit or 'days').lower()
            freq_value = custom_frequency_value or Decimal('1')
            if unit == 'weeks':
                # Value is "per N weeks", so weekly equivalent is value / N
                return _quantize_currency(value / freq_value)
            if unit == 'months':
                return _quantize_currency(value / (Decimal(str(self.AVERAGE_WEEKS_PER_MONTH)) * freq_value))
            return _quantize_currency(value * (Decimal('7') / freq_value))

        return value

    def calculate_cwi(self, payroll_settings, expected_weekly_hours: float = None) -> CWICalculation | None:
        """
        Calculate CWI (Classroom Wage Index) - expected weekly income for perfect attendance.

        Args:
            payroll_settings: PayrollSettings model instance (source of pay_rate only)
            expected_weekly_hours: Expected hours of attendance per week.
                                   If None, reads from the EconomicEngine version governing
                                   the payroll feature for this class (authoritative source
                                   per DOM-CLASS-002).

        Returns:
            CWICalculation with breakdown, or None if `expected_weekly_hours` is
            unconfigured on both the parameter and the EconomicEngine. Callers must
            handle None (display "configure CWI on Economic Engine" warning; disable
            pricing recommendations).

        NOTE (SPEC-ECON-003 migration): the canonical CWI calculation authority is
        ``app/services/economic_engine.resolve_base`` (per SPEC-ECON-003 §3/§4.1).
        This is a pre-existing duplicate formula site retained during the
        conservative migration; it should be consolidated to consume ``resolve_base``
        once parity is proven for the balance-checker surface. Numerically identical
        today: ``pay_rate_per_minute × 60 × expected_weekly_hours``.
        """
        notes = []

        # Get expected weekly hours from EconomicEngine (canonical source) if not provided
        from app.models import _quantize_currency
        if expected_weekly_hours is None:
            try:
                from app.services.class_configuration_query_service import (
                    get_effective_economic_engine,
                )
                class_id = getattr(payroll_settings, 'class_id', None)
                if class_id:
                    engine = get_effective_economic_engine(class_id, 'payroll')
                    if engine and engine.expected_weekly_hours is not None:
                        expected_weekly_hours = _quantize_currency(engine.expected_weekly_hours)
                        notes.append(f"Using expected weekly hours from EconomicEngine: {expected_weekly_hours} hours")
            except Exception:
                logger.exception(
                    "Failed to resolve expected_weekly_hours from EconomicEngine for class_id=%s",
                    getattr(payroll_settings, 'class_id', None),
                )

            if expected_weekly_hours is None:
                # No configured value → CWI is undefined.
                return None
        else:
            expected_weekly_hours = _quantize_currency(expected_weekly_hours)
            notes.append(f"Using provided expected weekly hours: {expected_weekly_hours} hours")

        # Convert pay_rate to per-minute rate
        # Note: pay_rate is stored as per-minute in the database for storage efficiency
        pay_rate_per_minute = Decimal(str(payroll_settings.pay_rate))
        notes.append(f"Pay rate: ${pay_rate_per_minute:.4f} per minute (from database)")

        # Calculate expected weekly minutes
        expected_weekly_minutes = expected_weekly_hours * Decimal('60')
        notes.append(f"Expected weekly attendance: {expected_weekly_hours} hours = {expected_weekly_minutes} minutes")

        # Calculate weekly income
        cwi = _quantize_currency(expected_weekly_minutes * pay_rate_per_minute)
        notes.append(f"CWI = {expected_weekly_minutes} min × ${pay_rate_per_minute:.4f}/min = ${cwi:.2f}")

        return CWICalculation(
            cwi=float(cwi),  # Convert to float for JSON serialization
            pay_rate=float(payroll_settings.pay_rate),  # Convert to float for JSON serialization
            time_unit=payroll_settings.time_unit or "minutes",
            pay_rate_per_minute=float(pay_rate_per_minute),
            expected_weekly_minutes=float(expected_weekly_minutes),
            payroll_frequency_days=payroll_settings.payroll_frequency_days or 7,
            notes=notes
        )

    def check_rent_balance(self, rent_settings, cwi: float) -> List[BalanceWarning]:
        """
        Check if rent amount is balanced relative to CWI.

        Args:
            rent_settings: RentSettings model instance
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not rent_settings:
            return warnings

        from app.models import _quantize_currency
        rent_amount = _quantize_currency(rent_settings.rent_amount)
        weekly_rent = self._normalize_to_weekly(
            rent_amount,
            rent_settings.frequency_type,
            rent_settings.custom_frequency_value,
            getattr(rent_settings, 'custom_frequency_unit', None)
        )
        monthly_rent = _quantize_currency(weekly_rent * Decimal(str(self.AVERAGE_WEEKS_PER_MONTH)))
        rent_min_ratio_weekly, rent_max_ratio_weekly, _ = self._ratio_band(
            "rent_weekly",
            self.RENT_MIN_RATIO,
            self.RENT_MAX_RATIO,
            self.RENT_DEFAULT_RATIO,
        )
        rent_min_ratio = rent_min_ratio_weekly * self.AVERAGE_WEEKS_PER_MONTH
        rent_max_ratio = rent_max_ratio_weekly * self.AVERAGE_WEEKS_PER_MONTH
        monthly_ratio = float(monthly_rent / Decimal(cwi)) if cwi > 0 else 0

        recommended_min = cwi * rent_min_ratio
        recommended_max = cwi * rent_max_ratio

        if monthly_ratio < rent_min_ratio:
            deviation = (rent_min_ratio - monthly_ratio) / rent_min_ratio
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Monthly-equivalent rent (${monthly_rent:.2f}) is below recommended minimum. Students may not learn proper budgeting.",
                current_value=monthly_rent,
                recommended_min=recommended_min,
                recommended_max=recommended_max,
                cwi_ratio=monthly_ratio
            ))
        elif monthly_ratio > rent_max_ratio:
            deviation = (monthly_ratio - rent_max_ratio) / rent_max_ratio
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Monthly-equivalent rent (${monthly_rent:.2f}) is above recommended maximum. Students may struggle with other expenses.",
                current_value=monthly_rent,
                recommended_min=recommended_min,
                recommended_max=recommended_max,
                cwi_ratio=monthly_ratio
            ))
        else:
            # Within bounds - provide info
            warnings.append(BalanceWarning(
                feature="Rent",
                level=WarningLevel.INFO,
                message=f"Rent is balanced at ${monthly_rent:.2f}/month ({monthly_ratio:.2f}x CWI)",
                current_value=monthly_rent,
                recommended_min=recommended_min,
                recommended_max=recommended_max,
                cwi_ratio=monthly_ratio
            ))

        return warnings

    def check_fines_balance(self, fines: List, cwi: float) -> List[BalanceWarning]:
        """
        Check if fines are balanced relative to CWI.

        Args:
            fines: List of PayrollFine model instances
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not fines:
            return warnings

        fine_min_ratio, fine_max_ratio, _ = self._ratio_band(
            "fine_weekly",
            self.FINE_MIN_RATIO,
            self.FINE_MAX_RATIO,
            self.FINE_DEFAULT_RATIO,
        )
        recommended_min = cwi * fine_min_ratio
        recommended_max = cwi * fine_max_ratio

        for fine in fines:
            if not fine.is_active:
                continue

            from app.models import _quantize_currency
            fine_amount = _quantize_currency(fine.amount)
            fine_ratio = float(fine_amount / Decimal(cwi)) if cwi > 0 else 0

            # Check if within bounds
            if fine_ratio < fine_min_ratio:
                deviation = (fine_min_ratio - fine_ratio) / fine_min_ratio
                if deviation > self.MINOR_DEVIATION_THRESHOLD:
                    level = WarningLevel.WARNING
                    warnings.append(BalanceWarning(
                        feature=f"Fine: {fine.name}",
                        level=level,
                        message=f"Fine amount (${abs(fine_amount):.2f}) is too small to be meaningful. Recommended range: ${recommended_min:.2f} - ${recommended_max:.2f}",
                        current_value=float(fine_amount),  # Convert to float for JSON serialization
                        recommended_min=recommended_min,
                        recommended_max=recommended_max,
                        cwi_ratio=fine_ratio
                    ))
            elif fine_ratio > fine_max_ratio:
                deviation = (fine_ratio - fine_max_ratio) / fine_max_ratio
                level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
                warnings.append(BalanceWarning(
                    feature=f"Fine: {fine.name}",
                    level=level,
                    message=f"Fine amount (${abs(fine_amount):.2f}) is too harsh and may cause student insolvency. Recommended range: ${recommended_min:.2f} - ${recommended_max:.2f}",
                    current_value=fine_amount,
                    recommended_min=recommended_min,
                    recommended_max=recommended_max,
                    cwi_ratio=fine_ratio
                ))
            else:
                # Within bounds
                warnings.append(BalanceWarning(
                    feature=f"Fine: {fine.name}",
                    level=WarningLevel.INFO,
                    message=f"Fine is balanced at ${fine_amount:.2f} ({fine_ratio:.2f}x CWI)",
                    current_value=fine_amount,
                    recommended_min=recommended_min,
                    recommended_max=recommended_max,
                    cwi_ratio=fine_ratio
                ))

        return warnings

    def check_store_items_balance(self, store_items: List, cwi: float) -> List[BalanceWarning]:
        """
        Check if store items are balanced relative to CWI.

        Args:
            store_items: List of StoreItem model instances
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not store_items:
            return warnings

        for item in store_items:
            if not item.is_active:
                continue

            # Skip long-term goal items from CWI balance checks
            if getattr(item, 'is_long_term_goal', False):
                continue

            price = float(item.price)
            price_ratio = price / cwi if cwi > 0 else 0

            # Determine appropriate tier
            appropriate_tier = None
            tier_message = ""

            store_tiers = self._store_tiers()
            for tier, (min_ratio, max_ratio) in store_tiers.items():
                if min_ratio <= price_ratio <= max_ratio:
                    appropriate_tier = tier
                    tier_message = f"Price fits {tier.value.upper()} tier"
                    break

            if appropriate_tier:
                warnings.append(BalanceWarning(
                    feature=f"Store Item: {item.name}",
                    level=WarningLevel.INFO,
                    message=f"{tier_message}: ${price:.2f} ({price_ratio:.2f}x CWI)",
                    current_value=price,
                    recommended_min=None,
                    recommended_max=None,
                    cwi_ratio=price_ratio
                ))
            else:
                # Price is outside all tiers
                if price_ratio > store_tiers[PricingTier.LUXURY][1]:
                    max_recommended = cwi * store_tiers[PricingTier.LUXURY][1]
                    warnings.append(BalanceWarning(
                        feature=f"Store Item: {item.name}",
                        level=WarningLevel.CRITICAL,
                        message=f"Price (${price:.2f}) exceeds LUXURY tier max (${max_recommended:.2f}). Students may never afford this. Consider marking as 'Long Term Goal Item' if this is intentional.",
                        current_value=price,
                        recommended_min=cwi * store_tiers[PricingTier.BASIC][0],
                        recommended_max=cwi * store_tiers[PricingTier.LUXURY][1],
                        cwi_ratio=price_ratio
                    ))
                elif price_ratio < store_tiers[PricingTier.BASIC][0]:
                    min_recommended = cwi * store_tiers[PricingTier.BASIC][0]
                    warnings.append(BalanceWarning(
                        feature=f"Store Item: {item.name}",
                        level=WarningLevel.WARNING,
                        message=f"Price (${price:.2f}) is below BASIC tier min (${min_recommended:.2f}). May not be a meaningful reward.",
                        current_value=price,
                        recommended_min=cwi * store_tiers[PricingTier.BASIC][0],
                        recommended_max=cwi * store_tiers[PricingTier.LUXURY][1],
                        cwi_ratio=price_ratio
                    ))

        return warnings

    def validate_rent_value(
        self,
        rent_amount: float,
        frequency_type: str,
        cwi: float,
        custom_frequency_value: Optional[float] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
        """
        Validate rent amount against CWI-based recommendations.

        The input amount is normalized to weekly for ratio checking.

        Recommendation source depends on scope:
        - block-scoped validation uses SPEC-ECON-003 monthly multipliers
          (2.0x-2.5x weekly CWI, with 2.25x default)
        - global validation uses policy-mode weekly burden bands converted to
          monthly-equivalent values

        Monthly recommendations are converted to the teacher's chosen
        frequency for display.
        """
        # Convert input rent to weekly for comparison
        from app.models import _quantize_currency
        weekly_rent = self._normalize_to_weekly(
            _quantize_currency(rent_amount),
            frequency_type,
            _quantize_currency(custom_frequency_value) if custom_frequency_value is not None else None,
            custom_frequency_unit,
        )

        # Rent validation uses policy-mode weekly burden bands, converted to monthly.
        rent_min_ratio_weekly, rent_max_ratio_weekly, rent_recommended_ratio_weekly = self._ratio_band(
            "rent_weekly",
            self.RENT_MIN_RATIO,
            self.RENT_MAX_RATIO,
            self.RENT_DEFAULT_RATIO,
        )
        weeks_per_month = Decimal(str(self.AVERAGE_WEEKS_PER_MONTH))
        rent_min_ratio_monthly = Decimal(str(rent_min_ratio_weekly)) * weeks_per_month
        rent_max_ratio_monthly = Decimal(str(rent_max_ratio_weekly)) * weeks_per_month
        rent_recommended_ratio_monthly = Decimal(str(rent_recommended_ratio_weekly)) * weeks_per_month

        monthly_min = cwi * float(rent_min_ratio_monthly)
        monthly_max = cwi * float(rent_max_ratio_monthly)
        monthly_recommended = cwi * float(rent_recommended_ratio_monthly)

        # Convert to weekly for ratio calculation

        # Calculate ratio based on weekly equivalents
        cwi_decimal = Decimal(str(cwi)) if isinstance(cwi, (float, int)) else cwi
        
        ratio = weekly_rent / cwi_decimal if cwi_decimal > 0 else Decimal('0')
        
        monthly_ratio = ratio * Decimal(str(self.AVERAGE_WEEKS_PER_MONTH))

        # Convert recommendations to match the input frequency for clarity
        def convert_from_monthly(monthly_value: float) -> float:
            """Convert a monthly value to the teacher's chosen frequency."""
            if frequency_type == 'monthly':
                return monthly_value
            elif frequency_type == 'weekly':
                return monthly_value / self.AVERAGE_WEEKS_PER_MONTH
            elif frequency_type == 'biweekly':
                return monthly_value / (self.AVERAGE_WEEKS_PER_MONTH / 2)
            elif frequency_type == 'daily':
                return monthly_value / (self.AVERAGE_WEEKS_PER_MONTH * 7)
            elif frequency_type == 'custom':
                unit = (custom_frequency_unit or 'days').lower()
                freq_value = custom_frequency_value or 1
                if unit == 'weeks':
                    return monthly_value / self.AVERAGE_WEEKS_PER_MONTH * freq_value
                elif unit == 'months':
                    return monthly_value * freq_value
                else:  # days
                    return monthly_value / (self.AVERAGE_WEEKS_PER_MONTH * 7) * freq_value
            raise ValueError(f"Unsupported frequency_type: {frequency_type}")

        recommendations = {
            'min': round(convert_from_monthly(monthly_min), 2),
            'max': round(convert_from_monthly(monthly_max), 2),
            'recommended': round(convert_from_monthly(monthly_recommended), 2),
        }

        # Generate frequency label for messages
        if frequency_type == 'custom':
            freq_value = custom_frequency_value or 1
            freq_unit = (custom_frequency_unit or 'days').lower()
            # Pluralize unit if needed
            if freq_value == 1:
                label_unit = freq_unit.rstrip('s')
            else:
                label_unit = freq_unit if freq_unit.endswith('s') else freq_unit + 's'
            frequency_label = f"per {freq_value} {label_unit}"
        else:
            frequency_label = {
                'monthly': 'per month',
                'weekly': 'per week',
                'biweekly': 'per 2 weeks',
                'daily': 'per day',
            }.get(frequency_type, frequency_type)

        warnings: List[Dict[str, str]] = []
        if monthly_ratio < rent_min_ratio_monthly:
            warnings.append({
                'level': 'warning',
                'title': 'Rent may be set too low',
                'message': (
                    f"The rent amount you entered (${rent_amount:.2f} {frequency_label}) is "
                    f"below the recommended minimum of ${recommendations['min']:.2f} {frequency_label}. "
                    f"This may reduce students' incentive to budget and save."
                ),
            })
        elif monthly_ratio > rent_max_ratio_monthly:
            warnings.append({
                'level': 'warning',
                'title': 'Rent may be set too high',
                'message': (
                    f"The rent amount you entered (${rent_amount:.2f} {frequency_label}) is "
                    f"above the recommended maximum of ${recommendations['max']:.2f} {frequency_label}. "
                    f"Students may have difficulty meeting their other obligations."
                ),
            })
        else:
            warnings.append({
                'level': 'success',
                'title': 'Rent is balanced',
                'message': (
                    f"Rent is set to ${rent_amount:.2f} {frequency_label} "
                    f"(${weekly_rent:.2f} per week), within the recommended range."
                ),
            })

        return warnings, recommendations, float(ratio)

    def validate_fine_value(self, fine_amount: float, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
        fine_amount = float(fine_amount)
        cwi = float(cwi)
        ratio = fine_amount / cwi if cwi > 0 else 0

        recommendations = {
            'min': round(cwi * self.FINE_MIN_RATIO, 2),
            'max': round(cwi * self.FINE_MAX_RATIO, 2),
            'recommended': round(cwi * self.FINE_DEFAULT_RATIO, 2),
        }

        warnings: List[Dict[str, str]] = []
        if ratio < self.FINE_MIN_RATIO:
            warnings.append({
                'level': 'warning',
                'message': f'Fine (${fine_amount:.2f}) may be too small to be meaningful.',
            })
        elif ratio > self.FINE_MAX_RATIO:
            warnings.append({
                'level': 'critical',
                'message': f'Fine (${fine_amount:.2f}) is too harsh. May cause student insolvency.',
            })
        else:
            warnings.append({
                'level': 'success',
                'message': f'Fine is balanced at ${fine_amount:.2f}',
            })

        return warnings, recommendations, float(ratio)

    def validate_store_item_value(self, price: float, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, float]], float]:
        price = float(price)
        cwi = float(cwi)
        ratio = price / cwi if cwi > 0 else 0
        recommendations: Dict[str, Dict[str, float]] = {}
        warnings: List[Dict[str, str]] = []

        store_tiers = self._store_tiers()
        tier_found = None
        for tier, (min_r, max_r) in store_tiers.items():
            if min_r <= ratio <= max_r:
                tier_found = tier
                recommendations[tier.value] = {
                    'min': round(cwi * min_r, 2),
                    'max': round(cwi * max_r, 2),
                }
                break

        recommendations['tiers'] = {
            tier.value: {
                'min': round(cwi * bounds[0], 2),
                'max': round(cwi * bounds[1], 2),
            }
            for tier, bounds in store_tiers.items()
        }

        if tier_found:
            warnings.append({
                'level': 'success',
                'message': f'Price fits {tier_found.value.upper()} tier (${price:.2f})',
            })
        elif ratio > store_tiers[PricingTier.LUXURY][1]:
            warnings.append({
                'level': 'critical',
                'message': f'Price (${price:.2f}) exceeds LUXURY tier max. Students may never afford this.',
            })
        elif ratio < store_tiers[PricingTier.BASIC][0]:
            warnings.append({
                'level': 'warning',
                'message': f'Price (${price:.2f}) is below BASIC tier. May not be meaningful reward.',
            })

        return warnings, recommendations, float(ratio)

    def validate_feature_value(self, feature: str, value: float, cwi: float, **kwargs):
        if feature == 'rent':
            return self.validate_rent_value(
                value,
                kwargs.get('frequency_type', 'monthly'),
                cwi,
                kwargs.get('custom_frequency_value'),
                kwargs.get('custom_frequency_unit'),
            )
        # NOTE (SPEC-ECON-003 migration): insurance validation is owned by the
        # Economic Engine (resolve_insurance) via the product-aware edit flow.
        # The legacy free-form CWI-band validator has been retired; 'insurance'
        # is no longer a supported feature for this generic validator.
        if feature == 'fine':
            return self.validate_fine_value(value, cwi)
        if feature == 'store_item':
            return self.validate_store_item_value(value, cwi)

        raise ValueError('Unsupported feature type')

    def calculate_budget_survival(
        self,
        cwi: float,
        rent_settings,
        insurance_policies: List,
        average_store_spending: Optional[float] = None
    ) -> Tuple[bool, float]:
        """
        Perform Budget Survival Test per SPEC-ECON-003 §4.2 (weekly savings target) and §7 (Economic Coherence Rules).

        A student with perfect attendance must be able to save at least 10% of CWI weekly.

        Args:
            cwi: Calculated CWI
            rent_settings: RentSettings model instance
            insurance_policies: List of active insurance policies (we'll use average or cheapest)
            average_store_spending: Average weekly store spending (optional, estimated if None)

        Returns:
            Tuple of (passed: bool, weekly_savings: float)
        """
        weekly_income = cwi

        # Calculate weekly rent
        weekly_rent = 0
        if rent_settings:
            rent_amount = float(rent_settings.rent_amount)
            weekly_rent = float(self._normalize_to_weekly(
                rent_amount,
                rent_settings.frequency_type,
                rent_settings.custom_frequency_value,
                getattr(rent_settings, 'custom_frequency_unit', None)
            ))

        # Calculate weekly insurance (use cheapest active policy as baseline)
        weekly_insurance = 0
        if insurance_policies:
            active_policies = [p for p in insurance_policies if p.is_active]
            if active_policies:
                # Find cheapest weekly equivalent
                cheapest_weekly = float('inf')
                for policy in active_policies:
                    premium = float(policy.premium)
                    weekly_equiv = float(self._normalize_to_weekly(premium, policy.charge_frequency))

                    if weekly_equiv < cheapest_weekly:
                        cheapest_weekly = weekly_equiv

                weekly_insurance = cheapest_weekly if cheapest_weekly != float('inf') else 0

        # Estimate weekly store spending if not provided
        if average_store_spending is None:
            # Conservative estimate: 15% of CWI on store items
            average_store_spending = cwi * self.ESTIMATED_WEEKLY_STORE_SPENDING_RATIO

        # Calculate weekly savings
        weekly_savings = weekly_income - weekly_rent - weekly_insurance - average_store_spending

        required_savings = cwi * self._minimum_ratio("savings_weekly", self.MIN_WEEKLY_SAVINGS_RATIO)
        passed = weekly_savings >= required_savings

        return passed, weekly_savings

    def analyze_economy(
        self,
        payroll_settings,
        rent_settings=None,
        insurance_policies: List = None,
        fines: List = None,
        store_items: List = None,
        expected_weekly_hours: float = None,
        average_store_spending: Optional[float] = None
    ) -> EconomyBalance:
        """
        Perform comprehensive economy balance analysis.

        Args:
            payroll_settings: PayrollSettings instance
            rent_settings: RentSettings instance (optional)
            insurance_policies: Policy rows (optional)
            fines: List of PayrollFine instances (optional)
            store_items: List of StoreItem instances (optional)
            expected_weekly_hours: Expected weekly attendance hours
            average_store_spending: Average weekly store spending (estimated if None)

        Returns:
            EconomyBalance with complete analysis
        """
        # Calculate CWI
        cwi_calc = self.calculate_cwi(payroll_settings, expected_weekly_hours)
        if cwi_calc is None:
            # CWI is undefined without expected_weekly_hours; skip pricing analysis.
            # Consumers should show a "configure CWI" warning and hide recommendations.
            return EconomyBalance(
                cwi=None,
                is_balanced=False,
                warnings=[BalanceWarning(
                    feature="CWI",
                    level=WarningLevel.WARNING,
                    message="Expected weekly hours not configured. Set it on the Economic Engine page to enable pricing recommendations.",
                    current_value=None,
                    recommended_min=None,
                    recommended_max=None,
                    cwi_ratio=None,
                )],
                recommendations={},
                budget_survival_test_passed=False,
                weekly_savings=0.0,
            )
        cwi = cwi_calc.cwi

        # Collect all warnings
        all_warnings = []

        # Check rent
        if rent_settings:
            all_warnings.extend(self.check_rent_balance(rent_settings, cwi))

        # NOTE (SPEC-ECON-003 migration): insurance balance analysis is now owned
        # by the Economic Engine (resolve_insurance). The legacy CWI-band checker
        # has been retired; insurance policies are not evaluated here.

        # Check fines
        if fines:
            all_warnings.extend(self.check_fines_balance(fines or [], cwi))

        # Check store items
        if store_items:
            all_warnings.extend(self.check_store_items_balance(store_items or [], cwi))

        # Run budget survival test
        survival_passed, weekly_savings = self.calculate_budget_survival(
            cwi, rent_settings, insurance_policies or [], average_store_spending
        )

        if not survival_passed:
            all_warnings.append(BalanceWarning(
                feature="Budget Survival Test",
                level=WarningLevel.CRITICAL,
                message=f"Students cannot save enough income! Weekly savings: ${weekly_savings:.2f} (need ${cwi * self._minimum_ratio('savings_weekly', self.MIN_WEEKLY_SAVINGS_RATIO):.2f})",
                current_value=weekly_savings,
                recommended_min=cwi * self._minimum_ratio("savings_weekly", self.MIN_WEEKLY_SAVINGS_RATIO),
                recommended_max=None,
                cwi_ratio=weekly_savings / cwi if cwi > 0 else 0
            ))

        recommendations = self.generate_recommendations(cwi, all_warnings)

        # Determine if economy is balanced
        # Balanced if: no critical warnings and survival test passed
        critical_warnings = [w for w in all_warnings if w.level == WarningLevel.CRITICAL]
        is_balanced = len(critical_warnings) == 0 and survival_passed

        return EconomyBalance(
            cwi=cwi_calc,
            is_balanced=is_balanced,
            warnings=all_warnings,
            recommendations=recommendations,
            budget_survival_test_passed=survival_passed,
            weekly_savings=weekly_savings
        )

    def generate_recommendations(self, cwi: float, warnings: Optional[List[BalanceWarning]] = None) -> Dict[str, Any]:
        """
        Generate recommended configurations based on CWI and warnings.

        Args:
            cwi: Calculated CWI
            warnings: Optional list of balance warnings

        Returns:
            Dictionary of recommendations per feature
        """
        recommendations = get_price_recommendation_context(self.policy_mode, cwi)
        return recommendations or {}

    def _generate_recommendations(self, cwi: float, warnings: List[BalanceWarning]) -> Dict[str, Any]:
        return self.generate_recommendations(cwi, warnings)


def format_warnings_for_display(warnings: List[BalanceWarning]) -> str:
    """
    Format warnings as HTML for teacher display.

    Args:
        warnings: List of BalanceWarning objects

    Returns:
        HTML string
    """
    if not warnings:
        return '<div class="alert alert-success"><i class="bi bi-check-circle-fill me-1"></i>Economy is balanced!</div>'

    # Group by level
    critical = [w for w in warnings if w.level == WarningLevel.CRITICAL]
    warning = [w for w in warnings if w.level == WarningLevel.WARNING]
    info = [w for w in warnings if w.level == WarningLevel.INFO]

    html_parts = []

    if critical:
        html_parts.append('<div class="alert alert-danger"><strong><i class="bi bi-exclamation-octagon-fill me-1"></i>Critical Issues:</strong><ul>')
        for w in critical:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    if warning:
        html_parts.append('<div class="alert alert-warning"><strong><i class="bi bi-exclamation-triangle-fill me-1"></i>Warnings:</strong><ul>')
        for w in warning:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    if info and not (critical or warning):  # Only show info if no problems
        html_parts.append('<div class="alert alert-info"><strong><i class="bi bi-info-circle-fill me-1"></i>Balance Info:</strong><ul>')
        for w in info[:5]:  # Limit to 5 info messages
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    return '\n'.join(html_parts)
