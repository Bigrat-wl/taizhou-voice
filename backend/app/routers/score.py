"""评分路由：POST /api/score（需登录）。

上传录音 → ASR 识别 → 与参考文本比对打分 → 录音落盘 + 存 recordings → 返回分数。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Recording, Sentence, User
from app.security import get_current_user
from app.services.asr_service import Qwen3ASRService
from app.services.scoring_service import compute_similarity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["score"])

# 录音落盘目录：backend/data/audio/
AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio"

# 允许的音频扩展名（与 /api/asr 保持一致）
_ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".wma", ".aac", ".webm"}

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


def _get_asr_service() -> Qwen3ASRService:
    """从 main 模块获取已初始化的 ASR 服务实例（延迟导入避免循环）。"""
    from app.main import asr_service

    return asr_service


@router.post("/score", summary="上传录音 → 识别 → 比对打分")
def score(
    audio: UploadFile = File(..., description="用户录音"),
    sentence_id: int = Form(..., description="对应句子 id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """挑战赛评分：上传录音 → ASR 识别 → 与参考文本比对 → 存录音+分数。

    响应：``{"score": 87, "transcript": "今天天气真好", "reference": "今天天气真好"}``
    """
    # 1. 校验句子存在
    sentence = db.execute(
        select(Sentence).where(Sentence.id == sentence_id)
    ).scalar_one_or_none()
    if sentence is None:
        raise HTTPException(status_code=400, detail="句子不存在")

    # 2. 校验音频格式
    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"不支持的音频格式: {suffix}")

    # 3. 临时落盘上传文件 → ASR 识别
    tmp_path: str | None = None
    wav_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="score_upload_", suffix=suffix, delete=False
        ) as tmp:
            tmp.write(audio.file.read())
            tmp_path = tmp.name

        # webm/opus 等格式需要 ffmpeg 转码后再识别
        wav_path = _ensure_wav(tmp_path, suffix)

        asr_service = _get_asr_service()
        transcript = asr_service.transcribe_file(wav_path)

        if not transcript:
            raise HTTPException(status_code=422, detail="未识别到有效语音内容")

        # 4. 计算相似度分数
        score_val = compute_similarity(transcript, sentence.text)

        # 5. 录音落盘：backend/data/audio/{sentence_id}_{user_id}_{ts}.wav
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d%H%M%S")
        audio_filename = f"{sentence_id}_{user.id}_{ts}.wav"
        audio_dest = AUDIO_DIR / audio_filename

        # 将上传文件转为 WAV（统一 16kHz 单声道）并保存
        _convert_to_wav(wav_path, str(audio_dest))

        # 6. 存 recordings 表
        recording = Recording(
            sentence_id=sentence_id,
            user_id=user.id,
            audio_path=f"audio/{audio_filename}",
            score=score_val,
        )
        db.add(recording)

        # 7. 累加用户总分
        user.total_score = (user.total_score or 0) + score_val
        db.commit()

        return {
            "score": score_val,
            "transcript": transcript,
            "reference": sentence.text,
        }

    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("评分失败")
        raise HTTPException(status_code=500, detail=f"评分失败: {exc}") from exc
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("临时文件清理失败: %s", tmp_path)
        if wav_path and wav_path != tmp_path:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("临时 wav 文件清理失败: %s", wav_path)


def _convert_to_wav(src_path: str, dest_path: str) -> None:
    """将任意音频格式转换为 16kHz 单声道 WAV 并保存到目标路径。

    如果源文件已经是 WAV，则直接复制；否则用 ffmpeg 转码。
    注意：webm/ogg 等格式应在调用前先经过 _ensure_wav() 处理，
    本函数主要处理 mp3/flac 等 librosa 支持的格式以及已转换的 wav。
    """
    src_suffix = Path(src_path).suffix.lower()
    if src_suffix == ".wav":
        # 已是 WAV，直接复制
        shutil.copy2(src_path, dest_path)
        return

    # 非 wav 格式：用 ffmpeg 转为 16kHz 单声道 wav
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", dest_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 转码失败（{src_suffix} → wav）: {result.stderr[:500]}"
        )
