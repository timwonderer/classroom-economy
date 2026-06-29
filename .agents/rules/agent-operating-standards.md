---
trigger: always_on
---

# Classroom Economy Agent Operating Standards

## Purpose

These rules define how all AI agents operate within this repository.

These are constitutional rules, not suggestions.

If a proposed implementation conflicts with these rules, the implementation is wrong.

---

# 1. Documentation is the Source of Truth

Never assume current code is correct.

Implementation may drift.
Tests may drift.
Documentation may drift.

Before implementing, modifying, or deleting behavior:

1. Identify the governing document.
2. Verify the requested behavior exists.
3. Follow the highest authority document.

Authority order:

- INV-CORE-*
- INV-ARC-*
- DOM-*
- FEAT-*
- docs/specs

Code never overrides documentation.

---

# 2. Preserve Architecture, Not Existing Code

Do not preserve behavior simply because it currently exists.

Existing behavior may be:

- legacy
- deprecated
- migration bridge
- implementation drift
- bug

Determine whether the behavior is architecturally valid before preserving it.

---

# 3. Never Invent Compatibility Layers

This repository is pre-release.

Do not create:

- compatibility bridges
- migration shims
- legacy adapters
- fallback identity paths
- dual-write logic

unless an authoritative document explicitly requires them.

If V1 behavior conflicts with V2 architecture:

Remove V1.

---

# 4. Canonical Context

Identity is resolved exactly once.

Only context_resolver may construct CanonicalContext.

CanonicalContext consists of:

- user_id
- class_id
- seat_id
- actor_role

No downstream helper may:

- reconstruct context
- infer context
- re-resolve context
- derive identity from session
- derive authority from join_code

Helpers receive CanonicalContext as an argument.

---

# 5. Domain Sovereignty

Every behavior belongs to exactly one domain.

Never duplicate domain ownership.

Examples:

Ledger owns balances.

Obligations own recurring liabilities.

Store owns inventory.

Attendance owns attendance.

Identity owns authentication.

If unsure:

Find the governing domain document first.

---

# 6. Tests Validate Architecture

Tests are specifications.

Do not modify tests merely to make them pass.

When a test fails:

1. Determine whether the test is still architecturally valid.

2. Cite the governing documentation.

3. Classify the failure.

Allowed classifications:

A. Shared fixture/helper defect

B. Test rewrite required

C. Assertion drift

D. Product regression

E. Legacy test (delete)

Never preserve obsolete architecture through tests.

---

# 7. Database Changes

Every schema change must follow Expand → Migrate → Contract.

Never:

- rename columns directly
- drop active columns
- edit historical migrations

Follow Alembic migration policy.

---

# 8. Identity Rules

Never introduce:

teacher_id

student_id

admin_id

created_by_admin_id

or other removed runtime identifiers.

Always use canonical identity.

---

# 9. Runtime Authority

Authority comes from CanonicalContext.

Never authorize using:

join_code

URL parameters

session values

request payload

Runtime authorization always flows from CanonicalContext.

---

# 10. Read Before Write

Before modifying unfamiliar code:

Locate:

- governing invariant
- governing domain document
- feature specification

Read first.

Code second.

---

# 11. Explain Architectural Decisions

For significant changes, explain:

- governing document
- invariant
- why existing implementation was incorrect
- why new implementation matches architecture

Do not justify changes solely because tests pass.

---

# 12. When Unsure

Do not guess.

Stop.

Search documentation.

Identify governing authority.

Then proceed.

---
# Documentation First

Before modifying behavior:

1. Identify the governing invariant.
2. Identify the governing domain document.
3. Identify any governing feature specification.
4. Verify the requested behavior exists.
5. Only then modify code.

If no governing document exists:

STOP.

Do not invent architecture.

Report the missing documentation instead.