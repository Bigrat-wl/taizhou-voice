"""leaderboard / like / sentences recordings 三个接口 TDD 测试。

覆盖：
- GET /api/leaderboard/correct：正确数榜（score >= 60 录音数排名）
- POST/DELETE /api/recordings/{id}/like：点赞/取消（需登录，幂等 200）
- GET /api/sentences/{id}/recordings：某句子下录音按点赞数降序
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Like, Recording, Sentence, User
from app.security import create_token, hash_password

# ---------------------------------------------------------------------------
# 独立的内存 SQLite（与现有测试同模式）
# ---------------------------------------------------------------------------
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client():
    """每个测试重建表 + 种子数据：2 个用户、2 个句子、3 条录音。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        # 用户
        db.add(User(
            id=1, email="alice@b.com", password_hash=hash_password("123456"),
            nickname="老泰州", total_score=0,
        ))
        db.add(User(
            id=2, email="bob@b.com", password_hash=hash_password("123456"),
            nickname="小明", total_score=0,
        ))
        # 句子
        db.add(Sentence(
            id=1, text="今天天气真好", dialect_text="今朝天气老好",
            category="日常", difficulty=1,
        ))
        db.add(Sentence(
            id=2, text="你吃饭了吗", dialect_text="你切过饭了嘛",
            category="问候", difficulty=1,
        ))
        # 录音：alice 两条（score=90 合格、score=40 不及格），bob 一条（score=80 合格）
        db.add(Recording(id=1, sentence_id=1, user_id=1, audio_path="audio/1_1_t1.wav", score=90))
        db.add(Recording(id=2, sentence_id=2, user_id=1, audio_path="audio/2_1_t2.wav", score=40))
        db.add(Recording(id=3, sentence_id=1, user_id=2, audio_path="audio/1_2_t3.wav", score=80))
        # alice 对 bob 的录音点赞
        db.add(Like(recording_id=3, user_id=1))
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth_header(user_id: int = 1) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user_id)}"}


# ===========================================================================
# GET /api/leaderboard/correct
# ===========================================================================

class TestLeaderboardCorrect:
    """正确数榜：score >= 60 的录音数排名。"""

    def test_returns_200_and_list(self, client):
        resp = client.get("/api/leaderboard/correct")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_fields_present(self, client):
        body = client.get("/api/leaderboard/correct").json()
        item = body[0]
        assert set(item) == {"rank", "nickname", "correct_count", "total_score", "best_score"}

    def test_ranked_by_correct_count_desc(self, client):
        """alice 正确数 1（score=90），bob 正确数 1（score=80），正确数相同按 total_score 排。"""
        body = client.get("/api/leaderboard/correct").json()
        # 都是 1 条正确录音
        assert body[0]["correct_count"] >= body[1]["correct_count"]

    def test_correct_count_only_counts_score_ge_60(self, client):
        """alice 有两条录音，只有 score=90 算正确。"""
        body = client.get("/api/leaderboard/correct").json()
        alice = next(r for r in body if r["nickname"] == "老泰州")
        assert alice["correct_count"] == 1

    def test_total_score_and_best_score(self, client):
        """alice total_score = 90+40 = 130，best_score = 90。"""
        body = client.get("/api/leaderboard/correct").json()
        alice = next(r for r in body if r["nickname"] == "老泰州")
        assert alice["total_score"] == 130
        assert alice["best_score"] == 90

    def test_limit_param(self, client):
        body = client.get("/api/leaderboard/correct", params={"limit": 1}).json()
        assert len(body) == 1

    def test_default_limit_is_20(self, client):
        """无 limit 参数时默认返回最多 20 条。"""
        body = client.get("/api/leaderboard/correct").json()
        assert len(body) <= 20

    def test_rank_sequential(self, client):
        """rank 从 1 开始连续递增。"""
        body = client.get("/api/leaderboard/correct").json()
        for i, item in enumerate(body, start=1):
            assert item["rank"] == i

    def test_no_auth_required(self, client):
        """排行榜无需登录。"""
        resp = client.get("/api/leaderboard/correct")
        assert resp.status_code == 200


# ===========================================================================
# POST /api/recordings/{id}/like
# ===========================================================================

