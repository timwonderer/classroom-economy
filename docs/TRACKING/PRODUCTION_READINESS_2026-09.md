# CTH v2 Production Readiness — Ship Tracker

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical tracker** |
| Audit date | 2026-09-03 |
| Branch | `codex/landed-architecture-execution-fixes` |
| Audit baseline commit | `09bdc353` |
| Ship target | **2026-09-17** |
| Supersedes | `DOMAIN_PROGRESS_MATRIX_2026.md` (archived — stale as of 2026-08-20, materially wrong on 4+ domains) |

---

## I. How Readiness Was Judged

Readiness is judged **against the normative documents only**: `INV-CORE-000` → `INV-ARC-*` → `DOM-*`.
Phase-completion claims in prior tracking documents were treated as hints, not evidence. Where a
document and the implementation disagree, the document defines the target state and the gap is
recorded here as a finding against the code.

Rubric anchors used:

- **INV-CORE-000 §III.1** — `class_id`-centric isolation; `join_code` is an alias only; `seat_id` anchors actor state
- **INV-CORE-000 §III.2 / INV-ARC-018** — PII never plaintext at rest; encrypted for display, HMAC-hashed for lookup
- **INV-CORE-000 §III.3** — deterministic financial logic; reversal is a counter-entry; **configuration changes must not retroactively alter prior ledger outcomes**
- **INV-CORE-000 §III.4 / INV-ARC-019** — principal (`users.id`) / actor (`seats.id`) / boundary (`classes.class_id`) authority separation
- **INV-CORE-000 §III.5 / INV-ARC-012** — hard deletion; a user with no remaining seats **must** be deleted
- **INV-CORE-000 §III.6 / INV-ARC-013 / INV-ARC-014** — existence-based membership; no lifecycle labels; `block`/`period`/`section` are display metadata and must never drive logic
- **INV-CORE-000 §III.7** — accessibility is a functional requirement, not polish
- **INV-ARC-006** — all mutation crosses the FEAT command boundary
- **INV-ARC-007** — GET handlers are pure
- **INV-ARC-021** — cross-domain coordination goes through a canonical FEAT, never domain-to-domain
- **DOM-POL-001 §VI** — policy repository is append-only and immutable; `policy_uuid` *is* the version

---

## II. Domain Scoreboard

| # | Domain | Verdict | Blocking |
|---|---|---|---|
| 1 | Identity | READY (with caveats) | — |
| 2 | Class Configuration | READY (with caveats) | — |
| 3 | Ledger | READY (with caveats) | — |
| 4 | Productivity & Payroll | READY (with caveats) | — |
| 5 | Obligations | READY (with caveats) | — |
| 6 | Store & Entitlements | READY (with caveats) | — |
| 7 | Policies | READY (with caveats) | — |
| 8 | Interpretation | READY (with caveats) | — |
| 9 | Operations | READY (with caveats) | — |
| 10 | Support | READY (with caveats) | — |

**10 of 10 domains are production-ready (2026-09-05).** T2 — the last open fix track — closed with
B4, B5, B6, and B7, returning Support and Identity to ready. Every blocker opened by the 2026-09-03
audit is now closed, twelve days ahead of the 2026-09-17 target.

*Evidence: `tests/dom/support` + `tests/dom/identity` — **140 passed, 0 failed**, including the eight
new pins in `test_escalation_disclosure_and_scope.py`. What remains before ship is the launch
checklist in §V (CI branch references, deploy trigger, retirement pass), not domain readiness.*

Six defects (B1, B2, B3, B8, B9, B10) have been found and closed on 2026-09-04/05. B1's closure
returned Obligations to ready and B2's returned Policies, clearing fix track T1. **B10** — a
`LedgerBalanceSnapshot` model/schema drift that broke the posted-balance read path — was found on
2026-09-05 by triaging the full suite during B2's closure, where it accounted for roughly
three-quarters of all failures. It was pre-existing and had gone untracked; it moved Ledger to NOT
READY, and track T5 closed it the same day, returning Ledger to ready.

---

## III. Blocking Issues

### B1 — Rent settings mutate in place, retroactively rewriting prior obligations — **CLOSED 2026-09-04**
**Domains:** Obligations, Policies · **Severity:** Critical · **Violates:** INV-CORE-000 §III.3, DOM-POL-001 §VI

`RentSettings.class_id` is `unique=True` (`app/models.py:1052`), so a class has exactly one mutable
settings row. The admin handler reassigns fields on the fetched row and never mints a new
`policy_uuid` (`app/routes/admin.py:5288-5337`). Prior obligation assessments resolve their
`amount_due` from that live row via the frozen `policy_uuid`
(`app/services/obligation_view_model.py:236,275-278`).

Consequence: a teacher editing rent from 50 to 200 silently rewrites the amount owed on every
already-assessed historical cycle. This corrupts financial truth, which is the single hardest
constraint in the system.

*Independently verified against source.*

**Fixed.** `rent_settings` is now the append-only repository DOM-POL-001 §VI.0/§VI.1 describes: the
`UNIQUE(class_id)` index is dropped, a CHECK-constrained `availability_state`
(`IN_USE`/`HIDDEN`/`RETIRED`) supplies the mutable projection over the immutable row, and a
`before_update` guard rejects in-place writes to any definition-payload column, so the defect cannot
return through a stray `setattr`. `get_rent_settings()` is a deterministic current-policy reader
(newest `IN_USE`), `admin_settings_service` gained `create_rent_settings` / `supersede_rent_settings`
(unspecified fields carry forward, so a partial submission is still a complete contract), both write
paths mint new rows, and `rent_payment_feat` resolves perks through **the assessment's**
`policy_uuid`. Migration `d5e6f7a8b9c0`; its `downgrade` is lossy by construction and says so.

