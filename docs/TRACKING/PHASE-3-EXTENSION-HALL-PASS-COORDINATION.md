# Phase 3 Extension: Hall-Pass Pending Actions & STORE/ENT ↔ PROD Coordination

**Reference**: DOM-STORE-001 v5.0 §VIII.E.6 + DOM-PROD-001 v?.0 (cross-domain)  
**Status**: Coordination Contract Establishment (No Implementation)  
**Date**: 2026-07-29  
**Authority Level**: Requires Cross-Domain Approval Before Implementation

---

## I. Purpose

Establish the workflow and cross-domain contract for hall-pass entitlements that require approval before exercise. This document clarifies:

- **When** approval is required for hall-pass exercise
- **Who** submits approval requests and **who** grants approval
- **How** Store/Entitlements coordinates with Productivity to atomically complete the operation
- **What** the coordination boundary is (PROD HallPassLog + STORE/ENT CONSUMED + PendingAction deletion)
- **What** the student experience is for pending vs approved passes

**Authority Clarification**: Hall-pass workflow is modeled **analogously to delayed-use**, with a critical difference: Teacher approval causes Store/Ent to **coordinate** (not just read) with Productivity. Prod receives an authorized request and owns writing the HallPassLog. Successful Prod logging participates in completing Store/Ent operation (writing CONSUMED + deleting pending_action).

**Design Phase Output**: Coordination specification + atomic boundary identification; ready for Store/Entitlements ↔ Productivity authority review before implementation.

---

## II. Current Specification Status

### Store/Entitlements Spec (DOM-STORE-001 §VIII.E.6)

> "Hall-pass entitlements are granted here, but their authoritative exercise may be recorded by another domain.
>
> Hall-pass entitlements SHALL:
> - grant `GRANTED`;
> - support pending action if the exercise requires approval;
> - record `EXPIRED` when a perk-based pass reaches the end of the governing rent period without exercise;
> - permit `REVOKED` only for direct-grant hall passes when the governing policy allows revocation;
> - not create a duplicate Store-and-Entitlements `CONSUMED` row when another domain is the authoritative consumer."

**What's Defined**:
- ✅ Entitlements granted in Store/Entitlements
- ✅ Pending action exists IF approval required
- ✅ EXPIRED at rent period end (perk grants)
- ✅ REVOKED only for direct grants (if policy allows)
- ✅ Other domain owns authoritative consumption record

**What's NOT Defined**:
- ❌ When is approval required (policy-dependent? always? never?)
- ❌ Who submits the approval request (student? teacher?)
- ❌ What does pending action payload contain?
- ❌ On approval: what happens? (entitlement already granted, or does approval trigger grant?)
- ❌ How does pending approval interact with Productivity domain consumption?
- ❌ Can approval request be denied? UX?

### Productivity Domain Spec (Need to Verify)

**Known**: FEAT-PROD-002_RECORD_HALL_PASS_LOG.md handles hall-pass consumption in Productivity domain

**Unclear**: How does Productivity domain interact with pending approval status in Store/Entitlements?

---

## III. Coordination Questions Requiring Cross-Domain Authority

### Question 1: Approval Requirement Condition

**Question**: When does a hall-pass entitlement require approval?

**Options**:
A) **Always** — Every hall-pass (perk or direct grant) requires teacher approval before use
B) **Policy-dependent** — Approval requirement configured in product policy
C) **Never** — Hall passes never require approval (pending_actions not used for passes)
D) **Product-type dependent** — Different rules for perk-grants vs direct-grants

**Cross-Domain Implication**: Determines whether Productivity domain checks for pending approval before accepting pass-use log

---

### Question 2: Approval Request Submission

**Question**: Who submits a hall-pass approval request?

**Options**:
A) **Student-initiated** — Student requests to use pass; creates pending action; teacher reviews and approves
B) **Teacher-initiated** — Teacher assigns/grants pass or manages pass distribution
C) **System-automatic** — Approval requests auto-created on configured trigger (time, event, etc.)
D) **Not applicable** — If approval is never required (Question 1 Answer = "Never")

