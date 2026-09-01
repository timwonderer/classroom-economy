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
# NOTE: The legacy TRANSACTION_* tier constants (base-premium × tier-multiplier
# pricing model) were removed as part of the SPEC-ECON-003 insurance migration.
# The canonical insurance economic model (deterministic per-(product, tier, mode)
# presets) now lives in app/services/economic_engine.py (resolve_insurance).
FEATURE_FLAGS = {
    "payroll",
    "insurance",
    "banking",
    "rent",
    "hall_pass",
    "store",
}

POLICY_MODES: Dict[str, Dict[str, Any]] = {
    "tight": {
        "label": "Tight",
        "summary": "More budgeting pressure",
        "description": "A leaner economy with less surplus and more deliberate spending.",
        "ratios": {
            "rent_weekly": {"min": 0.70, "max": 0.80, "recommended": 0.75},
            "utilities_weekly": {"min": 0.07, "max": 0.12, "recommended": 0.095},
            "fine_weekly": {"min": 0.07, "max": 0.18, "recommended": 0.11},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.04},
                "premium": {"min": 0.04, "max": 0.12},
                "luxury": {"min": 0.12, "max": 0.24},
            },
            "savings_weekly": {"min": 0.05, "target": 0.05},
        },
    },
    "default": {
        "label": "Default",
        "summary": "Balanced economy",
        "description": "The standard baseline with moderate pressure and stable survival margins.",
        "ratios": {
            "rent_weekly": {"min": 0.60, "max": 0.75, "recommended": 0.675},
            "utilities_weekly": {"min": 0.05, "max": 0.10, "recommended": 0.075},
            "fine_weekly": {"min": 0.05, "max": 0.15, "recommended": 0.10},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.05},
                "premium": {"min": 0.05, "max": 0.15},
                "luxury": {"min": 0.15, "max": 0.30},
            },
            "savings_weekly": {"min": 0.10, "target": 0.10},
        },
    },
    "comfortable": {
        "label": "Comfortable",
        "summary": "More breathing room",
        "description": "A more forgiving economy with lower fixed pressure and larger student margin.",
        "ratios": {
            "rent_weekly": {"min": 0.50, "max": 0.65, "recommended": 0.575},
            "utilities_weekly": {"min": 0.04, "max": 0.08, "recommended": 0.06},
            "fine_weekly": {"min": 0.04, "max": 0.12, "recommended": 0.08},
            "store_tiers": {
                "basic": {"min": 0.02, "max": 0.04},
                "standard": {"min": 0.03, "max": 0.06},
                "premium": {"min": 0.06, "max": 0.18},
                "luxury": {"min": 0.18, "max": 0.35},
            },
            "savings_weekly": {"min": 0.15, "target": 0.175},
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

    # NOTE (SPEC-ECON-003 migration): insurance pricing guidance is no longer
    # produced here. Insurance recommendations are owned exclusively by the
    # Economic Engine (app/services/economic_engine.resolve_insurance), which is
    # product- and tier-aware. This legacy builder retains only the
    # rent/utilities/fines/store/savings surfaces still pending their own
    # Engine migration.
    rent_weekly = band("rent_weekly", 0.60, 0.75, 0.675)
    utilities_weekly = band("utilities_weekly", 0.05, 0.10, 0.075)
    fine_weekly = band("fine_weekly", 0.05, 0.15, 0.10)
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
        "fine": {key: float(value) for key, value in fine_weekly.items()},
        "store_tiers": store_tiers(),
        "min_weekly_savings": float(_quantize_money(cwi_decimal * Decimal(str(savings.get("min", 0.10))))),
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
    from app.models import ClassFeature, EconomicEngine
    from sqlalchemy import desc

    valid_features = set(ClassFeature.feature_names())
    requested_features = {name for name in enabled_features if name in valid_features}
    # Payroll is mandatory in v2 class feature gating.
    requested_features.add("payroll")

    # Get the current economic version for this class
    latest_engine = EconomicEngine.query.filter_by(
        class_id=class_id
    ).order_by(desc(EconomicEngine.created_at)).first()

    if not latest_engine:
        # Create default engine if missing
        latest_engine = EconomicEngine(
            class_id=class_id,
            economic_version_id="v1",
            economy_policy_mode="default",
        )
        db.session.add(latest_engine)
        db.session.flush()

    economic_version_id = latest_engine.economic_version_id

    # Get currently enabled features for this class
    currently_enabled = ClassFeature.enabled_names_for_class(class_id)

    # For each feature, if the requested state differs from current state, append a row
    for feature_name in sorted(valid_features | requested_features):
        is_currently_enabled = feature_name in currently_enabled
        should_be_enabled = feature_name in requested_features

        if is_currently_enabled != should_be_enabled:
            # State changed; append new row to timeline
            if should_be_enabled:
                # Enable: set version_id to current version
                db.session.add(ClassFeature(
                    class_id=class_id,
                    feature=feature_name,
                    economic_version_id=economic_version_id
                ))
            else:
                # Disable: set version_id to None
                db.session.add(ClassFeature(
                    class_id=class_id,
                    feature=feature_name,
                    economic_version_id=None
                ))


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
    """Get the active policy mode for a class from its latest EconomicEngine version.

    Refactored in Phase 2 to get policy_mode from EconomicEngine instead of FeatureSettings.
    If no EconomicEngine version exists yet, returns the default policy mode.
    """
    if not has_app_context() or not class_id:
        return POLICY_MODE_DEFAULT

    from app.models import EconomicEngine
    from sqlalchemy import desc

    # Get the most recent EconomicEngine version for this class
    economic_engine = EconomicEngine.query.filter_by(
        class_id=class_id
    ).order_by(desc(EconomicEngine.created_at)).first()

    if not economic_engine:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(economic_engine, "economy_policy_mode", POLICY_MODE_DEFAULT))


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
