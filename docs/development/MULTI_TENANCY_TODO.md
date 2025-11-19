# Multi-Tenancy Implementation - TODO

## Overview
Currently, all teachers (admins) can see and manage all students in the system. This document outlines the plan to implement proper multi-tenancy where each teacher can only see and manage their own students.

## Current State
- ✅ System has Admin (teacher) accounts
- ✅ System has Student accounts
- ✅ System has SystemAdmin accounts (super users)
- ❌ No association between specific students and specific teachers
- ❌ All teachers can see all students
- ❌ All teachers can manage all students

## Goals
- Teachers should only see their own students
- Teachers should only be able to manage their own students
- System admins should see everything (super user privileges)
- Students should be assigned to a specific teacher during creation
- Support for transferring students between teachers

## Database Changes Required

### 1. Add teacher_id to Students table
```sql
ALTER TABLE students ADD COLUMN teacher_id INTEGER REFERENCES admins(id);
```

**Migration Tasks:**
- [ ] Create migration to add `teacher_id` column to `students` table
- [ ] Add foreign key constraint to `admins.id`
- [ ] Handle existing students (assign to first admin? leave NULL? manual assignment?)
- [ ] Make `teacher_id` required for new students

### 2. Update Student Model
```python
class Student(db.Model):
    # ... existing fields ...
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)

    # Relationship
    teacher = db.relationship('Admin', backref='students')
```

## Code Changes Required

### 1. Student Creation/Upload
- [ ] **CSV Upload** (`/admin/upload-students`):
  - Automatically assign `teacher_id = current_admin.id` when teacher uploads
  - System admin should be able to specify teacher during upload

- [ ] **Manual Student Creation** (if any routes exist):
  - Same logic as CSV upload

### 2. Student Queries - Add Filtering
All student queries in admin routes need teacher filtering:

**Routes to Update:**
- [ ] `/admin` - Dashboard student list
- [ ] `/admin/students` - Student management page
- [ ] `/admin/students/<int:student_id>` - Individual student view
- [ ] `/admin/payroll` - Payroll page (only show teacher's students)
- [ ] `/admin/run-payroll` - Run payroll (only for teacher's students)
- [ ] `/admin/payroll-history` - Show history for teacher's students
- [ ] `/admin/transactions` - Filter transactions by teacher's students
- [ ] `/admin/void-transaction/<id>` - Verify student belongs to teacher
- [ ] `/admin/hall-pass` - Filter hall passes by teacher's students
- [ ] `/admin/student/<id>/set-hall-passes` - Verify ownership
- [ ] `/admin/attendance-log` - Filter by teacher's students
- [ ] `/admin/insurance` - Show policies for teacher's students
- [ ] `/admin/insurance/claim/<id>` - Verify student ownership
- [ ] `/admin/bonuses` - Only apply to teacher's students
- [ ] `/admin/store` - Show purchases by teacher's students
- [ ] `/admin/rent-settings` - Apply to teacher's students

**Query Pattern:**
```python
# OLD (current)
students = Student.query.all()

# NEW (with multi-tenancy)
if session.get('is_system_admin'):
    students = Student.query.all()  # System admin sees all
else:
    current_admin_id = Admin.query.filter_by(username=session.get('admin_username')).first().id
    students = Student.query.filter_by(teacher_id=current_admin_id).all()
```

### 3. Create Helper Functions
```python
def get_current_admin():
    """Get the currently logged-in admin object."""
    if 'admin_username' in session:
        return Admin.query.filter_by(username=session['admin_username']).first()
    return None

def get_accessible_students():
    """Get students accessible to current admin (or all if system admin)."""
    if session.get('is_system_admin'):
        return Student.query
    else:
        admin = get_current_admin()
        if admin:
            return Student.query.filter_by(teacher_id=admin.id)
        return Student.query.filter(False)  # No results
```

### 4. Session Management
- [ ] Store `admin_id` in session during login (in addition to username)
- [ ] Add session variable for `is_system_admin` vs regular admin
- [ ] Update `admin_required` decorator to set these values

### 5. System Admin Dashboard
- [ ] Add student-teacher assignment interface
- [ ] Show which teacher owns which students
- [ ] Allow transferring students between teachers
- [ ] Bulk assignment tools

## UI Changes Required

### 1. Admin Dashboard
- [ ] Show teacher name on student list
- [ ] Filter students by teacher (system admin view)
- [ ] Indicate which teacher a student belongs to

### 2. Student Upload
- [ ] Teachers: Auto-assign to themselves (transparent)
- [ ] System admins: Dropdown to select teacher during upload

### 3. System Admin Dashboard
- [ ] Teacher management page showing student counts
- [ ] Student assignment interface
- [ ] Teacher selector when creating students

## Testing Requirements

### 1. Unit Tests
- [ ] Test teacher can only see their students
- [ ] Test teacher cannot access other teacher's students
- [ ] Test system admin can see all students
- [ ] Test student assignment on creation
- [ ] Test student transfer between teachers

### 2. Integration Tests
- [ ] Login as Teacher A, verify only sees their students
- [ ] Login as Teacher B, verify only sees their students
- [ ] Verify payroll only runs for teacher's students
- [ ] Verify transactions filtered correctly
- [ ] Test system admin global view

### 3. Security Tests
- [ ] Attempt to access other teacher's student by URL manipulation
- [ ] Attempt to modify other teacher's student data
- [ ] Verify authorization checks on all routes

## Migration Strategy

### Phase 1: Database Setup
1. Create migration adding `teacher_id` column (nullable initially)
2. Run migration on staging
3. Assign existing students to teachers (manual or script)
4. Make `teacher_id` NOT NULL in second migration

### Phase 2: Code Updates
1. Update Student model with relationship
2. Add helper functions for scoped queries
3. Update all student queries with teacher filtering
4. Add system admin override logic

### Phase 3: UI Updates
1. Update admin dashboard with teacher indicators
2. Add system admin assignment interface
3. Update CSV upload with auto-assignment

### Phase 4: Testing
1. Run all tests
2. Manual testing with multiple teacher accounts
3. Security testing for data isolation

### Phase 5: Deployment
1. Deploy to staging
2. Verify data isolation
3. Deploy to production
4. Monitor for issues

## Backwards Compatibility

**Breaking Changes:**
- Existing students need teacher assignment before enforcement
- Teachers will suddenly see fewer students (only theirs)
- Existing integrations/scripts may need updates

**Mitigation:**
- Add migration script to assign students fairly
- System admin retains global view
- Provide clear documentation for teachers

## Future Enhancements

### 1. Teacher Collaboration
- [ ] Allow teachers to share students (many-to-many)
- [ ] Co-teaching support
- [ ] Student transfer requests

### 2. Department/School Hierarchy
- [ ] Group teachers into departments
- [ ] Department admins can see all students in department
- [ ] School admins can see all students in school

### 3. Student Self-Selection
- [ ] Students choose their teacher during setup
- [ ] Teacher approval workflow

## Estimated Effort
- Database changes: 2-3 hours
- Code updates: 8-10 hours
- UI updates: 4-6 hours
- Testing: 4-6 hours
- Documentation: 2-3 hours
- **Total: 20-28 hours (3-4 days)**

## Priority
**Medium-High** - Important for multi-teacher deployments, but current single-teacher setups work fine.

## Dependencies
- None (standalone feature)

## Risks
- Data migration complexity for existing deployments
- Potential for data loss if teacher assignments are incorrect
- Teachers may be surprised by suddenly seeing fewer students

## Success Criteria
- [x] Teachers can only see their own students
- [x] System admins can see all students
- [x] No unauthorized access to other teachers' data
- [x] Clean migration path for existing data
- [x] All tests passing
- [x] Documentation updated