**Implication**: Determines whether student route or teacher route creates pending action

---

### Question 3: Pending Action Payload

**Question**: What information does a hall-pass approval request contain?

**Options**:
A) **Minimal** — Just entitlement_id (student says "I want to use this pass")
B) **Purpose/reason** — Student provides reason or explanation for pass use
C) **Temporal marker** — Student specifies WHEN pass should apply (e.g., "during period 3 today")
D) **Destination** — Student specifies WHERE/WHY (e.g., "library", "counselor", "restroom")

**Implication**: Determines pending_action payload structure and how Productivity domain validates pending approval

---

### Question 4: Entitlement Grant Timing

**Question**: Is the hall-pass entitlement already GRANTED when approval request is submitted, or is grant deferred until approval?

**Options**:
A) **Entitlement pre-granted** — GRANTED event created when pass is distributed; pending action created when student requests use
B) **Grant on approval** — No GRANTED event yet; pending action is the ONLY record until teacher approves; approval triggers GRANTED event
C) **Dual-phase grant** — Preliminary grant created; pending action gates further exercise until approval
D) **Product-dependent** — Timing varies by product

**Cross-Domain Critical**: Determines whether Productivity domain sees GRANTED entitlement or must wait for approval

**Implication**: Determines entitlement_events timeline and how read-side projects "available passes"

---

### Question 5: Approval vs Denial Outcomes

**Question**: What happens when teacher approves or denies a hall-pass request?

**Options**:

**If Approval**:
- A) Entitlement already GRANTED; pending_action deleted; pass becomes immediately usable
- B) GRANTED event created; pending_action deleted; pass becomes immediately usable
- C) Pending_action remains in "approved" state; Productivity consumes from approved state

**If Denial**:
- A) Entitlement receives REVOKED event; pending_action deleted; pass is unusable
- B) Pending_action deleted without terminal event; entitlement stays GRANTED; student can resubmit
- C) Pending_action marked "denied"; no REVOKED event; student can resubmit

**Cross-Domain Implication**: Determines whether Productivity domain checks GRANTED status, pending status, or event status before accepting pass log

---

### Question 6: Productivity Domain Integration

**Question**: How does Productivity domain (FEAT-PROD-002) interact with pending/approved hall passes?

**Options**:
A) **Productivity ignores Store pending** — Productivity consumes immediately when pass log created; Store/Ent handles pending/approval independently; no coordination
B) **Productivity checks pending** — Before accepting pass log, Productivity checks if pending_action exists; if pending, log is held until approval
C) **Productivity checks approval flag** — Productivity checks a mutable "approved" flag in pending_action; only logs if approved=true
D) **Different contract** — Hall-pass use doesn't go through Productivity domain; entirely Store/Ent owned

**Critical Coordination**: Determines cross-domain mutation order and atomicity

---

### Question 7: Student UX for Pending Passes

**Question**: What's the student experience when a hall pass requires approval?

**Options**:
A) **Student-initiated request** — Student sees pass in inventory, clicks "Request Use", request goes to pending, student sees "Awaiting Approval" status
B) **Teacher-grants-then-use** — Teacher approves pass first; then student can use immediately (student doesn't request)
C) **Transparent to student** — Student clicks "Use Pass"; system routes through approval backend; student waits or sees "Processing"
D) **Product-dependent** — UX varies by product type

**Implication**: Determines route structure and template views needed in Phase 7 (UI wiring)

---

### Question 8: Cross-Period/Rent-Period Boundary

**Question**: When a hall-pass grace period ends, what happens to pending approval requests?

**Options**:
A) **Auto-expire** — Pending pass automatically expires at rent period end; EXPIRED event recorded; pending_action deleted
B) **Auto-deny** — Pending pass automatically denied at rent period end; REVOKED event recorded; pending_action deleted
C) **Extend** — Pending request extends into next period (unusual)
D) **Product-dependent** — Expiration varies by product policy

**Implication**: Determines whether background job is needed to clean up old pending passes

---

## IV. Proposed Baseline Coordination Contract

