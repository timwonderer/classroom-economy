# Phase 3 Extension: Authority Clarifications Applied

**Date**: 2026-07-29  
**Status**: ✅ Clarifications Applied; Updated Design Documents; Implementation Blockers Refined  
**Authority Source**: User authority guidance on all three pending_actions workflows

---

## Summary of Clarifications

Authority has clarified all three pending_actions workflow models. Each affects implementation strategy significantly.

---

## Path 1: Insurance Claims (FEAT-STOR-003) ✅ READY FOR IMPLEMENTATION

### Authority Clarification Applied

**Both approval and rejection write CONSUMED events.**

This was **already correct in the original spec**, but authority clarified the rationale:

> "CONSUMED records that the redemption/claim reached a terminal outcome; the event payload records the outcome (APPROVED, REJECTED, etc.). Approval additionally produces the authorized benefit effects."

### Updated Contract

| Event | Outcome | CONSUMED Written? | Event Payload | Ledger Coordination |
|-------|---------|-------------------|----------------|---------------------|
| Approval | Claim accepted | ✅ YES | `"claim_decision": "APPROVED"`, reimbursement_amount, ledger_correlation | ✅ Yes (FEAT-LED-001) |
| Rejection | Claim rejected | ✅ YES | `"claim_decision": "REJECTED"`, rejection_reason | ❌ No (no refund) |

