---
trigger: always_on
---

# Test Execution Policy (CRITICAL)

The full pytest suite SHALL NOT be executed by the agent unless explicitly requested.

Reasons:

- wastes tokens
- wastes compute
- duplicates CI
- slows iteration

Instead:

1. Determine which files were modified.

2. Run only the tests covering those files.

3. If fixing a single failing test:
   run only that test.

4. If fixing a helper:
   run only tests that depend on that helper.

5. Full repository validation is performed by CI.

Do not execute:

pytest
pytest tests
pytest -q

unless the user explicitly requests a full validation.