**Authority Clarification Applied**: Hall-pass workflow is **coordinated operation**, not asynchronous read-check.

### Coordination Model (Revised)

When student submits approval-required hall-pass use request and teacher approves:

1. **Submission**: Store/Ent creates pending_action (FEAT-STOR-HALL_PASS_REQUEST-SUBMIT)
2. **Teacher Approval**: Store/Ent initiates coordinated operation with Productivity domain
3. **Coordination**:
   - Store/Ent validates entitlement + creates authorized request
   - Store/Ent coordinates with Productivity domain to write HallPassLog
   - Productivity domain receives authorized request (does NOT inspect Store/Ent tables)
   - Productivity owns writing the HallPassLog entry
4. **Atomic Completion**:
   - If Productivity successfully writes HallPassLog:
     * Store/Ent writes CONSUMED event (marking pass use)
     * Store/Ent deletes pending_action
     * Both succeed together
   - If Productivity fails to write HallPassLog:
     * Store/Ent operation fails
     * Pending_action remains intact
     * Can retry approval later

---

### Assumption 1: Policy-Dependent Approval

Approval is determined by product policy configuration.

Some products may require approval; others may not. Configuration is in Policies domain.

---

### Assumption 2: Student-Initiated Request for Approval

When student wants to use a pass that requires approval:

1. Student clicks "Use Pass" or "Request Use" in dashboard
2. Store/Entitlements creates pending_action (FEAT-STOR-HALL_PASS_REQUEST-SUBMIT)
3. Teacher sees pending request in dashboard
4. Teacher approves (FEAT-STOR-HALL_PASS_REQUEST-RESOLVE initiates coordinated operation)

---

### Assumption 3: Request Payload (Minimal)

```json
{
  "entitlement_id": "pass-uuid",
  "policy_uuid": "policy-uuid",  // IMMUTABLE
  "submitted_by_seat_id": student_seat_id,
  "submitted_at_timestamp": now,
  "use_purpose": null,           // Optional: reason from student
  "requested_use_date": null,    // Optional: temporal marker
  "eligibility_flags": {}
}
```

---

### Assumption 4: Entitlement Pre-Granted

When hall-pass is distributed (PURCHASE or GRANT path), GRANTED event is created.

When student requests use, entitlement is already GRANTED; pending_action gates exercise until approved.

---

### Assumption 5: Approval Outcomes (Coordinated)

**On Teacher Approval**:
- Store/Ent calls Productivity domain to record HallPassLog (authorized request)
- Productivity writes HallPassLog (owns authoritative log)
- If Productivity succeeds:
  * Store/Ent writes CONSUMED event (claim resolved with pass used)
  * Store/Ent deletes pending_action
  * Both domains commit their records
- If Productivity fails:
  * Store/Ent operation fails
  * Pending_action remains for retry

**On Teacher Denial** (DENY REQUEST):
- Pending_action deleted (request denied)
- NO entitlement event written (entitlement stays GRANTED)
- NO Productivity coordination
- Student can request use again later

---

### Assumption 6: Coordination Boundary (CRITICAL - REQUIRES AUTHORITY)

**Atomic boundary to be determined from existing cross-domain authority docs**:

PROD HallPassLog write + STORE/ENT CONSUMED write + PendingAction deletion must succeed/rollback together

**Questions for cross-domain authority**:
- Is this handled via Store/Ent calling Prod synchronously (simple case)?
- Or does it require async coordination via correlation_id (complex case)?
- What happens if Prod writes successfully but Store/Ent commit fails?
- What happens if Store/Ent rolls back but Prod HallPassLog already written?

**Current assumption**: Synchronous call with atomic transaction boundary covering both domains (TBD per authority docs)

---

### Assumption 7: Student UX

**For Approval-Required Passes**:
1. Student sees pass in inventory with status "Available (Approval Required)"
2. Student clicks "Request Use"
3. Optional modal for purpose/reason/timing (if configured)
4. Pending_action created; student sees "Awaiting Teacher Approval"
5. Teacher approves via dashboard
6. Store/Ent coordinates with Productivity to record pass use
7. On success: pass use is recorded; claim resolved
8. On failure: request remains pending for retry

