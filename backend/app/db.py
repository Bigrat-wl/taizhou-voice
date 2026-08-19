"""数据库连接（SQLite）。

SQLite 文件位于 ``backend/data/taizhou_voice.db``（默认），
可通过环境变量 ``TAIZHOU_VOICE_DB`` 覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 数据库文件：backend/data/taizhou_voice.db
DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "taizhou_voice.db"

DB_URL = os.getenv(
    "TAIZHOU_VOICE_DB", f"sqlite:///{DEFAULT_DB_PATH}"
)

# ensure_foreign_keys：SQLite 默认不启用外键约束，显式打开
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},  # 供 FastAPI 多线程使用
    echo=bool(os.getenv("DB_ECHO", "")),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


def init_db() -> None:
    """建表（若不存在）并确保数据目录存在。"""
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 延迟导入，避免导入 app.db 时触发模型定义
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖：返回会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()