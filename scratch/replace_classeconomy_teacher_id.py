import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # We want to replace things like ClassEconomy(..., teacher_id=..., ...)
    # But also we need to catch places where it's economy.teacher_id or ClassEconomy.user_id
    
    # 1. Replace ClassEconomy.user_id -> ClassEconomy.user_id
    new_content = re.sub(r'ClassEconomy\.teacher_id', r'ClassEconomy.user_id', content)
    
    # 2. Replace kwargs in ClassEconomy(teacher_id=...) -> ClassEconomy(user_id=...)
    # This might be on a separate line if formatted.
    # It's safer to just look for teacher_id in contexts related to classes.
    # But let's start with test helpers.
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        return True
    return False

# Walk through all python files
modified_files = []
for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            if process_file(os.path.join(root, file)):
                modified_files.append(os.path.join(root, file))

print(f"Modified files: {modified_files}")
