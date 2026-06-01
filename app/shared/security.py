from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

ALGORITHM = settings.JWT_ALGORITHM
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def token_fingerprint(token: str) -> str:
    """生成短指纹用于日志关联 token，不记录 token 原文。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def get_password_hash(password: str) -> str:
    """生成 password hash；调用方不需要知道具体 hash 算法。"""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文 password 和已存 hash 是否匹配。"""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """创建 JWT access token，并返回 token 和秒级 expires_in。"""
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    expires_in = int((expires_at - now).total_seconds())
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT access token，失败时由 PyJWT 抛出异常。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
