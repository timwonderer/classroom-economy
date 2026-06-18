---
searchable: false
---

# PRN-SNP-001: Why Classroom Token Hub Does Not Implement SSO

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| PRN-SNP-001      | 1.0     | 2026-06-16     | N/A        | Informative      |

## 1. Purpose

This document explains why CTH's identity architecture, which utilizes class-scoped isolation anchored on `class_id`, a deidentified public actor reference (`seats.public_id`), and a no-DOB, minimal-PII claim model, was deliberately chosen over institutional SSO. It explains why that architecture satisfies the underlying risk-management intent of CSF 2.0's access-control function (`PR.AA`) more effectively than SSO would, given this product's data model and the actual severity of a worst-case breach. 

This document outlines a risk-based engineering decision. SSO would not merely fail to improve this system's security posture, it would affirmatively increase the severity of a breach by attaching durable, real-world identity to data that is currently low-severity specifically because it currently does not carry it.

> [!IMPORTANT]
> This document does not constitute a legal exception to FERPA or any other statute. It is intended for informational purposes only, and not as a substitute for legal counsel. This document does not claim, implicitly or otherwise, any form of certification, approval, or exemption from any legal or regulatory framework such as FERPA, COPPA, GDPR, or NIST CSF 2.0. **CTH strongly recommends that reviewing institutions consult with their own legal counsel for definitive guidance regarding compliance with applicable statutes and regulations.** However, the following sections outline why CTH's identity architecture satisfies the underlying risk-management intent of CSF 2.0's access-control function (`PR.AA`) more effectively than SSO would, given this product's data model and the actual severity of a worst-case breach. 

## 2. Scope

> [!IMPORTANT]
> This document is describing v2.0 architecture and invariants, which is currently being implemented across the codebase. At the time of this writing, not all components of the system have been migrated to v2.0, and some components may still be using v1.0 architecture. However, the system will be v2.0 compliant by public release. The v1.0 architecture is intentionally kept out of scope for the purposes of this document.

This document covers the authentication and identity architecture for all three CTH principals (Student, Teacher, System Administrator).

This document is not normative documentation within the CTH documentation namespace system and thus shall not modify or supersede CTH's official policies, standards, or requirements unless explicitly incorporated by reference. Please consult the following documentation for specification and invariants:

- `INV-CORE-000` (Core Invariants)
- `INV-ARC-019` (Identity and Ownership Model)
- `DOM-IDEN-001` (Identity/Class Binding Domain)
- `DOM-IDEN-002` (Student Account Recovery)
- `DOM-IDEN-003`/`DOM-IDEN-004` (Teacher Identity and Recovery)




## 3. Current Architecture

### 3.1 Identity model

CTH separates identity into three layers, per `INV-ARC-019`:

- **`users`** is the authentication principal. Owns login, credentials, TOTP/passkeys, recovery, and session state. A `users` row represents one human; it does not represent class membership and is never directly visible across class boundaries.
- **`seats`** is the operational actor inside exactly one class. Owns attendance, economy operations, claim verification artifacts, and all class-local state. A user may own multiple seats across multiple classes, but no seat spans more than one class.
- **`classes`** is the isolation boundary, identified by `class_id`. Per `INV-CORE-000` §1, all data access and mutation must resolve to a single `class_id`; `join_code` is only a human-facing alias that must resolve to `class_id` before any authority-sensitive operation. There is no global student directory, no institution-wide account, and no shared identity broker.

Students claim seats with a `join_code` (resolved to `class_id`) plus first name and last name. Students create a username, PIN, and passphrase after the account is claimed. Teachers and System Administrators authenticate with locally hashed username and forced TOTP at signup, optional passkeys.

### 3.2 PII minimization

Per `INV-CORE-000` §2 ("Minimal Use and Storage of PII"):

- **No PII other than first name and last name is collected, used, or stored for student users:** Student `seats` are pre-created by teachers and never exposed outside the class. Student claims seat via a `join_code`, `first_name`, and `last_name`. Backend normalizes and hashes to compare against existing seat fingerprints. Duplicate-name students within one class roster are disambiguated by a teacher-issued `dedupe_code`, which are two-digit numbers between 01-99 scoped to the class roster. 
- **Teacher accounts are created without any PII:** Teacher account is created with a username and forced TOTP at signup, optional passkeys. No name, email, phone, or other identifying information is collected, used, or stored.
- **No PII in plaintext:** PII stored for display (e.g., first name and last name in `identity_profiles`) must be symmetrically encrypted at rest; PII stored for lookup/matching (e.g., roster claim hashes on `seats`) must be one-way HMAC-hashed and not recoverable.
Any account that is inactive for 180 days (close to the length of an academic semester, which is 4.5 months) will be deleted.

> [!NOTE]
> Classroom Token Hub does not have a global archive, inactive status for users, or soft deletes. Deletion within the app is a hard delete with no traceable history other than operational logs that are rotated and truncated frequently. Deletion is in effect, the same as if the account never existed. 

