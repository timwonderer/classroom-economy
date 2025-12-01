# Migration Best Practices

This document outlines best practices for creating database migrations in the Classroom Economy application to ensure they are safe, idempotent, and can be run reliably in production environments.

## Core Principle: Migrations Must Be Idempotent

**Idempotent migrations** can be run multiple times without causing errors or data corruption. This is critical because:

1. Schema changes may have been applied manually in production to fix urgent issues
2. Previous migration runs may have partially completed before failing
3. The same migration may exist in multiple branches that get merged

## Required Checks Before Schema Changes

### 1. Check if Columns Exist Before Adding

Always check if a column exists before attempting to add it:

```python
def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if not column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.add_column(sa.Column('column_name', sa.Integer(), nullable=True))
        print("✅ Added column_name to table_name")
    else:
        print("⚠️  Column 'column_name' already exists on 'table_name', skipping...")
```

### 2. Check if Foreign Keys Exist Before Creating

Always check if a foreign key constraint exists before creating it:

```python
def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys


def upgrade():
    if not foreign_key_exists('table_name', 'fk_constraint_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_constraint_name', 'other_table', ['column_id'], ['id'])
        print("✅ Added foreign key constraint fk_constraint_name")
    else:
        print("⚠️  Foreign key 'fk_constraint_name' already exists, skipping...")
```

### 3. Check if Indexes Exist Before Creating

Always check if an index exists before creating it:

```python
def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    if not index_exists('table_name', 'ix_table_column'):
        op.create_index('ix_table_column', 'table_name', ['column_name'])
        print("✅ Added index ix_table_column")
    else:
        print("⚠️  Index 'ix_table_column' already exists, skipping...")
```

### 4. Check Column Nullability Before Altering

When making a column NOT NULL, check if it's currently nullable:

```python
def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Backfill NULL values first
    conn.execute(sa.text("UPDATE table_name SET column_name = default_value WHERE column_name IS NULL"))
    
    # Check if column is nullable before altering
    columns = inspector.get_columns('table_name')
    column = next((col for col in columns if col['name'] == 'column_name'), None)
    if column and column.get('nullable', True):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.alter_column('column_name', nullable=False)
        print("✅ Set column_name to NOT NULL")
    else:
        print("⚠️  Column 'column_name' is already NOT NULL, skipping...")
```

## Downgrade Functions

Downgrade functions should also be idempotent and check for existence before dropping:

```python
def downgrade():
    # Drop foreign key if it exists
    if foreign_key_exists('table_name', 'fk_constraint_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.drop_constraint('fk_constraint_name', type_='foreignkey')
        print("✅ Dropped foreign key constraint fk_constraint_name")
    else:
        print("⚠️  Foreign key 'fk_constraint_name' does not exist, skipping...")
    
    # Drop column if it exists
    if column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.drop_column('column_name')
        print("✅ Dropped column_name from table_name")
    else:
        print("⚠️  Column 'column_name' does not exist, skipping...")
```

## Logging Best Practices

Use clear, informative log messages:

- ✅ Use green checkmarks for successful operations
- ⚠️ Use warning symbols for skipped operations (already exists)
- ❌ Use red X for reversions/removals

This helps operators understand what the migration is doing and whether it's making changes or skipping already-applied changes.

## Examples of Idempotent Migrations

See these migrations for complete examples:

- `migrations/versions/1ef03001fb2a_add_teacher_id_to_store_items_for_multi_.py` - Adds column with FK
- `migrations/versions/w2x3y4z5a6b7_add_teacher_id_to_settings_tables.py` - Adds columns to multiple tables
- `migrations/versions/00212c18b0ac_add_join_code_to_transaction.py` - Adds column with indexes

## Testing Migrations

Always test migrations in the following scenarios:

1. **Fresh database**: Migration runs on a completely empty database
2. **Existing schema**: Migration runs when the schema elements already exist
3. **Partial state**: Migration runs when some but not all changes have been applied
4. **Upgrade/Downgrade cycle**: Verify that upgrade followed by downgrade followed by upgrade works correctly

See `tests/test_migration_idempotency.py` for test examples.

## Common Pitfalls to Avoid

1. ❌ **Don't** use `op.add_column()` directly without checking if column exists
2. ❌ **Don't** use `op.create_foreign_key()` without checking if FK exists
3. ❌ **Don't** use `op.create_index()` without checking if index exists
4. ❌ **Don't** assume the database is in a clean state
5. ❌ **Don't** forget to handle ENUM types and other PostgreSQL-specific features
6. ✅ **Do** always check for existence before creating schema elements
7. ✅ **Do** log clear messages about what the migration is doing
8. ✅ **Do** test migrations on a copy of production data when possible

## Migration Review Checklist

Before merging a migration PR, verify:

- [ ] All `add_column` calls check if column exists first
- [ ] All `create_foreign_key` calls check if FK exists first
- [ ] All `create_index` calls check if index exists first
- [ ] All `alter_column` calls check current state first
- [ ] Downgrade function mirrors upgrade with existence checks
- [ ] Clear log messages explain what's happening
- [ ] Migration has been tested on fresh database
- [ ] Migration has been tested with pre-existing schema
- [ ] Migration handles ENUM types correctly (PostgreSQL)
- [ ] No data loss occurs if migration is run multiple times

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Inspector API](https://docs.sqlalchemy.org/en/20/core/reflection.html)
