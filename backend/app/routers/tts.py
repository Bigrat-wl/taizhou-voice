"""语音合成路由：POST /api/tts（无需认证）。

文本 → CosyVoice2 合成 → 音频落盘 → 返回 audio_url。
模型未加载时返回 503。
"""

from __future__ import annotations

import logging
import soundfile as sf
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.tts_service import CosyVoice2Service, MAX_TEXT_LENGTH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tts"])

# TTS 音频落盘目录：backend/data/audio/
AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio"


class TTSRequest(BaseModel):
    """TTS 请求体。"""
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH, description="待合成文本")


class TTSResponse(BaseModel):
    """TTS 响应体。"""
    audio_url: str = Field(..., description="合成音频的相对 URL")


def _get_tts_service() -> CosyVoice2Service:
    """从 main 模块获取已初始化的 TTS 服务实例（延迟导入避免循环）。"""
    from app.main import tts_service
    return tts_service


@router.post(
    "/tts",
    response_model=TTSResponse,
    summary="文本 → 方言音频（CosyVoice2）",
)
def synthesize_tts(request: TTSRequest) -> TTSResponse:
    """将文本合成为方言音频并落盘。

    - 请求：JSON `{"text": "今朝天气老好"}`（text 必填，≤200 字）
    - 响应 200：`{"audio_url": "/data/audio/tts_xxx.wav"}`
    - 响应 503：TTS 模型未加载（GPU 不可用等）
    """
    tts_service = _get_tts_service()

    # 检查模型是否可用
    if not tts_service.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="TTS 模型未加载，请确保 GPU 可用且模型文件已就位"
        )

    # 文本校验
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"文本长度超过限制（最大 {MAX_TEXT_LENGTH} 字）"
        )

    try:
        # 合成音频
        waveform, sample_rate = tts_service.synthesize(text)

        # 音频落盘：backend/data/audio/tts_{ts}.wav
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d%H%M%S%f")
        audio_filename = f"tts_{ts}.wav"
        audio_dest = AUDIO_DIR / audio_filename

        # 保存为 16kHz 单声道 WAV（统一格式）
        sf.write(str(audio_dest), waveform, sample_rate, subtype="PCM_16")

        logger.info("TTS 合成成功: %s (%.2fs)", audio_filename, len(waveform) / sample_rate)

        return TTSResponse(audio_url=f"/data/audio/{audio_filename}")

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS 合成失败")
        raise HTTPException(status_code=500, detail=f"TTS 合成失败: {exc}") from exc