Teacher and student actor identity is itself deidentified at the public-reference layer: `seats.public_id`, a UUID carrying no human-readable or role-specific meaning, is the canonical way either role is referenced in any class-scoped context (`INV-ARC-019` §IX). It resolves only under the active `class_id` and grants no authority by itself.

### 3.3 Credential storage

Usernames are never persisted in plaintext and are instead stored as salted HMAC lookup hashes. Passwords/PINs use bcrypt with a server-side pepper. TOTP secrets and passkey metadata are encrypted at rest and are owned by `users.id`. All of this is only ever internal to CTH and is never exposed to any third-party identity provider.

## 4. Risk-Benefit Analysis of SSO Integration

### 4.1 SSO integration addresses security concerns that are not currently applicable to CTH.

A worst-case compromise of CTH's database currently exposes: a display first name and last initial per seat, a deidentified `seats.public_id`, and a simulated currency ledger with no real monetary value. There is no DOB, no email, no phone, no address, no government or district ID, and no resolvable link from a `seats.public_id` to a real institutional identity for either students or teachers. The worst realistic harm from this exposure is dignity- or embarrassment-tier — not identity theft, not financial fraud, and not a FERPA-grade education-record disclosure, because no education record beyond a simulated classroom economy exists in this system.

SSO does not protect this asset; it changes what the asset *is*. A SAML assertion or OIDC ID token from an institutional IdP routinely carries `givenName`, `sn`, `email`, and a persistent institution-unique identifier. Consuming any of these to provision or match a CTH account would directly violate `INV-CORE-000` §2's prohibition on DOB-class and contact-method PII, and — more importantly for severity — it would attach exactly the kind of durable, cross-context identity that currently does not exist anywhere in this system. A breach of the resulting dataset would no longer expose "a first name and last initial with no external reference"; it would expose a real, named, institutionally-attributable person. That is a strictly higher-severity outcome than the one being defended against today, achieved by adopting the very mechanism proposed to reduce risk.

The display name itself is also weaker than typical PII in a second respect: it is not student-asserted or institution-verified identity. The first name and last initial on a seat are free-text values the teacher enters when provisioning the roster, for the sole functional purpose of letting the student recognize and claim their own seat. Nothing in the claim flow requires this value to match a legal name, cross-checks it against any system of record, or treats it as authoritative — it is an unverified label, not a verified identity attribute. This is a materially different starting point than a SAML/OIDC assertion, which is by definition sourced from and verified against the institution's system of record. Adopting SSO would not be replacing one identity system with a better one; for this specific field, it would be the first time any verified identity entered the system at all.

Access to this display name is also narrow today: outside of direct database access, the only principal who can ever see a seat's decrypted first name and last initial is the teacher who owns that seat's class, through `identity_profiles`. Students do not see other students' names — they have no peer-name lookup surface. System administrators have no route that decrypts or displays `identity_profiles`; their tooling operates on `seats.public_id` and other non-identity fields only (`SEC-CONT-026`). A breach that compromises application-layer access (rather than the underlying database directly) would therefore not expose a single name beyond what one teacher could already see for their own roster.

### 4.2 SSO undermines tenant isolation 

`INV-CORE-000` §1 makes `class_id` the sole isolation boundary, and the project's own incident history (`SEC-INC-013`, the P0 same-teacher multi-period data leak) demonstrates that cross-class identity bleed is the highest-realized risk in this system. An institutional IdP authenticates a student or teacher once, globally, then expects applications to manage authorization on top of that single identity. This reintroduces exactly the failure mode CTH's architecture was rebuilt to eliminate: a single identity object that exists outside any one `class_id` and must be correctly re-scoped by the application on every request. The current design instead makes a global identity unnecessary for normal operation — every actor reference is local to one class and one seat by construction.

### 4.3 SSO concentrates blast radius

Under the current model, compromise of one student's or teacher's credentials exposes only the data within that single class. Under SSO, the institutional IdP becomes a single point of compromise for every classroom, every institution, and every deployment of CTH that trusts it — a breach, misconfiguration, or stale group/claims mapping at the IdP layer would simultaneously affect every tenant, and would do so with real identity attached. This is a direct tradeoff against the CSF 2.0 risk-management objective the requirement is nominally trying to serve: the severity of the worst case goes up while the asset being protected has not changed.

### 4.4 SSO does not fit the deployment model

CTH is used by individual teachers across institutions, charter schools, and homeschool co-ops, many without a SAML/OIDC-capable IdP at all. The product's accessibility — a teacher can run a class economy without any institutional IT involvement — is itself a privacy benefit: it avoids the alternative of ad hoc spreadsheets, third-party form tools, or other unmanaged systems that actually do collect names, emails, and grades with no encryption or access control. Hard-coding a dependency on one institution's IdP would not generalize, and would not by itself improve the security posture for any tenant that already operates inside the `class_id` isolation model.

