# Pending Actions Audit — Phase 3/4 Boundary Resolution

**Date**: 2026-07-28  
**Status**: ⚠️ CONTRACT DEFINED, IMPLEMENTATION INCOMPLETE  
**Scope**: Canonical persistence without current mutation paths; workflows documented but FEATs not yet implemented

---

## I. Executive Summary

The `pending_actions` table is canonical persistence with well-defined workflows documented in DOM-STORE-001 and FEAT specifications, but the FEATs that would write to it are not yet implemented.

**Current State**:
- ✅ `pending_actions` table created (Phase 2 schema migration)
- ✅ PendingAction model defined in `app/models.py`
- ✅ DOM-STORE-001 v5.0 defines contract and workflows
- ✅ FEAT-STOR-003 spec written (Insurance Claim Lifecycle)
- ❌ NO FEATs currently write to `pending_actions`
- ❌ Insurance claim submission FEAT not implemented
- ❌ Insurance claim resolution FEAT not implemented
- ❌ Delayed-use redemption FEAT not implemented
- ❌ Hall-pass request approval FEAT not implemented

**Correct Designation**: `pending_actions` is canonical persistence **with no current mutation surface**. All future mutations must enter through lawful FEATs (to be implemented in Phase 3+ of respective workflows).

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

## VI. Phase 3/4 Recommendation

### Do Not Close Phase 3 with Incomplete Pending Actions Workflows

**Rationale**: 
- `pending_actions` is canonical persistence with defined workflows (insurance, delayed-use, hall-pass)
- FEATs for these workflows are not yet implemented
- Phase 3 primitives should include all entitlement-related operations, including pending action submissions/resolutions

**Two Options**:

**Option A: Extend Phase 3 to Include Pending Actions FEATs** (Recommended if workflows are imminent)
- Add FEAT-STOR-003 (Insurance Claim Lifecycle) implementation to Phase 3
- Add delayed-use redemption FEAT to Phase 3
- Add hall-pass request FEAT to Phase 3
- Extends Phase 3 effort but ensures complete entitlement primitives

**Option B: Phase 3 Complete; Pending Actions Workflows = Phase 3+ Follow-Up** (Current status)
- Keep Phase 3 closed as-is (FEAT-STOR-001, FEAT-STOR-004, StorePolicyResolver)
- Document pending_actions as "canonical persistence with no current mutation surface"
- Mark FEAT-STOR-003, delayed-use, and hall-pass FEATs as Phase 3 Follow-Up or Phase 5+
- All future mutations to pending_actions must enter through lawful FEATs (enforced at Phase 4 when those FEATs exist)

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

## VIII. Phase 4 Check Points

When Phase 3 is extended or when pending action FEATs are later implemented:

**Before closing Phase 4 for pending_actions workflows**:
- ✅ Each pending_actions FEAT (STOR-003, delayed-use, hall-pass) is implemented
- ✅ No routes write pending_actions directly (only through FEAT)
- ✅ Each FEAT uses one transaction boundary
- ✅ Idempotency and correlation built into FEAT contracts
- ✅ Resolution path atomically writes entitlement event + deletes pending action
- ✅ Tests verify FEAT contracts
- ✅ Routes wired to FEATs (Phase 7 concern)

---

## IX. Handoff to Phase 5

**Phase 5 Read Models** can proceed independently:
- Read projections for pending actions (list pending for student, list pending by FEAT, etc.)
- View models for insurance claim status, redemption status
- No blocker: Phase 3/4 pending_actions work can happen in parallel

**Phase 5 should NOT**:
- Stub implementations of workflows without canonical FEATs
- Assume semantics for delayed-use or hall-pass requests
- Build projections that depend on unimplemented workflows

---

**Conclusion**: `pending_actions` is correctly designated as canonical persistence with no current mutation surface. All future mutations must enter through lawful FEATs (to be defined, specified, and implemented in later phases). Phase 3 completion stands as-is; pending_actions workflows are Phase 3 Follow-Up or Phase 5+ work.