**The write path was also dead.** `/admin/rent-settings` carried
`@requires_feat_context("FEAT-OBL-003")` over an inner `FEAT-SETTINGS-001`, so every POST raised
`FEATContextError` — a teacher could not change rent at all, which had masked B1 behind a more
visible failure. The decorator is removed rather than re-pointed (`requires_feat_context` reads
`idempotency_key` from `kwargs`, which a Flask view never receives, and would have discarded the
route's payload-derived key). An AST sweep of every FEAT-decorated route found the identical B9-class
defect on four more, all likewise dead: `/admin/rent-waiver/add` and `/student/rent/pay/<period>`
(decorated with the same FEAT their delegate already carries) and the three store *catalog* routes
(decorated `FEAT-STOR-001` over an inner `FEAT-SETTINGS-001` — a catalog edit is configuration, not a
purchase). All five now open exactly one envelope, at the layer that owns it.

Regression: `tests/dom/obligations/test_rent_policy_immutability.py`, 8 tests. The core one is
verified to fail against the pre-fix commit with `assert Decimal('200.00') == Decimal('50.00')`.
Suites re-run green: rent lifecycle + obligations + phase-7 verification + harness + FEAT ownership
(57 passed), rent-scope/settings-fallback/interpretation-Q3/phase-8 surfaces (28 passed). The three
`test_admin_membership_gates.py` store failures are pre-existing and stash-verified unchanged (a
FEAT-IDEN-001 self-nest in that file's own setup, unrelated to this work).

*Status: closed on `codex/landed-architecture-execution-fixes` @ `51cc9d9f` (2026-09-04).*

### B2 — Policy `*_settings` tables are mutable singletons, not append-only versions — **CLOSED 2026-09-05**
**Domain:** Policies · **Severity:** Critical · **Violates:** DOM-POL-001 §VI

`upsert_payroll_settings` mutated the existing row via `setattr`; `PayrollSettings` had **no
`policy_uuid` column at all**. `HallPassSettings` had the same shape. DOM-POL-001 §VI collapses
Insert/Update into a single Insert — every submission must create a new immutable row.

> B1 and B2 are the same defect class. One immutability rework clears both and unblocks two domains.

**The harm was live, not theoretical.** A payroll run pays out *all* attendance accrued since the
seat's last payroll event, and `_resolve_pay_rate_per_second` (`app/feats/prod.py:63`) prices it from
the class's current policy row. Because that row was rewritten in place, raising the rate mid-cycle
repriced time already worked and left no surviving version that remembered the old terms — so
`PayrollEvent`'s frozen `policy_uuid` had nothing stable to address. DOM-CLASS-003 ("Pending
Next-Cycle Payroll-Governing Changes") is explicit that such a change MUST NOT mutate the policy
governing the open cycle (INV-ARC-015 §VI.7).

**Closure applies B1's pattern verbatim.** Both tables gained `policy_uuid` and a CHECK-constrained
`availability_state` (`IN_USE`/`HIDDEN`/`RETIRED`) as the mutable projection over the immutable row,
plus a partial unique index on `class_id WHERE availability_state = 'IN_USE'` — which both forces
supersession to retire the predecessor in the same transaction and closes the TOCTOU race where two
concurrent submissions each observe no current policy and both insert. `block` is deliberately **not**
in that index: it is display metadata, never a scoping key (INV-ARC-019), and including it would
permit two concurrently-current policies the class-scoped reader could not disambiguate. A
`before_update` guard on each model rejects in-place writes to any definition-payload column, so the
defect cannot return through a stray `setattr`.

`upsert_payroll_settings` keeps its name (many call sites) but no longer updates anything: it retires
the predecessor, carries forward every field the submission did not mention, and inserts a new row —
then activates the payroll `PolicyVersion` snapshot as before. `is_active` is **replaced** by
`availability_state` rather than kept alongside it; two projections would be exactly the alternative
current-version pointer DOM-POL-001 §VI.0 prohibits. `next_payroll_date` is deliberately left mutable:
it is the recurring schedule's cursor, advanced after each run, not part of the submitted definition.

`HallPassSettings` already inserted a new row per save; what was missing was retiring the predecessor,
without which a class accumulated several rows all claiming to be current and the reader picked one by
sort order. Its read path also had a second defect — `_get_or_create_hall_pass_settings` inserted a
default policy as a side effect of being *asked* which policy applied. That is **not** an INV-ARC-007
GET-write — its only live caller was the queue-settings write command — but it did mint a governing
contract nobody submitted and leave that conjured row unretired alongside the submission that followed
it. It is now a pure reader; callers with no policy fall back to class defaults. The dead route shim
in `app/routes/api.py` is deleted.

A **third** defect surfaced while editing that function and was fixed here rather than left to ship:
`update_hall_pass_queue_settings` carried `@requires_feat_context("FEAT-SETTINGS-001")` and then called
`save_hall_pass_setup_config`, which carries it too. The decorator opens a context unconditionally, so
a FEAT composed a FEAT and **every** call raised `FEATContextError` — making the queue-limit API
endpoint an unconditional 500 for as long as the nesting had been in place. Same shape as B9 and the
five routes B1 uncovered. The decorator is removed from the outer function, a thin argument-preparer
over the inner command that owns the envelope (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).

`policy_versions` rows with `domain='payroll'` were left alone: they are DOM-CLASS-003 economic-policy
evolution, a separate lineage with its own boundary-activation rules, not this table's version
pointer. `PayrollEvent.policy_version_id` stays.

Migration `3bb29ef4e874` (guarded, idempotent, tested up → down → up; `flask db heads` shows one head).
Backfill maps `is_active` onto `availability_state`, retires all but the newest current row per class
before creating the unique index, then drops `is_active`.

Regression: `tests/dom/prod/test_payroll_policy_immutability.py` (9 tests) and
`tests/dom/attendance/test_hall_pass_policy.py` (6 tests). Verified by stash cycle: **9 of the 14 fail
against the pre-fix tree, all 14 pass after** — the regression proper being a raise from 0.25 to 2.00
that leaves exactly one `payroll_settings` row for the class, saying 2.00, with no version that
remembers 0.25. Each of the 5 that passed pre-fix was checked individually rather than assumed. Four
are genuine guards over behavior that was already correct. The fifth,
`test_reading_hall_pass_settings_never_mints_a_policy`, was **written wrong**: it exercised the
query-service reader, which was already pure, not the impure `_get_or_create` behind a different entry
point. It is relabeled in-file as a guard, and a real pin for the third defect was added in its place.

Two existing tests (`tests/dom/class/test_payroll_settings_class_scope.py`,
`tests/dom/identity/test_admin_membership_gates.py`) called `.one()` on `payroll_settings`, which
append-only legitimately breaks. Both now read through `get_payroll_settings` rather than loosening to
`.first()`, which would have reinstated the sort-order guessing this blocker exists to remove. These
were the only 2 of the 92 full-suite failures attributable to this change. The other 90 are
pre-existing and were classified individually: 42 from the `LedgerBalanceSnapshot` model/schema drift
now filed as **B10**, 19 from the known `FEAT-IDEN-001` harness-nesting noise, and 29 from 500s
downstream of that same ledger drift plus one axe test needing a live server.

*Status: closed on `codex/landed-architecture-execution-fixes` (2026-09-05).*

### B3 — Orphaned `users` rows are never deleted — **CLOSED 2026-09-04**
**Domain:** Identity · **Severity:** High · **Violates:** INV-CORE-000 §III.5, DOM-IDEN-001 §VI, INV-ARC-012, INV-ARC-018

`hard_delete_student_if_orphaned` (`app/utils/student_deletion.py:196`) deleted seats but left the
parent `User`. The class-teardown path had the same gap. The invariant is unconditional: a user with
no remaining seat in any class must be deleted from the system entirely. Because `User` carries
credential material, this is also a PII-retention violation. No test guarded it.

**Worse than the audit recorded.** Both orphan sweeps were not merely incomplete — they were
tautologies that deleted nothing at all. `_delete_orphan_students` selected seats whose `user_id` was
in the affected set and then excluded seats whose `user_id` was in the affected set; the class
teardown ran its sweep *after* deleting the class's seats, so the driving set was already empty.
Neither ever removed a row.

**Resolution.** New canonical helper `delete_orphaned_users(user_ids)` in
`app/utils/student_deletion.py`: it keeps only ids with no `Seat` anywhere and no owned
`ClassEconomy` (teacher principals are terminal-destroyed through FEAT-IDEN-007, never swept),
clears or removes the FK references that would block the delete (`attendance_sessions` rows —
`ON DELETE SET NULL` against a `NOT NULL` column — and `recovery_requests` are deleted;
`ledger_transaction.user_id`, `issues.sysadmin_id`, `policy_transitions.created_by` are nulled),
then deletes the `users` rows. Credential material (`passkey_credentials`) follows by FK cascade.
All three call paths now route through it: `hard_delete_student_if_orphaned`,
`remove_student_from_teacher_scope`, and the class teardown inside `_destroy_class_scope_rows`. The
acting principal is excluded from the sweep at both destruction sites.

**Regression evidence.** `tests/dom/identity/test_orphaned_user_deletion.py` — 6 tests covering the
last-seat delete, the still-seated-elsewhere preservation, teacher exemption, the production detach
path, class destruction, and credential removal. Green together with the 22 B8 destruction tests
(28 passed). `tests/dom/class` shows the same 7 pre-existing failures before and after (verified by
stash), so the teardown change introduces no regression.

*Status: closed on `codex/landed-architecture-execution-fixes` @ `25b54fcb` (2026-09-04).*

### B4 — Sysadmin escalated-issue and support-ticket views crash (hard 500) — **CLOSED 2026-09-05**
**Domain:** Support · **Severity:** High · **Violates:** INV-CORE-000 §III.7 (function is unreachable)

`_issue_to_view` (`app/routes/system_admin.py:781-797`) reads `issue.teacher`,
`issue.teacher.get_sysadmin_display_name()`, and `issue.class_label`. None exist: `Issue` has no
`teacher` relationship and no `class_label` column, and `get_sysadmin_display_name` is defined
nowhere in the codebase. Affects `escalated_issues`, `view_escalated_issue`, and `support_tickets`.

*Independently verified against source.*

**Resolution.** The root cause ran deeper than "a bad read." `Issue.reviewer_public_id` — the column
that exists precisely to record the reviewing teacher — **had no writer anywhere in the codebase**,
so the view had no lawful source for the reviewer at all and reached for a fabricated one. The fix
therefore had to add the writer, not merely change a read: `admin.escalate_issue` now stamps
`reviewer_public_id` with the escalating teacher's class-scoped seat `public_id`, and `_issue_to_view`
surfaces that. Sysadmin-facing payloads carry `public_id` only — never a name, never a raw `seat_id`
or `user_id` (DOM-SUP-001 §VII, INV-ARC-019 §IX). The three sysadmin templates render the truncated
`public_id`, falling back to `Unattributed`. Pinned by
`tests/dom/support/test_escalation_disclosure_and_scope.py::test_DOM_SUP_001__issue_view_builds_without_a_teacher_relationship`,
which also asserts no internal identifier appears on the payload.

*Status: closed on `codex/landed-architecture-execution-fixes` (2026-09-05).*

### B5 — Sysadmin view leaks class name, ignoring the consent flag — **CLOSED 2026-09-05**
**Domain:** Support · **Severity:** High · **Violates:** DOM-SUP-001 §VI, INV-CORE-000 §III.4

The same view returns a class label unconditionally, ignoring
`Issue.share_class_name_with_sysadmin` (default `false`). Currently masked by B4's crash — fixing B4
without fixing B5 turns a 500 into a live disclosure.

**Resolution — and a correction to the finding.** The description above is not quite right: all three
sysadmin templates *already* gated `class_label` on `share_class_name_with_sysadmin`, so nothing was
in fact being rendered. The real defect was upstream and larger. `issues.class_label` had **never been
created** — DOM-SUP-001 §VI lists it in the `issues` schema contract as a class context cache "frozen
at submission time" which "must not be re-fetched live from ClassEconomy after submission," and no
such column existed. Migration `a1c4e7d92f30` adds it; both submission sites
(`app/utils/issue_helpers.create_issue`, `app/services/issue_service.create_support_ticket`) write it
once, at submission, and never again.

Resolving the label live from `class_public_id` would have avoided the migration but broken the
freeze: an escalation describes the class as it stood when the student submitted, and a class renamed
— or destroyed — afterwards would silently rewrite or erase the context of tickets already in flight.
This matches the policy-immutability standard already set by B1/B2 on this branch. Backfill is an
explicit one-time reconstruction from the live class row; rows that cannot be matched stay `NULL`.

The consent gate was moved to the **view-dict boundary** anyway, rather than left in markup: that dict
is the contract the sysadmin surface is built on, and a consent-gated value should not travel to the
view layer relying on a template to hide it. Pinned by three tests covering the freeze, withholding,
and disclosure.

*Status: closed on `codex/landed-architecture-execution-fixes` (2026-09-05).*

### B6 — `escalate_issue` mutates state outside a FEAT context — **CLOSED 2026-09-05**
**Domain:** Support · **Severity:** Medium · **Violates:** INV-ARC-006

`escalate_issue` (`app/routes/admin.py:10562-10620`) writes without `@requires_feat_context`, unlike
its siblings `resolve_issue` and `close_issue`.

**Resolution.** `@requires_feat_context("FEAT-SUP-001")` added, placed inside `@admin_required` to
match the siblings — so an unauthenticated request is refused before any FEAT opens. Exercised by
the escalation test, which would not reach a clean redirect if the envelope were missing or nested.

*Status: closed on `codex/landed-architecture-execution-fixes` (2026-09-05).*

### B7 — Seat resolution by `public_id` is unscoped; scope fallback selects an unrequested class — **CLOSED 2026-09-05**
**Domains:** Support, Identity · **Severity:** Critical · **Violates:** INV-CORE-000 §III.1, §III.4, INV-ARC-008, INV-ARC-019

Four call sites resolve a seat from a public identifier with **no `class_id` predicate**, so a
`public_id` colliding across classes resolves to an arbitrary seat outside the caller's boundary:

- `app/routes/admin.py:10202` — `_resolve_issue_identity`
- `app/routes/admin.py:10350` — `issues_queue` bulk actor lookup
- `app/routes/admin.py:10468` — `resolve_issue` submitter/transaction-ownership check
- `app/routes/system_admin.py:1405` — `resolve_escalated_issue` reward target

Separately, `resolve_scope` (`app/access/scope_factory.py:170-192`) falls back to
`claimed_seats[0]` when no claimed seat matches `selected_class_id`, then **writes that class into
session context**. A student whose selected class cannot be honored is silently granted scope in a
*different* class. The boundary must be established or refused, never guessed.

`app/services/identity_service.py::_resolve_seat` has the same defect: given a `User` it returns the
lowest-numbered seat across all classes.

Remediation exists on `codex/compliance-check-legacy-structure` (commit `3cdb1294`): add the
`class_id` predicate at each site, replace the `resolve_scope` fallback with `AccessScopeDenied`,
and replace `_resolve_seat` with `resolve_seat_for_context(user_id, class_id, seat_id=None)`.
`resolve_issue` additionally stops proving transaction ownership via the submitter seat and checks
`transaction.class_id == class_id` directly, which is the correct authority.

> B7 shares files and reviewers with B4/B5/B6. Fold it into track T2. **Port the code from
> `3cdb1294`; do not port that commit's badge-system files** (see §V, Deferred).

**Resolution.** All six sites corrected; the badge-system files in `3cdb1294` were **not** ported.
Each admin/sysadmin lookup gained its `class_id` predicate and now degrades safely — to the truncated
`public_id` for display, or to refusal for anything authority-bearing. `resolve_scope` raises
`AccessScopeDenied(reason_code="no_class_scope")` instead of falling back to `claimed_seats[0]`; the
canonical context is the only lawful source of class scope, and when it cannot answer, the answer is
denial.

Two departures from `3cdb1294`, both deliberate:

1. **`_resolve_seat` is deleted, not replaced.** It had no callers anywhere in `app/`, `tests/`, or
   `scripts/`, and `resolve_seat_for_context` would likewise have had none — replacing dead code with
   different dead code. More to the point, its signature asks a question the canonical model cannot
   answer: under DOM-IDEN-001 §VI a `User` holds one `Seat` per `Class`, so "the seat for a user" is
   not well-formed without a class. Deleting it removes the defect outright rather than leaving a
   shape for a future caller to pick up.
2. **`resolve_issue` also guards on `class_id` being present at all.** Porting only
   `transaction.class_id != class_id` would let a request with no class scope compare `None` to `None`
   and pass. Both branches now require `class_id` before mutating a ledger row.

Pinned by `test_DOM_IDEN_001__student_detail_seat_refuses_to_cross_a_class_boundary`,
`test_DOM_IDEN_001__resolve_scope_denies_rather_than_guessing_a_class`, and
`test_DOM_IDEN_001__sysadmin_reward_requires_matching_class_scope`.

*Status: closed on `codex/landed-architecture-execution-fixes` (2026-09-05).*

### B10 — `LedgerBalanceSnapshot` model still declares the pre-split shape the migration dropped — **CLOSED 2026-09-05**
**Domain:** Ledger · **Severity:** Critical · **Found:** 2026-09-05 (full-suite triage during B2)

`app/models.py:688` still declares `posted_checking_balance_cents`, `posted_savings_balance_cents`, and
`UniqueConstraint('class_id', 'seat_id', name='uq_balance_cache_seat_universe')`. Migration
`e6f7a8b9c0d1_canonicalize_ledger_persistence` **dropped all three**: it added `account_type`,
`posted_balance_cents`, and `reconciled_through_posting_sequence`, split savings into its own row, and
created `uq_balance_snapshot_scope` on `(class_id, seat_id, account_type)`. Its `downgrade()` raises
`RuntimeError`, so the schema is one-way and the model is simply wrong.

The drift is not cosmetic, because `get_posted_balance` (`app/services/ledger_service.py:358-409`) has
a fallback it never reaches:

```python
def _get_balance_cache(seat_id, class_id):
    return LedgerBalanceSnapshot.query.filter_by(seat_id=seat_id, class_id=class_id).first()   # no account_type filter

def get_posted_balance(seat_id, class_id, account_type):
    cache = _get_balance_cache(seat_id, class_id)
    if cache:
        cents = (cache.posted_checking_balance_cents      # column no longer exists → raises
                 if account_type == "checking"
                 else cache.posted_savings_balance_cents)
        return _quantize_currency(Decimal(cents) / 100)
    return _get_posted_balance_fallback(seat_id, class_id, account_type)
```

Two faults compound: the unfiltered lookup would return an arbitrary account's row even if the columns
existed, and the attribute access raises instead of degrading to the recompute path.

**Evidence:** in the 2026-09-05 full suite (92 failed / 1102 passed) this accounts for **42 direct
failures plus most of the 29 downstream 500s** — roughly three-quarters of all failures. Confirmed
pre-existing at HEAD and untouched by the B2 diff; it is *not* a B2 regression.

This contradicts the §II scoreboard, which listed Ledger as READY (with caveats) and whose caveats
(§V) do not mention it. Ledger is moved to **NOT READY**. Balance reads are the most load-bearing path
in the product; this must be closed before ship.

**Resolution (2026-09-05).** Closed by track T5. The fix is DOM-LED-001 §2 — snapshot identity is
`(class_id, seat_id, account_type)`, one row per account — carried through every layer that assumed
otherwise:

- `app/models.py` — declares `account_type`, `posted_balance_cents`,
  `reconciled_through_posting_sequence`, the previously undeclared
  `reconciled_through_transaction_id`, and `uq_balance_snapshot_scope`.
- `app/services/ledger_service.py` — `_get_balance_cache` now *requires* `account_type`, so an
  account-blind lookup is no longer expressible; `get_posted_balance` reaches its INV-LED-006 fallback.
- `app/utils/banking.py` — the settlement writer was reworked, not patched. It locks **all** applicable
  account snapshots in the fixed `SETTLEMENT_ACCOUNT_TYPES` order and reconciles them against one
  settlement boundary, which is what INV-LED-009 requires and what the old single-row writer never
  did. Per-account seeding, deltas, and absorption of unsettled posted rows follow from that.
- `app/services/balance_service.py` — the bulk reader buckets per-account rows.
- `migrations/versions/f2c9d1a6b7e8_…` — its `_assert_expected_runtime_shape` guard demanded the
  *pre-split* columns. Because migration `0001` materializes the **current** ORM schema, correcting
  the model retroactively broke this historical step. The guard now accepts either shape, matching the
  tolerance `e6f7a8b9c0d1` already had. This is the bootstrap temporal-causality hazard, and it will
  recur for any future model change that touches a table an older migration asserts on.

Two unrelated pre-existing defects surfaced and were fixed rather than left to ship: four
`test_banking_core.py` tests wrapped `initialize()` — which opens its own FEAT — inside a FEAT context,
violating the one-FEAT-per-path guard; and `test_transaction_idempotency.py`'s deliberate enumeration
pin had gone stale when `564fa49a` added `rent_payment`.

**Regression pin:** `tests/dom/ledger/test_balance_snapshot_account_scope.py` — four tests covering
per-account rows, account-scoped reads, the INV-LED-006 recompute-on-missing-row path, and scope
uniqueness. All four fail against the pre-fix tree with
`UndefinedColumn: column ledger_balance_snapshot.posted_checking_balance_cents does not exist`.

**Full-suite effect (measured, not projected).** 92 failed / 1102 passed → **16 failed / 1183 passed**
(commit `dbb97fa00`). The estimate above — 42 direct plus most of the 29 downstream 500s — held: 76
failures cleared. The 16 survivors are two classes, neither of them Ledger:

| Count | Failures | Disposition |
|---|---|---|
| 14 | `test_admin_membership_gates.py`, `test_multi_teacher_hardening.py` | ~~Track **T2**~~ — **not T2. Test defects, closed 2026-09-05** (see below) |
| 2 | `test_axe_compliance.py`, `test_layout_accessibility_contract.py` | Untracked until now — regressions from the 2026-09-04 two-host landing-page work, **closed 2026-09-05** (`244757497`, `42aa14738`) |

The two accessibility failures were mine and were not in this tracker, which is worth recording as a
gap in how it is maintained: a blocker list assembled from domain review will not catch a defect
introduced *after* the review. The icon-font contract asserted the published pages must not use a CDN,
which is a single-host assumption the deliberate two-host split invalidated; the axe audit hard-failed
when its dev server was absent instead of skipping like its other two prerequisites. With a server up
the axe audit passes on all seven public routes, so nothing was hidden by making it skip.

**The 14 identity failures were not T2 (2026-09-05).** Attributing them to T2 on filename alone was
wrong, and triage says so: 13 of the 14 were one harness defect —
`FEATContextError: Nested FEAT context forbidden — Active=FEAT-IDEN-001, attempted=FEAT-IDEN-001`,
raised from `initialize()`, which opens its own `FEAT-IDEN-001` and so cannot be called from inside a
test-owned context (INV-ARC-000 §VIII.2). This is exactly the harness noise the §V Identity caveat
predicted. The 14th was a test asserting the *opposite* of DOM-IDEN-001 §VI: that a seat's
`IdentityProfile` survives its seat. It does not — the profile is per-seat-within-class and cascades —
and that test also never constructed the shared student its name claims. Both files now pass in full
(**22 passed**, from 14 failed / 8 passed).

The consequence for T2 is the point: this noise was *masking* signal, and no genuine B4–B7 failure
could be judged until it was cleared. With it cleared, **none appeared**. B4–B7 remain open on source
review, not on a red test — which is consistent with their nature (B4 is a hard 500 on sysadmin views,
B5 a disclosure behind that 500, B7 an unscoped lookup that needs a colliding `public_id` to observe).
They are real, and they are unpinned. T2 must therefore land regression coverage alongside the fix,
not merely turn existing tests green.

### B9 — Daily-limit auto tap-out is silently non-functional (FEAT-PROD-001 executes itself) — **CLOSED 2026-09-04**
**Domain:** Productivity & Payroll · **Severity:** High · **Violates:** INV-ARC-000 §VIII.2, INV-ARC-021 §V.2

`enforce_daily_limits` (`app/scheduled_tasks.py:15`) is decorated `@requires_feat_context("FEAT-PROD-001")`
and then calls `record_attendance_session` (`app/feats/prod.py:240`), which carries the **same**
decorator. The nested envelope raises `FEATContextError: Nested FEAT context forbidden` — and the
`except Exception` at `app/scheduled_tasks.py:202` logs and **swallows** it, then `continue`s. The job
reports success while closing zero sessions.

Consequence: students who hit the daily attendance limit are never tapped out, so paid time keeps
accruing past the cap. Observable as two failures in `tests/dom/identity/test_admin_tenancy.py`
(expects 2 attendance sessions, gets 1; expects a `done_for_day` row, gets 0).

This is the same defect class as B8: a caller-level envelope wrapping a FEAT-decorated domain
command.

**Resolution.** `record_attendance_session` was split along the pattern already established in the
same module by `_record_hall_pass_log_impl` / `record_hall_pass_log`: a plain
`_record_attendance_session_impl` domain command plus a thin `@requires_feat_context("FEAT-PROD-001")`
entry. Every route ingress keeps the FEAT entry; the daily-limit job, which already owns the
envelope, composes the domain command. The per-seat `except Exception` now re-raises
`FEATContextError` — swallowing a constitutional violation as per-seat noise is precisely how this
job reported success while closing zero sessions for eight weeks.

**The other three job envelopes were audited and are correct.** `FEAT-PROD-004` (:407) and
`FEAT-STOR-002` (:539) open a fresh per-item context inside an *undecorated* function — one
top-level FEAT per class/item, by design — and `complete_payroll_cycle`, `expire_entitlement`, and
`delete_due_policy_lineages` are all undecorated. `FEAT-OPS-001` (:222) calls no FEAT at all.

**Regression evidence.** `tests/dom/identity/test_admin_tenancy.py` already covered this and was
failing: 2 failed / 7 passed before, **9 passed** after (verified by stash). `tests/dom/prod` and
`tests/dom/attendance`: 26 passed, with one pre-existing hall-pass failure unchanged before and
after.

*Found 2026-09-04 during B8 remediation. Not part of the 2026-09-03 audit sweep.*

*Status: closed on `codex/landed-architecture-execution-fixes` @ `5f3bc4c0` (2026-09-04).*

---

### B8 — Class destruction selected its target from a public alias; both destruction gates were defeatable — **CLOSED 2026-09-04**
**Domains:** Identity, Class Configuration · **Severity:** Critical · **Violates:** INV-CORE-000 §III.1, §III.4, INV-ARC-006, INV-ARC-012 §V

Found while investigating a user-reported symptom ("the deletion modal doesn't fire, it just says the
phrase doesn't match"). Not part of the 2026-09-03 audit sweep. Four distinct defects:

1. `POST /admin/join-code/delete` read `join_code` from the request body and destroyed whatever class
   that alias resolved to — target selection from a public alias, across tenants.
2. The same route honored a `confirm_join_code` shortcut that skipped `_validate_destruction_gate`
   entirely. The join code is public — every student in the class holds it — so echoing it back
   bypassed the countdown, typed phrase, and press-and-hold gate.
3. `/admin/account-delete` rendered its confirmation phrase from `get_display_username()`, which
   returns `f"user_{User.id}"` — the internal principal key presented as an identity.
4. The gate JavaScript bound to `getElementById('deletion-request-form')` while the form was rendered
   as `account-delete-form`. The null lookup threw, killing the `DOMContentLoaded` handler, so the
   modal never fired and the page posted natively with an empty `gate_phrase`. This was the reported
   symptom; defects 1–3 were found underneath it.

Two latent bugs made teacher account deletion **inoperative since 2026-07-11** (`68e08abe`):
`_hard_delete_teacher_account_scope` was passed an `int` where its signature had changed to expect a
canonical context, raising `ValueError` into a broad `except` that flashed a generic error; and
`_delete_teacher_residual_ownership_rows` called `.delete()` on a joined query, which SQLAlchemy
rejects. The second was unreachable until the first was fixed.

**Resolution.** Both surfaces now resolve their target exclusively from the canonical context
(`user_id` for the account, `class_id` for the class); the gate is unconditional; the account phrase
comes from the lawful Identity display read (`build_identity_profile_view`) with a non-identity
`DELETE MY ACCOUNT` fallback; and the destroyed class's canonical pointers are cleared (INV-ARC-012
§V). Display names and join codes are presentation only and never participate in lookup,
authorization, or target resolution. The class-destruction UI, which did not previously exist
anywhere in `templates/` or `static/`, was built on the existing gate contract.

Teacher account destruction was given canonical FEAT shape as **FEAT-IDEN-007** (registry +
`docs/FEATURE-EXECUTION/FEAT-IDEN-007_TEACHER_ACCOUNT_DESTRUCTION.md`). Because exactly one FEAT
executes per request, the class-destruction body was split into a plain domain command
(`_destroy_class_scope_rows`), with `_hard_delete_class_scope` retained as the thin FEAT-CLASS-001
entry for single-class destruction; the account FEAT composes that command rather than executing
FEAT-CLASS-001. One envelope now spans the whole teardown, making it atomic.

Regression: `tests/dom/identity/test_destruction_authority_boundary.py` (21 tests) pins the authority
boundary and every gate-failure mode. Verified 22 passed with
`tests/dom/class/test_hard_delete_class_scope_isolation.py`; `tests/test_class_phase2_persistence.py`
clean after the domain-command split.

*Status: closed on `codex/landed-architecture-execution-fixes` @ `25b54fcb` (2026-09-04).*

---

## IV. Fix Tracks

| Track | Clears | Unblocks | Est. | Owner | Status |
|---|---|---|---|---|---|
| **T1 — Policy immutability rework** | ~~B1~~, ~~B2~~ | Obligations, Policies | Large | — | **Done 2026-09-05** |
| **T2 — Sysadmin support surface + seat-scope** | ~~B4~~, ~~B5~~, ~~B6~~, ~~B7~~ | Support, Identity | Medium | — | **Done 2026-09-05** |
| **T3 — Orphaned-user deletion** | B3 | Identity | Small | — | **Done 2026-09-04** |
| **T4 — FEAT self-nesting in scheduled jobs** | B9 | Productivity & Payroll | Small | — | **Done 2026-09-04** |
| **T5 — Ledger snapshot model/schema realignment** | B10 | Ledger | Medium *(estimated Small–Medium; see below)* | — | **Done 2026-09-05** |

**Sequencing to 2026-09-17.** T1 was the critical path and the only substantial design work; it is
now clear. B1 established the append-only pattern (immutable payload + `availability_state` projection
+ supersession command + guarded migration) and B2 applied that same pattern to `PayrollSettings` and
`HallPassSettings`. T3, T4, T5, and now T2 are all done as well, so **every fix track opened by the
2026-09-03 audit is closed** with twelve days to spare against the 2026-09-17 target.

> **T2 closed 2026-09-05.** B4 and B5 both turned out to be larger than their entries described, and in
> the same direction: each was a symptom of a schema-contract gap rather than a bad read. B4's crashing
> view had no lawful source for the reviewing teacher because `Issue.reviewer_public_id` had **no
> writer anywhere in the codebase**; B5's `issues.class_label` had **never been created**, though
> DOM-SUP-001 §VI lists it in the `issues` schema contract. Fixing either properly meant adding the
> missing writer, not redirecting the read. B5's correction also went the other way on the finding
> itself: the templates already honored the consent flag, so nothing was in fact leaking — the gate was
> moved to the view-dict boundary on principle, not to stop an active disclosure.
>
> The estimate held at Medium, but for a different reason than assumed: the work was not four small
> independent patches but one coherent repair of a single surface, and the four blockers shared enough
> that fixing them in isolation would have been slower.

> **Correction (2026-09-05).** This section previously sized T5 as "a one-file model correction plus
> an `account_type` predicate" scoped to `app/models.py` + `ledger_service.py`. That was wrong, and
> the error was one of reasoning rather than of information: I sized the *symptom* (a wrong column
> list) instead of reading what depended on it. The whole settlement writer assumed one row per seat
> holding both accounts, so correcting the model required reworking `settle_balances` to lock every
> applicable account snapshot in deterministic order under INV-LED-009 — plus the bulk reader, the
> adversarial harness, the fixtures, and a historical migration guard. Seven files and one new pin,
> not one file. Sequencing it first was still right, for the stated reason: until it landed the suite
> could not be read as a ship signal.

**Exit criteria for the ship gate.** All open blockers closed; each with a regression test that
fails against the pre-fix commit; full pytest suite green; `flask db heads` shows exactly one head.

---

## V. Non-Blocking Findings

Carried as post-ship backlog unless a track happens to touch the same code.

**Identity** — teardown helpers still physically live in `app/routes/admin.py` even though they are
now proper FEAT/domain commands (`FEAT-IDEN-007` and `_destroy_class_scope_rows`); they should move
into `app/feats/`. 7 `print()` calls in `context_resolver.py`; residual `Seat.block` property.
~14 identity tests wrap `initialize()` in a redundant `FEATContext`, which now raises
`FEATContextError: Nested FEAT context forbidden` — test-harness noise that masks real signal.

**Class Configuration** — dead FEAT-bypass branch (`app/services/economy_policy.py:289-295`); dead
`replace_enabled_class_features` import; cascade behavior untested; `customizations()` edits
DOM-CLASS fields under a FEAT-IDEN context.

**Ledger** — ~~3 ops scripts raise `ImportError` on the removed `BalanceCache`~~ **swept in T5
(2026-09-05)**: `scripts/verify_balance_cache.py`, `scripts/adversarial/verify_cross_class_isolation.py`,
and `scripts/adversarial/inject_impossible_state.py` now import `LedgerBalanceSnapshot` and read
`account_type` / `posted_balance_cents`. Remaining: misleading `student` variable actually bound to a
Seat (`app/routes/student.py:761`); residual `join_code` / `user_id` columns on `Transaction`.
*(These were the caveats behind Ledger's former READY verdict. They did not include the snapshot model
drift, which was missed here and became **B10** — the ops-script `ImportError` was the same migration's
fallout, which is why both closed together.)*

**Productivity & Payroll** — `daily_limit` missing from the `AttendanceReasonCode` enum; pay-rate
selection filters on a block/section label (**INV-ARC-014 violation, promote to blocking if it can
select the wrong rate**); hardcoded `0.25/60` fallback rate; heuristic reversal correlation.

**Store & Entitlements** — dual `StoreItem` / `StoreProduct` catalog; `InsuranceClaim` has mutable
status; reliance on FK cascade rather than explicit teardown.

**Interpretation** — stale docstrings claiming the payload is "partial" and materialization is "NOT
IMPLEMENTED"; both are false. Dead comment in `analytics_engine.py`.

**Operations** — DOM-OPS event tables not built; telemetry still goes to log files;
`combined_logs` / `error_logs` / `network_activity` are stubbed.

**Support** — `update_user_report` handler is dead and incorrect; announcement creation does not
re-verify ownership; zero test coverage on the sysadmin surface.

**Obligations (dead code)** — `RentWaiverView` and `get_active_rent_waivers_for_class`
(`app/services/obligations_service.py:746-789`) have **zero callers**. `rent_settings` was reworked
to `get_rent_waiver_history_for_class` under DOM-OBL-001 §V.6 one-time-immutable-waiver semantics.
`_count_rent_waiver_periods` (`app/routes/admin.py:839`) is likewise orphaned and reads
`.coverage_start_time` / `.coverage_end_time`, attributes DOM-OBL-001 v2.5 removed from
`assessment_events`. Delete all three.

**Cross-cutting** — 9 Dependabot advisories on the default branch (8 high, 1 moderate); accessibility
remediation tracked separately in `ACCESSIBILITY_REVIEW_2026-09-03.md`.

### Launch checklist (must clear before promotion) — verified 2026-09-05

Unlike the findings above, these are *not* post-ship backlog. Each one is a release-mechanics defect
that domain readiness does not cover, and every item was confirmed against the working tree rather
than recalled.

**CI gates on a branch that does not exist.** Three workflows filter on `codex/v2.0`. That ref is
absent locally *and* on the remote — `git branch -a | grep -c codex/v2.0` returns **0**. The
integration branch is `CTH_v2.0` (`origin/HEAD` points there). Consequences differ per workflow and
the difference matters:

| Workflow | PR leg | Push leg | Net effect |
|---|---|---|---|
| `actionlint.yml` | `pull_request` — no branch filter, **fires** | dead | degraded only |
| `policy-guardrails.yml` | `pull_request: '**'`, **fires** | dead | the `guardrails-push` job is `if: github.ref == 'refs/heads/codex/v2.0'` — permanently false, so the **"no waivers allowed" strict check has never once run** |
| `check-migrations.yml` | filters `codex/v2.0`, **dead** | dead | **fully inert — zero migration validation on any PR** |

`check-migrations` being wholly dead is the sharpest of the three: migrations are this repo's
single most documented source of deploy failure, and the gate built to catch that has never fired.
It carries a second, independent bug — its `paths` filter watches `app/models/**`, but this repo has
`app/models.py`, a module, not a package. Fixing only the branch name would leave model changes
still unable to trigger it.

**`deploy.yml` deploys production from `main`, which is 1053 commits behind.**
`git rev-list --count origin/main..origin/CTH_v2.0` = **1053**. Production therefore currently runs
v1-era code, and shipping v2 requires an explicit decision — merge `CTH_v2.0` into `main`, or
repoint the deploy trigger. This is a decision for the owner, not a defect to silently fix: it
determines what "ship" means on 2026-09-17.

**Retirement pass.** `v2progress.html` and the "transition site" vocabulary (see §VI) go stale the
moment this branch is promoted. `github-pages/v2transition.html` is absent from HEAD and would
vanish from the published site on promotion.

**Stale branch references in guidance.** `CLAUDE.md` names `codex/v2.0` as the base branch. It is
the same nonexistent ref the CI workflows point at, and it will keep reproducing this class of
error in future work until corrected.

---

## VI. Deferred Work Recovered From Branch Triage

A 2026-09-04 sweep of 53 local branches and 15 worktrees found three bodies of work that exist
nowhere on this branch. They are recorded here so the source branches can be deleted. **Nothing else
across those branches was unported** — every other unmerged branch was verified superseded by
content already present on HEAD.

| Item | Source | Disposition |
|---|---|---|
| Seat-scope isolation fix | `codex/compliance-check-legacy-structure` @ `3cdb1294` | **Launch** — promoted to blocker B7, track T2 |
| Support-content registry | `support-text-extraction` @ `fe3e3e0d..` | **Backlog** — see below |
| Bug-hunter badge system | `codex/compliance-check-legacy-structure` @ `3cdb1294` | **Backlog** — see below |
| `github-pages/v2transition.html` | `CTH_v2.0`, `docs/v2-progress-page` | **Pre-promotion** — see below |

### Support-content registry (backlog)

A canonical registry that lifts user-facing help text out of templates into versioned content files:
`app/content/registry.py` (388 lines), `app/content/__init__.py`, `content/help/admin.yaml`,
`content/help/long/admin/rent.md`, `content/inventory.md` (517-line audit of every user-facing
string), `scripts/validate_content_keys.py`, `tests/test_content_registry.py` (364 lines), plus
template rewiring. ~1,600 insertions.

This serves INV-CORE-000 §III.7 — help text that is discoverable, translatable, and
screen-reader-addressable rather than inlined markup. It is a genuine improvement but touches every
template, so it is **not** a two-week item. Schedule after ship, alongside the accessibility
remediation it complements.

Note: HEAD carries an empty `content/` directory and an untracked `app/content/__pycache__` — ghosts
of a partial application. Clean both before starting the port.

### Bug-hunter badge system (backlog)

`DOM-OPS-003_BADGE_SYSTEM.md`, `SPEC-OPS-001_BUG_HUNTER_BADGE_SYSTEM.md`,
`SPEC-OPS-002_BUG_HUNTER_BADGE_USER_EXPERIENCE.md`, and nine award SVGs under `app/static/badges/`.
Design-only — no implementation accompanies it, and Operations already carries an unbuilt DOM-OPS
event-table backlog item this would sit on top of. Post-ship.

**Blocker on port:** `SPEC-OPS-001` collides. HEAD already defines
`docs/SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md`. The badge specs must be renumbered before landing.

### `github-pages/v2transition.html` (pre-promotion)

HEAD has `v2progress.html` but not `v2transition.html`. If this branch is promoted to default, that
page disappears from the published site. Confirm whether it is still linked; port or consciously
retire it **before** promotion, not after.

---

## VII. Maintenance

Update this file when a track changes status or a finding is closed. Record closure with the commit
SHA. Do not create a new dated tracking document for this sprint — amend this one. Historical
tracking artifacts live in `docs/archive/v2-tracking-2026/`.
