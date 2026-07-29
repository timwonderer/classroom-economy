# Phase 3 Extension: Pending Actions Mutation Primitives — Status

**Date**: 2026-07-29  
**Status**: ✅ Design & Specification Complete; Implementation Blocking Awaiting Authority Approval  
**Authority**: SOP-DEV-002 Phase 3 Reopened; Per PENDING_ACTIONS_AUDIT_2026-07-28.md

---

## Executive Summary

Phase 3 has been reopened to establish all required mutation primitives for `pending_actions` workflows. Three distinct paths are now specified:

| Path | Workflow | Status | Authority | Implementation |
|------|----------|--------|-----------|-----------------|
| **Path 1** | Insurance Claims (FEAT-STOR-003) | ✅ READY TO IMPLEMENT | ✅ Complete (DOM-STORE-001 §VIII.E.1 + FEAT-STOR-003 v2.0) | Can start Phase 3 implementation immediately |
| **Path 2** | Delayed-Use Redemption (FEAT-TBD) | ✅ Design complete | ⏳ Awaiting authority answers to 9 questions | Blocked until authority clarifies contract |
| **Path 3** | Hall-Pass Pending (FEAT-TBD) | ✅ Design complete | ⏳ Awaiting cross-domain approval (8 questions) | Blocked until Store/Ent + Prod coordinate |

---

## Path 1: Insurance Claims (FEAT-STOR-003) — READY FOR IMPLEMENTATION

**Document**: `PHASE-3-EXTENSION-FEAT-STOR-003-IMPLEMENTATION.md`

### Specification Status

✅ **Complete and Ready**

- Function signatures defined: `submit_insurance_claim()` and `resolve_insurance_claim()`
- Full execution sequences specified
- Preconditions and error cases documented
- Data models defined: `InsuranceClaimSubmissionResult` and `InsuranceClaimResolutionResult`
- Test coverage checklist complete
- Policy-UUID immutability enforced throughout

### Authority

✅ **Sufficient**

- **DOM-STORE-001 v5.0 §VIII.E.1**: Insurance claim workflow fully specified
- **FEAT-STOR-003 v2.0**: Complete FEAT contract exists
- **Cross-domain coordination**: FEAT-LED-001 (Ledger coordination) is named and can be integrated

### Key Architectural Decisions

