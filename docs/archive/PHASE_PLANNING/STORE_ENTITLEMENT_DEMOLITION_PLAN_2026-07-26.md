# Store/Entitlements Domain Demolition Plan
## Phase 9 Execution: Legacy Deletion

> Historical plan note: this document describes the pre-closeout deletion target set from 2026-07-26. The current live-tree Store closure state is summarized in `docs/TRACKING/STORE_ENTITLEMENT_PHASE6_SURFACE_INVENTORY_2026-07-31.md`, and the remaining references in this plan are archival unless explicitly revalidated against current code.
| Reference | Value |
|-----------|-------|
| **Domain** | Store and Entitlements (DOM-STORE-001 v3.0) |
| **Phase** | 9 — Legacy Deletion (SOP-DEV-002) |
| **Execution Date** | 2026-07-26 |
| **Prior Audit** | STORE_ENTITLEMENT_DOMAIN_CORRECTNESS_AUDIT_2026-07-26.md |

---

## Demolition Targets

### A. Forbidden Tables & Models (Delete Entirely)

**Table 1: store_purchases**
- Model: `app/models.py` — StorePurchase class (lines 867-889)
- Reason: DOM-STORE-001 §VI forbidden persistence
- Disposition: Collapse into Entitlements + Ledger transactions
- Dependencies: Route queries, deletion utilities, tests

**Table 2: redemption_events**
- Model: `app/models.py` — RedemptionEvent class (lines 902-937)
- Model: `app/models.py` — RedemptionEventAction enum (lines 892-895)
- Model: `app/models.py` — RedemptionEventSource enum (lines 898-900)
- Reason: DOM-STORE-001 §VI forbidden, §XIX disposition says delete
- Disposition: Replace with EntitlementConsumption + InsuranceClaim workflows
- Dependencies: derive_display_status() function, tests

**Table 3: entitlement_events** ⚠️ CONDITIONAL
- Model: `app/models.py` — EntitlementEvent class (lines 1191-1210)
- Reason: Mutable balance tracking via quantity_delta violates §IV
- Disposition: Move hall-pass entitlements to canonical Entitlement + EntitlementConsumption
- OR: Move to Productivity domain if hall passes are productivity-owned
- Dependencies: entitlement_service.py grant/consume/balance functions

---

## Demolition Sequence

### Phase 1: Identify All References (Read-Only)

For each table, find all code paths that reference it:
1. Direct ORM queries (Model.query.filter)
2. Imports in other modules
3. Route handlers
4. Service functions
5. Test fixtures
6. Migration files

### Phase 2: Delete Route & Service References

Remove code that creates/reads/deletes these tables:
1. Direct db.session operations in routes
2. Helper functions that bypass canonical FEATs
3. Bridge compatibility code

### Phase 3: Delete Models & Enums

1. Remove class definitions from models.py
2. Remove backref relationships
3. Remove any @event.listens_for decorators

### Phase 4: Historical Migration Record

1. Preserve the applied migration history as an archive of the original demolition target set
2. Do not delete revision history that has already been applied to deployed environments
3. Verify only that the archived chain description still matches the historical closeout record

### Phase 5: Delete Tests

1. Remove test files that only test legacy tables
2. Remove test fixtures that create these tables
3. Update tests that reference these objects

### Phase 6: Verify Cleanup

1. Run grep to ensure no orphaned imports
2. Run pytest to verify no import errors
3. Check migration heads are valid

---

## Demolition Checklist

- [ ] Create complete reference inventory
- [ ] Delete StorePurchase references from routes
- [ ] Delete RedemptionEvent references from services
- [ ] Delete EntitlementEvent handling from entitlement_service
- [ ] Delete model classes
- [ ] Delete/rollback migrations
- [ ] Delete orphaned tests
- [ ] Verify import chain
- [ ] Run full test suite
- [ ] Commit demolition changes

---

## Expected Files to Modify/Delete

### models.py
- Remove StorePurchase class
- Remove RedemptionEvent class
- Remove RedemptionEventAction enum
- Remove RedemptionEventSource enum
- Remove EntitlementEvent class (or move to another domain)

### services/entitlement_service.py
- Replace get_hall_pass_balance() (uses EntitlementEvent)
- Replace grant_hall_passes() (creates EntitlementEvent)
- Replace remove_hall_passes() (creates EntitlementEvent)
- Replace consume_hall_pass() (creates EntitlementEvent)
- Delete _available_hall_pass_grant() helper

### services/store_entitlement_service.py
- Remove RedemptionEvent queries from derive_display_status()
- Simplify terminal event derivation

### routes/admin.py
- Remove StorePurchase queries
- Remove RedemptionEvent handling if any

### routes/api.py
- Remove StorePurchase queries

### utils/deletion.py
- Remove StorePurchase deletion logic

### utils/student_deletion.py
- Remove StorePurchase deletion logic

### migrations/versions/
- Delete or rollback migrations creating these tables

---

## Execution Steps (To Follow)

1. ✋ **STOP HERE** — User provides confirmation to proceed
2. Create complete reference inventory (grep all files)
3. Delete forbidden code in execution order
4. Run incremental tests
5. Final verification
