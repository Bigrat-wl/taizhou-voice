"""POST /api/tts 接口测试（mock TTS 模型，不加载真实模型）。

覆盖：
- 模型未加载 → 503
- 文本为空 → 400
- 文本超长 → 400
- 成功合成 → 200 + audio_url
- 音频落盘到 backend/data/audio/tts_*.wav
- 合成失败 → 500
- CPU 回退（pyttsx3）路径
"""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    yield TestClient(app)


def _fake_waveform(duration_s: float = 0.1, sample_rate: int = 22050) -> np.ndarray:
    """生成一个简单的正弦波作为合成音频。"""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


class TestTTSModelNotLoaded:
    """模型未加载时的返回。"""

    def test_returns_503_when_model_not_loaded(self, client):
        """模型未加载 → 503。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = False
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "今朝天气老好"},
            )
        assert resp.status_code == 503
        assert "TTS 模型未加载" in resp.json()["detail"]


class TestTTSTextValidation:
    """文本校验。"""

    def test_empty_text_returns_400(self, client):
        """空文本 → 400。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": ""},
            )
        assert resp.status_code == 422  # Pydantic 校验 (min_length=1)

    def test_whitespace_only_text_returns_400(self, client):
        """纯空格文本 → 400（strip 后为空）。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.side_effect = ValueError("文本不能为空")
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "   "},
            )
        assert resp.status_code == 400
        assert "文本不能为空" in resp.json()["detail"]

    def test_text_over_limit_returns_400(self, client):
        """文本超长 → 400。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_get.return_value = mock_service

            long_text = "这" * 201
            resp = client.post(
                "/api/tts",
                json={"text": long_text},
            )
        assert resp.status_code == 422  # Pydantic 校验 (max_length=200)


class TestTTSSuccess:
    """成功合成测试。"""

    def test_success_returns_200_with_audio_url(self, client, tmp_path):
        """成功合成 → 200 + audio_url。"""
        fake_waveform = _fake_waveform()

        with patch("app.routers.tts._get_tts_service") as mock_get, \
             patch("app.routers.tts.AUDIO_DIR", tmp_path):
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.return_value = (fake_waveform, 22050)
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "今朝天气老好"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "audio_url" in body
        assert body["audio_url"].startswith("/data/audio/tts_")
        assert body["audio_url"].endswith(".wav")

    def test_audio_saved_to_disk(self, client, tmp_path):
        """合成音频落盘到 backend/data/audio/tts_*.wav。"""
        fake_waveform = _fake_waveform()

        with patch("app.routers.tts._get_tts_service") as mock_get, \
             patch("app.routers.tts.AUDIO_DIR", tmp_path):
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.return_value = (fake_waveform, 22050)
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "今朝天气老好"},
            )
        assert resp.status_code == 200
        audio_files = list(tmp_path.glob("tts_*.wav"))
        assert len(audio_files) == 1
        # 验证文件是有效的 WAV
        import soundfile as sf
        data, sr = sf.read(str(audio_files[0]))
        assert sr == 22050
        assert len(data) > 0

    def test_text_is_trimmed(self, client, tmp_path):
        """文本首尾空格被去除。"""
        fake_waveform = _fake_waveform()

        with patch("app.routers.tts._get_tts_service") as mock_get, \
             patch("app.routers.tts.AUDIO_DIR", tmp_path):
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.return_value = (fake_waveform, 22050)
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "  今朝天气老好  "},
            )
        assert resp.status_code == 200
        # synthesize 被调用时文本已 strip
        mock_service.synthesize.assert_called_once_with("今朝天气老好")


