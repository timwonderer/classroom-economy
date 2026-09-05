---
title: Rent Itemization Troubleshooting
description: Why rent itemization totals or covered items don't match what students see.
category: diagnostics
subcategory: teacher
roles: [teacher]
---

# Rent Itemization Troubleshooting

**Quick diagnostic guide for rent itemization issues.**

**Version:** 1.7.0+
**Route:** `/admin/settings/rent`

---

## Items Not Showing in Store

### Symptoms
- Created rent item with "Available in Store" enabled
- Item not appearing in student store view
- Students can't find rent alternatives

### Quick Fixes

**1. Verify Store Availability Toggle:**

- Go to Rent Settings
- Check each item has "Available in Store" = ON
- Save settings if you toggled anything

**2. Check Block Visibility:**

- Rent items inherit block visibility from rent settings
- Ensure rent enabled for current block/period
- Verify students viewing correct class

**3. Force Sync:**

- Toggle "Available in Store" OFF
- Save settings
- Toggle back ON
- Save again
- Check store within 1 minute

**4. Verify Store Item Created:**

- Go to Store Management page
- Look for items marked "Rent Alternative"
- Should match your rent items exactly

### Still Not Working?
Check server logs or contact support with:

- Rent item name
- Join code/class period
- Screenshot of rent settings

---

## Students Can't Purchase Rent Items

### Symptoms
- Items show in store
- Purchase button disabled or gives error
- "Cannot purchase" message

### Causes & Solutions

**Cause 1: Insufficient Balance**

- **Check:** Student balance vs. item price
- **Fix:** Students need enough money in checking account
- **Note:** Just like any store purchase

**Cause 2: Already Owns (Per-Period Items)**

- **Check:** Is this "per rent period" item?
- **Check:** Student privilege badges - do they already have it?
- **Fix:** They must wait until privilege expires (next rent due)
- **Note:** Limit 1 per period enforced automatically

**Cause 3: Late on Rent + Non-Rent Item**

- **Check:** Is student late on rent?
- **Check:** Is purchase restriction enabled?
- **Fix:** Student can ONLY buy rent-covered items when late
- **Note:** This is intentional incentive structure

**Cause 4: Item Inactive/Expired**

- **Check:** Is rent item still active in settings?
- **Check:** Was item recently deleted then recreated?
- **Fix:** Verify item exists and active in both rent and store

---

## Privilege Badges Not Showing

### Symptoms
- Student paid rent but no green badges
- Student bought item but no blue badge
- Teacher dashboard doesn't show privileges

### Quick Fixes

**1. Verify Purchase Duration:**

- Only "per rent period" items show as badges
- "Per use" items don't create privileges
- Check rent item settings for duration type

**2. Check Rent Payment Status:**

- Green badges only for students who paid rent
- Student must be current on rent (not late)
- Verify rent payment recorded in transactions

**3. Check Expiration:**

- Badges only show for non-expired privileges
- Check if next rent payment came due
- Per-period items expire when rent due

**4. Refresh Student Detail Page:**

- Navigate away and back to student page
- Hard refresh browser (Ctrl+Shift+R)
- Check multiple students to rule out single case

**5. Verify Rent Perk Grants Are Healthy:**

- Paid students with per-use perks should have an active grant row (`uses_remaining > 0` or `-1` for unlimited).
- Exhausted legacy grant rows (`uses_remaining = 0`) no longer block new free-use grants, but older data may need one fresh rent payment to normalize.
- Hall-pass top-offs now reconcile against actual pass balance if `rent_hall_passes` drifted out of sync.

### Badge Colors Meaning
- 🟢 **Green:** Included in paid rent (automatic)
- 🔵 **Blue:** Purchased individually from store
- **No Badge:** Expired, not owned, or not applicable

---

## Store Prices Not Syncing

### Symptoms
- Changed store price in rent settings
- Store item still shows old price
- Price mismatch between rent and store

### Quick Fixes

**1. Save After Changes:**

- Always click "Save Settings" after price changes
- Verify save confirmation message
- Wait 30 seconds for sync

**2. Check Store Management:**

- Go to Store Management page
- Find rent alternative item
- Manually update price if needed
- Save store settings

**3. Verify Item Link:**

- Is store item properly linked to rent item?
- Check if manually created store item vs. auto-created
- Delete and let auto-recreation happen

**4. Clear Cache:**

- Students may see cached prices
- Have students refresh browser
- Prices update on next page load

### When Prices Don't Sync
Manual fix:

1. Note the correct price from rent settings
2. Go to Store Management
3. Edit the rent alternative item
4. Update price manually
5. Save

Report persistent sync issues to support.

---

## Items Duplicated in Store

### Symptoms
- Same rent item appearing twice in store
- Multiple entries for "Desk" or "Locker"
- Confusion for students

### Causes & Solutions

**Cause: Manual Store Item + Auto-Created**

- You may have manually created store item with same name
- Then enabled "Available in Store" creating duplicate

**Fix:**

1. Go to Store Management
2. Identify the manual item (older creation date)
3. Delete the manual item
4. Keep the auto-created rent alternative
5. Verify only one remains

**Prevention:**

- Let rent itemization auto-create store items
- Don't manually create items for rent alternatives
- Use rent settings as single source of truth

---

## Base Value vs. Store Price Confusion

### Common Questions

**"Should base value equal store price?"**

- **No!** Base value = portion of rent
- Store price = à la carte purchase price
- Store price usually 20-50% higher
- Creates incentive to pay rent

**"My base values don't add up to rent amount"**

- **That's okay!** Base values show relative worth
- They don't have to sum exactly to rent
- Use them to communicate value breakdown

**"Students don't understand the math"**

