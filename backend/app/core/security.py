import re
from datetime import timedelta
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.utils import current_time_utc

# TODO: review

# Use PBKDF2-SHA256 for new hashes (no 72-byte limit) while still verifying legacy bcrypt
_pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt_sha256", "bcrypt"], deprecated="auto")

_PASSWORD_MIN_LENGTH = 12


def validate_password_strength(password: str) -> None:
    if len(password) < _PASSWORD_MIN_LENGTH:
        msg = f"Password must be at least {_PASSWORD_MIN_LENGTH} characters long"
        raise ValueError(msg)

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must include at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must include at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must include at least one number")


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = current_time_utc() + expires_delta
    else:
        expire = current_time_utc() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}

    if settings.JWT_SECRET_KEY is None:
        msg = "JWT_SECRET_KEY is not set"
        raise ValueError(msg)

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def verify_token(token: str) -> str | None:
    if settings.JWT_SECRET_KEY is None:
        msg = "JWT_SECRET_KEY is not set"
        raise ValueError(msg)

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
        UUID(user_id)
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
    return user_id
