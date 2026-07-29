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
- **How** pending actions interact with hall-pass consumption recorded by Productivity domain
- **What** the student experience is for pending vs approved passes

**Design Phase Output**: Coordination specification ready for Store/Entitlements ↔ Productivity authority review before implementation.

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

**Until authority clarifies above questions, the following baseline contract is proposed**:

### Assumption 1: Policy-Dependent Approval

Approval is determined by product policy configuration (see Question 1 Answer = B).

Some products may require approval; others may not. Configuration is in Policies domain.

---

### Assumption 2: Student-Initiated Request for Approval

When student wants to use a pass that requires approval:

1. Student clicks "Use Pass" or "Request Use" in dashboard
2. Store/Entitlements creates pending_action (FEAT-STOR-HALL_PASS_REQUEST-SUBMIT)
3. Teacher sees pending request in dashboard
4. Teacher approves or denies (FEAT-STOR-HALL_PASS_REQUEST-RESOLVE)
5. Productivity domain checks pending approval status before accepting pass-use log

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

### Assumption 4: Entitlement Already GRANTED

When hall-pass is distributed (PURCHASE or GRANT path), GRANTED event is created.

When student requests use, entitlement is already GRANTED; pending_action is gates further exercise until approved.

Productivity domain reads entitlement status and sees GRANTED; pending_action status determines whether pass can be used.

---

### Assumption 5: Approval Outcomes

**On Teacher Approval**:
- Pending_action deleted
- Entitlement remains GRANTED (no new event)
- Productivity domain checks: `is_entitlement_exercisable(entitlement_id)` = TRUE and no recent pending_action
- Productivity creates HALL_PASS_LOG entry (owns authoritative consumption record)
- Productivity DOES NOT call Store/Ent; owns consumption record independently

**On Teacher Denial**:
- Pending_action deleted
- Entitlement remains GRANTED (no terminal event)
- Productivity domain check fails until resubmission
- Student can request use again later

---

### Assumption 6: Productivity-Store/Ent Boundary

**Store/Entitlements owns**:
- Hall-pass entitlement GRANTED status
- Pending approval requests (pending_actions)
- Entitlement lifecycle (GRANTED → EXPIRED/REVOKED only)

**Productivity owns**:
- Authoritative pass-use log (FEAT-PROD-002_RECORD_HALL_PASS_LOG)
- Consumption record when use is recorded

**Coordination points**:
- Productivity reads entitlement status before accepting pass log
- Productivity reads pending_action status to check if approval required
- No write coordination (Productivity doesn't write to Store/Ent; Store/Ent doesn't write to Productivity)

---

### Assumption 7: Student UX

**For Approval-Required Passes**:
1. Student sees pass in inventory with status "Available (Approval Required)"
2. Student clicks "Request Use"
3. Optional modal for purpose/reason/timing (if configured)
4. Pending_action created; student sees "Awaiting Teacher Approval"
5. Teacher approves via dashboard
6. Student retries use; Productivity accepts log
7. OR student can retract request before teacher approval

**For Non-Approval Passes**:
1. Student sees pass in inventory with status "Available"
2. Student clicks "Use Pass"
3. Productivity records immediately; no Store/Ent pending action

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

- Teacher approval deletes pending_action; Productivity can now accept pass log
- Teacher denial deletes pending_action; student can resubmit
- Expired pending_action auto-deleted at rent period boundary
- Policy deleted while pending creates POLICY_DELETED error (soft failure)

### Productivity Integration Tests

- Productivity reads entitlement status and pending_action status before accepting pass log
- Pending_action blocks Productivity consumption until approval
- Approved pass allows Productivity to create authoritative log

---

## VII. Cross-Domain Authority Checklist

**Store/Entitlements Authority Must Approve**:
- [ ] Policy-UUID immutability rule for hall-pass requests
- [ ] Pending_action schema and lifecycle for passes
- [ ] GRANTED timing (pre-granted vs grant-on-approval)
- [ ] Denial outcomes (REVOKED vs return-to-GRANTED)

**Productivity Domain Authority Must Approve**:
- [ ] How Productivity checks for pending approval before accepting pass log
- [ ] Atomicity of Productivity logging (is it blocked by pending_action?)
- [ ] Whether Productivity owns authoritative consumption or delegates to Store/Ent

**Cross-Domain Authority (Both Domains) Must Approve**:
- [ ] **Question 1**: Approval requirement is policy-dependent
- [ ] **Question 6**: Coordination contract (Productivity checks pending before logging)
- [ ] **Question 8**: Rent period expiration of pending requests
- [ ] Overall workflow: student request → teacher approval → Productivity logging

---

## VIII. Next Steps (Awaiting Cross-Domain Authority)

**Phase 3 Implementation Blocked Until**:
- Both Store/Entitlements and Productivity domains approve baseline contract
- Answer all questions in §VII checklist
- Policy-UUID immutability rule confirmed
- Coordination atomicity verified (Productivity can safely check pending status)
- Test coverage checklist approved

**Phase 3 Implementation Will**:
- Implement FEAT-STOR-HALL_PASS_REQUEST-SUBMIT (student request)
- Implement FEAT-STOR-HALL_PASS_REQUEST-RESOLVE (teacher approval/denial)
- Implement pending_action cleanup at rent period boundary
- Coordinate with Productivity domain on status-checking API

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
