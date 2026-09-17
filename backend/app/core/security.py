import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.config import settings


# Precomputed valid bcrypt hash used to mitigate timing attacks on invalid emails
DUMMY_BCRYPT_HASH = "$2b$12$e8Y6bFj63y3hG7G7e68vOuG1qK75eO9t8rP.gO0wQp/k98Z.q9G6u"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with auto-generated salt."""
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed 72 bytes")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hashed counterpart."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Encode payload data into a signed HS256 JWT token with an expiration timestamp.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and cryptographically verify an HS256 JWT access token.
    Raises jwt.PyJWTError on expiration, invalid signature or tampering.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

