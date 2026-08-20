"""FastAPI 应用入口：POST /api/asr 音频转普通话文本。"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Sentence
from app.routers.auth import router as auth_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.score import router as score_router
from app.routers.tts import router as tts_router
from app.services.asr_service import Qwen3ASRService
from app.services.translate_service import TranslateService
from app.services.tts_service import CosyVoice2Service

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.getenv(
    "QWEN3_ASR_MODEL_DIR", "/home/rat/dialect_asr_system/finetune/output/final"
)
DEVICE = os.getenv("ASR_DEVICE", "cpu")
MAX_NEW_TOKENS = int(os.getenv("ASR_MAX_NEW_TOKENS", "512"))

asr_service = Qwen3ASRService(
    model_dir=MODEL_DIR,
    device=DEVICE,
    max_new_tokens=MAX_NEW_TOKENS,
)

# TTS 服务：CosyVoice2（仅 GPU 环境可用，懒加载）
TTS_MODEL_DIR = os.getenv(
    "TTS_MODEL_DIR", "/home/rat/dialect_asr_system/tts/output/final"
)
TTS_DEVICE = os.getenv("TTS_DEVICE", "cuda")

tts_service = CosyVoice2Service(
    model_dir=TTS_MODEL_DIR,
    device=TTS_DEVICE,
)

# 翻译服务：方言↔普通话 文本互译（基于平行句对的规则映射）
TRANSLATE_PAIRS_JSON = os.getenv(
    "TRANSLATE_PAIRS_JSON",
    str(Path(__file__).resolve().parent.parent / "data" / "translate_pairs.json"),
)

translate_service = TranslateService(pairs_json=TRANSLATE_PAIRS_JSON)

# 允许的音频扩展名（用于临时文件落盘；解码本身交给 librosa/soundfile）
_ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".wma", ".aac", ".webm"}

# CORS：开发期放开本地来源（Nuxt 前端 3000 等）；生产环境再收紧
CORS_ALLOW_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost",
    "http://127.0.0.1",
]

# 静态文件目录：backend/data/audio/
AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时后台预热模型，避免首个请求等待过久；失败不阻塞启动，请求时再懒加载
    try:
        import threading

        threading.Thread(target=asr_service.load, name="asr-warmup", daemon=True).start()
    except Exception:  # pragma: no cover
        logger.exception("模型预热失败，将在首个请求时重新加载")
    yield
    asr_service.unload()
    tts_service.unload()
    translate_service.unload()


app = FastAPI(
    title="泰州方言通 ASR 服务",
    description="Qwen3-ASR（本地 CPU / float32）音频转普通话文本",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 确保音频目录存在并挂载静态文件服务
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/data/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

# 认证路由：/api/auth/register、/api/auth/login
app.include_router(auth_router)
# 排行榜/点赞/句子录音路由
app.include_router(leaderboard_router)
# 评分路由：/api/score（需登录）
app.include_router(score_router)
# 语音合成路由：/api/tts（无需认证）
app.include_router(tts_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": asr_service.is_loaded,
        "tts_loaded": tts_service.is_loaded,
    }


MAX_SENTENCES = 50  # 单次最多返回条数（上限限制）

# 需要 ffmpeg 转码的格式（libsndfile/librosa 不支持）
_FFMPEG_ONLY_SUFFIXES = {".webm", ".ogg", ".m4a", ".aac", ".wma"}


def _ensure_wav(src_path: str, src_suffix: str) -> str:
    """确保音频文件为 wav 格式；非 wav 时用 ffmpeg 转为 16kHz 单声道 wav。

    Returns:
        wav 文件路径（src_path 本身已是 wav 时原样返回，否则为新临时文件路径）。

    Raises:
        RuntimeError: ffmpeg 转码失败。
    """
    if src_suffix == ".wav":
        return src_path

    if src_suffix in _FFMPEG_ONLY_SUFFIXES:
        wav_path = src_path + ".wav"
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg 转码失败（{src_suffix} → wav）: {result.stderr[:500]}"
            )
        return wav_path

    # 其他格式（mp3/flac 等）：librosa 本身支持，直接用原文件
    return src_path


@app.get("/api/sentences")
def get_sentences(
    n: int = Query(default=5, ge=1, description="返回句子条数"),
    db: Session = Depends(get_db),
) -> dict:
    """从 sentences 表随机取 N 句（挑战赛用）。

    默认 n=5，上限 MAX_SENTENCES（50）。
    响应：``{"sentences": [{"id":..,"text":..,"dialect_text":..}, ...]}``
    """
    n = min(n, MAX_SENTENCES)
    rows = db.execute(
        select(Sentence).order_by(func.random()).limit(n)
    ).scalars().all()
    return {
        "sentences": [
            {"id": s.id, "text": s.text, "dialect_text": s.dialect_text}
            for s in rows
        ]
    }


@app.post("/api/asr")
def asr(audio: UploadFile = File(...)) -> JSONResponse:
    """接收音频文件，返回识别结果（谐音字 + 普通话翻译）。

    - 请求：multipart/form-data，字段名 `audio`。
    - 响应：``{"text": "<谐音字>", "mandarin": "<普通话>", "language": "Chinese"}``
    """
    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"不支持的音频格式: {suffix}")

    tmp_path: str | None = None
    wav_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="asr_upload_", suffix=suffix, delete=False
        ) as tmp:
            tmp.write(audio.file.read())
            tmp_path = tmp.name

        # webm/opus 等格式需要 ffmpeg 转码后再识别
        wav_path = _ensure_wav(tmp_path, suffix)
        text = asr_service.transcribe_file(wav_path)
        if not text:
            raise HTTPException(status_code=422, detail="未识别到有效语音内容")

        # 方言→普通话翻译
        mandarin = ""
        tr_result = translate_service.translate_dialect_to_mandarin(text)
        if tr_result.get("success"):
            mandarin = tr_result.get("target", "")

        return JSONResponse({
            "text": text,       # 谐音字（ASR 原始输出）
            "mandarin": mandarin,  # 普通话翻译
            "language": "Chinese",
        })
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("ASR 识别失败")
        raise HTTPException(status_code=500, detail=f"识别失败: {exc}") from exc
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                logger.warning("临时文件清理失败: %s", tmp_path)
        if wav_path and wav_path != tmp_path:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                logger.warning("临时 wav 文件清理失败: %s", wav_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")