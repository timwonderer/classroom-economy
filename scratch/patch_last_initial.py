import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Replace last_initial= with last_name= INSIDE IdentityProfile(...)
    # Using regex to find IdentityProfile(..., last_initial=..., ...)
    # Because there are newlines, we use DOTALL
    def repl(m):
        inner = m.group(1)
        new_inner = re.sub(r'\blast_initial=', 'last_name=', inner)
        return f"IdentityProfile({new_inner})"
        
    new_content = re.sub(r'IdentityProfile\((.*?)\)', repl, content, flags=re.DOTALL)

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Patched IdentityProfile in {filepath}")

for fp in ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']:
    patch_file(fp)

