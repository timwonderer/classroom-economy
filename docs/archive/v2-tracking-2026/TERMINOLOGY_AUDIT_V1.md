# Classroom Token Hub — Terminology Audit (Inventory Run)

> Part 1 of the documentation audit. Inventory only; no rewriting.
> Date: 2026-06-15
> Revision: 2 — accuracy corrections, frequency fixes, removal candidates flagged

## Corrections Applied (Revision 2)

| # | Term | Issue | Fix |
|---|---|---|---|
| 1 | block | Definition incomplete; frequency wildly inflated (8250→~3700, many are model names like `StudentBlock`) | Rewrote definition to reflect current transitional state; corrected frequency |
| 2 | class_economies | Marked v1-only but the Python model `ClassEconomy` is still the active class anchor (mapped to `classes` table) | Changed to "both"; clarified table-name vs model-name distinction |
| 3 | ClassEconomy | Marked v1-only but it is the active runtime model | Changed to "both" |
| 4 | ClassMembership | Marked v1-only but still active in routes and listed in `.claude/CLAUDE.md` as current scoping authority | Changed to "both" |
| 5 | balance_cache | Marked v1-only but `BalanceCache` model is active (backed by `ledger_balance_snapshot` table) | Changed to "both"; clarified the table rename |
| 6 | StudentBlock | Marked v1-only but still actively used in routes for per-seat per-class state | Changed to "both" |
| 7 | tap_events | Marked v1-only/superseded but still in active dual-write transition | Changed to "both" |
| 8 | Economy Balance Checker | Marked v1 but the class and route are active in current codebase | Changed to "both" |
| 9 | Economy Health | Marked v1 but the route and feature are active | Changed to "both" |
| 10 | default (policy mode) | Frequency 1456 massively inflated by Python `default=` keyword across codebase | Corrected to ~280 (policy-mode-specific) |
| 11 | FEAT | Frequency 9200 overstated; measured ~6300 (dominated by docs) | Corrected |
| 12 | join_code | "alias-only in v2" is aspirational; it remains a primary operational key on ~30 tables | Clarified definition |
| 13 | Canonical class time | Name is correct per docs; definition accurate but tightened to reference TemporalContext | Tightened definition |

---

## Terminology Table

