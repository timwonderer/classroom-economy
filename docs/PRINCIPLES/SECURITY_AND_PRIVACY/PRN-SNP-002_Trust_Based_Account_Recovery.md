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
This document covers the Student-Assisted Teacher Account Recovery (SATAR) and Teacher-Initiated Student Account Recovery (TISAR). These two mechanisms are the only two canonical methods of account recovery for students and teachers in Classroom Token Hub. 

This document is not a normative documentation within the CTH documentation namespace system and thus shall not modify or supersede CTH's official policies, standards, or requirements unless explicitly incorporated by reference. Please consult the following documentation for specification and invariants:

- `INV-CORE-000` (Core Invariants)
- `INV-ARC-019` (Identity and Ownership Model)
- `DOM-IDEN-001` (Identity/Class Binding Domain)
- `DOM-IDEN-002` (Student Account Recovery)
- `DOM-IDEN-003`/`DOM-IDEN-004` (Teacher Identity and Recovery)

## 3. Background: Threats and Existing Mitigations

This section provides an overview of the threat models and existing mitigations that inform the design of CTH's account recovery mechanisms. It is intended to provide context for the design decisions described in the following sections.

