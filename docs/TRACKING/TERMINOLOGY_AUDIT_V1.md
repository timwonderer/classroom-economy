# Classroom Token Hub — Terminology Audit (Inventory Run)

> Part 1 of the documentation audit. Inventory only; no rewriting.
> Date: 2026-06-15

| Term | Definition | Usage/Context | Version | Facing |
|---|---|---|---|---|
| Account Lifecycle Map | The non-normative human-story map of teacher and student identity progression from provisioning through operation and recovery. | Identity onboarding and developer orientation. | v2 | dev |
| account_balances | Planned v2 per-account checkpoint/cache table keyed by class, seat, and account type for available/current balance tracking. | Future banking/ledger rebuild design. | v2 | dev |
| Accrual Frequency | How often savings interest is earned (daily, weekly, monthly), distinct from compounding and payout timing. | Banking policy and execution scheduling. | v2 | both |
| Accrued Interest | Interest earned but not yet posted into spendable savings; it exists as intermediate banking state until payout. | Banking domain accrual and payout model. | v2 | both |
| Activation Intent | The abstract timing mode attached to a policy transition that says whether a change is immediate, at the next lawful boundary, or manual. | Economic policy governance and disclosure. | v2 | both |
| actor_public_id | Support-facing copy of a seat public ID used in sysadmin views so support workflows do not expose raw seat/student identifiers. | Support tickets, correlation packs, escalation views. | v2 | dev |
| Aggregate Analytics Principle | Rule that analytics should describe class-level ecosystem health and drift, not rank or surveil individual students. | Economy analytics philosophy. | both | both |
| Alignment Status | Teacher-facing indication of whether live class settings align with the selected economy policy mode and recommendations. | Economy Health and rebalance workflow. | v1 | both |
| AnalyticsAlert | Legacy/sysadmin alert object raised from analytics snapshots when a class economy crosses health thresholds. | v1 sysadmin observability and alerting. | v1 | dev |
| AnalyticsSnapshot | Immutable aggregate class-health snapshot captured for analytics and sysadmin alerting without exposing individual student data. | Analytics, alerting, and legacy sysadmin monitoring. | both | dev |
| anonymous_code | HMAC-derived opaque reference displayed for free-form user reports instead of raw identity. | Support/user report workflow. | v2 | dev |
| append-only policy evolution | Core economic governance rule that policy changes are represented as new transition lineage, never in-place mutation of active truth. | Economic policy governance and migration away from hidden delayed mutation. | v2 | dev |
| Attendance Event Log | Conceptual append-only timeline formed by attendance sessions and hall-pass events as the authoritative attendance fact history. | Attendance domain model. | v2 | dev |
| attendance_sessions | Canonical v2 table for tap-in/tap-out attendance facts; the successor to legacy tap_events. | Attendance tracking, payroll inputs, and temporal rules. | v2 | both |
| Audit Event | High-integrity append-only record for security-sensitive, identity-sensitive, and money-moving side effects. | Operations domain audit trail. | v2 | dev |
| audit_log | Operations-owned audit table that stores structured before/after records for sensitive side effects and FEAT execution traces. | Audit lineage and operational compliance. | v2 | dev |
| available_balance | Operational balance that includes posted balance plus pending delta and is used for real-time reads and preconditions. | Ledger reads, banking UI, overdraft checks, and settlement contract. | both | both |
| Axis Exclusivity | Interpretation rule that every metric belongs to exactly one axis—behavioral or structural—and must not blend them into one authority path. | Interpretation domain invariants. | v2 | dev |
| balance_cache | Legacy balance cache term for the derived money cache used before the canonical ledger_balance_snapshot/account-balance direction. | v1/v1.5 ledger implementation and migration bridge. | v1 | dev |
| Behavioral Interpretation | Interpretation axis that explains how seats behave over completed payroll cycles using domain event logs. | Interpretation/analytics meaning layer. | v2 | both |
| block | Legacy label used for periods/sections and sometimes policy scope; v2 treats it as metadata only and forbids label-based authority. | v1 scoping model and v2 prohibition boundary. | both | both |
| Budget Survival Test | Canonical solvency check asking whether students can still preserve a minimum weekly savings buffer after recurring costs. | Economy governance, validation, and analytics. | both | both |
| Canonical class time | The class-local notion of current time derived from UTC plus the class timezone and used for all behavioral evaluation. | Temporal architecture and class-scoped execution. | v2 | dev |
| Catastrophe Stability rule | Economy solvency rule testing whether a student can recover within roughly one cycle from a pair of shocks such as fines or loss. | Economic policy validation and recommendations. | both | both |
| claim artifacts | Seat-owned verification artifacts used to prove entitlement to a rostered participant position during the claim flow. | Student seat claim and roster provisioning. | v2 | dev |
| Claim Lifecycle | Identity flow that binds a global user to a class-local seat after verifying class-specific claim artifacts. | Identity onboarding and seat binding. | v2 | both |
| Claim-Based Model | Public hall-pass verification model that only answers a specific student claim instead of exposing a roster or pass list. | Public hall-pass verification portal. | both | both |
| class day | The canonical classroom day boundary defined as midnight-to-midnight in class timezone, then converted to UTC query bounds. | Temporal architecture, attendance, and daily limits. | v2 | dev |
| Class Drift | Identity/context problem where a session restores or remains in the wrong class; sticky-context rules exist to prevent it. | Identity session restoration. | v2 | both |
| class timezone | Immutable IANA timezone owned by the class and used to evaluate days, periods, due dates, accrual windows, and attendance boundaries. | Temporal model, interpretation, obligations, and banking. | v2 | both |
| class universe | The isolated classroom-economy boundary represented canonically by class_id and operationalized through class-local seats. | Identity architecture and scoping law. | v2 | both |
| class-scoped isolation | Rule that all class activity, records, and permissions remain within one resolved class boundary with no cross-class leakage. | Core invariants, request context, and domain ownership. | both | both |
| class_economies | Legacy v1 class container model that held class identity and join code before the canonical classes/class_id v2 model. | v1 architecture and migration references. | v1 | dev |
| class_features | Class Configuration table whose row existence per feature acts as authoritative feature enablement for a class. | Feature enablement and class policy surfaces. | v2 | dev |
| class_id | Canonical private class-universe identifier and internal scoping boundary for all authority-sensitive v2 behavior. | Identity, policy, ledger, attendance, and isolation invariants. | both | both |
| ClassEconomy | Legacy v1 private tenant container for a classroom economy, paired with a public join code. | v1 multi-tenancy and class identity model. | v1 | dev |
| classes | Canonical v2 class-anchor table that defines the universe boundary and carries join code token, display name, and section metadata. | Identity and all class-wide configuration references. | v2 | dev |
| ClassMembership | Legacy membership/bridge record linking a person to a class; v2 replaces this with seat existence as membership truth. | v1 identity and scoping model, plus migration discussions. | v1 | dev |
| Classroom Token Hub (CTH) | The classroom economy platform whose documentation uses CTH/ Classroom Token Hub as the canonical product name. | Cross-document product identity. | both | both |
| Classroom Wage Index (CWI) | Expected weekly income for perfect attendance; the baseline economic unit that all recommended pricing and solvency ratios are measured against. | Economy governance, analytics, policy modes, and recommendations. | both | both |
| Collective Goal | A shared class objective or store-goal construct priced relative to CWI to encourage coordinated saving and participation. | Economy design, store catalog, and analytics. | both | both |
| collective_goal_instance_code | Instance key that groups one or more collective-goal store items into the same progress bucket. | Store catalog and collective-goal tracking. | both | dev |
| comfortable | The most generous policy mode, intended to lower pressure and accelerate progression relative to CWI. | Economy governance and teacher policy selection. | both | both |
| Compound Frequency | How often accrued interest joins the future earning base; distinct from earning frequency and payout frequency. | Banking policy and accrual math. | v2 | both |
| Compound Participation | The rule deciding whether accrued-but-unpaid interest is allowed to participate in future accrual calculations. | Banking domain semantics. | v2 | both |
| ConsumptionIntent | Attendance-originated trigger concept for using an obligation-linked entitlement such as a rent-granted hall pass. | Attendance-to-Obligations coordination. | v2 | dev |
| Context-First Execution | FEAT rule that a user, seat, and class context must be resolved before any domain interaction or mutation occurs. | Feature execution contract. | v2 | dev |
| Core Orchestrator | A FEAT designated as a reusable high-integrity orchestration unit, especially for money posting/voiding and similar cross-domain actions. | Feature-execution architecture. | v2 | dev |
| correlation pack | Immutable support snapshot that captures request-trace and error context at issue submission time. | Support diagnostics and escalation. | v2 | dev |
| correlation_id | System-wide workflow identifier propagated across requests, FEATs, reversals, audits, jobs, and incidents to preserve causality. | Operations, ledger, FEAT, and support tracing. | both | both |
| current_balance | Authoritative posted-only account balance used after settlement and reconciliation, distinct from available balance. | Banking/ledger settlement model. | both | both |
| current_session_nonce | Per-login nonce stored on users that binds all requests to one current session and invalidates older sessions on next sign-in. | Identity session security. | v2 | dev |
| default | The balanced middle policy mode used as the baseline classroom economy climate. | Economy governance and teacher settings. | both | both |
| Diagnostic Drill-Down Metrics | Analytics metrics revealed only after interaction so a teacher can inspect context without making student ranking the default view. | Analytics and interpretation UX. | both | both |
| display_name | Human-facing class title metadata, normally paired with section for teacher-facing class display. | Identity/class metadata and UI labels. | both | both |
| Distributed trust | Teacher-recovery principle requiring one verifying student per active class so no single student can recover a teacher account alone. | Teacher account recovery. | v2 | both |
| Domain Blindness | Ledger rule that money rows record operational provenance but not business meaning such as rent or store semantics. | Ledger domain architecture. | v2 | dev |
| Domain Guard | Standardized read-only domain check that returns allowed/reason/metadata for FEAT orchestration instead of mutating or throwing business errors. | Capability and FEAT interaction pattern. | v2 | dev |
| Domain Law | Shorthand for the codified domain authority model that says each domain owns one bounded truth and mutation boundary. | V2 restructuring and authority summary. | v2 | dev |
| done_for_day_date | Per-seat attendance lock date used for O(1) gating; if it disagrees with the event log, attendance history remains authoritative. | Attendance state and daily lock behavior. | both | both |
| Drift & Anomaly Metrics | Trend-oriented analytics that surface divergence from expected classroom-economy behavior instead of reporting totals alone. | Analytics and interpretation surfaces. | both | both |
| drift indicators | Derived interpretation outputs that flag comparative movement away from expected system behavior over time. | Interpretation domain state classification. | v2 | dev |
| Economy Balance Checker | Shared recommendation/validation engine that checks whether a class economy fits policy-mode guidance and solvency expectations. | Economy Health, rebalance preview, and recommendation APIs. | v1 | both |
| Economy Health | Teacher-facing surface for policy mode, alignment review, recommendation visibility, and rebalance actions. | Economy feature/UI. | v1 | both |
| economy_pending_rebalance_json | Deprecated compatibility field that stored delayed rebalance payloads before append-only policy transitions became the constitutional model. | Migration bridge from v1 delayed mutation to v2 governance. | both | dev |
| economy_policy_alignment_status | Stored teacher-facing result showing whether current settings are aligned or misaligned with policy guidance. | Legacy feature_settings economy mode support. | v1 | both |
| economy_policy_mode | Stored policy climate selector (tight/default/comfortable); in v2 it is an operational projection rather than independent constitutional truth. | Class configuration and economy UI. | both | both |
| Eligible Savings Balance | The authoritative posted balance slice that actually qualifies to earn interest in a given accrual period. | Banking accrual rules and projections. | v2 | both |
| Entitlement Balance | Derived count/value of obligation-linked perks; it is computed from events and is never stored as authoritative state. | Obligations and entitlement usage. | v2 | both |
| entitlement_events | Append-only event stream for obligation-linked grants, consumption, and revocations such as rent-linked hall-pass quota. | Obligations domain. | v2 | dev |
| Event-Log Authority | V2 rule that authoritative truth comes from immutable event records or explicit projections derived from them. | Core schema and domain summary. | v2 | dev |
| Event-Log Fallback | Ledger rule that the posted transaction log can always recompute the spendable-balance cache if the cache is missing or inconsistent. | Ledger invariants and recovery behavior. | v2 | dev |
| FEAT | Atomic feature-execution orchestration unit and the only lawful place for state mutation, money movement, binding, and cross-domain coordination. | Core execution architecture. | v2 | dev |
| Foundational | Highest documentation authority level for system identity and non-negotiable invariants. | Documentation governance model. | both | dev |
| Future Economic Law | Pending policy state treated as visible announced law rather than hidden backend configuration. | Economic policy transitions and disclosure. | v2 | both |
| Generic Placeholder | Teacher-created unclaimed seat waiting for a future student claim/binding. | Roster provisioning and identity lifecycle. | v2 | both |
| hall pass balance | Combined pass availability model where rent-granted quota is tracked separately from purchased or other pass sources. | Hall-pass and entitlement behavior. | both | both |
| hall_pass_logs | Attendance-owned lifecycle records for hall-pass requests, approvals, departures, and returns. | Hall-pass execution history. | both | both |
| hall_pass_settings | Class-owned configuration for queueing, pass types, and simultaneous limits. | Class configuration and hall-pass feature. | both | both |
| hall_pass_verify_token | Legacy hall-pass public verification token retained only as a compatibility surface; newer docs prefer UUID/public-token patterns. | v1 public hall-pass verification. | both | both |
| health_check_events | Operations events capturing liveness, readiness, or correctness checks for components and workflows. | Operational health model. | v2 | dev |
| Hidden Deferred Mutation | Forbidden pattern where future economic changes live only in opaque delayed payloads instead of visible transition lineage. | Economic governance and FEAT compliance. | v2 | dev |
| Idempotency Lock | Ledger/system guard enforcing uniqueness of write intent at the database level. | Ledger state classification and FEAT retry safety. | v2 | dev |
| idempotency_key | Unique replay-protection key attached to writes so retries cannot create duplicate effects. | FEAT execution, ledger writes, obligations, and activation flows. | both | both |
| identity rebinding | Recovery principle that restores credential access on the same identity record without creating or moving economic state. | Student and teacher account recovery. | v2 | both |
| identity_profiles | Seat-owned display-identity table for encrypted first name and public-facing initials; not an authority or credential table. | Identity display layer. | v2 | dev |
| incident_events | Append-only lifecycle events describing incident creation, updates, comments, and resolution. | Operations incident management. | v2 | dev |
| incident_summary | Cache/projection of the current state of an incident, derived from its append-only event history. | Operations and status page surfaces. | v2 | dev |
| Interest Payout | The lawful posting of accrued interest into a student’s savings balance through FEAT and ledger execution. | Banking domain and payout scheduling. | v2 | both |
| Interpretation Snapshot | Cached materialization of a computed behavioral or structural metric window for a class. | Interpretation domain performance layer. | v2 | dev |
| issue_categories | System-managed taxonomy used to classify student support issues. | Support domain. | v2 | both |
| issue_resolution_actions | Append-only declaration log of support actions such as reversals or waivers, without owning the underlying money effect. | Support domain and FEAT-linked remediation. | v2 | dev |
| issue_status_history | Append-only audit trail of every support issue status transition. | Support domain lifecycle tracking. | v2 | dev |
| job_events | Operations event log for scheduled/background work such as invariant runs, activation jobs, retries, and failures. | Operations domain. | v2 | dev |
| join_code | Human-facing class entry alias that resolves to class_id before any authority-sensitive action; canonical in v1, alias-only in v2. | Student claim, routing, recovery, and class selection. | both | both |
| last_active_seat_id | Sticky-context pointer on users that restores the last resolved class-local actor context across devices and logins. | Identity session restoration. | v2 | dev |
| ledger_balance_snapshot | Canonical v2 spendable-balance cache owned by the Ledger domain and re-derivable from posted transactions. | Ledger performance/read model. | v2 | dev |
| ledger_transaction | Canonical immutable money-movement record used by the Ledger domain. | Ledger authority, FEAT posting, reversals, and audit. | v2 | dev |
| Liveness / Readiness / Correctness | Three-part health model distinguishing process uptime, dependency availability, and invariant/business correctness. | Operations health semantics. | v2 | dev |
| Mid-Period Lock | Rule that rent-item type semantics cannot change after a valid payment has occurred in the current coverage period. | Rent-linked perks and rent feature behavior. | v1 | both |
| money velocity | Core class-level metric describing how quickly currency circulates through the classroom economy. | Analytics and interpretation. | both | both |
| money_action_cooldown_until | Global rate-limit field on users that gates rapid financial mutations. | Identity security state and money-action safety. | v2 | dev |
| next_boundary | Activation mode meaning a pending policy should take effect at the next lawful operational boundary rather than immediately. | Economic transition governance. | v2 | both |
| obligation-linked entitlements | Perks whose grant/consumption is controlled by the Obligations domain because they arise from rent/assessment satisfaction rather than store purchase. | Obligations-store boundary. | v2 | both |
| obligation_lifecycle | Derived per-assessment state row describing whether an obligation is due, overdue, paid, waived, or reversed. | Obligations domain. | v2 | dev |
| obligation_reversal | Immutable record that nullifies a prior assessment and forces downstream interpretation to treat the obligation as non-existent. | Obligations corrections. | v2 | dev |
| obligation_satisfaction | Immutable record of how a debt was resolved, such as payment or waiver. | Obligations domain lifecycle. | v2 | dev |
| Operational Provenance | Ledger classification idea behind category fields such as SYSTEM/MANUAL/ADJUSTMENT; it records where a transaction came from, not its business meaning. | Ledger domain-blind design. | v2 | dev |
| Operational Truth | Operations-domain truth about system behavior, health, incidents, jobs, and alerts—not business facts like balances or attendance. | Operations domain definition. | v2 | dev |
| operational_events | Structured JSON operational logs with indexed trace fields outside the payload blob. | Operations observability. | v2 | dev |
| passkey | WebAuthn-based passwordless authentication capability owned by users and optionally used by teacher/sysadmin accounts. | Identity and login architecture. | both | both |
| payroll_fines | Class-owned fine presets that FEAT can translate into deductions but that do not create ledger entries by themselves. | Class configuration for payroll. | v2 | both |
| payroll_rewards | Class-owned reward presets that FEAT can translate into payroll credits but that do not create ledger entries by themselves. | Class configuration for payroll. | v2 | both |
| pending slice | The eligible subset of pending transactions processed during settlement rather than a full historical ledger rescan. | Banking/ledger settlement design. | v2 | dev |
| PeriodKey | Deterministic class-calendar/policy-schedule key that creates a one-to-one mapping between a liability period and an assessment. | Obligations idempotency and period logic. | v2 | dev |
| policy mode | Teacher-selectable economy climate (tight, default, comfortable) that shapes recommended ratios, pacing, and solvency expectations. | Economy governance and classroom configuration. | both | both |
| policy_transitions | Append-only lineage objects describing source/target policy versions, activation mode, status, and supersession relationships. | Economic governance and class configuration. | v2 | dev |
| policy_versions | Immutable constitutional policy records representing the active or historical economic truth for a class/domain pair. | Economic governance and class configuration. | v2 | dev |
| Posted Balance Snapshot | The cached spendable-balance view derived from posted transactions only; authoritative for spending if recomputable from the event log. | Ledger state model. | v2 | dev |
| Public Verification Portal | Public hall-pass verification surface that verifies one claimed student situation without exposing broader roster history. | Hall-pass public-facing feature. | both | user |
| queue_enabled | Hall-pass configuration toggle that determines whether queued pass requests are used for a class. | Hall-pass settings and teacher controls. | both | both |
| queue_limit | Configured maximum number of concurrent or queued hall-pass requests allowed by a class or pass type. | Hall-pass settings and request-time gating. | both | both |
| recovery_status | Short lifecycle marker used in bridge-era student recovery to represent whether an identity is active or waiting to be reclaimed. | Student account recovery. | both | both |
| RecoveryRequest | Teacher-recovery state object that tracks one pending/verified/expired recovery session across all represented classes. | Teacher account recovery. | v2 | both |
| redemption_audit_logs | Store-owned append-only audit rows recording redemption requests and approval/rejection outcomes. | Store entitlement redemption history. | both | dev |
| redemption_prompt | Teacher-facing prompt text attached to delayed store items to guide redemption handling. | Store catalog behavior. | both | both |
| Rent Late Fee Reversal | Targeted corrective transaction used when mid-cycle rent changes incorrectly caused late fees under the locked base-rate rule. | Rent corrections and admin remediation. | v1 | both |
| rent-linked store item | Store catalog item that is a store-facing alias of a rent/obligation-controlled benefit. | Store and obligations integration. | both | both |
| rent_hall_passes | Legacy/bridge count of hall passes granted from rent rather than purchased, used for top-off behavior. | Rent-linked hall-pass logic. | both | both |
| Reset code | Short teacher-visible student recovery code used for identity rebinding without altering economic state. | Student recovery flow. | both | both |
| resume PIN | Teacher-recovery resume secret that reconnects a later browser session to DB-persisted partial recovery progress. | Teacher account recovery. | v2 | both |
| Reversal Primacy | Obligations rule that a reversal overrides any prior satisfaction history when computing the real status of an assessment. | Obligations invariants and interpretation. | v2 | dev |
| Roster Provisioning Contract | Identity rule that roster upload provisions a user shell, class seat, display profile, and claim artifacts without activating credentials. | Student onboarding and seat creation. | v2 | dev |
| Scheduled activation infrastructure | Operations-side evidence model for jobs that may trigger lawful policy activation without giving OPS authority over policy truth or timing legality. | OPS ↔ FEAT ↔ economic-governance integration. | v2 | dev |
| seat | Class-local participant position and the canonical actor identity for economic/operational activity inside one class universe. | Identity, attendance, ledger, obligations, and store. | v2 | both |
| seat-scoped isolation | Rule that debt, money movement, entitlement usage, attendance facts, and other actor activity stay bound to one seat within one class. | Core v2 authority and domain design. | v2 | dev |
| seat_attendance_state | Per-seat mutable attendance gate row used for tap enablement and done-for-day locking. | Attendance domain. | v2 | dev |
| seat_id | Canonical actor identifier for class-local activity; all economic and operational records hang from it in v2. | Identity, attendance, ledger, obligations, support, and store. | both | both |
| seats.public_id | UUID-encoded deidentified public actor identifier used in class-scoped participant navigation and sysadmin-safe references. | Identity, support, and scoped routing. | v2 | both |
| section | Canonical metadata field for class-period labeling such as Block A or Period 1; useful for display but not authority. | Class identity and teacher-facing UI. | both | both |
| share_class_name_with_sysadmin | Explicit teacher-consent flag controlling whether class name/context can be shown during issue escalation. | Support escalation privacy boundary. | v2 | both |
| Signed Magnitude | Ledger rule that transaction direction is encoded by sign alone: positive credits and negative debits. | Ledger invariants and money math. | v2 | dev |
| Single active session per seat | Attendance invariant that only one active attendance session may exist for a seat at a time. | Attendance concurrency and write-time enforcement. | v2 | dev |
| Solvency Preservation Principle | Economic principle requiring system-recommended settings to keep ordinary fully-attending students financially viable. | Economy governance. | both | both |
| Spendable Balance | The authoritative sum of posted ledger transactions for a seat/account context and the balance truth other domains query for solvency decisions. | Ledger derived state. | v2 | both |
| Sticky Context | The last-active class/seat restoration mechanism used to keep users in the correct class context across sessions and devices. | Identity session handling. | v2 | both |
| store_item_visibility | Seat-scoped visibility mapping that limits which seats may see a store item; absence of rows means visible to all class seats. | Store catalog scoping. | v2 | dev |
| store_items | Store-owned catalog rows describing price, item behavior, inventory, collective-goal settings, and rent-link flags. | Store domain. | both | both |
| Structural Interpretation | Interpretation axis that evaluates class configuration and economy health relative to the modeled system structure and CWI. | Interpretation/analytics meaning layer. | v2 | both |
| Structured Operational Log | JSON log record with indexed trace fields such as timestamp, correlation_id, domain, and level separated from payload. | Operations observability. | v2 | dev |
| Student Seat | Seat whose role is student and which acts as the earning/spending/claiming actor inside a class. | Identity and classroom economy participation. | v2 | both |
| student-assisted recovery | Teacher-recovery pattern in which one student per active class helps verify the teacher’s identity by providing generated recovery codes. | Teacher account recovery. | v2 | both |
| student_items | Store-held purchased or granted entitlements attached to a seat, including status, expiry, bundle, and use counters. | Store domain. | both | both |
| student_recovery_codes | Teacher-recovery rows storing hashed six-digit codes contributed by verifying student seats. | Teacher account recovery. | v2 | dev |
| StudentBlock | Legacy v1 student-in-class object that carried class-local state such as passes or done-for-day markers before the seat-based v2 model. | v1 identity and attendance architecture. | v1 | dev |
| System Health Metrics | Always-visible analytics metrics representing the classroom economy’s heartbeat, such as participation rate or money velocity. | Analytics feature. | both | both |
| tap_enabled | Teacher-controlled per-seat flag that allows or blocks future tap accumulation without erasing prior session history. | Attendance gate state. | both | both |
| tap_events | Legacy v1 attendance event table superseded conceptually by attendance_sessions in the canonical v2 schema. | v1 attendance implementation and migration bridge. | v1 | dev |
| Teacher Seat | Seat whose role is teacher and which owns class-scoped operational authority within one class universe. | Identity and teacher-side class administration. | v2 | both |
| teacher_blocks | Legacy v1 table/model for teacher-to-block relationships superseded by seat/class ownership in v2. | v1 identity and class-scoping architecture. | v1 | dev |
| teacher_public_id | Legacy canonical public teacher identifier used for public flows before the unified seat public-ID direction. | v1 teacher identity and public verification. | v1 | both |
| teacher_public_token | Public, non-enumerable verification token used for hall-pass verification portals. | Public hall-pass verification. | both | both |
| TemporalContext | Immutable per-request object carrying UTC timestamp, class timezone, and derived class-local time as the only approved execution-time temporal truth. | Temporal architecture and future rebuild model. | v2 | dev |
| ticket_correlation_packs | Support-owned immutable 1:1 diagnostic snapshots tying an issue to frozen request traces and error references. | Support diagnostics. | v2 | dev |
| tight | Most restrictive policy mode emphasizing survival, slower savings growth, and higher economic pressure. | Economy governance and teacher settings. | both | both |
| Top-Off Logic | Rule for adding only the missing rent-granted portion of hall passes so purchased passes are preserved. | Rent-linked hall-pass benefit behavior. | both | both |
| Unclaimed seat | Seat provisioned in a class with no bound user_id yet; it exists as a future participant position awaiting claim. | Roster provisioning and student onboarding. | v2 | both |
| Unified identity model | V2 identity architecture where teachers, students, and sysadmins share users/seats/classes primitives instead of separate role tables. | Identity redesign. | v2 | dev |
| user_recovery_tokens | Canonical user-owned recovery-token lifecycle rows for v2 recovery authority, distinct from short-lived bridge reset-code fields. | Student and teacher account recovery. | v2 | dev |
| user_reports | Free-form bug/suggestion/comment records separate from the structured class issue-ticket system. | Support domain. | both | both |
| username_lookup_hash | Deterministic hashed lookup key used to locate a user during login and recovery without storing plaintext usernames. | Identity and recovery flows. | both | dev |
| users | Canonical global identity table that owns authentication, recovery, session security, and role law. | Identity domain and cross-class human identity. | v2 | dev |
| visible future economic law | The disclosure principle that pending policy state must be visible to affected teachers, students, and operational domains. | Economic policy visibility. | v2 | both |
| Waiver-Aware Paid Status | Rule that a rent coverage period counts as paid either by sufficient payment or by an active waiver that covers the due date. | Rent/obligation behavior. | v1 | both |
| Withdrawal Participation | Banking rule that withdrawals reduce future eligible balance so interest is not paid on funds no longer represented in authoritative balance. | Banking eligibility. | v2 | both |
| Zero-Cost Perk | Rent-linked store purchase that resolves at zero price when the seat already has the qualifying obligation-linked benefit. | Rent/store integration. | v1 | both |
| Zero-Sum Transfers | Ledger invariant requiring all transactions in one correlated transfer group to net to zero atomically. | Ledger integrity and transfer orchestration. | v2 | dev |
