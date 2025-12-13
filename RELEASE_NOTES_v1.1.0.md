# Release Notes - Version 1.1.0

**Release Date**: December 13, 2024

Version 1.1.0 brings exciting new analytics features, a completely redesigned user interface, and important quality-of-life improvements for teachers managing classroom economies.

---

## 🎉 What's New

### Student Analytics Dashboard
Students now have visibility into their financial habits with a new **Weekly Statistics** card on their dashboard:

- **Days Tapped In** - Track attendance participation
- **Minutes This Week** - Total time spent in class
- **Earnings This Week/Month** - See income trends
- **Spending This Week/Month** - Monitor spending habits

These metrics help students understand their financial behavior and make better decisions about budgeting and saving.

### Savings Projection Visualization
The bank page now features a **12-month savings projection graph** that:

- Shows visual projection of savings growth based on current balance
- Respects banking settings (simple vs. compound interest)
- Accounts for compounding frequency (daily, weekly, monthly)
- Helps students visualize long-term saving goals
- Uses Chart.js for interactive, responsive charts

### Long-Term Goal Items
Teachers can now mark store items as **Long-Term Goal Items**:

- Exempt expensive items from CWI balance warnings
- Perfect for class rewards that students save for over many weeks
- Examples: class party, field trip, special privileges
- Allows flexible pricing without triggering economy health warnings

### Modern UI Redesign
Complete visual refresh of the entire application:

- **Softer, Eye-Friendly Colors** - Reduced brightness and harsh contrasts
- **Improved Navigation** - Sticky sidebar for quick access to features
- **Better Layout** - Reorganized student dashboard with left navigation
- **Professional Design** - Modern card-based layouts with shadows and spacing
- **Responsive** - Better mobile and tablet experiences

### Enhanced Economy Health Dashboard
The Economy Health page now provides more actionable guidance:

- **Specific Recommended Ranges** - No more vague warnings
- **Clear Action Items** - Links directly to settings pages
- **Better Formatting** - Absolute values for negative amounts (fines)
- **Helpful Suggestions** - Guidance on when to use Long-Term Goal items

---

## 🐛 Bug Fixes

### Critical Fixes
- **Fixed invisible tabs** on 15+ pages (Student Management, Store Management, etc.)
- **Restored missing Pending Actions section** on admin dashboard (store approvals, hall passes, insurance claims)
- **Fixed missing navigation links** on login screens (account setup, recovery, privacy/terms)

### UI Fixes
- Fixed CSS scoping issue that affected Bootstrap tab navigation
- Added missing Bootstrap Icons CSS imports
- Added missing utility CSS classes (`.btn-white`, `.icon-circle`)
- Improved navigation accessibility with proper ARIA labels

---

## 🔧 Technical Improvements

### Database Changes
- Added `is_long_term_goal` column to `store_items` table
- Migration is backward-compatible and safe to deploy
- Includes proper up/down migration scripts

### Performance
- Optimized weekly statistics calculation with efficient queries
- Reduced context usage with improved template rendering
- Added proper indexing for analytics queries

### Code Quality
- Improved balance checker with better warning messages
- Enhanced error handling in analytics calculations
- Better separation of concerns in template structure

---

## 📊 Analytics Details

### How Weekly Stats Work
- **Days Tapped In**: Counts unique calendar days with active attendance
- **Minutes This Week**: Sums duration of all tap-in sessions (including ongoing sessions)
- **Earnings**: Aggregates positive transactions (payroll, bonuses, etc.)
- **Spending**: Aggregates negative transactions (purchases, rent, fines, etc.)
- All calculations use UTC timestamps and respect week boundaries (Monday-Sunday)

### Savings Projection Algorithm
The projection graph uses the following formulas:

**Compound Interest**:
```
Future Value = Current Balance × (1 + rate)^periods
```

**Simple Interest**:
```
Future Value = Principal × (1 + rate × time)
```

The graph projects 12 months forward and updates dynamically based on:
- Current savings balance
- Annual percentage yield (APY)
- Compounding frequency
- Interest calculation type (simple vs. compound)

---

## 🎓 For Teachers

### Setting Up Long-Term Goal Items
1. Go to **Store Management**
2. Create or edit an item
3. Check **"Long-Term Goal Item"** checkbox
4. Set any price you want - it won't trigger CWI warnings
5. Save the item

Perfect for:
- Class pizza parties ($200+)
- Field trips ($500+)
- Special privileges (priceless!)
- End-of-year rewards

### Using the Enhanced Economy Health
The improved Economy Health page now shows:
- **Specific dollar ranges** for each setting
- **Direct links** to fix issues
- **Color-coded warnings** (Critical, Warning, Info)
- **Actionable recommendations** based on your CWI

---

## 📦 Upgrade Instructions

### For Existing Installations

1. **Pull the latest code**:
   ```bash
   git pull origin main
   ```

2. **Run database migrations**:
   ```bash
   flask db upgrade
   ```

3. **Restart the application**:
   ```bash
   sudo systemctl restart classroom-economy
   ```

4. **Clear browser cache** to see the new UI

### Migration Notes
- The `is_long_term_goal` column defaults to `False` for existing items
- No data loss or breaking changes
- Downgrade available if needed: `flask db downgrade`

---

## 🔗 Documentation Updates

- Updated CHANGELOG.md with all changes
- Added economy health tips to teacher manual
- Documented analytics calculations
- Updated DEVELOPMENT.md roadmap

---

## 🙏 Credits

Thanks to all contributors who helped test and provide feedback on the UI redesign and analytics features.

---

## 📝 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.

---

## 🐞 Known Issues

None at this time.

---

## 💬 Support

- Report issues: [GitHub Issues](https://github.com/timwonderer/classroom-economy/issues)
- Documentation: `/docs` directory
- Email: [support contact]

---

**Enjoy v1.1.0! 🎉**
