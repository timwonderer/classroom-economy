# Database Schema Documentation

This document summarizes the database schema for Classroom Token Hub based on `app/models.py`. All timestamps are stored in UTC.

---

## Core Models

### `students`
Stores student records and credentials.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `first_name` | PIIEncryptedType | Encrypted first name. |
| `last_initial` | String(1) | Last initial. |
| `block` | String(10) | Class block/period. |
| `salt` | LargeBinary(16) | Salt for credential hashes. |
| `first_half_hash` | String(64) | Hash for the first part of credential verification. |
| `second_half_hash` | String(64) | Secondary hash for backward compatibility. |
| `username_hash` | String(64) | Hash of generated username. |
| `last_name_hash_by_part` | JSON | Hashes for each last-name segment (fuzzy matching). |
| `teacher_id` | Integer (nullable) | **Deprecated** legacy primary owner reference. |
| `pin_hash` / `passphrase_hash` | Text | Credential hashes. |
| `hall_passes` | Integer | Remaining hall passes. |
| `is_rent_enabled` | Boolean | Whether rent billing is enabled. |
| `insurance_plan` | String | Legacy insurance plan label. |
| `insurance_last_paid` | DateTime | Last insurance payment timestamp. |
| `second_factor_type` | String | Second factor type. |
| `second_factor_enabled` | Boolean | Whether second factor is enabled. |
| `has_completed_setup` | Boolean | Whether first-time setup is complete. |
| `dob_sum` | Integer | Non-reversible DOB sum used for username generation. |

**Relationships**
- `teachers`: many-to-many link via `student_teachers` (authoritative ownership model).
- `transactions`, `tap_events`, `items`, `rent_payments`, `rent_waivers`, `reports` backrefs.

### `admins`
Teacher/admin accounts.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `username` | String(80) | Unique username. |
| `totp_secret` | String(32) | TOTP secret for login. |
| `created_at` | DateTime | Creation timestamp. |
| `last_login` | DateTime | Last login time. |
| `has_assigned_students` | Boolean | One-time setup flag. |

### `system_admins`
Super-user accounts with global visibility.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `username` | String(80) | Unique username. |
| `totp_secret` | String(32) | TOTP secret. |

### `student_teachers`
Authoritative mapping between students and teachers (many-to-many).

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | FK to `students.id` (CASCADE). |
| `admin_id` | Integer | FK to `admins.id` (CASCADE). |
| `created_at` | DateTime | Link creation timestamp. |

Constraints: unique on (`student_id`, `admin_id`); indexed on both columns.

### `teacher_blocks`
Roster seats created during CSV uploads so students can self-claim via join codes.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `teacher_id` | Integer | FK to `admins.id`. |
| `block` | String(10) | Class block identifier. |
| `first_name` | PIIEncryptedType | Encrypted first name from roster. |
| `last_initial` | String(1) | Last initial from roster. |
| `last_name_hash_by_part` | JSON | Hashes for fuzzy last-name matching. |
| `dob_sum` | Integer | Non-reversible DOB sum for matching. |
| `salt` / `first_half_hash` | | Matching hashes. |
| `join_code` | String(20) | Shared join code for the block. |
| `student_id` | Integer | Claimed student FK. |
| `is_claimed` | Boolean | Claim status. |
| `claimed_at` | DateTime | Claim timestamp. |

### `transactions`
Ledger entries for checking/savings accounts, scoped by teacher economy.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | FK to `students.id`. |
| `teacher_id` | Integer (nullable) | FK to `admins.id` indicating which teacher economy the transaction belongs to. |
| `amount` | Float | Positive/negative amount. |
| `timestamp` | DateTime | Transaction timestamp. |
| `account_type` | String(20) | `checking` or `savings`. |
| `description` | String(255) | Description. |
| `is_void` | Boolean | Soft-void flag. |
| `type` | String(50) | Optional transaction type label. |
| `date_funds_available` | DateTime | Availability date. |

---

## Attendance & Hall Passes

### `tap_events`
Append-only log of tap in/out actions.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | FK to `students.id`. |
| `period` | String(10) | Class period. |
| `status` | String(10) | `active` or `inactive`. |
| `timestamp` | DateTime | Event timestamp. |
| `reason` | String(50) | Optional reason. |

### `hall_pass_logs`
Tracks hall pass lifecycle.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | FK to `students.id`. |
| `reason` | String(50) | Request reason. |
| `status` | String(20) | `pending`, `approved`, `rejected`, `left`, `returned`. |
| `pass_number` | String(3) | Assigned pass number. |
| `period` | String(10) | Class period. |
| `request_time` | DateTime | Request timestamp. |
| `decision_time` | DateTime | Approval/rejection timestamp. |
| `left_time` / `return_time` | DateTime | Movement timestamps. |

### `hall_pass_settings`
Per-teacher hall pass configuration scoped by optional class block.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `teacher_id` | Integer | FK to `admins.id`; enforces tenancy. |
| `block` | String(10) | Optional block/period identifier; NULL for global teacher defaults. |
| `queue_enabled` | Boolean | Whether restricted passes are queued. |
| `queue_limit` | Integer | Maximum queued + out passes when queueing is enabled. |
| `created_at` | DateTime | Creation timestamp. |
| `updated_at` | DateTime | Update timestamp. |

