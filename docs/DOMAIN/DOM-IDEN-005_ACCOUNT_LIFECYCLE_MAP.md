# DOM-IDEN-005: Account Lifecycle Map

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-IDEN-001     | 1.1     | 2026-06-05     | 1.0 | Informative     |

---

> [!NOTE]
> This is a **Non-Normative** document. It is a derivative map intended for developer onboarding and high-level visualization. All authoritative rules, schema constraints, and state definitions are owned exclusively by the `DOM-IDEN-*` series.

---

## I. Teacher Lifecycle Overview

Teacher accounts are long-lived global identities that act as class operators.

1.  **Provisioning**: A `users` record is created. The teacher has an identity but no access yet.
2.  **Activation**: The teacher completes TOTP setup and initializes their first class. They now exist in both the `users` table and a `seats` table (as `role='teacher'`).
3.  **Operation**: The teacher logs in and resolves their context. The system uses the "Sticky Context" (`last_active_seat_id`) to restore their last class.
4.  **Recovery**: If credentials are lost, the teacher initiates a student-assisted recovery request. Access is restored to the *same* record; ownership is preserved.

## II. Student Lifecycle Overview

Student accounts transition from roster-provisioned participant positions to
credentialed global users.

1.  **Rostering**: A class exists or is created, an inactive `users` auth shell is provisioned, a `seats` row is bound to the class, an `identity_profiles` row is bound one-to-one to the seat, and claim artifacts are stored on the seat. No credentials are active.
2.  **Binding (The First Claim)**: The student proves entitlement to the seat using class-local claim artifacts. The claim binds the seat to the same `users` row or to an already-authenticated compatible `users` row.
3.  **Credential Activation**: The student sets their PIN/passphrase on `users` and becomes a full economic actor through `seat_id + class_id`.
4.  **Cross-Class Participation**: The student claims a seat in a *second* class. The new `seats` row binds to the *same* existing `users` record.
5.  **Recovery**: If credentials are lost, a teacher generates a reset code. The student re-sets their credentials on the same identity.
6.  **Class Re-entry**: If `last_active_class_id` is missing or stale, login may surface explicit class selection only when at least one valid seat still exists. The selector is a boundary, not a recovery helper; hard fail only occurs when no valid class/seat pair remains.

## III. Key State Transitions

| Action | Impact | Primary Domain |
| :--- | :--- | :--- |
| **Initialize Teacher** | Creates `users` row. | `DOM-IDEN-003` |
| **Upload Roster** | Provisions inactive `users`, `seats`, `identity_profiles`, and seat-owned claim artifacts. | `DOM-IDEN-001` |
| **Claim Seat** | Proves entitlement to a class-local seat and binds `user_id` to `seat_id`. | `DOM-IDEN-001` |
| **Setup PIN** | Activates global login capability on `users`. | `DOM-IDEN-001` |
| **Select Class Context** | Explicitly chooses a valid class/seat pair when persisted class preference is missing or stale. | `DOM-IDEN-001` |
| **Initiate Reset** | Initiates a recovery process targeting the existing `users` record. | `DOM-IDEN-002` / `004` |
| **Switch Class** | Initiates a recovery process targeting the existing `users` record. | `DOM-IDEN-001` |

---

## IV. Relationship to Implementation

This map provides the "Human Story" of the identity model. Developers should always refer to the **Normative Schema Contracts** in `DOM-IDEN-001` and `DOM-IDEN-003` for field-level implementation details.
