# SPEC-STORE-001: Store Product Policy Payload Schema

| Reference Number | Version | Effective Date | Authority Level |
|------------------|---------|----------------|-----------------|
| SPEC-STORE-001 | 1.0 | 2026-07-28 | Normative |

## I. Purpose

Define the JSON schema for `STORE_PRODUCT` policy payloads consumed by Store & Entitlements FEATs.

This specification is the authoritative contract for parsing and validating product configuration when creating entitlements.

## II. Scope

This specification applies to:

- All product policies stored in `policy_versions` with `policy_family="STORE_PRODUCT"`
- All FEAT operations that read and consume product policies (FEAT-STOR-001, FEAT-STOR-004, etc.)
- All parsers, validators, and configuration objects that process product policies

## III. Authority Level

Normative. This specification is subordinate to:

- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

## IV. JSON Schema

### A. Required Fields

```json
{
  "product_id": <integer>,
  "is_purchasable": <boolean>,
  "supports_direct_grants": <boolean>,
  "price": <decimal string>,
  "entitlement_type": <enum>
}
```

**Field Definitions:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `product_id` | integer | Stable product identifier | Must match policy_id in policy_versions |
| `is_purchasable` | boolean | Can students purchase this product? | Required for FEAT-STOR-001 validation |
| `supports_direct_grants` | boolean | Can teachers grant directly? | Required for FEAT-STOR-004 validation |
| `price` | decimal (string) | Cost per unit | Must be ≥ 0; decimal with 2 scale |
| `entitlement_type` | enum | Entitlement lifecycle type | See Section IV.B for valid values |

### B. Entitlement Type Values

Closed enum; exactly one of:

```
IMMEDIATE_USE     - Granted and consumed in the same action (no expiry)
DELAYED_USE       - Granted now, consumed later (requires auto_expiry_days)
HALL_PASS         - Teacher-grantable; externally consumed by Productivity domain
PRIVILEGE         - Non-counted state (e.g., seat selection); expires by revocation only
INSURANCE         - Recurring premium liability (coordinates with Obligations)
COLLECTIVE_GOAL   - Threshold/deadline purchase (group goal completion)
```

### C. Optional Fields

```json
{
  "limit_per_student": <integer | null>,
  "auto_expiry_days": <integer | null>,
  "name": <string | null>,
  "description": <string | null>,
  "tier": <string | null>,
  "bypass_cwi_warnings": <boolean>,
  "is_long_term_goal": <boolean>,
  "bundle_quantity": <integer | null>,
  "bulk_discount_quantity": <integer | null>,
  "bulk_discount_percentage": <float | null>,
  "collective_goal_type": <string | null>,
  "collective_goal_target": <integer | null>,
  "collective_goal_expires_at": <ISO8601 datetime | null>
}
```

**Field Definitions:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `limit_per_student` | int \| null | Max purchasable per student | If set, must be > 0; null = unlimited |
| `auto_expiry_days` | int \| null | Days until entitlement expires | If set, must be > 0; null = never expires |
| `name` | string \| null | Display name (UI only) | Max 100 chars; informational only |
| `description` | string \| null | Product description (UI only) | Informational only |
| `tier` | string \| null | Organizational category | Values: "basic", "standard", "premium", "luxury" |
| `bypass_cwi_warnings` | boolean | Override CWI balance warnings? | Default: false |
| `is_long_term_goal` | boolean | Exclude from CWI balance checks? | Default: false |
| `bundle_quantity` | int \| null | Items in bundle | If set, must be > 1; mutually exclusive with collective_goal |
| `bulk_discount_quantity` | int \| null | Min quantity for discount | If set, must be > 1 |
| `bulk_discount_percentage` | float \| null | Discount percentage | Range: 0-100; paired with bulk_discount_quantity |
| `collective_goal_type` | string \| null | Goal threshold type | Values: "fixed" or "whole_class"; mutually exclusive with bundle fields |
| `collective_goal_target` | int \| null | Required purchases for goal | If set, must be > 0; requires collective_goal_type and collective_goal_expires_at |
| `collective_goal_expires_at` | datetime \| null | Deadline for goal completion | ISO8601 format; required if collective_goal_type is set |

## V. Validation Rules

### A. Type-Specific Rules

**IMMEDIATE_USE:**
- `auto_expiry_days` MUST be null (or will be ignored)
- `limit_per_student` optional
- Cannot be bundled or part of collective goal

**DELAYED_USE:**
- `auto_expiry_days` optional but recommended (null = perpetual entitlement)
- `limit_per_student` optional
- Cannot be bundled or part of collective goal