- Add "Pro Tip" message explaining:
  - Total rent value vs. à la carte total
  - Money saved by paying rent
  - Use visual comparison chart

---

## Purchase Duration Issues

### "Per Use" Items

**Problem: Students buying repeatedly**

- **Expected behavior!** Per-use means each time
- If this is wrong, change to "per rent period"
- Edit rent item → Change duration → Save

**Problem: Students think it's broken**

- Add clear description: "You must buy each time you need this"
- Example: "Supply Pack - Buy each time you need supplies"

### "Per Rent Period" Items

**Problem: Can't buy more than once**

- **Expected behavior!** Limit 1 per period
- Students wait until next rent cycle
- Check expiration date shown to student

**Problem: Expired too soon**

- Tied to rent due date, not calendar period
- If rent due monthly on 1st, items expire on 1st
- Check rent frequency settings

**Problem: Never expires**

- Check rent frequency configured
- Verify rent is actually enabled
- Check next rent due date set correctly

---

## Enhanced Purchase Restrictions

### Symptoms
- Student late on rent
- Can't buy ANY store items (expected some to work)
- OR can buy rent items but expected full block

### How It Works

**Without Itemization:**

- Late students blocked from ALL store purchases
- Original behavior

**With Itemization:**

- Late students CAN buy rent-covered items
- Late students BLOCKED from other store items
- Intentional incentive: "Pay rent or pay premium + lose other access"

### Common Scenarios

**Scenario 1: "Student late, can't buy snacks"**

- ✅ **Correct:** Snacks not covered by rent
- ✅ **Expected:** Blocked until rent paid
- 💡 **Message:** Pay rent to access full store

**Scenario 2: "Student late, bought locker"**

- ✅ **Correct:** Locker IS covered by rent
- ✅ **Expected:** Can buy at à la carte price
- 💡 **Message:** Paying more than if paid rent

**Scenario 3: "Student paid rent, still blocked"**

- ❌ **Problem:** Should have full access
- **Check:** Did rent payment process correctly?
- **Check:** Is student marked as current on rent?
- **Fix:** Verify transaction, re-process if needed

### Disabling Enhanced Restrictions

If you don't want dynamic behavior:

1. Turn OFF "Prevent Purchase When Late" toggle
2. OR don't use rent itemization
3. Can't have both features independently yet

---

## Student Confusion Issues

### "Students don't understand why buy individually?"

**Solutions:**

- Emphasize total value comparison
- Show math: Rent $50 vs. Individual items $67
- Create visual chart in classroom
- Discuss in class: bundling economics

### "Students think per-use items are broken"

**Solutions:**

- Clear descriptions: "Single use - buy each time needed"
- Examples: "Like buying one pencil, not a box"
- Explain consumables vs. privileges
- Consider changing to per-period if confusion persists

### "Students asking why rent includes everything"

**Teaching Opportunity:**

- Real-world parallel: Apartment rent (unit + water + trash)
- Bundle economics: Cheaper together than separate
- Convenience fee: One payment covers multiple items
- Financial planning: Predictable monthly cost

---

## Setup Best Practices Checklist

Avoid common issues by:

- [ ] Base values show relative worth (don't have to sum to rent)
- [ ] Store prices 20-50% higher than base values
- [ ] Clear item descriptions explaining what included
- [ ] Choose appropriate duration (per-use vs per-period)
- [ ] Test purchase as student before announcing
- [ ] Explain to students in class
- [ ] Create visual comparison chart
- [ ] Monitor first week for confusion

---

## Testing Checklist

Before rolling out to students:

**As Teacher:**

- [ ] Created rent items with reasonable values
- [ ] Enabled store availability on desired items
- [ ] Checked store shows rent alternatives
- [ ] Verified prices match expectations
- [ ] Tested privilege badge appears after purchase

**As Student (using demo/test account):**

- [ ] Can see itemized rent breakdown
- [ ] Can find items in store
- [ ] Can purchase when have balance
- [ ] Sees privilege badge after purchase
- [ ] Understands per-use vs per-period

**Edge Cases:**

- [ ] Tested late rent + purchase restrictions
- [ ] Verified expiration works (per-period items)
- [ ] Checked privilege badges update correctly
- [ ] Confirmed price changes sync to store

---

## When to Contact Support

Report if:

- Store sync completely broken (items never appear)
- Privilege badges not working at all
- Price syncing fails consistently
- Purchase restrictions blocking incorrectly
- Database errors or crashes

**Don't Report:**

- Students confused (teach them the system)
- Wanting different behavior (feature works as designed)
- Minor price delays (<5 minutes)

**Include in Report:**

- Specific rent item name
- Join code/class
- Screenshots of settings
- Steps to reproduce
- Expected vs. actual behavior

---

## Quick Troubleshooting Flowchart

```
Item not in store?
├─ Toggle OFF/ON → Save → Wait 1 min
└─ Still broken? Check store management page

Student can't purchase?
├─ Check balance sufficient?
├─ Already owns (per-period)?
├─ Late on rent (non-rent item)?
└─ Item active in settings?

Badges not showing?
├─ Only per-period items create badges
├─ Check rent payment status
├─ Verify not expired
└─ Refresh student page

Prices wrong?
├─ Saved after changing?
├─ Check store management
└─ Manual update if needed

Students confused?
├─ Clear descriptions?
├─ Class explanation?
└─ Visual comparison chart?
```

---

## Related Documentation

- **[Student Guide](../../student_guide.md)** - Student perspective

---

**Last Updated:** 2026-01-09
**Version:** 1.7.0
**Quick Tip:** Most store sync issues resolve by toggling "Available in Store" OFF then ON and saving.
