"""
Application-wide constants for Classroom Economy.

This module contains configuration constants used throughout the application,
including theme prompts for student account setup and validation rules.
"""

import re

# Period/Block Validation
PERIOD_MAX_LENGTH = 10  # Must match database column definition in Student.block and DeletionRequest.period
PERIOD_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_]+$')  # Alphanumeric, spaces, hyphens, underscores

THEME_PROMPTS = [
    {"slug": "animal", "prompt": "Write in your favorite animal."},
    {"slug": "color", "prompt": "Write in your favorite color."},
    {"slug": "space", "prompt": "Write in something related to outer space."},
    {"slug": "nature", "prompt": "Write in a nature word (tree, river, etc.)."},
    {"slug": "food", "prompt": "Write in your favorite fruit or food."},
    {"slug": "trait", "prompt": "Write in a positive character trait (bravery, kindness, etc.)."},
    {"slug": "place", "prompt": "Write in a place you want to visit."},
    {"slug": "science", "prompt": "Write in a science word you like."},
    {"slug": "hobby", "prompt": "Write in your favorite hobby or sport."},
    {"slug": "happy", "prompt": "Write in something that makes you happy."},
]
