# Audit TODO: Implied-Authorization Changes

This file records the remaining doc gaps for changes that were treated as
implied authorization during the commit audit.

## `c6e11fe2` - `tests/test_economy_policy_mode.py`

- Resolved: the policy-mode fixture reshaping now uses explicit class scope
  construction and keeps `join_code` as display metadata only.
- The canonical helper path for these scenarios is
  `create_class_scope(...)` plus explicit FEAT-owned fixture setup where the
  test needs additional rows.

## `c6e11fe2` - `tests/test_collective_goal_expiration.py`

- Resolved: the collective-goal expiration slice now threads class scope
  explicitly through the helper boundary and no longer infers class ownership
  from teacher lookup.
- The canonical helper contract for this slice is explicit class_id threading
  plus FEAT-owned creation of the teacher, student, and collective item rows.
