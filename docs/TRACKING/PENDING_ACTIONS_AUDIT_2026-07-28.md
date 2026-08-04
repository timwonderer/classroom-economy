# Pending Actions Audit — Phase 3 Reopened for Required Primitives

**Date**: 2026-07-28  
**Status**: ⚠️ PERSISTENCE CONTRACT DEFINED; WORKFLOW CONTRACTS INCOMPLETE  
**Scope**: Canonical persistence required by STORE/ENT behavior; FEATs not yet implemented; some workflows lack full authority

---

## I. Executive Summary

The `pending_actions` table is canonical persistence required by STORE/ENT behavior. The table contract is fully defined; however, some workflow contracts are incomplete. Phase 3 must be reopened to establish all required mutation primitives.

**Current State**:
- ✅ `pending_actions` table created (Phase 2 schema migration)
- ✅ PendingAction model defined in `app/models.py`
- ✅ DOM-STORE-001 v5.0 defines persistence contract (§VII.B) and general pending-action semantics (§IX)
- ✅ FEAT-STOR-003 spec written with sufficient authority (Insurance Claim Lifecycle)
- ⚠️ Delayed-use redemption workflow lacks FEAT contract (design needed)
- ⚠️ Hall-pass pending-action workflow lacks STORE/ENT ↔ PROD coordination contract (clarification needed)
- ❌ NO FEATs currently write to `pending_actions`
- ❌ FEAT-STOR-003 implementation code does not exist
- ❌ Delayed-use redemption FEAT not designed
- ❌ Hall-pass request FEAT not designed (coordination unclear)

**Phase 3 Reopened For**: Complete all required pending_actions mutation primitives with lawful FEAT contracts and implementations.

---

## II. Canonical Workflows Requiring Pending Actions

### A. Insurance Claims (FEAT-STOR-003)

**Authority**: DOM-STORE-001 §VIII.E.1 + FEAT-STOR-003 v2.0

**Workflow**:
1. **Submission** (Student or teacher-assisted):
   - Student submits claim under active insurance entitlement
   - Creates `pending_actions` row with payload containing claim subject
   - `authoritative_feat = "FEAT-STOR-003"`
   - Action awaits teacher adjudication

2. **Resolution** (Teacher decision):
   - Teacher reviews claim
   - Two outcomes: Accept or Reject
   - Accepted: Write CONSUMED event + coordinate Ledger credit + delete pending_action
   - Rejected: Write CONSUMED event (with rejection marker) + delete pending_action

**Contract Gap**: FEAT-STOR-003 implementation code does not exist
- Submission logic not implemented
- Resolution logic not implemented
- Ledger coordination not implemented (though FEAT-LED-001 exists)

**Current Mutation Path**: None

**Impact**: Insurance workflows completely blocked until FEAT-STOR-003 is implemented

---

### B. Delayed-Use Redemption

**Authority**: DOM-STORE-001 §VIII.E.4 + FEAT-STOR-002 (partial)

**Specification Excerpt**:
> "Delayed-use entitlements SHALL... support a pending action before resolution; record `CONSUMED` on successful redemption; record `REVOKED` when redemption is rejected"

**Workflow** (inferred from spec):
1. **Submission**: Student initiates redemption of delayed-use entitlement
   - Creates `pending_actions` row
   - `authoritative_feat = "FEAT-TBD"` (FEAT not yet specified or named)
   - Action awaits authorization/resolution

2. **Resolution**: Teacher or system approves/rejects redemption
   - Approved: Write CONSUMED event + delete pending_action
   - Rejected: Write REVOKED event + delete pending_action

**Contract Gap**: 
- No named FEAT exists for delayed-use redemption workflow
- No FEAT specification document for redemption submission logic
- No FEAT specification for redemption resolution logic
- Unclear: who submits (student or teacher)? When? What conditions apply?

**Current Mutation Path**: None

