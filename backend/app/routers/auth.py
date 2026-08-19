"""认证路由：POST /api/auth/register、POST /api/auth/login。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, nickname=user.nickname)


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(token=create_token(user.id), user=_to_user_out(user))


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册：邮箱 + 密码 + 昵称",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """注册新用户；邮箱已存在 → 409。"""
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="邮箱格式不合法")

    exists = db.execute(select(User.id).where(User.email == email)).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname.strip(),
        total_score=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="登录：邮箱 + 密码",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """邮箱 + 密码登录；账号不存在或密码错误 → 401。"""
    email = payload.email.strip().lower()
    user = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _auth_response(user)
