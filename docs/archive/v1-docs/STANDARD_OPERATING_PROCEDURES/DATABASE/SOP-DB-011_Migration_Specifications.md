# Database Migration Specifications

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-011       | 1.0     | 2026-03-01     | N/A        | Normative                 |

> [!IMPORTANT]
> This is the **Single Source of Truth** for all database migration policies, best practices, and workflows in the Classroom Economy project. All contributors must adhere to these standards.

---

## I. Purpose
To be the Single Source of Truth for all database migration policies, best practices, and workflows in the Classroom Economy project. Idempotency is strict and enforced.

## II. Scope
All Alembic migrations authored by developers modifying the application database.

## III. Authority Level
Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`

## V. The Golden Rules

1.  **NEVER modify `app/models.py` without creating a migration.**
2.  **ALWAYS test migrations before committing** (upgrade AND downgrade).
3.  **NEVER edit old migrations after they're merged to main.**
4.  **ALWAYS review auto-generated migrations** before committing.
5.  **NEVER skip migrations** - each schema change needs its own migration.
6.  **ALWAYS include idempotency helpers** in every migration (`table_exists`, `column_exists`, etc.).
7.  **NEVER use hardcoded constraint names** - discover dynamically via inspection.
8.  **ALWAYS check existence before CREATE operations** (tables, columns, indexes, foreign keys).

---

## VI. Migration Best Practices

### Core Principle: Migrations Must Be Idempotent

**Idempotent migrations** can be run multiple times without causing errors or data corruption. This is critical because:

1.  Schema changes may have been applied manually in production to fix urgent issues.
2.  Previous migration runs may have partially completed before failing.
3.  The same migration may exist in multiple branches that get merged.

### Required Idempotency Helpers

Every migration MUST include these helper functions to enable safe existence checks:

```python
def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []
```

### Usage Patterns

#### Upgrade Safety
```python
def upgrade():
    # IDEMPOTENT - Safe to run multiple times
    if not column_exists('student', 'email'):
        op.add_column('student', sa.Column('email', sa.String(length=255), nullable=True))
        print("✅ Added email column to student")
    else:
        print("⚠️  Column 'email' already exists on 'student', skipping...")
```

#### Downgrade Safety
```python
def downgrade():
    # Check before dropping
    if column_exists('student', 'email'):
        op.drop_column('student', 'email')
        print("❌ Dropped email column from student")
    else:
        print("⚠️  Column 'email' does not exist on 'student', skipping...")
```

---

## VII. Implementation Guidelines

### Migration Naming Conventions
Use descriptive names that clearly state changes:

- **Add Column:** `flask db migrate -m "Add join_code to Transaction table"`
- **Create Table:** `flask db migrate -m "Create RecoveryRequest table"`
- **Remove Column:** `flask db migrate -m "Remove deprecated field from StoreItem"`
- **Renaming:** `flask db migrate -m "Rename student_id to user_id in Transaction"`
- **Relationship:** `flask db migrate -m "Add foreign key between Student and Teacher"`

### Common Scenarios

#### 1. Adding a Required Field to Existing Table
**Problem:** Cannot add `nullable=False` to a table with existing data.
**Solution:**

1.  Add column as `nullable=True`.
2.  Backfill data (UPDATE).
3.  Alter column to `nullable=False`.

```python
def upgrade():
    # 1. Add nullable
    if not column_exists('student', 'email'):
        op.add_column('student', sa.Column('email', sa.String(255), nullable=True))
    
    # 2. Backfill
    op.execute("UPDATE student SET email = 'default@example.com' WHERE email IS NULL")
    
    # 3. Make required
    op.alter_column('student', 'email', nullable=False)
```

#### 2. Renaming a Column
```python
def upgrade():
    op.alter_column('transaction', 'student_id', new_column_name='user_id')

def downgrade():
    op.alter_column('transaction', 'user_id', new_column_name='student_id')
```

#### 3. Data Migration
When transforming existing data:
```python
def upgrade():
    op.add_column('student', sa.Column('full_name', sa.String(255)))
    
    connection = op.get_bind()
    connection.execute("""
        UPDATE student
        SET full_name = first_name || ' ' || last_initial
    """)
```

---

## VIII. Policy Standards

### Schema Change Gate
This gate is **PR‑blocking**.

**Applies when:**

- Dropping/Renaming columns or tables
- Removing/Changing Foreign Keys
- Replacing relations

**PR Classification:**

- [ ] **EXPAND** – Additive, backward-compatible
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal
- [ ] **CONTRACT (DATABASE)** – Destructive migration

### Schema Contraction Policy ("Expand and Contract")

**Phase 1: Expand (Release N)**

- New elements exist alongside legacy.
- Application supports both.
- NO destructive migrations.

**Phase 2: Contract Code (Release N+1)**

- Legacy removed from Code models.
- DB column remains.
- Application operates without legacy.

**Phase 3: Contract Database (Release N+2)**

- Migration drops legacy column/table.
- Isolated migration.

### Constraint Name Agnosticism
**Rule:** NEVER use hardcoded constraint names.
**Pattern:**
```python
from sqlalchemy import inspect
bind = op.get_bind()
inspector = inspect(bind)
for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

---

## IX. Workflows

### Standard Cycle
1.  **Sync:** `git fetch origin main && git merge origin/main`
2.  **Verify Head:** `flask db heads` (Must be 1)
3.  **Code:** Modify `app/models.py`
4.  **Generate:** `flask db migrate -m "Description"`
5.  **Review & Guard:**
    - Verify `down_revision`
    - **Add Idempotency Helpers**
    - Wrap `op` calls in existence checks
6.  **Lint:** `python scripts/lint_migrations.py`
7.  **Test:** `flask db upgrade` → `flask db downgrade` → `flask db upgrade`
8.  **Commit:** Git allowlist model and migration files

### Fixing "Multiple Heads"
1.  `flask db merge heads -m "Merge migration heads"`
2.  Review generated merge file.
3.  `flask db upgrade`
4.  Test and commit.

### Deployment Checklist
- [ ] Migrations tested locally (upgrade + downgrade)
- [ ] Idempotency verified
- [ ] Staging rehearsal complete
- [ ] Backup plan ready

---

## X. Deprecation Standards

**Registry:** `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-014_Deprecated_Symbols_Registry.md`

**Deprecated Patterns:**

- `datetime.utcnow()` → `datetime.now(datetime.UTC)`
- `Query.get()` → `db.session.get(Model, id)`

---

## XI. Resources
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Inspector API](https://docs.sqlalchemy.org/en/20/core/reflection.html)
## XII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
