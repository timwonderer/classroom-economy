import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Find where student_user is created, and inject last_active_class_id and last_active_seat_id
    # The string looks like: student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
    
    # We should add `last_active_class_id=class_econ.class_id, last_active_seat_id=seat.id` but class_econ and seat might not be defined right before user!
    # Wait, in the test fixtures, `student_user = User(...)` is usually defined before `store_item`. But maybe we can just do:
    # student_user.last_active_class_id = ClassEconomy.query.first().class_id
    # student_user.last_active_seat_id = Seat.query.filter_by(user_id=student_user.id).first().id
    
    # Let's just find `db.session.add(store_item)` or `db.session.flush()` and append it there?
    # Or find `sess['user_id'] = student_user.id` and just above it, put:
    # student_user.last_active_class_id = ClassEconomy.query.first().class_id
    # student_user.last_active_seat_id = Seat.query.filter_by(user_id=student_user.id).first().id
    # db.session.commit()
    
    def patch_session(match):
        indent = match.group(1)
        injection = f"""{indent}student_user.last_active_class_id = ClassEconomy.query.first().class_id
{indent}student_user.last_active_seat_id = Seat.query.filter_by(user_id=student_user.id).first().id
{indent}db.session.commit()
{indent}with client.session_transaction() as sess:"""
        return injection
    
    content = re.sub(r'(\s*)with client\.session_transaction\(\) as sess:', patch_session, content)
    
    with open(filepath, 'w') as f:
        f.write(content)

