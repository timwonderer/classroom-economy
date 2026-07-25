# STORE Domain End-to-End Audit Instruction

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-STORE-001 | 1.0 | 2026-07-23 | QA/Review | [TBD] |

---

## Purpose

This audit validates that the Store and insurance surfaces have been rewired to the canonical v2 architecture and that the class-configuration insurance editor now aligns with the broader STORE rewire.

This is a strict checklist. Treat the route/template audit as the checklist source. Do not use discovery to invent new scope.

**Outcome:** either `AUDIT PASS` or `AUDIT FAIL` with explicit findings, evidence, and missing items.

---

## Pre-Audit Setup

### 1. Branch and Environment
- [ ] Checked out the target audit branch
- [ ] Database migrated to current head
- [ ] Test database initialized and accessible
- [ ] Working tree clean before audit begins

### 2. Read Authoritative Documents
Read these in order before starting the audit:

- [ ] `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- [ ] `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-CLASS-003_INSURANCE_POLICY_MANAGEMENT.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md`
- [ ] `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-CORE-000_CORE_INVARIANTS.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_REQUEST_HANDLER_AUTHORITY_AND_SIDE_EFFECT_BOUNDARIES.md` if present in the tree

---

## Part A: Schema and Data Model Audit

### A1: Canonical Store/Entitlement Tables
Verify the domain owns the current canonical tables and no retired persistence is treated as authority.

- [ ] `entitlements`
- [ ] `entitlement_consumptions`
- [ ] `insurance_claims`

Check for retired or forbidden authority-bearing fields/patterns:

- [ ] no mutable entitlement balance columns
- [ ] no `uses_remaining`
- [ ] no `bundle_remaining`
- [ ] no purchase quantity used as entitlement truth
- [ ] no direct Store ownership of class configuration
- [ ] no direct Ledger ownership leaks into Store rows

### A2: Insurance Policy Configuration Tables
Verify class configuration owns insurance policy lineage and versioning.

- [ ] `policy_versions`
- [ ] `policy_transitions`

Check that insurance configuration is class-owned and versioned:

- [ ] `entitlement_item_id` mapping is present on policy lineage
- [ ] versioned terms are stored in policy payload/lineage
- [ ] downstream entitlement, obligation, and ledger tables are not rewritten to represent policy edits

### A3: Required Table Checks
Use schema inspection against the current database to confirm:

- [ ] `entitlements` is append-only grant history
- [ ] `entitlement_consumptions` is append-only terminal lifecycle history
- [ ] `insurance_claims` is a mutable claim workflow table, not an entitlement store
- [ ] `policy_versions` / `policy_transitions` are the only class-side insurance lineage tables

---

## Part B: FEAT Layer Audit

### B1: FEAT-STOR-001
Audit the purchase-and-grant path.

- [ ] `FEAT-STOR-001` is the only lawful writer for purchase-origin `grant_type = PURCHASE`
- [ ] purchase creates one entitlement row per purchased unit
- [ ] quantity does not become entitlement balance authority
- [ ] insurance purchase uses configured entitlement mapping and canonical purchase orchestration
- [ ] Ledger posting remains through the lawful Ledger boundary

### B2: FEAT-STOR-002
Audit entitlement terminal lifecycle.

- [ ] `FEAT-STOR-002` is the only lawful writer for Store-owned terminal lifecycle rows
- [ ] `CONSUMED`, `EXPIRED`, and `REVOKED` are the only terminal dispositions
- [ ] insurance claims do not create entitlement terminal events
- [ ] hall-pass consumption is owned by the Productivity/Payroll domain and does not duplicate Store terminal rows
- [ ] insurance entitlements are non-revocable after lawful purchase

### B3: FEAT-STOR-003
Audit insurance claim lifecycle.

- [ ] claim submission creates `SUBMITTED`
- [ ] claim decision transitions are forward-only
- [ ] transaction claims route compensatory credit through Ledger
- [ ] productivity claims route `MANUAL_CREDIT` through Payroll, then Ledger
- [ ] claim submission does not consume entitlement
- [ ] cancellation of the offering does not invalidate existing active coverage

### B4: FEAT-CLASS-003
Audit insurance policy management.

- [ ] policy create, edit, inactivate, delete scheduling, and switching are class-configuration operations
- [ ] policy edits create a new prospective version
- [ ] switching is limited to the same tier group
- [ ] bundle eligibility honors grouped tiers as a whole
- [ ] deletion is scheduled from the last currently enforced entitlement boundary
- [ ] policy changes emit persistent student-visible banners
- [ ] class-config changes do not mutate entitlement, obligation, or ledger tables directly

---

## Part C: Route Wiring Audit

Use `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` as the checklist source. For each row marked `REWIRED` or still pending, verify the actual code and template contract.

### C1: Store Dashboard Read Model
File: `app/routes/admin.py` and `templates/admin_store.html`

- [ ] route uses canonical store read model data
- [ ] pending redemptions are derived from canonical redemption workflow rows
- [ ] recent purchases are derived from entitlement or purchase lineage as defined by the current domain contract
- [ ] template fields match the route view model
- [ ] no stale `StorePurchase` attribute assumptions remain in the template
- [ ] GET path has no side effects and no legacy FEAT wrapper leak

### C2: Store Item Management
Files: `app/routes/admin.py`, `templates/admin_store.html`, `templates/admin_edit_item.html`

- [ ] create/edit/deactivate actions are class-configuration writes
- [ ] deactivation hides items from new purchases without mutating unrelated domain records
- [ ] store catalog views read class configuration, not store-owned configuration rows

### C3: Store Purchase and Redemption
Files: `app/routes/api.py`, `app/routes/student.py`, `templates/student_shop.html`, `templates/admin_store.html`

- [ ] purchase route calls `FEAT-STOR-001`
- [ ] item use route calls `FEAT-STOR-002`
- [ ] approval writes authoritative terminal consumption only when appropriate
- [ ] rejection preserves entitlement
- [ ] student shop view model matches the template contract

### C4: Insurance Marketplace and Purchase
Files: `app/routes/student.py`, `templates/student_insurance_marketplace.html`

- [ ] marketplace renders class-scoped insurance offerings
- [ ] insurance purchase uses canonical entitlement-backed purchase orchestration
- [ ] group/tier data are represented consistently with class configuration
- [ ] no direct mutation of insurance configuration leaks into entitlement rows

### C5: Insurance Claim and Policy Views
Files: `app/routes/student.py`, `app/routes/admin.py`, `templates/student_file_claim.html`, `templates/student_view_policy.html`, `templates/admin_process_claim.html`, `templates/admin_view_student_policy.html`

- [ ] student claim submission uses canonical claim lifecycle
- [ ] student policy view derives from entitlement plus claim lineage
- [ ] teacher claim decision surface matches `FEAT-STOR-003`
- [ ] policy view and claim view render from canonical lineages and not legacy models

### C6: Insurance Policy Management
Files: `app/routes/admin.py`, `templates/admin_insurance.html`, `templates/admin_edit_insurance_policy.html`

- [ ] insurance editor uses `FEAT-CLASS-003`
- [ ] edit creates new prospective version
- [ ] deactivate makes policy unavailable for new enrollment
- [ ] delete schedules hard deletion using entitlement end boundary
- [ ] notification banners are persistent until dismissed

---

## Part D: Template Audit

For each audited surface, confirm that the rendered template only dereferences fields that exist on the current view model.

- [ ] `admin_store.html`
- [ ] `admin_insurance.html`
- [ ] `admin_edit_insurance_policy.html`
- [ ] `student_shop.html`
- [ ] `student_insurance_marketplace.html`
- [ ] `student_file_claim.html`
- [ ] `student_view_policy.html`
- [ ] `admin_process_claim.html`
- [ ] `admin_view_student_policy.html`

Required checks:

- [ ] no template reads of retired fields
- [ ] no template reliance on stale row shapes
- [ ] no template-side reconstruction of authority
- [ ] no hidden assumptions about legacy purchase or claim models
- [ ] all action forms point at the current route surface

---

## Part E: Completion Criteria

The audit passes only if all of the following are true:

- [ ] the MAP checklist rows for STORE and insurance surfaces are either `REWIRED` or explicitly justified as pending
- [ ] the current code matches the authority and persistence model in the canonical docs
- [ ] no stale template row shapes remain on audited surfaces
- [ ] no direct domain boundary violations remain in the audited paths
- [ ] all findings are documented with exact file, route, and template references

If any requirement is not proven by current evidence, mark `AUDIT FAIL` and record the specific missing proof.
