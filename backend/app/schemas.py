"""Pydantic 请求/响应模型（认证部分）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求：邮箱 + 密码 + 昵称（演示期宽松校验）。"""

    email: str = Field(..., min_length=3, max_length=255, description="登录邮箱（唯一）")
    password: str = Field(..., min_length=6, max_length=128, description="密码，至少 6 位")
    nickname: str = Field(..., min_length=1, max_length=64, description="昵称，≤64 字")


class LoginRequest(BaseModel):
    """登录请求：邮箱 + 密码。"""

    email: str = Field(..., min_length=1, max_length=255, description="登录邮箱")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserOut(BaseModel):
    """对外返回的用户信息（绝不包含 password_hash）。"""

    id: int
    email: str
    nickname: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """注册/登录成功响应：token + user。"""

    token: str
    user: UserOut
