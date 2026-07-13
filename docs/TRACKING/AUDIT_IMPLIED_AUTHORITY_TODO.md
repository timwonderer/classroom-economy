# Audit TODO: Implied-Authorization Changes

This file records the remaining doc gaps for changes that were treated as
implied authorization during the commit audit.

## `c6e11fe2` - `tests/test_economy_policy_mode.py`

- Establish an explicit governing document that authorizes the FEAT-wrapped
  fixture reshaping used by the policy-mode regression tests.
- Clarify whether the test helper refactor is owned by `FEAT-IDEN-001`,
  `FEAT-CLASS-*`, or a domain-specific testing rule.
- Document whether `create_class_scope(...)` / `make_student_identity(...)`
  are the canonical test construction path for policy-mode and rebalance
  scenarios, or whether a dedicated helper contract is required.

## `c6e11fe2` - `tests/test_collective_goal_expiration.py`

- Establish an explicit governing document that authorizes the FEAT-wrapped
  fixture reshaping used by the collective-goal expiration tests.
- Clarify the canonical helper contract for creating teacher, student, and
  collective-item fixtures under FEAT ownership.
- Document the required authority boundary for `process_expired_collective_goals`
  test setup so the fixture pattern can be cited directly rather than inferred.
