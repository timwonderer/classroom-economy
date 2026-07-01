import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Remove created_by_admin_id=...
    new_content = re.sub(r'created_by_admin_id=[a-zA-Z0-9_]+\.id,? *', '', content)
    new_content = re.sub(r'created_by_admin_id=[a-zA-Z0-9_]+,? *', '', new_content)
    
    # Also I need to remove ClassEconomy teacher_id if any was missed
    new_content = re.sub(r'(ClassEconomy\s*\([^)]*?)\s*teacher_id=[^,)]+,?\s*', r'\1', new_content)

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Patched created_by_admin_id in {filepath}")

for fp in ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']:
    patch_file(fp)

