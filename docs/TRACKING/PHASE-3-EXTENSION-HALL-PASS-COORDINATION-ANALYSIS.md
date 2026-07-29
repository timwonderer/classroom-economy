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

## Proposed Coordination Models

### Model A: Synchronous Call Within Store/Ent FEAT

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

## Authority Documents Consulted

1. **INV-ARC-021** (Cross-Domain Coordination):
   - FEAT is sole coordination layer
   - All cross-domain logic within FEAT
   - No domain-to-domain calls allowed (only via FEAT layer)
   - Implies: Store/Ent FEAT calls Prod FEAT or Prod service

2. **DOM-LED-001** (Ledger):
   - Shows Ledger as domain-blind (doesn't know business meaning)
   - Implies Prod would be similar (doesn't know Store/Ent semantics)

3. **FEAT-LED-001** (Ledger Posting):
   - Called from Store/Ent FEATs
   - Single transaction boundary
   - Suggests Model A pattern

4. **FEAT-PROD-002** (Hall Pass Logging):
   - Currently stands alone
   - Would need refactoring for coordination with Store/Ent
   - Currently consumes entitlements; future model unclear

---

## Recommendation for Authority Decision

**The authority must clarify**:

1. **Is the coordination synchronous (Model A/C) or asynchronous (Model B)?**
   - If synchronous: Store/Ent calls Prod FEAT/API; waits for completion
   - If asynchronous: Store/Ent submits request; Prod completes independently

2. **What is the transaction boundary?**
   - Single transaction (not possible across separate DB connections)
   - Coordinated via idempotency keys and correlation IDs
   - Eventual consistency with background job completion

3. **If Prod succeeds but Store/Ent fails, what is the recovery?**
   - Background job retries? Idempotency ensures no duplicate?
   - Manual recovery process?

4. **Can we use existing FEAT-LED-001 pattern?**
   - If yes: Store/Ent calls Prod synchronously within same FEAT/transaction
   - If no: What pattern should be used instead?

---

## Next Step

**Do not implement hall-pass coordination until authority answers**:
- [ ] Coordination model (sync vs async)
- [ ] Transaction boundary semantics
- [ ] Failure recovery path
- [ ] Whether FEAT-LED-001 pattern is applicable

---

**Status**: Analysis Complete  
**Blocking**: Authority decision on coordination model  
**Action**: Ask authority which model is intended (A, B, or C) and confirm transaction boundary semantics
