"""FastAPI 应用入口：POST /api/asr 音频转普通话文本。"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Sentence
from app.routers.auth import router as auth_router
from app.routers.score import router as score_router
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

# CORS：开发期放开本地来源（Nuxt 前端 3000 等）；生产环境再收紧
CORS_ALLOW_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost",
    "http://127.0.0.1",
]


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 认证路由：/api/auth/register、/api/auth/login
app.include_router(auth_router)
# 评分路由：/api/score（需登录）
app.include_router(score_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": asr_service.is_loaded}


MAX_SENTENCES = 50  # 单次最多返回条数（上限限制）


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