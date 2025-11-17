# Database Schema Documentation

This document provides a detailed overview of the database schema for the Classroom Token Hub application.

## Table of Contents

- [Core Models](#core-models)
  - [students](#students)
  - [admins](#admins)
  - [system_admins](#system_admins)
  - [transactions](#transactions)
- [Authentication & Access](#authentication--access)
  - [admin_invite_codes](#admin_invite_codes)
- [Features](#features)
  - [tap_events](#tap_events)
  - [hall_pass_logs](#hall_pass_logs)
  - [store_items](#store_items)
  - [student_items](#student_items)
  - [rent_settings](#rent_settings)
  - [rent_payments](#rent_payments)
  - [insurance_policies](#insurance_policies)
  - [student_insurance](#student_insurance)
  - [insurance_claims](#insurance_claims)
- [System](#system)
  - [error_logs](#error_logs)

---

## Core Models

### `students`

Stores student records and their account information.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `first_name` | PIIEncryptedType | The student's first name, encrypted at rest. |
| `last_initial` | String(1) | The student's last initial. |
| `block` | String(10) | The class block or period the student belongs to. |
| `salt` | LargeBinary(16) | A unique, random salt for this student's credentials. |
| `first_half_hash` | String(64) | A hash used for the first part of the account claim process. |
| `second_half_hash` | String(64) | A hash used for the second part of the account claim process. |
| `username_hash` | String(64) | A hash of the student's generated username. |
| `pin_hash` | Text | A hash of the student's PIN. |
| `passphrase_hash` | Text | A hash of the student's passphrase. |
| `hall_passes` | Integer | The number of hall passes the student currently has. |
| `is_rent_enabled` | Boolean | Whether rent is enabled for this student. |
| `is_property_tax_enabled` | Boolean | Whether property tax is enabled for this student. |
| `owns_seat` | Boolean | Whether the student owns their seat (for property tax). |
| `insurance_plan` | String | The name of the student's insurance plan. |
| `insurance_last_paid` | DateTime | The timestamp of the last insurance payment. |
| `second_factor_type` | String | The type of second-factor authentication enabled (e.g., 'TOTP'). |
| `second_factor_enabled` | Boolean | Whether second-factor authentication is enabled. |
| `has_completed_setup` | Boolean | Whether the student has completed the initial account setup. |
| `dob_sum` | Integer | A non-reversible sum of the student's date of birth, used for username generation. |

### `admins`

Stores administrator (teacher) accounts.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `username` | String(80) | The admin's unique username. |
| `totp_secret` | String(32) | The secret key for TOTP-based two-factor authentication. |
| `created_at` | DateTime | The timestamp when the admin account was created. |
| `last_login` | DateTime | The timestamp of the admin's last login. |

### `system_admins`

Stores system administrator (super-user) accounts.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `username` | String(80) | The system admin's unique username. |
| `totp_secret` | String(32) | The secret key for TOTP-based two-factor authentication. |

### `transactions`

Logs all financial transactions for students.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `amount` | Float | The transaction amount (positive for deposits, negative for withdrawals). |
| `timestamp` | DateTime | The timestamp of the transaction. |
| `account_type` | String(20) | The account type ('checking' or 'savings'). |
| `description` | String(255) | A description of the transaction. |
| `is_void` | Boolean | Whether the transaction has been voided. |
| `type` | String(50) | The type of transaction (e.g., 'payroll', 'bonus', 'purchase'). |
| `date_funds_available` | DateTime | The date when the funds from this transaction are available. |

---

## Authentication & Access

### `admin_invite_codes`

Stores single-use invite codes for admin registration.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `code` | String(255) | The unique invite code. |
| `expires_at` | DateTime | The timestamp when the invite code expires. |
| `used` | Boolean | Whether the invite code has been used. |
| `created_at` | DateTime | The timestamp when the invite code was created. |

---

## Features

### `tap_events`

An append-only log of student attendance tap-in and tap-out events.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `period` | String(10) | The class period for the tap event. |
| `status` | String(10) | The status of the tap ('active' or 'inactive'). |
| `timestamp` | DateTime | The timestamp of the tap event. |
| `reason` | String(50) | The reason for the tap-out (e.g., 'done', 'restroom'). |

### `hall_pass_logs`

Logs all hall pass requests and their status.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `reason` | String(50) | The reason for the hall pass request. |
| `status` | String(20) | The status of the request ('pending', 'approved', 'rejected', 'left', 'returned'). |
| `pass_number` | String(3) | The unique pass number assigned upon approval. |
| `period` | String(10) | The class period of the request. |
| `request_time` | DateTime | The timestamp of the request. |
| `decision_time` | DateTime | The timestamp of the decision (approval/rejection). |
| `left_time` | DateTime | The timestamp when the student left the class. |
| `return_time` | DateTime | The timestamp when the student returned to class. |

### `store_items`

Stores items available for purchase in the classroom store.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `name` | String(100) | The name of the item. |
| `description` | Text | A description of the item. |
| `price` | Float | The price of the item. |
| `item_type` | String(20) | The type of item ('immediate', 'delayed', 'collective'). |
| `inventory` | Integer | The number of items in stock (null for unlimited). |
| `limit_per_student` | Integer | The maximum number of this item a student can purchase (null for no limit). |
| `auto_delist_date` | DateTime | The date when the item will be automatically removed from the store. |
| `auto_expiry_days` | Integer | The number of days after purchase before the item expires. |
| `is_active` | Boolean | Whether the item is currently available in the store. |

### `student_items`

Tracks items purchased by students.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `store_item_id` | Integer | Foreign key to `store_items.id`. |
| `purchase_date` | DateTime | The timestamp of the purchase. |
| `expiry_date` | DateTime | The timestamp when the item expires. |
| `status` | String(20) | The status of the item ('purchased', 'pending', 'processing', 'completed', 'expired', 'redeemed'). |
| `redemption_details` | Text | Notes from the student on how they want to use the item. |
| `redemption_date` | DateTime | The timestamp when the student requested to use the item. |

### `rent_settings`

A singleton table to store global rent settings.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `rent_amount` | Float | The amount of rent due each month. |
| `due_day_of_month` | Integer | The day of the month when rent is due. |
| `late_fee` | Float | The fee for late rent payments. |
| `grace_period_days` | Integer | The number of days after the due date before a payment is considered late. |
| `is_enabled` | Boolean | Whether the rent system is enabled. |
| `updated_at` | DateTime | The timestamp of the last update to the settings. |

### `rent_payments`

Logs rent payments made by students.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `period` | String(10) | The class period for which rent was paid. |
| `amount_paid` | Float | The amount paid. |
| `period_month` | Integer | The month for which rent was paid (1-12). |
| `period_year` | Integer | The year for which rent was paid. |
| `payment_date` | DateTime | The timestamp of the payment. |
| `was_late` | Boolean | Whether the payment was late. |
| `late_fee_charged` | Float | The late fee charged, if any. |

### `insurance_policies`

Stores insurance policies available for purchase.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `title` | String(100) | The title of the policy. |
| `description` | Text | A description of the policy. |
| `premium` | Float | The monthly cost of the policy. |
| `charge_frequency` | String(20) | How often the premium is charged (e.g., 'monthly'). |
| `autopay` | Boolean | Whether autopay is enabled for the policy. |
| `waiting_period_days` | Integer | The number of days before coverage begins. |
| `max_claims_count` | Integer | The maximum number of claims allowed per period. |
| `max_claims_period` | String(20) | The period for the maximum claims count (e.g., 'month'). |
| `max_claim_amount` | Float | The maximum amount that can be claimed per incident. |
| `is_monetary` | Boolean | Whether the policy pays out money or provides an item/service. |
| `no_repurchase_after_cancel` | Boolean | Whether the policy can be repurchased after being canceled. |
| `enable_repurchase_cooldown` | Boolean | Whether there is a cooldown period before repurchase. |
| `repurchase_wait_days` | Integer | The number of days in the repurchase cooldown period. |
| `auto_cancel_nonpay_days` | Integer | The number of days of non-payment before the policy is automatically canceled. |
| `claim_time_limit_days` | Integer | The number of days after an incident to file a claim. |
| `bundle_with_policy_ids` | Text | A comma-separated list of policy IDs for bundle discounts. |
| `bundle_discount_percent` | Float | The percentage discount for purchasing a bundle. |
| `bundle_discount_amount` | Float | The flat amount discount for purchasing a bundle. |
| `is_active` | Boolean | Whether the policy is currently available. |
| `created_at` | DateTime | The timestamp when the policy was created. |
| `updated_at` | DateTime | The timestamp of the last update. |

### `student_insurance`

Links students to the insurance policies they have purchased.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `policy_id` | Integer | Foreign key to `insurance_policies.id`. |
| `status` | String(20) | The status of the policy ('active', 'cancelled', 'suspended'). |
| `purchase_date` | DateTime | The timestamp of the purchase. |
| `cancel_date` | DateTime | The timestamp of the cancellation. |
| `last_payment_date` | DateTime | The timestamp of the last premium payment. |
| `next_payment_due` | DateTime | The date of the next premium payment. |
| `coverage_start_date` | DateTime | The date when coverage begins (after the waiting period). |
| `payment_current` | Boolean | Whether the student's payments are current. |
| `days_unpaid` | Integer | The number of days the policy has been unpaid. |

### `insurance_claims`

Logs insurance claims filed by students.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `student_insurance_id` | Integer | Foreign key to `student_insurance.id`. |
| `policy_id` | Integer | Foreign key to `insurance_policies.id`. |
| `student_id` | Integer | Foreign key to `students.id`. |
| `incident_date` | DateTime | The date of the incident. |
| `filed_date` | DateTime | The timestamp when the claim was filed. |
| `description` | Text | A description of the incident. |
| `claim_amount` | Float | The amount claimed (for monetary policies). |
| `claim_item` | Text | The item/service claimed (for non-monetary policies). |
| `comments` | Text | Additional comments from the student. |
| `status` | String(20) | The status of the claim ('pending', 'approved', 'rejected', 'paid'). |
| `rejection_reason` | Text | The reason for rejection, if applicable. |
| `admin_notes` | Text | Notes from the admin who processed the claim. |
| `approved_amount` | Float | The amount approved by the admin. |
| `processed_date` | DateTime | The timestamp when the claim was processed. |
| `processed_by_admin_id` | Integer | Foreign key to `admins.id` of the admin who processed the claim. |

---

## System

### `error_logs`

Logs all application errors.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `timestamp` | DateTime | The timestamp of the error. |
| `error_type` | String(100) | The type of error (e.g., 'ValueError'). |
| `error_message` | Text | The error message. |
| `request_path` | String(500) | The URL path that caused the error. |
| `request_method` | String(10) | The HTTP method of the request. |
| `user_agent` | String(500) | The user agent of the client. |
| `ip_address` | String(50) | The IP address of the client. |
| `log_output` | Text | The last 50 lines of the application log. |
| `stack_trace` | Text | The full stack trace of the error. |
