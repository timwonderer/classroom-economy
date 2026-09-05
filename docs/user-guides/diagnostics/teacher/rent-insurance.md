---
title: Rent and Insurance Troubleshooting
description: Why rent bills, waivers, late fees, or insurance policies behave unexpectedly.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/store
  - user-guides/diagnostics/teacher/transactions-banking
---

# Rent and Insurance Troubleshooting

Diagnostic guide for resolving errors related to rent billing, late penalties, and insurance claims.

## Rent is not showing for students

### Symptoms
- Students cannot see their impending rent charges.
- The rent payment button is missing or disabled.

### Causes & Solutions
**Cause 1: Rent feature disabled**
- **Check:** Verify Rent is enabled in Feature Settings for the class period.
- **Fix:** Enable the feature.

**Cause 2: Rent cycle has not started**
- **Check:** Check the rent due date and preview window in Rent Settings.
- **Fix:** Rent does not appear until the preview window begins. Adjust the due date or preview window length if necessary.

**Cause 3: Student in wrong class context**
- **Check:** Verify the student's dashboard class switcher.
- **Fix:** Rent is calculated per join code. Ask the student to switch to the correct class.

## Rent payments look wrong

### Symptoms
- Students cannot make partial payments.
- Late penalties are not applied.
- Students can make store purchases while late on rent.

### Causes & Solutions
**Cause 1: Incremental payments disabled**
- **Check:** Look at your Rent Settings configuration.
- **Fix:** Incremental payments only work when explicitly enabled in settings; otherwise, rent must be paid in full.

**Cause 2: Grace period active**
- **Check:** Check the late penalty grace period setting.
- **Fix:** Late penalties only apply *after* the grace period ends, not immediately on the due day.

**Cause 3: Purchase prevention disabled**
- **Check:** Check the "Prevent purchases when late" setting.
- **Fix:** Enable "prevent purchases when late" to block store access until rent is paid. Note: If rent itemization is enabled, students can still buy rent-covered items.

## Insurance enrollments or claims fail

### Symptoms
- Students cannot buy a policy or submit a claim.

### Causes & Solutions
**Cause 1: Waiting periods or claim limits**
- **Check:** Review the policy tier requirements.
- **Fix:** Claims are blocked before coverage start dates (waiting periods), or when max claims per period are reached.

**Cause 2: Policy exclusivity**
- **Check:** See if the student is already enrolled in a different tier.
- **Fix:** One policy per tier is enforced when tiers are configured.

## When to Contact Support
Report this issue if:
- The system charges widespread duplicate late fees to the same student.
- Claims process but the reimbursement logic fails to trigger.
