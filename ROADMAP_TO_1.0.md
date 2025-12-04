# Roadmap to Version 1.0

**Current Version:** 0.9.0 (Pre-Release)
**Target:** 1.0.0 Production Release
**Last Updated:** 2025-12-04

---

## Executive Summary

Classroom Token Hub is nearing its 1.0 release. The platform is feature-complete and actively used in classroom testing. However, **one critical security issue** and several code quality improvements must be addressed before the 1.0 release.

---

## Release Blockers (MUST FIX)

### 🚨 P0: Critical Data Isolation Issue

**Issue:** Same-Teacher Multi-Period Data Leak
**Status:** ❌ **NOT FIXED** - BLOCKING 1.0 RELEASE
**Documentation:** [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/security/CRITICAL_SAME_TEACHER_LEAK.md)

**Problem:**
Students enrolled in multiple periods with the same teacher see aggregated data across all periods instead of period-specific, isolated data.

**Root Cause:**
The `Transaction` table (and related models: `StudentItem`, `StudentInsurance`, `RentPayment`, `HallPassLog`) only track `teacher_id`, not the specific `join_code` or `block` that identifies individual class periods.

**Impact:**
- Students see combined balances across periods
- Transactions from all periods are visible together
- Store purchases, insurance policies, and rent payments are not properly scoped
- Violates the core principle: "join code is the source of truth"

**Required Fix:**
1. Add `join_code` column to affected tables
2. Create database migrations with backfill strategies
3. Refactor all queries to scope by `join_code` instead of `teacher_id` alone
4. Update transaction creation to include `join_code`
5. Implement comprehensive tests for multi-period isolation

**Estimated Effort:** 12-16 hours
- Schema changes: 2-3 hours
- Query refactoring: 4-6 hours
- Testing: 4-5 hours
- Migration and deployment: 2-3 hours

**Recommended Approach:**
See the detailed implementation plan in [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/security/CRITICAL_SAME_TEACHER_LEAK.md)

---

## High Priority (RECOMMENDED FOR 1.0)

### 🔧 P1: Deprecated Code Pattern Updates

**Status:** ⚠️ Documented, not yet fixed
**Documentation:** [docs/development/DEPRECATED_CODE_PATTERNS.md](docs/development/DEPRECATED_CODE_PATTERNS.md)

**Issues:**

1. **Deprecated `datetime.utcnow()` (~45 occurrences)**
   - Replace with `datetime.now(UTC)` for Python 3.12+ compatibility
   - Affects: models, routes, wsgi, scripts

2. **Deprecated `Query.get()` (~20 occurrences)**
   - Replace with `db.session.get(Model, id)` for SQLAlchemy 2.0+ compatibility
   - Affects: auth helpers, all route files

3. **SQLAlchemy Subquery Warning (1 occurrence)**
   - Make subquery coercion explicit in `system_admin.py:849`

**Estimated Effort:** 6-8 hours
- Pattern replacement: 4-5 hours
- Testing: 2-3 hours

**Risk:** Low (non-breaking changes if done carefully)

---

## Medium Priority (NICE TO HAVE)

### 📝 GitHub Secrets Configuration

**Status:** ⚠️ Action required by repository maintainer
**Issue:** GitHub Actions workflows now reference `secrets.PRODUCTION_SERVER_IP` but the secret must be manually configured

**Required Action:**
1. Go to repository Settings → Secrets and Variables → Actions
2. Add new repository secret:
   - Name: `PRODUCTION_SERVER_IP`
   - Value: `24.199.127.184` (or current production server IP)

**Estimated Effort:** 2 minutes

---

## Completed Preparatory Work ✅

The following housekeeping tasks have been completed in preparation for 1.0:

### Documentation Organization
- ✅ Consolidated scattered root-level documentation into organized `docs/` structure
- ✅ Created comprehensive `PROJECT_HISTORY.md` capturing project philosophy and evolution
- ✅ Reorganized security audits into `docs/security/`
- ✅ Moved development guides to `docs/development/`
- ✅ Archived historical fix summaries to `docs/archive/`
- ✅ Updated `docs/README.md` with complete documentation map

### Code Cleanup
- ✅ Removed hardcoded IP addresses from GitHub Actions workflows
- ✅ Removed obsolete duplicate scripts
- ✅ Removed debug print statements from production routes
- ✅ Created tracking document for deprecated patterns

### Documentation Updates
- ✅ Updated README with version 0.9.0 status and project status section
- ✅ Removed platform-specific deployment language for universal compatibility
- ✅ Updated CHANGELOG with comprehensive housekeeping summary
- ✅ Created this ROADMAP document

---

## Version 1.0 Release Criteria

To release version 1.0, the following must be achieved:

### 🚨 CRITICAL (BLOCKING)
- [ ] **Fix same-teacher multi-period data leak** (P0 blocker)
  - [ ] Add `join_code` columns to Transaction, StudentItem, StudentInsurance, RentPayment, HallPassLog
  - [ ] Create and test database migrations
  - [ ] Refactor all queries to scope by join_code
  - [ ] Comprehensive testing for data isolation
  - [ ] Deploy and validate in staging environment

### ⚡ HIGH PRIORITY (STRONGLY RECOMMENDED)
- [ ] **Update deprecated Python/SQLAlchemy patterns** (P1)
  - [ ] Replace `datetime.utcnow()` with `datetime.now(UTC)`
  - [ ] Replace `Query.get()` with `db.session.get()`
  - [ ] Fix SQLAlchemy subquery warning
  - [ ] Full test suite validation

