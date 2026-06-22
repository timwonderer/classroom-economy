# ARC-SYS-002: Deterministic Analytics Alerting Pipeline

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-SYS-002     | 1.0     | 2026-04-12     | N/A        | Constitutional  |

## I. Purpose
Define the architecture for proactive platform health monitoring through deterministic analytics snapshots and automated sysadmin alerting.

## II. Scope
Applies to the `AnalyticsSnapshot` and `AnalyticsAlert` models, the periodic snapshot aggregation jobs, and the sysadmin alerting dashboard.

## III. Authority Level
Constitutional (ARC Tier). Subordinate to INV-CORE-000 (Section 1: Isolation).

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `ARC-SYS-001_Sysadmin_Interface.md`

## V. Data Capture: The Snapshot Mechanical
To monitor the health of isolated class economies without violating multi-tenancy boundaries, the system uses a periodic "Snapshot" pattern.

### 1. `AnalyticsSnapshot`
- **Definition**: An immutable record of the aggregate health metrics for a specific `class_id` at a precise point in time.
- **Metrics Captured**:
  - Total Money Supply (Cents)
  - Collective Goal Progress (%)
  - Active Student Count
  - Average Balance
  - Gini Coefficient (Inequality metric)
- **Constraint**: Snapshots are derived from ledger state but do not store individual student transaction data.

## VI. Alerting Pipeline: Deterministic Triggers
Alerts are generated automatically when a snapshot violates predefined economic health thresholds.

### 1. `AnalyticsAlert`
- **Model**: Bridges the specific class economy to the System Admin interface.
- **Attributes**:
  - `alert_type`: (e.g., `INSOLVENCY_RISK`, `HYPER_INFLATION`, `GOAL_STAGNATION`).
  - `severity`: (INFO, WARNING, CRITICAL).
  - `status`: (ACTIVE, ACKNOWLEDGED, RESOLVED).
  - `context_payload`: JSON blob containing the snapshot metrics that triggered the alert.

### 2. Trigger Logic
- Triggers must be **deterministic**: If Metric X > Threshold Y, an alert MUST be emitted.
- Trigger definitions live in the backend service layer (`app/services/analytics_service.py`).
- Alerts are deduplicated: A new alert for an existing active condition on the same `class_id` will update the existing alert rather than creating a duplicate.

## VII. Sysadmin Intervention Flow
Sysadmins interact with alerts via the `/sysadmin/alerts` dashboard.

1. **Detection**: Sysadmin reviews the Active Alerts list.
2. **Analysis**: Sysadmin inspects the `context_payload` to understand why the alert fired.
3. **Action**: 
   - **Acknowledge**: Mark as acknowledged while investigating.
   - **Contact**: Reach out to the teacher (via provided teacher identity) to discuss class health.
   - **Ignore**: Mark as resolved if the economic state is intentional or a known test case.

## VIII. Multi-tenancy Compliance
- The `AnalyticsAlert` model contains a `class_id` reference only for internal routing.
- Sysadmins can see aggregate metrics (Snapshot) but MUST NOT be able to drill down into individual student names or transaction histories through the alert context (per INV-CORE-000).

## IX. Amendment
Revisions to trigger definitions or threshold logic must be documented here and reflected in the implementation.
