# Ticket Lifecycle Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|FEAT-TICK-001| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose
To define the required lifecycle, role boundaries, and integrity constraints for student support tickets and system bug escalation.

## II. Scope
This specification applies to support ticket behavior for Student, Teacher, and Sysadmin/Developer roles across ticket submission, review, escalation, technical resolution, economic correction, and closure.

## III. Authority Level
Normative (Tier 2). This document derives from constitutional and domain constraints and must not conflict with Tier 0 or Tier 1 authority.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_Authority_Model.md`
- `DOM-ECON-002_Economy_Specification.md`
- `ARC-OPS-007_Database_Schema.md`

## V. Design Principles

### 1. Teacher Owns Classroom Reality
- The teacher shall control final resolution for issues that affect classroom economic state.
- A developer shall not close tickets.
- A developer may only resolve technical behavior and return the ticket to teacher review.
- A ticket shall not enter `CLOSED` without teacher action.

### 2. Developer Owns System Behavior
- A developer shall act only on tickets escalated by a teacher for bug or malfunction conditions.
- Developer responsibility shall include log diagnosis, root-cause analysis, behavior fix, and technical resolution notes.
- A developer shall not modify classroom ledger transactions.

### 3. Append-Only Ledger Integrity
- Economic corrections must be performed using compensating transactions.
- Direct mutation of historical ledger entries is prohibited.
- Tickets may reference transaction identifiers but shall not provide ledger edit controls.

## VI. Ticket State Machine

### 1. States
- `OPEN`
- `TEACHER_REVIEW`
- `ESCALATED_TO_DEV`
- `DEV_RESOLVED`
- `TEACHER_FINAL_REVIEW`
- `CLOSED`

### 2. State Invariants
- Only teachers may transition a ticket to `CLOSED`.
- Tickets in `ESCALATED_TO_DEV` are developer-owned for technical investigation.
- Tickets in `TEACHER_FINAL_REVIEW` are teacher-owned for classroom correctness validation.

## VII. Lifecycle Flow

### 1. Student Files Ticket (`OPEN`)
- Student submits issue details (`ticket_type`, `description`, context).
- System must capture ticket metadata, timestamps, and available request diagnostics.
- Ownership is assigned to teacher.

### 2. Teacher Initial Review (`TEACHER_REVIEW`)
- Teacher reviews the issue and determines whether to resolve or escalate.
- If classroom correction is sufficient, ticket transitions to `TEACHER_FINAL_REVIEW`.
- If system malfunction is suspected, ticket transitions to `ESCALATED_TO_DEV`.

### 3. Teacher Escalation (`ESCALATED_TO_DEV`)
- Escalation must attach relevant evidence where available, including `related_transaction_ids`, incident timestamp, seat public actor identifier, and endpoint name or route reference.
- Teacher notes are permitted while escalated.
- Teacher resolution actions are blocked while escalated.

### 4. Developer Resolution (`DEV_RESOLVED`)
- Developer investigates logs, traces, endpoint behavior, and relevant data state.
- Developer may append notes and mark technical fix complete.
- On developer resolution, ticket must transition to `DEV_RESOLVED` and return to teacher ownership.

### 5. Teacher Final Review (`TEACHER_FINAL_REVIEW`)
- Teacher confirms technical fix validity and classroom ledger correctness.
- Teacher may execute compensating transactions when economic correction is required.
- Teacher may provide final explanation to student.

### 6. Closure (`CLOSED`)
- Teacher executes closure.
- Closure must persist `teacher_id`, `resolution_summary`, and `closed_at`.
- Closed tickets are immutable except for authorized administrative audit pathways.

## VIII. State Transition Table

| From | Action | To | Actor |
|------|--------|----|-------|
| `OPEN` | Teacher opens ticket workflow | `TEACHER_REVIEW` | Teacher |
| `TEACHER_REVIEW` | Resolve | `TEACHER_FINAL_REVIEW` | Teacher |
| `TEACHER_REVIEW` | Escalate | `ESCALATED_TO_DEV` | Teacher |
| `ESCALATED_TO_DEV` | Developer resolves | `DEV_RESOLVED` | Developer |
| `DEV_RESOLVED` | Teacher review | `TEACHER_FINAL_REVIEW` | Teacher |
| `TEACHER_FINAL_REVIEW` | Close | `CLOSED` | Teacher |

Developer transition to `CLOSED` is prohibited.

## IX. Ticket Metadata Requirements

### 1. Required Fields
- `ticket_id`
- `join_code`
- `actor_public_id` — UUID-encoded `Seat.public_id` under the ticket's `class_id`
- `ticket_type`
- `status`
- `description`
- `created_at`
- `updated_at`
- `escalated_at`
- `dev_resolved_at`
- `closed_at`

### 2. Recommended Diagnostic Fields
- `related_transaction_ids`
- `endpoint_name`
- `error_log_reference`
- `user_agent`

## X. Interface Behavior Requirements

### 1. Teacher Interface
- Teacher views must show open tickets, escalated tickets, and developer-resolved tickets awaiting teacher review.
- Tickets returned from developer resolution shall display a clear status marker: `Developer Fix Applied - Teacher Review Required`.

### 2. Developer Interface
- Developer views shall include escalated tickets only.
- Developer views shall not expose or permit mutation of classroom balances.
- Developer views may include logs, traces, and related transaction identifiers.

## XI. Economic Correction Flow
- Financial error correction must be teacher-initiated from ticket context.
- Permitted correction patterns include refund, payroll correction, penalty reversal, and insurance reimbursement.
- Every correction must generate a new ledger entry.
- Direct mutation or deletion of prior ledger entries is prohibited.

## XII. Optional Enhancements
- Automatic log capture at ticket creation (short rolling error and endpoint context).
- First-class transaction attachments to improve developer diagnosis.
- Ticket analytics for type frequency, bug frequency, and resolution latency.

## XIII. Anti-Goals
- Ledger editing capability is prohibited.
- Developer closure capability is prohibited.
- Exposure of student identity outside class-scoped seat public identifiers and class context is prohibited.
- Teacher mutation of system logs is prohibited.

## XIV. Amendment
Changes to this specification must preserve role separation (teacher economic authority vs. developer system authority) and append-only ledger integrity, and must be reviewed for consistency with `DOM-ECON-002` and applicable constitutional documents before adoption.
