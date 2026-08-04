# Store/Entitlements Domain Phase 2: Persistence Migration
## Historical Record of the Canonical Schema Cutover

| Reference | Value |
|-----------|-------|
| **Phase** | 2 — Persistence (SOP-DEV-002) |
| **Authority** | DOM-STORE-001 v3.0 (effective 2026-07-22) |
| **Migration Date** | 2026-07-26 |
| **Prior Phase** | Phase 0-1 (Boundary + Truth completed) |
| **Next Phase** | Phase 3 (Primitives/Services) |

---

## I. Migration Scope

This document is a historical cutover note. The canonical event-based schema was implemented by migration `4aa06b69d65d_rebuild_store_entitlements_phase2.py`.

### New Tables Created

**1. entitlement_events** (replaces: entitlements + entitlement_consumptions + redemption_events + entitlement_events)

```sql
CREATE TABLE entitlement_events (
  event_id CHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
  class_id VARCHAR(36) NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
  entitlement_id CHAR(36) NOT NULL,  -- stable lineage across lifecycle
  target_seat_id INTEGER NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
  actor_seat_id INTEGER NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
  product_id INTEGER NULL,  -- references Policy-owned product; nullable for cross-domain compatibility
  entitlement_type VARCHAR(50) NOT NULL,  -- INSURANCE, PRIVILEGE, IMMEDIATE_USE, DELAYED_USE, COLLECTIVE_GOAL, HALL_PASS
  acquisition_type VARCHAR(20) NOT NULL,  -- PURCHASE, GRANT, PERK
  event_type VARCHAR(20) NOT NULL,  -- GRANTED, CONSUMED, EXPIRED, REVOKED
  correlation_id VARCHAR(200),  -- cross-domain lineage
  payload JSONB,  -- type-specific canonical facts
  timestamp TIMESTAMP WITH TIMEZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes for common queries
  INDEX ix_entitlement_events_class (class_id),
  INDEX ix_entitlement_events_entitlement_id (entitlement_id),
  INDEX ix_entitlement_events_seat_class (target_seat_id, class_id),
  INDEX ix_entitlement_events_correlation (correlation_id),
  INDEX ix_entitlement_events_type (event_type),
  UNIQUE (entitlement_id, event_type) IF event_type IN ('EXPIRED', 'REVOKED')  -- single terminal event per type
);
```

**2. pending_actions** (replaces: redemption_events REQUEST/APPROVED/REJECTED workflow)

```sql
CREATE TABLE pending_actions (
  pending_action_id CHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
  class_id VARCHAR(36) NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
  seat_id INTEGER NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
  entitlement_id CHAR(36) NOT NULL,  -- references entitlement_events
  correlation_id VARCHAR(200) NOT NULL UNIQUE,  -- identifies the action lifecycle
  authoritative_feat VARCHAR(100) NOT NULL,  -- FEAT-STOR-002, FEAT-STOR-003, etc.
  payload JSONB NOT NULL,  -- typed request envelope validated by submitting FEAT
  submitted_at TIMESTAMP WITH TIMEZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes for common queries
  INDEX ix_pending_actions_class (class_id),
  INDEX ix_pending_actions_seat (seat_id),
  INDEX ix_pending_actions_entitlement (entitlement_id),
  INDEX ix_pending_actions_correlation (correlation_id),
  INDEX ix_pending_actions_feat (authoritative_feat)
);
```

### Legacy Tables During the Cutover

The cutover originally retained legacy tables for validation, then the live tree moved beyond them:

- `entitlements`
- `entitlement_consumptions`
- `redemption_events`
- `store_purchases`
- the old mutable `entitlement_events` hall-pass table

---

## II. Data Migration Strategy

### A. No Data Preservation Required (Rebuild Semantics)

Since this is a complete paradigm shift from grant+consumption to event-based history:

1. **Old entitlements + consumptions** → Convert to new event-based rows (if preserving history)
2. **Old hall-pass entitlement_events** → Delete (mutable balance model is forbidden)
3. **Old redemption_events** → Delete (replaced by event_type in new model)
4. **Old store_purchases** → Delete (no quantity persistence in new model)

### B. Recommended Migration Approach

**Option 1: Clean Break (Safest for New Model)**
- Create new empty tables
- Run Phase 3-7 with new code using new tables
- Validate everything works
- Delete old tables in Phase 9 (legacy deletion)
- No data migration complexity

**Option 2: Historical Reconstruction (If Audit Trail Required)**
- Create new tables
- Migrate grant+consumption rows → entitlement_events GRANTED + CONSUMED
- Migrate hall-pass balance state → entitlement_events GRANTED (with reconstruction)
- Migrate redemption workflow → entitlement_events (CONSUMED/REVOKED)
- Requires careful correlation/payload mapping
- More complex, higher risk

**Recommendation:** Go with **Option 1 (Clean Break)** only if the deployment has explicit approval for destructive data disposition because:
- Old tables had mutable balance tracking (forbidden per spec)
- Migration would require inferring historical state that wasn't properly recorded
- New paradigm is fundamentally different (events, not grant+consumption split)
- Safer to start fresh with new canonical tables

---

## III. Migration Execution Plan

### Step 1: Create New Tables (Non-Destructive)

Create idempotent migration that:
- ✅ Checks if tables exist before creating
- ✅ Creates `entitlement_events` table with proper schema
- ✅ Creates `pending_actions` table with proper schema
- ✅ Adds proper indexes and constraints
- ✅ Includes full rollback capability

