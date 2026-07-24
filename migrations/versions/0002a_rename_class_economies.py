"""Rename class_economies to classes

Revision ID: 0002a
Revises: 0001
Create Date: 2026-04-29

Renames the `class_economies` table to `classes` (aligning the physical
schema with the ORM model that already declares __tablename__ = 'classes').

Steps performed by upgrade():
  1. Drop the canonical-stub `classes` table created by the bootstrap
     migration (it is a schema-only placeholder with no FKs or data).
  2. Drop all FK constraints on child tables that reference
     `class_economies.class_id`.
  3. Rename the table itself.
  4. Rename indexes that carry the old table name.
  5. Recreate every FK constraint pointing at the new table name,
     preserving the original ondelete behaviour.

downgrade() reverses every step.
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------
revision = "0002a"
down_revision = "0001"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Defensive introspection helpers  (borrowed style from 0001_bootstrap.py)
# ---------------------------------------------------------------------------

def _inspector():
    return sa.inspect(op.get_bind())


def table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def index_exists(table: str, index_name: str) -> bool:
    try:
        return index_name in [i["name"] for i in _inspector().get_indexes(table)]
    except Exception:
        return False


def foreign_key_exists(table: str, fk_name: str) -> bool:
    try:
        return fk_name in [fk["name"] for fk in _inspector().get_foreign_keys(table)]
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FK catalogue
#
# Every entry describes one FK that references class_economies.class_id.
# Format per entry:
#   (child_table, fk_name_old, fk_name_new, col, ondelete)
#
# fk_name_old  – the constraint name in the DB right now (on class_economies)
# fk_name_new  – the constraint name after the rename (references 'classes')
#
# Both names are kept so that downgrade() can recreate the originals.
# ---------------------------------------------------------------------------

FK_CATALOGUE = [
    # (child_table, old_fk_name, new_fk_name, local_col, ondelete)
    ("actor_request_trace",   "fk_actor_request_trace_class_id_class_economies",   "fk_actor_request_trace_class_id_classes",   "class_id", "SET NULL"),
    ("analytics_alerts",      "analytics_alerts_class_id_fkey",                    "fk_analytics_alerts_class_id_classes",       "class_id", "CASCADE"),
    ("analytics_events",      "analytics_events_class_id_fkey",                    "fk_analytics_events_class_id_classes",       "class_id", "CASCADE"),
    ("analytics_snapshots",   "analytics_snapshots_class_id_fkey",                 "fk_analytics_snapshots_class_id_classes",    "class_id", "CASCADE"),
    ("announcements",         "announcements_class_id_fkey",                       "fk_announcements_class_id_classes",          "class_id", "CASCADE"),
    ("balance_cache",         "balance_cache_class_id_fkey",                       "fk_balance_cache_class_id_classes",          "class_id", "CASCADE"),
    ("banking_settings",      "fk_banking_settings_class_id_class_economies",      "fk_banking_settings_class_id_classes",       "class_id", "CASCADE"),
    ("class_features",        "class_features_class_id_fkey",                      "fk_class_features_class_id_classes",         "class_id", "CASCADE"),
    ("class_memberships",     "class_memberships_class_id_fkey",                   "fk_class_memberships_class_id_classes",      "class_id", "CASCADE"),
    ("economy_snapshot",      "economy_snapshot_class_id_fkey",                    "fk_economy_snapshot_class_id_classes",       "class_id", "CASCADE"),
    ("error_events",          "fk_error_events_class_id_class_economies",          "fk_error_events_class_id_classes",           "class_id", "SET NULL"),
    ("feature_settings",      "fk_feature_settings_class_id_class_economies",      "fk_feature_settings_class_id_classes",       "class_id", "CASCADE"),
    ("hall_pass_logs",        "hall_pass_logs_class_id_fkey",                      "fk_hall_pass_logs_class_id_classes",         "class_id", "CASCADE"),
    ("hall_pass_settings",    "fk_hall_pass_settings_class_id_class_economies",    "fk_hall_pass_settings_class_id_classes",     "class_id", "CASCADE"),
    ("insurance_claims",      "insurance_claims_class_id_fkey",                    "fk_insurance_claims_class_id_classes",       "class_id", "CASCADE"),
    ("insurance_policies",    "fk_insurance_policies_class_id_class_economies",    "fk_insurance_policies_class_id_classes",     "class_id", "CASCADE"),
    ("insurance_policy_blocks","insurance_policy_blocks_class_id_fkey",            "fk_insurance_policy_blocks_class_id_classes","class_id", "CASCADE"),
    ("issue_resolution_actions","issue_resolution_actions_class_id_fkey",          "fk_issue_resolution_actions_class_id_classes","class_id","CASCADE"),
    ("issue_status_history",  "issue_status_history_class_id_fkey",                "fk_issue_status_history_class_id_classes",   "class_id", "CASCADE"),
    ("issues",                "issues_class_id_fkey",                              "fk_issues_class_id_classes",                 "class_id", "CASCADE"),
    ("payroll_cache",         "fk_payroll_cache_class_id_class_economies",         "fk_payroll_cache_class_id_classes",          "class_id", "CASCADE"),
    ("payroll_fines",         "payroll_fines_class_id_fkey",                       "fk_payroll_fines_class_id_classes",          "class_id", "CASCADE"),
    ("payroll_rewards",       "payroll_rewards_class_id_fkey",                     "fk_payroll_rewards_class_id_classes",        "class_id", "CASCADE"),
    ("payroll_settings",      "fk_payroll_settings_class_id_class_economies",      "fk_payroll_settings_class_id_classes",       "class_id", "CASCADE"),
    ("redemption_audit_logs", "redemption_audit_logs_class_id_fkey",               "fk_redemption_audit_logs_class_id_classes",  "class_id", "CASCADE"),
    ("rent_items",            "fk_rent_items_class_id_class_economies",            "fk_rent_items_class_id_classes",             "class_id", "CASCADE"),
    ("rent_payments",         "rent_payments_class_id_fkey",                       "fk_rent_payments_class_id_classes",          "class_id", "CASCADE"),
    ("rent_settings",         "fk_rent_settings_class_id_class_economies",         "fk_rent_settings_class_id_classes",          "class_id", "CASCADE"),
    ("rent_waivers",          "rent_waivers_class_id_fkey",                        "fk_rent_waivers_class_id_classes",           "class_id", "CASCADE"),
    ("seats",                 "seats_class_id_fkey",                               "fk_seats_class_id_classes",                  "class_id", "CASCADE"),
    ("store_item_blocks",     "store_item_blocks_class_id_fkey",                   "fk_store_item_blocks_class_id_classes",      "class_id", "CASCADE"),
    ("store_items",           "fk_store_items_class_id_class_economies",           "fk_store_items_class_id_classes",            "class_id", "CASCADE"),
    ("student_blocks",        "student_blocks_class_id_fkey",                      "fk_student_blocks_class_id_classes",         "class_id", "CASCADE"),
    ("student_insurance",     "student_insurance_class_id_fkey",                   "fk_student_insurance_class_id_classes",      "class_id", "CASCADE"),
    ("student_items",         "student_items_class_id_fkey",                       "fk_student_items_class_id_classes",          "class_id", "CASCADE"),
    ("student_teachers",      "student_teachers_class_id_fkey",                    "fk_student_teachers_class_id_classes",       "class_id", "CASCADE"),
    ("students",              "fk_students_class_id_class_economies",              "fk_students_class_id_classes",               "class_id", "CASCADE"),
    ("tap_events",            "tap_events_class_id_fkey",                          "fk_tap_events_class_id_classes",             "class_id", "CASCADE"),
    ("teacher_blocks",        "fk_teacher_blocks_class_id_class_economies",        "fk_teacher_blocks_class_id_classes",         "class_id", "CASCADE"),
    ("ticket_correlation_pack","fk_ticket_correlation_pack_class_id_class_economies","fk_ticket_correlation_pack_class_id_classes","class_id","SET NULL"),
    ("transaction",           "fk_transaction_class_id_class_economies",           "fk_transaction_class_id_classes",            "class_id", "CASCADE"),
    ("user_reports",          "user_reports_class_id_fkey",                        "fk_user_reports_class_id_classes",           "class_id", "CASCADE"),
]

# Index renames: (old_name, new_name, table_after_rename)
# These are the indexes whose names embed "class_economies".
INDEX_RENAMES = [
    ("ix_class_economies_join_code",   "ix_classes_join_code",   "classes"),
    ("ix_class_economies_teacher_id",  "ix_classes_teacher_id",  "classes"),
    ("ix_class_economies_created_by",  "ix_classes_created_by",  "classes"),
    # uq_class_economies_class_id is a UNIQUE CONSTRAINT backed index;
    # rename separately to avoid confusion.
    ("uq_class_economies_class_id",    "uq_classes_class_id",    "classes"),
]


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade():
    bind = op.get_bind()

    # Fresh squash-bootstrap databases are built from live runtime metadata.
    # Once ClassEconomy declares __tablename__ = "classes", 0001 creates the
    # fully referenced target table directly and there is nothing to rename.
    if table_exists("classes") and not table_exists("class_economies"):
        return

    # ------------------------------------------------------------------ #
    # Step 0: drop the canonical-stub `classes` table that was created by  #
    # the bootstrap migration (Class_ placeholder in the canonical docs). #
    # It has no FKs pointing at it and no data; safe to drop.             #
    # ------------------------------------------------------------------ #
    if table_exists("classes"):
        # Verify it really is the empty stub (no FKs referencing it)
        fks_referencing_classes = [
            fk
            for tbl in _inspector().get_table_names()
            for fk in _inspector().get_foreign_keys(tbl)
            if fk.get("referred_table") == "classes"
        ]
        if fks_referencing_classes:
            raise RuntimeError(
                "Cannot drop existing 'classes' table: it has FK references. "
                "Inspect the schema manually before re-running this migration."
            )
        op.drop_table("classes")

    # ------------------------------------------------------------------ #
    # Step 1: drop all FK constraints on child tables that point at        #
    # class_economies.class_id (they will be recreated in step 3).        #
    # ------------------------------------------------------------------ #
    for child_table, old_fk, _new_fk, _col, _ondelete in FK_CATALOGUE:
        if not table_exists(child_table):
            continue
        if foreign_key_exists(child_table, old_fk):
            op.drop_constraint(old_fk, child_table, type_="foreignkey")

    # ------------------------------------------------------------------ #
    # Step 2: rename the table.                                            #
    # ------------------------------------------------------------------ #
    if table_exists("class_economies") and not table_exists("classes"):
        op.rename_table("class_economies", "classes")

    # ------------------------------------------------------------------ #
    # Step 3: rename indexes.                                              #
    # ------------------------------------------------------------------ #
    for old_idx, new_idx, table in INDEX_RENAMES:
        # After rename the indexes live on 'classes' but Postgres tracks
        # index names globally – pass the post-rename table name.
        if index_exists(table, old_idx):
            op.execute(f'ALTER INDEX "{old_idx}" RENAME TO "{new_idx}"')

    # ------------------------------------------------------------------ #
    # Step 4: recreate FK constraints pointing at the renamed table.       #
    # ------------------------------------------------------------------ #
    for child_table, _old_fk, new_fk, col, ondelete in FK_CATALOGUE:
        if not table_exists(child_table):
            continue
        if not foreign_key_exists(child_table, new_fk):
            op.create_foreign_key(
                new_fk,
                child_table,
                "classes",
                [col],
                ["class_id"],
                ondelete=ondelete,
            )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade():
    # ------------------------------------------------------------------ #
    # Step 1: drop the new FK constraints.                                 #
    # ------------------------------------------------------------------ #
    for child_table, _old_fk, new_fk, _col, _ondelete in FK_CATALOGUE:
        if not table_exists(child_table):
            continue
        if foreign_key_exists(child_table, new_fk):
            op.drop_constraint(new_fk, child_table, type_="foreignkey")

    # ------------------------------------------------------------------ #
    # Step 2: rename indexes back.                                         #
    # ------------------------------------------------------------------ #
    # After downgrade the table is called 'class_economies' again, but the
    # indexes are still globally named; use the intermediate table name.
    for old_idx, new_idx, _table in INDEX_RENAMES:
        if index_exists("class_economies", new_idx) or index_exists("classes", new_idx):
            op.execute(f'ALTER INDEX "{new_idx}" RENAME TO "{old_idx}"')

    # ------------------------------------------------------------------ #
    # Step 3: rename table back.                                           #
    # ------------------------------------------------------------------ #
    if table_exists("classes") and not table_exists("class_economies"):
        op.rename_table("classes", "class_economies")

    # ------------------------------------------------------------------ #
    # Step 4: recreate the original FK constraints.                        #
    # ------------------------------------------------------------------ #
    for child_table, old_fk, _new_fk, col, ondelete in FK_CATALOGUE:
        if not table_exists(child_table):
            continue
        if not foreign_key_exists(child_table, old_fk):
            op.create_foreign_key(
                old_fk,
                child_table,
                "class_economies",
                [col],
                ["class_id"],
                ondelete=ondelete,
            )

    # ------------------------------------------------------------------ #
    # Step 5: recreate the canonical-stub `classes` table that was dropped  #
    # during upgrade (mirrors the canonical Class_ mapping).              #
    # ------------------------------------------------------------------ #
    if not table_exists("classes"):
        op.create_table(
            "classes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("class_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        if not index_exists("classes", "ix_classes_class_id"):
            op.create_index("ix_classes_class_id", "classes", ["class_id"], unique=True)