**Impact**: Delayed-use purchases cannot be redeemed (if they're even available)

---

### C. Hall-Pass Requests (Request/Approval Path)

**Authority**: DOM-STORE-001 §VIII.E.6 + FEAT-STOR-002

**Specification Excerpt**:
> "Hall-pass entitlements SHALL... support pending action if the exercise requires approval"

**Specification Examples** (IX - Pending Action Semantics):
> "a hall-pass request remains pending until the authoritative FEAT resolves it"

**Workflow** (inferred from spec):
1. **Submission**: Student or system initiates hall-pass request
   - Creates `pending_actions` row
   - Requires teacher approval before granting
   - `authoritative_feat = "FEAT-TBD"` (FEAT not yet specified)

2. **Resolution**: Teacher approves or denies request
   - Approved: Create hall-pass grant or consumption event (unclear which)
   - Denied: Delete pending_action without creating entitlement event

**Contract Gap**:
- Hall-pass request workflow not fully specified
- No named FEAT exists for hall-pass requests
- No FEAT specification document
- Unclear: request for what action? (approval to use? to grant? to consume?)
- Unclear: who creates the hall-pass entitlement if approved?
- Unclear: coordination with cross-domain hall-pass consumption

**Current Mutation Path**: None

**Current Implementation**: `FEAT-PROD-002_RECORD_HALL_PASS_LOG.md` handles hall-pass consumption events in Productivity domain, but does not involve pending_actions

**Impact**: If approval-required hall passes are configured, no workflow to request/approve them

---

## III. Model Status

### PendingAction Model (app/models.py)

**Status**: ✅ Defined and correct

```python
class PendingAction(db.Model):
    pending_action_id: str (PK, UUID)
    class_id: str (FK to classes)
    seat_id: int (FK to seats)
    entitlement_id: str (internal lineage reference)
    correlation_id: str (cross-domain lineage, unique)
    authoritative_feat: str (FEAT that owns resolution)
    payload: JSON (typed request envelope)
    submitted_at: datetime (canonical submission time)
```

**Indexes**: 
- ix_pending_actions_class (for class-scoped queries)
- correlation_id UNIQUE (ensures one pending action per lifecycle)
- seat_id, class_id, entitlement_id, authoritative_feat all indexed

**Relationships**: 
- seat: backref to Seat.pending_actions

**Correctness**: Model correctly implements DOM-STORE-001 §VII.B contract

---

## IV. Phase 3/4 Boundary Assessment

### Phase 3 (Primitive Operations): INCOMPLETE FOR PENDING ACTIONS

**Current Phase 3 Deliverables** (per PHASE-3-COMPLETION-STATUS.md):
- ✅ FEAT-STOR-004 (Direct Entitlement Grant) — does not touch pending_actions
- ✅ FEAT-STOR-001 (Store Purchase) — does not touch pending_actions
- ✅ StorePolicyResolver + test coverage

**Missing Phase 3 Primitives** (required for pending_actions workflows):
- ❌ Insurance claim submission primitive (needed for FEAT-STOR-003)
- ❌ Insurance claim resolution primitive (needed for FEAT-STOR-003)
- ❌ Delayed-use redemption submission primitive (needs FEAT-TBD)
- ❌ Delayed-use redemption resolution primitive (needs FEAT-TBD)
- ❌ Hall-pass request submission primitive (needs FEAT-TBD)
- ❌ Hall-pass request resolution primitive (needs FEAT-TBD)

### Phase 4 (Legal Mutation Boundary): INCOMPLETE FOR PENDING ACTIONS

**Current Phase 4 Assessment** (per PHASE-4-LEGAL-MUTATION-BOUNDARY.md):
- ✅ FEAT-STOR-001 and FEAT-STOR-004 have canonical mutation paths
- ✅ No routes bypass FEATs for entitlement_events
- ❌ **No FEATs implemented for pending_actions mutations yet**

**Required Phase 4 Work** (when Phase 3 FEATs are completed):
- Define legal mutation boundary for each pending_actions workflow
- Wire submission paths through canonical FEATs (e.g., claim submission only through FEAT-STOR-003)
- Wire resolution paths through canonical FEATs (e.g., claim decision only through FEAT-STOR-003)
- Ensure atomicity of resolution (write entitlement event + delete pending_action + coordinate Ledger)

---

## V. Authority and Contract Gaps

### Gap 1: Delayed-Use Redemption FEAT Specification

**Missing**: A FEAT specification for delayed-use item redemption workflow

**Currently Defined**: Only that DELAYED_USE entitlements "support a pending action before resolution"

**Questions Requiring Authority**:
- Who can submit a redemption request? (student only? teacher-assisted?)
- When can redemption be requested? (immediately? after time period? based on entitlement policy?)
- What validates a redemption request? (just entitlement existence? product availability?)
- What conditions must teacher verify before approval? (what does "successful redemption" look like?)
- On rejection: does the entitlement get REVOKED or return to GRANTED?
- Can a delayed-use entitlement be redeemed multiple times or is it terminal?

**Required**: Amendment to DOM-STORE-001 or new FEAT-STOR-DELAYED_USE specification

---

### Gap 2: Hall-Pass Request Workflow FEAT Specification

**Missing**: A FEAT specification for hall-pass requests (if request/approval model is used)

**Currently Known**: Hall passes "support pending action if the exercise requires approval"

**Questions Requiring Authority**:
- When is approval required? (policy-dependent? always? never?)
- Who submits the request? (student initiating use? teacher managing?)
- What does the pending action payload contain? (time requested? reason? duration?)
- On approval: what happens? (entitlement already granted, or does approval trigger grant?)
- Interaction with cross-domain consumption: how does FEAT-PROD-002 interact with pending approval?
- Can a hall-pass request be denied? What's the student experience?

**Required**: Clarification in DOM-STORE-001 §VIII.E.6 or new FEAT specification

---

### Gap 3: Interaction Between Delayed-Use and Entitlement Events

**Ambiguity**: What is the interaction between a submitted delayed-use redemption (pending action) and the entitlement grant event?

**Current Model**:
- GRANTED event created when entitlement granted
- Pending action created when redemption submitted
- On approval: CONSUMED event created, pending action deleted
- On rejection: REVOKED event created, pending action deleted

**Unclear**: Should rejection REVOKE the original grant or just mark the redemption request as denied? Does REVOKED mean the student gets a refund?

**Required**: Clarification in the redemption/refund contract

---

## VI. Phase 3 Reopened — Three Distinct Paths

`pending_actions` is canonical persistence required by already-defined STORE/ENT behavior. Phase 3 Primitive Operations is incomplete without its required mutation capabilities. Reopen Phase 3 with three sequential paths:

### Path 1: FEAT-STOR-003 (Insurance Claim Lifecycle) — IMPLEMENT

**Authority**: Sufficient
- ✅ DOM-STORE-001 §VIII.E.1 defines insurance claim workflow
- ✅ FEAT-STOR-003 v2.0 specification complete
- ✅ Claim submission, adjudication, and resolution contracts clear

**Phase 3 Task**: Implement FEAT-STOR-003 (submission and resolution)
- Claim submission FEAT creates pending_action
- Claim resolution FEAT reads pending_action, writes CONSUMED event, deletes pending_action
- Both paths include `policy_uuid` immutable reference + Ledger coordination

---

### Path 2: Delayed-Use Redemption — DESIGN & ESTABLISH CONTRACT

**Authority**: Insufficient
- ✅ DOM-STORE-001 §VIII.E.4 states DELAYED_USE "support a pending action before resolution"
- ❌ No FEAT specification exists
- ❌ No redemption workflow defined (who submits? when? what validates?)
- ❌ Unclear if redemption is one-time or repeatable
- ❌ Refund/revocation semantics undefined

**Phase 3 Task**: Design document + FEAT contract (do NOT implement yet)
- Document pending-action-based redemption workflow
- Establish FEAT-STOR-DELAYED_USE or similar contract
- Define: submission authority, validation rules, approval conditions, refund model
- Include `policy_uuid` immutable reference rule
- Submit for authority approval before implementation

---

### Path 3: Hall-Pass Pending Actions — CLARIFY COORDINATION CONTRACT

**Authority**: Incomplete
- ✅ DOM-STORE-001 §VIII.E.6 states hall passes "support pending action if the exercise requires approval"
- ❌ Unclear when approval is required (policy-dependent?)
- ❌ Coordination with FEAT-PROD-002 (RECORD_HALL_PASS_LOG) undefined
- ❌ Workflow for pending request/approval not specified
- ❌ STORE/ENT ↔ PROD boundary for pending actions unclear

**Phase 3 Task**: Coordination contract specification (do NOT implement yet)
- Clarify in DOM-STORE-001 or new contract document:
  - When does a hall-pass request become pending?
  - Who submits? Who approves?
  - How does pending request interact with cross-domain consumption (PROD)?
  - What is the approval/denial user experience?
- Include `policy_uuid` immutable reference rule
- Submit for cross-domain authority approval before implementation

---

## VII. Current Designation (Correct)

**Pending Actions Status**: 

Canonical persistence with **no current mutation surface**. The table exists for defined workflows (insurance claims, delayed-use redemptions, hall-pass requests), but the FEATs that would write to it are not yet implemented.

**All future mutation must enter through a lawful FEAT:**
- Insurance claims → FEAT-STOR-003 (spec exists, code needed)
- Delayed-use redemptions → FEAT-TBD (spec needed)
- Hall-pass requests → FEAT-TBD (spec clarification needed)

No routes, helpers, or background jobs currently write `pending_actions` directly. When FEATs are implemented, they will become the single lawful mutation path.

---

## VII. Critical Policy-Reference Rule for All Workflows

**All PendingAction-based workflows SHALL follow this canonical rule**:

- PendingAction SHALL record exact immutable `policy_uuid` (not `product_id`, not copied config)
- Policy configuration resolved from `policy_uuid` at resolution time
- Payload contains request-specific facts ONLY (claim subject, redemption details, etc.)
- Payload SHALL NOT duplicate policy rules or configuration
- While PendingAction is executable, it is an executable dependency → policy must remain resolvable
- If policy is deleted while pending action exists, deletion must fail unless policy has no executable dependencies

**Rationale**: 
- Prevents policy-config drift between submission and resolution
- Maintains immutable historical record
- Ensures policy version consistency through lifecycle
- Enables future policy audits and versions

---

## VIII. Phase 3 Sequence (Reopened)

**Current Phase 3 (FEAT-STOR-001, FEAT-STOR-004, StorePolicyResolver)**: ✅ Complete

**Phase 3 Extension — Pending Actions Primitives** (reopened):

1. **FEAT-STOR-003 (Insurance)**: Implement
   - Submission: `create_insurance_claim(entitlement_id, policy_uuid, subject_payload) → pending_action`
   - Resolution: `resolve_insurance_claim(pending_action_id, approved: bool) → entitlement_event + delete pending_action`
   - Include Ledger coordination for accepted claims

2. **Delayed-Use Redemption (FEAT-TBD)**: Design & establish contract
   - Document workflow, define FEAT contract
   - Submit for approval (no implementation yet)

3. **Hall-Pass Pending (FEAT-TBD)**: Clarify STORE/ENT ↔ PROD coordination
   - Establish cross-domain contract with Productivity domain
   - Submit for approval (no implementation yet)

---

## IX. Phase 4 Rerun (After Phase 3 Extension)

After all Phase 3 pending-action primitives are implemented:

**Phase 4 will audit**:
- ✅ FEAT-STOR-003 has one lawful mutation path (no routes bypass it)
- ✅ Each FEAT uses one transaction boundary
- ✅ Idempotency via correlation_id
- ✅ Resolution atomically writes entitlement event + deletes pending_action
- ✅ Policy_uuid immutable reference rule enforced
- ✅ All tests pass

---

## X. Phase 5 Resumes (After Phase 3/4 Complete)

Phase 5 read models may then include:
- Insurance claim status projections
- Delayed-use redemption tracking (after workflow is designed)
- Hall-pass request/approval status (after coordination is clarified)
- All OTHER entitlement reads (safe to build now)

**Phase 5 remains paused until**: Phase 3 extension complete AND Phase 4 audit complete

---

**Conclusion**: `pending_actions` is canonical persistence required by STORE/ENT behavior. Phase 3 reopened to complete all required mutation primitives. Path 1 (Insurance) has authority and is ready to implement. Paths 2 & 3 (Delayed-use, Hall-pass) require contract establishment before implementation. Phase 5 read-model work (already completed: read service) preserved but remains paused until Phase 3/4 complete.
