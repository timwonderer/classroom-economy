# REF-TERM-002: User Vocabulary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| REF-TERM-002     | 1.0     | 2026-06-15     | N/A        | Normative       |

## I. Purpose

Define the authoritative user-facing vocabulary for the Classroom Token Hub. These are the terms that appear in teacher and student interfaces, user guides, help text, and support communications.

## II. Scope

This glossary covers terms that teachers or students encounter during normal use. Each term carries a plain-language definition suitable for non-technical audiences. Implementation details, internal table names, and developer-only concepts belong in `REF-TERM-001`.

Terms that also appear in REF-TERM-001 carry their user-facing definition here and their implementation-facing definition there.

## III. Authority Level

Normative. User-interface text, help copy, and user documentation must use these terms as defined here.

## III-A. Dependencies

- `REF-TERM-001_DEVELOPER_VOCABULARY.md` (developer-facing counterpart)

---

## IV. Glossary

### Economy & Policy

**Classroom Token Hub**
The name of this classroom economy platform.

**Classroom Wage Index (CWI)**
The expected weekly income a student earns for perfect attendance. All prices, savings goals, and economic recommendations are measured against this number.

**Policy Mode**
The overall economic climate of a class, selected by the teacher. There are three modes:

- **Comfortable** — Lower pressure, faster savings growth, more room for mistakes.
- **Default** — Balanced middle ground; the recommended starting point.
- **Tight** — Higher pressure, slower savings growth, more economic challenge.

**Economy Health**
A teacher-facing dashboard that shows whether current class settings (wages, rent, prices) are aligned with the selected policy mode and whether the economy is sustainable.

**Budget Survival Test**
A check that asks: can students still save a minimum amount each week after paying all recurring costs? If not, the economy may need rebalancing.

**Catastrophe Stability Rule**
A check that asks: can a student recover within about one week from two unexpected costs (like fines or lost items)?

### Money & Balances

**Checking Balance**
The amount of money a student can spend right now.

**Savings Balance**
Money a student has set aside in savings. May earn interest depending on class banking settings.

**Spendable Balance**
The total amount available for purchases or transfers — equivalent to checking balance in most contexts.

**Accrued Interest**
Interest that has been earned on savings but not yet added to the spendable savings balance. It will be posted at the next payout.

**Accrual Frequency**
How often savings interest is earned — daily, weekly, or monthly, as set by the teacher.

**Compound Frequency**
How often previously earned interest starts earning its own interest.

**Interest Payout**
When accrued interest is officially added to a student's savings balance so it can be spent or continue earning.

### Attendance

**Attendance Session**
A record of when a student tapped in and tapped out of class. Used to calculate daily earnings.

**Class Day**
The school day as defined by the class timezone — midnight to midnight. Daily limits and attendance windows are measured within this boundary.

**Tap Enabled**
Whether a student is currently allowed to tap in for attendance. A teacher can disable this without erasing prior attendance history.

**Done for Day**
A per-student daily lock that prevents further attendance taps after the student has completed their session for the day.

### Class & Identity

**Class**
An individual classroom economy. Each class has its own join code, settings, students, and financial records. A teacher may run multiple classes; a student may belong to multiple classes.

**Join Code**
The short code students use to find and join a class. It is the public-facing identifier for a class (distinct from the class display name); internally, the system uses a private class ID.

**Section**
A label for the class period — for example, "Block A" or "Period 3." Used for display only; it does not affect how the system scopes data.

**Seat**
A student's or teacher's position within a specific class. Everything a student does in a class — earning, spending, attendance — is attached to their seat in that class.

**Student Seat**
A seat held by a student. The student earns, spends, and participates through this seat.

**Teacher Seat**
A seat held by the teacher. The teacher manages the class through this seat.

### Store & Goals

**Store Item**
A product, privilege, or reward available for purchase in the class store. Teachers set the price and availability.

**Collective Goal**
A shared class savings objective. All participating students contribute toward a common target, encouraging teamwork.

**Redemption Prompt**
Instructions attached to a store item that tell the teacher how to fulfill the purchase when a student redeems it.

### Hall Passes

**Hall Pass**
A time-tracked pass that allows a student to leave the classroom. Passes can be requested, approved, and timed through the system.

**Queue**
When enabled, students request hall passes and wait in line rather than receiving them immediately. The teacher controls queue settings and simultaneous limits.

### Rent & Obligations

**Rent**
A recurring cost that students pay at regular intervals — for example, weekly desk rent. Rent can include linked benefits like hall passes.

**Obligation**
A scheduled financial responsibility assigned to a student, such as rent or an assessment. The system tracks whether each obligation is due, paid, overdue, or waived.

**Waiver**
A teacher action that marks an obligation as satisfied without requiring payment.

### Recovery & Security

**Reset Code**
A short code shown to the teacher that a student can use to recover access to their account without affecting their class balance or history.

**Passkey**
A modern, passwordless way for teachers to log in using biometrics or a security key instead of a password.

**Two-Factor Authentication (2FA)**
An extra security step required for teacher accounts. After entering a password, the teacher must also enter a time-based code from an authenticator app.

### Policy Changes

**Activation Intent**
When a teacher changes an economy setting, this controls when the change takes effect: immediately, at the start of the next period, or manually at a chosen time.

**Future Economic Law**
A pending change to class settings that has been announced but hasn't taken effect yet. Students and teachers can see what will change and when.

### Analytics

**Money Velocity**
A measure of how quickly money circulates through the classroom economy. High velocity means money is being earned and spent actively; low velocity may indicate stagnation.

---

## V. Terms Not Used in User-Facing Contexts

The following terms from the developer vocabulary (`REF-TERM-001`) do not appear in user interfaces and should not be used in student- or teacher-facing text:

`class_id`, `seat_id`, `correlation_id`, `idempotency_key`, `FEAT`, `domain guard`, `ledger_transaction`, `audit_log`, `policy_versions`, `policy_transitions`, `append-only policy evolution`, `domain blindness`, `operational events`, `TemporalContext`.

If user-facing text needs to refer to the concept behind one of these terms, use the corresponding plain-language term from this glossary instead.

---

## VI. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-15 | Terminology Audit | Initial creation from TERMINOLOGY_AUDIT_V1.md governance classification. Covers all user-facing terms from the 82-term KEEP set plus plain-language definitions for merged concepts. |
