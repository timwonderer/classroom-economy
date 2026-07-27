# Audit State Verification Rule

**CRITICAL:** To prevent false positives/negatives during code audits, QA reviews, or certification runs, you MUST verify the actual state of the workspace on disk at the beginning of the task.

---

## The Rule

1. **Never Assume Codebase State**: You must never rely on cached test results, logs, or codebase models from prior turns or conversations if a turn boundary has passed or a server/environment restart has occurred.
2. **Mandatory Synchronization Steps**: Before compiling any findings or editing an audit checklist, you MUST:
   - Run `git log -n 5 --oneline` to confirm the exact commit context and history.
   - Run `git status` to check for active local changes.
   - Run targeted test suites (using `pytest` or standard test commands) to verify test execution status against the current commit on disk.
3. **Audit Truth Tracing**: Verify database schemas directly by inspecting the active model classes (`app/models.py`) and/or running database inspection commands rather than assuming database configuration based on old spec files.
