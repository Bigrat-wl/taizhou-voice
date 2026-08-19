"""POST /api/score 接口 + 评分相似度逻辑单测（TDD）。

覆盖：
- 纯函数：文本相似度计算（及格线 60）
- 接口：需登录 401、缺字段 400、句子不存在 400、成功打分 200、音频落盘、录音入库
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Recording, Sentence, User
from app.security import create_token, hash_password
from app.services.scoring_service import compute_similarity

# ---------------------------------------------------------------------------
# 独立的内存 SQLite
# ---------------------------------------------------------------------------
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _make_wav_bytes(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
    """构造一个合法的极简 WAV 文件（单声道 16bit PCM），用于模拟上传。"""
    num_samples = int(sample_rate * duration_s)
    # WAV header: 44 bytes
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,  # file size - 8
        b"WAVE",
        b"fmt ",
        16,  # PCM chunk size
        1,  # PCM format
        1,  # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,  # block align
        16,  # bits per sample
        b"data",
        data_size,
    )
    # 简单静音波形
    data = b"\x00\x00" * num_samples
    return header + data


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # 种子数据：一个句子 + 一个用户
    with TestingSessionLocal() as db:
        db.add(
            Sentence(
                id=1, text="今天天气真好", dialect_text="今朝天气老好",
                category="日常", difficulty=1,
            )
        )
        db.add(
            User(
                id=1, email="test@b.com",
                password_hash=hash_password("123456"),
                nickname="测试用户", total_score=0,
            )
        )
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
# 纯函数：文本相似度计算
# ===========================================================================

class TestComputeSimilarity:
    """评分相似度逻辑：识别文本 ↔ 参考文本比对，及格线 60。"""

    def test_perfect_match_returns_100(self):
        assert compute_similarity("今天天气真好", "今天天气真好") == 100

    def test_empty_both_returns_100(self):
        # 两个空字符串视为完全匹配
        assert compute_similarity("", "") == 100

    def test_completely_different_returns_low_score(self):
        # 完全不同文本，分数应该很低（< 60）
        score = compute_similarity("你好世界", "abcdefghijklmnop")
        assert score < 60

    def test_partial_match_above_pass(self):
        # 大部分匹配：前缀相同
        score = compute_similarity("今天天气真好啊", "今天天气真好")
        assert score >= 60
        assert score <= 100

    def test_partial_match_below_pass(self):
        # 少量匹配：差异大
        score = compute_similarity("今天", "明天后天大后天大大大大")
        assert score < 60

    def test_one_empty_one_nonempty_returns_0(self):
        assert compute_similarity("", "你好") == 0
        assert compute_similarity("你好", "") == 0

    def test_single_char_match(self):
        assert compute_similarity("你", "你") == 100

    def test_single_char_mismatch(self):
        score = compute_similarity("你", "好")
        assert score == 0

    def test_transposition_penalty(self):
        # 顺序不同应该有惩罚
        score = compute_similarity("ABC", "BCA")
        assert 0 < score < 100

    def test_score_is_integer_0_to_100(self):
        # 所有返回值都是 0~100 的整数
        pairs = [
            ("你好", "你好"),
            ("你好", "世界"),
            ("abc", "abcd"),
            ("", ""),
            ("完全不同的句子", "这里也是完全不同"),
        ]
        for a, b in pairs:
            score = compute_similarity(a, b)
            assert isinstance(score, int), f"({a!r}, {b!r}) → {score} 不是 int"
            assert 0 <= score <= 100, f"({a!r}, {b!r}) → {score} 超出范围"

    def test_pass_threshold_at_60(self):
        # 及格线 = 60：score >= 60 才算正确
        assert compute_similarity("今天天气真好", "今天天气真好") >= 60
        assert compute_similarity("完全不同的文本", "也是完全不同的句") < 60


# ===========================================================================
# 接口：POST /api/score
# ===========================================================================

class TestPostScore:
    """POST /api/score 接口集成测试（mock ASR，避免加载真实模型）。"""

    def test_no_auth_returns_401(self, client):
        """未登录 → 401。"""
        resp = client.post(
            "/api/score",
            files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
            data={"sentence_id": 1},
        )
        assert resp.status_code == 401

    def test_missing_sentence_id_returns_422(self, client):
        """缺少 sentence_id → 422（FastAPI Pydantic 验证）。"""
        resp = client.post(
            "/api/score",
            headers=_auth_header(),
            files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
        )
        assert resp.status_code == 422

    def test_sentence_not_found_returns_400(self, client):
        """句子不存在 → 400。"""
        resp = client.post(
            "/api/score",
            headers=_auth_header(),
            files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
            data={"sentence_id": 9999},
        )
        assert resp.status_code == 400

    def test_unsupported_audio_format_returns_415(self, client):
        """不支持的音频格式 → 415。"""
        resp = client.post(
            "/api/score",
            headers=_auth_header(),
            files={"audio": ("test.xyz", b"fake", "audio/xyz")},
            data={"sentence_id": 1},
        )
        assert resp.status_code == 415

    def test_score_success_returns_200(self, client):
        """成功评分：mock ASR 返回参考文本 → score=100。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气真好",
        ):
            resp = client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"score", "transcript", "reference"}
        assert body["transcript"] == "今天天气真好"
        assert body["reference"] == "今天天气真好"
        assert body["score"] == 100

    def test_score_partial_match(self, client):
        """部分匹配：mock ASR 返回不同文本 → score < 100。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气还不错",
        ):
            resp = client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["score"] <= 100
        assert isinstance(body["score"], int)

    def test_score_asr_empty_returns_422(self, client):
        """ASR 未识别到内容 → 422。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="",
        ):
            resp = client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        assert resp.status_code == 422

    def test_audio_saved_to_disk(self, client, tmp_path):
        """录音落盘到 backend/data/audio/{sentence_id}_{user_id}_{ts}.wav。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气真好",
        ), patch(
            "app.routers.score.AUDIO_DIR", tmp_path
        ):
            resp = client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        assert resp.status_code == 200
        audio_files = list(tmp_path.glob("1_1_*.wav"))
        assert len(audio_files) == 1

    def test_recording_saved_to_db(self, client):
        """评分后 recordings 表有一条记录。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气真好",
        ):
            client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        with TestingSessionLocal() as db:
            recs = db.execute(select(Recording)).scalars().all()
            assert len(recs) == 1
            assert recs[0].sentence_id == 1
            assert recs[0].user_id == 1
            assert recs[0].score == 100

    def test_user_total_score_updated(self, client):
        """评分后 users.total_score 累加。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气真好",
        ):
            client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        with TestingSessionLocal() as db:
            user = db.execute(select(User).where(User.id == 1)).scalar_one()
            assert user.total_score == 100

    def test_score_is_integer_no_level(self, client):
        """响应只含 score（整数），不含 level 字段。"""
        with patch(
            "app.services.asr_service.Qwen3ASRService.transcribe_file",
            return_value="今天天气真好",
        ):
            resp = client.post(
                "/api/score",
                headers=_auth_header(),
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={"sentence_id": 1},
            )
        body = resp.json()
        assert isinstance(body["score"], int)
        assert "level" not in body
