import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

COOKIE_NAME = "vt_session"
ALGORITHM = "HS256"

_settings = get_settings()
# Argon2id. The parameters follow the OWASP minimum recommendation (19 MiB, 2 passes, 1 lane).
# The "fast" switch is only for the automated tests.
_hasher = (
    PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    if _settings.fast_hashing
    else PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_session_token(user_id: int, csrf: str | None = None) -> tuple[str, str]:
    """Return (jwt, csrf_token). The CSRF token lives inside the JWT and is also given to the app."""
    settings = get_settings()
    csrf = csrf or secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "csrf": csrf,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.session_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), csrf


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
