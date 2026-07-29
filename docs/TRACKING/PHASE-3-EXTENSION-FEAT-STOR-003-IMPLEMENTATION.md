# Phase 3 Extension: FEAT-STOR-003 Implementation Plan

**Reference**: FEAT-STOR-003 v2.0 (Insurance Claim Lifecycle)  
**Authority**: DOM-STORE-001 v5.0 §VIII.E.1 + §IX (Pending Action Semantics)  
**Status**: Ready for Implementation  
**Date**: 2026-07-28

---

## I. Purpose

Implement the lawful lifecycle for insurance claims through the `pending_actions` workflow.

The FEAT orchestrates:
- Pending insurance claim submission (creates pending_action)
- Teacher adjudication (reads pending_action)
- Canonical insurance claim resolution outcome (writes CONSUMED entitlement event with outcome in payload)
- Coordinated Ledger reimbursement on approval (via FEAT-LED-001)
- Atomic resolution (write CONSUMED event + delete pending_action)

**Authority Clarification**: Both approval and rejection write CONSUMED events (claim reached terminal resolution); the event payload records the decision (APPROVED vs REJECTED). Only approval triggers Ledger coordination. Rejection does not reverse the entitlement or trigger refunds (those are Ledger domain concerns). The entitlement remains GRANTED for future claims per policy.

---

## II. Scope

### In Scope for Phase 3

1. **FEAT-STOR-003-SUBMIT**: Create pending insurance claim
   - Validate entitlement and coverage
   - Validate claim subject and policy eligibility
   - Create pending_actions row with immutable policy_uuid
   - Return success or structural-validation failure

2. **FEAT-STOR-003-RESOLVE**: Adjudicate and apply claim decision
   - Read pending_action by ID
   - Revalidate entitlement and policy
   - Apply teacher decision (accept/reject)
   - For accepted: coordinate Ledger credit via FEAT-LED-001
   - Write CONSUMED entitlement event with outcome
   - Atomically delete pending_action
   - Handle idempotency

3. **Tests**: Unit tests for both FEATs covering happy path, error cases, idempotency

### Out of Scope

- UI/route wiring (Phase 7)
- Policy discovery or student-facing submission UI (Phase 5+)
- Payment processing (Ledger domain owns this)
- Payroll integration for `MANUAL_CREDIT` (Payroll domain owns this)

---

## III. Critical Architecture Rule

**Policy-UUID Immutability**:
- PendingAction SHALL store exact `policy_uuid` from entitlement
- NOT: product_id, policy config snapshot, or derived values
- On resolution: resolve policy from UUID via `StorePolicyResolver`
- While pending: policy must remain resolvable (executable dependency)

**Rationale**:
- Prevents policy-config drift between submission and resolution
- Maintains immutable historical record tied to exact policy version
- Enforces that deletion cannot happen while pending_action references it

---

## IV. FEAT-STOR-003-SUBMIT: Claim Submission

### Signature

```python
def submit_insurance_claim(
    *,
    canonical_context: CanonicalContext,  # user_id, class_id, seat_id, actor_role
    entitlement_id: str,                  # insurance entitlement being claimed against
    claim_subject: dict,                  # type-specific: {transaction_id: X} or {dates: [...]}
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimSubmissionResult:
    """Submit an insurance claim against an active entitlement."""
```

### Preconditions

1. Canonical context valid (user_id, class_id, seat_id, actor_role)
2. Entitlement exists and belongs to requesting seat
3. Entitlement references insurance product (resolved via policy_uuid)
4. Coverage cycle is currently active (canonical temporal resolution)
5. No terminal EXPIRED event exists
6. Claim subject is structurally valid (type matches policy)
7. Student is authorized to submit (or teacher-assisted submission authorized)

### Execution Sequence

