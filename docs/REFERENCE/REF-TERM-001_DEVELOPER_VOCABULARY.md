# REF-TERM-001: Developer Vocabulary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| REF-TERM-001     | 1.0     | 2026-06-15     | N/A        | Normative       |

## I. Purpose

Define the authoritative developer-facing vocabulary for the Classroom Token Hub architecture. Every term in this glossary represents an independent concept referenced in constitutional (INV-\*), domain (DOM-\*), or architectural documents and is expected to survive architectural evolution.

## II. Scope

This glossary covers terms used in specifications, code review, domain contracts, and internal documentation. It does not include:

- Schema-level field names or table names without independent conceptual meaning (see `ARC-OPS-007_Database_Schema.md`)
- Feature-specific behavioral rules that belong in their respective feature specs
- User-facing vocabulary (see `REF-TERM-002`)

Terms that appear in both this document and REF-TERM-002 carry their developer-facing definition here and their user-facing definition there. Where definitions diverge, this document is authoritative for implementation semantics.

## III. Authority Level

Normative. Subordinate to `INV-CORE-000` and `INV-CORE-001`.

## III-A. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/DOMAIN/DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`

## IV. Glossary

### A

**Activation Intent**
The abstract timing mode attached to a policy transition: immediate, next-boundary, or manual. Governs when a pending policy version becomes the active constitutional truth. Subsumes the `next_boundary` activation mode.

**Append-Only Policy Evolution**
Core economic governance rule that policy changes are represented as new transition lineage (`policy_transitions` → `policy_versions`), never as in-place mutation of the active record. The inverse of the forbidden Hidden Deferred Mutation pattern (formerly operationalized as `economy_pending_rebalance_json`).

**Attendance Sessions** (`attendance_sessions`)
Canonical v2 table for tap-in/tap-out attendance facts. It is the authoritative attendance fact source for the active runtime and replaces legacy `tap_events`.

**Audit Event**
High-integrity append-only record for security-sensitive, identity-sensitive, and money-moving side effects. Stored in `audit_log`. Distinguished from general `operational_events` by its compliance and traceability guarantees.

### B

**Budget Survival Test**
Named solvency check asking whether students can still preserve a minimum weekly savings buffer after recurring costs. Used as a decision criterion in economy validation and analytics. See also: Catastrophe Stability Rule.

### C

**Canonical Class Time**
The class-local current time derived from UTC plus the class IANA timezone. In the planned v2 temporal model, this is the `class_time` field inside a per-request temporal context object. All behavioral evaluation (attendance boundaries, due dates, accrual windows) must use canonical class time rather than raw UTC or server-local time.

**Catastrophe Stability Rule**
Economy solvency rule testing whether a student can recover within roughly one cycle from a pair of shocks such as fines or loss. Distinguished from Budget Survival Test by its focus on shock recovery rather than steady-state viability.

**Claim Artifacts**
Seat-owned verification credentials used to prove entitlement to a rostered participant position during the claim flow. Part of the Claim Lifecycle; their existence is the precondition for seat binding.

**Claim Lifecycle**
Identity flow that binds a global `user` to a class-local `seat` after verifying class-specific claim artifacts. Transitions a seat from unclaimed to bound.

**Class Day**
The canonical classroom day boundary defined as midnight-to-midnight in class timezone, then converted to UTC query bounds. All daily limits, attendance windows, and day-scoped features use this definition.

**Class Timezone**
Immutable IANA timezone owned by the class and used to evaluate class days, period boundaries, due dates, accrual windows, and attendance boundaries. Set at class creation; cannot be changed after the class has active seats.

**Class Universe**
The isolated classroom-economy boundary represented canonically by `class_id` and operationalized through class-local seats. All activity, records, and permissions remain within one resolved class universe.

**Classroom Token Hub (CTH)**
The canonical product name for the classroom economy platform.

**Classroom Wage Index (CWI)**
Expected weekly income for perfect attendance. The baseline economic unit against which all recommended pricing, solvency ratios, and policy-mode guidance are measured.

**Comfortable**
The most generous of three policy modes. Lowers economic pressure and accelerates progression relative to CWI. See also: Default, Tight, Policy Mode.

**Correlation ID** (`correlation_id`)
System-wide workflow identifier propagated across requests, FEATs, reversals, audits, jobs, and incidents to preserve causal linkage. Every side-effecting operation must carry or generate one.

