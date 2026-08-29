"""
Class Configuration FEATs — Phase 4 Mutation Boundary (SOP-DEV-002)

These FEATs orchestrate canonical class configuration mutations per DOM-CLASS-001/002:
- FEAT-CLASS-001: Create class boundary (immutable class + initial economic engine)
- FEAT-CLASS-002: Modify class boundary (roster modifications within existing class)
- FEAT-CLASS-003: Insurance policy management (orchestrates FEAT-POL-001 definition writes)
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
)
from .feat_class_002_modify_class_boundary import (
    execute_modify_student,
    execute_remove_student_seat,
    ModifyStudentResult,
    RemoveStudentSeatResult,
)
from .feat_class_003_insurance_policy_management import (
    configure_insurance_definition,
    set_insurance_definition_availability,
    recommend_insurance_terms,
    InsuranceContractViolation,
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
    "execute_modify_student",
    "execute_remove_student_seat",
    "ModifyStudentResult",
    "RemoveStudentSeatResult",
    "configure_insurance_definition",
    "set_insurance_definition_availability",
    "recommend_insurance_terms",
    "InsuranceContractViolation",
    "execute_enable_feature",
    "execute_disable_feature",
    "FeatureEnablementResult",
    "FeatureDisablementResult",
    "execute_transition_economic_policy",
    "EconomicEngineEvolutionResult",
]
