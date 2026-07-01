import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

# Fix the broken dict(user_id...)
content = re.sub(
    r"dict\(user_id=student_user.id, teacher_id=teacher_admin.id\)\([\s\S]*?first_half_hash='scope-hash',\n        \),",
    "",
    content
)
content = re.sub(
    r"\)\(join_code='JOINCODE123', admin_id=teacher_admin.id, role=\"admin\"\)\(join_code='JOINCODE123', user_id=student_user.id, role=\"student\"\)",
    ")",
    content
)

# Fix RentSettings missing class_id
# If it has RentSettings(block='A' and NOT class_id=
content = re.sub(
    r"RentSettings\(block='A'",
    "RentSettings(class_id=admin_class_scope.class_id, block='A'",
    content
)

# And fix any RentSettings(join_code=... missing class_id
content = re.sub(
    r"RentSettings\(join_code=([^,]+),",
    r"RentSettings(class_id=\1, join_code=\1,",
    content
)
# Note: actually admin_class_scope.class_id should be used for join_code=admin_class_scope.join_code

with open(filepath, 'w') as f:
    f.write(content)