```
1. Validate canonical context + seat authorization
   ↓
2. Read EntitlementEvent GRANTED for entitlement_id
   - Confirm product_id references INSURANCE type
   - Record policy_uuid from event
   ↓
3. Resolve policy via StorePolicyResolver.resolve_store_item(policy_uuid)
   - Validate insurance product type
   - Confirm coverage cycle active (via policy config + temporal context)
   ↓
4. Validate claim subject
   - If transaction insurance: validate transaction_id exists
   - If productivity insurance: validate dates are in valid range
   - Check policy eligibility rules (but don't reject; flag for teacher review)
   ↓
5. Check for existing pending_action with same correlation_id (idempotency)
   - If exists: return prior result
   ↓
6. Create pending_actions row:
   - pending_action_id: new UUID
   - class_id: from context
   - seat_id: from context
   - entitlement_id: supplied
   - correlation_id: generated or supplied (must be unique)
   - authoritative_feat: "FEAT-STOR-003-RESOLVE"
   - payload: {
       "claim_subject": claim_subject,  # {transaction_id: X} or {dates: [...]}
       "policy_uuid": policy_uuid,      # immutable reference
       "submitted_by_seat_id": seat_id,
       "submitted_at_timestamp": now,
       "policy_eligibility_flags": {    # warnings for teacher review
         "count_limit_exceeded": bool,
         "period_limit_exceeded": bool,
         "claim_window_exceeded": bool,
       }
     }
   ↓
7. Return InsuranceClaimSubmissionResult:
   - success: true
   - pending_action_id: created ID
   - correlation_id: used
   - submitted_at: timestamp
```

### Error Cases

- Invalid context → INVALID_CONTEXT
- Entitlement not found → ENTITLEMENT_NOT_FOUND
- Entitlement not insurance → WRONG_ENTITLEMENT_TYPE
- Coverage not active → COVERAGE_NOT_ACTIVE
- Coverage expired → COVERAGE_EXPIRED
- Structurally invalid subject → INVALID_CLAIM_SUBJECT
- Duplicate claim (same correlation_id) → return prior result (idempotent)

---

## V. FEAT-STOR-003-RESOLVE: Claim Adjudication

### Signature

```python
def resolve_insurance_claim(
    *,
    canonical_context: CanonicalContext,  # user_id, class_id, seat_id, actor_role (teacher)
    pending_action_id: str,
    approved: bool,
    override_reason: str | None = None,   # if approving ineligible claim
    idempotency_key: str | None = None,
) -> InsuranceClaimResolutionResult:
    """Adjudicate a pending insurance claim (approve or reject)."""
```

### Preconditions

1. Canonical context valid (actor_role must be "teacher")
2. Teacher authorized for class
3. Pending action exists and belongs to class
4. Pending action references valid entitlement
5. Entitlement still in GRANTED state (not consumed/expired/revoked)
6. Policy still resolvable from policy_uuid

### Execution Sequence

```
1. Validate canonical context + teacher authorization
   ↓
2. Read pending_action by ID
   - Confirm class_id matches context
   - Extract entitlement_id, policy_uuid, claim_subject
   ↓
3. Read EntitlementEvent GRANTED for entitlement_id
   - Confirm entitlement still exercisable
   ↓
4. Resolve policy via StorePolicyResolver.resolve_store_item(policy_uuid)
   - Confirm policy still resolvable
   - Read insurance reimbursement rules
   ↓
5. If APPROVED:
   a. Revalidate claim eligibility
   b. Resolve reimbursement amount from policy + claim subject
   c. Coordinate Ledger credit via FEAT-LED-001:
      - Call resolve_intended_ledger_plan(...)
      - Create credit for insurance reimbursement
      - Confirm Ledger accepts (ACCEPT or TRANSFORM outcome)
   d. Within same transaction:
      - Write EntitlementEvent (event_type=CONSUMED):
        * entitlement_id: from pending_action
        * event_type: CONSUMED
        * product_id: from resolved policy
        * entitlement_type: INSURANCE
        * acquisition_type: PERK
        * event_payload: {
            "claim_subject": claim_subject,
            "claim_decision": "APPROVED",
            "reimbursement_amount": amount,
            "ledger_correlation": ledger_transaction_id,
            "override_reason": override_reason (if applicable),
            "policy_uuid": policy_uuid
          }
      - Delete pending_action
      - Commit Ledger transaction
   ↓
6. If REJECTED:
   a. Write EntitlementEvent (event_type=CONSUMED with rejection marker):
      * entitlement_id: from pending_action
      * event_type: CONSUMED
      * event_payload: {
          "claim_subject": claim_subject,
          "claim_decision": "REJECTED",
          "rejection_reason": override_reason,
          "policy_uuid": policy_uuid
        }
   b. Delete pending_action
   c. No Ledger transaction (no reimbursement)
   ↓
7. Return InsuranceClaimResolutionResult:
   - success: true
   - pending_action_id: deleted
   - entitlement_event_id: created event
   - decision: "APPROVED" or "REJECTED"
   - reimbursement_amount: if approved
```

