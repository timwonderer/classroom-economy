import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. When creating student_user, set a nonce
    # Wait, the user creation is in the fixture!
    # Let's replace the fixture creation of student_user to include current_session_nonce
    content = content.replace(
        "student_user = User(username_hash=f\"auto_{student.id}\", username_lookup_hash=f\"auto_l_{student.id}\", user_role=UserRole.STUDENT)",
        "student_user = User(username_hash=f\"auto_{student.id}\", username_lookup_hash=f\"auto_l_{student.id}\", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')"
    )

    # 2. When setting sess['user_id'] = student_user.id, also set sess['current_session_nonce'] = 'test_nonce_123'
    # Wait, it could be `sess['current_session_nonce'] = student_user.current_session_nonce`
    content = re.sub(
        r"sess\['user_id'\] = student_user\.id",
        r"sess['user_id'] = student_user.id\n        sess['current_session_nonce'] = student_user.current_session_nonce",
        content
    )

    with open(filepath, 'w') as f:
        f.write(content)

