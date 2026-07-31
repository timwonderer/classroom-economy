# Store/Entitlements Phase 6 Surface Inventory

| Reference | Value |
|---|---|
| **Domain** | Store and Entitlements |
| **Phase** | SOP-DEV-002 Phase 6: Application Surface Inventory |
| **Date** | 2026-07-31 |
| **Source Map** | `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` |
| **Scope** | Remaining Store/Entitlement application surfaces still carrying legacy persistence or unresolved FEAT wiring |

---

## I. Purpose

This inventory is the Phase 6 bridge between the current surface map and the remaining Store/Entitlement demolition work.

It does not rewire routes. It identifies which current surfaces are:

- `REWIRE` - move to canonical FEAT / read paths
- `REMOVE` - delete legacy surface usage
- `COLLAPSE` - reduce to canonical read helper or resolver
- `VERIFY` - already aligned, but needs explicit revalidation

---

## II. Current Store/Entitlement Surface State

### A. Already Rewired or Verified

These are already represented in MAP-UI-001 as rewired surfaces and were confirmed in the live tree:

- `student_shop.html` browse/purchase surface
- `admin_store.html` store management surface
- direct purchase / grant / redemption FEAT paths
- insurance marketplace and claim entry surfaces

### B. Remaining Legacy Runtime References

These runtime references were present when the inventory was first written, but the current live tree has already removed the StorePurchase / RedemptionEvent / quantity_delta runtime paths. What remains here is historical tracking residue and doc reconciliation:

#### 1. `app/routes/admin.py`

Historical references noted in the inventory:

- `StorePurchase`
- `RedemptionEvent`
- `RedemptionEventAction`
- `RedemptionEventSource`

Observed usage clusters:

- store item deletion / cleanup
- student purchase history and active purchase lookups
- redemption audit and admin queue logic

Disposition:

- Verified clean in current runtime tree; retain only historical comments and doc references

#### 2. `app/routes/api.py`

Historical references noted in the inventory:

- `StorePurchase`
- `RedemptionEventAction`
- bridge purchase lookup logic

Observed usage clusters:

- purchase endpoint bridge compatibility
- redemption action translation
- hall-pass request helpers that still import older store-side concepts

Disposition:

- Verified clean in current runtime tree; retain only historical comments and doc references

#### 3. `app/services/entitlement_service.py`

Historical references noted in the inventory:

- `EntitlementEvent`
- hall-pass grant / removal / consume helpers

Observed usage clusters:

- hall-pass balance derivation
- hall-pass grant and consume mutation

Disposition:

- Verified clean in current runtime tree; hall-pass helpers now align with canonical EntitlementEvent lineage and read-service balance derivation

#### 4. `app/services/store_service.py`

Current runtime references are class-scoped catalog helpers, not StorePurchase/RedemptionEvent runtime paths:

- `StoreItem`
- `StoreItemVisibility`
- store catalog CRUD helpers

Observed usage clusters:

- item catalog definition
- rent-linked item helpers

Disposition:

- catalog CRUD helpers -> `VERIFY` against class-configuration authority
- rent-linked item helpers -> `COLLAPSE` into canonical class-config / policy reads

#### 5. `app/services/view_model_builders.py`

Current runtime references include:

- `EntitlementEvent`

Observed usage clusters:

- entitlement list view
- purchase history view

Disposition:

- `VERIFY` for Phase 5 read purity
- no immediate route rewiring required until Phase 7

---

## III. Outstanding Contract Gaps

### 1. `list_store_policies(class_id)`

Status:

- discovery primitive exists
- resolver is pure
- policy list view is unblocked and now consumes the canonical discovery payload

Disposition:

- `VERIFY` for resolver purity
- `VERIFY` policy list view against the Phase 5 builder contract

### 2. `pending_actions`

Status:

- canonical persistence exists
- no current mutation surface was identified in the live Store/Entitlement runtime path
- pending-action workflows are separately documented and still need their own FEAT contracts before mutation rewiring

Disposition:

- `VERIFY`
- no Store/Entitlement route rewiring until FEAT authority is explicit

---

## IV. Phase 6 Surface Disposition Table

| Surface | Status | Next Action |
|---|---|---|
| `app/routes/admin.py` legacy `StorePurchase` queries | `REMOVE` | Delete store-purchase references and collapse to entitlement reads |
| `app/routes/admin.py` legacy `RedemptionEvent` audit flows | `REMOVE` / `COLLAPSE` | Replace with canonical entitlement consumption and approved workflow reads |
| `app/routes/api.py` bridge purchase lookup | `REMOVE` | Require exact `policy_uuid` / canonical FEAT input only |
| `app/services/entitlement_service.py` hall-pass balance math | `VERIFY` | Confirm helpers remain aligned to canonical EntitlementEvent lineage and read-service balance derivation |
| `app/services/store_service.py` catalog CRUD helpers | `VERIFY` | Confirm whether helpers are only class-config surfaces or need removal |
| `app/services/view_model_builders.py` read builders | `VERIFY` | Keep pure; no route rewiring in Phase 6 |
| `StorePolicyResolver.list_store_policies(class_id)` | `VERIFY` | Contract is pure and now feeds the Phase 5 discovery view model |
| `PolicyListView` | `VERIFY` | Implemented as pure discovery + presentation ordering |

---

## V. Immediate Next Step

The remaining Store work is no longer a map-discovery problem. It is a demolition/reconciliation problem:

1. Reconcile the remaining historical StorePurchase / RedemptionEvent references in docs and comments.
2. Revalidate the store map against the live tree after any additional doc cleanup and confirm the remaining `VERIFY` surfaces are still accurate.

This inventory is the authoritative Phase 6 handoff for the remaining Store closure work.
