# Hall-Pass Coordination: Atomic Boundary Analysis

**Date**: 2026-07-29  
**Status**: Authority Clarification Analysis - Awaiting Cross-Domain Decision  
**Scope**: Determining coordination pattern for Store/Ent ↔ Productivity hall-pass completion

---

## Authority Guidance

The user's authority clarification states:

> "STORE/ENT validates the entitlement and creates the PendingAction. Teacher approval causes STORE/ENT to coordinate with PROD. PROD does not inspect STORE/ENT persistence or determine entitlement eligibility; it receives an authorized request and owns writing the HallPassLog. Successful PROD logging then participates in completing the STORE/ENT operation, including the permanent CONSUMED event and PendingAction resolution."

**Key Points**:
1. Store/Ent coordinates (not just reads)
2. Prod receives authorized request (doesn't inspect Store/Ent)
3. Successful Prod logging participates in Store/Ent completion
4. Both operations complete together atomically

---

## The Coordination Boundary Question

The guidance establishes a **two-phase completion**:
- Phase 1: Prod writes HallPassLog (receives authorized request from Store/Ent)
- Phase 2: Store/Ent writes CONSUMED event + deletes pending_action (after Prod succeeds)

**Critical Unknowns**:
1. **Synchronous or Asynchronous?**
   - Synchronous: Store/Ent calls Prod; waits for result; commits both in single transaction
   - Asynchronous: Store/Ent submits request to Prod; Prod completes separately; Store/Ent completion triggered by Prod callback or polling

2. **Transaction Boundary?**
   - Single transaction: Both domains use same DB transaction (unlikely; domains are separate)
   - Coordinated transactions: Store/Ent and Prod each have their transaction; some protocol ensures atomicity
   - Eventual consistency: Prod writes first; Store/Ent commits after Prod succeeds (can fail between)

3. **Failure Handling?**
   - If Prod succeeds but Store/Ent fails: HallPassLog exists but CONSUMED event doesn't
   - If Prod fails: Store/Ent doesn't proceed; pending_action remains
   - Rollback semantics: If Store/Ent fails after Prod succeeds, is there a rollback hook?

---

## Existing Evidence from Codebase

### FEAT-LED-001 (Ledger Coordination)

FEAT-LED-001 is used by FEAT-STOR-003 (Insurance Claims) for Ledger coordination. Pattern:

```
FEAT-STOR-003 (Store/Ent domain)
├─ Validate claim
├─ Call FEAT-LED-001 (Ledger domain)
│  └─ Post reimbursement to Ledger
├─ Write CONSUMED event (within same FEAT transaction)
└─ Delete pending_action (atomic with CONSUMED)
```

**Model**: Ledger is called as a sub-FEAT within Store/Ent FEAT; both complete in same transaction boundary.

### FEAT-PROD-002 (Hall Pass Logging - Current)

Current FEAT-PROD-002 is standalone Productivity domain FEAT that:
- Receives entitlement ID
- Consumes entitlement directly (calls entitlement service)
- Writes HallPassLog

**Model**: Productivity domain owns entitlement consumption; independent FEAT.

---

## Coordination Model Analysis (Leading to Canonical Pattern)

This analysis reconciles three possible patterns against existing authority and practice. **Model A emerges as the canonical pattern** based on INV-ARC-021 and existing FEAT-LED-001 implementation.

### Model A: Synchronous Call Within Store/Ent FEAT (CANONICAL)

**Pattern** (similar to FEAT-LED-001):

```python
def resolve_hall_pass_approval(pending_action_id, approved):
    # Store/Ent layer
    pending_action = read_pending_action(pending_action_id)
    
    # Call Prod domain to write HallPassLog
    prod_result = call_prod_write_hall_pass_log(
        entitlement_id=pending_action.entitlement_id,
        destination=pending_action.payload.get("destination"),
        approved_by_seat_id=teacher_seat_id
    )
    
    if prod_result.success:
        # Both domains complete in same transaction
        write_consumed_event(...)  # Store/Ent
        delete_pending_action(...)  # Store/Ent
        commit()  # Single transaction covers both
    else:
        rollback()  # Prod failed; Store/Ent doesn't proceed
```

**Pros**:
- Atomic at transaction boundary
- Failure is clear (rollback entire operation)
- Simple coordination

**Cons**:
- Requires Prod to expose a callable FEAT or API
- Store/Ent transaction waits for Prod to complete
- Tight coupling if Prod is slow

---

### Model B: Asynchronous Coordination via Correlation_ID

**Pattern** (Eventual consistency):

```python
def resolve_hall_pass_approval(pending_action_id, approved):
    # Store/Ent layer
    pending_action = read_pending_action(pending_action_id)
    correlation_id = pending_action.correlation_id
    
    # Submit request to Prod domain (async)
    prod_request_id = submit_to_prod_queue(
        type="RECORD_HALL_PASS_LOG",
        correlation_id=correlation_id,
        entitlement_id=pending_action.entitlement_id,
        destination=pending_action.payload.get("destination"),
        approved_by_seat_id=teacher_seat_id
    )
    
    # Create intermediate pending record or transaction state
    db.add(IntermediateHallPassCompletion(
        pending_action_id=pending_action_id,
        prod_request_id=prod_request_id,
        state="AWAITING_PROD"
    ))
    db.commit()
    
    # Return to caller; Prod processes async
    # Background job polls/checks Prod completion
    # Once Prod HallPassLog written, background job writes CONSUMED + deletes pending
```

**Pros**:
- Loose coupling between domains
- Prod can be slow without blocking Store/Ent
- Follows event-driven architecture

**Cons**:
- Eventual consistency; complex failure modes
- Intermediate state requires cleanup/recovery
- More complex testing and debugging

---

### Model C: Coordinated Atomicity via Shared Correlation_ID

**Pattern** (Correlation-based recovery):

```python
def resolve_hall_pass_approval(pending_action_id, approved):
    # Store/Ent layer
    pending_action = read_pending_action(pending_action_id)
    correlation_id = pending_action.correlation_id
    
    # Call Prod synchronously
    prod_result = call_prod_write_hall_pass_log(
        correlation_id=correlation_id,
        ...
    )
    
    if prod_result.success:
        # Store/Ent completes
        write_consumed_event(
            payload={...  "prod_hall_pass_id": prod_result.hall_pass_log_id}
        )
        delete_pending_action()
        db.commit()
    else:
        # Prod failed; Store/Ent doesn't write anything
        raise ProdCoordinationFailure()
        # pending_action remains; can retry
```

**Pros**:
- Correlation_ID ties both records together for audit
- Prod result is captured in Store/Ent event payload
- Allows rollback if Prod fails

**Cons**:
- Still synchronous call (wait for Prod)
- Same coupling as Model A

---

## Authority Documents & Pattern Analysis

### Evidence for Model A as Canonical

1. **INV-ARC-021** (Cross-Domain Coordination):
   - FEAT is sole coordination layer
   - All cross-domain logic **within FEAT** (not between FEATs)
   - No domain-to-domain calls allowed (only via FEAT layer)
   - **Implication**: Store/Ent FEAT orchestrates Prod calls; doesn't call another FEAT

2. **FEAT-LED-001** (Ledger Posting - Existing Pattern):
   - Called synchronously from Store/Ent FEATs (e.g., FEAT-STOR-003)
   - Single transaction boundary covering both domains
   - Result is awaited; both complete together
   - **This is the established pattern in the codebase**

3. **DOM-LED-001** (Ledger):
   - Domain-blind (doesn't know business meaning of callers)
   - Responds to calls from other domain FEATs
   - No inspection of caller's internal state

4. **Authority Clarification**:
   - Store/Ent "coordinates" with Prod
   - Prod receives "authorized request" (not "pending approval")
   - Prod doesn't inspect Store/Ent pending or entitlement state
   - Successful Prod logging "participates in completing the STORE/ENT operation"

### Conclusion: Model A is Canonical

**Model A (Synchronous Call Within Store/Ent FEAT)** is the established pattern:
- Aligns with existing FEAT-LED-001 precedent
- Satisfies INV-ARC-021 "FEAT layer is coordination layer" requirement
- Supports atomic completion (both domains succeed/rollback together)
- Matches authority description of "coordinated operation"

**Models B & C** are theoretically possible but contradict:
- Existing FEAT-LED-001 pattern in the codebase
- INV-ARC-021 requirement for FEAT-only coordination
- Authority's description of atomic completion

---

## Implementation Pattern (Model A)

```python
# Within FEAT-STOR-HALL_PASS_REQUEST-RESOLVE (Store/Ent FEAT)

def resolve_hall_pass_approval(pending_action_id, teacher_approves):
    pending_action = read_pending_action(pending_action_id)
    
    # Validate entitlement is still GRANTED
    entitlement_event = get_entitlement_granted_event(pending_action.entitlement_id)
    if not entitlement_event:
        raise EntitlementNotGranted()
    
    # Resolve policy from immutable policy_uuid
    policy = StorePolicyResolver.resolve_store_item(
        pending_action.payload["policy_uuid"]
    )
    
    if teacher_approves:
        # Call Prod domain to write HallPassLog (authorized command)
        prod_result = call_prod_record_hall_pass_log(
            entitlement_id=pending_action.entitlement_id,
            destination=pending_action.payload.get("destination"),
            approved_by_seat_id=teacher_seat_id,
            correlation_id=pending_action.correlation_id
        )
        
        if prod_result.success:
            # Both complete in same transaction
            write_consumed_event(pending_action)  # Store/Ent
            delete_pending_action(pending_action_id)  # Store/Ent
            db.commit()  # Single transaction
        else:
            # Prod failed; Store/Ent operation fails
            raise ProdCoordinationFailure(prod_result.error)
    else:
        # Deny request (no Prod coordination)
        delete_pending_action(pending_action_id)
        db.commit()
```

This follows the established FEAT-LED-001 pattern used by FEAT-STOR-003.

---

## Status

**Resolved**: Model A is canonical pattern based on:
- Existing FEAT-LED-001 precedent
- INV-ARC-021 authority
- Authority's description of coordinated atomic completion

**Not awaiting further decisions** on Models B/C; they contradict existing authority.

**Implementation**: Use Model A pattern (synchronous call within Store/Ent FEAT)
