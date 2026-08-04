# Phase 3 Extension: Document Reconciliation & Authority Reconciliation

**Date**: 2026-07-29  
**Status**: ✅ Document reconciliation complete; obsolete baselines removed; authority clarifications established as controlling  
**Reference**: Authority clarifications from user guidance on all three pending_actions workflows

---

## Reconciliation Objectives

Per user guidance:
1. Remove obsolete baseline proposals that conflict with newer authority clarifications
2. Clarify that newer clarifications supersede earlier baselines
3. Treat A/B/C hall-pass models as analysis leading to Model A conclusion, not alternatives
4. Reduce delayed-use authority questions by separating policy-config from authority-decisions
5. Verify policy_uuid storage location from canonical persistence authority

---

## Changes Made

### Path 1: Insurance Claims (FEAT-STOR-003) — No Changes Required

**Status**: Already aligned with authority clarifications

All earlier baseline proposals were correct:
- ✅ Both approval and rejection write CONSUMED events (already specified in implementation doc)
- ✅ Only approval triggers Ledger coordination (already specified)
- ✅ Rejection doesn't reverse entitlement (already specified)
- ✅ Policy-UUID immutably stored in payload (already specified)

**Only addition**: Added clarification note on authority rationale for CONSUMED-in-both-paths.

---

### Path 2: Delayed-Use Redemption — Significant Reconciliation

**Removed Obsolete Proposals**:

❌ **Question 6: Rejection Outcome** (Removed)
- Previous baseline assumed authority might decide between REVOKED vs return-to-GRANTED
- Authority clarified: Rejection is DENY REQUEST only, no terminal event, entitlement stays GRANTED
- This was AUTHORITY DECISION, not optional—now established, not a question

❌ **Question 7: Refund Coordination** (Removed)
- Previous baseline proposed Ledger coordination on rejection
- Authority clarified: No refund on denial; purchase reversal is Ledger domain's separate concern
- This was ruled out by authority, not a question

❌ **Questions 8-9 Reclassified** (Moved from authority questions to policy-configuration):
- **Previous Q8: Redemption Repeatability** → Now policy-configuration (product policy, not authority)
  - Per DOM-STORE-001: Repeatability is determined by product (one-time vs repeatable)
  - Authority doesn't decide this; product policy does
  
- **Previous Q9: Expiration Trigger** → Now policy-configuration (product policy, not authority)
  - Per DOM-STORE-001: Expiration trigger is configured per product policy
  - Authority doesn't decide this; product policy does

**Result**: Reduced from 9 authority questions to 5 genuine workflow/authorization decisions

**5 Remaining Authority Questions** (Workflow/Authorization Policy):
1. Submission authority (student, teacher, system, both?)
2. Submission trigger (on-demand, time-based, automatic, policy-dependent?)
3. Validation scope (hard block vs flag for teacher review?)
4. Payload structure (what type-specific data?)
5. Approval authority (manual, automatic, policy-dependent?)

**Updated Documents**:
- `PHASE-3-EXTENSION-DELAYED-USE-REDEMPTION-DESIGN.md` §VII — Reduced questions, clarified policy-config vs authority-decisions
- `PHASE-3-EXTENSION-STATUS.md` Path 2 — Updated to reflect 5 decisions, not 9 questions

---

### Path 3: Hall-Pass Coordination — Major Clarifications

**Removed Obsolete Baseline**:

❌ **Coordination Model Presented as Three Alternatives**
- Previous baseline presented Models A, B, C as equally authoritative alternatives
- Authority clarifications + architectural analysis establish Model A as canonical

**Authority Clarifications Applied**:

✅ **Model A is Canonical** (Synchronous call within Store/Ent FEAT)
- Aligns with INV-ARC-021 ("FEAT is sole coordination layer")
- Matches existing FEAT-LED-001 precedent (Ledger coordination within Store/Ent FEAT)
- Authority confirmed: coordinated operation with Prod receiving authorized command
- Establishes single transaction boundary for atomic completion

❌ **Removed**: Productivity domain "reads pending_action status before accepting pass log"
- Earlier baseline assumed Prod inspects Store/Ent pending_action status
- Authority clarified: Prod receives **authorized command**, does NOT inspect Store/Ent state
- Prod is domain-blind to pending_action semantics; only receives authorization decision

**Result**: No further authority decision needed on coordination model; pattern is established

**Updated Documents**:
- `PHASE-3-EXTENSION-HALL-PASS-COORDINATION.md` — Updated to reflect Model A as canonical
- `PHASE-3-EXTENSION-HALL-PASS-COORDINATION-ANALYSIS.md` — Reframed analysis to establish Model A conclusion, not present alternatives
- `PHASE-3-EXTENSION-STATUS.md` Path 3 — Updated to reflect established pattern

