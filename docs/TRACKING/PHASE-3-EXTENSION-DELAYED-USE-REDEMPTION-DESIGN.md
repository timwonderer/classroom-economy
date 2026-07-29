# Phase 3 Extension: Delayed-Use Redemption Workflow Design

**Reference**: DOM-STORE-001 v5.0 §VIII.E.4 (Delayed-use semantics)  
**Status**: Design & Contract Establishment (No Implementation)  
**Date**: 2026-07-29  
**Authority Level**: Requires Approval Before Implementation

---

## I. Purpose

Establish the workflow contract for delayed-use entitlement redemption through the `pending_actions` workflow. This document defines WHO submits redemptions, WHEN they are submitted, WHAT validates a submission, and HOW redemptions are resolved—without implementing code.

**Design Phase Output**: Specification ready for authority review and approval before Phase 3 implementation begins.

---

## II. Current Specification (DOM-STORE-001 §VIII.E.4)

DOM-STORE-001 v5.0 defines delayed-use lifecycle as:

> "Delayed-use entitlements may be redeemed later. Delayed-use entitlements SHALL:
> - grant `GRANTED`;
> - support a pending action before resolution;
> - record `CONSUMED` on successful redemption;
> - record `REVOKED` when redemption is rejected and the entitlement is returned/refunded through the lawful reversal path;
> - record `EXPIRED` when the configured expiration boundary is reached without lawful exercise."

**What's Defined**:
- ✅ Lifecycle events (GRANTED → CONSUMED/REVOKED/EXPIRED)
- ✅ Pending action exists before resolution
- ✅ CONSUMED marks successful redemption
- ✅ REVOKED marks rejection with refund

**What's NOT Defined**:
- ❌ Who initiates redemption (student? teacher? system?)
- ❌ When/how redemption is initiated (immediately on grant? UI flow? time-based?)
- ❌ What validates a redemption request
- ❌ What teacher must verify/decide during approval
- ❌ Redemption repeatability (one-time terminal or multiple uses?)
- ❌ Refund/reversal semantics (coordinate with Ledger? automatic?)

---

## III. Contract Questions Requiring Authority

### Question 1: Redemption Submission Authority

**Question**: Who is authorized to submit a delayed-use redemption?

**Options**:
A) **Student-initiated** — Student submits redemption request from their dashboard; teacher reviews and approves/rejects
B) **Teacher-initiated** — Teacher submits redemption on behalf of student (e.g., applying makeup work)
C) **Both** — Student or teacher can initiate redemption
D) **System-automatic** — Redemption auto-triggered on configured condition (time, score, etc.)

**Implication**: Determines FEAT submission authorization (student vs teacher route)

---

### Question 2: Redemption Submission Trigger

**Question**: When is a delayed-use redemption submitted?

**Options**:
A) **Immediate on grant** — Redemption automatically created when entitlement granted (pending action exists immediately)
B) **On-demand via UI** — Student clicks "Redeem" button or teacher selects action; submission is explicit user action
C) **After time window** — Submission allowed only after configured duration (e.g., "can redeem after 24 hours")
D) **On event** — Submission triggered by external event (scheduled job, teacher action, policy milestone)

**Implication**: Determines whether FEAT-STOR-DELAYED_REDEEM-SUBMIT exists or if redemption IS the pending action creation

---

### Question 3: Redemption Request Validation

**Question**: What facts must be validated when a delayed-use redemption is submitted?

**Options**:
A) **Minimal** — Just verify entitlement exists and is GRANTED (non-terminal)
B) **Policy-based** — Verify eligibility per product policy (e.g., only after 48-hour hold, or on school days only)
C) **Cross-domain** — Verify external conditions (e.g., student attendance ≥ threshold, no active obligations)
D) **Product-specific** — Validation rules defined in Policies product configuration

**Implication**: Determines what StorePolicyResolver must resolve for redemption eligibility

---

### Question 4: Redemption Subject/Payload

**Question**: What information does a delayed-use redemption request contain?

**Options**:
A) **Minimal** — Just entitlement_id (entitlement already exists, student just says "redeem me")
B) **Purpose statement** — Student provides optional reason/explanation for redemption
C) **Temporal marker** — Redemption specifies WHEN the benefit should apply (e.g., "apply this bonus to today's work")
D) **Product-specific data** — Varies by product (e.g., for "use any perk" entitlements, student specifies WHICH perk to activate)

**Implication**: Determines payload structure in pending_action

---

### Question 5: Redemption Approval Conditions

**Question**: What conditions must teacher verify before approving a delayed-use redemption?

**Options**:
A) **Automatic** — If submitted validation passes, auto-approve on next system tick
B) **Automatic after timeout** — Auto-approve if no teacher objection after X hours
C) **Manual review required** — Teacher must explicitly click "Approve"; no auto-approval
D) **Product-dependent** — Approval requirement varies by product policy configuration

