"""SQLAlchemy ORM 模型：sentences / users / recordings / likes / translations。

字段严格按《数据模型设计（v2）》对齐：
- 时间统一中国时区（Asia/Shanghai）
- 用户用邮箱 + 密码（bcrypt），无 openid
- 评分只存整数分，无等级字段
- 点赞关系单独一张表（联合唯一）
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    """上海本地时间（naive），保证与「中国时区」约定一致。"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


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
        DateTime, nullable=False, default=_now, comment="创建时间"
    )


class User(Base):
    """用户（邮箱 + 密码登录）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="登录邮箱（唯一标识）"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="bcrypt 哈希，永不返回"
    )
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, comment="昵称（允许重名）")
    total_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="累计总分（整数分）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, comment="创建时间"
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
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="音频相对路径")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="评分 0~100 整数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, comment="创建时间"
    )


class Like(Base):
    """点赞关系（录音 × 用户，联合唯一防重复点赞）。"""

    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("recording_id", "user_id", name="uq_like_recording_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id"), nullable=False, comment="被点赞录音"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="点赞人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, comment="创建时间"
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
        DateTime, nullable=False, default=_now, comment="创建时间"
    )
