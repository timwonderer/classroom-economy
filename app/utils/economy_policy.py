from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from flask import has_app_context
from app.utils.join_code import get_display_join_code


POLICY_MODE_DEFAULT = "default"
AVERAGE_WEEKS_PER_MONTH = Decimal("4.348214285714")
FREQUENCY_WEEK_MULTIPLIERS = {
    "daily": Decimal("0.142857142857"),
    "weekly": Decimal("1.0"),
    "biweekly": Decimal("2.0"),
    "monthly": Decimal("4.348214285714"),
    "semester": Decimal("18.0"),
    "yearly": Decimal("52.0"),
}
TIER_WAITING_PERIOD_DAYS = {
    1: 7,
    2: 5,
    3: 3,
}
TRANSACTION_TIER_MULTIPLIERS = {
    1: Decimal("0.75"),
    2: Decimal("1.0"),
    3: Decimal("1.3"),
}
TRANSACTION_TIER_LABELS = {
    1: "basic",
    2: "mid",
    3: "premium",
}
TRANSACTION_DEFAULTS = {
    "non_tiered": {
        "coverage_percent": Decimal("0.70"),
        "weekly_cap_multiplier": Decimal("3.0"),
        "waiting_period_days": 5,
    },
    "tiers": {
        1: {
            "coverage_percent": Decimal("0.50"),
            "weekly_cap_multiplier": Decimal("2.0"),
            "period_cap_multiplier": Decimal("6.0"),
            "waiting_period_days": 7,
        },
        2: {
            "coverage_percent": Decimal("0.70"),
            "weekly_cap_multiplier": Decimal("3.0"),
            "period_cap_multiplier": Decimal("8.0"),
            "waiting_period_days": 5,
        },
        3: {
            "coverage_percent": Decimal("0.90"),
            "weekly_cap_multiplier": Decimal("4.0"),
            "period_cap_multiplier": Decimal("10.0"),
            "waiting_period_days": 3,
        },
    },
}
VARIABLE_MONETARY_RISK_FACTORS = {
    "tight": Decimal("0.20"),
    "default": Decimal("0.15"),
    "comfortable": Decimal("0.12"),
}
FEATURE_FLAGS = {
    "payroll",
    "insurance",
    "banking",
    "rent",
    "hall_pass",
    "store",
}

ANALYTICS_POLICY_DEFAULTS: Dict[str, float] = {
    "cwi_deviation_band": 0.20,
    "cwi_deviation_warning_threshold": 0.20,
    "velocity_drop_warning_threshold": 0.30,
    "participation_warning_threshold": 0.70,
}

