"""排行榜 + 点赞 + 句子录音路由。

- GET  /api/leaderboard/correct       正确数榜（score >= 60 排名）
- GET  /api/leaderboard/likes          点赞数榜（所有录音，按点赞数降序，同赞随机）
- POST /api/recordings/{id}/like      点赞（需登录，幂等 200）
- DEL  /api/recordings/{id}/like      取消点赞（需登录，幂等 200）
- GET  /api/sentences/{id}/recordings 某句子下录音按点赞数降序
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DialectRecording, Like, Recording, Sentence, User
from app.security import decode_token, get_current_user

router = APIRouter(prefix="/api", tags=["leaderboard"])

_bearer_optional = HTTPBearer(auto_error=False)


def _get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """可选鉴权：有 token 返回 User，无 token 返回 None。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        user_id = decode_token(credentials.credentials)
    except Exception:
        return None
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /api/leaderboard/correct
# ---------------------------------------------------------------------------

@router.get("/leaderboard/correct", summary="正确数榜")
def leaderboard_correct(
    limit: int = Query(default=20, ge=1, description="返回条数"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """正确数榜：score >= 60 的录音数排名。

    按正确数降序，正确数相同按 total_score 降序。
    响应：``[{ rank, nickname, correct_count, total_score, best_score }, ...]``
    """
    # 子查询：每个用户的正确数、总分、最高分
    subq = (
        select(
            Recording.user_id,
            func.count().filter(Recording.score >= 60).label("correct_count"),
            func.coalesce(func.sum(Recording.score), 0).label("total_score"),
            func.coalesce(func.max(Recording.score), 0).label("best_score"),
        )
        .group_by(Recording.user_id)
        .subquery()
    )

    rows = (
        db.execute(
            select(
                User.nickname,
                subq.c.correct_count,
                subq.c.total_score,
                subq.c.best_score,
            )
            .join(subq, User.id == subq.c.user_id)
            .order_by(subq.c.correct_count.desc(), subq.c.total_score.desc())
            .limit(limit)
        )
        .all()
    )

    return [
        {
            "rank": idx,
            "nickname": r.nickname,
            "correct_count": r.correct_count,
            "total_score": r.total_score,
            "best_score": r.best_score,
        }
        for idx, r in enumerate(rows, start=1)
    ]


# ---------------------------------------------------------------------------
# GET /api/leaderboard/likes
# ---------------------------------------------------------------------------

@router.get("/leaderboard/likes", summary="点赞数榜（所有录音）")
def leaderboard_likes(
    limit: int = Query(default=50, ge=1, description="返回条数"),
    current_user: User | None = Depends(_get_optional_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """点赞数榜：所有录音按点赞数降序，点赞数相同则随机排序。

    带 token 时 liked_by_me 反映当前用户状态，否则恒为 false。
    响应：``[{ recording_id, nickname, sentence_text, audio_url, like_count, liked_by_me }, ...]``
    """
    # 子查询：每条录音的点赞数
    like_count_subq = (
        select(
            Like.recording_id,
            func.count().label("like_count"),
        )
        .group_by(Like.recording_id)
        .subquery()
    )

    rows = (
        db.execute(
            select(
                Recording.id,
                User.nickname,
                Sentence.text.label("sentence_text"),
                Recording.audio_path,
                func.coalesce(like_count_subq.c.like_count, 0).label("like_count"),
            )
            .join(User, Recording.user_id == User.id)
            .join(Sentence, Recording.sentence_id == Sentence.id)
            .outerjoin(like_count_subq, Recording.id == like_count_subq.c.recording_id)
            .order_by(func.coalesce(like_count_subq.c.like_count, 0).desc())
        )
        .all()
    )

    # 点赞数相同则随机排序
    rows_list = list(rows)
    grouped: dict[int, list] = {}
    for r in rows_list:
        grouped.setdefault(r.like_count, []).append(r)
    shuffled = []
    for like_count in sorted(grouped.keys(), reverse=True):
        group = grouped[like_count]
        random.shuffle(group)
        shuffled.extend(group)

    # 截取 limit 条
    shuffled = shuffled[:limit]

    # 当前用户的点赞集合（用于 liked_by_me）
    liked_ids: set[int] = set()
    if current_user is not None:
        liked_ids = set(
            db.execute(
                select(Like.recording_id).where(
                    Like.recording_id.in_([r.id for r in shuffled]),
                    Like.user_id == current_user.id,
                )
            ).scalars().all()
        )

    return [
        {
            "recording_id": r.id,
            "nickname": r.nickname,
            "sentence_text": r.sentence_text,
            "audio_url": f"/data/{r.audio_path}",
            "like_count": r.like_count,
            "liked_by_me": r.id in liked_ids,
        }
        for r in shuffled
    ]


# ---------------------------------------------------------------------------
# POST /api/recordings/{id}/like
# ---------------------------------------------------------------------------

@router.post("/recordings/{recording_id}/like", summary="点赞录音")
def post_like(
    recording_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """点赞录音（幂等：已点返回 200 不报错）。

    响应：``{ like_count, liked_by_me }``
    """
    # 校验录音存在
    recording = db.execute(
        select(Recording.id).where(Recording.id == recording_id)
    ).scalar_one_or_none()
    if recording is None:
        raise HTTPException(status_code=404, detail="录音不存在")

    # 幂等：已点赞则跳过插入
    existing = db.execute(
        select(Like).where(Like.recording_id == recording_id, Like.user_id == user.id)
    ).scalar_one_or_none()
    if existing is None:
        db.add(Like(recording_id=recording_id, user_id=user.id))
        db.commit()

    like_count = db.execute(
        select(func.count()).where(Like.recording_id == recording_id)
    ).scalar()

    return {"like_count": like_count, "liked_by_me": True}


# ---------------------------------------------------------------------------
# DELETE /api/recordings/{id}/like
# ---------------------------------------------------------------------------

@router.delete("/recordings/{recording_id}/like", summary="取消点赞")
def delete_like(
    recording_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """取消点赞（幂等：未点也返回 200）。

    响应：``{ like_count, liked_by_me }``
    """
    # 校验录音存在
    recording = db.execute(
        select(Recording.id).where(Recording.id == recording_id)
    ).scalar_one_or_none()
    if recording is None:
        raise HTTPException(status_code=404, detail="录音不存在")

    # 幂等：未点赞则跳过删除
    existing = db.execute(
        select(Like).where(Like.recording_id == recording_id, Like.user_id == user.id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()

    like_count = db.execute(
        select(func.count()).where(Like.recording_id == recording_id)
    ).scalar()

    return {"like_count": like_count, "liked_by_me": False}


# ---------------------------------------------------------------------------
# GET /api/sentences/{id}/recordings
# ---------------------------------------------------------------------------

@router.get("/sentences/{sentence_id}/recordings", summary="某句子下录音按点赞数降序")
def sentence_recordings(
    sentence_id: int,
    current_user: User | None = Depends(_get_optional_user),
    db: Session = Depends(get_db),
) -> dict:
    """某句子下所有录音（方言录音 + 用户录音），按点赞数降序。

    带 token 时 liked_by_me 反映当前用户状态，否则恒为 false。
    响应：``{ sentence: { id, text, dialect_text }, items: [...] }``
    """
    sentence = db.execute(
        select(Sentence).where(Sentence.id == sentence_id)
    ).scalar_one_or_none()
    if sentence is None:
        raise HTTPException(status_code=404, detail="句子不存在")

    # 子查询：每条用户录音的点赞数
    like_count_subq = (
        select(
            Like.recording_id,
            func.count().label("like_count"),
        )
        .group_by(Like.recording_id)
        .subquery()
    )

    # 用户录音
    user_rows = (
        db.execute(
            select(
                Recording.id,
                User.nickname,
                Recording.audio_path,
                func.coalesce(like_count_subq.c.like_count, 0).label("like_count"),
            )
            .join(User, Recording.user_id == User.id)
            .outerjoin(like_count_subq, Recording.id == like_count_subq.c.recording_id)
            .where(Recording.sentence_id == sentence_id)
            .order_by(func.coalesce(like_count_subq.c.like_count, 0).desc())
        )
        .all()
    )

    # 方言录音（原始方言版本）
    dialect_rows = db.execute(
        select(DialectRecording)
        .where(DialectRecording.sentence_id == sentence_id)
    ).scalars().all()

    # 当前用户的点赞集合（用于 liked_by_me）
    liked_ids: set[int] = set()
    if current_user is not None:
        liked_ids = set(
            db.execute(
                select(Like.recording_id).where(
                    Like.recording_id.in_([r.id for r in user_rows]),
                    Like.user_id == current_user.id,
                )
            ).scalars().all()
        )

    # 合并：方言录音 + 用户录音
    items = []
    # 方言录音（无点赞，标记为 dialect 类型）
    for dr in dialect_rows:
        items.append({
            "recording_id": f"dialect_{dr.id}",
            "nickname": dr.speaker or "方言",
            "audio_url": f"/data/{dr.audio_path}",
            "like_count": 0,
            "liked_by_me": False,
            "type": "dialect",
            "dialect_text": dr.dialect_text,
        })
    # 用户录音
    for r in user_rows:
        items.append({
            "recording_id": r.id,
            "nickname": r.nickname,
            "audio_url": f"/data/{r.audio_path}",
            "like_count": r.like_count,
            "liked_by_me": r.id in liked_ids,
            "type": "user",
        })

    return {
        "sentence": {
            "id": sentence.id,
            "text": sentence.text,
            "dialect_text": sentence.dialect_text,
        },
        "items": items,
    }
