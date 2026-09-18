"""Password hashing, JWT issuing/verification, and opaque token generation.

Uses only the standard library plus ``PyJWT``:

* Password hashing is PBKDF2-HMAC-SHA256 with a per-user random salt and a high
  iteration count. This is deliberately *not* bcrypt/argon2 — those need a
  compiled dependency, and Render's free tier is memory-constrained (512 MB).
  ``hashlib.pbkdf2_hmac`` is C-backed, allocation-light, and adequate for a
  single-tenant buyer login.
* JWT is HS256 signed with ``SECRET_KEY``.
* Supplier invitation tokens are ``secrets.token_urlsafe`` — opaque, unguessable,
  and never derived from the quote data.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

PBKDF2_ITERATIONS = 260_000
PBKDF2_ALGORITHM = "sha256"
SALT_BYTES = 16
TOKEN_BYTES = 32

JWT_ALGORITHM = "HS256"


# --------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    """Return ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``."""

    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "$".join(
        [
            f"pbkdf2_{PBKDF2_ALGORITHM}",
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a stored PBKDF2 hash."""

    try:
        algorithm, iterations, salt_b64, hash_b64 = stored.split("$")
    except ValueError:
        return False

    if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
        return False

    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        int(iterations),
    )

    return hmac.compare_digest(candidate, expected)


# -------------------------------------------------------------------------- JWT
def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "access",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a bearer token.

    Raises ``UnauthorizedError`` (401) for any invalid, expired, or
    wrong-type token so the router layer never has to translate PyJWT errors.
    """

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Session expired — please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    if payload.get("typ") != "access":
        raise UnauthorizedError("Invalid authentication token.")

    return payload


# ------------------------------------------------------------------ opaque tokens
def generate_invitation_token() -> str:
    """URL-safe, unguessable token used in the supplier's public form link."""

    return secrets.token_urlsafe(TOKEN_BYTES)


def generate_reference_number(rfq_number: str, invitation_id: int) -> str:
    """Human-readable confirmation reference shown to the supplier."""

    return f"SQ-{rfq_number}-{invitation_id:04d}"


def tokens_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