### Step 2: Verify Schema

- [ ] Check table structure matches spec
- [ ] Verify foreign keys to classes and seats
- [ ] Verify indexes exist
- [ ] Verify JSONB columns work
- [ ] Test insert/select on new tables

### Step 3: Legacy Tables Were Later Removed

- [x] Old `entitlements` table preserved during the cutover window
- [x] Old `entitlement_consumptions` table preserved during the cutover window
- [x] Old `redemption_events` table preserved during the cutover window
- [x] Old `entitlement_events` table removed with the canonical cutover
- [x] Old `store_purchases` table removed in the later demolition pass

### Step 4: Update Models

- [x] Add new `EntitlementEvent` model (event-based, different from old)
- [x] Add new `PendingAction` model
- [x] Keep old models for temporary validation
- [x] Mark old models with deprecation comments

---

## IV. Implementation Tasks

### A. Create Migration File

File: `migrations/versions/<timestamp>_rebuild_store_entitlements_canonical_schema.py`

Requirements:
- Copy idempotency helpers from `migrations/migration_template.py.mako`
- Add functions: `column_exists()`, `table_exists()`, `index_exists()`, `foreign_key_exists()`
- Upgrade: Create both tables with all constraints
- Downgrade: Drop both tables and restore old state
- Include comments explaining Phase 2 purpose

### B. Add Models to models.py

**New EntitlementEvent model (event-based):**
```python
class EntitlementEvent(db.Model):
    """Event-based immutable entitlement history — DOM-STORE-001 v3.0 §VII.A
    
    One row per atomic event: GRANTED, CONSUMED, EXPIRED, REVOKED
    Replaces: old entitlements + entitlement_consumptions + hall-pass tracking
    """
    __tablename__ = 'entitlement_events'
    
    event_id = db.Column(db.String(36), primary_key=True, ...)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), ...)
    entitlement_id = db.Column(db.String(36), nullable=False, index=True)  # stable lineage
    target_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), ...)
    actor_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), ...)
    product_id = db.Column(db.Integer, nullable=True)  # references Policy-owned product
    entitlement_type = db.Column(db.String(50), nullable=False)  # INSURANCE, PRIVILEGE, etc.
    acquisition_type = db.Column(db.String(20), nullable=False)  # PURCHASE, GRANT, PERK
    event_type = db.Column(db.String(20), nullable=False, index=True)  # GRANTED, CONSUMED, EXPIRED, REVOKED
    correlation_id = db.Column(db.String(200), nullable=True, index=True)
    payload = db.Column(db.JSON, nullable=True)  # type-specific facts
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
```

**New PendingAction model:**
```python
class PendingAction(db.Model):
    """Unresolved entitlement action — DOM-STORE-001 v3.0 §VII.B
    
    Holds pending insurance claims and other actions awaiting resolution.
    """
    __tablename__ = 'pending_actions'
    
    pending_action_id = db.Column(db.String(36), primary_key=True, ...)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), ...)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), ...)
    entitlement_id = db.Column(db.String(36), nullable=False, index=True)
    correlation_id = db.Column(db.String(200), nullable=False, unique=True, index=True)
    authoritative_feat = db.Column(db.String(100), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
```

### C. Verify Migration Chain

```bash
flask db heads  # Must show exactly 1 head
flask db migrate  # Auto-detect schema changes (for review)
flask db upgrade  # Apply migration
flask db downgrade  # Test rollback
flask db upgrade  # Re-apply
pytest tests/  # Verify no import errors
```

---

## V. Testing Phase 2 Migration

### Unit Tests

- [ ] New tables exist in test database
- [ ] Columns have correct types and constraints
- [ ] Foreign keys are enforced
- [ ] Indexes are created
- [ ] JSONB columns accept valid JSON
- [ ] Migration is idempotent (upgrade then downgrade then upgrade = same state)

### Integration Tests

- [ ] Models can be imported without errors
- [ ] Old models still work (for validation phase)
- [ ] New models can insert test rows
- [ ] Queries on new tables return correct data

---

## VI. Rollback Plan

If Phase 2 migration fails:

```bash
# Rollback
flask db downgrade

# Verify old state
flask db current

# Check old tables still exist
psql classroom_economy -c "\dt"
```

---

## VII. Deliverables

After Phase 2 completion:

- ✅ Migration file: `migrations/versions/<timestamp>_rebuild_store_entitlements_canonical_schema.py`
- ✅ New models in `app/models.py`: `EntitlementEvent`, `PendingAction`
- ✅ Updated migration chain (single head)
- ✅ All tests pass with new schema
- ✅ Old tables preserved for Phase 9 cleanup

---

## VIII. Next Steps (Phase 3-4)

After Phase 2 migration succeeds:

1. **Phase 3 - Primitives:** Implement read/write service methods for new tables
2. **Phase 4 - Mutation Boundary:** Implement FEAT-STOR-001/002/003/004 with new schema
3. **Phase 5 - Read Models:** Build immutable view models from new event history
4. **Phase 6-7 - Surface/Rewire:** Update routes to use new FEATs
5. **Phase 8 - Verify:** Run full test suite
6. **Phase 9 - Legacy Deletion:** Delete old tables and code
7. **Phase 10 - Audit:** Certification audit

---

**Status:** Completed historical record  
**Evidence:** Applied migration `e13a59b6aa6b_add_store_products_table.py` and the canonical event-based model cutover in the live tree
