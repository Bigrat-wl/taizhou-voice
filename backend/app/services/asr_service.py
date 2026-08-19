"""Qwen3-ASR 识别服务（本地模型，CPU / float32）。

封装层：只复用模型权重与官方 transformers 后端（qwen-asr 包提供的
``Qwen3ASRForConditionalGeneration`` / ``Qwen3ASRProcessor``），
识别流程、音频预处理、生命周期管理全部在本服务内从零实现。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from qwen_asr.core.transformers_backend import (
    Qwen3ASRForConditionalGeneration,
    Qwen3ASRProcessor,
)

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # Qwen3-ASR 标准输入采样率
_ASR_TEXT_TAG = "<asr_text>"


class Qwen3ASRService:
    """将音频波形转写为普通话文本。

    线程安全：模型懒加载（带锁），推理串行执行，适合单机演示场景。
    """

    def __init__(
        self,
        model_dir: str | Path = "/home/rat/dialect_asr_system/finetune/output/final",
        device: str = "cpu",
        dtype: torch.dtype = torch.float32,
        max_new_tokens: int = 512,
        language: str = "Chinese",
    ) -> None:
        self.model_dir = Path(model_dir)
        self.device = torch.device(device)
        self.dtype = dtype
        self.max_new_tokens = max_new_tokens
        self.language = language

        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._model: Optional[Qwen3ASRForConditionalGeneration] = None
        self._processor: Optional[Qwen3ASRProcessor] = None

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._processor is not None

    def load(self) -> None:
        """加载本地模型与处理器（幂等，可安全并发调用）。"""
        if self.is_loaded:
            return
        with self._load_lock:
            if self.is_loaded:
                return
            logger.info(
                "Loading Qwen3-ASR from %s (dtype=%s, device=%s)...",
                self.model_dir,
                self.dtype,
                self.device,
            )
            if not self.model_dir.exists():
                raise FileNotFoundError(
                    f"模型目录不存在: {self.model_dir}"
                )
            self._processor = Qwen3ASRProcessor.from_pretrained(
                str(self.model_dir), fix_mistral_regex=True
            )
            self._model = Qwen3ASRForConditionalGeneration.from_pretrained(
                str(self.model_dir),
                dtype=self.dtype,
            ).to(self.device)
            self._model.eval()
            logger.info("Qwen3-ASR loaded (param count=%d).", self._model.num_parameters())

    def unload(self) -> None:
        with self._load_lock:
            self._model = None
            self._processor = None

    def _ensure_loaded(self) -> None:
        if not self.is_loaded:
            self.load()

    # ------------------------------------------------------------------ #
    # 提示词构建
    # ------------------------------------------------------------------ #
    def _build_prompt(self) -> str:
        """构造单轮识别提示词：系统消息 + 音频占位 + 强制目标语种（纯文本输出）。"""
        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]},
        ]
        prompt = self._processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        if self.language:
            prompt = prompt + f"language {self.language}{_ASR_TEXT_TAG}"
        return prompt

    # ------------------------------------------------------------------ #
    # 预处理
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_waveform(
        waveform: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """归一化为 16kHz 单声道 float32 波形，数值范围 [-1, 1]。"""
        wav = np.asarray(waveform, dtype=np.float32)
        if wav.ndim == 2:
            # 兼容 (channels, samples) 或 (samples, channels)
            if wav.shape[0] <= 8 and wav.shape[1] > wav.shape[0]:
                wav = wav.T
            wav = np.mean(wav, axis=-1).astype(np.float32)
        elif wav.ndim != 1:
            raise ValueError(f"不支持的波形维度: {wav.ndim}")

        if sample_rate != SAMPLE_RATE:
            import librosa

            wav = librosa.resample(
                wav, orig_sr=int(sample_rate), target_sr=SAMPLE_RATE
            ).astype(np.float32)

        if wav.size == 0:
            raise ValueError("音频为空")
        peak = float(np.max(np.abs(wav)))
        if peak > 1.0:
            wav = wav / peak
        return np.clip(wav, -1.0, 1.0)

    # ------------------------------------------------------------------ #
    # 推理
    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def transcribe_waveform(
        self, waveform: np.ndarray, sample_rate: int = SAMPLE_RATE
    ) -> str:
        """识别单段波形，返回普通话文本。

        Args:
            waveform: 单声道或多声道 float32 波形。
            sample_rate: 输入波形采样率。

        Returns:
            识别出的普通话文本（去除首尾空白）。
        """
        self._ensure_loaded()
        wav = self.normalize_waveform(waveform, sample_rate)

        prompt = self._build_prompt()
        inputs = self._processor(
            text=prompt, audio=wav, return_tensors="pt", padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        logger.debug("ASR inference start (audio=%.2fs)...", wav.size / SAMPLE_RATE)
        with self._infer_lock:
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
            )
        logger.debug("ASR inference done.")

        # 只解码生成的 token（截掉提示词部分）
        prompt_len = inputs["input_ids"].shape[1]
        generated_ids = outputs.sequences[:, prompt_len:]
        text = self._processor.tokenizer.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return text.strip()

    def transcribe_file(self, audio_path: str | Path) -> str:
        """读取音频文件（任意格式）并识别，自动重采样为 16kHz 单声道。"""
        import librosa

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        wav, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)
        return self.transcribe_waveform(wav, sr)