**Implication**: Determines whether resolution is automatic/deferred vs manual

---

### Question 6: Rejection Semantics (REVOKED vs Return to GRANTED)

**Question**: When a teacher rejects a delayed-use redemption request, what happens?

**Options**:
A) **Record REVOKED** — Entitlement receives a REVOKED terminal event; entitlement becomes unusable
B) **Return to GRANTED** — Entitlement stays GRANTED; pending_action deleted without terminal event; student can resubmit
C) **Defer rejection** — Entitlement stays in intermediate state; student can retry after time window
D) **Product-dependent** — Varies by product policy

**Implication**: Determines whether rejected redemptions are refundable vs permanently consumed

---

### Question 7: Refund/Reversal Coordination

**Question**: When a redemption is rejected (if REVOKED), how is the refund/reversal coordinated?

**Options**:
A) **Automatic via Ledger** — System automatically credits Ledger on REVOKED event
B) **Manual teacher action** — Teacher issues refund through separate process
C) **Deferred** — No automatic refund; teacher handles out-of-band
D) **Product-dependent** — Varies by product configuration

**Implication**: Determines cross-domain coordination with Ledger domain

---

### Question 8: Redemption Repeatability

**Question**: Can the same delayed-use entitlement be redeemed multiple times?

**Options**:
A) **One-time only** — CONSUMED is terminal; no further redemption possible
B) **Repeatable** — Multiple CONSUMED events can exist for same entitlement_id; entitlement can be redeemed multiple times
C) **Product-dependent** — Varies by product policy (e.g., "use once per week" vs "unlimited uses")
D) **Quantity-based** — Grant specifies quantity; each redemption consumes one unit

**Implication**: Determines whether multiple pending actions can exist for single entitlement

---

### Question 9: Expiration Boundary

**Question**: What triggers the EXPIRED event for delayed-use entitlements?

**Options**:
A) **Fixed deadline** — EXPIRED recorded at policy-configured absolute time (e.g., "expires June 30")
B) **Relative window** — EXPIRED recorded after duration from grant (e.g., "expires 30 days after grant")
C) **End of period** — EXPIRED recorded at end of rent period or class semester
D) **No expiration** — Only CONSUMED or REVOKED; no automatic expiration

**Implication**: Determines whether read-side must periodically check expiration vs event-driven marking

---

## IV. Proposed Baseline Contract

**Until authority clarifies above questions, the following baseline contract is proposed**:

### Submission (FEAT-STOR-DELAYED_REDEEM-SUBMIT)

**Submitted By**: Student (on-demand)

**Submission Trigger**: Student clicks "Redeem" button in dashboard or item view

**Preconditions**:
- Entitlement exists with `entitlement_type='DELAYED_USE'` and `event_type='GRANTED'`
- Entitlement has no terminal event (CONSUMED, REVOKED, EXPIRED)
- Current timestamp is before entitlement expiration boundary (per policy)
- No prior pending_action exists for this entitlement (one redemption at a time)
- Student authorization verified (owns the entitlement seat)