**Key Points**:
- Both paths write CONSUMED (terminal resolution for the claim itself)
- CONSUMED doesn't mean "reimbursement issued" — it means "claim adjudication finished"
- Entitlement remains GRANTED for future claims per policy
- Only approval triggers Ledger coordination
- Rejection never reverses entitlement or triggers refund (Ledger domain's concern)

### Implementation Status

✅ **Ready to implement immediately**

All authority is in place. Can write FEAT-STOR-003-SUBMIT and FEAT-STOR-003-RESOLVE in Phase 3.

---

## Path 2: Delayed-Use Redemption (FEAT-STOR-DELAYED_REDEEM-*) ✅ MAJOR CLARIFICATION, 7 QUESTIONS REMAIN

### Authority Clarification Applied

**Teacher rejection is strictly DENY REQUEST. Entitlement stays GRANTED.**

Authority explicitly rejected the proposed refund-on-rejection behavior:

> "Do not implement a rejection path that writes REVOKED, CONSUMED, refunds the purchase, or otherwise reverses the entitlement. 'Cannot fulfill/cancel purchase' is a separate reversal concern owned by Ledger's lawful void/compensation workflow, with any necessary entitlement consequences coordinated from that authority."

### Updated Contract

| Event | Outcome | Pending_Action | Entitlement | Event Written? | Ledger Coordination |
|-------|---------|-----------------|-------------|-----------------|---------------------|
| Approval | Redemption accepted | ✅ Deleted | Stays GRANTED | CONSUMED written | ❌ No |
| Denial | Redemption rejected | ✅ Deleted | **Stays GRANTED** | ❌ NO EVENT | ❌ No refund |

**Key Points**:
- Rejection is DENY REQUEST only (not a purchase reversal)
- Pending_action deleted (request is no longer pending)
- **Entitlement stays GRANTED** (student can resubmit)
- **No terminal event written** (GRANTED continues unchanged)
- **No Ledger coordination** (purchase reversal is Ledger domain's concern)
- Student can request redemption again later

### Design Document Updates

Removed Question 6 (Refund coordination) as no longer relevant.

Remaining questions requiring authority answer:
- Question 1: Submission authority (student, teacher, system, both?)
- Question 2: Submission trigger (on-demand, time-based, automatic?)
- Question 3: Validation scope
- Question 4: Payload structure
- Question 5: Approval conditions (manual, automatic?)
- Question 6: Redemption repeatability (one-time, repeatable?)
- Question 7: Expiration trigger

### Implementation Status

⏳ **Blocked pending authority answers to 5 questions**

Cannot finalize FEAT signature or validation logic until Questions 1-5 are answered.

---

## Path 3: Hall-Pass Pending Actions (FEAT-STOR-HALL_PASS_REQUEST-*) ✅ MAJOR CLARIFICATION, 1 CRITICAL BLOCKER

### Authority Clarification Applied

**Model analogously to delayed-use, but with coordinated operation.**

Authority clarified a critical difference: Hall-pass is not asynchronous; it's a **coordinated operation**:

> "STORE/ENT validates the entitlement and creates the PendingAction. Teacher approval causes STORE/ENT to coordinate with PROD. PROD does not inspect STORE/ENT persistence or determine entitlement eligibility; it receives an authorized request and owns writing the HallPassLog. Successful PROD logging then participates in completing the STORE/ENT operation, including the permanent CONSUMED event and PendingAction resolution."

### Updated Model

```
Submission:
  STORE/ENT validates entitlement → creates pending_action → awaits teacher approval

Teacher Approval:
  STORE/ENT coordinates with PROD
  ├─ PROD receives AUTHORIZED REQUEST (not inspection)
  ├─ PROD writes HallPassLog
  └─ (PROD success or failure determines next step)

  IF Prod succeeds:
    STORE/ENT writes CONSUMED event
    STORE/ENT deletes pending_action
    Both complete together
    
  IF Prod fails:
    STORE/ENT operation fails
    pending_action remains intact
    Can retry later

Teacher Denial:
  STORE/ENT deletes pending_action (DENY REQUEST)
  NO entitlement event written
  NO Productivity coordination
  Entitlement stays GRANTED
  Student can resubmit later
```

### Critical Blocker Identified

**Coordination Boundary Model MUST be determined**

Authority clarified the semantic (coordinated operation), but the implementation pattern is unclear:

**Three possible models** identified:
- **Model A**: Synchronous call (Store/Ent calls Prod FEAT; waits for completion)
  - Atomic transaction boundary
  - Follows FEAT-LED-001 pattern
- **Model B**: Asynchronous coordination (eventual consistency via queue/polling)
  - Loose coupling
  - Complex state management
- **Model C**: Coordinated via correlation_id (synchronous with shared ID)
  - Auditable; allows rollback on failure

**Decision Needed**:
1. Which coordination model?
2. What is transaction boundary semantics?
3. If Prod succeeds but Store/Ent fails, what is recovery?
4. Can we use existing FEAT-LED-001 pattern?

### Design Document Updates

- Updated baseline to reflect coordinated operation (not asynchronous read-check)
- Identified critical blocker (coordination boundary)
- Created separate analysis document (PHASE-3-EXTENSION-HALL-PASS-COORDINATION-ANALYSIS.md)
- Revised test coverage to reflect coordinated atomicity requirements

### Implementation Status

⏳ **Blocked pending authority clarification on coordination boundary**

Must research cross-domain authority docs (INV-ARC-021, DOM-LED-001, DOM-PROD-001) and determine coordination pattern **before implementation can proceed**.

---

## Authority Decision Checklist

### Path 1: Insurance Claims (FEAT-STOR-003)

- ✅ Both approval and rejection write CONSUMED (clarified)
- ✅ Only approval triggers Ledger coordination (clarified)
- ✅ Rejection doesn't reverse entitlement (clarified)
- ✅ Ready to implement

### Path 2: Delayed-Use Redemption

- ✅ Denial is DENY REQUEST only (clarified)
- ✅ Entitlement stays GRANTED on denial (clarified)
- ✅ No refund on denial (clarified)
- ⏳ Remaining questions: 1, 2, 3, 4, 5, 7, 8 (awaiting answers)

### Path 3: Hall-Pass Coordination

- ✅ Coordinated operation (not asynchronous read) (clarified)
- ✅ Prod receives authorized request (clarified)
- ✅ Successful Prod logging participates in Store/Ent completion (clarified)
- ✅ Denial is DENY REQUEST (clarified per analogy to delayed-use)
- ⏳ **CRITICAL**: Coordination boundary model (awaiting authority decision)
  - Must determine: sync call, async queue, or correlation-based?
  - Must determine: transaction boundary semantics
  - Must determine: failure recovery path

---

## Updated Implementation Roadmap

### Phase 3 (Pending Implementation Start)

#### Path 1: Insurance Claims ✅ READY

**Can start immediately**:
1. Implement FEAT-STOR-003-SUBMIT
   - Create pending_action
   - Validate entitlement + policy
   - Capture eligibility flags
2. Implement FEAT-STOR-003-RESOLVE
   - Read pending_action
   - Write CONSUMED event (both approval and rejection)
   - Coordinate Ledger on approval (via FEAT-LED-001)
   - Delete pending_action
   - Handle idempotency
3. Write comprehensive tests per checklist

**Estimated effort**: 2-3 days for complete implementation + testing

#### Path 2: Delayed-Use Redemption ⏳ BLOCKED

**Awaiting authority answers**:
- [ ] Question 1: Submission authority
- [ ] Question 2: Submission trigger
- [ ] Question 3: Validation scope
- [ ] Question 4: Payload structure
- [ ] Question 5: Approval conditions
- [ ] Question 7: Redemption repeatability
- [ ] Question 8: Expiration trigger

**After authority answers**:
1. Implement FEAT-STOR-DELAYED_REDEEM-SUBMIT
2. Implement FEAT-STOR-DELAYED_REDEEM-RESOLVE
3. Write comprehensive tests

**Estimated effort**: 2 days (after authority answers questions)

#### Path 3: Hall-Pass Coordination ⏳ CRITICAL BLOCKER

**Awaiting coordination boundary clarification**:
- [ ] Which coordination model (A, B, or C)?
- [ ] Transaction boundary semantics?
- [ ] Failure recovery if Prod succeeds but Store/Ent fails?
- [ ] Can we use FEAT-LED-001 pattern?

**Steps to unblock**:
1. Research existing cross-domain coordination patterns in authority docs
   - INV-ARC-021 (general cross-domain rules)
   - DOM-LED-001 (Ledger coordination example)
   - FEAT-LED-001 (shows synchronous pattern)
2. Ask authority which model is intended
3. Confirm transaction boundary semantics

**After coordination model approved**:
1. Implement FEAT-STOR-HALL_PASS_REQUEST-SUBMIT
2. Implement FEAT-STOR-HALL_PASS_REQUEST-RESOLVE (with coordination call to Prod)
3. Coordinate with Productivity domain on API/contract
4. Write comprehensive tests (including cross-domain coordination tests)

**Estimated effort**: 3-4 days (after coordination model clarified + Prod coordination agreed)

---

## Critical Rule: Policy-UUID Immutability

**All three workflows enforce**:

- `pending_action.payload.policy_uuid` stores exact immutable reference
- Policy resolved from UUID via `StorePolicyResolver` at resolution time
- While pending_action exists, policy must remain resolvable
- Deletion of policy fails unless no executable dependencies remain

---

## Next Actions

### For Authority (Delayed-Use Path 2)

**Provide answers to 7 questions**:
- Questions 1, 2, 3, 4, 5, 7, 8 in PHASE-3-EXTENSION-DELAYED-USE-REDEMPTION-DESIGN.md

### For Authority (Hall-Pass Path 3)

**Clarify coordination boundary**:
1. Review analysis in PHASE-3-EXTENSION-HALL-PASS-COORDINATION-ANALYSIS.md
2. Determine which model (A, B, or C)
3. Confirm transaction boundary semantics
4. Provide guidance on failure recovery

### For Implementation Team (Path 1)

**Ready to start immediately**:
1. Begin FEAT-STOR-003 implementation
2. Parallel: await authority decisions on Paths 2 & 3
3. Can implement Paths 2 & 3 immediately once authority decides

---

## Summary Table

| Path | Status | Blocker | Authority Clarifications | Next Action |
|------|--------|---------|--------------------------|-------------|
| **1: Insurance** | ✅ Ready | ❌ None | Both approval/rejection write CONSUMED | Start implementation |
| **2: Delayed-Use** | ⏳ Blocked | ⏳ 7 questions | Denial = DENY REQUEST only, no refund | Authority answers questions |
| **3: Hall-Pass** | ⏳ Blocked | 🔴 **Critical**: Coordination model | Coordinated operation (not async read) | Authority clarifies coordination boundary |

---

**Date**: 2026-07-29  
**Status**: All authority clarifications documented; Implementation ready for Path 1; Paths 2-3 blocked on specific authority decisions
