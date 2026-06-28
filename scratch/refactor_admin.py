import re

with open('app/routes/admin.py', 'r') as f:
    content = f.read()

# Replace session.get('admin_id') and session.get("admin_id") with g.canonical_context.user_id
content = re.sub(r'session\.get\([\'"]admin_id[\'"]\)', 'g.canonical_context.user_id', content)

# Remove current_admin = get_current_admin() and replace it with ctx logic if needed?
# Actually, let's just do session.get('admin_id') first.
with open('app/routes/admin.py', 'w') as f:
    f.write(content)
