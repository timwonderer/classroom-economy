import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace("resp = client.post('/api/purchase-item', json=data)\n    assert resp.status_code == 200", "resp = client.post('/api/purchase-item', json=data)\n    print('DEBUG_RESPONSE:', resp.status_code, resp.json)\n    assert resp.status_code == 200")

with open(filepath, 'w') as f:
    f.write(content)
