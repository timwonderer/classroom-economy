"""Username generation for student account setup.

Production format:
    username = f"{system_word_1}-{chosen_word}-{system_word_2}{fingerprint_suffix}"

Where:
    chosen_word       — supplied by the student during the create_username step
    system_word_1/2   — two distinct words drawn from username_vocabulary.txt
    fingerprint_suffix — last two hex characters of seat.roster_fingerprint

The vocabulary is loaded once at module import and cached.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

_VOCAB_PATH = Path(__file__).parent.parent / "data" / "username_vocabulary.txt"


@lru_cache(maxsize=1)
def load_vocabulary() -> list[str]:
    """Return the full word list from username_vocabulary.txt."""
    words = [line.strip() for line in _VOCAB_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(words) < 2:
        raise RuntimeError("username_vocabulary.txt must contain at least two words")
    return words


def build_username(chosen_word: str, roster_fingerprint: str) -> str:
    """Build a canonical username from a student-chosen word and seat fingerprint.

    Args:
        chosen_word: The word the student typed in (already validated: alpha, 3-12 chars).
        roster_fingerprint: The hex string stored on Seat.roster_fingerprint.

    Returns:
        A username string of the form:
            {system_word_1}-{chosen_word}-{system_word_2}{fingerprint_suffix}

    The two system words are drawn without replacement from the vocabulary.
    The fingerprint_suffix is the last two characters of roster_fingerprint.
    """
    vocabulary = load_vocabulary()
    system_word_1, system_word_2 = random.sample(vocabulary, 2)
    fingerprint_suffix = roster_fingerprint[-2:] if roster_fingerprint else "00"
    return f"{system_word_1}-{chosen_word}-{system_word_2}{fingerprint_suffix}"


def validate_chosen_word(word: str) -> bool:
    """Return True if the word meets the student input requirements.

    Rules:
        - alphabetic only (no symbols, spaces, numbers)
        - length between 3 and 12 characters inclusive
    """
    return word.isalpha() and 3 <= len(word) <= 12
