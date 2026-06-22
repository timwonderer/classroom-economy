# DOM-ECON-001: Economy Balance Checker - Implementation Guide

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ECON-001     | 1.1     | 2026-03-08     | 1.0        | Normative       |

## I. Purpose
The Economy Balance Checker is a centralized system that validates all economy settings against the Classroom Wage Index (CWI) per the AGENTS financial setup specification. This document outlines its implementation, components, and integration points.

## II. Scope
Applies to the Python backend utility, administrative REST APIs, and client-side JavaScript module that perform real-time and structural validation of economy prices/premiums/rents in the application.

## III. Authority Level
Normative (DOM Tier). Subordinate to INV-CORE-000 and DOM-ECON-002.

## IV. Dependencies
- `DOM-ECON-002_Economy_Specification.md`

## V. CWI Definition
**CWI (Classroom Wage Index)** is the expected weekly income for a student with perfect attendance. All economy features (rent, insurance, fines, store items) must scale proportionally from CWI to maintain balance.

Teachers must specify their **expected weekly hours** (or minutes) in payroll settings. This value represents how many hours per week students typically attend class. This is used ONLY for economy balance checking, not for actual payroll calculations.

## VI. System Components

### 1. Backend Utility (`app/utils/economy_balance.py`)
Core Python module that:
- Calculates CWI dynamically based on payroll settings
- Validates economy settings against standard ratios (defined in DOM-ECON-002)
- Returns teacher recommendation payloads from the shared economy-policy layer
- Performs budget survival tests

### 2. Admin Economy Health Page (`/admin/economy-health`)
Teachers can review their current CWI and economy balance from one place. The page:
- Shows the active CWI, pay rate, and expected weekly hours
- Summarizes rent, insurance, fines, store setup, and banking interest
- Surfaces critical/warning/info notices from the `EconomyBalanceChecker`
- Lists recommended ranges for economics parameters

### 3. API Endpoints (`app/routes/admin.py`)
Three RESTful endpoints for real-time validation:
- `/admin/api/economy/calculate-cwi` (POST): Calculate CWI based on pay rate.
- `/admin/api/economy/analyze` (POST): Perform comprehensive economy analysis.
- `/admin/api/economy/validate/<feature>` (POST): Validate a specific feature value.

### 4. Client-Side Module (`static/js/economy-balance.js`)
JavaScript class for real-time validation in forms (debounce 500ms).
Usage requires standard data attributes (e.g., `data-economy-validate="rent"`).

Client-side pages may display validation results, but ratio derivation and recommendation values remain backend-owned. Recommendation math shall originate in `app/utils/economy_policy.py`; `EconomyBalanceChecker`, admin routes, and templates are consumers of that source, not alternative calculators.

## VII. Integrated Pages
The balance checker is currently integrated into:
1. **Payroll Page** (`/admin/payroll`)
2. **Rent Settings** (`/admin/rent-settings`)
3. **Insurance Policy Editor** (`/admin/insurance/edit/<id>`)
4. **Store Item Editor** (`/admin/store/edit/<id>`)
5. **Fines** (via API)
6. **Insurance Policy Creation** (`/admin/insurance`) for shared premium guidance text

## VIII. Budget Survival Test
The system performs a "Budget Survival Test" to ensure students can:
- Pay rent
- Afford insurance (cheapest option)
- Purchase store items
- Save at least **10% of CWI** weekly

If this test fails, teachers receive a **CRITICAL** warning.

## IX. Warning Levels
- **INFO**: Setting is balanced and within recommended range
- **WARNING**: Setting deviates from recommended range (15-30%)
- **CRITICAL**: Setting deviates significantly (>30%) or fails budget test

## X. Block-Scoped CWI Calculations

**IMPORTANT:** For specialty schools with different pay rates per class/block:
- **Payroll Settings** are block-scoped (different pay rates and expected weekly hours)
- **Rent Settings** are block-scoped
- **Insurance Policies** are NOT block-scoped: Premiums are the same across all blocks (only visibility is controlled)
- **Store Items** are NOT block-scoped
- **Fines** are NOT block-scoped

When calculating CWI, the API uses the `block` parameter if provided, otherwise defaulting to the first active payroll setting found.

## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
