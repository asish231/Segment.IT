"""Password hashing, JWT issuance/verification, and FastAPI auth dependencies."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from models import ApiKey, User

SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-insecure-secret-change-me-in-.env"
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "60"))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "14"))

# bcrypt's algorithm caps input at 72 bytes; longer inputs are truncated (not an error).
def _bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_bytes(password), hashed.encode("utf-8"))
    except Exception:
        return False


def _make_token(user_id: str, minutes: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def make_access_token(user_id: str) -> str:
    return _make_token(user_id, ACCESS_TOKEN_MINUTES, "access")


def make_refresh_token(user_id: str) -> str:
    return _make_token(user_id, REFRESH_TOKEN_DAYS * 24 * 60, "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "invalid token")


# --- API keys -----------------------------------------------------------

def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hashed_key) for a freshly minted API key."""
    raw = secrets.token_urlsafe(32)
    prefix = f"bh_{raw[:8]}"
    full_key = f"{prefix}.{raw}"
    hashed = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, hashed


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode()).hexdigest()


# --- FastAPI dependencies -------------------------------------------------

def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(401, "not authenticated")

    # API key path: "bh_xxxxxxxx.yyyy..."
    if token.startswith("bh_"):
        hashed = hash_api_key(token)
        key = db.query(ApiKey).filter(ApiKey.hashed_key == hashed, ApiKey.revoked_at.is_(None)).first()
        if not key:
            raise HTTPException(401, "invalid API key")
        key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        user = db.query(User).filter(User.id == key.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(401, "user inactive")
        return user

    # JWT path
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(401, "not an access token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(401, "user inactive")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(403, f"requires role in {roles}")
        return user

    return _dep
