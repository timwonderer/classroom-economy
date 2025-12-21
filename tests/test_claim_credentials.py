
import pytest
from app.utils.claim_credentials import match_claim_hash, compute_primary_claim_hash
from hash_utils import hash_hmac, get_random_salt

def test_match_claim_hash_legacy():
    salt = get_random_salt()
    # Legacy was LastInitial + DOB
    # Credential: "L2020"
    stored_hash = hash_hmac(b"L2020", salt)

    first_initial = "F"
    last_initial = "L"
    dob_sum = 2020

    matched, is_primary, canonical = match_claim_hash(
        stored_hash, first_initial, last_initial, dob_sum, salt
    )

    assert matched is True
    assert is_primary is False
    assert canonical == hash_hmac(b"F2020", salt)

def test_match_claim_hash_primary():
    salt = get_random_salt()
    # Primary is FirstInitial + DOB
    # Credential: "F2020"
    stored_hash = hash_hmac(b"F2020", salt)

    first_initial = "F"
    last_initial = "L"
    dob_sum = 2020

    matched, is_primary, canonical = match_claim_hash(
        stored_hash, first_initial, last_initial, dob_sum, salt
    )

    assert matched is True
    assert is_primary is True
    assert canonical == stored_hash

def test_match_claim_hash_nomatch():
    salt = get_random_salt()
    stored_hash = hash_hmac(b"X2020", salt)

    first_initial = "F"
    last_initial = "L"
    dob_sum = 2020

    matched, is_primary, canonical = match_claim_hash(
        stored_hash, first_initial, last_initial, dob_sum, salt
    )

    assert matched is False
