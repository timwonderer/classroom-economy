# Archive — v2 Domain Migration Tracking (2026-07 → 2026-08)

Historical, **non-authoritative** working documents from the v2 domain migration. Retained for
provenance only. Nothing here describes current system state.

Archived 2026-09-03, when `docs/TRACKING/` was reset around a single ship tracker.

**Current canonical tracker:** [`docs/TRACKING/PRODUCTION_READINESS_2026-09.md`](../../TRACKING/PRODUCTION_READINESS_2026-09.md)

## Why these were archived

- `DOMAIN_PROGRESS_MATRIX_2026.md` — the previous canonical tracker. Last updated 2026-08-20 and
  materially wrong by 2026-09-03: it listed Interpretation, Operations, and Support as NOT STARTED
  and Ledger and Payroll as BLOCKED, all contradicted by the code on this branch.
- `PHASE1_*`, `PHASE3_*`, `PHASE4_*`, `CLASS_CONFIG_PHASE3_*`, `CLASS_PHASE2_*` — SOP-DEV-002 phase
  working notes for phases that have since completed.
- `SOP-DEV-002*_AUDIT.md`, `*_QA_AUDIT*.md`, `AUDIT_BASELINE_2026-08-04.md`,
  `V2_REBUILD_VALIDATION_REPORT.md` — point-in-time audits superseded by the 2026-09-03
  doc-authoritative readiness audit.
- `V2_BUILD_SPEC/`, `V2_Full_compliance_migration_plan.md`, `V2_REMEDIATION_PLAN_2026-07-16.md`,
  `INV-ARC_CONSOLIDATION_AND_CANONICAL_OBJECT_STRATEGY.md` — planning documents whose conclusions
  were absorbed into the normative `INV-*` and `DOM-*` documents. **Read the normative docs, not
  these.**
- `TEMPLATE_AUDIT_FOR_REWIRING/`, `TEMPLATE_JINJA_INVENTORY.md`, `TERMINOLOGY_AUDIT_V1.md` —
  completed inventory sweeps.
- `DOM_ECON_ARCHAEOLOGY_2026-08-16.md`, `INTERPRETATION_METRIC_RECOVERY_2026-08-16.md`,
  `OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`, `DOM-ITR_PAYROLL_CYCLE_LIFECYCLE_HANDOFF_2026-08-30.md`
  — investigation and session-handoff notes whose outcomes have landed.
- `PYTEST_BASELINE_dc5e0efb.md` — test baseline for a commit far behind current HEAD.