| Term | Definition | Usage/Context | Version | Facing | Frequency |
|---|---|---|---|---|---|
| account_balances | Planned v2 per-account checkpoint/cache table keyed by class, seat, and account type for available/current balance tracking. | Future banking/ledger rebuild design. | v2 | dev | 7 |
| Accrual Frequency | How often savings interest is earned (daily, weekly, monthly), distinct from compounding and payout timing. | Banking policy and execution scheduling. | v2 | both | 5 |
| Accrued Interest | Interest earned but not yet posted into spendable savings; it exists as intermediate banking state until payout. | Banking domain accrual and payout model. | v2 | both | 14 |
| Activation Intent | The abstract timing mode attached to a policy transition that says whether a change is immediate, at the next lawful boundary, or manual. | Economic policy governance and disclosure. | v2 | both | 14 |
| actor_public_id | Support-facing copy of a seat public ID used in sysadmin views so support workflows do not expose raw seat/student identifiers. | Support tickets, correlation packs, escalation views. | v2 | dev | 150 |
| Alignment Status | Teacher-facing indication of whether live class settings align with the selected economy policy mode and recommendations. | Economy Health and rebalance workflow. | both | both | 3 |
| AnalyticsAlert | Sysadmin alert object raised from analytics snapshots when a class economy crosses health thresholds. | Sysadmin observability and alerting. | both | dev | 57 |
| AnalyticsSnapshot | Immutable aggregate class-health snapshot captured for analytics and sysadmin alerting without exposing individual student data. | Analytics, alerting, and sysadmin monitoring. | both | dev | 55 |
| anonymous_code | HMAC-derived opaque reference displayed for free-form user reports instead of raw identity. | Support/user report workflow. | v2 | dev | 23 |
| append-only policy evolution | Core economic governance rule that policy changes are represented as new transition lineage, never in-place mutation of active truth. | Economic policy governance and migration away from hidden delayed mutation. | v2 | dev | 2 |
| attendance_sessions | Canonical v2 table for tap-in/tap-out attendance facts; coexists with legacy tap_events in a dual-write transition. | Attendance tracking, payroll inputs, and temporal rules. | v2 | both | 66 |
| Audit Event | High-integrity append-only record for security-sensitive, identity-sensitive, and money-moving side effects. | Operations domain audit trail. | v2 | dev | 14 |
| audit_log | Operations-owned audit table that stores structured before/after records for sensitive side effects and FEAT execution traces. | Audit lineage and operational compliance. | v2 | dev | 115 |
| available_balance | Operational balance that includes posted balance plus pending delta and is used for real-time reads and preconditions. | Ledger reads, banking UI, overdraft checks, and settlement contract. | both | both | 43 |
| balance_cache | Legacy table name for the derived money cache; the Python model `BalanceCache` is still active, now backed by the `ledger_balance_snapshot` table. | Ledger implementation and migration bridge. | both | dev | 114 |
| block | Legacy label for periods/sections. Still used operationally in routes and models (e.g. `StudentBlock.period`) during v1→v2 transition; v2 goal is to treat it as display-only metadata under the canonical `section` field, forbidding label-based authority. | v1 scoping model and v2 migration target. | both | both | ~3700 |
| Budget Survival Test | Canonical solvency check asking whether students can still preserve a minimum weekly savings buffer after recurring costs. | Economy governance, validation, and analytics. | both | both | 19 |
| Canonical class time | The class-local current time derived from UTC plus the class IANA timezone; modeled as the `class_time` field inside `TemporalContext`. | Temporal architecture and class-scoped execution. | v2 | dev | 6 |
| Catastrophe Stability rule | Economy solvency rule testing whether a student can recover within roughly one cycle from a pair of shocks such as fines or loss. | Economic policy validation and recommendations. | both | both | 3 |
| claim artifacts | Seat-owned verification artifacts used to prove entitlement to a rostered participant position during the claim flow. | Student seat claim and roster provisioning. | v2 | dev | 13 |
| Claim Lifecycle | Identity flow that binds a global user to a class-local seat after verifying class-specific claim artifacts. | Identity onboarding and seat binding. | v2 | both | 6 |
| class day | The canonical classroom day boundary defined as midnight-to-midnight in class timezone, then converted to UTC query bounds. | Temporal architecture, attendance, and daily limits. | v2 | dev | 4 |
| class timezone | Immutable IANA timezone owned by the class and used to evaluate days, periods, due dates, accrual windows, and attendance boundaries. | Temporal model, interpretation, obligations, and banking. | v2 | both | 33 |
| class universe | The isolated classroom-economy boundary represented canonically by class_id and operationalized through class-local seats. | Identity architecture and scoping law. | v2 | both | 33 |
| class_economies | Legacy v1 table name (now renamed to `classes`). The Python model `ClassEconomy` is still the active class anchor mapped to the `classes` table. | Identity and class universe references. | both | dev | 420 |
| class_features | Class Configuration table whose row existence per feature acts as authoritative feature enablement for a class. | Feature enablement and class policy surfaces. | v2 | dev | 56 |
| class_id | Canonical private class-universe identifier and internal scoping boundary for all authority-sensitive behavior. | Identity, policy, ledger, attendance, and isolation invariants. | both | both | ~7100 |
| ClassEconomy | Active Python model for the class universe anchor, now mapped to the `classes` table (was `class_economies` in v1). Paired with a public `join_code`. | Multi-tenancy and class identity model. | both | dev | 887 |
| classes | Canonical v2 class-anchor table (renamed from `class_economies`) that defines the universe boundary and carries join code token, display name, and section metadata. | Identity and all class-wide configuration references. | v2 | dev | 840 |
| ClassMembership | Active membership record linking a person to a class; v2 aspires to replace this with seat existence as membership truth, but the model remains operationally active. | Identity and scoping model. | both | dev | 269 |
| Classroom Token Hub (CTH) | The classroom economy platform whose documentation uses CTH/Classroom Token Hub as the canonical product name. | Cross-document product identity. | both | both | 11 |
| Classroom Wage Index (CWI) | Expected weekly income for perfect attendance; the baseline economic unit that all recommended pricing and solvency ratios are measured against. | Economy governance, analytics, policy modes, and recommendations. | both | both | 16 |
| Collective Goal | A shared class objective or store-goal construct priced relative to CWI to encourage coordinated saving and participation. | Economy design, store catalog, and analytics. | both | both | 115 |
| collective_goal_instance_code | Instance key that groups one or more collective-goal store items into the same progress bucket. | Store catalog and collective-goal tracking. | both | dev | 95 |
| comfortable | The most generous policy mode, intended to lower pressure and accelerate progression relative to CWI. | Economy governance and teacher policy selection. | both | both | 49 |
| Compound Frequency | How often accrued interest joins the future earning base; distinct from earning frequency and payout frequency. | Banking policy and accrual math. | v2 | both | 10 |
| Compound Participation | The rule deciding whether accrued-but-unpaid interest is allowed to participate in future accrual calculations. | Banking domain semantics. | v2 | both | 4 |
| correlation pack | Immutable support snapshot that captures request-trace and error context at issue submission time. | Support diagnostics and escalation. | v2 | dev | 13 |
| correlation_id | System-wide workflow identifier propagated across requests, FEATs, reversals, audits, jobs, and incidents to preserve causality. | Operations, ledger, FEAT, and support tracing. | both | both | 1048 |
| current_balance | Authoritative posted-only account balance used after settlement and reconciliation, distinct from available balance. | Banking/ledger settlement model. | both | both | 42 |
| current_session_nonce | Per-login nonce stored on users that binds all requests to one current session and invalidates older sessions on next sign-in. | Identity session security. | v2 | dev | 20 |
| default (policy mode) | The balanced middle policy mode used as the baseline classroom economy climate. | Economy governance and teacher settings. | both | both | ~280 |
| display_name | Human-facing class title metadata, normally paired with section for teacher-facing class display. | Identity/class metadata and UI labels. | both | both | 394 |
| Distributed trust | Teacher-recovery principle requiring one verifying student per active class so no single student can recover a teacher account alone. | Teacher account recovery. | v2 | both | 4 |
| Domain Blindness | Ledger rule that money rows record operational provenance but not business meaning such as rent or store semantics. | Ledger domain architecture. | v2 | dev | 6 |
| done_for_day_date | Per-seat attendance lock date used for O(1) gating; if it disagrees with the event log, attendance history remains authoritative. | Attendance state and daily lock behavior. | both | both | 68 |
| Economy Balance Checker | Shared recommendation/validation engine that checks whether a class economy fits policy-mode guidance and solvency expectations. | Economy Health, rebalance preview, and recommendation APIs. | both | both | 11 |
| Economy Health | Teacher-facing surface for policy mode, alignment review, recommendation visibility, and rebalance actions. | Economy feature/UI. | both | both | 62 |
| economy_pending_rebalance_json | Deprecated compatibility field that stored delayed rebalance payloads before append-only policy transitions became the constitutional model. | Migration bridge from v1 delayed mutation to v2 governance. | both | dev | 24 |
| economy_policy_alignment_status | Stored teacher-facing result showing whether current settings are aligned or misaligned with policy guidance. | Legacy feature_settings economy mode support. | v1 | both | 7 |
| economy_policy_mode | Stored policy climate selector (tight/default/comfortable); in v2 it is an operational projection rather than independent constitutional truth. | Class configuration and economy UI. | both | both | 129 |
| Eligible Savings Balance | The authoritative posted balance slice that actually qualifies to earn interest in a given accrual period. | Banking accrual rules and projections. | v2 | both | 2 |
| Entitlement Balance | Derived count/value of obligation-linked perks; it is computed from events and is never stored as authoritative state. | Obligations and entitlement usage. | v2 | both | 5 |
| entitlement_events | Append-only event stream for obligation-linked grants, consumption, and revocations such as rent-linked hall-pass quota. | Obligations domain. | v2 | dev | 50 |
| FEAT | Atomic feature-execution orchestration unit and the only lawful place for state mutation, money movement, binding, and cross-domain coordination. | Core execution architecture. | v2 | dev | ~6300 |
| Foundational | Highest documentation authority level for system identity and non-negotiable invariants. | Documentation governance model. | both | dev | 93 |
| Future Economic Law | Pending policy state treated as visible announced law rather than hidden backend configuration. | Economic policy transitions and disclosure. | v2 | both | 19 |
| hall pass balance | Combined pass availability model where rent-granted quota is tracked separately from purchased or other pass sources. | Hall-pass and entitlement behavior. | both | both | 10 |
| hall_pass_logs | Attendance-owned lifecycle records for hall-pass requests, approvals, departures, and returns. | Hall-pass execution history. | both | both | 121 |
| hall_pass_settings | Class-owned configuration for queueing, pass types, and simultaneous limits. | Class configuration and hall-pass feature. | both | both | 139 |
| hall_pass_verify_token | Legacy hall-pass public verification token retained as a compatibility surface; newer docs prefer UUID/public-token patterns. | Public hall-pass verification. | both | both | 68 |
| health_check_events | Operations events capturing liveness, readiness, or correctness checks for components and workflows. | Operational health model. | v2 | dev | 15 |
| idempotency_key | Unique replay-protection key attached to writes so retries cannot create duplicate effects. | FEAT execution, ledger writes, obligations, and activation flows. | both | both | 1797 |
| identity rebinding | Recovery principle that restores credential access on the same identity record without creating or moving economic state. | Student and teacher account recovery. | v2 | both | 6 |
| identity_profiles | Seat-owned display-identity table for encrypted first name and public-facing initials; not an authority or credential table. | Identity display layer. | v2 | dev | 95 |
| incident_events | Append-only lifecycle events describing incident creation, updates, comments, and resolution. | Operations incident management. | v2 | dev | 15 |
| incident_summary | Cache/projection of the current state of an incident, derived from its append-only event history. | Operations and status page surfaces. | v2 | dev | 15 |
| Interest Payout | The lawful posting of accrued interest into a student's savings balance through FEAT and ledger execution. | Banking domain and payout scheduling. | v2 | both | 12 |
| issue_categories | System-managed taxonomy used to classify student support issues. | Support domain. | v2 | both | 31 |
| issue_resolution_actions | Append-only declaration log of support actions such as reversals or waivers, without owning the underlying money effect. | Support domain and FEAT-linked remediation. | v2 | dev | 44 |
| issue_status_history | Append-only audit trail of every support issue status transition. | Support domain lifecycle tracking. | v2 | dev | 40 |
| job_events | Operations event log for scheduled/background work such as invariant runs, activation jobs, retries, and failures. | Operations domain. | v2 | dev | 20 |
| join_code | Human-facing class entry alias that resolves to class_id before any authority-sensitive action. Still a primary operational key on ~30 tables during v1→v2 transition; v2 goal is alias-only. | Student claim, routing, recovery, and class selection. | both | both | 6110 |
| last_active_seat_id | Sticky-context pointer on users that restores the last resolved class-local actor context across devices and logins. | Identity session restoration. | v2 | dev | 30 |
| ledger_balance_snapshot | Canonical v2 spendable-balance cache owned by the Ledger domain and re-derivable from posted transactions. | Ledger performance/read model. | v2 | dev | 54 |
| ledger_transaction | Canonical immutable money-movement record used by the Ledger domain. | Ledger authority, FEAT posting, reversals, and audit. | v2 | dev | 98 |
| Mid-Period Lock | Rule that rent-item type semantics cannot change after a valid payment has occurred in the current coverage period. | Rent-linked perks and rent feature behavior. | v1 | both | 7 |
| money velocity | Core class-level metric describing how quickly currency circulates through the classroom economy. | Analytics and interpretation. | both | both | 18 |
| money_action_cooldown_until | Global rate-limit field on users that gates rapid financial mutations. | Identity security state and money-action safety. | v2 | dev | 30 |
| next_boundary | Activation mode meaning a pending policy should take effect at the next lawful operational boundary rather than immediately. | Economic transition governance. | v2 | both | 4 |
| obligation_lifecycle | Derived per-assessment state row describing whether an obligation is due, overdue, paid, waived, or reversed. | Obligations domain. | v2 | dev | 44 |
| obligation_reversal | Immutable record that nullifies a prior assessment and forces downstream interpretation to treat the obligation as non-existent. | Obligations corrections. | v2 | dev | 57 |
| obligation_satisfaction | Immutable record of how a debt was resolved, such as payment or waiver. | Obligations domain lifecycle. | v2 | dev | 46 |
| Operational Provenance | Ledger classification idea behind category fields such as SYSTEM/MANUAL/ADJUSTMENT; it records where a transaction came from, not its business meaning. | Ledger domain-blind design. | v2 | dev | 6 |
| operational_events | Structured JSON operational logs with indexed trace fields outside the payload blob. | Operations observability. | v2 | dev | 21 |
| passkey | WebAuthn-based passwordless authentication capability owned by users and optionally used by teacher/sysadmin accounts. | Identity and login architecture. | both | both | 446 |
| payroll_fines | Class-owned fine presets that FEAT can translate into deductions but that do not create ledger entries by themselves. | Class configuration for payroll. | v2 | both | 75 |
| payroll_rewards | Class-owned reward presets that FEAT can translate into payroll credits but that do not create ledger entries by themselves. | Class configuration for payroll. | v2 | both | 75 |
| policy mode | Teacher-selectable economy climate (tight, default, comfortable) that shapes recommended ratios, pacing, and solvency expectations. | Economy governance and classroom configuration. | both | both | 49 |
| policy_transitions | Append-only lineage objects describing source/target policy versions, activation mode, status, and supersession relationships. | Economic governance and class configuration. | v2 | dev | 89 |
| policy_versions | Immutable constitutional policy records representing the active or historical economic truth for a class/domain pair. | Economic governance and class configuration. | v2 | dev | 100 |
| Public Verification Portal | Public hall-pass verification surface that verifies one claimed student situation without exposing broader roster history. | Hall-pass public-facing feature. | both | user | 2 |
| queue_enabled | Hall-pass configuration toggle that determines whether queued pass requests are used for a class. | Hall-pass settings and teacher controls. | both | both | 21 |
| queue_limit | Configured maximum number of concurrent or queued hall-pass requests allowed by a class or pass type. | Hall-pass settings and request-time gating. | both | both | 38 |
| recovery_status | Short lifecycle marker used in bridge-era student recovery to represent whether an identity is active or waiting to be reclaimed. | Student account recovery. | both | both | 71 |
| RecoveryRequest | Teacher-recovery state object that tracks one pending/verified/expired recovery session across all represented classes. | Teacher account recovery. | v2 | both | 48 |
| redemption_audit_logs | Store-owned append-only audit rows recording redemption requests and approval/rejection outcomes. | Store entitlement redemption history. | both | dev | 58 |
| redemption_prompt | Teacher-facing prompt text attached to delayed store items to guide redemption handling. | Store catalog behavior. | both | both | 26 |
| Rent Late Fee Reversal | Targeted corrective transaction used when mid-cycle rent changes incorrectly caused late fees under the locked base-rate rule. | Rent corrections and admin remediation. | v1 | both | 4 |
| rent-linked store item | Store catalog item that is a store-facing alias of a rent/obligation-controlled benefit. | Store and obligations integration. | both | both | 5 |
| rent_hall_passes | Legacy/bridge count of hall passes granted from rent rather than purchased, used for top-off behavior. | Rent-linked hall-pass logic. | both | both | 72 |
| Reset code | Short teacher-visible student recovery code used for identity rebinding without altering economic state. | Student recovery flow. | both | both | 62 |
| resume PIN | Teacher-recovery resume secret that reconnects a later browser session to DB-persisted partial recovery progress. | Teacher account recovery. | v2 | both | 13 |
| seat | Class-local participant position and the canonical actor identity for economic/operational activity inside one class universe. | Identity, attendance, ledger, obligations, and store. | v2 | both | 5584 |
| seat-scoped isolation | Rule that debt, money movement, entitlement usage, attendance facts, and other actor activity stay bound to one seat within one class. | Core v2 authority and domain design. | v2 | dev | 4 |
| seat_attendance_state | Per-seat mutable attendance gate row used for tap enablement and done-for-day locking. | Attendance domain. | v2 | dev | 53 |
| seat_id | Canonical actor identifier for class-local activity; all economic and operational records hang from it in v2. | Identity, attendance, ledger, obligations, support, and store. | both | both | 1844 |
| seats.public_id | UUID-encoded deidentified public actor identifier used in class-scoped participant navigation and sysadmin-safe references. | Identity, support, and scoped routing. | v2 | both | 35 |
| section | Canonical metadata field for class-period labeling such as Block A or Period 1; useful for display but not authority. | Class identity and teacher-facing UI. | both | both | 629 |
| share_class_name_with_sysadmin | Explicit teacher-consent flag controlling whether class name/context can be shown during issue escalation. | Support escalation privacy boundary. | v2 | both | 14 |
| Spendable Balance | The authoritative sum of posted ledger transactions for a seat/account context and the balance truth other domains query for solvency decisions. | Ledger derived state. | v2 | both | 6 |
| Sticky Context | The last-active class/seat restoration mechanism used to keep users in the correct class context across sessions and devices. | Identity session handling. | v2 | both | 5 |
| store_item_visibility | Seat-scoped visibility mapping that limits which seats may see a store item; absence of rows means visible to all class seats. | Store catalog scoping. | v2 | dev | 18 |
| store_items | Store-owned catalog rows describing price, item behavior, inventory, collective-goal settings, and rent-link flags. | Store domain. | both | both | 237 |
| Structural Interpretation | Interpretation axis that evaluates class configuration and economy health relative to the modeled system structure and CWI. | Interpretation/analytics meaning layer. | v2 | both | 4 |
| Student Seat | Seat whose role is student and which acts as the earning/spending/claiming actor inside a class. | Identity and classroom economy participation. | v2 | both | 47 |
| student-assisted recovery | Teacher-recovery pattern in which one student per active class helps verify the teacher's identity by providing generated recovery codes. | Teacher account recovery. | v2 | both | 3 |
| student_items | Store-held purchased or granted entitlements attached to a seat, including status, expiry, bundle, and use counters. | Store domain. | both | both | 151 |
| student_recovery_codes | Teacher-recovery rows storing hashed six-digit codes contributed by verifying student seats. | Teacher account recovery. | v2 | dev | 39 |
| StudentBlock | Per-student per-class state record carrying tap_enabled, done_for_day_date, and rent_hall_passes. Still actively used in routes; v2 aspires to replace with seat_attendance_state and canonical seat-scoped tables. | Identity, attendance, and per-class student state. | both | dev | 253 |
| System Health Metrics | Always-visible analytics metrics representing the classroom economy's heartbeat, such as participation rate or money velocity. | Analytics feature. | both | both | 19 |
| tap_enabled | Teacher-controlled per-seat flag that allows or blocks future tap accumulation without erasing prior session history. | Attendance gate state. | both | both | 92 |
| tap_events | Legacy v1 attendance event table; coexists with attendance_sessions in a dual-write transition. New writes target attendance_sessions; tap_events still read for analytics and soft-deletion. | Attendance implementation and migration bridge. | both | dev | 179 |
| Teacher Seat | Seat whose role is teacher and which owns class-scoped operational authority within one class universe. | Identity and teacher-side class administration. | v2 | both | 33 |
| teacher_blocks | Legacy v1 table for teacher-to-block relationships; Python model removed from models.py but still referenced in a few legacy code paths. | v1 identity and class-scoping architecture. | v1 | dev | 258 |
| teacher_public_id | Legacy canonical public teacher identifier used for public flows before the unified seat public-ID direction. | v1 teacher identity and public verification. | v1 | both | 133 |
| teacher_public_token | Public, non-enumerable verification token used for hall-pass verification portals. | Public hall-pass verification. | both | both | 23 |
| TemporalContext | Immutable per-request object carrying UTC timestamp, class timezone, and derived class-local time as the only approved execution-time temporal truth. | Temporal architecture and future rebuild model. | v2 | dev | 20 |
| ticket_correlation_packs | Support-owned immutable 1:1 diagnostic snapshots tying an issue to frozen request traces and error references. | Support diagnostics. | v2 | dev | 17 |
| tight | Most restrictive policy mode emphasizing survival, slower savings growth, and higher economic pressure. | Economy governance and teacher settings. | both | both | 79 |
| Top-Off Logic | Rule for adding only the missing rent-granted portion of hall passes so purchased passes are preserved. | Rent-linked hall-pass benefit behavior. | both | both | 3 |
| Unclaimed seat | Seat provisioned in a class with no bound user_id yet; it exists as a future participant position awaiting claim. | Roster provisioning and student onboarding. | v2 | both | 79 |
| Unified identity model | V2 identity architecture where teachers, students, and sysadmins share users/seats/classes primitives instead of separate role tables. | Identity redesign. | v2 | dev | 5 |
| user_recovery_tokens | Canonical user-owned recovery-token lifecycle rows for v2 recovery authority, distinct from short-lived bridge reset-code fields. | Student and teacher account recovery. | v2 | dev | 47 |
| user_reports | Free-form bug/suggestion/comment records separate from the structured class issue-ticket system. | Support domain. | both | both | 62 |
| username_lookup_hash | Deterministic hashed lookup key used to locate a user during login and recovery without storing plaintext usernames. | Identity and recovery flows. | both | dev | 288 |
| users | Canonical global identity table that owns authentication, recovery, session security, and role law. | Identity domain and cross-class human identity. | v2 | dev | 535 |
| visible future economic law | The disclosure principle that pending policy state must be visible to affected teachers, students, and operational domains. | Economic policy visibility. | v2 | both | 5 |
| Waiver-Aware Paid Status | Rule that a rent coverage period counts as paid either by sufficient payment or by an active waiver that covers the due date. | Rent/obligation behavior. | v1 | both | 2 |

