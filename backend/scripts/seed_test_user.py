"""种子脚本：预置测试账号 test@test.com / 123456 / 测试用户。

幂等：已存在则跳过不报错。
验证：查 users 表能查到该账号，且 verify_password("123456", hash) 为 True。

用法（在 backend/ 目录下执行）：
    UV_CACHE_DIR=$PWD/.uv-cache uv run python scripts/seed_test_user.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 backend/ 在 sys.path，供 `from app.xxx` 导入
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import User
from app.security import hash_password, verify_password

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "123456"
TEST_NICKNAME = "测试用户"


def seed_test_user() -> bool:
    """插入测试账号；返回 True 表示新建，False 表示已存在（跳过）。"""
    init_db()
    with SessionLocal() as db:
        existing = db.execute(
            select(User).where(User.email == TEST_EMAIL)
        ).scalar_one_or_none()

        if existing is not None:
            return False

        user = User(
            email=TEST_EMAIL,
            password_hash=hash_password(TEST_PASSWORD),
            nickname=TEST_NICKNAME,
            total_score=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return True


def verify() -> None:
    """从库里读出测试账号，校验密码哈希正确性。"""
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.email == TEST_EMAIL)
        ).scalar_one_or_none()

    if user is None:
        print("ERROR: 测试账号不存在，seed 失败")
        sys.exit(1)

    ok = verify_password(TEST_PASSWORD, user.password_hash)
    print(f"  id={user.id}  email={user.email}  nickname={user.nickname}")
    print(f"  verify_password('{TEST_PASSWORD}', hash) = {ok}")
    if not ok:
        print("ERROR: 密码校验失败")
        sys.exit(1)
    print("验证通过 ✓")


if __name__ == "__main__":
    created = seed_test_user()
    if created:
        print(f"测试账号已创建：{TEST_EMAIL}")
    else:
        print(f"测试账号已存在，跳过：{TEST_EMAIL}")
    verify()
