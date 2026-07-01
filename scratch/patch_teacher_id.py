import os
import glob
import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    new_content = content
    
    # 1. Models where we RENAME teacher_id to user_id
    rename_models = ['StoreItem', 'ClassEconomy', 'RecoveryRequest']
    for model in rename_models:
        pattern = re.compile(rf'({model}\s*\([^)]*?)teacher_id=')
        while True:
            updated = pattern.sub(r'\1user_id=', new_content)
            if updated == new_content:
                break
            new_content = updated
            
    # 2. Models where we REMOVE teacher_id entirely because it's no longer used
    #    or they already have user_id (like Transaction).
    remove_models = ['Transaction', 'RentSettings', 'PayrollSettings', 'Seat', 'dict']
    for model in remove_models:
        # Match 'teacher_id=something,' or 'teacher_id=something' before ')'
        # We need to handle optional trailing comma or leading comma.
        # Let's just match `teacher_id=[^,)]+,?` and replace with empty string.
        # But wait, it might leave a dangling comma. `\s*teacher_id=[^,)]+,?\s*`
        pattern = re.compile(rf'({model}\s*\([^)]*?)\s*teacher_id=[^,)]+,?\s*')
        while True:
            updated = pattern.sub(r'\1', new_content)
            if updated == new_content:
                break
            new_content = updated

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Patched {filepath}")

for filepath in glob.glob('tests/**/*.py', recursive=True):
    patch_file(filepath)
