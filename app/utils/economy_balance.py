"""
Economy Balance Checker - Centralized CWI Calculator and Balance Validator

This module implements the AGENTS financial setup specification for the Classroom Economy App.
It provides tools to:
- Calculate CWI (Classroom Wage Index) dynamically
- Validate economy settings against standard ratios
- Generate teacher recommendations for balanced configurations
- Warn when settings deviate from CWI guidelines

Reference: AGENTS financial setup.md
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class WarningLevel(Enum):
    """Severity levels for economy balance warnings"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PricingTier(Enum):
    """Store item pricing tiers per AGENTS spec"""
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

    All monetary values in the Classroom Economy must scale from CWI per AGENTS spec.
    This class provides the single source of truth for:
    - CWI calculation
    - Ratio-based validation
    - Teacher recommendations
    - Balance warnings
    """

    # Standard ratios from AGENTS specification
    RENT_MIN_RATIO = 2.0
    RENT_MAX_RATIO = 2.5
    RENT_DEFAULT_RATIO = 2.25

    UTILITIES_MIN_RATIO = 0.20
    UTILITIES_MAX_RATIO = 0.30
    UTILITIES_DEFAULT_RATIO = 0.25

    INSURANCE_MIN_RATIO = 0.05
    INSURANCE_MAX_RATIO = 0.12
    INSURANCE_DEFAULT_RATIO = 0.08

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

    def __init__(self, teacher_id: int, block: Optional[str] = None):
        """
        Initialize checker for a specific teacher and optional block.

        Args:
            teacher_id: The teacher's ID
            block: Optional block/period identifier for scoped settings
        """
        self.teacher_id = teacher_id
        self.block = block

    def _normalize_to_weekly(
        self,
        value: float,
        frequency: str,
        custom_frequency_value: Optional[float] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> float:
        """Normalize a value to its weekly equivalent based on frequency."""

        if frequency == 'monthly':
            return value / self.AVERAGE_WEEKS_PER_MONTH
        if frequency == 'weekly':
            return value
        if frequency == 'biweekly':
            return value / 2
        if frequency == 'daily':
            return value * 7
        if frequency == 'custom':
            # Default to days when unit is unspecified
            unit = (custom_frequency_unit or 'days').lower()
            freq_value = custom_frequency_value or 1
            if unit == 'weeks':
                return value * (7 / freq_value)
            if unit == 'months':
                return value / (self.AVERAGE_WEEKS_PER_MONTH * freq_value)
            return value * (7 / freq_value)

        return value

    def calculate_cwi(self, payroll_settings, expected_weekly_hours: float = None) -> CWICalculation:
        """
        Calculate CWI (Classroom Wage Index) - expected weekly income for perfect attendance.

        Args:
            payroll_settings: PayrollSettings model instance
            expected_weekly_hours: Expected hours of attendance per week
                                  If None, uses value from payroll_settings (default 5.0)

        Returns:
            CWICalculation with breakdown
        """
        notes = []

        # Get expected weekly hours from settings if not provided
        if expected_weekly_hours is None:
            expected_weekly_hours = float(payroll_settings.expected_weekly_hours or 5.0)
            notes.append(f"Using expected weekly hours from payroll settings: {expected_weekly_hours} hours")
        else:
            notes.append(f"Using provided expected weekly hours: {expected_weekly_hours} hours")

        # Convert pay_rate to per-minute rate
        # Note: pay_rate is stored as per-minute in the database for storage efficiency
        pay_rate_per_minute = float(payroll_settings.pay_rate)
        notes.append(f"Pay rate: ${pay_rate_per_minute:.4f} per minute (from database)")

        # Calculate expected weekly minutes
        expected_weekly_minutes = expected_weekly_hours * 60
        notes.append(f"Expected weekly attendance: {expected_weekly_hours} hours = {expected_weekly_minutes} minutes")

        # Calculate weekly income
        cwi = expected_weekly_minutes * pay_rate_per_minute
        notes.append(f"CWI = {expected_weekly_minutes} min × ${pay_rate_per_minute:.4f}/min = ${cwi:.2f}")

        return CWICalculation(
            cwi=cwi,
            pay_rate=float(payroll_settings.pay_rate),
            time_unit=payroll_settings.time_unit or "minutes",
            pay_rate_per_minute=pay_rate_per_minute,
            expected_weekly_minutes=expected_weekly_minutes,
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

        if not rent_settings or not rent_settings.is_enabled:
            return warnings

        rent_amount = float(rent_settings.rent_amount)
        weekly_rent = self._normalize_to_weekly(
            rent_amount,
            rent_settings.frequency_type,
            rent_settings.custom_frequency_value,
            getattr(rent_settings, 'custom_frequency_unit', None)
        )
        # Convert to monthly for ratio comparison per AGENTS spec
        monthly_rent = weekly_rent * self.AVERAGE_WEEKS_PER_MONTH
        rent_ratio = monthly_rent / cwi if cwi > 0 else 0

        # Calculate recommended MONTHLY bounds
        recommended_monthly_min = cwi * self.RENT_MIN_RATIO
        recommended_monthly_max = cwi * self.RENT_MAX_RATIO

        # Check if within bounds
        # Use Monthly values for Rent reporting as it is the standard for this feature
        if rent_ratio < self.RENT_MIN_RATIO:
            deviation = (self.RENT_MIN_RATIO - rent_ratio) / self.RENT_MIN_RATIO
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Monthly rent equivalent (${monthly_rent:.2f}) is below recommended minimum (${recommended_monthly_min:.2f}). Students may not learn proper budgeting.",
                current_value=monthly_rent,
                recommended_min=recommended_monthly_min,
                recommended_max=recommended_monthly_max,
                cwi_ratio=rent_ratio
            ))
        elif rent_ratio > self.RENT_MAX_RATIO:
            deviation = (rent_ratio - self.RENT_MAX_RATIO) / self.RENT_MAX_RATIO
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Monthly rent equivalent (${monthly_rent:.2f}) is above recommended maximum (${recommended_monthly_max:.2f}). Students may struggle with other expenses.",
                current_value=monthly_rent,
                recommended_min=recommended_monthly_min,
                recommended_max=recommended_monthly_max,
                cwi_ratio=rent_ratio
            ))
        else:
            # Within bounds - provide info
            warnings.append(BalanceWarning(
                feature="Rent",
                level=WarningLevel.INFO,
                message=f"Monthly rent equivalent (${monthly_rent:.2f}) is balanced ({rent_ratio:.2f}x CWI)",
                current_value=monthly_rent,
                recommended_min=recommended_monthly_min,
                recommended_max=recommended_monthly_max,
                cwi_ratio=rent_ratio
            ))

        return warnings

    def check_insurance_balance(self, insurance_policies: List, cwi: float) -> List[BalanceWarning]:
        """
        Check if insurance premiums are balanced relative to CWI.

        Args:
            insurance_policies: List of InsurancePolicy model instances
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not insurance_policies:
            return warnings

        recommended_min = cwi * self.INSURANCE_MIN_RATIO
        recommended_max = cwi * self.INSURANCE_MAX_RATIO

        for policy in insurance_policies:
            if not policy.is_active:
                continue

            # Convert premium to weekly equivalent for comparison
            premium = float(policy.premium)

            # Normalize to weekly based on charge_frequency
            weekly_premium = self._normalize_to_weekly(premium, policy.charge_frequency)

            premium_ratio = weekly_premium / cwi if cwi > 0 else 0

            # Check if within bounds
            if premium_ratio < self.INSURANCE_MIN_RATIO:
                deviation = (self.INSURANCE_MIN_RATIO - premium_ratio) / self.INSURANCE_MIN_RATIO
                if deviation > self.MINOR_DEVIATION_THRESHOLD:
                    level = WarningLevel.WARNING
                    warnings.append(BalanceWarning(
                        feature=f"Insurance: {policy.title}",
                        level=level,
                        message=f"Premium (${premium:.2f}/{policy.charge_frequency}) may be too low relative to coverage.",
                        current_value=premium,
                        recommended_min=recommended_min if policy.charge_frequency == 'weekly' else None,
                        recommended_max=recommended_max if policy.charge_frequency == 'weekly' else None,
                        cwi_ratio=premium_ratio
                    ))
            elif premium_ratio > self.INSURANCE_MAX_RATIO:
                deviation = (premium_ratio - self.INSURANCE_MAX_RATIO) / self.INSURANCE_MAX_RATIO
                level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
                warnings.append(BalanceWarning(
                    feature=f"Insurance: {policy.title}",
                    level=level,
                    message=f"Premium (${premium:.2f}/{policy.charge_frequency}) is too expensive. Students may not enroll.",
                    current_value=premium,
                    recommended_min=recommended_min if policy.charge_frequency == 'weekly' else None,
                    recommended_max=recommended_max if policy.charge_frequency == 'weekly' else None,
                    cwi_ratio=premium_ratio
                ))
            else:
                # Within bounds
                warnings.append(BalanceWarning(
                    feature=f"Insurance: {policy.title}",
                    level=WarningLevel.INFO,
                    message=f"Premium is balanced at ${premium:.2f}/{policy.charge_frequency} ({premium_ratio:.2f}x CWI)",
                    current_value=premium,
                    recommended_min=recommended_min if policy.charge_frequency == 'weekly' else None,
                    recommended_max=recommended_max if policy.charge_frequency == 'weekly' else None,
                    cwi_ratio=premium_ratio
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

        recommended_min = cwi * self.FINE_MIN_RATIO
        recommended_max = cwi * self.FINE_MAX_RATIO

        for fine in fines:
            if not fine.is_active:
                continue

            fine_amount = float(fine.amount)
            fine_ratio = fine_amount / cwi if cwi > 0 else 0

            # Check if within bounds
            if fine_ratio < self.FINE_MIN_RATIO:
                deviation = (self.FINE_MIN_RATIO - fine_ratio) / self.FINE_MIN_RATIO
                if deviation > self.MINOR_DEVIATION_THRESHOLD:
                    level = WarningLevel.WARNING
                    warnings.append(BalanceWarning(
                        feature=f"Fine: {fine.name}",
                        level=level,
                        message=f"Fine amount (${fine_amount:.2f}) may be too small to be meaningful.",
                        current_value=fine_amount,
                        recommended_min=recommended_min,
                        recommended_max=recommended_max,
                        cwi_ratio=fine_ratio
                    ))
            elif fine_ratio > self.FINE_MAX_RATIO:
                deviation = (fine_ratio - self.FINE_MAX_RATIO) / self.FINE_MAX_RATIO
                level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
                warnings.append(BalanceWarning(
                    feature=f"Fine: {fine.name}",
                    level=level,
                    message=f"Fine amount (${fine_amount:.2f}) is too harsh. May cause student insolvency.",
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

            price = float(item.price)
            price_ratio = price / cwi if cwi > 0 else 0

            # Determine appropriate tier
            appropriate_tier = None
            tier_message = ""

            for tier, (min_ratio, max_ratio) in self.STORE_TIERS.items():
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
                if price_ratio > self.STORE_TIERS[PricingTier.LUXURY][1]:
                    warnings.append(BalanceWarning(
                        feature=f"Store Item: {item.name}",
                        level=WarningLevel.CRITICAL,
                        message=f"Price (${price:.2f}) exceeds LUXURY tier max. Students may never afford this.",
                        current_value=price,
                        recommended_min=cwi * self.STORE_TIERS[PricingTier.BASIC][0],
                        recommended_max=cwi * self.STORE_TIERS[PricingTier.LUXURY][1],
                        cwi_ratio=price_ratio
                    ))
                elif price_ratio < self.STORE_TIERS[PricingTier.BASIC][0]:
                    warnings.append(BalanceWarning(
                        feature=f"Store Item: {item.name}",
                        level=WarningLevel.WARNING,
                        message=f"Price (${price:.2f}) is below BASIC tier. May not be meaningful reward.",
                        current_value=price,
                        recommended_min=cwi * self.STORE_TIERS[PricingTier.BASIC][0],
                        recommended_max=cwi * self.STORE_TIERS[PricingTier.LUXURY][1],
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

        Per AGENTS spec, rent ratios (2.0-2.5x CWI) are defined for MONTHLY rent.
        The spec formula: weekly_savings = CWI - (rent/weeks_per_month) - utilities - store
        indicates rent is monthly and CWI is weekly.

        Therefore:
        - Monthly rent_min = 2.0 * CWI (weekly)
        - Monthly rent_max = 2.5 * CWI (weekly)
        - Monthly rent_ideal = 2.25 * CWI (weekly)

        This is converted to other frequencies as needed.
        """
        # Convert input rent to weekly for comparison
        weekly_rent = self._normalize_to_weekly(
            rent_amount,
            frequency_type,
            custom_frequency_value,
            custom_frequency_unit,
        )

        # Calculate monthly recommendations per AGENTS spec
        # These ratios are explicitly for MONTHLY rent in the spec
        monthly_min = cwi * self.RENT_MIN_RATIO
        monthly_max = cwi * self.RENT_MAX_RATIO
        monthly_recommended = cwi * self.RENT_DEFAULT_RATIO

        # Convert to weekly for ratio calculation

        # Calculate ratio based on weekly equivalents
        ratio = weekly_rent / cwi if cwi > 0 else 0
        monthly_ratio = ratio * self.AVERAGE_WEEKS_PER_MONTH

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
        # Compare against monthly ratios since spec defines ratios for monthly rent
        if monthly_ratio < self.RENT_MIN_RATIO:
            warnings.append({
                'level': 'warning',
                'message': f"Rent amount is too low. To meet the recommended minimum, set rent to at least ${recommendations['min']:.2f} {frequency_label}.",
            })
        elif monthly_ratio > self.RENT_MAX_RATIO:
            warnings.append({
                'level': 'critical',
                'message': f"Rent amount is too high. Students may struggle with other expenses. Set rent to at most ${recommendations['max']:.2f} {frequency_label}.",
            })
        else:
            warnings.append({
                'level': 'success',
                'message': f'Rent is balanced at ${rent_amount:.2f} {frequency_label} (${weekly_rent:.2f}/week)',
            })

        return warnings, recommendations, ratio

    def validate_insurance_value(self, premium: float, frequency: str, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
        weekly_value = self._normalize_to_weekly(premium, frequency)
        ratio = weekly_value / cwi if cwi > 0 else 0

        recommendations = {
            'min_weekly': round(cwi * self.INSURANCE_MIN_RATIO, 2),
            'max_weekly': round(cwi * self.INSURANCE_MAX_RATIO, 2),
            'recommended_weekly': round(cwi * self.INSURANCE_DEFAULT_RATIO, 2),
        }

        warnings: List[Dict[str, str]] = []
        if ratio < self.INSURANCE_MIN_RATIO:
            warnings.append({
                'level': 'warning',
                'message': 'Premium may be too low relative to coverage.',
            })
        elif ratio > self.INSURANCE_MAX_RATIO:
            warnings.append({
                'level': 'critical',
                'message': f'Premium (${premium:.2f}/{frequency}) is too expensive. Students may not enroll.',
            })
        else:
            warnings.append({
                'level': 'success',
                'message': f'Premium is balanced at ${premium:.2f}/{frequency}',
            })

        return warnings, recommendations, ratio

    def validate_fine_value(self, fine_amount: float, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
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

        return warnings, recommendations, ratio

    def validate_store_item_value(self, price: float, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, float]], float]:
        ratio = price / cwi if cwi > 0 else 0
        recommendations: Dict[str, Dict[str, float]] = {}
        warnings: List[Dict[str, str]] = []

        tier_found = None
        for tier, (min_r, max_r) in self.STORE_TIERS.items():
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
            for tier, bounds in self.STORE_TIERS.items()
        }

        if tier_found:
            warnings.append({
                'level': 'success',
                'message': f'Price fits {tier_found.value.upper()} tier (${price:.2f})',
            })
        elif ratio > self.STORE_TIERS[PricingTier.LUXURY][1]:
            warnings.append({
                'level': 'critical',
                'message': f'Price (${price:.2f}) exceeds LUXURY tier max. Students may never afford this.',
            })
        elif ratio < self.STORE_TIERS[PricingTier.BASIC][0]:
            warnings.append({
                'level': 'warning',
                'message': f'Price (${price:.2f}) is below BASIC tier. May not be meaningful reward.',
            })

        return warnings, recommendations, ratio

    def validate_feature_value(self, feature: str, value: float, cwi: float, **kwargs):
        if feature == 'rent':
            return self.validate_rent_value(
                value,
                kwargs.get('frequency_type', 'monthly'),
                cwi,
                kwargs.get('custom_frequency_value'),
                kwargs.get('custom_frequency_unit'),
            )
        if feature == 'insurance':
            return self.validate_insurance_value(value, kwargs.get('frequency', 'weekly'), cwi)
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
        Perform Budget Survival Test per AGENTS spec.

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
        if rent_settings and rent_settings.is_enabled:
            rent_amount = float(rent_settings.rent_amount)
            weekly_rent = self._normalize_to_weekly(
                rent_amount,
                rent_settings.frequency_type,
                rent_settings.custom_frequency_value,
                getattr(rent_settings, 'custom_frequency_unit', None)
            )

        # Calculate weekly insurance (use cheapest active policy as baseline)
        weekly_insurance = 0
        if insurance_policies:
            active_policies = [p for p in insurance_policies if p.is_active]
            if active_policies:
                # Find cheapest weekly equivalent
                cheapest_weekly = float('inf')
                for policy in active_policies:
                    premium = float(policy.premium)
                    weekly_equiv = self._normalize_to_weekly(premium, policy.charge_frequency)

                    if weekly_equiv < cheapest_weekly:
                        cheapest_weekly = weekly_equiv

                weekly_insurance = cheapest_weekly if cheapest_weekly != float('inf') else 0

        # Estimate weekly store spending if not provided
        if average_store_spending is None:
            # Conservative estimate: 15% of CWI on store items
            average_store_spending = cwi * self.ESTIMATED_WEEKLY_STORE_SPENDING_RATIO

        # Calculate weekly savings
        weekly_savings = weekly_income - weekly_rent - weekly_insurance - average_store_spending

        # Must save at least 10% of CWI
        required_savings = cwi * self.MIN_WEEKLY_SAVINGS_RATIO
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
            insurance_policies: List of InsurancePolicy instances (optional)
            fines: List of PayrollFine instances (optional)
            store_items: List of StoreItem instances (optional)
            expected_weekly_hours: Expected weekly attendance hours
            average_store_spending: Average weekly store spending (estimated if None)

        Returns:
            EconomyBalance with complete analysis
        """
        # Calculate CWI
        cwi_calc = self.calculate_cwi(payroll_settings, expected_weekly_hours)
        cwi = cwi_calc.cwi

        # Collect all warnings
        all_warnings = []

        # Check rent
        if rent_settings:
            all_warnings.extend(self.check_rent_balance(rent_settings, cwi))

        # Check insurance
        if insurance_policies:
            all_warnings.extend(self.check_insurance_balance(insurance_policies or [], cwi))

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
                message=f"Students cannot save 10% of income! Weekly savings: ${weekly_savings:.2f} (need ${cwi * 0.10:.2f})",
                current_value=weekly_savings,
                recommended_min=cwi * 0.10,
                recommended_max=None,
                cwi_ratio=weekly_savings / cwi if cwi > 0 else 0
            ))

        # Generate recommendations
        recommendations = self._generate_recommendations(cwi, all_warnings)

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

    def _generate_recommendations(self, cwi: float, warnings: List[BalanceWarning]) -> Dict[str, Any]:
        """
        Generate recommended configurations based on CWI and warnings.

        Args:
            cwi: Calculated CWI
            warnings: List of balance warnings

        Returns:
            Dictionary of recommendations per feature
        """
        recommendations = {
            "rent": {
                "min": round(cwi * self.RENT_MIN_RATIO, 2),
                "max": round(cwi * self.RENT_MAX_RATIO, 2),
                "recommended": round(cwi * self.RENT_DEFAULT_RATIO, 2),
            },
            "utilities": {
                "min": round(cwi * self.UTILITIES_MIN_RATIO, 2),
                "max": round(cwi * self.UTILITIES_MAX_RATIO, 2),
                "recommended": round(cwi * self.UTILITIES_DEFAULT_RATIO, 2),
            },
            "insurance_premium_weekly": {
                "min": round(cwi * self.INSURANCE_MIN_RATIO, 2),
                "max": round(cwi * self.INSURANCE_MAX_RATIO, 2),
                "recommended": round(cwi * self.INSURANCE_DEFAULT_RATIO, 2),
            },
            "fine": {
                "min": round(cwi * self.FINE_MIN_RATIO, 2),
                "max": round(cwi * self.FINE_MAX_RATIO, 2),
                "recommended": round(cwi * self.FINE_DEFAULT_RATIO, 2),
            },
            "store_tiers": {
                "basic": {
                    "min": round(cwi * self.STORE_TIERS[PricingTier.BASIC][0], 2),
                    "max": round(cwi * self.STORE_TIERS[PricingTier.BASIC][1], 2),
                },
                "standard": {
                    "min": round(cwi * self.STORE_TIERS[PricingTier.STANDARD][0], 2),
                    "max": round(cwi * self.STORE_TIERS[PricingTier.STANDARD][1], 2),
                },
                "premium": {
                    "min": round(cwi * self.STORE_TIERS[PricingTier.PREMIUM][0], 2),
                    "max": round(cwi * self.STORE_TIERS[PricingTier.PREMIUM][1], 2),
                },
                "luxury": {
                    "min": round(cwi * self.STORE_TIERS[PricingTier.LUXURY][0], 2),
                    "max": round(cwi * self.STORE_TIERS[PricingTier.LUXURY][1], 2),
                },
            },
            "min_weekly_savings": round(cwi * self.MIN_WEEKLY_SAVINGS_RATIO, 2),
        }

        return recommendations


def format_warnings_for_display(warnings: List[BalanceWarning]) -> str:
    """
    Format warnings as HTML for teacher display.

    Args:
        warnings: List of BalanceWarning objects

    Returns:
        HTML string
    """
    if not warnings:
        return '<div class="alert alert-success">✓ Economy is balanced!</div>'

    # Group by level
    critical = [w for w in warnings if w.level == WarningLevel.CRITICAL]
    warning = [w for w in warnings if w.level == WarningLevel.WARNING]
    info = [w for w in warnings if w.level == WarningLevel.INFO]

    html_parts = []

    if critical:
        html_parts.append('<div class="alert alert-danger"><strong>⚠️ Critical Issues:</strong><ul>')
        for w in critical:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    if warning:
        html_parts.append('<div class="alert alert-warning"><strong>⚠ Warnings:</strong><ul>')
        for w in warning:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    if info and not (critical or warning):  # Only show info if no problems
        html_parts.append('<div class="alert alert-info"><strong>ℹ️ Balance Info:</strong><ul>')
        for w in info[:5]:  # Limit to 5 info messages
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div>')

    return '\n'.join(html_parts)
