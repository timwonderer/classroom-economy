---
searchable: false
---

# PRN-SNP-002: Trust-Based Account Recovery

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| PRN-SNP-002      | 1.0     | 2026-06-16     | N/A        | Informative      |

## 1. Purpose
This document outlines the two main account recovery mechanisms for teachers and students in Classroom Token Hub. It explains the architectural trade-offs and benefits of our design. These mechanisms are designed to allow account recovery without the need of external identity providers or additional PII collection. In addition, it allows classroom data to remain in the custody of the teacher who owns the class and further reduces the reliance on system administrators to intervene.

## 2. Scope
This document covers the **Student-Assisted Teacher Account Recovery** (SATAR) and **Teacher-Initiated Student Account Recovery** (TISAR). These two mechanisms are the only two canonical methods of account recovery for students and teachers in Classroom Token Hub. 

This document is not a normative documentation within the CTH documentation namespace system and thus shall not modify or supersede CTH's official policies, standards, or requirements unless explicitly incorporated by reference. Please consult the following documentation for specification and invariants:

- `INV-CORE-000` (Core Invariants)
- `INV-ARC-019` (Identity and Ownership Model)
- `DOM-IDEN-001` (Identity/Class Binding Domain)
- `DOM-IDEN-002` (Student Account Recovery)
- `DOM-IDEN-003`/`DOM-IDEN-004` (Teacher Identity and Recovery)

## 3. Current Architecture

### 3.1 Student-Assisted Teacher Account Recovery (SATAR)

SATAR allows a teacher who has lost access to their credentials or TOTP device to regain control of their account through distributed student verification across all of their active classes.

**Flow:**

1. The teacher initiates a recovery request by providing one student username and join code pair per class they teach. The backend validates each pair by resolving the chain: `join_code` → `class_id` → `seat_id` (with teacher metadata) → `user_id`. All join codes must resolve to the same teacher `user_id`; if any pair fails validation or resolves to a different identity, the request is rejected. For each supplied student username, the system verifies that `username` → `user_id` → `class_id` matches the corresponding teacher's class.
2. A minimum quorum of students must participate in the recovery. The quorum is distributed across classes with a floor of 3 total verifiers. The structure of the submitted pairing set determines the expected quorum tier. After resolving the teacher identity, the backend independently verifies that the submission structure matches the teacher’s actual number of active classes.:

   | Pairings per class | Implied class count | Total verifiers |
   |--------------------|---------------------|-----------------|
   | 1                  | 3+                  | 3+    |
   | 2                  | 2                   | 4               |
   | 4                  | 1                   | 4               |

   After resolving the teacher's identity from the submitted pairings, the backend queries the actual number of active classes owned by that teacher and verifies that the submission matches the correct tier. If a teacher truly owns 5 classes but only submits 2 join codes with 2 pairings each, the request is rejected because the backend expects 1 pairing per class across all 5 classes. Similarly, if a teacher owns 3 classes but submits 4 pairings from a single join code, the tier does not match. The submission structure must be both internally consistent and accurately reflect the teacher's actual class ownership.
3. The system creates a `RecoveryRequest` with a 5-day time-to-live. The request supports cross-session persistence through a resume PIN so the teacher can return to the process if interrupted.
4. Only the specifically selected students receive a notification to participate in recovery — not the entire class. Each selected student authenticates with their passphrase and the system generates a unique 6-digit numeric code displayed once to the student.
5. The student provides this code to the teacher in person (verbally or written down). The code is never stored in plaintext. Only its HMAC hash is persisted.
6. The teacher collects codes from the required students and submits them as a set. Validation is **all-or-nothing and order-independent**: if any single code is invalid, all stored code hashes are wiped and students must regenerate new codes. No feedback is given about which specific code failed.
7. On successful validation, the teacher sets a new username and scans a new TOTP QR code. Credentials are written atomically and the recovery request is marked as verified.

**Security properties:** Distributed trust (students across all classes must participate), minimum quorum of 3 verifiers, targeted notification (not class-wide), no incremental code probing, generic failure messages, and a hard 5-day expiry on the recovery window.

### 3.2 Teacher-Initiated Student Account Recovery (TISAR)

TISAR allows a teacher to reset a student's credentials when the student has forgotten their username, passphrase, or PIN. The teacher acts as the trusted authority for students within their class.

**Flow:**

1. The teacher initiates a reset for a specific student from their dashboard. The system generates an 8-character alphanumeric reset code with a 10-minute time-to-live and sets the student's recovery status to `to_be_claimed`.
2. The teacher provides this code to the student in real time (the code is visible on the teacher's screen until it expires).
3. The student enters their join code and the reset code at the recovery page. The system validates that the code matches, has not expired, and that the join code corresponds to the student's claimed seat.
4. On successful validation, the student's existing credentials (username hash, PIN hash, passphrase hash) are all cleared. The student is redirected to the credential setup flow to create a new username, PIN, and passphrase.
5. Once new credentials are set, the reset code is cleared and the student's recovery status returns to active. The student's `user_id` is preserved throughout the process — only authentication credentials are cleared, not identity.

**Security properties:** 10-minute hard expiry, single-use code (cleared on use or expiry), rate-limited endpoints, generic error messages that do not disclose student identity, and identity continuity (`user_id` is never destroyed).

## 4. Physical Classroom as Trust Boundary

### 4.1 Student-Consensus
Classroom Token Hub recovers teacher account through the use of student-consensus model. A teacher is a trusted individual in a classroom and at a school setting. Students can visually verify the teacher in their classroom because the teacher physically exists in the classroom and the student recognizes the individual as their teacher. This provides a strong layer of protection against phishing attacks because an attacker would need to physically be in the classroom and be able to trick multiple students across multiple classes into taking over a teacher account. An attacker should also consider that the resulting compromise yields control over a simulated classroom economy teacher account with effectively zero real-world value beyond irritating a large group of students who rely on that teacher to run their classroom economy.

> [!NOTE]
> Classroom Token Hub was written to explicitly scope each class with `class_id`. A teacher can only access a class they have created and no `class_id` may have more than one teacher assigned to it. Therefore, compromising a single teacher account would affect only the classes owned by that teacher. Cross-class take over cannot occur under the current architecture.