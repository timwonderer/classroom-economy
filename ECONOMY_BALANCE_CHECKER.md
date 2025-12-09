# Economy Balance Checker - Implementation Guide

## Overview

The Economy Balance Checker is a centralized system that validates all economy settings against the **Classroom Wage Index (CWI)** per the AGENTS financial setup specification.

## What is CWI?

**CWI (Classroom Wage Index)** is the expected weekly income for a student with perfect attendance. All economy features (rent, insurance, fines, store items) must scale proportionally from CWI to maintain balance.

### Expected Weekly Hours

Teachers must specify their **expected weekly hours** (or minutes) in payroll settings. This value represents how many hours per week students typically attend class. This is used **ONLY** for economy balance checking, not for actual payroll calculations.

**Example:**
- A class that meets 5 days/week for 1 hour each = 5 hours/week
- A class that meets 3 days/week for 90 minutes each = 4.5 hours/week

This field is stored in `PayrollSettings.expected_weekly_hours` (default: 5.0 hours).

## Components

### 1. Backend Utility (`app/utils/economy_balance.py`)

Core Python module that:
- Calculates CWI dynamically based on payroll settings
- Validates economy settings against standard ratios
- Generates teacher recommendations
- Performs budget survival tests

#### Key Classes:

- `EconomyBalanceChecker`: Main checker class
- `CWICalculation`: CWI calculation result
- `BalanceWarning`: Individual balance warning
- `EconomyBalance`: Complete economy analysis

#### Standard Ratios (per AGENTS spec):

```python
Rent:      2.0-2.5x CWI (default: 2.25x)
Utilities: 0.20-0.30x CWI (default: 0.25x)
Insurance: 0.05-0.12x CWI (default: 0.08x)
Fines:     0.05-0.15x CWI (default: 0.10x)

Store Items:
  BASIC:    0.02-0.05x CWI
  STANDARD: 0.05-0.10x CWI
  PREMIUM:  0.10-0.25x CWI
  LUXURY:   0.25-0.50x CWI
```

### 2. API Endpoints (`app/routes/admin.py`)

Three RESTful endpoints for real-time validation:

#### `/admin/api/economy/calculate-cwi` (POST)
Calculate CWI based on pay rate.

**Request:**
```json
{
  "pay_rate": 15.0,
  "expected_weekly_hours": 5.0,
  "block": "A" (optional)
}
```

**Response:**
```json
{
  "status": "success",
  "cwi": 75.0,
  "breakdown": {
    "pay_rate_per_hour": 15.0,
    "pay_rate_per_minute": 0.25,
    "expected_weekly_hours": 5.0,
    "expected_weekly_minutes": 300.0,
    "notes": ["Calculation notes..."]
  }
}
```

#### `/admin/api/economy/analyze` (POST)
Perform comprehensive economy analysis.

**Request:**
```json
{
  "expected_weekly_hours": 5.0,
  "block": "A" (optional)
}
```

**Response:**
```json
{
  "status": "success",
  "cwi": 75.0,
  "is_balanced": true,
  "budget_survival_test_passed": true,
  "weekly_savings": 10.5,
  "warnings": {
    "critical": [],
    "warning": [],
    "info": [...]
  },
  "recommendations": {
    "rent": {
      "min": 150.0,
      "max": 187.5,
      "recommended": 168.75
    },
    ...
  }
}
```

#### `/admin/api/economy/validate/<feature>` (POST)
Validate a specific feature value.

**Features:** `rent`, `insurance`, `fine`, `store_item`

**Request:**
```json
{
  "value": 170.0,
  "frequency": "weekly" (for insurance only),
  "expected_weekly_hours": 5.0
}
```

**Response:**
```json
{
  "status": "success",
  "is_valid": true,
  "warnings": [
    {
      "level": "success",
      "message": "Rent is balanced at $170.00 (2.27x weekly income)"
    }
  ],
  "recommendations": {
    "min": 150.0,
    "max": 187.5,
    "recommended": 168.75
  },
  "cwi": 75.0,
  "ratio": 2.27
}
```

### 3. Client-Side Module (`static/js/economy-balance.js`)