POLICY_MODES: Dict[str, Dict[str, Any]] = {
    "tight": {
        "label": "Tight",
        "summary": "More budgeting pressure",
        "description": "A leaner economy with less surplus and more deliberate spending.",
        "ratios": {
            "rent_weekly": {"min": 0.70, "max": 0.80, "recommended": 0.75},
            "utilities_weekly": {"min": 0.07, "max": 0.12, "recommended": 0.095},
            "insurance_weekly": {"min": 0.06, "max": 0.14, "recommended": 0.09},
            "insurance_coverage_multiplier": {"min": 2.5, "max": 4.0, "recommended": 3.25},
            "insurance_period_cap_multiplier": {"min": 5.0, "max": 8.0, "recommended": 6.5},
            "insurance_waiting_period_days": {"min": 10, "max": 14, "recommended": 10},
            "fine_weekly": {"min": 0.07, "max": 0.18, "recommended": 0.11},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.04},
                "premium": {"min": 0.04, "max": 0.12},
                "luxury": {"min": 0.12, "max": 0.24},
            },
            "savings_weekly": {"min": 0.05, "target": 0.05},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.07,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
    "default": {
        "label": "Default",
        "summary": "Balanced economy",
        "description": "The standard baseline with moderate pressure and stable survival margins.",
        "ratios": {
            "rent_weekly": {"min": 0.60, "max": 0.75, "recommended": 0.675},
            "utilities_weekly": {"min": 0.05, "max": 0.10, "recommended": 0.075},
            "insurance_weekly": {"min": 0.05, "max": 0.12, "recommended": 0.08},
            "insurance_coverage_multiplier": {"min": 3.0, "max": 5.0, "recommended": 4.0},
            "insurance_period_cap_multiplier": {"min": 6.0, "max": 10.0, "recommended": 8.0},
            "insurance_waiting_period_days": {"min": 7, "max": 7, "recommended": 7},
            "fine_weekly": {"min": 0.05, "max": 0.15, "recommended": 0.10},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.05},
                "premium": {"min": 0.05, "max": 0.15},
                "luxury": {"min": 0.15, "max": 0.30},
            },
            "savings_weekly": {"min": 0.10, "target": 0.10},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.06,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
    "comfortable": {
        "label": "Comfortable",
        "summary": "More breathing room",
        "description": "A more forgiving economy with lower fixed pressure and larger student margin.",
        "ratios": {
            "rent_weekly": {"min": 0.50, "max": 0.65, "recommended": 0.575},
            "utilities_weekly": {"min": 0.04, "max": 0.08, "recommended": 0.06},
            "insurance_weekly": {"min": 0.04, "max": 0.10, "recommended": 0.07},
            "insurance_coverage_multiplier": {"min": 4.0, "max": 6.0, "recommended": 5.0},
            "insurance_period_cap_multiplier": {"min": 8.0, "max": 12.0, "recommended": 10.0},
            "insurance_waiting_period_days": {"min": 3, "max": 7, "recommended": 5},
            "fine_weekly": {"min": 0.04, "max": 0.12, "recommended": 0.08},
            "store_tiers": {
                "basic": {"min": 0.02, "max": 0.04},
                "standard": {"min": 0.03, "max": 0.06},
                "premium": {"min": 0.06, "max": 0.18},
                "luxury": {"min": 0.18, "max": 0.35},
            },
            "savings_weekly": {"min": 0.15, "target": 0.175},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.05,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
}


def normalize_policy_mode(value: Optional[str]) -> str:
    mode = (value or POLICY_MODE_DEFAULT).strip().lower()
    return mode if mode in POLICY_MODES else POLICY_MODE_DEFAULT


def get_policy_profile(mode: Optional[str]) -> Dict[str, Any]:
    return POLICY_MODES[normalize_policy_mode(mode)]


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def convert_weekly_amount_to_frequency(
    value: Optional[Decimal],
    frequency: Optional[str],
    *,
    custom_frequency_value: Optional[int] = None,
    custom_frequency_unit: Optional[str] = None,
) -> Optional[Decimal]:
    if value is None:
        return None

    amount = Decimal(str(value))
    normalized_frequency = (frequency or "weekly").strip().lower()
    if normalized_frequency == "custom":
        unit = (custom_frequency_unit or "days").strip().lower()
        count = Decimal(str(custom_frequency_value or 1))
        if unit == "weeks":
            return _quantize_money(amount * count)
        if unit == "months":
            return _quantize_money(amount * AVERAGE_WEEKS_PER_MONTH * count)
        return _quantize_money(amount / (Decimal("7") / count))

    multiplier = FREQUENCY_WEEK_MULTIPLIERS.get(normalized_frequency, FREQUENCY_WEEK_MULTIPLIERS["weekly"])
    return _quantize_money(amount * multiplier)


def get_price_recommendation_context(mode: Optional[str], cwi: Optional[Decimal]) -> Optional[Dict[str, Any]]:
    """
    Central recommendation source for all economy-policy pricing guidance.
    """
    if cwi is None:
        return None

    profile = get_policy_profile(mode)
    ratios = profile.get("ratios", {})
    cwi_decimal = _quantize_money(Decimal(str(cwi)))

    def band(key: str, fallback_min: float, fallback_max: float, fallback_recommended: float) -> Dict[str, Decimal]:
        values = ratios.get(key, {})
        return {
            "min": _quantize_money(cwi_decimal * Decimal(str(values.get("min", fallback_min)))),
            "max": _quantize_money(cwi_decimal * Decimal(str(values.get("max", fallback_max)))),
            "recommended": _quantize_money(cwi_decimal * Decimal(str(values.get("recommended", fallback_recommended)))),
        }

    def multiplier_band(key: str, fallback_min: float, fallback_max: float, fallback_recommended: float) -> Dict[str, float]:
        values = ratios.get(key, {})
        return {
            "min": round(float(values.get("min", fallback_min)), 2),
            "max": round(float(values.get("max", fallback_max)), 2),
            "recommended": round(float(values.get("recommended", fallback_recommended)), 2),
        }

    def store_tiers() -> Dict[str, Dict[str, float]]:
        configured = ratios.get("store_tiers", {})
        defaults = {
            "basic": {"min": 0.02, "max": 0.05},
            "standard": {"min": 0.05, "max": 0.10},
            "premium": {"min": 0.10, "max": 0.25},
            "luxury": {"min": 0.25, "max": 0.50},
        }
        tier_map: Dict[str, Dict[str, float]] = {}
        for tier_name, fallback in defaults.items():
            band_values = configured.get(tier_name, fallback)
            tier_map[tier_name] = {
                "min": float(_quantize_money(cwi_decimal * Decimal(str(band_values.get("min", fallback["min"]))))),
                "max": float(_quantize_money(cwi_decimal * Decimal(str(band_values.get("max", fallback["max"]))))),
            }
        return tier_map

    rent_weekly = band("rent_weekly", 0.60, 0.75, 0.675)
    utilities_weekly = band("utilities_weekly", 0.05, 0.10, 0.075)
    insurance_weekly = band("insurance_weekly", 0.05, 0.12, 0.08)
    fine_weekly = band("fine_weekly", 0.05, 0.15, 0.10)
    coverage = multiplier_band("insurance_coverage_multiplier", 3.0, 5.0, 4.0)
    period_cap = multiplier_band("insurance_period_cap_multiplier", 6.0, 10.0, 8.0)
    waiting_period = ratios.get("insurance_waiting_period_days", {"min": 7, "max": 7, "recommended": 7})
    savings = ratios.get("savings_weekly", {"min": 0.10, "target": 0.10})

    return {
        "policy_mode": normalize_policy_mode(mode),
        "policy_label": profile["label"],
        "cwi": float(cwi_decimal),
        "rent_weekly": {key: float(value) for key, value in rent_weekly.items()},
        "rent": {
            key: float(_quantize_money(value * AVERAGE_WEEKS_PER_MONTH))
            for key, value in rent_weekly.items()
        },
        "utilities": {key: float(value) for key, value in utilities_weekly.items()},
        "insurance_premium_weekly": {key: float(value) for key, value in insurance_weekly.items()},
        "insurance_coverage": {
            "multiplier_min": coverage["min"],
            "multiplier_max": coverage["max"],
            "multiplier_recommended": coverage["recommended"],
        },
        "insurance_period_cap": {
            "multiplier_min": period_cap["min"],
            "multiplier_max": period_cap["max"],
            "multiplier_recommended": period_cap["recommended"],
        },
        "insurance_waiting_period_days": {
            "min": int(waiting_period.get("min", 7)),
            "max": int(waiting_period.get("max", 7)),
            "recommended": int(waiting_period.get("recommended", 7)),
        },
        "fine": {key: float(value) for key, value in fine_weekly.items()},
        "store_tiers": store_tiers(),
        "min_weekly_savings": float(_quantize_money(cwi_decimal * Decimal(str(savings.get("min", 0.10))))),
    }


def get_insurance_premium_recommendation(
    mode: Optional[str],
    cwi: Optional[Decimal],
    *,
    frequency: str = "weekly",
) -> Optional[Dict[str, Any]]:
    """
    Shared premium guidance for insurance pricing.

    This helper is the backend source for the values shown in economy-health style
    recommendations and insurance setup/edit guidance. It follows the policy-mode
    profile ratios, which in turn implement the documented economics contract:
    - docs/FEATURES/ECONOMY/FEAT-ECON-001_Policy_Mode_and_Rebalancer.md
    - docs/DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md
    """
    recommendation_context = get_price_recommendation_context(mode, cwi)
    if recommendation_context is None:
        return None

    weekly = recommendation_context["insurance_premium_weekly"]
    cwi_decimal = _quantize_money(Decimal(str(recommendation_context["cwi"])))
    weekly_min = _quantize_money(Decimal(str(weekly["min"])))
    weekly_max = _quantize_money(Decimal(str(weekly["max"])))
    weekly_recommended = _quantize_money(Decimal(str(weekly["recommended"])))

    return {
        "frequency": (frequency or "weekly").strip().lower(),
        "cwi": cwi_decimal,
        "min_weekly": weekly_min,
        "max_weekly": weekly_max,
        "recommended_weekly": weekly_recommended,
        "min": convert_weekly_amount_to_frequency(weekly_min, frequency),
        "max": convert_weekly_amount_to_frequency(weekly_max, frequency),
        "recommended": convert_weekly_amount_to_frequency(weekly_recommended, frequency),
    }


def get_transaction_coverage_default(mode: Optional[str]) -> Decimal:
    return TRANSACTION_DEFAULTS["non_tiered"]["coverage_percent"]


def get_tier_waiting_period_days(tier_rank: Optional[int]) -> int:
    try:
        normalized_rank = int(tier_rank) if tier_rank is not None else None
    except (TypeError, ValueError):
        normalized_rank = None
    return int(TIER_WAITING_PERIOD_DAYS.get(normalized_rank, TRANSACTION_DEFAULTS["non_tiered"]["waiting_period_days"]))


def get_variable_monetary_risk_factor(mode: Optional[str]) -> Decimal:
    return VARIABLE_MONETARY_RISK_FACTORS.get(normalize_policy_mode(mode), VARIABLE_MONETARY_RISK_FACTORS[POLICY_MODE_DEFAULT])


def get_transaction_tier_multipliers_by_level() -> Dict[str, float]:
    return {
        TRANSACTION_TIER_LABELS[rank]: float(multiplier)
        for rank, multiplier in TRANSACTION_TIER_MULTIPLIERS.items()
    }


def get_recommended_insurance_weekly_premium(mode: Optional[str], cwi: Optional[Decimal]) -> Optional[Decimal]:
    if cwi is None:
        return None
    profile = get_policy_profile(mode)
    weekly_premium_rate = Decimal(
        str(profile.get("ratios", {}).get("insurance_weekly", {}).get("recommended", 0.08))
    )
    return (Decimal(str(cwi)) * weekly_premium_rate).quantize(Decimal("0.01"))


def get_transaction_tier_defaults(
    mode: Optional[str],
    tier_rank: int,
    cwi: Optional[Decimal] = None,
    *,
    base_premium: Optional[Decimal] = None,
    billing_weeks: int = 1,
) -> Dict[str, Any]:
    profile = get_policy_profile(mode)
    profile_tier_defaults = profile.get("insurance_transaction_defaults", {}).get("tiers", {}).get(int(tier_rank), {})
    tier_defaults = TRANSACTION_DEFAULTS["tiers"].get(int(tier_rank), TRANSACTION_DEFAULTS["non_tiered"])
    weekly_premium_rate = Decimal(
        str(profile.get("ratios", {}).get("insurance_weekly", {}).get("recommended", 0.08))
    )
    coverage_percent = Decimal(str(profile_tier_defaults.get("coverage_percent", tier_defaults["coverage_percent"])))
    tier_multiplier = TRANSACTION_TIER_MULTIPLIERS.get(int(tier_rank), Decimal("1.0"))
    weekly_cap_multiplier = Decimal(str(tier_defaults["weekly_cap_multiplier"]))
    period_cap_multiplier = Decimal(
        str(profile_tier_defaults.get("period_cap_multiplier", tier_defaults.get("period_cap_multiplier", weekly_cap_multiplier)))
    )
    resolved_base_premium = None
    if base_premium is not None:
        resolved_base_premium = Decimal(str(base_premium)).quantize(Decimal("0.01"))
    elif cwi is not None:
        resolved_base_premium = get_recommended_insurance_weekly_premium(mode, cwi)
    resolved_premium = None
    weekly_cap = None
    max_payout_per_period = None
    normalized_weeks = max(int(billing_weeks or 1), 1)
    if resolved_base_premium is not None:
        resolved_premium = (resolved_base_premium * tier_multiplier).quantize(Decimal("0.01"))
        weekly_cap = (resolved_premium * weekly_cap_multiplier).quantize(Decimal("0.01"))
        max_payout_per_period = (weekly_cap * Decimal(str(normalized_weeks))).quantize(Decimal("0.01"))

    return {
        "weekly_premium_rate": weekly_premium_rate,
        "base_premium": resolved_base_premium,
        "coverage_percent": coverage_percent,
        "tier_multiplier": tier_multiplier,
        "period_cap_multiplier": period_cap_multiplier,
        "weekly_cap_multiplier": weekly_cap_multiplier,
        "weekly_cap": weekly_cap,
        "billing_weeks": normalized_weeks,
        "waiting_period_days": int(profile_tier_defaults.get("waiting_period_days", tier_defaults["waiting_period_days"])),
        "premium": resolved_premium,
        "max_payout_per_period": max_payout_per_period,
    }


def resolve_class_scope(
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, str]]:
    if not has_app_context() or not user_id:
        return None

    from app.models import ClassEconomy

    normalized_class_id = str(class_id).strip() if class_id else None
    if not normalized_class_id:
        return None

    class_row = (
        ClassEconomy.query.with_entities(ClassEconomy.class_id, ClassEconomy.section)
        .filter(
            ClassEconomy.teacher_user_id == user_id,
            ClassEconomy.class_id == normalized_class_id,
        )
        .first()
    )
    if not class_row:
        return None

    return {
        "class_id": class_row.class_id,
        "join_code": get_display_join_code(class_row.class_id),
        "block": class_row.section,
    }


def resolve_feature_class(
    user_id: int,
    feature_name: str,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if feature_name not in FEATURE_FLAGS:
        raise ValueError(f"Unknown feature flag: {feature_name}")

    scope = resolve_class_scope(user_id, class_id=class_id)
    if not scope:
        return None

    from app.models import ClassFeature

    enabled = feature_name in ClassFeature.enabled_names_for_class(scope["class_id"])

    return {
        **scope,
        "enabled": bool(enabled),
        "feature_name": feature_name,
    }


def get_class_feature_settings(
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not has_app_context():
        return None

    from app.models import ClassFeature

    scope = resolve_class_scope(user_id, class_id=class_id)
    if not scope:
        return None
    return {
        **scope,
        "features": ClassFeature.feature_map_for_class(scope["class_id"]),
    }


def replace_enabled_class_features(class_id: str, enabled_features: set[str]) -> None:
    from app.extensions import db
    from app.models import ClassFeature

    valid_features = set(ClassFeature.feature_names())
    requested_features = {name for name in enabled_features if name in valid_features}
    # Payroll is mandatory in v2 class feature gating.
    requested_features.add("payroll")
    existing_rows = ClassFeature.query.filter_by(class_id=class_id).all()
    existing_names = {row.feature for row in existing_rows}

    for row in existing_rows:
        if row.feature not in requested_features:
            db.session.delete(row)

    missing_names = requested_features - existing_names
    for feature_name in sorted(missing_names):
        db.session.add(ClassFeature(class_id=class_id, feature=feature_name))


def get_feature_settings_row(
    user_id: int,
    class_id: Optional[str] = None,
    create: bool = False,
):
    if not has_app_context():
        return None

    scope = resolve_class_scope(user_id, class_id=class_id)
    if not scope:
        return None
    return get_feature_settings_row_for_class(
        scope["class_id"],
        create=create,
    )


def get_feature_settings_row_for_class(
    class_id: str | None,
    *,
    create: bool = False,
):
    """Resolve feature settings by explicit canonical class_id context.

    This helper is class-authoritative and never infers scope from legacy keys.
    """
    if not has_app_context() or not class_id:
        return None

    from app.extensions import db
    from app.models import FeatureSettings

    row = FeatureSettings.query.filter_by(class_id=class_id).first()
    if row or not create:
        return row

    row = FeatureSettings(
        class_id=class_id,
    )
    db.session.add(row)
    db.session.flush()
    return row


def get_active_policy_mode(
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> str:
    if not has_app_context():
        return POLICY_MODE_DEFAULT

    row = get_feature_settings_row(user_id, class_id=class_id, create=False)
    if not row:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(row, "economy_policy_mode", POLICY_MODE_DEFAULT))


def get_active_policy_mode_for_class(class_id: Optional[str]) -> str:
    if not has_app_context() or not class_id:
        return POLICY_MODE_DEFAULT

    from app.models import FeatureSettings

    row = FeatureSettings.query.filter_by(class_id=class_id).first()
    if not row:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(row, "economy_policy_mode", POLICY_MODE_DEFAULT))


def resolve_feature_class_for_class(
    class_id: Optional[str],
    feature_name: str,
) -> Optional[dict[str, Any]]:
    """Resolve feature enablement by explicit canonical class_id."""
    if feature_name not in FEATURE_FLAGS:
        raise ValueError(f"Unknown feature flag: {feature_name}")
    if not has_app_context() or not class_id:
        return None

    from app.extensions import db
    from app.models import ClassFeature
    from app.models import ClassEconomy
    from app.utils.join_code import get_display_join_code

    class_row = db.session.get(ClassEconomy, class_id)
    if not class_row:
        return None

    enabled = feature_name in ClassFeature.enabled_names_for_class(class_id)
    return {
        "class_id": class_id,
        "enabled": bool(enabled),
        "feature_name": feature_name,
        "join_code": get_display_join_code(class_id),
    }


def get_class_feature_settings_for_class(
    class_id: Optional[str],
) -> Optional[dict[str, Any]]:
    """Return class feature map by explicit canonical class_id."""
    if not has_app_context() or not class_id:
        return None

    from app.models import ClassEconomy, ClassFeature

    class_exists = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(class_id=class_id).first()
    if not class_exists:
        return None

    return {
        "class_id": class_id,
        "features": ClassFeature.feature_map_for_class(class_id),
    }


def get_analytics_policy(mode: Optional[str]) -> Dict[str, float]:
    profile = get_policy_profile(mode)
    configured = profile.get("analytics", {})
    return {
        key: float(configured.get(key, default_value))
        for key, default_value in ANALYTICS_POLICY_DEFAULTS.items()
    }
