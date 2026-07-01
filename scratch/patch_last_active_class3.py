import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the block where we set last_active_class_id
    def patch_db_update(match):
        indent = match.group(1)
        return f"""{indent}seat = Seat.query.filter_by(user_id=student_user.id).first()
{indent}db.session.execute(db.text("UPDATE users SET last_active_class_id = :cid, last_active_seat_id = :sid WHERE id = :uid"), {{'cid': seat.class_id, 'sid': seat.id, 'uid': student_user.id}})
{indent}db.session.commit()
{indent}with client.session_transaction() as sess:"""

    # We need to replace the old patch.
    # The old patch had:
    # student_user.last_active_class_id = ...
    # student_user.last_active_seat_id = ...
    # db.session.commit()
    # with client.session_transaction() as sess:
    
    # I will just write a regex to replace everything from `seat = Seat.query...` to `with client.session_transaction() as sess:`
    content = re.sub(
        r'(\s*)seat = Seat\.query.*?\n\s*student_user\.last_active_class_id = .*?\n\s*student_user\.last_active_seat_id = .*?\n\s*db\.session\.commit\(\)\n\s*with client\.session_transaction\(\) as sess:',
        patch_db_update,
        content,
        flags=re.DOTALL
    )

    with open(filepath, 'w') as f:
        f.write(content)

