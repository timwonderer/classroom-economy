# Support Content Inventory

Generated: 2026-08-15
Total templates scanned: 96

## Legend

- **EXTRACTED** — support text present in the template, will be moved into the canonical content registry
- **GAP** — expected support text is missing (complex UI, consequential action, unfamiliar term with no explanation)
- **ANOMALY** — page normally doesn't require support text but has a UX oddity worth logging (missing next-step link on error page, unlabeled action, etc.)

Each entry has: proposed content ID, source file:line, kind, one-line description. GAP entries also carry a severity (`informational` | `decision-support`) and a reason. Do not include real body text — the extraction pass fills that in.

## EXTRACTED

- `admin.admin_account_delete.aria` — source: admin_account_delete.html:60 — kind: aria — description: Delete countdown
- `admin.admin_account_delete.warning` — source: admin_account_delete.html:13 — kind: warning — description: warning block
- `admin.admin_analytics_dashboard.alert` — source: admin_analytics_dashboard.html:31 — kind: alert — description: alert block
- `admin.admin_analytics_events.alert` — source: admin_analytics_events.html:103 — kind: alert — description: alert block
- `admin.admin_analytics_events.hint` — source: admin_analytics_events.html:63 — kind: hint — description: {{ event.event_date|format_datetime('%I:%M %p') }}
- `admin.admin_analytics_student_detail.alert` — source: admin_analytics_student_detail.html:78 — kind: alert — description: alert block
- `admin.admin_analytics_student_detail.alert` — source: admin_analytics_student_detail.html:175 — kind: alert — description: alert block
- `admin.admin_analytics_student_detail.hint` — source: admin_analytics_student_detail.html:19 — kind: hint — description: — Individual Performance vs CWI
- `admin.admin_announcement_form.alert` — source: admin_announcement_form.html:23 — kind: alert — description: alert block
- `admin.admin_announcement_form.alert` — source: admin_announcement_form.html:30 — kind: alert — description: alert block
- `admin.admin_announcement_form.hint` — source: admin_announcement_form.html:55 — kind: hint — description: Students will see this message on their dashboard.
- `admin.admin_announcement_form.hint` — source: admin_announcement_form.html:83 — kind: hint — description: Leave blank for no expiration. Expired announcements will be hidden automatically.
- `admin.admin_announcement_form.hint` — source: admin_announcement_form.html:91 — kind: hint — description: Inactive announcements are hidden from students.
- `admin.admin_announcements.alert` — source: admin_announcements.html:115 — kind: alert — description: alert block
- `admin.admin_announcements.alert` — source: admin_announcements.html:45 — kind: alert — description: alert block
- `admin.admin_attendance_log.alert` — source: admin_attendance_log.html:36 — kind: alert — description: alert block
- `admin.admin_attendance_log.aria` — source: admin_attendance_log.html:226 — kind: aria — description: Attendance pagination
- `admin.admin_attendance_log.warning` — source: admin_attendance_log.html:76 — kind: warning — description: warning block
- `admin.admin_banking.alert` — source: admin_banking.html:42 — kind: alert — description: alert block
- `admin.admin_banking.alert` — source: admin_banking.html:576 — kind: alert — description: alert block
- `admin.admin_banking.alert` — source: admin_banking.html:490 — kind: alert — description: alert block
- `admin.admin_banking.alert` — source: admin_banking.html:128 — kind: alert — description: alert block
- `admin.admin_banking.aria` — source: admin_banking.html:432 — kind: aria — description: Transaction pagination
- `admin.admin_banking.aria` — source: admin_banking.html:524 — kind: aria — description: Interest rate input mode
- `admin.admin_banking.hint` — source: admin_banking.html:579 — kind: hint — description: Enter an interest rate to see estimated payouts
- `admin.admin_banking.hint` — source: admin_banking.html:549 — kind: hint — description: Annual Percentage Yield for savings accounts
- `admin.admin_banking.hint` — source: admin_banking.html:813 — kind: hint — description: Enter an interest rate to see estimated payouts
- `admin.admin_banking.hint` — source: admin_banking.html:668 — kind: hint — description: Fixed fee charged per overdraft transaction
- `admin.admin_banking.hint` — source: admin_banking.html:186 — kind: hint — description: Students w/ Savings
- `admin.admin_banking.hint` — source: admin_banking.html:614 — kind: hint — description: Number of days in each cycle (for monthly schedule)
- `admin.admin_banking.hint` — source: admin_banking.html:705 — kind: hint — description: Optional maximum total fees per period
- `admin.admin_banking.hint` — source: admin_banking.html:182 — kind: hint — description: Total Deposits
- `admin.admin_banking.hint` — source: admin_banking.html:566 — kind: hint — description: Monthly interest rate
- `admin.admin_banking.hint` — source: admin_banking.html:599 — kind: hint — description: How often interest compounds (only applies to compound interest)
- `admin.admin_banking.hint` — source: admin_banking.html:638 — kind: hint — description: If enabled, negative checking balances will be covered by savings
- `admin.admin_banking.hint` — source: admin_banking.html:174 — kind: hint — description: Total Checking
- `admin.admin_banking.hint` — source: admin_banking.html:178 — kind: hint — description: Total Savings
- `admin.admin_banking.hint` — source: admin_banking.html:620 — kind: hint — description: Date when interest payouts begin
- `admin.admin_banking.warning` — source: admin_banking.html:82 — kind: warning — description: warning block
- `admin.admin_banking.warning` — source: admin_banking.html:122 — kind: warning — description: warning block
- `admin.admin_customizations.alert` — source: admin_customizations.html:97 — kind: alert — description: alert block
- `admin.admin_customizations.hint` — source: admin_customizations.html:125 — kind: hint — description: Class ID:
- `admin.admin_customizations.hint` — source: admin_customizations.html:114 — kind: hint — description: Teacher ID:
- `admin.admin_customizations.hint` — source: admin_customizations.html:130 — kind: hint — description: These identifiers are used for support and troubleshooting.
- `admin.admin_customizations.hint` — source: admin_customizations.html:118 — kind: hint — description: Account Created:
- `admin.admin_dashboard.alert` — source: admin_dashboard.html:33 — kind: alert — description: alert block
- `admin.admin_dashboard.aria` — source: admin_dashboard.html:251 — kind: aria — description: Refund and remove
- `admin.admin_dashboard.hint` — source: admin_dashboard.html:242 — kind: hint — description: {{ req.store_item.name }}
- `admin.admin_dashboard.warning` — source: admin_dashboard.html:21 — kind: warning — description: warning block
- `admin.admin_economic_engine.alert` — source: admin_economic_engine.html:41 — kind: alert — description: alert block
- `admin.admin_economic_engine.alert` — source: admin_economic_engine.html:45 — kind: alert — description: alert block
- `admin.admin_economic_engine.alert` — source: admin_economic_engine.html:78 — kind: alert — description: alert block
- `admin.admin_economic_engine.alert` — source: admin_economic_engine.html:256 — kind: alert — description: alert block
- `admin.admin_economic_engine.hint` — source: admin_economic_engine.html:458 — kind: hint — description: Sorted by severity
- `admin.admin_economic_engine.warning` — source: admin_economic_engine.html:241 — kind: warning — description: warning block
- `admin.admin_economic_engine.warning` — source: admin_economic_engine.html:316 — kind: warning — description: warning block
- `admin.admin_economic_engine.warning` — source: admin_economic_engine.html:114 — kind: warning — description: warning block
- `admin.admin_economic_engine.warning` — source: admin_economic_engine.html:94 — kind: warning — description: warning block
- `admin.admin_edit_insurance_policy.alert` — source: admin_edit_insurance_policy.html:144 — kind: alert — description: alert block
- `admin.admin_edit_insurance_policy.aria` — source: admin_edit_insurance_policy.html:10 — kind: aria — description: breadcrumb
- `admin.admin_edit_insurance_policy.hint` — source: admin_edit_insurance_policy.html:49 — kind: hint — description: This store item is the class-configured capability FEAT-STOR-001 grants when the policy is purchased.
- `admin.admin_edit_insurance_policy.hint` — source: admin_edit_insurance_policy.html:102 — kind: hint — description: Comma-separated policy IDs. If one bundled policy belongs to a tier group, any tier in that group satisfies the slot.
- `admin.admin_edit_item.alert` — source: admin_edit_item.html:131 — kind: alert — description: alert block
- `admin.admin_edit_item.alert` — source: admin_edit_item.html:61 — kind: alert — description: alert block
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:154 — kind: hint — description: If set, the goal expires at end of this date. If the goal is not reached, the item deactivates; reactivating always starts progress at 0.
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:119 — kind: hint — description: Leave blank for no purchase limit
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:99 — kind: hint — description: Hold Ctrl/Cmd to select multiple periods. Leave empty to show to all periods.
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:77 — kind: hint — description: Choose how students can use this item
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:58 — kind: hint — description: Optional pricing category for organization
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:236 — kind: hint — description: Item will be automatically hidden on this date
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:87 — kind: hint — description: Suppress live CWI warnings for this item and hide it from Economy Health.
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:215 — kind: hint — description: Discount percentage (e.g., 10 for 10% off)
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:175 — kind: hint — description: Bundled items give students multiple uses that can be redeemed separately
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:143 — kind: hint — description: Number of students who must purchase to unlock this item
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:92 — kind: hint — description: For expensive items students save for over many weeks (won't trigger CWI warnings)
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:114 — kind: hint — description: Leave blank for unlimited inventory
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:210 — kind: hint — description: Minimum quantity to qualify for discount
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:203 — kind: hint — description: Offer a discount when students buy multiple quantities
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:182 — kind: hint — description: How many items in this bundle?
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:137 — kind: hint — description: Choose how the goal is calculated
- `admin.admin_edit_item.hint` — source: admin_edit_item.html:241 — kind: hint — description: Days before item expires (for delayed-use items)
- `admin.admin_edit_item.warning` — source: admin_edit_item.html:147 — kind: warning — description: warning block
- `admin.admin_feature_settings.aria` — source: admin_feature_settings.html:32 — kind: aria — description: {{ feat.name }}
- `admin.admin_feature_settings.hint` — source: admin_feature_settings.html:26 — kind: hint — description: {{ feat.description }}
- `admin.admin_hall_pass.alert` — source: admin_hall_pass.html:31 — kind: alert — description: alert block
- `admin.admin_hall_pass.aria` — source: admin_hall_pass.html:209 — kind: aria — description: Hall pass request actions
- `admin.admin_hall_pass.aria` — source: admin_hall_pass.html:335 — kind: aria — description: History pagination
- `admin.admin_hall_pass.hint` — source: admin_hall_pass.html:260 — kind: hint — description: Left: {{ req.left_time | format_datetime }} | Period: {{ req.period }}
- `admin.admin_hall_pass.hint` — source: admin_hall_pass.html:207 — kind: hint — description: Requested: {{ req.request_time | format_datetime }} | Period: {{ req.period }}
- `admin.admin_hall_pass.hint` — source: admin_hall_pass.html:236 — kind: hint — description: Issued: {{ req.decision_time | format_datetime }} | Period: {{ req.period }}
- `admin.admin_hall_pass.warning` — source: admin_hall_pass.html:53 — kind: warning — description: warning block
- `admin.admin_hall_pass.warning` — source: admin_hall_pass.html:82 — kind: warning — description: warning block
- `admin.admin_insurance.alert` — source: admin_insurance.html:15 — kind: alert — description: alert block
- `admin.admin_issues_queue.alert` — source: admin_issues_queue.html:95 — kind: alert — description: alert block
- `admin.admin_issues_queue.alert` — source: admin_issues_queue.html:42 — kind: alert — description: alert block
- `admin.admin_issues_queue.warning` — source: admin_issues_queue.html:58 — kind: warning — description: warning block
- `admin.admin_login.hint` — source: admin_login.html:143 — kind: hint — description: TEACHER PORTAL
- `admin.admin_login.warning` — source: admin_login.html:150 — kind: warning — description: warning block
- `admin.admin_login.warning` — source: admin_login.html:156 — kind: warning — description: warning block
- `admin.admin_nav.aria` — source: admin_nav.html:4 — kind: aria — description: Toggle navigation
- `admin.admin_passkey_settings.alert` — source: admin_passkey_settings.html:24 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:398 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:452 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:830 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:803 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:723 — kind: alert — description: alert block
- `admin.admin_payroll.alert` — source: admin_payroll.html:122 — kind: alert — description: alert block
- `admin.admin_payroll.hint` — source: admin_payroll.html:258 — kind: hint — description: Avg Payout
- `admin.admin_payroll.hint` — source: admin_payroll.html:249 — kind: hint — description: Estimated Payout
- `admin.admin_payroll.hint` — source: admin_payroll.html:488 — kind: hint — description: Date of the first payroll run
- `admin.admin_payroll.hint` — source: admin_payroll.html:673 — kind: hint — description: If time doesn't reach next increment
- `admin.admin_payroll.hint` — source: admin_payroll.html:245 — kind: hint — description: Next Payroll
- `admin.admin_payroll.hint` — source: admin_payroll.html:467 — kind: hint — description: Amount paid per hour of attendance
- `admin.admin_payroll.hint` — source: admin_payroll.html:593 — kind: hint — description: Must be ≥ 1.0 (e.g., 1.5 = 1.5x base rate for overtime)
- `admin.admin_payroll.hint` — source: admin_payroll.html:235 — kind: hint — description: Total Students
- `admin.admin_payroll.warning` — source: admin_payroll.html:117 — kind: warning — description: warning block
- `admin.admin_payroll.warning` — source: admin_payroll.html:43 — kind: warning — description: warning block
- `admin.admin_payroll.warning` — source: admin_payroll.html:512 — kind: warning — description: warning block
- `admin.admin_payroll.warning` — source: admin_payroll.html:387 — kind: warning — description: warning block
- `admin.admin_payroll.warning` — source: admin_payroll.html:681 — kind: warning — description: warning block
- `admin.admin_process_claim.alert` — source: admin_process_claim.html:191 — kind: alert — description: alert block
- `admin.admin_process_claim.hint` — source: admin_process_claim.html:246 — kind: hint — description: Per-claim and period caps will be applied automatically.
- `admin.admin_process_claim.hint` — source: admin_process_claim.html:240 — kind: hint — description: Leave blank to use requested amount
- `admin.admin_process_claim.hint` — source: admin_process_claim.html:254 — kind: hint — description: Required if rejecting claim
- `admin.admin_process_claim.warning` — source: admin_process_claim.html:188 — kind: warning — description: warning block
- `admin.admin_recover.hint` — source: admin_recover.html:167 — kind: hint — description: TEACHER PORTAL
- `admin.admin_recovery_saved.alert` — source: admin_recovery_saved.html:87 — kind: alert — description: alert block
- `admin.admin_recovery_saved.alert` — source: admin_recovery_saved.html:106 — kind: alert — description: alert block
- `admin.admin_recovery_saved.warning` — source: admin_recovery_saved.html:97 — kind: warning — description: warning block
- `admin.admin_recovery_status.alert` — source: admin_recovery_status.html:170 — kind: alert — description: alert block
- `admin.admin_recovery_status.alert` — source: admin_recovery_status.html:129 — kind: alert — description: alert block
- `admin.admin_recovery_status.hint` — source: admin_recovery_status.html:160 — kind: hint — description: Notified {{ code.notified_at.strftime('%B %d at %I:%M %p') }}
- `admin.admin_recovery_status.hint` — source: admin_recovery_status.html:157 — kind: hint — description: Verified {{ code.verified_at.strftime('%B %d at %I:%M %p') if code.verified_at else 'recently' }}
- `admin.admin_recovery_status.warning` — source: admin_recovery_status.html:178 — kind: warning — description: warning block
- `admin.admin_rent_settings.alert` — source: admin_rent_settings.html:1320 — kind: alert — description: alert block
- `admin.admin_rent_settings.alert` — source: admin_rent_settings.html:85 — kind: alert — description: alert block
- `admin.admin_rent_settings.alert` — source: admin_rent_settings.html:686 — kind: alert — description: alert block
- `admin.admin_rent_settings.alert` — source: admin_rent_settings.html:772 — kind: alert — description: alert block
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:594 — kind: hint — description: Days between recurring penalty charges
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:586 — kind: hint — description: How often late penalties are applied
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:572 — kind: hint — description: Fee charged for late payments
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:1317 — kind: hint — description: Allow students to buy this privilege separately (expires next rent due date)
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:499 — kind: hint — description: Time unit for the period
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:630 — kind: hint — description: How many days before due date students can see the bill
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:769 — kind: hint — description: Allow students to buy this privilege separately (expires next rent due date)
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:935 — kind: hint — description: Starts from the next upcoming due date
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:1334 — kind: hint — description: Rent payers get this many free uses per period.
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:565 — kind: hint — description: Days after due date before late penalty applies
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:541 — kind: hint — description: Day of month rent is due (1-31, only used for monthly frequency)
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:883 — kind: hint — description: Hold Ctrl/Cmd to select multiple students
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:458 — kind: hint — description: How much students pay per rent period
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:623 — kind: hint — description: Students can see incoming bills before due date
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:895 — kind: hint — description: (select students first)
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:486 — kind: hint — description: Number of time units
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:1342 — kind: hint — description: Number of hall passes added when rent is paid
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:788 — kind: hint — description: Rent payers get this many free uses per period.
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:474 — kind: hint — description: How often rent is due
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:796 — kind: hint — description: Number of hall passes added when rent is paid
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:509 — kind: hint — description: Suppress live CWI warnings for rent and hide rent notes from Economy Health for this class.
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:988 — kind: hint — description: ({{ waiver.periods_count }} period{{ 's' if waiver.periods_count != 1 }})
- `admin.admin_rent_settings.hint` — source: admin_rent_settings.html:906 — kind: hint — description: (no active period)
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:52 — kind: warning — description: warning block
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:947 — kind: warning — description: warning block
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:428 — kind: warning — description: warning block
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:810 — kind: warning — description: warning block
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:309 — kind: warning — description: warning block
- `admin.admin_rent_settings.warning` — source: admin_rent_settings.html:201 — kind: warning — description: warning block
- `admin.admin_reset_credentials.alert` — source: admin_reset_credentials.html:173 — kind: alert — description: alert block
- `admin.admin_reset_credentials.hint` — source: admin_reset_credentials.html:213 — kind: hint — description: This will be your new login username
- `admin.admin_reset_credentials.hint` — source: admin_reset_credentials.html:189 — kind: hint — description: Enter each 6-digit code from your students. Click "Add Code" for each additional code.
- `admin.admin_reset_credentials.hint` — source: admin_reset_credentials.html:156 — kind: hint — description: TEACHER PORTAL
- `admin.admin_reset_credentials.warning` — source: admin_reset_credentials.html:177 — kind: warning — description: warning block
- `admin.admin_reset_credentials.warning` — source: admin_reset_credentials.html:164 — kind: warning — description: warning block
- `admin.admin_resume_credentials.alert` — source: admin_resume_credentials.html:138 — kind: alert — description: alert block
- `admin.admin_resume_credentials.hint` — source: admin_resume_credentials.html:156 — kind: hint — description: The 6-digit PIN from when you saved your progress
- `admin.admin_resume_credentials.hint` — source: admin_resume_credentials.html:123 — kind: hint — description: TEACHER PORTAL
- `admin.admin_resume_credentials.warning` — source: admin_resume_credentials.html:131 — kind: warning — description: warning block
- `admin.admin_select_class_context.hint` — source: admin_select_class_context.html:65 — kind: hint — description: TEACHER PORTAL
- `admin.admin_select_class_context.warning` — source: admin_select_class_context.html:74 — kind: warning — description: warning block
- `admin.admin_signup.hint` — source: admin_signup.html:111 — kind: hint — description: TEACHER SETUP — STEP 2 OF 3
- `admin.admin_signup_class.hint` — source: admin_signup_class.html:94 — kind: hint — description: TEACHER SETUP — STEP 1 OF 3
- `admin.admin_signup_totp.hint` — source: admin_signup_totp.html:234 — kind: hint — description: TEACHER SETUP — STEP 3 OF 3
- `admin.admin_signup_totp.warning` — source: admin_signup_totp.html:242 — kind: warning — description: warning block
- `admin.admin_store.alert` — source: admin_store.html:626 — kind: alert — description: alert block
- `admin.admin_store.alert` — source: admin_store.html:505 — kind: alert — description: alert block
- `admin.admin_store.alert` — source: admin_store.html:457 — kind: alert — description: alert block
- `admin.admin_store.alert` — source: admin_store.html:68 — kind: alert — description: alert block
- `admin.admin_store.alert` — source: admin_store.html:90 — kind: alert — description: alert block
- `admin.admin_store.aria` — source: admin_store.html:829 — kind: aria — description: Audit pagination
- `admin.admin_store.aria` — source: admin_store.html:253 — kind: aria — description: Refund and remove
- `admin.admin_store.hint` — source: admin_store.html:664 — kind: hint — description: Item will be automatically hidden on this date
- `admin.admin_store.hint` — source: admin_store.html:245 — kind: hint — description: {{ entitlement.purchased_at|fmt_timestamp }}
- `admin.admin_store.hint` — source: admin_store.html:585 — kind: hint — description: How many items in this bundle?
- `admin.admin_store.hint` — source: admin_store.html:521 — kind: hint — description: Choose how students can use this item
- `admin.admin_store.hint` — source: admin_store.html:502 — kind: hint — description: Optional pricing category for organization
- `admin.admin_store.hint` — source: admin_store.html:536 — kind: hint — description: For expensive items students save for over many weeks (won't trigger CWI warnings).
- `admin.admin_store.hint` — source: admin_store.html:632 — kind: hint — description: Choose how the goal is calculated
- `admin.admin_store.hint` — source: admin_store.html:669 — kind: hint — description: Days before item expires (for delayed-use items)
- `admin.admin_store.hint` — source: admin_store.html:578 — kind: hint — description: Bundled items give students multiple uses that can be redeemed separately
- `admin.admin_store.hint` — source: admin_store.html:613 — kind: hint — description: Discount percentage (e.g., 10 for 10% off)
- `admin.admin_store.hint` — source: admin_store.html:601 — kind: hint — description: Offer a discount when students buy multiple quantities
- `admin.admin_store.hint` — source: admin_store.html:191 — kind: hint — description: Active Items
- `admin.admin_store.hint` — source: admin_store.html:649 — kind: hint — description: If set, the goal expires at end of this date. If the goal is not reached, the item deactivates and must be reactivated to start fresh.
- `admin.admin_store.hint` — source: admin_store.html:302 — kind: hint — description: {{ entitlement.purchased_at|fmt_timestamp }}
- `admin.admin_store.hint` — source: admin_store.html:563 — kind: hint — description: Leave blank for no purchase limit
- `admin.admin_store.hint` — source: admin_store.html:543 — kind: hint — description: Hold Ctrl/Cmd to select multiple periods. Leave empty to show to all periods.
- `admin.admin_store.hint` — source: admin_store.html:558 — kind: hint — description: Leave blank for unlimited inventory
- `admin.admin_store.hint` — source: admin_store.html:187 — kind: hint — description: Total Items
- `admin.admin_store.hint` — source: admin_store.html:195 — kind: hint — description: Total Purchases
- `admin.admin_store.hint` — source: admin_store.html:638 — kind: hint — description: Number of students who must purchase to unlock this item
- `admin.admin_store.hint` — source: admin_store.html:608 — kind: hint — description: Minimum quantity to qualify for discount
- `admin.admin_store.hint` — source: admin_store.html:531 — kind: hint — description: Suppress live CWI warnings for this item and hide it from Economy Health.
- `admin.admin_store.warning` — source: admin_store.html:642 — kind: warning — description: warning block
- `admin.admin_store.warning` — source: admin_store.html:882 — kind: warning — description: warning block
- `admin.admin_students.alert` — source: admin_students.html:174 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:355 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:919 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:572 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:204 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:835 — kind: alert — description: alert block
- `admin.admin_students.alert` — source: admin_students.html:270 — kind: alert — description: alert block
- `admin.admin_students.aria` — source: admin_students.html:496 — kind: aria — description: Select all students
- `admin.admin_students.aria` — source: admin_students.html:963 — kind: aria — description: Type DELETE to confirm
- `admin.admin_students.aria` — source: admin_students.html:514 — kind: aria — description: Select {{ student_display_name }}
- `admin.admin_students.aria` — source: admin_students.html:416 — kind: aria — description: Delete pending student {{ seat.full_name }}.
- `admin.admin_students.aria` — source: admin_students.html:988 — kind: aria — description: Delete countdown
- `admin.admin_students.hint` — source: admin_students.html:409 — kind: hint — description: Teacher shadow account
- `admin.admin_students.hint` — source: admin_students.html:399 — kind: hint — description: Claim credential: managed by system
- `admin.admin_students.warning` — source: admin_students.html:845 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:850 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:1055 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:168 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:913 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:950 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:249 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:123 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:226 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:1022 — kind: warning — description: warning block
- `admin.admin_students.warning` — source: admin_students.html:598 — kind: warning — description: warning block
- `admin.admin_view_issue.alert` — source: admin_view_issue.html:332 — kind: alert — description: alert block
- `admin.admin_view_issue.alert` — source: admin_view_issue.html:445 — kind: alert — description: alert block
- `admin.admin_view_issue.hint` — source: admin_view_issue.html:167 — kind: hint — description: Savings
- `admin.admin_view_issue.hint` — source: admin_view_issue.html:173 — kind: hint — description: Total
- `admin.admin_view_issue.hint` — source: admin_view_issue.html:161 — kind: hint — description: Checking
- `admin.admin_view_issue.warning` — source: admin_view_issue.html:134 — kind: warning — description: warning block
- `admin.layout_admin.aria` — source: layout_admin.html:77 — kind: aria — description: Toggle navigation menu
- `admin.layout_admin.aria` — source: layout_admin.html:347 — kind: aria — description: Attendance
- `admin.layout_admin.aria` — source: layout_admin.html:86 — kind: aria — description: Navigation menu
- `admin.layout_admin.warning` — source: layout_admin.html:217 — kind: warning — description: warning block
- `error.error_400.alert` — source: error_400.html:146 — kind: alert — description: alert block
- `error.error_400.warning` — source: error_400.html:135 — kind: warning — description: warning block
- `error.error_401.alert` — source: error_401.html:125 — kind: alert — description: alert block
- `error.error_401.warning` — source: error_401.html:137 — kind: warning — description: warning block
- `error.error_403.alert` — source: error_403.html:116 — kind: alert — description: alert block
- `error.error_403.warning` — source: error_403.html:112 — kind: warning — description: warning block
- `error.error_404.alert` — source: error_404.html:133 — kind: alert — description: alert block
- `error.error_500.alert` — source: error_500.html:204 — kind: alert — description: alert block
- `error.error_500.warning` — source: error_500.html:196 — kind: warning — description: warning block
- `error.error_503.warning` — source: error_503.html:142 — kind: warning — description: warning block
- `public.hall_pass_setup.tooltip` — source: hall_pass_setup.html:439 — kind: tooltip — description: You must enable hall pass first
- `public.hall_pass_verify.warning` — source: hall_pass_verify.html:35 — kind: warning — description: warning block
- `public.hall_pass_verify.warning` — source: hall_pass_verify.html:41 — kind: warning — description: warning block
- `public.help.alert` — source: help.html:50 — kind: alert — description: alert block
- `public.identity_update.alert` — source: identity_update.html:8 — kind: alert — description: alert block
- `public.index.aria` — source: index.html:26 — kind: aria — description: Documentation Audience Toggle
- `public.reset_form.warning` — source: reset_form.html:11 — kind: warning — description: warning block
- `public.search.alert` — source: search.html:74 — kind: alert — description: alert block
- `public.view.aria` — source: view.html:395 — kind: aria — description: Toggle documentation sidebar
- `public.view.aria` — source: view.html:428 — kind: aria — description: Toggle table of contents
- `public.view.aria` — source: view.html:403 — kind: aria — description: breadcrumb
- `student.layout_student.aria` — source: layout_student.html:72 — kind: aria — description: Toggle navigation menu
- `student.layout_student.aria` — source: layout_student.html:81 — kind: aria — description: Student navigation
- `student.layout_student.warning` — source: layout_student.html:164 — kind: warning — description: warning block
- `student.student_account_claim.alert` — source: student_account_claim.html:150 — kind: alert — description: alert block
- `student.student_account_claim.hint` — source: student_account_claim.html:139 — kind: hint — description: STUDENT PORTAL
- `student.student_add_class.alert` — source: student_add_class.html:18 — kind: alert — description: alert block
- `student.student_create_username.alert` — source: student_create_username.html:184 — kind: alert — description: alert block
- `student.student_create_username.hint` — source: student_create_username.html:168 — kind: hint — description: STUDENT SETUP
- `student.student_create_username.warning` — source: student_create_username.html:176 — kind: warning — description: warning block
- `student.student_create_username.warning` — source: student_create_username.html:194 — kind: warning — description: warning block
- `student.student_dashboard.alert` — source: student_dashboard.html:70 — kind: alert — description: alert block
- `student.student_dashboard.alert` — source: student_dashboard.html:40 — kind: alert — description: alert block
- `student.student_dashboard.alert` — source: student_dashboard.html:185 — kind: alert — description: alert block
- `student.student_dashboard.hint` — source: student_dashboard.html:202 — kind: hint — description: Time Today
- `student.student_dashboard.warning` — source: student_dashboard.html:298 — kind: warning — description: warning block
- `student.student_detail.alert` — source: student_detail.html:549 — kind: alert — description: alert block
- `student.student_detail.alert` — source: student_detail.html:492 — kind: alert — description: alert block
- `student.student_detail.alert` — source: student_detail.html:709 — kind: alert — description: alert block
- `student.student_detail.alert` — source: student_detail.html:423 — kind: alert — description: alert block
- `student.student_detail.alert` — source: student_detail.html:796 — kind: alert — description: alert block
- `student.student_detail.alert` — source: student_detail.html:668 — kind: alert — description: alert block
- `student.student_detail.hint` — source: student_detail.html:97 — kind: hint — description: (Per Rent Period Items)
- `student.student_detail.warning` — source: student_detail.html:235 — kind: warning — description: warning block
- `student.student_detail.warning` — source: student_detail.html:786 — kind: warning — description: warning block
- `student.student_detail.warning` — source: student_detail.html:275 — kind: warning — description: warning block
- `student.student_file_claim.alert` — source: student_file_claim.html:180 — kind: alert — description: alert block
- `student.student_file_claim.alert` — source: student_file_claim.html:85 — kind: alert — description: alert block
- `student.student_file_claim.hint` — source: student_file_claim.html:66 — kind: hint — description: Claims must be filed within {{ contract_claim_time_limit_days }} days of the transaction.
- `student.student_file_claim.hint` — source: student_file_claim.html:81 — kind: hint — description: Be as detailed as possible to help with processing your claim.
- `student.student_file_claim.hint` — source: student_file_claim.html:126 — kind: hint — description: Optional: Add any additional comments or context.
- `student.student_file_claim.warning` — source: student_file_claim.html:215 — kind: warning — description: warning block
- `student.student_file_claim.warning` — source: student_file_claim.html:34 — kind: warning — description: warning block
- `student.student_file_claim.warning` — source: student_file_claim.html:190 — kind: warning — description: warning block
- `student.student_file_claim.warning` — source: student_file_claim.html:184 — kind: warning — description: warning block
- `student.student_file_claim.warning` — source: student_file_claim.html:57 — kind: warning — description: warning block
- `student.student_insurance_marketplace.alert` — source: student_insurance_marketplace.html:366 — kind: alert — description: alert block
- `student.student_insurance_marketplace.alert` — source: student_insurance_marketplace.html:447 — kind: alert — description: alert block
- `student.student_insurance_marketplace.hint` — source: student_insurance_marketplace.html:91 — kind: hint — description: {{ enrollment.policy.charge_frequency }}
- `student.student_insurance_marketplace.hint` — source: student_insurance_marketplace.html:120 — kind: hint — description: Max Claims
- `student.student_insurance_marketplace.hint` — source: student_insurance_marketplace.html:292 — kind: hint — description: / {{ policy.charge_frequency }}
- `student.student_insurance_marketplace.hint` — source: student_insurance_marketplace.html:111 — kind: hint — description: Wait Days
- `student.student_insurance_marketplace.warning` — source: student_insurance_marketplace.html:376 — kind: warning — description: warning block
- `student.student_insurance_marketplace.warning` — source: student_insurance_marketplace.html:371 — kind: warning — description: warning block
- `student.student_login.alert` — source: student_login.html:170 — kind: alert — description: alert block
- `student.student_login.hint` — source: student_login.html:161 — kind: hint — description: STUDENT PORTAL
- `student.student_login.warning` — source: student_login.html:175 — kind: warning — description: warning block
- `student.student_payroll.alert` — source: student_payroll.html:107 — kind: alert — description: alert block
- `student.student_payroll.alert` — source: student_payroll.html:113 — kind: alert — description: alert block
- `student.student_payroll.alert` — source: student_payroll.html:216 — kind: alert — description: alert block
- `student.student_payroll.alert` — source: student_payroll.html:182 — kind: alert — description: alert block
- `student.student_payroll.hint` — source: student_payroll.html:203 — kind: hint — description: Based on current unpaid time
- `student.student_payroll.warning` — source: student_payroll.html:238 — kind: warning — description: warning block
- `student.student_pin_setup.hint` — source: student_pin_setup.html:233 — kind: hint — description: STUDENT SETUP
- `student.student_pin_setup.warning` — source: student_pin_setup.html:247 — kind: warning — description: warning block
- `student.student_rent.alert` — source: student_rent.html:47 — kind: alert — description: alert block
- `student.student_rent.alert` — source: student_rent.html:197 — kind: alert — description: alert block
- `student.student_rent.alert` — source: student_rent.html:285 — kind: alert — description: alert block
- `student.student_rent.alert` — source: student_rent.html:161 — kind: alert — description: alert block
- `student.student_rent.alert` — source: student_rent.html:171 — kind: alert — description: alert block
- `student.student_rent.alert` — source: student_rent.html:155 — kind: alert — description: alert block
- `student.student_rent.hint` — source: student_rent.html:272 — kind: hint — description: Outstanding
- `student.student_rent.hint` — source: student_rent.html:266 — kind: hint — description: Paid/Waived
- `student.student_rent.hint` — source: student_rent.html:278 — kind: hint — description: Past Due
- `student.student_rent.warning` — source: student_rent.html:188 — kind: warning — description: warning block
- `student.student_rent.warning` — source: student_rent.html:182 — kind: warning — description: warning block
- `student.student_rent.warning` — source: student_rent.html:176 — kind: warning — description: warning block
- `student.student_shop.alert` — source: student_shop.html:97 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:165 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:251 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:93 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:340 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:310 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:35 — kind: alert — description: alert block
- `student.student_shop.alert` — source: student_shop.html:269 — kind: alert — description: alert block
- `student.student_shop.hint` — source: student_shop.html:112 — kind: hint — description: {{ item.collective_progress.remaining_count }} more needed!
- `student.student_shop.hint` — source: student_shop.html:352 — kind: hint — description: This information will be sent to your teacher for review.
- `student.student_shop.warning` — source: student_shop.html:117 — kind: warning — description: warning block
- `student.student_submit_issue.alert` — source: student_submit_issue.html:42 — kind: alert — description: alert block
- `student.student_submit_issue.hint` — source: student_submit_issue.html:88 — kind: hint — description: Select the type of issue you're experiencing.
- `student.student_submit_issue.warning` — source: student_submit_issue.html:129 — kind: warning — description: warning block
- `student.student_transfer.alert` — source: student_transfer.html:230 — kind: alert — description: alert block
- `student.student_transfer.alert` — source: student_transfer.html:404 — kind: alert — description: alert block
- `student.student_transfer.alert` — source: student_transfer.html:323 — kind: alert — description: alert block
- `student.student_transfer.alert` — source: student_transfer.html:383 — kind: alert — description: alert block
- `student.student_transfer.tooltip` — source: student_transfer.html:310 — kind: tooltip — description: Report an issue with this transaction
- `student.student_transfer.tooltip` — source: student_transfer.html:370 — kind: tooltip — description: Report an issue with this transaction
- `student.student_verify_recovery.alert` — source: student_verify_recovery.html:18 — kind: alert — description: alert block
- `student.student_verify_recovery.alert` — source: student_verify_recovery.html:52 — kind: alert — description: alert block
- `student.student_verify_recovery.hint` — source: student_verify_recovery.html:81 — kind: hint — description: This is the passphrase you use to log in to your account.
- `student.student_verify_recovery.warning` — source: student_verify_recovery.html:32 — kind: warning — description: warning block
- `sysadmin.layout_system_admin.aria` — source: layout_system_admin.html:85 — kind: aria — description: System admin navigation
- `sysadmin.layout_system_admin.aria` — source: layout_system_admin.html:75 — kind: aria — description: Toggle navigation menu
- `sysadmin.layout_system_admin.aria` — source: layout_system_admin.html:176 — kind: aria — description: Quick navigation
- `sysadmin.sysadmin_user_report_detail.hint` — source: sysadmin_user_report_detail.html:136 — kind: hint — description: {{ report.user_agent or 'N/A' }}
- `sysadmin.sysadmin_user_reports.alert` — source: sysadmin_user_reports.html:113 — kind: alert — description: alert block
- `sysadmin.sysadmin_view_escalated_issue.alert` — source: sysadmin_view_escalated_issue.html:131 — kind: alert — description: alert block
- `sysadmin.sysadmin_view_escalated_issue.hint` — source: sysadmin_view_escalated_issue.html:298 — kind: hint — description: This will be visible to the teacher. Developers cannot close the ticket.
- `sysadmin.sysadmin_view_escalated_issue.hint` — source: sysadmin_view_escalated_issue.html:315 — kind: hint — description: Creates a bug reward transaction for the student.
- `sysadmin.sysadmin_view_escalated_issue.warning` — source: sysadmin_view_escalated_issue.html:70 — kind: warning — description: warning block
- `sysadmin.sysadmin_view_escalated_issue.warning` — source: sysadmin_view_escalated_issue.html:182 — kind: warning — description: warning block
- `sysadmin.system_admin_error_logs.aria` — source: system_admin_error_logs.html:176 — kind: aria — description: Page navigation
- `sysadmin.system_admin_login.hint` — source: system_admin_login.html:153 — kind: hint — description: SYSTEM ADMIN PORTAL
- `sysadmin.system_admin_login.warning` — source: system_admin_login.html:170 — kind: warning — description: warning block
- `sysadmin.system_admin_logs.alert` — source: system_admin_logs.html:16 — kind: alert — description: alert block
- `sysadmin.system_admin_network_activity.aria` — source: system_admin_network_activity.html:245 — kind: aria — description: Page navigation
- `sysadmin.system_admin_passkey_settings.alert` — source: system_admin_passkey_settings.html:23 — kind: alert — description: alert block

## GAP

- `admin.admin_banking.overdraft_config` — source: admin_banking.html — kind: informational — severity: decision-support — reason: progressive fee configuration with complex cap logic
- `admin.admin_edit_item.bypass_cwi_help` — source: admin_edit_item.html — kind: informational — severity: decision-support — reason: irreversible pricing override presented without user context
- `admin.admin_process_claim.decision_context` — source: admin_process_claim.html — kind: informational — severity: decision-support — reason: approve/deny decision lacks workflow guidance or policy context
- `admin.admin_rent_settings.eviction_guidance` — source: admin_rent_settings.html — kind: informational — severity: decision-support — reason: irreversible consequence triggering student account restrictions
- `admin.admin_edit_item.collective_goal_help` — source: admin_edit_item.html — kind: informational — severity: informational — reason: complex multi-student configuration with expiry and dynamic targeting
- `admin.admin_insurance.entitlement_calc` — source: admin_insurance.html — kind: informational — severity: informational — reason: insurance policy payout logic not explained

## ANOMALY

(none detected)

## Scan Summary

| Template | Classification | EXTRACTED | GAP | ANOMALY |
|----------|-----------------|-----------|-----|---------|
| account_lookup.html | sparse | 0 | 0 | 0 |
| admin_account_delete.html | moderate | 2 | 0 | 0 |
| admin_analytics_dashboard.html | moderate | 1 | 0 | 0 |
| admin_analytics_events.html | moderate | 2 | 0 | 0 |
| admin_analytics_student_detail.html | well-covered | 3 | 0 | 0 |
| admin_announcement_form.html | well-covered | 5 | 0 | 0 |
| admin_announcements.html | moderate | 2 | 0 | 0 |
| admin_attendance_log.html | well-covered | 3 | 0 | 0 |
| admin_banking.html | well-covered | 22 | 1 | 0 |
| admin_create_class.html | sparse | 0 | 0 | 0 |
| admin_create_class_form.html | sparse | 0 | 0 | 0 |
| admin_customizations.html | well-covered | 5 | 0 | 0 |
| admin_dashboard.html | well-covered | 4 | 0 | 0 |
| admin_economic_engine.html | well-covered | 9 | 0 | 0 |
| admin_edit_insurance_policy.html | well-covered | 4 | 0 | 0 |
| admin_edit_item.html | bare | 20 | 2 | 0 |
| admin_feature_disabled.html | sparse | 0 | 0 | 0 |
| admin_feature_settings.html | moderate | 2 | 0 | 0 |
| admin_hall_pass.html | well-covered | 8 | 0 | 0 |
| admin_insurance.html | moderate | 1 | 1 | 0 |
| admin_issues_queue.html | well-covered | 3 | 0 | 0 |
| admin_login.html | well-covered | 3 | 0 | 0 |
| admin_nav.html | moderate | 1 | 0 | 0 |
| admin_passkey_settings.html | moderate | 1 | 0 | 0 |
| admin_payroll.html | well-covered | 19 | 0 | 0 |
| admin_payroll_history.html | sparse | 0 | 0 | 0 |
| admin_process_claim.html | well-covered | 5 | 1 | 0 |
| admin_recover.html | moderate | 1 | 0 | 0 |
| admin_recovery_saved.html | well-covered | 3 | 0 | 0 |
| admin_recovery_status.html | well-covered | 5 | 0 | 0 |
| admin_rent_settings.html | well-covered | 33 | 1 | 0 |
| admin_reset_credentials.html | well-covered | 6 | 0 | 0 |
| admin_resume_credentials.html | well-covered | 4 | 0 | 0 |
| admin_select_class_context.html | moderate | 2 | 0 | 0 |
| admin_setup_recovery.html | sparse | 0 | 0 | 0 |
| admin_signup.html | moderate | 1 | 0 | 0 |
| admin_signup_class.html | moderate | 1 | 0 | 0 |
| admin_signup_totp.html | moderate | 2 | 0 | 0 |
| admin_store.html | well-covered | 31 | 0 | 0 |
| admin_students.html | well-covered | 25 | 0 | 0 |
| admin_support_tickets.html | sparse | 0 | 0 | 0 |
| admin_view_issue.html | well-covered | 6 | 0 | 0 |
| admin_view_student_policy.html | sparse | 0 | 0 | 0 |
| error_400.html | moderate | 2 | 0 | 0 |
| error_401.html | moderate | 2 | 0 | 0 |
| error_403.html | moderate | 2 | 0 | 0 |
| error_404.html | moderate | 1 | 0 | 0 |
| error_500.html | moderate | 2 | 0 | 0 |
| error_503.html | moderate | 1 | 0 | 0 |
| getting_started_widget.html | sparse | 0 | 0 | 0 |
| hall_pass_setup.html | moderate | 1 | 0 | 0 |
| hall_pass_verify.html | moderate | 2 | 0 | 0 |
| help.html | moderate | 1 | 0 | 0 |
| identity_update.html | moderate | 1 | 0 | 0 |
| index.html | moderate | 1 | 0 | 0 |
| landing.html | sparse | 0 | 0 | 0 |
| layout.html | sparse | 0 | 0 | 0 |
| layout_admin.html | well-covered | 4 | 0 | 0 |
| layout_student.html | well-covered | 3 | 0 | 0 |
| layout_system_admin.html | well-covered | 3 | 0 | 0 |
| reset_form.html | moderate | 1 | 0 | 0 |
| search.html | moderate | 1 | 0 | 0 |
| student_account_claim.html | moderate | 2 | 0 | 0 |
| student_add_class.html | moderate | 1 | 0 | 0 |
| student_create_username.html | well-covered | 4 | 0 | 0 |
| student_dashboard.html | well-covered | 5 | 0 | 0 |
| student_detail.html | well-covered | 10 | 0 | 0 |
| student_file_claim.html | well-covered | 10 | 0 | 0 |
| student_help_support_new.html | sparse | 0 | 0 | 0 |
| student_insurance_marketplace.html | well-covered | 8 | 0 | 0 |
| student_login.html | well-covered | 3 | 0 | 0 |
| student_payroll.html | well-covered | 6 | 0 | 0 |
| student_pin_setup.html | moderate | 2 | 0 | 0 |
| student_rent.html | well-covered | 12 | 0 | 0 |
| student_select_class_context.html | sparse | 0 | 0 | 0 |
| student_setup_complete.html | sparse | 0 | 0 | 0 |
| student_shop.html | well-covered | 11 | 0 | 0 |
| student_submit_issue.html | well-covered | 3 | 0 | 0 |
| student_transfer.html | well-covered | 6 | 0 | 0 |
| student_verify_recovery.html | well-covered | 4 | 0 | 0 |
| student_view_policy.html | sparse | 0 | 0 | 0 |
| sysadmin_combined_logs.html | sparse | 0 | 0 | 0 |
| sysadmin_escalated_issues.html | sparse | 0 | 0 | 0 |
| sysadmin_support_tickets.html | sparse | 0 | 0 | 0 |
| sysadmin_user_report_detail.html | moderate | 1 | 0 | 0 |
| sysadmin_user_reports.html | moderate | 1 | 0 | 0 |
| sysadmin_view_escalated_issue.html | well-covered | 5 | 0 | 0 |
| system_admin_dashboard.html | sparse | 0 | 0 | 0 |
| system_admin_error_logs.html | moderate | 1 | 0 | 0 |
| system_admin_login.html | moderate | 2 | 0 | 0 |
| system_admin_logs.html | moderate | 1 | 0 | 0 |
| system_admin_logs_testing.html | sparse | 0 | 0 | 0 |
| system_admin_network_activity.html | moderate | 1 | 0 | 0 |
| system_admin_passkey_settings.html | moderate | 1 | 0 | 0 |
| timeline.html | sparse | 0 | 0 | 0 |
| view.html | well-covered | 3 | 0 | 0 |

**Coverage Summary:**
- Well-covered (>=3 EXTRACTED, 0 critical GAP): 38
- Moderate (1-2 EXTRACTED): 36
- Sparse (<1 EXTRACTED): 21
- Bare (critical GAP with no support): 1
- N/A (infrastructure/layout): 3

**Totals:**
- EXTRACTED: 376
- GAP: 6
- ANOMALY: 0