JavaScript class for real-time validation in forms.

#### Features:
- Automatic validation on input
- Visual feedback (success/warning/critical)
- CWI display
- Pricing tier recommendations
- Debounced validation (500ms)

#### Usage:

**1. Include the script:**
```html
<script src="{{ url_for('static', filename='js/economy-balance.js') }}"></script>
```

**2. Add data attributes to inputs:**
```html
<input type="number"
       name="rent_amount"
       data-economy-validate="rent">

<input type="number"
       name="premium"
       data-economy-validate="insurance"
       data-economy-frequency="weekly">

<input type="number"
       name="price"
       data-economy-validate="store_item">

<input type="number"
       name="fine_amount"
       data-economy-validate="fine">
```

**3. Add containers for warnings and CWI:**
```html
<div id="cwi-info"></div>
<div id="economy-warnings"></div>
```

**4. Initialize in JavaScript:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
  if (typeof EconomyBalanceChecker !== 'undefined') {
    const economyChecker = new EconomyBalanceChecker({
      warningsContainer: '#economy-warnings',
      expectedWeeklyHours: 5.0
    });

    // Display CWI info
    economyChecker.analyzeEconomy().then(analysis => {
      economyChecker.displayCWIInfo(analysis, '#cwi-info');
    }).catch(err => {
      console.log('Payroll not configured yet');
    });
  }
});
```

## Integrated Pages

The balance checker is currently integrated into:

1. **Payroll Page** (`/admin/payroll`)
   - **Overview tab**: Displays CWI calculation card with real-time updates
   - Configure expected weekly hours per class/block
   - Shows pay rate breakdown and weekly income projection
   - Displays all economy recommendations (rent, insurance, fines, store tiers)
   - Block-scoped: Each class can have different expected hours
   - **Apply to All Classes** option for bulk updates
   - Real-time CWI recalculation as expected hours change

2. **Rent Settings** (`/admin/rent-settings`)
   - Validates rent amount against CWI
   - Shows recommended rent range
   - Displays warnings if too high/low
   - Block-scoped: Different rent for different classes

3. **Insurance Policy Editor** (`/admin/insurance/edit/<id>`)
   - Validates premium amount against CWI
   - Adjusts for billing frequency (weekly, monthly, etc.)
   - Shows recommended premium ranges
   - Global: Same premium across all blocks

4. **Store Item Editor** (`/admin/store/edit/<id>`)
   - Validates price against CWI
   - Shows pricing tier (BASIC, STANDARD, PREMIUM, LUXURY)
   - Warns if price is outside all tiers
   - Global: Same price across all blocks

5. **Fines** (via API - UI integration pending)
   - Validates fine amounts
   - Ensures fines are meaningful but not excessive
   - Global: Same fine amounts across all blocks

## Budget Survival Test

The system performs a "Budget Survival Test" to ensure students can:
- Pay rent
- Afford insurance (cheapest option)
- Purchase store items
- Save at least **10% of CWI** weekly

If this test fails, teachers receive a **CRITICAL** warning.

## Warning Levels

- **INFO**: Setting is balanced and within recommended range
- **WARNING**: Setting deviates from recommended range (15-30%)
- **CRITICAL**: Setting deviates significantly (>30%) or fails budget test

## Customization

### Adjusting Ratios

Edit `app/utils/economy_balance.py`:

```python
class EconomyBalanceChecker:
    RENT_MIN_RATIO = 2.0
    RENT_MAX_RATIO = 2.5
    # ... etc
```

### Changing Expected Weekly Hours

Default is 5 hours. Adjust per teacher/class:

```javascript
const economyChecker = new EconomyBalanceChecker({
  expectedWeeklyHours: 7.5  // Custom value
});
```

### Customizing Validation Thresholds

```python
class EconomyBalanceChecker:
    MINOR_DEVIATION_THRESHOLD = 0.15  # 15%
    MAJOR_DEVIATION_THRESHOLD = 0.30  # 30%
