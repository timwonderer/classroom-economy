# DOM-CLASS-002: Class Economy Governance

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-CLASS-002 | 2.0 | 2026-08-08 | 1.1 | Constitutional |

## I. Purpose

This document defines the class economy foundation for Classroom Token Hub (CTH).

It derives its authority from `DOM-CLASS-001` and provides the class-economy facts that `DOM-CLASS-003` and the `SPEC-ECON-*` documents build on.

This document establishes:
- the class economy is CWI-relative,
- the class economy supports `tight`, `default`, and `comfortable` modes,
- class economy configuration belongs to Class Configuration,
- rebalance actions are class-economy events,
- bank-related businesses are part of class configuration,
- behavioral calculations are defined by the relevant `SPEC-ECON-*` documents.

## II. Scope

This document governs:
- class economic posture,
- supported economic mode,
- class-wide economic configuration facts,
- economic rebalance boundaries,
- class-level economic inputs consumed by downstream specs and features.

This document does not govern:
- interest formulas,
- compounding formulas,
- accrual timing,
- solvency math,
- analytics metrics,
- visibility behavior,
- or other execution semantics.

The exact specification for interest and compounding rules as well as overdraft behavior belongs in SPEC level documentations.

## III. Authority Level

Constitutional (DOM Tier).

Subordinate to:
- `INV-CORE-000`
- `DOM-CORE-000`
- `INV-ARC-015`

No FEAT, SOP, runtime workflow, API surface, or UI behavior may override the class economy facts established here.

## IV. Class Economy Facts

`DOM-CLASS-002` establishes these class economy facts:
- the class economy is CWI-relative,
- the class economy has exactly three supported modes,
- the class economy can be rebalanced,
- class-level economic configuration is stored by `DOM-CLASS-001`,
- execution semantics are owned by the relevant SPEC and FEAT layers.

`DOM-CLASS-002` does not define the formulas or behavioral rules for:
- CWI derivation,
- savings interest,
- policy calibration,
- solvency,
- or analytics.

## V. Relationship to Other Documents

`DOM-CLASS-001` owns:
- class identity,
- class configuration storage,
- and the `economic-engine` table.

`DOM-CLASS-003` owns:
- economics policy lineage,
- policy version state,
- and policy activation semantics.

`SPEC-ECON-001` owns:
- savings interest accrual,
- disbursement,
- compounding,
- eligibility,
- and scheduling behavior.

`SPEC-ECON-002` owns:
- policy visibility,
- future-law disclosure,
- and operational disclosure behavior.

## VI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with `DOM-CLASS-001`.
