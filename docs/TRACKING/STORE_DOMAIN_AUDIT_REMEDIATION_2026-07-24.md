# STORE Domain Audit Remediation

Date: 2026-07-24

This document records code remediations applied in response to
[`STORE_DOMAIN_AUDIT_REPORT_2026-07-23.md`](./STORE_DOMAIN_AUDIT_REPORT_2026-07-23.md).
The audit report remains unchanged and is treated as the failure ledger.

## Authority

The fixes below were applied under the following canonical documents:

- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CLASS-003_INSURANCE_POLICY_MANAGEMENT.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_REQUEST_HANDLER_AUTHORITY_AND_SIDE_EFFECT_BOUNDARIES.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`

## Remediated Findings

### F3 - Insurance purchase lacked a FEAT boundary

Code changed:

- `app/feats/insurance_purchase_feat.py`

What changed:

- Added `@feat_shell("FEAT-STOR-001")` to `execute_insurance_purchase`.
- The insurance purchase path is now authored through the Store FEAT boundary instead of an unguarded service entry point.

Authority used:

- FEAT-STOR-001 for store purchase orchestration.
- INV-ARC-007 for handler/service side-effect boundaries.

### F5 - Entitlement terminal lifecycle lacked FEAT gating

Code changed:

- `app/services/store_entitlement_service.py`

What changed:

- Added `@feat_shell("FEAT-STOR-002")` to `revoke_entitlement` and `expire_entitlement`.
- Preserved terminal lifecycle writes behind the canonical Store FEAT boundary.

Authority used:

- FEAT-STOR-002 for entitlement terminal lifecycle.
- INV-ARC-016 for lawful terminal facts.

### F6 - Insurance entitlements could be revoked through the wrong path

Code changed:

- `app/services/store_entitlement_service.py`

What changed:

- Added a guard in `revoke_entitlement` that rejects insurance-linked entitlements.
- Insurance entitlements now fail closed with a clear error if they are routed through the wrong lifecycle command.

Authority used:

- DOM-STORE-001 for domain ownership of terminal lifecycle facts.
- FEAT-STOR-002 for non-insurance terminal lifecycle handling.

### F1 - Claim approval did not produce a compensatory ledger credit

Code changed:

- `app/feats/insurance_claim_feat.py`

What changed:

- `execute_claim_approval` now creates a pending reimbursement transaction when approving a transaction-based monetary claim.
- The approval result remains FEAT-owned and the reimbursement is recorded as a ledger write instead of only changing the claim status message.
- The same approval path now also branches for productivity claims and coordinates a `manual_credit` payroll event through FEAT-PROD-003 when the claim type is productivity.

Authority used:

- FEAT-STOR-003 for claim lifecycle orchestration.
- INV-ARC-007 for FEAT-owned state mutation.
- Ledger domain authority for monetary compensation writes.

### F2 - Claim type resolution rejected valid non-transaction claim types too early

Code changed:

- `app/utils/insurance_eligibility.py`
- `app/feats/insurance_claim_feat.py`

What changed:

- Added canonical support for the `productivity` claim type in claim-type resolution.
- Claim approval now lets the resolved claim type flow through to the lifecycle branch instead of blocking productivity claim handling at resolution time.

Authority used:

- FEAT-STOR-003 for claim lifecycle dispatch.
- DOM-STORE-001 for claim domain behavior.

### F13 - Hall-pass redemption bypassed terminal consumption writes

Code changed:

- `app/routes/api.py`

What changed:

- The hall-pass inventory redemption early exit now calls `consume_entitlement(...)` before marking the purchase as redeemed.
- The redemption path now writes the entitlement terminal fact instead of only updating purchase status.

Authority used:

- FEAT-STOR-002 for terminal entitlement consumption.
- INV-ARC-016 for append-only terminal facts.

### F14 - Claim decision path had a bare commit outside the FEAT boundary

Code changed:

- `app/routes/admin.py`

What changed:

- Removed explicit `db.session.commit()` calls after claim approval/rejection.
- Claim decision persistence is now left to the FEAT-owned boundary.

Authority used:

- INV-ARC-007 for request-handler side-effect boundaries.
- FEAT-STOR-003 for claim lifecycle orchestration.

### F7 - Insurance policy edit template referenced the wrong field

Code changed:

- `templates/admin_edit_insurance_policy.html`
- `app/routes/admin.py`

What changed:

- Replaced `item.title` with `item.name`.
- The template now matches the `StoreItem` model shape.
- The insurance editor route now orders by `StoreItem.name`, so the GET path no longer raises on the missing `title` attribute.

Authority used:

- MAP-UI-001 template-to-model wiring.

### F8 - Claim history templates assumed `incident_date` on claim rows

Code changed:

- `app/routes/student.py`
- `app/routes/admin.py`
- `templates/student_insurance_marketplace.html`
- `templates/student_view_policy.html`
- `templates/admin_view_student_policy.html`

What changed:

- Claim rows are now normalized in the route layer before rendering.
- Date display falls back to `claimed_dates[0]` or `submitted_at` and no longer depends on a missing `incident_date` attribute.

Authority used:

- MAP-UI-001 template wiring.
- DOM-STORE-001 claim lifecycle shape.

### F9 - Claim filing GET crashed because the template expected real form fields

Code changed:

- `app/routes/student.py`

What changed:

- Added a render-time dummy form shape for the GET path so the template can safely dereference the expected fields.
- The template receives the fields it needs without changing the canonical POST submission path.

Authority used:

- MAP-UI-001 for template contract satisfaction.
- INV-ARC-007 for request-path shape enforcement.

### F18 - Admin claim view showed the seat public ID instead of a display name

Code changed:

- `app/routes/admin.py`
- `templates/admin_process_claim.html`

What changed:

- The admin claim view now resolves the student display name from `IdentityProfile` when available.
- The template now renders the normalized date fields for claim incident/filed dates.

Authority used:

- DOM-STORE-001 for identity/display provenance.
- MAP-UI-001 for admin claim template wiring.

### F12 - Policy transition lineage stored `created_by` as a bare integer

Code changed:

- `app/models.py`
- `migrations/versions/8f1a2c3d4b5e_add_policy_transition_created_by_fk.py`
- `migrations/versions/7a9b8c6d5e4f_merge_policy_transition_fk_head.py`

What changed:

- Added a foreign key from `policy_transitions.created_by` to `users.id`.
- Added the corresponding Alembic migration and merge revision so the repository stays single-headed.

Authority used:

- DOM-CLASS-001 for policy transition lineage authority.
- DOM-ECON-003 for transition lineage semantics.

### F20 - Policy version activation state was treated as mutable historical truth

Code changed:

- `app/services/insurance_policy_service.py`
- `app/utils/economy_rebalance.py`

What changed:

- Removed the in-place deactivation writes that mutated source policy-version rows.
- Preserved the active/projection field on newly created target versions while stopping historical version rows from being rewritten to represent later policy state.

Authority used:

- DOM-CLASS-001 for immutable policy lineage semantics.
- DOM-ECON-003 for append-only policy evolution.

## Verification

Targeted verification completed on the patched paths:

- `python3 -m py_compile app/feats/insurance_purchase_feat.py app/services/store_entitlement_service.py app/feats/insurance_claim_feat.py app/routes/api.py app/routes/student.py app/routes/admin.py`
- `pytest -q tests/dom/entitlement/test_store.py tests/dom/entitlement/test_redemption_rejection.py tests/dom/entitlement/test_redemption_disposition.py`

Result: targeted tests passed.

## Notes

The audit report still lists the historical structural concern `F20` in the report body, but the code path that mutated historical policy-version rows has been removed. This remediation note only records the failures that were fixed in code during this pass and the authority used for those fixes.
