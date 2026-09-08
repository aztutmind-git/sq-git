import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings


# ---------------- passwords ----------------
def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------- JWT access tokens ----------------
def create_access_token(user_id: str, userid: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "userid": userid, "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ---------------- password-reset tokens ----------------
# We generate a random URL-safe token, send/return the RAW token to the user,
# but only ever store its SHA-256 hash in the DB (same principle as password
# storage: the raw token is never persisted).
def generate_reset_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    return raw, token_hash, expires_at


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
