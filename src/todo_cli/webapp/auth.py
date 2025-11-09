"""
Authentication utilities: password hashing (bcrypt) and JWT token handling
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, status

# ============================================================================
# Settings
# ============================================================================

SECRET_KEY = os.getenv("TODO_WEB_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = os.getenv("TODO_WEB_JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TODO_WEB_ACCESS_TOKEN_MINUTES", "60"))


# ============================================================================
# Password hashing
# ============================================================================

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ============================================================================
# JWT helpers
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token, raising 401 on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _extract_bearer_from_cookie(request: Request) -> Optional[str]:
    """Extract 'Bearer <token>' from access_token cookie and return the raw token."""
    cookie = request.cookies.get("access_token")
    if not cookie:
        return None
    if cookie.startswith("Bearer "):
        return cookie[len("Bearer ") :]
    return cookie


# ============================================================================
# Authentication helpers
# ============================================================================

def authenticate_user(username: str, password: str):
    """Validate user credentials and return the user or None."""
    # Import here to avoid circular import
    from .database import get_db
    
    db = get_db()
    user = db.get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_current_user(request: Request):
    """FastAPI dependency that returns the current user from JWT cookie or raises 401."""
    # Import here to avoid circular import
    from .database import get_db
    
    token = _extract_bearer_from_cookie(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = get_db()
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