**HALL_PASS:**
- `supports_direct_grants` MUST be true
- `auto_expiry_days` optional
- `limit_per_student` optional
- Cannot be bundled or part of collective goal

**PRIVILEGE:**
- `auto_expiry_days` MUST be null (expires by revocation only)
- `limit_per_student` optional
- `supports_direct_grants` MUST be true
- Cannot be bundled or part of collective goal

**INSURANCE:**
- Recurring premium product
- `price` is per premium cycle
- `auto_expiry_days` typically null (managed by Obligations bill cycles)
- `limit_per_student` typically null or 1
- Additional insurance-specific fields (see SPEC-OBL-001)

**COLLECTIVE_GOAL:**
- `collective_goal_type` MUST be set ("fixed" or "whole_class")
- `collective_goal_target` MUST be > 0
- `collective_goal_expires_at` MUST be valid future datetime
- Bundle fields MUST all be null
- Cannot coexist with bundle/bulk discount

### B. Mutual Exclusion Rules

1. **Bundle XOR Collective Goal**
   - If any of `bundle_quantity`, `bulk_discount_quantity`, `bulk_discount_percentage` is set, all collective_goal fields MUST be null
   - If any collective_goal field is set, all bundle fields MUST be null

2. **Collective Goal Completeness**
   - If `collective_goal_type` is set, both `collective_goal_target` and `collective_goal_expires_at` MUST be set
   - If only some collective_goal fields are set, validation fails

### C. Value Range Rules

1. **Price:** Must be ≥ 0 (Decimal with 2 scale)
2. **limit_per_student:** If set, must be > 0
3. **auto_expiry_days:** If set, must be > 0
4. **bundle_quantity:** If set, must be > 1
5. **bulk_discount_quantity:** If set, must be > 1
6. **bulk_discount_percentage:** If set, must be in range [0, 100]
7. **collective_goal_target:** If set, must be > 0
8. **collective_goal_expires_at:** If set, must be a valid future datetime

## VI. Example Payloads

### Example 1: Simple Delayed-Use Hall Pass

```json
{
  "product_id": 101,
  "is_purchasable": true,
  "supports_direct_grants": true,
  "price": "50.00",
  "entitlement_type": "DELAYED_USE",
  "name": "Hall Pass - Bathroom",
  "description": "Valid for 30 days",
  "auto_expiry_days": 30,
  "tier": "basic"
}
```

### Example 2: Immediate-Use Privilege

```json
{
  "product_id": 102,
  "is_purchasable": true,
  "supports_direct_grants": true,
  "price": "75.00",
  "entitlement_type": "PRIVILEGE",
  "name": "Seat Selection",
  "description": "Choose your own seat for one term",
  "limit_per_student": 1
}
```

### Example 3: Collective Goal Product

```json
{
  "product_id": 103,
  "is_purchasable": true,
  "supports_direct_grants": false,
  "price": "25.00",
  "entitlement_type": "COLLECTIVE_GOAL",
  "name": "Class Pizza Party",
  "collective_goal_type": "fixed",
  "collective_goal_target": 50,
  "collective_goal_expires_at": "2026-08-31T23:59:59Z",
  "description": "50 purchases triggers class pizza party"
}
```

### Example 4: Bulk Discount Product

```json
{
  "product_id": 104,
  "is_purchasable": true,
  "supports_direct_grants": false,
  "price": "10.00",
  "entitlement_type": "DELAYED_USE",
  "name": "Homework Pass",
  "auto_expiry_days": 60,
  "bulk_discount_quantity": 5,
  "bulk_discount_percentage": 15.0,
  "description": "Buy 5+ for 15% discount"
}
```

## VII. Parser Contract

### Input

A JSON object (dict) from `policy_version.payload`

### Output

A typed `StoreProductConfig` object with validated fields

### Exceptions

| Condition | Exception Type | Message |
|-----------|----------------|---------|
| Required field missing | `ValueError` | "Required field {name} missing" |
| Invalid entitlement_type | `ValueError` | "Invalid entitlement_type: {value}" |
| Invalid combination | `ValueError` | "Invalid combination: {reason}" |
| Price negative | `ValueError` | "Price cannot be negative" |
| Type mismatch | `TypeError` | "Field {name} must be {type}, got {actual_type}" |

## VIII. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-28 | Initial specification |

## IX. Amendment

Changes to this specification require:

1. Update this document with new version number and effective date
2. Update all consuming code to handle new or changed fields
3. Add migration guidance if existing policies must be upgraded
4. Update related domain specs (DOM-STORE-001, SPEC-OBL-001, etc.)