---

## Policy-UUID Storage Verification

**Authority Source**: DOM-STORE-001 v5.0 §VII.B (Canonical Persistence)

**Verified**: `policy_uuid` is stored in `payload`, NOT as a first-class PendingAction field

**Schema Definition** (from DOM-STORE-001):
- `pending_action_id` — primary key
- `class_id` — class boundary
- `seat_id` — seat that submitted/affected
- `correlation_id` — cross-domain lineage
- `entitlement_id` — entitlement being acted upon
- `authoritative_feat` — FEAT that resolves this action
- `payload` — canonical typed request inputs
- `submitted_at` — submission timestamp

**Rationale**: `policy_uuid` is type-specific request data (not a universal PendingAction field), so it belongs in the type-specific `payload` field per DOM-STORE-001 §VII.B ("canonical typed request envelope").

**Verification Results**:
- ✅ FEAT-STOR-003 spec: `payload.policy_uuid` (correct)
- ✅ Delayed-use spec: `payload.policy_uuid` (correct)
- ✅ Hall-pass spec: `payload.policy_uuid` (correct)

All implementation specs correctly reflect this schema.

---

## Authority Clarifications Now Controlling

**Established Order of Authority** (newer supersedes earlier):

1. **Canonical Persistence Authority** (DOM-STORE-001 v5.0)
   - Defines pending_actions schema: 8 fields, no policy_uuid as first-class
   - Defines entitlement lifecycle: terminal events (CONSUMED, EXPIRED, REVOKED)

2. **Workflow Authority Clarifications** (User guidance 2026-07-29)
   - Insurance: Both approval and rejection write CONSUMED (claim reached terminal resolution)
   - Delayed-use: Rejection is DENY REQUEST only (no terminal event, entitlement stays GRANTED)
   - Hall-pass: Coordinated operation with Prod; Prod receives authorized command, doesn't inspect Store/Ent

3. **Earlier Baselines** (Now Superseded)
   - Delayed-use proposed REVOKED on rejection → Superseded by DENY REQUEST clarification
   - Delayed-use proposed Ledger refund → Superseded by "Ledger owns reversal" clarification
   - Hall-pass proposed Prod reads pending_action → Superseded by "Prod receives authorized command" clarification
   - Hall-pass presented three models equally → Superseded by Model A as canonical per FEAT-LED-001 precedent

---

## No Ambiguity Going Forward

**For Implementation Teams**:

1. **Policy-UUID Storage**: Always goes in `payload` per DOM-STORE-001 schema (verified)
2. **Denial Semantics**: 
   - Delayed-use: DENY REQUEST only; pending_action deleted; entitlement stays GRANTED; no event
   - Hall-pass: DENY REQUEST only; pending_action deleted; entitlement stays GRANTED; no event
3. **Approval Semantics**:
   - Insurance: CONSUMED event written; Ledger coordinated (atomic)
   - Delayed-use: CONSUMED event written; no Ledger coordination
   - Hall-pass: CONSUMED event written; Prod coordination (atomic)
4. **Coordination Pattern**: Model A (synchronous call) per existing FEAT-LED-001 precedent

---

## Summary of Reductions

| Path | Before | After | Reduction | Reason |
|------|--------|-------|-----------|--------|
| **Delayed-Use** | 9 questions | 5 decisions | -4 questions | Questions 6-9 clarified/reclassified; not authority decisions |
| **Hall-Pass** | 8 questions + Model A/B/C analysis | 5 decisions + Model A canonical | -3 questions, -2 models | Coordination pattern established; Models B/C contradict existing authority |
| **Insurance** | - | - | - | No changes; already aligned |

---

## Verification Checklist

- ✅ No conflicting baselines remain in documents
- ✅ All earlier proposals that contradict authority clarifications have been removed
- ✅ Authority clarifications are clearly marked as controlling
- ✅ Policy-configuration parameters separated from authority decisions
- ✅ Policy-UUID storage verified from canonical authority (payload, not first-class)
- ✅ All three workflows document immutable policy-UUID storage correctly
- ✅ Model A established as canonical; A/B/C analysis shows how it was determined
- ✅ Delayed-use reduced from 9 questions to 5 genuine workflow/authorization decisions
- ✅ Hall-pass reduced from 8 questions to established pattern + 5-decision alignment

---

**Status**: ✅ Complete  
**Documents Reconciled**: 5  
**Obsolete Proposals Removed**: 7  
**Policy-UUID Verification**: ✅ Confirmed in payload (not first-class field)  
**Authority Clarifications**: ✅ Established as controlling