**For Non-Approval Passes**:
1. Student sees pass in inventory with status "Available"
2. Student clicks "Use Pass"
3. Store/Ent directly coordinates with Productivity to record use
4. No pending_action involved

---

### Assumption 8: Rent Period Expiration

When rent period ends for perk-granted passes:

- Background job runs at period boundary
- Checks all hall-pass entitlements with `acquisition_type='PERK'` in ended period
- For each GRANTED pass: creates EXPIRED event
- For each pending_action: deletes pending_action (request auto-cancelled)
- Entitlement status becomes EXPIRED; unavailable for use

---

## V. Policy-UUID Immutability Rule (Hall Passes)

**Hall-pass pending actions SHALL enforce**:

- `pending_action.payload.policy_uuid` stores exact policy reference at request time
- On approval, policy is resolved to check approval conditions (if any)
- While pending_action exists, policy must remain resolvable
- If policy deleted while pending_action references it, deletion fails

---

## VI. Test Coverage Required (Proposed)

### Hall-Pass Approval Submission Tests

- Valid pass request creates pending_action with policy_uuid immutable
- Idempotent: retrying same correlation_id returns same pending_action_id
- Non-approval-required pass doesn't create pending_action (direct to Productivity)
- Expired entitlement request rejected (ENTITLEMENT_EXPIRED)
- Existing pending_action prevents duplicate request (ONE_REQUEST_AT_A_TIME)
- Request can be retracted before teacher approval (soft-delete)

### Hall-Pass Approval Resolution Tests

- Teacher approval coordinates with Productivity to write HallPassLog
- On successful Productivity log: Store/Ent writes CONSUMED + deletes pending_action (atomic)
- On failed Productivity log: Store/Ent operation fails; pending_action remains for retry
- Teacher denial deletes pending_action; no Productivity coordination; student can resubmit
- Expired pending_action auto-deleted at rent period boundary
- Policy deleted while pending creates POLICY_DELETED error (soft failure)

### Cross-Domain Coordination Tests

- **Atomic success**: Productivity HallPassLog + Store/Ent CONSUMED + PendingAction deletion all commit
- **Atomic failure**: If any operation fails, all roll back (pending_action remains)
- **Idempotency**: Retrying same approval produces same outcome (no duplicate HallPassLog)
- **Coordination boundary**: Verify Productivity doesn't inspect pending_action status independently
- **Authorization**: Verify Productivity trusts Store/Ent approval decision (authorized request)

---

## VII. Cross-Domain Authority Checklist

**✅ AUTHORITY CLARIFICATION RECEIVED**:
- Hall-pass workflow is **coordinated operation** (not asynchronous read-check)
- Teacher approval causes Store/Ent to coordinate with Productivity
- Productivity receives authorized request and owns writing HallPassLog
- Successful Prod logging participates in Store/Ent completion (CONSUMED + PendingAction deletion)

**CRITICAL BLOCKER - Before Implementation**:
- [ ] **Determine atomic/coordination boundary** from existing cross-domain authority docs (INV-ARC-021 or DOM-LED-001 or DOM-PROD-001)
  - How are multi-domain transactions coordinated (synchronous vs async via correlation_id)?
  - What is the rollback semantics if one domain succeeds but other fails?
  - Is there an existing pattern for PROD↔STORE/ENT coordination?

**Store/Entitlements Authority Must Approve**:
- [ ] Policy-UUID immutability rule for hall-pass requests
- [ ] Pending_action schema and lifecycle for passes
- [ ] GRANTED timing (pre-granted, confirmed)
- [ ] Denial outcomes (DENY REQUEST only, confirmed)
- [ ] Coordination call signature to Productivity (how to pass authorized request?)

**Productivity Domain Authority Must Approve**:
- [ ] HallPassLog write accepts authorization from Store/Ent
- [ ] Productivity does NOT inspect Store/Ent pending_action status
- [ ] Productivity returns success/failure to Store/Ent
- [ ] How Productivity coordinates rollback on failure