```

## Future Enhancements

1. **Onboarding Integration**: Add CWI calculator to teacher onboarding
2. **Dashboard Widget**: Show overall economy health on admin dashboard
3. **Historical Tracking**: Track CWI changes over time
4. **Student Simulation**: Predict student balance trajectories
5. **Utilities Feature**: Add utilities feature (not yet implemented)
6. **Batch Validation**: Validate all settings at once

## Testing

To test the balance checker:

1. **Configure payroll** first (required for CWI calculation)
2. Navigate to rent/insurance/store settings
3. Adjust values and observe real-time warnings
4. Check that recommendations update dynamically

## Troubleshooting

**Issue: "Payroll not configured yet" message**
- Solution: Configure payroll settings first

**Issue: Warnings not appearing**
- Check browser console for errors
- Verify `economy-balance.js` is loaded
- Ensure `data-economy-validate` attributes are present

**Issue: Incorrect CWI calculation**
- Verify payroll settings are correct
- Check pay rate is stored as per-minute in database
- Verify expected_weekly_hours parameter

**Issue: CWI not updating after changing expected weekly hours** (FIXED in latest commit)
- **Symptom**: Changing expected weekly hours on payroll page doesn't update CWI on other pages
- **Root Cause**: API was defaulting to 5.0 hours instead of using value from database
- **Fix**: API now reads `expected_weekly_hours` from `payroll_settings` when not provided in request
- **Action**: Update to latest version and refresh pages

**Issue: Wrong CWI for different blocks/classes** (FIXED in latest commit)
- **Symptom**: All blocks show same CWI even with different pay rates
- **Root Cause**: Block parameter wasn't being passed from frontend to backend API
- **Fix**: JavaScript now passes current block to `analyzeEconomy()`, API filters by block
- **Action**: Update to latest version and test with block selector

**Issue: Rent settings showing wrong CWI** (FIXED in latest commit)
- **Symptom**: Rent settings page shows incorrect CWI for selected block
- **Root Cause**: Template wasn't passing `settings_block` to API call
- **Fix**: Updated template to pass current block parameter
- **Action**: Update to latest version

## Technical Notes

- CWI is calculated weekly, regardless of payroll frequency
- Pay rates are stored as **per-minute** in the database
- All monetary comparisons use weekly equivalents
- Insurance premiums are normalized to weekly for comparison
- Rent is normalized to weekly based on frequency type

### Block-Scoped CWI Calculations

**IMPORTANT:** For specialty schools with different pay rates per class/block:

- **Payroll Settings** are block-scoped: Each block can have different pay rates and expected weekly hours
- **Rent Settings** are block-scoped: Each block can have different rent amounts
- **Insurance Policies** are NOT block-scoped: Premiums are the same across all blocks (only visibility is controlled)
- **Store Items** are NOT block-scoped: Prices are the same across all blocks (only visibility is controlled)
- **Fines** are NOT block-scoped: Fine amounts are the same across all blocks

When calculating CWI:
- The API endpoints accept an optional `block` parameter
- If provided, the endpoint uses the payroll settings for that specific block
- If not provided, the endpoint uses the first active payroll setting found

**Example Use Cases:**
- AP Chemistry: $0.30/min pay rate, 5 hours/week → CWI = $90/week
- Regular Chemistry: $0.25/min pay rate, 3 hours/week → CWI = $45/week
- Honors Chemistry: $0.25/min pay rate, 4 hours/week → CWI = $60/week

Each class maintains its own CWI calculation, allowing accurate economy recommendations for each class independently.

**JavaScript Usage:**
```javascript
// Pass block parameter when calling analyzeEconomy
const currentBlock = 'A';
economyChecker.analyzeEconomy(expectedHours, currentBlock).then(analysis => {
  // Analysis uses payroll settings for block A
});
```

**Known Limitation:**
- Insurance and Store Item pages show CWI based on first payroll setting if teacher has multiple blocks
- This is by design since these features are not block-scoped in pricing
- Teachers should ensure consistent pay rates if using shared pricing across blocks

## References

- AGENTS financial setup specification: `/AGENTS financial setup.md`
- Original feature request: [Add economy balance checker]
- Backend utility: `app/utils/economy_balance.py`
- Frontend module: `static/js/economy-balance.js`
- API endpoints: `app/routes/admin.py`
