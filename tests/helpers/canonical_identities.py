"""
Canonical Test Universe

This file defines the canonical input data used throughout the test suite.
It implements TEST-IDEN-001: Canonical Test Identities.

This file intentionally defines only production INPUTS — the data a teacher
supplies at roster upload time, plus preset credentials for deterministic test setup.

It must never define:
- User
- Seat
- IdentityProfile
- Session
- Claim
- Authentication state

Those are created exclusively through production FEATs.

Username generation (new format):
  username = f"{system_word_1}-{chosen_word}-{system_word_2}{fingerprint_suffix}"

  - chosen_word  : supplied by the student at claim time; preset here for test determinism
  - system_word_1/2 : drawn from username_vocabulary.txt by production code
  - fingerprint_suffix : last two hex digits of seat.roster_fingerprint

Only chosen_word is a canonical input. The rest is computed by production code.
"""

TEACHERS = {
    "teacher_alice": {
        "username": "teacher.alice",
    },
    "teacher_brian": {
        "username": "teacher.brian",
    },
    "teacher_carmen": {
        "username": "teacher.carmen",
    },
    "teacher_daniel": {
        "username": "teacher.daniel",
    },
}

CLASSROOMS = {
    # Scenario A / B — Standard classroom, unique names; Ava Chen and Noah Patel also appear
    # in ap_csp_p3 (same teacher, different class) — tests multi-class identity binding.
    "chemistry_p1": {
        "teacher": "teacher_alice",
        "display_name": "Chemistry",
        "section": "Period 1",
        "roster": [
            {
                "first_name": "Ava",
                "last_name": "Chen",
                "teacher_note": "Excellent lab partner",
                "chosen_word": "spark",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Noah",
                "last_name": "Patel",
                "teacher_note": "Soccer",
                "chosen_word": "river",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Mia",
                "last_name": "Garcia",
                "teacher_note": "Absent first week",
                "chosen_word": "cloud",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Lucas",
                "last_name": "Kim",
                "teacher_note": "Needs Chromebook",
                "chosen_word": "frost",
                "pin": "1234",
                "passphrase": "testpass",
            },
        ],
    },

    # Scenario A / B — Standard classroom; Ava Chen and Noah Patel appear in chemistry_p1 too.
    # No identity relationship is implied — the fixture makes no assumption about whether
    # these are the same person or two independent users.
    "ap_csp_p3": {
        "teacher": "teacher_alice",
        "display_name": "AP CSP",
        "section": "Period 3",
        "roster": [
            {
                "first_name": "Ava",
                "last_name": "Chen",
                "teacher_note": "Always finishes early",
                "chosen_word": "maple",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Noah",
                "last_name": "Patel",
                "teacher_note": "Great debugger",
                "chosen_word": "stone",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Ethan",
                "last_name": "Martinez",
                "teacher_note": "Robotics Club",
                "chosen_word": "forge",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Sophia",
                "last_name": "Nguyen",
                "teacher_note": "Peer tutor",
                "chosen_word": "bloom",
                "pin": "1234",
                "passphrase": "testpass",
            },
        ],
    },

    # Scenario D — Cross-teacher: Ava Chen appears here under teacher_brian, also in
    # chemistry_p1 under teacher_alice. Tests cross-teacher isolation and ownership boundaries.
    "biology_block_a": {
        "teacher": "teacher_brian",
        "display_name": "Biology",
        "section": "Block A",
        "roster": [
            {
                "first_name": "Ava",
                "last_name": "Chen",
                "teacher_note": "Transferred in",
                "chosen_word": "cedar",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Jordan",
                "last_name": "Kim",
                "teacher_note": "Chess Club",
                "chosen_word": "knight",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Emma",
                "last_name": "Davis",
                "teacher_note": "Needs glasses",
                "chosen_word": "prism",
                "pin": "1234",
                "passphrase": "testpass",
            },
        ],
    },

    # Scenario C — Duplicate names within one class. Teacher notes are the disambiguation
    # signal. Dedupe codes are required during the claim flow for these students.
    "duplicate_names": {
        "teacher": "teacher_carmen",
        "display_name": "Physics",
        "section": "Period 5",
        "roster": [
            {
                "first_name": "Alex",
                "last_name": "Lee",
                "teacher_note": "Basketball",
                "chosen_word": "dunk",
                "pin": "1234",
                "passphrase": "testpass",
                "dedupe_code": "BBALL",
            },
            {
                "first_name": "Alex",
                "last_name": "Lee",
                "teacher_note": "Glasses",
                "chosen_word": "lens",
                "pin": "1234",
                "passphrase": "testpass",
                "dedupe_code": "GLASS",
            },
            {
                "first_name": "Jordan",
                "last_name": "Kim",
                "teacher_note": "Twin A",
                "chosen_word": "alpha",
                "pin": "1234",
                "passphrase": "testpass",
                "dedupe_code": "TWINA",
            },
            {
                "first_name": "Jordan",
                "last_name": "Kim",
                "teacher_note": "Twin B",
                "chosen_word": "bravo",
                "pin": "1234",
                "passphrase": "testpass",
                "dedupe_code": "TWINB",
            },
        ],
    },

    # Scenario E — Unicode: apostrophes, hyphens, accented characters, international names.
    # Tests encoding correctness through hashing and rendering.
    "unicode": {
        "teacher": "teacher_daniel",
        "display_name": "World History",
        "section": "Period 2",
        "roster": [
            {
                "first_name": "Ana María",
                "last_name": "Soto",
                "teacher_note": "Spanish Club",
                "chosen_word": "fiesta",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Jean-Luc",
                "last_name": "Martin",
                "teacher_note": "Exchange Student",
                "chosen_word": "voyage",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Chloë",
                "last_name": "O'Connor",
                "teacher_note": "Drama",
                "chosen_word": "stage",
                "pin": "1234",
                "passphrase": "testpass",
            },
            {
                "first_name": "Li",
                "last_name": "Wei",
                "teacher_note": "Orchestra",
                "chosen_word": "chord",
                "pin": "1234",
                "passphrase": "testpass",
            },
        ],
    },
}
