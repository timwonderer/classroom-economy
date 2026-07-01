import pytest
pytest.skip('Legacy TeacherBlock test', allow_module_level=True)
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, ClassEconomy, ClassMembership, StoreItem, StoreItemBlock, Seat
from app.scheduled_tasks import database_maintenance_job


def _admin(username="teacher"):
    admin = make_admin(username, "test-secret")
    db.session.add(admin)
    db.session.flush()
    return admin


def _teacher_block(teacher_id, block="A", join_code="JOINA"):
    tb = TeacherBlock(
        teacher_id=teacher_id,
        block=block,
        class_label=block,
        first_name="Seat",
        last_initial="S",
        last_name_hash_by_part=["hash"],
        dob_sum_hash=None,
        salt=b"0123456789abcdef",
        first_half_hash=f"hash-{teacher_id}-{block}",
        join_code=join_code,
        is_claimed=False,
    )
    db.session.add(tb)
    return tb


def test_database_maintenance_bulk_cleans_only_orphaned_store_item_blocks(app):
    with app.app_context():
        admin = _admin()
        db.session.flush()
        class_economy = ClassEconomy(
            join_code="JOINA",
            user_id=admin.id,
            status="active",
            created_by_admin_id=admin.id,
        )
        db.session.add(class_economy)
        db.session.flush()
        db.session.add(ClassMembership(join_code="JOINA", admin_id=admin.id, role="admin"))

        valid_item = StoreItem(user_id=admin.id, class_id=class_economy.class_id, join_code="JOINA", name="Valid", price=1, item_type="delayed")
        orphan_item = StoreItem(user_id=admin.id, class_id=class_economy.class_id, join_code="JOINA", name="Orphan", price=2, item_type="delayed")
        db.session.add_all([valid_item, orphan_item])
        db.session.flush()

        _teacher_block(admin.id, block="A", join_code="JOINA")
        db.session.add_all([
            StoreItemBlock(store_item_id=valid_item.id, block="A"),
            StoreItemBlock(store_item_id=orphan_item.id, block="B"),
        ])
        db.session.commit()

        database_maintenance_job()

        remaining_blocks = {
            (row.store_item_id, row.block)
            for row in StoreItemBlock.query.order_by(StoreItemBlock.store_item_id).all()
        }

        assert (valid_item.id, "A") in remaining_blocks
        assert (orphan_item.id, "B") not in remaining_blocks
