# Operational Constraints Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-000      | 1.0     | 2026-03-01     | N/A        | Constitutional            |

## I. Purpose
Define non-negotiable operational constraints for the Classroom Token Hub application, setting the baseline for performance, resources, limits, dependencies, time zone handling, and data retention.

## II. Scope
Applies to all application environments (production, staging, demo) and governs future architectural additions.

## III. Authority Level
Authoritative (ARC Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- INV-CORE-000: Core Invariants

## V. Operational Constraints

### 1. Performance Baselines
- API response times must not exceed 500ms at the 95th percentile under normal load.
- Background jobs must complete within 5 minutes or gracefully chunk their work.

### 2. Scalability Limits
- Database connection pools must be scoped and bounded; manual overriding logic without pooling is prohibited.

### 3. Dependency Constraints
- The project dependencies (e.g. Python, PostgreSQL versions) are strictly controlled via `requirements.txt` and cannot be modified without accompanying infrastructure validation.

### 4. Time Zone Handling
- All internal storage must use strict UTC.
- Timezone interpretation must happen strictly at the presentation layer based on localized context of the user.

### 5. Data Retention
- Data retention must conform to the policies outlined in INV-CORE-000. Stale accounts must be securely purged according to their lifecycle.

## VI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