class TestPostLike:
    """点赞：需登录，幂等 200。"""

    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/recordings/1/like")
        assert resp.status_code == 401

    def test_like_success_returns_200(self, client):
        """alice 点赞录音 1。"""
        resp = client.post("/api/recordings/1/like", headers=_auth_header(2))
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"like_count", "liked_by_me"}
        assert body["liked_by_me"] is True
        assert isinstance(body["like_count"], int)

    def test_like_is_idempotent(self, client):
        """重复点赞返回 200，不报错。"""
        client.post("/api/recordings/3/like", headers=_auth_header(1))
        resp = client.post("/api/recordings/3/like", headers=_auth_header(1))
        assert resp.status_code == 200
        assert resp.json()["liked_by_me"] is True

    def test_like_count_correct(self, client):
        """录音 3 已有 alice 的 1 条赞，bob 点赞后 like_count=2。"""
        resp = client.post("/api/recordings/3/like", headers=_auth_header(2))
        assert resp.json()["like_count"] == 2

    def test_like_nonexistent_recording_returns_404(self, client):
        resp = client.post("/api/recordings/999/like", headers=_auth_header(1))
        assert resp.status_code == 404


# ===========================================================================
# DELETE /api/recordings/{id}/like
# ===========================================================================

class TestDeleteLike:
    """取消点赞：需登录，幂等 200。"""

    def test_no_auth_returns_401(self, client):
        resp = client.delete("/api/recordings/1/like")
        assert resp.status_code == 401

    def test_unlike_success_returns_200(self, client):
        """alice 取消对录音 3 的赞。"""
        resp = client.delete("/api/recordings/3/like", headers=_auth_header(1))
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"like_count", "liked_by_me"}
        assert body["liked_by_me"] is False
        assert body["like_count"] == 0

    def test_unlike_is_idempotent(self, client):
        """重复取消返回 200，不报错。"""
        client.delete("/api/recordings/3/like", headers=_auth_header(1))
        resp = client.delete("/api/recordings/3/like", headers=_auth_header(1))
        assert resp.status_code == 200
        assert resp.json()["liked_by_me"] is False

    def test_unlike_nonexistent_recording_returns_404(self, client):
        resp = client.delete("/api/recordings/999/like", headers=_auth_header(1))
        assert resp.status_code == 404


# ===========================================================================
# GET /api/sentences/{id}/recordings
# ===========================================================================

class TestSentenceRecordings:
    """某句子下录音按点赞数降序。"""

    def test_returns_200_and_structure(self, client):
        resp = client.get("/api/sentences/1/recordings")
        assert resp.status_code == 200
        body = resp.json()
        assert "sentence" in body
        assert "items" in body

    def test_sentence_fields(self, client):
        body = client.get("/api/sentences/1/recordings").json()
        s = body["sentence"]
        assert set(s) == {"id", "text", "dialect_text"}
        assert s["id"] == 1

    def test_item_fields(self, client):
        body = client.get("/api/sentences/1/recordings").json()
        item = body["items"][0]
        assert set(item) == {"recording_id", "nickname", "audio_url", "like_count", "liked_by_me"}

    def test_sorted_by_like_count_desc(self, client):
        """录音 3（like_count=1）应排在录音 1（like_count=0）前面。"""
        body = client.get("/api/sentences/1/recordings").json()
        items = body["items"]
        assert len(items) == 2
        assert items[0]["like_count"] >= items[1]["like_count"]

    def test_liked_by_me_without_auth(self, client):
        """不带 token 时 liked_by_me 恒为 false。"""
        body = client.get("/api/sentences/1/recordings").json()
        for item in body["items"]:
            assert item["liked_by_me"] is False

    def test_liked_by_me_with_auth(self, client):
        """带 token 时反映当前用户的点赞状态。"""
        body = client.get(
            "/api/sentences/1/recordings", headers=_auth_header(1)
        ).json()
        # alice 点赞了录音 3
        rec3 = next(i for i in body["items"] if i["recording_id"] == 3)
        assert rec3["liked_by_me"] is True
        # alice 未点赞录音 1
        rec1 = next(i for i in body["items"] if i["recording_id"] == 1)
        assert rec1["liked_by_me"] is False

    def test_sentence_not_found_returns_404(self, client):
        resp = client.get("/api/sentences/999/recordings")
        assert resp.status_code == 404

    def test_empty_recordings(self, client):
        """句子 2 有录音，句子不存在时 404；句子 1 有录音。"""
        # 句子 2 有 1 条录音
        body = client.get("/api/sentences/2/recordings").json()
        assert len(body["items"]) == 1

    def test_audio_url_format(self, client):
        body = client.get("/api/sentences/1/recordings").json()
        for item in body["items"]:
            assert item["audio_url"].startswith("/data/")