**Cross-Domain Authority (Both Domains) Must Approve**:
- [ ] **Coordination pattern**: Synchronous call with atomic transaction? Async via correlation_id?
- [ ] **Approval requirement**: Policy-dependent (confirmed)
- [ ] **Denial model**: DENY REQUEST only, no Productivity coordination (confirmed)
- [ ] **Rent period expiration**: Pending requests auto-cancelled (confirmed)
- [ ] Overall workflow: student request → teacher approval → coordinated Prod logging + Store/Ent CONSUMED

---

## VIII. Next Steps (Awaiting Cross-Domain Authority)

**CRITICAL BLOCKER - Before Phase 3 Implementation**:
- [ ] Research existing cross-domain coordination patterns in:
  - `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
  - `DOM-LED-001_LEDGER_DOMAIN.md` (for monetary coordination examples)
  - `DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md` (for Prod coordination patterns)
  - Any existing FEAT-LED-* or FEAT-PROD-* documents that coordinate with other domains

**Phase 3 Implementation Blocked Until**:
- Atomic/coordination boundary is identified from authority docs
- Both Store/Entitlements and Productivity domains approve revised baseline contract
- Answer all critical questions in §VII checklist
- Policy-UUID immutability rule confirmed
- Test coverage checklist approved

**Phase 3 Implementation Will** (once boundary determined):
- Implement FEAT-STOR-HALL_PASS_REQUEST-SUBMIT (student request)
- Implement FEAT-STOR-HALL_PASS_REQUEST-RESOLVE (teacher approval/denial with coordinated Prod call)
- Implement pending_action cleanup at rent period boundary
- Implement atomic coordination with Productivity domain per identified pattern

**Phase 4 Will**:
- Audit that all hall-pass mutations enter through lawful FEAT paths
- Verify atomicity of approval (delete pending_action) and Productivity logging
- Verify idempotency via correlation_id
- Verify policy-UUID immutability
- Verify Productivity can safely read pending_action status

**Phase 7 Will**:
- Wire student dashboard "Use Pass" button to FEAT-STOR-HALL_PASS_REQUEST-SUBMIT
- Wire teacher dashboard approval interface to FEAT-STOR-HALL_PASS_REQUEST-RESOLVE
- Implement pending request display and retraction UX

---

## IX. Appendix: Design Rationale

### Why cross-domain coordination matters

Hall passes are unique because:
- **Store/Entitlements owns entitlement grant and pending approval**
- **Productivity owns authoritative consumption record**
- **Neither domain should write to the other**

This creates a coordination boundary: Productivity must check Store/Entitlements pending status before recording consumption.

### Why pending_actions are needed

Without pending_actions, there's no way to represent "pass granted but awaiting teacher approval before use."

With pending_actions:
- Student request is durable (survives across requests)
- Teacher can review and approve/deny
- Productivity can check approval status without calling back to Store/Ent
- Rent period cleanup can handle expired pending passes

### Why questions matter

- **Question 1** determines scope (some vs all vs configurable passes)
- **Question 2** determines who initiates (student empowerment vs teacher control)
- **Question 4** determines timeline (pre-granted vs deferred)
- **Question 6** determines atomicity model (Store/Ent then Productivity vs simultaneous)
- **Question 8** determines background job requirements

### Baseline rationale

The proposed baseline assumes:
- **Policy-dependent approval** for flexibility
- **Student-initiated requests** for self-service
- **Minimal payload** (entitlement exists; just signal intent)
- **Pre-granted entitlements** for consistent Store/Ent model
- **Denial doesn't terminate** (student can retry) because passes are limited resources
- **Productivity reads pending** before accepting log for atomicity
- **Simple UX** (Request Use → Awaiting Approval → Use when approved)
- **Automatic expiration** at rent boundary for cleanup

This baseline is **proposed for cross-domain authority review**, not directive.

---

**Ready for Cross-Domain Authority Review**: Yes. Coordination design complete. Awaiting approval of Questions 1-8 and baseline contract before implementation proceeds.
