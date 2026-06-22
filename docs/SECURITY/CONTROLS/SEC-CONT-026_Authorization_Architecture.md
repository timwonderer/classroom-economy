# SEC-CONT-026: Authorization Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SEC-CONT-026     | 1.0     | 2026-03-01     | N/A        | Normative       |

## I. Purpose
Define the Role-Based Access Control (RBAC) model, role definitions, permission scoping, and authoritative access constraints.

## II. Scope
All routes, services, and tenant operations within the application.

## III. Authority Level
Authoritative (ARC Tier). Evaluated against INV-CORE-000 isolation rules.

## IV. Dependencies
- INV-CORE-000: Core Invariants

## V. Role Definitions and Mapping
1. **System Administrator**
   - **Scope:** Application-wide management.
   - **Permissions:** Account administration, feature toggles, environment configurations. Cannot impersonate or login to student accounts.
   
2. **Teacher**
   - **Scope:** Bounded to owned `join_code` allocations.
   - **Permissions:** Can issue currency, deduct currency, handle attendance, approve transactions, setup storefronts, and manage class configurations.
   
3. **Student**
   - **Scope:** Bounded strictly to their specific `join_code` context.
   - **Permissions:** Can view balances, purchase items, clock in/out, and transfer to other students within the exact same `join_code` ONLY.

## VI. Cross-Tenant Constraints
- No user with the role `Teacher` or `Student` may access records that lack their direct `join_code` associated primary or foreign keys.
- Privilege escalation is strictly prohibited. Transitioning from Teacher to Student requires independent session initialization.

## VII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
