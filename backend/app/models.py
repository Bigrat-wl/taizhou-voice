"""SQLAlchemy ORM 模型：sentences / users / recordings / translations。

字段严格按《泰州方言通-项目设计》第六节数据设计。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now()


class Sentence(Base):
    """句子库（27 句种子）。"""

    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="普通话参考文本")
    dialect_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="方言文本"
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="分类")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="难度等级")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="创建时间"
    )


class User(Base):
    """用户（演示用昵称）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, comment="openid/演示唯一标识"
    )
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, comment="昵称")
    total_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="总分"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="创建时间"
    )


class Recording(Base):
    """录音 + 评分。"""

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sentence_id: Mapped[int] = mapped_column(
        ForeignKey("sentences.id"), nullable=False, comment="关联句子"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="关联用户"
    )
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="音频本地路径")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="评分")
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="", comment="等级")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="创建时间"
    )


class Translation(Base):
    """翻译 / 转写历史。"""

    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="关联用户"
    )
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="源文本")
    result_text: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="结果文本")
    direction: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="方向")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="创建时间"
    )