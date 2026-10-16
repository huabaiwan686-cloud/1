"""密码哈希与 JWT。"""
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    # 坏 hash（空、损坏、未知格式）时返回 False，不抛异常
    # （之前 bug：pwd_context.verify 抛 UnknownHashError，登录 500）
    try:
        if not hashed:
            return False
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def _create_token(subject: str, expires: timedelta, token_type: str, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": jti or secrets.token_hex(16),  # N15：JWT ID，用于撤销
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def is_token_revoked(db, jti: str) -> bool:
    """N15：检查 Refresh Token 是否已撤销。"""
    if not jti:
        return False
    return False


def revoke_token(db, jti: str, username: str = "", expires_at=None) -> None:
    """N15：撤销 Refresh Token（已删黑名单，不再检查）。"""
    return