**Correlation Pack**
Immutable support snapshot that captures request-trace and error context at issue submission time. Stored in `ticket_correlation_packs`. Once written, it is never updated — it represents the diagnostic state at the moment of report.

### D

**Default (Policy Mode)**
The balanced middle policy mode used as the baseline classroom economy climate. See also: Comfortable, Tight, Policy Mode.

**Display Metadata** (`display_name`, `section`)
Class-level metadata fields used for teacher-facing display. `display_name` is the human-facing class title; `section` is the canonical period label (e.g., "Block A", "Period 1"). Neither field carries authority — they are metadata only, not scoping keys.

**Distributed Trust**
Teacher-recovery principle requiring one verifying student per active class so no single student can recover a teacher account alone. Implemented through student-assisted recovery flows using hashed recovery codes.

**Domain Blindness**
Ledger rule that money rows record operational provenance (SYSTEM / MANUAL / ADJUSTMENT) but never business meaning such as rent or store semantics. The ledger does not know why a transaction occurred — only where it came from.

### E

**Entitlement Balance**
Derived count or value of obligation-linked perks. Computed from `entitlement_events` and never stored as authoritative state. Distinguished from monetary balances by being event-derived and non-cacheable.

**Entitlement Events** (`entitlement_events`)
Append-only event stream for obligation-linked grants, consumption, and revocations such as rent-linked hall-pass quota. Owned by the Obligations domain.

### F

**FEAT**
Atomic feature-execution orchestration unit and the only lawful mechanism for state mutation, money movement, binding, and cross-domain coordination. Routes and background jobs must invoke a FEAT; they must not call `db.session.add/commit` directly on domain models. The FEAT resolves identity context before any domain interaction, validates intent through read-only domain guards, executes all mutations within a single transaction boundary, and emits an auditable execution trace.

**Foundational**
Highest documentation authority level. Assigned to system identity documents and non-negotiable invariants (`INV-CORE-*`). Documents at this level cannot be superseded by normative or informational documents.

**Future Economic Law**
Pending policy state treated as visible announced law rather than hidden backend configuration. Teachers, students, and operational domains must be able to see what will change and when. The disclosure principle behind `visible future economic law`.

### H

**Health Check Events** (`health_check_events`)
Operations-domain events capturing liveness, readiness, or correctness checks for components and workflows.

### I

**Idempotency Key** (`idempotency_key`)
Unique replay-protection key attached to writes so retries cannot create duplicate effects. Every FEAT must accept or generate one. Used across ledger writes, obligation events, and activation flows.

**Identity Profiles** (`identity_profiles`)
Seat-owned display-identity table for encrypted first name and public-facing initials. Not an authority or credential table — it carries display state only, with PII encrypted at rest.

**Identity Rebinding**
Recovery principle that restores credential access on the same identity record without creating new records or moving economic state. The student's seat, balances, and history are untouched; only the authentication path is re-established.

**Incident Events** (`incident_events`)
Append-only lifecycle events describing incident creation, updates, comments, and resolution. Owned by the Operations domain.

**Incident Summary** (`incident_summary`)
Cache/projection of the current state of an incident, derived from its append-only event history. Owned by the Operations domain.

**Interest Payout**
The lawful posting of accrued interest into a student's savings balance through FEAT and ledger execution. Distinguished from interest accrual (earning) and compounding (reinvesting).

**Interpretation Axes**
The two orthogonal dimensions of analytics interpretation. _Behavioral Interpretation_ explains how seats behave over completed payroll cycles using domain event logs. _Structural Interpretation_ evaluates class configuration and economy health relative to CWI and the modeled system structure. Every metric belongs to exactly one axis and must not blend them into one authority path.

**Issue Categories** (`issue_categories`)
System-managed taxonomy used to classify student support issues. Owned by the Support domain.

**Issue Resolution Actions** (`issue_resolution_actions`)
Append-only declaration log of support actions such as reversals or waivers. Records what action was declared, not the underlying money effect (which goes through FEAT → Ledger).

**Issue Status History** (`issue_status_history`)
Append-only audit trail of every support issue status transition. Owned by the Support domain.

### J

**Job Events** (`job_events`)
Operations-domain event log for scheduled and background work such as invariant runs, activation jobs, retries, and failures.

