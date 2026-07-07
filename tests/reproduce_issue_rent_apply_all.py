import pytest
from app.models import RentSettings, RentItem, Seat, IdentityProfile

@pytest.fixture
def teacher_with_classes(client):
    """Create a teacher with two classes."""
    from app.models import User, UserRole, Admin
    from app import db
    
    # Create teacher
    teacher = Admin(
        username="test_teacher",
        totp_secret="base32secret3232"
    )
    db.session.add(teacher)
    db.session.commit()
    
    # Create two classes (blocks)
    # TODO: block_a needs class_id set from the ClassEconomy for join_code JOIN_A
    block_a = Seat(block="BlockA", block_identifier="BlockA", role="student")
    db.session.add(block_a)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=block_a.id, profile_type='student_unclaimed', first_name="P", last_name="P"))
    # TODO: block_b needs class_id set from the ClassEconomy for join_code JOIN_B
    block_b = Seat(block="BlockB", block_identifier="BlockB", role="student")
    db.session.add(block_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=block_b.id, profile_type='student_unclaimed', first_name="P", last_name="P"))
    db.session.add_all([block_a, block_b])
    db.session.commit()
    
    return teacher

def test_rent_items_apply_to_all(client, teacher_with_classes):
    """Test that rent items are applied to all classes when 'apply_to_all' is checked."""
    from app.models import RentSettings, RentItem, Seat, IdentityProfile
    from app import db
    
    # Log in as teacher
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_with_classes.id
        sess['is_admin'] = True
        from datetime import datetime, timezone
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['_fresh'] = True
        
    # Define form data for BlockA with apply_to_all=True and one rent item
    data = {
        'settings_block': 'BlockA',
        'apply_to_all': 'true',
        'is_enabled': 'on',
        'rent_amount': '100.0',
        'frequency_type': 'monthly',
        'rent_item_id_0': '', # New item
        'rent_item_name_0': 'Test Item',
        'rent_item_description_0': 'Description',
        'rent_item_store_available_0': 'on',
        'rent_item_store_price_0': '50.0',
        'rent_item_purchase_duration_0': 'per_use'
    }
    
    # helper to add CSRF token would be needed in full integration test, 
    # but here we rely on test_client bypassing CSRF if configured or us manually disabling it if needed.
    # checking if CSRF is enabled in config. usually WTForms in flask requires it.
    # Assuming test config disables CSRF or we ignore if it fails on that.
    # Let's try simple post first.
    
    resp = client.post('/admin/rent-settings', data=data, follow_redirects=True)
    assert resp.status_code == 200
    
    # Verify RentSettings were created for both blocks
    settings_a = RentSettings.query.filter_by(teacher_id=teacher_with_classes.id, block='BlockA').first()
    settings_b = RentSettings.query.filter_by(teacher_id=teacher_with_classes.id, block='BlockB').first()

    assert settings_a is not None
    assert settings_b is not None
    assert settings_b.rent_amount == 100.0
    
    # Verify RentItems for BlockA (Should exist)
    items_a = RentItem.query.filter_by(rent_setting_id=settings_a.id).all()
    assert len(items_a) == 1
    assert items_a[0].name == 'Test Item'
    
    # Verify RentItems for BlockB (Should exist if bug is fixed, Fail if bug exists)
    items_b = RentItem.query.filter_by(rent_setting_id=settings_b.id).all()
    
    # This assertion fails if the bug is present
    assert len(items_b) == 1, "Rent items were not applied to BlockB!"
    assert items_b[0].name == 'Test Item'