---

## Store

### `store_items`
Available items in the classroom store.

Key fields: `name`, `description`, `price`, `item_type` (`immediate`, `delayed`, `collective`), `inventory`, `limit_per_student`, `auto_delist_date`, `auto_expiry_days`, `is_active`, bundle flags (`is_bundle`, `bundle_size`, `bundle_discount_amount`, `bundle_discount_percent`, `bundle_item_limit`), and `requires_approval`.

### `student_items`
Items purchased by students.

Key fields: `student_id`, `store_item_id`, `purchase_date`, `expiry_date`, `status`, `redemption_details`, `redemption_date`, `is_from_bundle`, `bundle_remaining`, `quantity_purchased`.

---

## Rent & Fees

### `rent_settings`
Global rent configuration.

Key fields: `is_enabled`, `rent_amount`, `frequency_type`, `custom_frequency_value`, `custom_frequency_unit`, `first_rent_due_date`, `due_day_of_month`, `grace_period_days`, `late_penalty_amount`, `late_penalty_type`, `late_penalty_frequency_days`, `bill_preview_enabled`, `bill_preview_days`, `allow_incremental_payment`, `prevent_purchase_when_late`, `updated_at`.

### `rent_payments`
Rent payment history.

Key fields: `student_id`, `period`, `amount_paid`, `period_month`, `period_year`, `payment_date`, `was_late`, `late_fee_charged`.

### `rent_waivers`
Tracks rent waivers.

Key fields: `student_id`, `waiver_start_date`, `waiver_end_date`, `periods_count`, `reason`, `created_by_admin_id`, `created_at`.

---

## Insurance

### `insurance_policies`
Policy definitions available to admins/students.

Key fields: `title`, `description`, `premium`, `charge_frequency`, `autopay`, `waiting_period_days`, `max_claims_count`, `max_claims_period`, `max_claim_amount`, `is_monetary`, `no_repurchase_after_cancel`, `enable_repurchase_cooldown`, `repurchase_wait_days`, `auto_cancel_nonpay_days`, `claim_time_limit_days`, bundle discounts (`bundle_with_policy_ids`, `bundle_discount_percent`, `bundle_discount_amount`), `is_active`, timestamps.

### `student_insurance`
Student enrollments in policies.

Key fields: `student_id`, `policy_id`, `status`, `purchase_date`, `cancel_date`, `last_payment_date`, `next_payment_due`, `coverage_start_date`, `payment_current`, `days_unpaid`.

### `insurance_claims`
Claims filed against policies.

Key fields: `student_policy_id`, `policy_id`, `student_id`, `status`, `claim_type`, `description`, `evidence`, `amount_requested`, `amount_approved`, `decision_date`, `decision_notes`, timestamps and reviewer metadata.

---

## Payroll & Banking

### `payroll_settings`
Configurable payroll rates/schedules (global or per block).

Key fields: `block`, `pay_rate`, `payroll_frequency_days`, `next_payroll_date`, `is_active`, `overtime_multiplier`, `settings_mode`, `daily_limit_hours`, `time_unit`, `overtime_enabled`, `overtime_threshold`, `overtime_threshold_unit`, `overtime_threshold_period`, `max_time_per_day`, `max_time_per_day_unit`, `pay_schedule_type`, `pay_schedule_custom_value`, `pay_schedule_custom_unit`, `first_pay_date`, `rounding_mode`, timestamps.

### `payroll_rewards` / `payroll_fines`
Catalog of bonuses/deductions.

Key fields: `name`, `description`, `amount`, `is_active`, `created_at`.

### `banking_settings`
Savings interest configuration.

Key fields: `savings_apy`, `savings_monthly_rate`, `interest_calculation_type`, `compound_frequency`, `interest_schedule_type`, `interest_schedule_cycle_days`, `interest_payout_start_date`, overdraft controls (`overdraft_protection_enabled`, `overdraft_fee_enabled`, `overdraft_fee_type`, `overdraft_fee_flat_amount`, progressive fee tiers, `overdraft_fee_progressive_cap`), `is_active`, timestamps.

---

## System & Support

### `admin_invite_codes`
Single-use codes for admin signup.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `code` | String(255) | Unique invite code. |
| `expires_at` | DateTime | Expiration. |
| `used` | Boolean | Whether redeemed. |
| `created_at` | DateTime | Creation timestamp. |

### `error_logs`
Server-side error logging.

Key fields: `error_type`, `message`, `stack_trace`, `created_at`.

### `user_reports`
Student-submitted reports (e.g., bugs or feedback).

Key fields: `_student_id` (FK), `category`, `description`, `contact`, `status`, `reward_amount`, review metadata, `submitted_at`, `ip_address`, `user_agent`.

### `demo_students`
Ephemeral demo accounts used for “view as student”.

Key fields: `student_id`, `created_at`, `expires_at`.

---

## Notes
- Prefer `student_teachers` for ownership; `students.teacher_id` is scheduled for removal once all data is migrated.
- All monetary values are stored as floating point; rounding is handled in business logic.
- Indices are defined on frequent lookup fields (e.g., join codes, student/teacher IDs, timestamps) to support pagination and scoped queries.
