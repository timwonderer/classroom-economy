---
description: An instruction on using repository documentations to make decisions
---

When engaging in problem solving, testing, debugging, or other workflow in this codebase, any decisions or changes made must be based on established documentation. Any proposed changes in violation of the documentation is automatically invalid.

When reading documentation, you MUST read them in this order. The earlier one overrides the lower one should they conflict

1. INV-CORE-*
2. INV-ARC-*
3. DOM-*
4. FEAT-*
5. docs/STANDARD_OPERATING_PROCEDURES
6. docs/SPECS

Documentation in the archive folder are never used as references. If a documentation indicated that a certain structure or variable is legacy, it means DO NOT USE in codebase.