class TestTTSSynthesisFailure:
    """合成失败测试。"""

    def test_synthesis_error_returns_500(self, client):
        """合成过程抛出异常 → 500。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.side_effect = RuntimeError("GPU 显存不足")
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "今朝天气老好"},
            )
        assert resp.status_code == 500
        assert "GPU 显存不足" in resp.json()["detail"]

    def test_empty_synthesis_result_returns_500(self, client):
        """合成返回空结果 → 500。"""
        with patch("app.routers.tts._get_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_loaded = True
            mock_service.synthesize.side_effect = RuntimeError("TTS 合成返回空结果")
            mock_get.return_value = mock_service

            resp = client.post(
                "/api/tts",
                json={"text": "今朝天气老好"},
            )
        assert resp.status_code == 500
        assert "空结果" in resp.json()["detail"]


class TestTTSServiceUnit:
    """CosyVoice2Service 单元测试（纯 mock，不加载模型）。"""

    def test_is_loaded_initially_false(self):
        """初始状态 is_loaded 为 False。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        assert service.is_loaded is False

    def test_engine_initially_none(self):
        """初始状态 engine 为 'none'。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        assert service.engine == "none"

    def test_gpu_available_loads_cosyvoice2(self):
        """GPU 可用时加载 CosyVoice2 引擎。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")

        mock_model = MagicMock()
        with patch("app.services.tts_service.CosyVoice2Service.is_gpu_available", new_callable=PropertyMock, return_value=True), \
             patch("app.services.tts_service.CosyVoice2Service._load_cosyvoice2") as mock_load:
            mock_load.side_effect = lambda: setattr(service, '_model', mock_model) or setattr(service, '_engine', 'cosyvoice2')
            service.load()

        # 应该调用 _load_cosyvoice2
        mock_load.assert_called_once()

    def test_load_no_gpu_fallback_to_pyttsx3(self):
        """无 GPU 时回退到 pyttsx3 引擎。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")

        mock_pyttsx3_engine = MagicMock()
        with patch("app.services.tts_service.CosyVoice2Service.is_gpu_available", new_callable=PropertyMock, return_value=False), \
             patch("app.services.tts_service.CosyVoice2Service._load_pyttsx3") as mock_load:
            mock_load.side_effect = lambda: setattr(service, '_pyttsx3_engine', mock_pyttsx3_engine) or setattr(service, '_engine', 'pyttsx3')
            service.load()

        # 应该调用 _load_pyttsx3
        mock_load.assert_called_once()

    def test_load_cosyvoice2_fails_fallback_to_pyttsx3(self):
        """CosyVoice2 加载失败时回退到 pyttsx3。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")

        mock_pyttsx3_engine = MagicMock()
        with patch("app.services.tts_service.CosyVoice2Service.is_gpu_available", new_callable=PropertyMock, return_value=True), \
             patch("app.services.tts_service.CosyVoice2Service._load_cosyvoice2", side_effect=RuntimeError("模型文件缺失")), \
             patch("app.services.tts_service.CosyVoice2Service._load_pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.side_effect = lambda: setattr(service, '_pyttsx3_engine', mock_pyttsx3_engine) or setattr(service, '_engine', 'pyttsx3')
            service.load()

        # CosyVoice2 加载失败后应该尝试 pyttsx3
        mock_pyttsx3.assert_called_once()

    def test_synthesize_empty_text(self):
        """空文本抛出 ValueError。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        with pytest.raises(ValueError, match="文本不能为空"):
            service.synthesize("")

    def test_synthesize_whitespace_only(self):
        """纯空格文本抛出 ValueError。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        with pytest.raises(ValueError, match="文本不能为空"):
            service.synthesize("   ")

    def test_synthesize_text_over_limit(self):
        """超长文本抛出 ValueError。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        long_text = "这" * 201
        with pytest.raises(ValueError, match="文本长度超过限制"):
            service.synthesize(long_text)

    def test_synthesize_model_not_loaded(self):
        """引擎未加载时合成抛出 RuntimeError。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        # 引擎未加载，synthesis 会尝试加载，然后失败
        with patch.object(service, '_ensure_loaded', side_effect=RuntimeError("TTS 引擎加载失败")):
            with pytest.raises(RuntimeError, match="TTS 引擎加载失败"):
                service.synthesize("今朝天气老好")

    def test_synthesize_cosyvoice2_engine(self):
        """CosyVoice2 引擎合成测试（mock）。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")

        # 模拟 CosyVoice2 引擎
        mock_model = MagicMock()
        fake_waveform = _fake_waveform()
        mock_model.inference_sft.return_value = [
            {"tts_speech": fake_waveform}
        ]

        service._model = mock_model
        service._engine = "cosyvoice2"
        service._sample_rate = 22050

        waveform, sr = service.synthesize("测试文本")
        assert sr == 22050
        assert len(waveform) > 0
        mock_model.inference_sft.assert_called_once()

    def test_synthesize_pyttsx3_engine(self):
        """pyttsx3 引擎合成测试（mock）。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")

        # 模拟 pyttsx3 引擎
        mock_pyttsx3_engine = MagicMock()
        service._pyttsx3_engine = mock_pyttsx3_engine
        service._engine = "pyttsx3"
        service._sample_rate = 22050

        # mock soundfile.read 返回一个假波形
        fake_waveform = _fake_waveform(duration_s=0.1, sample_rate=22050)
        with patch("soundfile.read", return_value=(fake_waveform, 22050)):
            waveform, sr = service.synthesize("测试文本")

        assert sr == 22050
        assert len(waveform) > 0
        mock_pyttsx3_engine.save_to_file.assert_called_once()
        mock_pyttsx3_engine.runAndWait.assert_called_once()

    def test_unload_clears_model(self):
        """卸载后 is_loaded 变为 False。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        # 模拟模型已加载
        service._model = MagicMock()
        assert service.is_loaded is True
        service.unload()
        assert service.is_loaded is False
        assert service.engine == "none"

    def test_unload_stops_pyttsx3(self):
        """卸载时停止 pyttsx3 引擎。"""
        from app.services.tts_service import CosyVoice2Service
        service = CosyVoice2Service(model_dir="/nonexistent/path")
        mock_pyttsx3_engine = MagicMock()
        service._pyttsx3_engine = mock_pyttsx3_engine
        service._engine = "pyttsx3"
        assert service.is_loaded is True
        service.unload()
        mock_pyttsx3_engine.stop.assert_called_once()
        assert service.is_loaded is False
