"""POST /api/asr 接口 webm/opus 转码测试。

覆盖：
- webm 上传走 ffmpeg 转码路径
- ffmpeg 失败返回 422
- wav 上传不触发 ffmpeg
"""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _make_wav_bytes(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
    """构造一个合法的极简 WAV 文件（单声道 16bit PCM）。"""
    num_samples = int(sample_rate * duration_s)
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    data = b"\x00\x00" * num_samples
    return header + data


@pytest.fixture()
def client():
    yield TestClient(app)


class TestAsrWebmTranscode:
    """webm 上传走 ffmpeg 转码路径。"""

    def test_webm_triggers_ffmpeg_transcode(self, client):
        """webm 上传 → ffmpeg 转码 → ASR 识别 → 正常返回。"""
        fake_webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 100

        def fake_subprocess_run(cmd, **kwargs):
            dest = cmd[-1]
            Path(dest).write_bytes(_make_wav_bytes())
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        with (
            patch("app.main.subprocess.run", side_effect=fake_subprocess_run),
            patch(
                "app.services.asr_service.Qwen3ASRService.transcribe_file",
                return_value="今天天气真好",
            ),
        ):
            resp = client.post(
                "/api/asr",
                files={"audio": ("test.webm", fake_webm, "audio/webm")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "今天天气真好"
        assert body["language"] == "Chinese"

    def test_webm_ffmpeg_failure_returns_422(self, client):
        """ffmpeg 转码失败 → 422。"""
        fake_webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 100

        def fake_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stderr = "Invalid data found when processing input"
            return result

        with patch("app.main.subprocess.run", side_effect=fake_subprocess_run):
            resp = client.post(
                "/api/asr",
                files={"audio": ("test.webm", fake_webm, "audio/webm")},
            )
        assert resp.status_code == 422
        assert "ffmpeg" in resp.json()["detail"].lower()

    def test_wav_upload_skips_ffmpeg(self, client):
        """wav 上传不应触发 ffmpeg 转码。"""
        with (
            patch("app.main.subprocess.run") as mock_run,
            patch(
                "app.services.asr_service.Qwen3ASRService.transcribe_file",
                return_value="今天天气真好",
            ),
        ):
            resp = client.post(
                "/api/asr",
                files={"audio": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 200
        mock_run.assert_not_called()
