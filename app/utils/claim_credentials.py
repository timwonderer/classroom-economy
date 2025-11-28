"""Helpers for student account claim credentials.

Provides a single source of truth for how claim credentials are built
and matched, including legacy fallbacks that used the last initial
instead of the first initial.
"""

from __future__ import annotations

from typing import Optional, Tuple

from hash_utils import hash_hmac


def _normalize_initial(value: Optional[str]) -> str:
    """Return an uppercase initial or an empty string if missing."""
    if not value:
        return ""
    return value.strip().upper()[:1]


def _build_credentials(first_initial: Optional[str], last_initial: Optional[str], dob_sum: Optional[int]):
    """Generate claim credential strings with primary + legacy fallbacks."""
    if dob_sum is None:
        return []

    credentials = []
    primary_initial = _normalize_initial(first_initial)
    legacy_initial = _normalize_initial(last_initial)

    if primary_initial:
        credentials.append(f"{primary_initial}{dob_sum}")

    if legacy_initial and legacy_initial != primary_initial:
        credentials.append(f"{legacy_initial}{dob_sum}")

    return credentials


def compute_primary_claim_hash(first_initial: Optional[str], dob_sum: Optional[int], salt) -> Optional[str]:
    """Compute the canonical claim hash (first initial + DOB sum)."""
    if dob_sum is None or not salt:
        return None

    initial = _normalize_initial(first_initial)
    if not initial:
        return None

    credential = f"{initial}{dob_sum}"
    return hash_hmac(credential.encode(), salt)


def match_claim_hash(
    stored_hash: Optional[str],
    first_initial: Optional[str],
    last_initial: Optional[str],
    dob_sum: Optional[int],
    salt,
) -> Tuple[bool, bool, Optional[str]]:
    """
    Check if a stored hash matches any supported credential pattern.

    Returns a tuple of:
    - matched (bool): stored hash matches a supported credential
    - is_primary (bool): matched the canonical first-initial pattern
    - canonical_hash (str|None): hash for the canonical credential so callers can normalize data
    """
    if not stored_hash or not salt or dob_sum is None:
        return False, False, None

    credentials = _build_credentials(first_initial, last_initial, dob_sum)
    canonical_hash = None
    matched = False
    matched_primary = False

    for idx, credential in enumerate(credentials):
        current_hash = hash_hmac(credential.encode(), salt)
        if canonical_hash is None:
            canonical_hash = current_hash

        if stored_hash == current_hash:
            matched = True
            matched_primary = idx == 0

    return matched, matched_primary, canonical_hash


def normalize_claim_hash(
    stored_hash: Optional[str],
    first_initial: Optional[str],
    last_initial: Optional[str],
    dob_sum: Optional[int],
    salt,
) -> Tuple[Optional[str], bool]:
    """Return a canonical claim hash when the stored hash is legacy-compatible.

    This is a convenience wrapper around :func:`match_claim_hash` that keeps
    the stored hash intact when it is already canonical, but returns the
    canonical hash for persistence when the stored value matches a legacy
    pattern (e.g., last-initial + dob_sum).

    Returns a tuple of:
    - updated_hash: canonical hash when the stored hash matches a supported
      pattern, otherwise the original stored hash
    - changed: True when the canonical hash differs from what was stored
    """

    matched, is_primary, canonical_hash = match_claim_hash(
        stored_hash,
        first_initial,
        last_initial,
        dob_sum,
        salt,
    )

    if not matched or not canonical_hash:
        return stored_hash, False

    if stored_hash == canonical_hash:
        return stored_hash, False

    if is_primary:
        return stored_hash, False

    return canonical_hash, True
