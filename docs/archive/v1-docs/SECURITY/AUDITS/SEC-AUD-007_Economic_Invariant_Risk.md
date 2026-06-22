# Stage 2 – Economic Invariant Risk Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-007| 1.1 | 2026-03-08 | 1.0 |Normative|

**Date:** 2026-02-16

**Status:** Complete

**Updated:** 2026-02-16

**Updated by:** Timothy Chang (signed commit on GitHub)

## Findings

### 1. Cross-Tenant Fund Leakage in Purchase Authorization
**Severity:** Critical

**File:** `app/routes/api.py`

**Line Range:** 408-413

**Category:** Multi-tenant boundaries

**Description:**
The `purchase_item` route authorizes purchases by checking `student.checking_balance` (a global property summing funds across all classes) against the item price, instead of using the class-scoped balance calculated earlier.


**Why This Violates Financial Invariants:**
This allows a student with funds in Class A to purchase items in Class B even if they have $0 or negative balance in Class B. The transaction is then recorded in Class B (correctly scoped), driving Class B's ledger into negative territory based on funds that exist only in Class A. This breaks tenant isolation and fund segregation.
**Worst Case Scenario:**

A student uses funds earned in a high-paying class to drain the economy of a stricter class, effectively counterfeiting currency across tenant boundaries.

**Confidence:** 100%

---
### 2. Global Balance Properties Violate Tenant Isolation

**Severity:** Critical

**File:** `app/models.py`

**Line Range:** 463-473

**Category:** Multi-tenant boundaries

**Description:**
The `Student.checking_balance` and `Student.savings_balance` properties calculate balances by summing *all* non-void transactions for a student, ignoring `join_code`.

**Why This Violates Financial Invariants:**
Any logic relying on these properties (like the purchase check above, or CSV exports) inherently mixes data from different tenants. A student belonging to multiple classes has no isolated "balance" in this model, only a global aggregate.

**Worst Case Scenario:**
System-wide confusion where students see inflated balances, and financial decisions (overdrafts, purchases) are made on incorrect global aggregates rather than the relevant class economy.

**Confidence:** 100%

---
### 3. Cross-Tenant Data Leakage in CSV Export

**Severity:** High
**File:** `app/routes/admin.py`

**Line Range:** 7156-7158

**Category:** Multi-tenant boundaries

**Description:**
The `export_students` route writes `student.checking_balance`, `student.savings_balance`, and `student.total_earnings` to the CSV export. Since these properties are global aggregates (see Finding #2), this exposes a student's total financial status across *all* their classes to any single teacher who exports their roster.

**Why This Violates Financial Invariants:**
This violates tenant isolation and privacy. Teacher A should only see the funds earned/spent in Teacher A's class. Exporting the global sum leaks information about the student's activity in Teacher B's class.

**Worst Case Scenario:**
A teacher uses the exported data to grade or judge students based on financial activity in other classes, or infers private information about other class economies.

**Confidence:** 100%

---
### 4. Ledger Mutability via Direct Voiding

**Severity:** High

**File:** `app/routes/admin.py`

**Line Range:** 6597 (void_payroll_transaction), 6629 (void_transactions_bulk), 9454 (resolve_issue)

**Category:** Void logic

**Description:**
Transactions are voided by setting the `is_void` flag to `True` on the original record.

**Why This Violates Financial Invariants:**
Financial ledgers should be immutable. Voids should be implemented as a new transaction with an inverted amount (reversal) linked to the original. Modifying the original record destroys the historical state of the ledger at the time the transaction occurred and complicates point-in-time reconstruction.

**Worst Case Scenario:**
An admin voids a transaction from a closed accounting period, changing historical reports retroactively without a clear audit trail of *when* the void happened.

**Confidence:** 95%

---
### 5. Precision Loss due to Float Usage
**Severity:** High

**File:** `app/models.py` (Line 467, 473), `app/routes/admin.py` (Line 2225)

**Category:** Balance calculations

**Description:**
Financial values are frequently cast to `float` for calculations or API responses. `Student.checking_balance` explicitly casts `Decimal` to `float`.

**Why This Violates Financial Invariants:**
Floats are imprecise for currency. Accumulating float errors can lead to "penny shaving" issues, where ledger sums do not equal the sum of their parts (e.g., $0.10 + $0.20 != $0.30).

**Worst Case Scenario:**
Balances drift over time due to rounding errors, causing reconciliation failures or allowing students to exploit fractional discrepancies.

**Confidence:** 100%

---
### 6. Audit Trail Destruction in Join Code Cleanup
**Severity:** ~~Medium~~ Intended Behavior / Need Guardrail

**File:** `app/routes/admin.py`

**Line Range:** 212-313

**Category:** Audit trails

**Description:**
`_hard_delete_join_code_scope` performs hard deletes (`.delete()`) on `Transaction`, `RentPayment`, `InsuranceClaim`, and other financial records.

~~**Why This Violates Financial Invariants:**
While intended for cleaning up deleted classes, hard deleting financial records prevents any future audit or dispute resolution regarding that data. "Deleted" classes should ideally be archived (soft deleted) or at least their financial history preserved for a retention period.~~

~~**Worst Case Scenario:**
A teacher deletes a class by mistake or maliciously to hide embezzlement/fraud, and the financial history is permanently lost.~~

~~**Confidence:** 90~~

> [!IMPORTANT]
> Join code is the sole multitenancy boundary of this application. Destruction of join code necessitates the destruction all data scoped under that join code. No global ledger or archival storage is allowed via any route of the application. Any future changes to this design principle must be explicitly written and justified.

**Why was this risk downgraded:** Join code is the sole boundary in which a "Class" is defined. "Teachers" and "Students" are merely tenants within the scope of that boundary. When a join code is deleted, everything derived from that join code cease to exist. If a financial record is kept without join code, it would be useless since it would be devoid of join code (and therefore the users under that join code). If historic financial record can be traced back to its user without join code, that would render join code a mere facade that does not, in fact, define multitenancy boundary. This behavior is not only appropriate, but necessary to uphold the grounding principle of this application: minimal data retention. This means if a teacher delete the class, they are effectively deleting the join code and everything related to that join code. This application does not have hidden global ledger, but tiny scoped universe wrapped with join code.

**Additional Precaution:** The main concern of this behavior is not, in fact, concealment of malicious activity. Because teachers are constantly making decisions and could suffer from decision fatigue (or just being tired), it is very likely a teacher could, in theory, accidentally delete the class without the intent to delete the class. Without secondary prompts and explicit confirmation from the teacher, it would be an UX landmine and UI failure. Therefore, a couple of UX designs must be in place:
1. A highly visible modal must open up and clearly state the consequences of such action, preferably with simple sentence no longer than a line.
2. A countdown timer of at least 30 seconds must be displayed in the modal. During the 30 second period, the `Yes, I am sure` button is disabled (the `cancel` button is always available). The behavior of the `return` key on this modal should be the same as `cancel`
3. Once the teacher click on `Yes, I am sure`, open a second modal that have the teacher type in *Delete [insert class name here]* in a textbox. Disable copy and pasting within the modal so the teacher must type it in. 
4. After the positive explicitly typed confirmation, the teacher must click and hold the `Confirm Deletion` button for 10 seconds with visible timer. The `cancel` button is always available and instant. The behavior of the `return` key on this modal should be the same as `cancel`
5. Once the `Confirm Deletion` is held for 10 seconds, the modal will close and proceed with the current deletion workflow.

