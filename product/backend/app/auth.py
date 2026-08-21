"""Authentication helpers — JWT tokens + password hashing."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import database as db

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# Resolved lazily and cached — the settings table only exists after init_db().
_jwt_secret: str | None = None


def _jwt_secret_key() -> str:
    """Return this install's JWT signing key.

    JWT_SECRET env var wins; otherwise the key stored in the settings table is
    used, and a random one is generated and persisted on first use. Shipping a
    build-time default would give every install the same signing key, so there
    is deliberately no fallback constant here.
    """
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret

    env_secret = os.environ.get("JWT_SECRET", "")
    if env_secret:
        _jwt_secret = env_secret
        return _jwt_secret

    stored = db.get_settings().get("jwt_secret", "")
    if not stored:
        stored = secrets.token_urlsafe(48)
        db.put_settings({"jwt_secret": stored})
    _jwt_secret = stored
    return _jwt_secret

_bearer_scheme = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────────────────

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _jwt_secret_key(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret_key(), algorithms=[JWT_ALGORITHM])


# ── FastAPI dependency ────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """Decode JWT from Authorization header and return the user dict."""
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_recruiter(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Reject non-recruiter users with 403."""
    if current_user.get("role", "recruiter") != "recruiter":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recruiter access only")
    return current_user
