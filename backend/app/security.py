"""安全工具：bcrypt 密码哈希 + JWT 签发/校验 + FastAPI 鉴权依赖。

- 密码：bcrypt 哈希，永不回传明文/哈希。
- Token：HS256 JWT，载荷只放 user_id 与签发时间（演示期）。
- 鉴权依赖 ``get_current_user``：解析 ``Authorization: Bearer <token>``，
  供后续评分、点赞等受保护端点使用；失败统一抛 401。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

# JWT 密钥：演示期可用环境变量覆盖，默认开发用固定值；上线前务必换。
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "taizhou-voice-demo-secret-change-me")
ALGORITHM = "HS256"
# token 有效期（演示期 7 天）
TOKEN_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "168"))

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """返回 bcrypt 哈希（str）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    """签发 JWT。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """解析 JWT 返回 user_id；非法/过期抛 HTTPException 401。"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return user_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI 鉴权依赖：Bearer token → 当前 User；未登录/失效 → 401。

    用法：``def protected(user: User = Depends(get_current_user))``
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(credentials.credentials)
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
