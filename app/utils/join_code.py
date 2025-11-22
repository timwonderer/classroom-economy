"""
Utilities for generating and validating join codes for classroom periods.

Join codes are short, easy-to-type codes that students use to claim their account
in a specific teacher's period.
"""

import secrets
import string


def generate_join_code(length=6):
    """
    Generate a random join code for a classroom period.

    Uses uppercase letters and digits, excluding ambiguous characters (0, O, I, 1, l).
    Length defaults to 6 characters for easy typing while maintaining security.

    Examples:
        "A7K2M9"
        "P3XW8R"

    Args:
        length: Length of the join code (default 6)

    Returns:
        str: Randomly generated join code
    """
    # Exclude ambiguous characters: 0/O, 1/I/l
    alphabet = string.ascii_uppercase.replace('O', '').replace('I', '')  # Remove O and I
    digits = string.digits.replace('0', '').replace('1', '')  # Remove 0 and 1
    charset = alphabet + digits

    return ''.join(secrets.choice(charset) for _ in range(length))


def format_join_code(code):
    """
    Format a join code for display with consistent styling.

    Converts to uppercase and removes whitespace.

    Args:
        code: Raw join code input

    Returns:
        str: Formatted join code
    """
    if not code:
        return ""
    return code.upper().strip()


def is_valid_join_code_format(code):
    """
    Check if a join code has valid format (alphanumeric, correct length).

    Does NOT check if the code exists in database - just validates format.

    Args:
        code: Join code to validate

    Returns:
        bool: True if format is valid
    """
    if not code or not isinstance(code, str):
        return False

    code = code.strip()

    # Check length (6 characters)
    if len(code) != 6:
        return False

    # Check only contains alphanumeric (no special chars)
    if not code.isalnum():
        return False

    return True