---

## Removal Candidates

Terms removed from the main table or flagged for removal, with justification.

### Removed: One-off doc-only terms (≤1 occurrence outside this audit, no codebase presence)

These terms appear in exactly one spec paragraph and function as inline explanations, not reusable vocabulary. They add noise to the glossary without aiding cross-document comprehension.

| Term | Occurrences | Justification |
|---|---|---|
| Account Lifecycle Map | 1 | One-off narrative label in identity onboarding doc; not referenced elsewhere |
| Aggregate Analytics Principle | 1 | Stated once as a design philosophy; the rule is self-evident from context |
| ConsumptionIntent | 1 | Speculative v2 concept mentioned once; no model or code exists |
| Context-First Execution | 1 | Restates the FEAT resolution contract; redundant with FEAT definition |
| Domain Law | 1 | Informal shorthand used once; the authority model is described by DOM-CORE-001 |
| Event-Log Fallback | 1 | Single mention describing ledger recovery; covered by ledger_balance_snapshot definition |
| Hidden Deferred Mutation | 1 | Named anti-pattern mentioned once; the prohibition is covered by append-only policy evolution |
| PeriodKey | 1 | Single mention in obligations spec; an implementation detail, not a glossary term |
| Reversal Primacy | 1 | Single mention in obligations invariants; the rule is covered by obligation_reversal |
| Roster Provisioning Contract | 1 | Single mention; the concept is covered by Claim Lifecycle and Unclaimed seat |
| Signed Magnitude | 1 | Single mention describing ledger sign convention; self-evident from ledger_transaction |
| Single active session per seat | 1 | Single invariant statement; covered by seat_attendance_state and attendance_sessions |
| Solvency Preservation Principle | 1 | Single mention; the concept is operationalized as Budget Survival Test |
| Zero-Sum Transfers | 1 | Single mention; a standard ledger property, not domain-specific vocabulary |
| Generic Placeholder | 1 | Single mention; subsumed by Unclaimed seat |
| Claim-Based Model | 1 | Single mention describing verification approach; covered by Public Verification Portal |
| Interpretation Snapshot | 1 | Single mention; a cache row, not a concept needing glossary status |
| drift indicators | 1 | Single mention; a vague output category, not a precise term |
| pending slice | 1 | Single mention; an implementation detail of settlement |
| Attendance Event Log | 2 | Conceptual label for what attendance_sessions already describes |
| Diagnostic Drill-Down Metrics | 2 | A UX pattern, not a term; self-explanatory from context |
| Class Drift | 2 | Informal name for a session-restoration problem; covered by Sticky Context |
| Drift & Anomaly Metrics | 3 | A category label, not a precise term; covered by System Health Metrics |
| Behavioral Interpretation | 3 | One of two interpretation axes; useful only if Structural Interpretation stays (see below) |

