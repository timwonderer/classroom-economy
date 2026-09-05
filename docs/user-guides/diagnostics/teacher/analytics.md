---
title: Analytics Dashboard Troubleshooting
description: Why analytics figures look empty, stale, or inconsistent with the ledger.
category: diagnostics
subcategory: teacher
roles: [teacher]
---

# Analytics Dashboard Troubleshooting

**Quick diagnostic guide for common analytics dashboard issues.**

**Version:** 1.7.0+
**Route:** `/admin/analytics`

---

## Dashboard Won't Load

### Symptoms
- Analytics page shows error or blank screen
- Loading spinner never completes
- Page times out

### Quick Fixes

**1. Check if analytics data exists:**

- Navigate to different time window (try monthly if weekly doesn't work)
- Ensure you have transactions in the selected period
- Wait 24 hours after first setup for initial data computation

**2. Verify you're viewing correct class:**

- Check class selector in header
- Switch to a class with active students
- Ensure class has join_code properly configured

**3. Clear browser cache:**
```
Chrome: Ctrl+Shift+Del (Cmd+Shift+Del on Mac)
Select "Cached images and files" → Clear data
```

**4. Try different browser:**

- Test in incognito/private mode
- Switch to different browser (Chrome, Firefox, Safari)

### Still Not Working?
Report via Help & Support with:

- Browser and version
- Screenshot of error (if any)
- Which class period you're viewing

---

## Metrics Show "No Data"

### Symptoms
- Dashboard loads but all metrics show zero or "No data available"
- Charts are empty
- No alerts showing

### Causes & Solutions

**Cause 1: No Student Activity**

- **Check:** Do students have any transactions?
- **Fix:** Run a test transaction (manual adjustment)
- **Fix:** Ensure students are tapping in/out

**Cause 2: Wrong Time Window**

- **Check:** Are you viewing weekly data for a month-old period?
- **Fix:** Switch to monthly view
- **Fix:** Select "current week" or "current month"

**Cause 3: Data Not Yet Computed**

- **Check:** Is this a brand new class?
- **Fix:** Wait 24 hours for initial computation
- **Fix:** Make some transactions to trigger calculations

**Cause 4: All Students Inactive**

- **Check:** Number of enrolled students vs. active students
- **Fix:** Review student roster - mark inactive students appropriately
- **Fix:** Ensure students know how to participate

---

## Metrics Seem Inaccurate

### Participation Rate Issues

**Too Low (below expected):**

- Check if students understand how to tap in/out
- Verify tap devices/buttons working
- Review recent absences (holiday, testing week?)
- Check if inactive students included in calculation

**Too High (100% seems wrong):**

- Verify student count is correct
- Check for test/dummy accounts
- Review active vs. inactive student flags

### Money Velocity Issues

**Too Low (stagnant economy):**

- Are store items appealing?
- Is rent too high (students hoarding)?
- Check if students know how to make purchases
- Review store item availability

**Too High (chaotic activity):**

- Check for unusual transaction patterns
- Look for test transactions or errors
- Review if prices need adjustment

### CWI Deviation Issues

**Metrics say balanced but doesn't feel right:**

- Recalculate your CWI - has economy changed?
- Check if you're comparing to old CWI
- Verify CWI setting in Economic Engine page

**All students deviating:**

- **Strong indicator:** CWI needs recalibration
- Compare current average balance to CWI
- Adjust CWI to match new reality
- Then adjust economy settings gradually

### Budget Survival Rate Issues

**Rate dropping suddenly:**

- Check recent rent/insurance changes
- Review if wage changes needed
- Look for unexpected fees accumulating
- Check timeline for correlation with events

---

## Alerts Not Showing

### Symptoms
- Dashboard shows metrics but no alert cards
- Expected to see warnings but none appear

### Causes & Solutions

**Cause 1: Metrics in Healthy Range**

- **Good news:** Economy is balanced!
- **Action:** Monitor for changes
- **Note:** Alerts only show when action needed

**Cause 2: Alert Dismissed**

- **Check:** Were alerts previously dismissed?
- **Fix:** Alerts may reappear if condition worsens
- **Note:** Dismissed alerts can be reviewed in history

**Cause 3: Not Meeting Alert Thresholds**

- **Details:** Alerts trigger at specific levels:
  - Critical: Survival <50%, Participation <40%
  - Warning: Deviation >20%, Velocity dropping 50%+
- **Action:** Review metrics directly even without alerts

---

## Events Not Showing on Timeline

### Symptoms
- Made economy changes but timeline empty
- Recent adjustments not reflected in events

### Causes & Solutions

**Cause 1: Events Not Auto-Tracked Yet**

- **Currently:** Some changes don't auto-generate events
- **Workaround:** Track major changes manually in notes
- **Future:** More auto-tracking coming in v1.8

**Cause 2: Wrong Time Window**

- **Check:** Are you viewing weekly but made changes last month?
- **Fix:** Switch to monthly view
- **Fix:** Adjust date range if available

**Cause 3: Change Type Not Tracked**

- **Tracked:** Rent changes, wage changes, bonus payroll
- **Not Tracked:** Individual store item changes, minor tweaks
- **Note:** Major economy events tracked, minor changes aren't

---

## Trends Show "Stable" When Things Changed

### Symptoms
- Made significant economy changes but trend shows stable
- Expected to see "improving" or "worsening"

### Explanation

**Trend Detection Requirements:**

- Needs 2-4 weeks of data to identify trends
- Compares current period to previous period
- "Stable" means <10% change

**Solutions:**

- **Wait:** Give it 2+ weeks after major changes
- **Check:** Look at actual metric values, not just trend
- **Remember:** Stable can be good if metrics healthy

---

## Numbers Don't Match Expectations

### Common Misunderstandings

**"Participation shows 80% but only 15/25 students active"**

- **Explanation:** Percentage of students with ANY activity
- **Check:** Are 20 students active? 20/25 = 80%
- **Note:** Doesn't measure frequency, just participation

**"Money velocity shows 3.2 but I see way more transactions"**

- **Explanation:** Average transactions PER STUDENT
- **Math:** If 100 total transactions ÷ 30 students = 3.3
- **Note:** Not total transactions, per-student average

**"CWI deviation shows 25% but I think more students off-track"**

- **Explanation:** % of students MORE than 50% away from CWI
- **Example:** If CWI is $100, students at $40-$160 not counted
- **Note:** Only counts significant deviations (>50%)

**"Survival rate 90% but I know students struggling"**

- **Explanation:** Can afford rent+insurance RIGHT NOW
- **Example:** Student has $60, rent+insurance=$50 → counts as surviving
- **Note:** Doesn't mean thriving, just surviving current cycle

---

## Performance Issues

### Symptoms
- Dashboard slow to load
- Takes more than 5-10 seconds
- Animations laggy

### Quick Fixes

**1. Switch Time Window:**

- Try weekly (faster) vs. monthly (more data)
- Monthly view processes more transactions

**2. Check Network:**

- Slow internet connection?
- Try different WiFi network
- Use wired connection if possible

**3. Browser Issues:**

- Close other tabs
- Restart browser
- Update to latest version
- Disable browser extensions temporarily

**4. Device Resources:**

- Close other applications
- Check if device running slow overall
- Restart computer if needed

### Expected Load Times
- **Acceptable:** 2-5 seconds
- **Slow:** 5-10 seconds (check network)
- **Too Slow:** 10+ seconds (report issue)

---

## Error Messages

### "Unable to load analytics data"

**Causes:**

- Server error during computation
- Database connection issue
- Permission problem

**Solutions:**

1. Refresh page (F5)
2. Try again in 5 minutes
3. Switch to different class then back
4. Report if persists

### "Analytics data outdated"

**Meaning:** Cached data is old

**Solutions:**

- Normal if just made major changes
- Wait 1 hour for recomputation
- Data updates daily automatically
- Contact support if shows as "outdated" for 24+ hours

### "Not enough data for trend analysis"

**Meaning:** Need more historical data

**Solutions:**

- Need 2+ weeks of data
- Continue normal operations
- Check back in a week
- Metrics still shown, just no trends yet

---

## When to Contact Support

Report to Help & Support if:

- Dashboard completely broken for 24+ hours
- Data clearly incorrect (impossible values)
- Alerts triggering incorrectly
- Performance consistently terrible
- Error messages persisting after troubleshooting

**Include in Report:**

- Screenshot of issue
- Which class/join_code
- Time window selected
- Browser and version
- Steps to reproduce

---

## Quick Checks Checklist

Before reporting an issue, verify:

- [ ] Tried different time window (weekly/monthly)
- [ ] Checked in different browser/incognito mode
- [ ] Cleared browser cache
- [ ] Verified students have recent activity
- [ ] Waited 24 hours after major changes
- [ ] Checked if other teachers having same issue
- [ ] Read relevant documentation

---

## Related Documentation

- **[Classroom Economy Guide](../../economy_guide.md)** - Designing balanced economies
- **[Teacher Manual](../../teacher_manual.md)** - Complete reference

---

**Last Updated:** 2026-01-09
**Version:** 1.7.0
**Quick Help:** Most issues resolve by trying different time window or waiting 24 hours for data update.
