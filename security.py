from argon2 import PasswordHasher, exceptions

ph = PasswordHasher()

def hash_value(plaintext: str) -> str:
    return ph.hash(plaintext)

def verify_hash(hash: str, plaintext: str) -> bool:
    try:
        return ph.verify(hash, plaintext)
    except exceptions.VerifyMismatchError:
        return False