**Validation**:
- Verify entitlement still GRANTED
- Resolve policy from policy_uuid
- Check policy eligibility rules (but flag for teacher review, don't reject)
- Verify not expired per policy config

**Execution**:
1. Create pending_action row:
   - `entitlement_id`: from GRANTED event
   - `correlation_id`: unique per submission (idempotent)
   - `authoritative_feat`: "FEAT-STOR-DELAYED_REDEEM-RESOLVE"
   - `payload`: 
     ```json
     {
       "redemption_subject": {},  // product-specific data if any
       "submitted_by_seat_id": student_seat_id,
       "submitted_at_timestamp": now,
       "policy_uuid": policy_uuid,  // IMMUTABLE
       "eligibility_flags": { /* warnings for teacher */ }
     }
     ```
2. Return success with pending_action_id

**Result**: Entitlement remains GRANTED; pending_action created; awaits teacher resolution

---

### Resolution (FEAT-STOR-DELAYED_REDEEM-RESOLVE)

**Resolved By**: Teacher (manual review)

**Preconditions**:
- Pending action exists and belongs to teacher's class
- Teacher authorized for class
- Entitlement still GRANTED (not terminal)
- Policy still resolvable from policy_uuid

**Resolution Path A: APPROVED**

1. Revalidate eligibility
2. Write CONSUMED entitlement event:
   - `event_type='CONSUMED'`
   - `payload`: { redemption_subject, policy_uuid, approved_at, teacher_seat_id }
3. Delete pending_action
4. Commit atomically
5. Return success with event_id

**Resolution Path B: REJECTED**

1. Write REVOKED entitlement event:
   - `event_type='REVOKED'`
   - `payload`: { redemption_subject, rejection_reason, policy_uuid }
2. (Optional) Coordinate Ledger credit if product requires refund
3. Delete pending_action
4. Commit atomically
5. Return success with event_id

---

## V. Policy-UUID Immutability Rule (All Workflows)

**All delayed-use redemption FEATs SHALL enforce**:

- `pending_action.payload.policy_uuid` stores exact immutable reference to policy at submission time
- On resolution, policy is resolved from UUID via `StorePolicyResolver`
- While pending_action exists, policy must remain resolvable (is executable dependency)
- If policy deleted while pending_action references it, deletion must fail

---

## VI. Test Coverage Required

### Submission Tests (Proposed)

- Valid redemption submission creates pending_action with policy_uuid immutable
- Idempotent: retrying same correlation_id returns same pending_action_id
- Entitlement not GRANTED rejected (ENTITLEMENT_NOT_GRANTED)
- Entitlement already terminal rejected (ENTITLEMENT_TERMINAL)
- Expired entitlement rejected (ENTITLEMENT_EXPIRED)
- Existing pending_action prevents new submission (ONE_REDEMPTION_AT_A_TIME)
- Eligibility warnings captured in payload (but don't block submission)

### Resolution Tests (Proposed)

- Approved redemption writes CONSUMED event + deletes pending_action
- Rejected redemption writes REVOKED event + deletes pending_action + (optional) coordinates Ledger refund
- Idempotent: retrying approval returns same event_id
- Policy deletion while pending creates POLICY_DELETED error (soft failure)
- Ledger coordination failures tracked (if required)

---

## VII. Authority Checklist for Approval

Before Phase 3 implementation can proceed, authority must approve:

- [ ] **Question 1 Answer**: Student-initiated vs teacher-initiated vs system-automatic
- [ ] **Question 2 Answer**: On-demand vs time-triggered vs automatic
- [ ] **Question 3 Answer**: Validation scope (minimal, policy-based, cross-domain, product-specific)
- [ ] **Question 4 Answer**: Payload structure (minimal, purpose, temporal, product-specific)
- [ ] **Question 5 Answer**: Approval authority (automatic, manual, product-dependent)
- [ ] **Question 6 Answer**: REVOKED vs return-to-GRANTED on rejection
- [ ] **Question 7 Answer**: Refund coordination (automatic Ledger, manual, deferred, product-dependent)
- [ ] **Question 8 Answer**: Redemption repeatability (one-time, repeatable, product-dependent)
- [ ] **Question 9 Answer**: Expiration trigger (absolute, relative, period, none)

---

## VIII. Next Steps (Awaiting Authority)

**Phase 3 Implementation Blocked Until**:
- Authority answers all questions in §VII
- Contract is approved
- Policy-UUID immutability rule is confirmed
- Test coverage checklist is approved

**Phase 3 Implementation Will**:
- Implement FEAT-STOR-DELAYED_REDEEM-SUBMIT (student submission)
- Implement FEAT-STOR-DELAYED_REDEEM-RESOLVE (teacher resolution)
- Write comprehensive test coverage per approved checklist
- Integrate with StorePolicyResolver for policy resolution
- Coordinate Ledger refunds if required (per answer to Question 7)

**Phase 4 Will**:
- Audit that all delayed-use redemption mutations enter through lawful FEAT paths
- Verify atomicity of resolution (write entitlement event + delete pending_action)
- Verify idempotency via correlation_id
- Verify policy-UUID immutability

---

## IX. Appendix: Design Rationale

### Why these questions matter

- **Question 1** determines whether it's a student-self-service flow or teacher-managed flow — fundamental UX difference
- **Question 2** determines whether pending action is created immediately on grant or deferred to user action — architectural difference
- **Question 3** determines validation complexity and cross-domain dependencies
- **Question 4** determines payload complexity and product-specificity
- **Question 5** determines whether resolution is workflow (manual) or system-automatic
- **Question 6** determines whether rejection is terminal or gives student another chance
- **Question 7** determines Ledger coordination complexity
- **Question 8** determines whether multiple CONSUMED events can exist for single entitlement
- **Question 9** determines whether expiration is passive (policy boundary) or active (background job)

### Baseline rationale

The proposed baseline assumes:
- **Student-initiated** because students typically "redeem" benefits they own
- **On-demand** because redemption is a student action (not automatic system)
- **Policy-based validation** because product rules should govern eligibility
- **Minimal payload** because entitlement already exists; just signal intent
- **Manual teacher approval** for accountability and potential override
- **REVOKED on rejection** because DOM-STORE-001 explicitly says "REVOKED when redemption is rejected"
- **Automatic Ledger refund** per "refunded through the lawful reversal path"
- **One-time redemption** (but product can specify otherwise) as default safe behavior
- **Policy-boundary expiration** per policy config (absolute, relative, period as product specifies)

This baseline is **proposed for authority review**, not directive.

---

**Ready for Authority Review**: Yes. Design phase complete. Awaiting approval of Questions 1-9 and baseline contract before implementation proceeds.
