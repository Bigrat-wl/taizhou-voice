"""排行榜 + 点赞 + 句子录音路由。

- GET  /api/leaderboard/correct       正确数榜（score >= 60 排名）
- POST /api/recordings/{id}/like      点赞（需登录，幂等 200）
- DEL  /api/recordings/{id}/like      取消点赞（需登录，幂等 200）
- GET  /api/sentences/{id}/recordings 某句子下录音按点赞数降序
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Like, Recording, Sentence, User
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
    """某句子下所有录音，按点赞数降序。

    带 token 时 liked_by_me 反映当前用户状态，否则恒为 false。
    响应：``{ sentence: { id, text, dialect_text }, items: [...] }``
    """
    sentence = db.execute(
        select(Sentence).where(Sentence.id == sentence_id)
    ).scalar_one_or_none()
    if sentence is None:
        raise HTTPException(status_code=404, detail="句子不存在")

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

    # 当前用户的点赞集合（用于 liked_by_me）
    liked_ids: set[int] = set()
    if current_user is not None:
        liked_ids = set(
            db.execute(
                select(Like.recording_id).where(
                    Like.recording_id.in_([r.id for r in rows]),
                    Like.user_id == current_user.id,
                )
            ).scalars().all()
        )

    return {
        "sentence": {
            "id": sentence.id,
            "text": sentence.text,
            "dialect_text": sentence.dialect_text,
        },
        "items": [
            {
                "recording_id": r.id,
                "nickname": r.nickname,
                "audio_url": f"/data/{r.audio_path}",
                "like_count": r.like_count,
                "liked_by_me": r.id in liked_ids,
            }
            for r in rows
        ],
    }
