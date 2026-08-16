"""
Class Configuration domain — Phase 5 view models and builders.

Authority: DOM-CLASS-001
Implements: Frozen read models for class identity, feature state, and economic config.

Routes and templates consume these view models rather than accessing ClassEconomy,
ClassFeature, or EconomicEngine models directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.class_configuration_query_service import (
    calculate_cwi,
    get_all_classes_by_teacher,
    get_class_economy,
    get_class_features,
    get_policy_mode,
)


@dataclass(frozen=True)
class ClassSummaryView:
    """Lightweight class identity for lists and selectors."""
    class_id: str
    class_public_id: str
    join_code: str
    display_name: str | None
    section: str | None
    timezone: str
    created_at: datetime

    @property
    def label(self) -> str:
        return self.display_name or self.section or self.join_code


@dataclass(frozen=True)
class ClassConfigurationView:
    """Full class configuration for settings pages."""
    class_id: str
    class_public_id: str
    join_code: str
    display_name: str | None
    section: str | None
    timezone: str
    teacher_user_id: int
    created_at: datetime
    policy_mode: str | None
    cwi: float | None
    features_enabled: tuple[str, ...]

    @property
    def label(self) -> str:
        return self.display_name or self.section or self.join_code


@dataclass(frozen=True)
class FeatureStateView:
    """Single feature's enablement state."""
    feature: str
    enabled: bool
    effective_at: datetime | None


@dataclass(frozen=True)
class FeatureConfigurationView:
    """All feature toggles for a class."""
    class_id: str
    features: tuple[FeatureStateView, ...]

    def is_enabled(self, feature: str) -> bool:
        for f in self.features:
            if f.feature == feature:
                return f.enabled
        return False


KNOWN_FEATURES = ("payroll", "rent", "banking", "insurance", "hall_pass", "store")


@dataclass(frozen=True)
class FeatureDefinitionView:
    """Static feature metadata for display."""
    feature_id: str
    name: str
    icon: str
    description: str


FEATURE_DEFINITIONS = (
    FeatureDefinitionView("payroll_enabled", "Payroll", "payments", "Time tracking and student payments"),
    FeatureDefinitionView("insurance_enabled", "Insurance", "shield", "Insurance policies and claims"),
    FeatureDefinitionView("banking_enabled", "Banking", "account_balance", "Savings accounts and interest"),
    FeatureDefinitionView("rent_enabled", "Rent", "home", "Housing costs and payments"),
    FeatureDefinitionView("hall_pass_enabled", "Hall Pass", "confirmation_number", "Bathroom and water break passes"),
    FeatureDefinitionView("store_enabled", "Store", "storefront", "Marketplace for student rewards"),
)


@dataclass(frozen=True)
class ClassLabelView:
    """Class label for the account settings form."""
    section_key: str
    current_label: str | None
    display_fallback: str

    @property
    def form_key(self) -> str:
        return f"class_label_{self.section_key}"


@dataclass(frozen=True)
class FeatureSettingsPageView:
    """Page view model for admin_feature_settings.html (single-class scoped)."""
    class_id: str
    class_label: str
    features: tuple[FeatureToggleView, ...]


@dataclass(frozen=True)
class FeatureToggleView:
    """Single feature toggle with metadata for display."""
    feature_id: str
    feature_key: str
    name: str
    icon: str
    description: str
    enabled: bool


@dataclass(frozen=True)
class AccountSettingsPageView:
    """Page view model for admin_settings.html (CLASS-owned fields only)."""
    classes: tuple[ClassLabelView, ...]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_class_summary_view(class_id: str) -> ClassSummaryView | None:
    """Build a lightweight class summary from the canonical class record."""
    economy = get_class_economy(class_id)
    if not economy:
        return None
    return ClassSummaryView(
        class_id=economy.class_id,
        class_public_id=economy.class_public_id,
        join_code=economy.join_code,
        display_name=economy.display_name,
        section=economy.section,
        timezone=economy.class_timezone,
        created_at=economy.created_at,
    )


def build_class_list_view(teacher_user_id: int) -> list[ClassSummaryView]:
    """Build summary views for all classes owned by a teacher."""
    classes = get_all_classes_by_teacher(teacher_user_id)
    return [
        ClassSummaryView(
            class_id=c.class_id,
            class_public_id=c.class_public_id,
            join_code=c.join_code,
            display_name=c.display_name,
            section=c.section,
            timezone=c.class_timezone,
            created_at=c.created_at,
        )
        for c in classes
    ]


def build_class_configuration_view(class_id: str) -> ClassConfigurationView | None:
    """Build full class configuration view for settings pages."""
    economy = get_class_economy(class_id)
    if not economy:
        return None

    features = get_class_features(class_id)
    enabled_names = tuple(sorted(features.keys()))

    return ClassConfigurationView(
        class_id=economy.class_id,
        class_public_id=economy.class_public_id,
        join_code=economy.join_code,
        display_name=economy.display_name,
        section=economy.section,
        timezone=economy.class_timezone,
        teacher_user_id=economy.teacher_user_id,
        created_at=economy.created_at,
        policy_mode=get_policy_mode(class_id),
        cwi=calculate_cwi(class_id),
        features_enabled=enabled_names,
    )


def build_feature_configuration_view(class_id: str) -> FeatureConfigurationView:
    """Build feature enablement view for the feature settings page."""
    enabled_features = get_class_features(class_id)

    feature_states = tuple(
        FeatureStateView(
            feature=name,
            enabled=enabled_features.get(name) is not None,
            effective_at=enabled_features[name].effective_at if name in enabled_features else None,
        )
        for name in KNOWN_FEATURES
    )

    return FeatureConfigurationView(
        class_id=class_id,
        features=feature_states,
    )


def build_feature_settings_page_view(class_id: str) -> FeatureSettingsPageView | None:
    """Build page view model for admin_feature_settings.html (single-class scoped)."""
    economy = get_class_economy(class_id)
    if not economy:
        return None

    feature_map = get_class_features(class_id)

    toggles = tuple(
        FeatureToggleView(
            feature_id=defn.feature_id,
            feature_key=defn.feature_id.replace("_enabled", ""),
            name=defn.name,
            icon=defn.icon,
            description=defn.description,
            enabled=(defn.feature_id.replace("_enabled", "") in feature_map),
        )
        for defn in FEATURE_DEFINITIONS
    )

    return FeatureSettingsPageView(
        class_id=class_id,
        class_label=economy.display_name or economy.section or economy.join_code,
        features=toggles,
    )


def build_account_settings_page_view(teacher_user_id: int) -> AccountSettingsPageView:
    """Build CLASS-owned fields for admin_settings.html."""
    classes = get_all_classes_by_teacher(teacher_user_id)

    class_labels = tuple(
        ClassLabelView(
            section_key=cls.section or cls.join_code or "",
            current_label=cls.display_name,
            display_fallback=cls.section or cls.join_code or "",
        )
        for cls in classes
    )

    return AccountSettingsPageView(classes=class_labels)