### Idempotency

- Retrying approval: check if CONSUMED event already exists for this entitlement_id
  - If yes: return prior decision result (same event_id, amount, etc.)
  - If no: proceed with resolution
- Retrying rejection: same logic

### Error Cases

- Invalid context → INVALID_CONTEXT
- Pending action not found → PENDING_ACTION_NOT_FOUND
- Teacher not authorized → UNAUTHORIZED
- Entitlement not found → ENTITLEMENT_NOT_FOUND
- Entitlement already terminal → ENTITLEMENT_TERMINAL
- Policy not resolvable → POLICY_DELETED (soft failure; pending_action becomes irresolvable)
- Ledger rejects credit → LEDGER_REJECTED (soft failure; pending_action remains)
- Duplicate resolution (already approved/rejected) → return prior result (idempotent)

---

## VI. Data Models

### InsuranceClaimSubmissionResult

```python
@dataclass
class InsuranceClaimSubmissionResult:
    success: bool
    pending_action_id: str | None
    correlation_id: str | None
    entitlement_id: str | None
    submitted_at: datetime | None
    eligibility_flags: dict | None  # warnings for teacher review
    error_code: str | None
    error_message: str | None
```

### InsuranceClaimResolutionResult

```python
@dataclass
class InsuranceClaimResolutionResult:
    success: bool
    pending_action_id: str | None  # deleted on success
    entitlement_event_id: str | None  # created CONSUMED event
    decision: str | None  # "APPROVED" or "REJECTED"
    reimbursement_amount: Decimal | None  # if approved
    ledger_transaction_id: int | None  # if approved
    error_code: str | None
    error_message: str | None
```

---

## VII. Test Coverage Required

### Submission Tests

- ✅ Valid claim submission creates pending_action with correct payload
- ✅ Policy UUID immutably stored (not config copy)
- ✅ Idempotent: retrying same correlation_id returns same pending_action_id
- ✅ Invalid entitlement rejected (ENTITLEMENT_NOT_FOUND)
- ✅ Wrong entitlement type rejected (WRONG_ENTITLEMENT_TYPE)
- ✅ Expired coverage rejected (COVERAGE_EXPIRED)
- ✅ Invalid claim subject rejected (INVALID_CLAIM_SUBJECT)
- ✅ Eligibility warnings captured in payload (but don't block)

### Resolution Tests

- ✅ Approved claim writes CONSUMED event + deletes pending_action + coordinates Ledger
- ✅ Rejected claim writes CONSUMED (with rejection marker) + deletes pending_action
- ✅ Reimbursement amount calculated correctly from policy
- ✅ Ledger credit coordinated atomically (commit or rollback with event)
- ✅ Idempotent: retrying approval returns same event_id and amount
- ✅ Failed Ledger coordination keeps pending_action (soft failure)
- ✅ Policy deletion while pending creates POLICY_DELETED error (pending_action irresolvable)

---

## VIII. Implementation Checklist

- [ ] Create `app/feats/insurance_claim_feat.py` with both FEAT functions
- [ ] Add InsuranceClaimSubmissionResult and InsuranceClaimResolutionResult dataclasses
- [ ] Integrate with `StorePolicyResolver` for policy resolution
- [ ] Integrate with `FEAT-LED-001` for Ledger coordination
- [ ] Create `tests/test_insurance_claim_feat.py` with full coverage
- [ ] Verify idempotency (correlation_id deduplication)
- [ ] Verify policy_uuid immutability (not config copy)
- [ ] Verify entitlement_events atomicity (both events + deletion commit together)
- [ ] Document endpoint/route expectations (Phase 7 concern)
- [ ] Run full test suite (Phase 8 concern)

---

**Ready to implement**: Yes. FEAT-STOR-003 has sufficient authority and clear contract. Proceed with implementation.