**Join Code** (`join_code`)
Human-facing class entry alias that resolves to `class_id` before any authority-sensitive action. Still a primary operational key on ~30 tables during the v1→v2 transition; the v2 architectural goal is alias-only status where `class_id` is the sole internal scoping key.

### L

**Last Active Seat ID** (`last_active_seat_id`)
Sticky-context pointer on `users` that restores the last resolved class-local actor context across devices and logins. Part of the Sticky Context mechanism.

**Ledger Balance Snapshot** (`ledger_balance_snapshot`)
Canonical v2 spendable-balance cache owned by the Ledger domain. Re-derivable from posted transactions; if the cache disagrees with the event log, the event log is authoritative.

**Ledger Transaction** (`ledger_transaction`)
Canonical immutable money-movement record. Domain-blind — records operational provenance but not business meaning. All money posts, voids, and reversals produce rows in this table through FEAT execution.

### M

**Money Velocity**
Core class-level metric describing how quickly currency circulates through the classroom economy. Used in analytics and interpretation to detect stagnation or hyperinflation.

### O

**Obligation Lifecycle** (`obligation_lifecycle`)
Derived per-assessment state row describing whether an obligation is due, overdue, paid, waived, or reversed. Owned by the Obligations domain.

**Obligation Reversal** (`obligation_reversal`)
Immutable record that nullifies a prior assessment. A reversal overrides any prior satisfaction history when computing the real status of an assessment.

**Obligation Satisfaction** (`obligation_satisfaction`)
Immutable record of how a debt was resolved, such as payment or waiver. Owned by the Obligations domain.

**Operational Events** (`operational_events`)
Structured JSON operational logs with indexed trace fields (`timestamp`, `correlation_id`, `domain`, `level`) separated from the payload blob. Distinguished from `audit_log` by being observability-focused rather than compliance-focused.

### P

**Passkey**
WebAuthn-based passwordless authentication capability owned by `users` and optionally used by teacher and sysadmin accounts.

**Policy Mode**
Teacher-selectable economy climate (tight, default, comfortable) that shapes recommended ratios, pacing, and solvency expectations. Stored in `economy_policy_mode`; in v2 it is an operational projection derived from `policy_versions` rather than independent constitutional truth.

**Policy Transitions** (`policy_transitions`)
Append-only lineage objects describing source/target policy versions, activation mode (see Activation Intent), status, and supersession relationships. The backbone of append-only policy evolution.

**Policy Versions** (`policy_versions`)
Immutable constitutional policy records representing the active or historical economic truth for a class/domain pair. Once created, a policy version is never modified — it is superseded by a new version through a policy transition.

### S

**Seat**
Class-local participant position and the canonical actor identity for economic and operational activity inside one class universe. Distinguished by role: Student Seat or Teacher Seat. All economic records (transactions, obligations, entitlements) hang from `seat_id`.

**Seat-Scoped Isolation**
Rule that debt, money movement, entitlement usage, attendance facts, and other actor activity stay bound to one seat within one class. No cross-seat leakage is permitted.

**Seat Attendance State** (`seat_attendance_state`)
Per-seat mutable attendance gate row used for tap enablement and done-for-day locking. Owned by the Attendance domain.

**Seat ID** (`seat_id`)
Canonical actor identifier for class-local activity. All economic and operational records reference it. Distinguished from `user_id` (global identity) by being class-scoped.

**Seat Public ID** (`seats.public_id`, `actor_public_id`)
UUID-encoded deidentified public actor identifier used in class-scoped participant navigation and sysadmin-safe references. `actor_public_id` is a support-facing copy used in escalation views so support workflows do not expose raw seat/student identifiers.

**Share Class Name With Sysadmin** (`share_class_name_with_sysadmin`)
Explicit teacher-consent flag controlling whether class name and context can be shown during issue escalation. A privacy boundary within the support domain.

**Spendable Balance**
The authoritative sum of posted ledger transactions for a seat/account context. The balance truth that other domains query for solvency decisions. Distinguished from _available balance_ (posted + pending delta, used for real-time reads) and _current balance_ (posted-only, used after settlement). In the banking domain, _eligible savings balance_ is the accrual-period-specific slice that qualifies to earn interest.

