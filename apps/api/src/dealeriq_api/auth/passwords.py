"""Argon2id password hashing (ADR-009, FR-002). Parameters meet the SRS minimums
(memory>=64MiB, iterations>=3) exactly. Passwords are never logged or returned - callers must
not put a plaintext password into a log line or response model."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
