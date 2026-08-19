"""FastAPI 应用入口：POST /api/asr 音频转普通话文本。"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.asr_service import Qwen3ASRService

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

# 允许的音频扩展名（用于临时文件落盘；解码本身交给 librosa/soundfile）
_ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".wma", ".aac", ".webm"}


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


app = FastAPI(
    title="泰州方言通 ASR 服务",
    description="Qwen3-ASR（本地 CPU / float32）音频转普通话文本",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": asr_service.is_loaded}


@app.post("/api/asr")
def asr(audio: UploadFile = File(...)) -> JSONResponse:
    """接收音频文件，返回普通话识别文本。

    - 请求：multipart/form-data，字段名 `audio`。
    - 响应：``{"text": "<普通话文本>", "language": "Chinese"}``
    """
    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"不支持的音频格式: {suffix}")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="asr_upload_", suffix=suffix, delete=False
        ) as tmp:
            tmp.write(audio.file.read())
            tmp_path = tmp.name

        text = asr_service.transcribe_file(tmp_path)
        if not text:
            raise HTTPException(status_code=422, detail="未识别到有效语音内容")
        return JSONResponse({"text": text, "language": "Chinese"})
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("ASR 识别失败")
        raise HTTPException(status_code=500, detail=f"识别失败: {exc}") from exc
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                logger.warning("临时文件清理失败: %s", tmp_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")