**Sticky Context**
The last-active class/seat restoration mechanism used to keep users in the correct class context across sessions and devices. Operationalized through `last_active_seat_id`.

**Store Items** (`store_items`)
Store-domain catalog rows describing price, item behavior, inventory, collective-goal settings, and rent-link flags.

**Student Items** (`student_items`)
Store-held purchased or granted entitlements attached to a seat, including status, expiry, bundle, and use counters.

**Student Seat**
Seat whose role is student. Acts as the earning, spending, and claiming actor inside a class. See also: Teacher Seat.

### T

**Teacher Seat**
Seat whose role is teacher. Owns class-scoped operational authority within one class universe. See also: Student Seat.

**Ticket Correlation Packs** (`ticket_correlation_packs`)
Support-owned immutable 1:1 diagnostic snapshots tying an issue to frozen request traces and error references.

**Tight**
Most restrictive policy mode. Emphasizes survival, slower savings growth, and higher economic pressure. See also: Default, Comfortable, Policy Mode.

### U

**Unified Identity Model**
V2 identity architecture where teachers, students, and sysadmins share `users`/`seats`/`classes` primitives instead of separate role-specific tables.

**User Recovery Tokens** (`user_recovery_tokens`)
Canonical user-owned recovery-token lifecycle rows for v2 recovery authority. Distinct from short-lived bridge-era reset-code fields.

**Username Lookup Hash** (`username_lookup_hash`)
Deterministic hashed lookup key used to locate a user during login and recovery without storing plaintext usernames.

**Users** (`users`)
Canonical global identity table that owns authentication, recovery, session security, and role law. The only table that exists outside a class universe — it represents the human across all classes.

### V

**Visible Future Economic Law**
The disclosure principle that pending policy state must be visible to affected teachers, students, and operational domains. Pending changes are announced law, not hidden backend configuration.

---

## V. Banking Domain Terms

These terms form a coherent sub-vocabulary within the banking/savings domain.

**Accrual Frequency**
How often savings interest is earned (daily, weekly, monthly). Distinct from Compound Frequency and payout timing.

**Accrued Interest**
Interest earned but not yet posted into spendable savings. Exists as intermediate banking state until Interest Payout occurs.

**Compound Frequency**
How often accrued interest joins the future earning base. Distinct from Accrual Frequency. Includes the Compound Participation sub-rule: whether accrued-but-unpaid interest participates in future accrual calculations.

**Interest Payout**
(Cross-referenced from Section IV.) The lawful posting of accrued interest into a student's savings balance through FEAT and ledger execution.

---

## VI. Excluded Terms

The following term categories are intentionally excluded from this glossary:

### Moved to Schema Documentation (`ARC-OPS-007`)

Database column names, table names, and implementation artifacts that carry no independent architectural meaning: `account_balances`, `anonymous_code`, `balance_cache`, `class_economies`, `ClassEconomy`, `ClassMembership`, `done_for_day_date`, `hall_pass_verify_token`, `money_action_cooldown_until`, `payroll_fines`, `payroll_rewards`, `queue_enabled`, `queue_limit`, `recovery_status`, `redemption_audit_logs`, `redemption_prompt`, `rent_hall_passes`, `student_recovery_codes`, `tap_enabled`, `teacher_public_id`, `teacher_public_token`, `user_reports`.

### Moved to Feature Specs

Feature-specific behavioral rules: Mid-Period Lock, Rent Late Fee Reversal, rent-linked store item, Top-Off Logic, Waiver-Aware Paid Status, Public Verification Portal, Unclaimed seat, RecoveryRequest, System Health Metrics, Economy Balance Checker.

### Removed (Replaced or Premature)

Legacy terms being replaced by canonical vocabulary: `block` (→ section), `StudentBlock` (→ seat_attendance_state), `tap_events` (→ attendance_sessions; legacy table dropped), `teacher_blocks` (model removed from `models.py`; any remaining references are transitional migration or archived-doc residue, not live runtime authority). Premature terms: `TemporalContext` (no code yet). Derivable model names: `AnalyticsAlert`, `AnalyticsSnapshot`.

---

## VII. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-15 | Terminology Audit | Initial creation from TERMINOLOGY_AUDIT_V1.md governance classification. 82 terms retained, 18 merged, 22 moved to schema docs, 10 moved to feature specs, 7 removed. |
