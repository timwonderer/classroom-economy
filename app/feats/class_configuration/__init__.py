"""
Class Configuration FEATs — Phase 4 Mutation Boundary (SOP-DEV-002)

These FEATs orchestrate canonical class configuration mutations per DOM-CLASS-001/002:
- FEAT-CLASS-001: Create class boundary (immutable class + initial economic engine)
- FEAT-CLASS-002: Modify class boundary (roster modifications within existing class)
- FEAT-CLASS-004: Feature enablement/disablement (append-only class_features timeline)
- FEAT-CLASS-005: Economic engine evolution (immutable versioned policy transitions)

All FEATs enforce:
- CanonicalContext (user_id, class_id, seat_id, actor_role=teacher)
- Idempotency via natural primary key tuples
- SPEC-TIME-001 canonical temporal resolution
- INV-ARC-016 audit lineage (soft deletion)
"""

from .feat_class_001_create_class_boundary import (
    execute_create_class_boundary,
    CreateClassBoundaryResult,
    execute_set_class_timezone,
    SetClassTimezoneResult,
)
from .feat_class_002_modify_class_boundary import (
    execute_modify_student,
    execute_provision_student_seat,
    execute_remove_student_seat,
    ModifyStudentResult,
    ProvisionStudentSeatResult,
    RemoveStudentSeatResult,
)
from .feat_class_004_feature_enablement import (
    execute_enable_feature,
    execute_disable_feature,
    FeatureEnablementResult,
    FeatureDisablementResult,
)
from .feat_class_005_economic_engine_evolution import (
    execute_transition_economic_policy,
    EconomicEngineEvolutionResult,
)

__all__ = [
    "execute_create_class_boundary",
    "CreateClassBoundaryResult",
    "execute_set_class_timezone",
    "SetClassTimezoneResult",
    "execute_modify_student",
    "execute_provision_student_seat",
    "execute_remove_student_seat",
    "ModifyStudentResult",
    "ProvisionStudentSeatResult",
    "RemoveStudentSeatResult",
    "execute_enable_feature",
    "execute_disable_feature",
    "FeatureEnablementResult",
    "FeatureDisablementResult",
    "execute_transition_economic_policy",
    "EconomicEngineEvolutionResult",
]