### 4.5 CSF 2.0 does not mandate SSO specifically, and is risk-based by design

NIST CSF 2.0's `PR.AA` (Identity Management, Authentication, and Access Control) category requires that "identities and credentials for authorized users... are managed by the organization" and that access is "limited to authorized users... and authorized devices, services, and connections is managed commensurate with the assessed risk." The phrase "commensurate with the assessed risk" is load-bearing: CSF 2.0 is a risk-based framework, not a fixed control checklist, and a control's appropriateness depends on the sensitivity of the asset it protects. SSO is a common implementation pattern for satisfying `PR.AA` for systems holding grades, SIS records, financial-aid data, or other high-sensitivity education records. Applied to a system whose worst-case exposure is a first name, last initial, and play-money ledger, a blanket SSO mandate is disproportionate to the asset, and — per §5.1 — actively counterproductive to the risk it is meant to manage. CTH satisfies the same underlying control objectives — credential management, least-privilege scoping, session expiry, MFA for administrative roles — through mechanisms suited to its actual risk profile: locally salted/peppered/hashed credentials, mandatory TOTP for system administrators, strict non-sliding 10-minute session windows, and CSRF/Turnstile-protected entry points (`SEC-CORE-000` §IV).

## 5. Comparative Risk Assessment

| Dimension | Institutional SSO (SAML/OIDC) | CTH `class_id`/`seats` Model (v2) |
|---|---|---|
| PII required to authenticate | Full name, email, persistent institution-assigned ID (assertion-level) | No PII required for authentication; display first name (encrypted) + last initial only, never used as a credential |
| DOB or birth-date-derived data | Not applicable to SSO directly, but commonly paired with SIS records that include it | None collected, stored, or used anywhere in the model |
| Worst-case breach severity | Real, named, institutionally-attributable identity exposed | Deidentified display name + simulated currency ledger; no external reference point |
| Blast radius of a single credential compromise | Institution-wide (IdP-scoped) | Single class (`class_id`-scoped) |
| Cross-tenant correlation risk | High — same federated identity persists across all classes/years | None by design — `seats.public_id` resolves only under its own `class_id` and carries no identity |
| Dependency for basic operation | Requires institutional IdP availability and SAML/OIDC metadata correctness | None — fully self-contained, works for any teacher regardless of institutional IT capacity |
| Additional attack surface | XML signature wrapping, IdP metadata spoofing, token replay, third-party IdP outages | Local bcrypt/HMAC/Fernet primitives already audited under `SEC-CORE-000` |
| Data sharing agreement scope | Requires the institution to release PII attributes to CTH via assertions | None — no PII is requested from or shared with any external identity system |
| Alignment with `INV-CORE-000` §2 (PII minimization) | Conflicts — requires durable PII the invariant prohibits, including categories (email, persistent ID) never collected today | Native — invariant was authored around this exact model |


## 6. Conclusion

CTH's non-implementation of SSO is a deliberate, documented architectural decision, not an oversight. The `class_id`/`seats`-centric, no-DOB, minimal-PII model defined in `INV-CORE-000` and `INV-ARC-019` achieves the access-control and identity-management intent behind CSF 2.0's `PR.AA` category through mechanisms better suited to this product's actual risk profile than federated SSO would be. Because CTH's worst-case breach exposure currently contains no resolvable real-world identity, federating identity through an institutional IdP would convert a low-severity, deidentified exposure into a high-severity, attributable one, while also concentrating breach impact across every classroom rather than containing it to one, and reintroducing the class of cross-tenant identity bleed that CTH's prior incident response (`SEC-INC-013`) was specifically architected to eliminate. 

> [!IMPORTANT]
In that case, Classroom Token Hub no longer retains any responsibility for the security and privacy of that instance nor does the instance represent Classroom Token Hub in any way.

## 7. References

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md` — §1 (`class_id`-Centric Isolation), §2 (Minimal Use and Storage of PII)
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md` — Principal/actor/boundary separation and `seats.public_id` semantics
- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md` — No-DOB claim flow, `dedupe_code` disambiguation
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md` — Unified teacher/student `users`/`seats` model
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_ACCOUNT_RECOVERY.md`, `DOM-IDEN-004_TEACHER_ACCOUNT_RECOVERY.md` — Identity rebinding without credential federation
- `docs/SECURITY/SEC-CORE-000_Security_Foundation.md` — §IV (Security Precepts)
- `docs/SECURITY/CONTROLS/SEC-CONT-026_Authorization_Architecture.md` — Role-Based Access Control model
- `docs/SECURITY/INCIDENTS/SEC-INC-013_Critical_Same_Teacher_Leak.md` — Prior incident motivating tenant-isolation-first design
- NIST Cybersecurity Framework (CSF) 2.0, Function: Protect, Category: Identity Management, Authentication, and Access Control (`PR.AA`)
