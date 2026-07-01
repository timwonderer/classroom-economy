import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    new_content = content
    if "from app.models import" in new_content and "User" not in new_content:
        new_content = new_content.replace("from app.models import", "from app.models import User, UserRole,")

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Added imports to {filepath}")

for fp in ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']:
    patch_file(fp)

