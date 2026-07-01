import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace `ClassEconomy.query.first().class_id` with `class_id=ClassEconomy.query.first().class_id if ClassEconomy.query.first() else None`
# actually let's just do `print("CLASS_ID_DEBUG:", ClassEconomy.query.first().class_id)`
injection = """
    class_econ = ClassEconomy.query.first()
    print("CLASS_ID_DEBUG:", class_econ.class_id if class_econ else "NONE")
"""
content = content.replace("settings = RentSettings(", injection + "    settings = RentSettings(")

with open(filepath, 'w') as f:
    f.write(content)

