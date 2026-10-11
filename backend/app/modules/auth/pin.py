"""Parent PIN hashing with the standard library's scrypt (no extra dependency, fully offline)."""

import hashlib
import hmac
import os
import re

PIN_PATTERN = re.compile(r"^\d{4,6}$")
_N, _R, _P = 2**14, 8, 1


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    _, n, r, p, salt, digest = stored.split("$")
    candidate = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    return hmac.compare_digest(candidate.hex(), digest)
