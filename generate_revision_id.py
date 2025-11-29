#!/usr/bin/env python3
"""Generate a unique revision ID for migrations."""

import hashlib
import time

def generate_revision_id():
    """Generate a unique 12-character revision ID similar to Alembic's format."""
    # Use timestamp and a random component for uniqueness
    timestamp = str(time.time()).encode('utf-8')
    hash_obj = hashlib.sha256(timestamp)
    revision_id = hash_obj.hexdigest()[:12]
    return revision_id

if __name__ == '__main__':
    new_id = generate_revision_id()
    print(new_id)
