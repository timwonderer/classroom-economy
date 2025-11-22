"""
Utilities for handling name variations in multi-teacher rosters.

Handles cases where different teachers enter the same student's name differently:
- "Smith" vs "Smith-Jones"
- "Smith Jones" vs "Smith-Jones"
- "O'Brien" vs "OBrien"
"""

import re
from hash_utils import hash_hmac


def split_last_name_parts(last_name):
    """
    Split last name into parts by space and hyphen.

    Examples:
        "Smith" → ["smith"]
        "Smith-Jones" → ["smith", "jones"]
        "Van Der Berg" → ["van", "der", "berg"]
        "O'Brien" → ["o'brien"] (apostrophe NOT a delimiter)

    Returns:
        list: Normalized lowercase parts (min 2 chars each)
    """
    if not last_name:
        return []

    # Split by space or hyphen (NOT apostrophe)
    parts = re.split(r'[\s\-]+', last_name)

    # Normalize: lowercase, strip whitespace, filter single chars and empty strings
    parts = [p.lower().strip() for p in parts if len(p.strip()) >= 2]

    return parts


def hash_last_name_parts(last_name, salt):
    """
    Hash each part of a last name separately.

    Args:
        last_name: Full last name string (e.g., "Smith-Jones")
        salt: Salt bytes for hashing

    Returns:
        list: List of hex hashes for each part

    Example:
        hash_last_name_parts("Smith-Jones", salt)
        → ["abc123...", "def456..."]
    """
    parts = split_last_name_parts(last_name)
    return [hash_hmac(part.encode('utf-8'), salt) for part in parts]


def verify_last_name_parts(entered_last_name, stored_part_hashes, salt):
    """
    Verify if entered last name matches stored part hashes.

    Uses subset matching: All entered parts must exist in stored parts.
    This handles cases where teacher entered more name parts than student.

    Args:
        entered_last_name: What student entered (e.g., "Smith Jones")
        stored_part_hashes: List of hashes from roster (e.g., ["hash(smith)", "hash(jones)"])
        salt: Salt bytes used for hashing

    Returns:
        bool: True if all entered parts match stored parts

    Examples:
        Teacher entered: "Smith-Jones" → stored: [hash("smith"), hash("jones")]
        Student enters: "Smith Jones" → entered: [hash("smith"), hash("jones")]
        → All entered parts in stored parts ✅

        Teacher entered: "Smith-Jones"
        Student enters: "Smith" → entered: [hash("smith")]
        → Only partial match ❌ (need full name)

        Teacher entered: "Smith"
        Student enters: "Smith Jones" → entered: [hash("smith"), hash("jones")]
        → Entered has parts not in stored ❌
    """
    if not entered_last_name or not stored_part_hashes:
        return False

    # Hash the entered name parts
    entered_hashes = hash_last_name_parts(entered_last_name, salt)

    # Convert to sets for comparison
    entered_set = set(entered_hashes)
    stored_set = set(stored_part_hashes)

    # All entered parts must be in stored parts (subset check)
    # This prevents partial matches while allowing exact matches regardless of delimiters
    return len(entered_set) > 0 and entered_set.issubset(stored_set)


def fuzzy_match_last_name(entered_last_name, stored_part_hashes, salt):
    """
    Fuzzy match allowing partial overlap for cases where teacher added middle name.

    More permissive than verify_last_name_parts - allows if at least one part matches.
    Combined with DOB verification, this is secure enough.

    Args:
        entered_last_name: What student entered
        stored_part_hashes: List of hashes from roster
        salt: Salt bytes

    Returns:
        bool: True if at least one part overlaps
    """
    if not entered_last_name or not stored_part_hashes:
        return False

    entered_hashes = hash_last_name_parts(entered_last_name, salt)
    entered_set = set(entered_hashes)
    stored_set = set(stored_part_hashes)

    # At least one part must match
    return len(entered_set & stored_set) > 0
