"""CosyVoice2 语音合成服务（GPU）+ pyttsx3 CPU 回退。

封装层：
- GPU 可用时加载 CosyVoice2（AutoModel），走 inference_sft 合成方言语音。
- GPU 不可用时 fallback 到 pyttsx3（系统 TTS），走 save_to_file 读回 wav。
- 外部接口不变：synthesize(text) → (waveform, sample_rate)。
"""

from __future__ import annotations

import logging
import tempfile
import threading
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050  # CosyVoice2 默认输出采样率
MAX_TEXT_LENGTH = 200  # 契约约定最大文本长度


class CosyVoice2Service:
    """将文本合成为方言音频波形。

    线程安全：模型懒加载（带锁），推理串行执行，适合单机演示场景。

    后端引擎：
    - GPU 可用：CosyVoice2（AutoModel），方言语音合成。
    - GPU 不可用：pyttsx3（系统 TTS），CPU 回退，无方言效果但功能可用。

    调用方可通过 is_loaded 判断是否可用，通过 engine 属性判断当前引擎。
    """

    def __init__(
        self,
        model_dir: str | Path = "/home/rat/dialect_asr_system/tts/output/final",
        device: str = "cuda",
    ) -> None:
        self.model_dir = Path(model_dir)
        self.device = device

        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._model = None  # CosyVoice2 实例（GPU 模式）
        self._pyttsx3_engine = None  # pyttsx3 实例（CPU 回退模式）
        self._engine: str = "none"  # "cosyvoice2" | "pyttsx3" | "none"

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    @property
    def is_loaded(self) -> bool:
        """模型是否已加载并可用（GPU 或 CPU 回退引擎均可）。"""
        return self._model is not None or self._pyttsx3_engine is not None

    @property
    def engine(self) -> str:
        """当前使用的引擎名称：'cosyvoice2' | 'pyttsx3' | 'none'。"""
        return self._engine

    @property
    def is_gpu_available(self) -> bool:
        """检查 CUDA 是否可用。"""
        import torch
        return torch.cuda.is_available()

    def load(self) -> None:
        """加载 TTS 引擎（幂等，可安全并发调用）。

        策略：
        1. GPU 可用 → 尝试加载 CosyVoice2（AutoModel）。
        2. CosyVoice2 加载失败或 GPU 不可用 → fallback 到 pyttsx3。
        3. pyttsx3 也失败 → 抛出 RuntimeError。

        Raises:
            RuntimeError: 所有引擎均加载失败。
            FileNotFoundError: GPU 模式下模型目录不存在。
        """
        if self.is_loaded:
            return
        with self._load_lock:
            if self.is_loaded:
                return

            # 尝试 GPU 路径：CosyVoice2
            if self.is_gpu_available:
                try:
                    self._load_cosyvoice2()
                    return
                except Exception as exc:
                    logger.warning(
                        "CosyVoice2 加载失败，回退到 pyttsx3: %s", exc
                    )
                    # 清理可能的半加载状态
                    self._model = None

            # CPU 回退路径：pyttsx3
            try:
                self._load_pyttsx3()
            except Exception as exc:
                raise RuntimeError(
                    f"TTS 引擎加载失败（CosyVoice2 + pyttsx3 均不可用）: {exc}"
                ) from exc

    def _load_cosyvoice2(self) -> None:
        """加载 CosyVoice2 模型（GPU 专属）。"""
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"TTS 模型目录不存在: {self.model_dir}"
            )

        logger.info(
            "Loading CosyVoice2 from %s (device=%s)...",
            self.model_dir,
            self.device,
        )

        try:
            # 延迟导入 CosyVoice2（仅 GPU 环境需要）
            from cosyvoice.cli.cosyvoice import CosyVoice
            import cosyvoice.sample_rate

            self._model = CosyVoice(str(self.model_dir))
            self._sample_rate = cosyvoice.sample_rate
            self._engine = "cosyvoice2"
            logger.info(
                "CosyVoice2 loaded successfully from %s (sample_rate=%d).",
                self.model_dir,
                self._sample_rate,
            )

        except ImportError as exc:
            raise RuntimeError(
                f"CosyVoice2 依赖未安装: {exc}"
            ) from exc

    def _load_pyttsx3(self) -> None:
        """加载 pyttsx3 引擎（CPU 回退）。"""
        logger.info("Loading pyttsx3 TTS engine (CPU fallback)...")

        try:
            import pyttsx3

            self._pyttsx3_engine = pyttsx3.init()
            self._sample_rate = 22050  # pyttsx3 默认输出采样率（因系统而异）
            self._engine = "pyttsx3"
            logger.info("pyttsx3 TTS engine loaded successfully.")

        except ImportError as exc:
            raise RuntimeError(
                f"pyttsx3 未安装，请运行: uv pip install pyttsx3 — {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"pyttsx3 初始化失败: {exc}"
            ) from exc

    def unload(self) -> None:
        """卸载所有引擎，释放资源。"""
        with self._load_lock:
            if self._model is not None:
                del self._model
                self._model = None
            if self._pyttsx3_engine is not None:
                try:
                    self._pyttsx3_engine.stop()
                except Exception:  # pragma: no cover
                    pass
                self._pyttsx3_engine = None
            self._engine = "none"
            logger.info("TTS engine unloaded.")

    def _ensure_loaded(self) -> None:
        """确保引擎已加载，未加载则尝试加载。"""
        if not self.is_loaded:
            self.load()

    # ------------------------------------------------------------------ #
    # 合成
    # ------------------------------------------------------------------ #
    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """将文本合成为音频波形。

        Args:
            text: 待合成的文本（≤200 字）。

        Returns:
            (waveform, sample_rate)：合成的音频波形和采样率。

        Raises:
            ValueError: 文本为空或超过长度限制。
            RuntimeError: 所有引擎均不可用或合成失败。
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"文本长度超过限制（最大 {MAX_TEXT_LENGTH} 字）")

        self._ensure_loaded()

        with self._infer_lock:
            if self._engine == "cosyvoice2":
                return self._synthesize_cosyvoice2(text)
            elif self._engine == "pyttsx3":
                return self._synthesize_pyttsx3(text)
            else:
                raise RuntimeError("TTS 引擎未加载")

    def _synthesize_cosyvoice2(self, text: str) -> tuple[np.ndarray, int]:
        """CosyVoice2 合成路径（GPU）。"""
        import torch

        try:
            logger.debug("CosyVoice2 inference start (text=%.20s...).", text)

            # CosyVoice2 合成：文本 → 音频波形
            # inference_sft 用于微调说话人，inference_zero_shot 用于零样本克隆
            # 先尝试 inference_sft，失败则 inference_zero_shot
            audio_chunks = []

            # 尝试 inference_sft（微调说话人）
            try:
                for chunk in self._model.inference_sft(
                    tts_text=text,
                    spk_id="default",  # 使用默认说话人
                ):
                    audio_chunks.extend(self._extract_audio_chunks(chunk))
            except (AttributeError, TypeError):
                # inference_sft 不可用，尝试 inference_zero_shot
                logger.debug("inference_sft 不可用，尝试 inference_zero_shot")
                for chunk in self._model.inference_zero_shot(
                    tts_text=text,
                    prompt_text="",
                    prompt_speech=torch.zeros(1, 16000),  # 空白 prompt
                ):
                    audio_chunks.extend(self._extract_audio_chunks(chunk))

            if not audio_chunks:
                raise RuntimeError("CosyVoice2 合成返回空结果")

            # 拼接所有 chunk
            waveform = np.concatenate(audio_chunks, axis=-1).flatten().astype(np.float32)

            # 归一化到 [-1, 1]
            peak = float(np.max(np.abs(waveform)))
            if peak > 1.0:
                waveform = waveform / peak
            waveform = np.clip(waveform, -1.0, 1.0)

            logger.debug(
                "CosyVoice2 inference done (%.2fs audio).",
                waveform.size / self._sample_rate,
            )
            return waveform, self._sample_rate

        except Exception as exc:
            logger.exception("CosyVoice2 合成失败")
            raise RuntimeError(f"CosyVoice2 合成失败: {exc}") from exc

    def _extract_audio_chunks(self, chunk) -> list[np.ndarray]:
        """从 CosyVoice2 返回的 chunk 中提取音频数据。"""
        import torch

        chunks = []
        if isinstance(chunk, dict) and "tts_speech" in chunk:
            speech_tensor = chunk["tts_speech"]
            if isinstance(speech_tensor, torch.Tensor):
                chunks.append(speech_tensor.cpu().numpy())
            elif isinstance(speech_tensor, np.ndarray):
                chunks.append(speech_tensor)
        elif isinstance(chunk, (torch.Tensor, np.ndarray)):
            if isinstance(chunk, torch.Tensor):
                chunks.append(chunk.cpu().numpy())
            else:
                chunks.append(chunk)
        return chunks

    def _synthesize_pyttsx3(self, text: str) -> tuple[np.ndarray, int]:
        """pyttsx3 合成路径（CPU 回退）。"""
        import soundfile as sf

        try:
            logger.debug("pyttsx3 inference start (text=%.20s...).", text)

            # pyttsx3 合成：文本 → wav 文件 → 读回 numpy
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="tts_pyttsx3_"
            ) as tmp:
                tmp_path = tmp.name

            try:
                self._pyttsx3_engine.save_to_file(text, tmp_path)
                self._pyttsx3_engine.runAndWait()

                # 读回 wav 文件
                waveform, sample_rate = sf.read(tmp_path, dtype="float32")

                # 确保单声道
                if waveform.ndim > 1:
                    waveform = waveform[:, 0]

                # 归一化到 [-1, 1]
                peak = float(np.max(np.abs(waveform)))
                if peak > 1.0:
                    waveform = waveform / peak
                waveform = np.clip(waveform, -1.0, 1.0)

                logger.debug(
                    "pyttsx3 inference done (%.2fs audio, sr=%d).",
                    waveform.size / sample_rate,
                    sample_rate,
                )
                return waveform, sample_rate

            finally:
                # 清理临时文件
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:  # pragma: no cover
                    pass

        except Exception as exc:
            logger.exception("pyttsx3 合成失败")
            raise RuntimeError(f"pyttsx3 合成失败: {exc}") from exc