### 📋 NICE TO HAVE
- [ ] Configure `PRODUCTION_SERVER_IP` GitHub secret
- [ ] Review and update user-facing documentation for clarity
- [ ] Create release notes document
- [ ] Update version numbers across all files

### ✅ ALREADY COMPLETE
- [x] Feature completeness (all core features implemented)
- [x] Security audits completed and recommendations implemented
- [x] Comprehensive test coverage (47 test files)
- [x] Documentation organization and cleanup
- [x] CI/CD pipeline operational
- [x] Production deployment infrastructure ready
- [x] Monitoring and alerting configured
- [x] Backup and restore procedures documented

---

## Post-1.0 Roadmap

After achieving 1.0 release, the following enhancements are planned:

### Version 1.1 - Analytics & Insights
- Dashboard visualizations for student progress
- Class economy health metrics
- Teacher analytics for payroll and store performance
- Export capabilities for reports

### Version 1.2 - Mobile Experience
- Responsive design improvements
- Progressive Web App (PWA) capabilities
- Native mobile app exploration
- Offline support for attendance tracking

### Version 1.3 - Gamification
- Achievement badge system
- Optional leaderboards (privacy-conscious)
- Progress tracking and milestones
- Student engagement metrics

### Version 1.4 - Extended Features
- Parent portal (optional, privacy-controlled)
- Curriculum integration resources
- Pre-built lesson plans
- Financial literacy assessment tools

### Version 2.0 - Internationalization
- Multi-language support
- Currency localization
- Regional educational standard alignment
- Translation community platform

---

## Risk Assessment

### High Risk Items
1. **Same-teacher data leak fix** - Complex schema changes affecting core functionality
   - **Mitigation:** Thorough testing, staged rollout, rollback plan

2. **Database migrations** - Backfilling join_code for existing data
   - **Mitigation:** Dry-run testing, backup before migration, validation scripts

### Medium Risk Items
1. **Deprecated pattern updates** - Widespread code changes
   - **Mitigation:** Comprehensive test suite, incremental changes, code review

### Low Risk Items
1. **Documentation updates** - No code impact
2. **GitHub secrets configuration** - Simple administrative task

---

## Timeline Estimate

**Optimistic:** 2-3 weeks
**Realistic:** 4-6 weeks
**Conservative:** 8-10 weeks

### Week-by-Week Breakdown (Realistic Scenario)

**Weeks 1-2: Critical Data Leak Fix**
- Design schema changes and migration strategy
- Implement database migrations with backfill
- Refactor queries across all routes
- Unit and integration testing

**Week 3: Staging Validation**
- Deploy to staging environment
- Run comprehensive regression tests
- Validate data isolation in real-world scenarios
- Fix any discovered issues

**Week 4: Deprecated Pattern Updates**
- Update datetime.utcnow() occurrences
- Update Query.get() occurrences
- Fix SQLAlchemy warnings
- Full test suite validation

**Week 5: Final Testing & Documentation**
- Complete system testing
- Update release documentation
- Create migration guides for existing deployments
- Security review

**Week 6: Release Preparation**
- Create release candidate
- Final production deployment planning
- Rollback procedures documented
- **Version 1.0 Release! 🎉**

---

## Success Metrics

Version 1.0 will be considered successful when:

1. ✅ All P0 and P1 issues resolved
2. ✅ Full test suite passes (100% of existing tests)
3. ✅ No known security vulnerabilities
4. ✅ Staging environment validated for 1+ week
5. ✅ Production deployment successful
6. ✅ No critical bugs reported within 48 hours of release
7. ✅ Documentation complete and accurate
8. ✅ Rollback plan tested and ready

---

## Resources & Support

### Development Team
- Primary maintainer(s): [To be specified]
- Code reviewers: [To be specified]
- Testing team: [To be specified]

### Documentation
- **Technical Reference:** [docs/technical-reference/](docs/technical-reference/)
- **Security Documentation:** [docs/security/](docs/security/)
- **Development Guides:** [docs/development/](docs/development/)
- **Operations Guides:** [docs/operations/](docs/operations/)

### Issue Tracking
- **Critical Issues:** GitHub Issues with `P0` label
- **High Priority:** GitHub Issues with `P1` label
- **Enhancements:** GitHub Issues with `enhancement` label

### Communication
- **Updates:** Track progress via GitHub Issues and Pull Requests
- **Questions:** GitHub Discussions or Issues
- **Security:** Report privately to maintainers

---

## Conclusion

Classroom Token Hub has reached a mature state with comprehensive features, solid architecture, and thorough documentation. The path to version 1.0 is clear: fix the critical data isolation issue, update deprecated code patterns, and conduct final validation testing.

With an estimated 4-6 weeks of focused effort, the project will be ready for official version 1.0 release, marking a significant milestone in providing educators with a robust platform for teaching financial literacy through hands-on classroom economy simulations.

**The journey to 1.0 is nearly complete. Let's finish strong! 🚀**

---

**Next Steps:**
1. Create GitHub issue for P0 critical data leak fix
2. Create GitHub issue for P1 deprecated pattern updates
3. Schedule development time for fixes
4. Begin implementation following this roadmap
5. Regular progress updates and timeline adjustments as needed

**Questions or concerns? Open a GitHub Discussion or Issue.**

---

**Last Updated:** 2025-12-04
**Version:** 0.9.0 Pre-Release
