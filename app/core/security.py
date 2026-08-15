import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Matric hashing — SHA-256 with server-side pepper
# NOTE: Pepper is a server-side secret (not stored in DB).
#       This means even a full DB dump reveals no matric numbers.
# ---------------------------------------------------------------------------

def hash_matric(matric: str, admin: bool = False) -> str:
    """Hash a matric number with the appropriate pepper.

    We use separate peppers for students and admins so that even if one pepper
    is compromised, the other set of hashes remains protected.
    """
    pepper = settings.admin_pepper if admin else settings.matric_pepper
    normalized = matric.strip().upper()
    return hashlib.sha256(f"{normalized}{pepper}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Admin PIN hashing — bcrypt (adaptive, brute-force resistant)
# ---------------------------------------------------------------------------

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT — issued as httpOnly cookie, never returned in response body
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"


def create_access_token(
    hashed_matric_id: str,
    role: str,  # "student" | "admin"
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expire_hours)
    )
    payload = {
        "sub": hashed_matric_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Returns the decoded payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