1. **Policy-UUID Immutability**: Pending action records exact `policy_uuid` from entitlement; no config snapshot
2. **Atomic Resolution**: Approved claims write CONSUMED event + delete pending_action + coordinate Ledger in single transaction
3. **Ledger Coordination**: Via FEAT-LED-001; coordinate reimbursement credit atomically
4. **Idempotency**: Via `correlation_id` deduplication
5. **Submission Flag**: Eligibility flags captured in payload (warnings for teacher review, don't block)

### Implementation Blockers

✅ **None** — Ready to code

All authority is in place. Implementation can begin immediately in Phase 3.

---

## Path 2: Delayed-Use Redemption (FEAT-STOR-DELAYED_REDEEM-*) — Design Complete, 5 Authority Decisions

**Document**: `PHASE-3-EXTENSION-DELAYED-USE-REDEMPTION-DESIGN.md`

### Specification Status

✅ **Design Complete with Authority Clarifications**

- Workflow contract established
- Authority clarification applied: Rejection = DENY REQUEST only (no terminal event, no refund, entitlement stays GRANTED)
- 5 authority decisions identified (workflow/authorization policy, not configuration)
- Test coverage checklist proposed

### Authority Decisions Needed (5 Canonical Questions)

⏳ **Authority must decide** (workflow/authorization policy, not product-configuration):

1. **Submission Authority** — Student self-service? Teacher-assisted? Teacher-directed? Both?
2. **Submission Trigger** — On-demand via UI? Time-based? Automatic? Policy-dependent?
3. **Validation Scope** — Hard block on eligibility, or flag for teacher review?
4. **Request Payload** — What type-specific data in redemption request?
5. **Approval Authority** — Manual teacher review? Auto-approval? Policy-dependent?

### Policy-Configuration (NOT Authority Decisions)

Determined by product policy per DOM-STORE-001:
- **Redemption repeatability** (one-time vs repeatable) — product policy
- **Expiration trigger** (absolute, relative, period) — product policy

### Baseline Proposed

Pending authority answers to Questions 1-5:
- Student-initiated submission (on-demand via UI)
- Policy-based validation (flags for teacher, doesn't block)
- Minimal payload (just signal intent to redeem)
- Manual teacher approval required
- Rejection = DENY REQUEST only (no terminal event, no refund, entitlement stays GRANTED)

### Implementation Blockers

⏳ **Authority must answer 5 workflow decisions**

- Cannot finalize FEAT signatures until submission authority (Q1) is known
- Cannot finalize validation rules until validation scope (Q3) is clarified
- Cannot determine resolution model until approval authority (Q5) is known

**Estimated Time to Unblock**: Depends on authority decision velocity

---

## Path 3: Hall-Pass Pending Actions & STORE/ENT ↔ PROD Coordination — ✅ PATTERN DETERMINED

**Document**: `PHASE-3-EXTENSION-HALL-PASS-COORDINATION.md`

### Specification Status

✅ **Coordination Pattern Established (Model A - Synchronous)**

- Coordination boundary established per INV-ARC-021 (FEAT-only coordination)
- Coordination pattern reconciled with existing FEAT-LED-001 precedent
- Workflow contract outlined with canonical pattern
- Test coverage checklist (cross-domain coordination tests) proposed
- Analysis document reconciling three possible models (Model A is canonical)

### Authority Clarifications Applied

✅ **COORDINATION PATTERN DETERMINED**:

Per **INV-ARC-021** and existing **FEAT-LED-001 precedent** (synchronous Ledger coordination within Store/Ent FEAT):

**Canonical Pattern: Model A (Synchronous Call Within Store/Ent FEAT)**
- Store/Ent validates entitlement + prepares authorized command
- Store/Ent calls Prod synchronously to write HallPassLog
- Prod receives **authorized command** (does NOT inspect Store/Ent pending_action or entitlement state)
- Store/Ent awaits Prod result
- On Prod success: Store/Ent writes CONSUMED + deletes pending_action (atomic)
- On Prod failure: Store/Ent transaction fails and rolls back

This pattern **matches FEAT-LED-001** and satisfies INV-ARC-021 requirements.

### Workflow Contract

- **Policy-dependent approval requirement** (configurable per product)
- **Student-initiated requests** (on-demand "Request Use" button)
- **Minimal payload** (entitlement_id + optional metadata)
- **Pre-granted entitlements** (GRANTED on distribution; pending_action gates exercise)
- **Denial = DENY REQUEST only** (no Productivity coordination, entitlement stays GRANTED)
- **Simple UX** (Request Use → Awaiting Approval → Use when approved)
- **Auto-expire pending passes** at rent period end

### Remaining Coordination Work

⏳ **Productivity Domain Coordination**:
- Refactor FEAT-PROD-002 to accept authorized logging command from Store/Ent
- Confirm FEAT-PROD-002 does NOT inspect pending_action status
- Confirm FEAT-PROD-002 returns success/failure to Store/Ent caller

✅ **Pattern established** — no further authority decision needed on coordination model

---

## Supporting Infrastructure Completed

### Enhanced Entitlement Read Service

**File**: `app/services/entitlement_read_service.py`

Added methods for pending_actions read-side support:

- `get_entitlement_status(entitlement_id, class_id)` → Returns status (GRANTED, CONSUMED, EXPIRED, REVOKED, UNKNOWN)
- `get_active_entitlements(seat_id, class_id)` → Returns all GRANTED entitlements for seat
- Enhanced docstrings with preconditions, purity statements, and cross-domain use notes

These methods support read models and UI projections for pending_actions workflows.

---

## Overall Phase 3 Extension Timeline

### Completed (✅)

- **2026-07-28**: Audit of pending_actions workflows (3 paths identified)
- **2026-07-28**: FEAT-STOR-003 implementation specification completed
- **2026-07-29**: Delayed-use redemption design document completed (9 questions)
- **2026-07-29**: Hall-pass coordination design document completed (8 questions)
- **2026-07-29**: Enhanced entitlement read service

### In Progress (🔄)

- Awaiting authority answers to Path 2 questions (Delayed-Use)
- Awaiting cross-domain approval for Path 3 (Hall-Pass)

### Ready to Start (⏳ Next)

- Phase 3 implementation of FEAT-STOR-003 (Insurance) — no blockers
- Once authority answers Path 2 questions → implement delayed-use FEATs
- Once Path 3 coordination approved → implement hall-pass FEATs with Productivity

---

## Next Steps for Authority & Implementation

### For Authority (Delayed-Use, Path 2)

**Decision needed before Phase 3 implementation** (5 workflow questions):
- Answer Questions 1-5 in `PHASE-3-EXTENSION-DELAYED-USE-REDEMPTION-DESIGN.md` §VII
  1. Submission authority (student, teacher, system, both?)
  2. Submission trigger (on-demand, time-based, automatic, policy-dependent?)
  3. Validation scope (hard block vs flag for teacher review?)
  4. Payload structure (what type-specific data?)
  5. Approval authority (manual, automatic, policy-dependent?)
- Confirm baseline contract or specify alternatives
- Return approval to development team

### For Authority (Hall-Pass, Path 3)

✅ **Coordination pattern already established** — no further authority decision needed on Model A (synchronous call within Store/Ent FEAT)

**Remaining coordination work** (cross-domain team alignment):
- Productivity domain: refactor FEAT-PROD-002 to receive authorized command from Store/Ent (not pending_action inspection)
- Both domains: align on API/contract for Store/Ent→Prod call

### For Phase 3 Implementation Team (Insurance, Path 1)

**Ready to start**:
1. Implement FEAT-STOR-003-SUBMIT: `submit_insurance_claim()`
   - Create pending_action
   - Validate entitlement + policy
   - Capture eligibility flags
   - Return InsuranceClaimSubmissionResult

2. Implement FEAT-STOR-003-RESOLVE: `resolve_insurance_claim()`
   - Read pending_action
   - Validate policy still resolvable
   - Process approval/rejection
   - Write CONSUMED event atomically
   - Coordinate Ledger credit (if approved)
   - Delete pending_action
   - Return InsuranceClaimResolutionResult

3. Write comprehensive tests
   - Happy path (submit + approve + reject)
   - Error cases (expired, not found, etc.)
   - Idempotency (retry same correlation_id)
   - Atomicity (event + deletion + Ledger)
   - Multi-tenancy scoping

---

## Phase 4 Audit (After Phase 3 Complete)

After all three Phase 3 extension paths are implemented, Phase 4 will re-run its mutation boundary audit to verify:

- ✅ FEAT-STOR-003 has one lawful mutation path (no routes bypass it)
- ✅ FEAT-STOR-DELAYED_REDEEM-* paths implemented (if Path 2 approved)
- ✅ FEAT-STOR-HALL_PASS_REQUEST-* paths implemented (if Path 3 approved)
- ✅ Each FEAT uses one transaction boundary
- ✅ Idempotency via correlation_id enforced
- ✅ Resolution atomically writes entitlement event + deletes pending_action
- ✅ Policy_uuid immutable reference rule enforced
- ✅ All tests pass

---

## Phase 5 Resume (After Phase 3/4 Complete)

Phase 5 read models may then include:
- Insurance claim status projections
- Delayed-use redemption tracking (after workflow designed)
- Hall-pass request/approval status (after coordination clarified)
- All OTHER entitlement reads (safe to build now)

**Phase 5 remains paused until**: Phase 3 extension complete AND Phase 4 audit complete

---

## Critical Policy-Reference Rule (All Workflows)

**All PendingAction-based workflows SHALL enforce**:

- `pending_action.payload.policy_uuid` stores exact immutable reference (NOT `product_id`, NOT config snapshot)
- Policy resolved from UUID via `StorePolicyResolver` at resolution time
- While pending_action exists, policy must remain resolvable (executable dependency)
- Deletion of policy fails unless no executable dependencies remain

**Rationale**:
- Prevents policy-config drift between submission and resolution
- Maintains immutable historical record
- Ensures consistency through lifecycle
- Enables future policy audits and versions

---

## Summary

Phase 3 extension work is **design-complete for all three paths**:

- **Path 1 (Insurance)**: ✅ Ready for immediate implementation — full authority in place
- **Path 2 (Delayed-Use)**: ✅ Design complete; 🔄 awaiting authority answers to 9 questions
- **Path 3 (Hall-Pass)**: ✅ Design complete; 🔄 awaiting cross-domain approval

All workflows enforce policy-UUID immutability and atomic resolution semantics per DOM-STORE-001 v5.0.

**No code implementation will proceed for Paths 2 or 3 until authority has clarified the workflow contracts.**

Phase 3 implementation can begin immediately for Path 1 (Insurance Claims), pending concurrent authority review of Paths 2 and 3.

---

**Status**: ✅ Specification & Design Complete  
**Blocking**: ⏳ Authority answers (Path 2) + Cross-domain approval (Path 3)  
**Ready**: ✅ Path 1 implementation can start  
**Target**: Resume Phase 4 audit after all three paths implemented and tested