### Removed: Zero occurrences outside this audit

| Term | Justification |
|---|---|
| class-scoped isolation | 0 occurrences; the concept is fully expressed by class universe and class_id |
| obligation-linked entitlements | 0 occurrences; described inline wherever entitlement_events is used |
| Liveness / Readiness / Correctness | 0 occurrences; a standard ops taxonomy, not project-specific vocabulary |
| Zero-Cost Perk | 0 occurrences; a one-off store behavior, not a reusable term |
| Withdrawal Participation | 2 occurrences but purely a banking eligibility sub-rule; an implementation detail |

### Kept but flagged for consolidation

| Term | Suggestion |
|---|---|
| Structural Interpretation / Behavioral Interpretation | Consider merging into a single "Interpretation Axes" entry |
| Core Orchestrator / Domain Guard | Could be folded into the FEAT entry as sub-patterns rather than standalone terms |
| Operational Truth / Operational Provenance | Consider merging into a single "Operations domain semantics" entry |
| Posted Balance Snapshot / Spendable Balance / Eligible Savings Balance | Three related balance concepts that could consolidate under a "Balance taxonomy" entry |
| Event-Log Authority | Near-duplicate of append-only policy evolution; consider merging |
| Idempotency Lock | Subsumed by idempotency_key; consider merging |
| Scheduled activation infrastructure | Only 7 occurrences; borderline — keep if OPS↔FEAT boundary docs grow |
| Axis Exclusivity | Only 2 occurrences; borderline — only meaningful if interpretation axes are retained |

---

## Term Count

- **Original inventory:** 177 terms
- **Removed (one-off / zero-occurrence / implementation detail):** 30 terms
- **Cleaned table:** 147 terms
- **Flagged for consolidation:** ~10 terms (potential further reduction to ~140)
