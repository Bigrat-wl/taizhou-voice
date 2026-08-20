"""方言↔普通话 文本互译服务（基于平行句对的映射规则）。

移植自 dialect_asr_system/translator.py，适配 taizhou-voice 项目结构。

规则提取: 逐字符对齐（difflib）自动发现 方言词↔普通话词 对应，
         可被 translate_overrides.json 人工覆盖。

⚠️ 待优化：当前规则映射方案覆盖范围有限，后续应替换为大模型翻译。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CJK = "\u4e00-\u9fff"


def _norm(s: str) -> str:
    """去掉空白与所有标点，用于整句匹配"""
    return re.sub(
        r"[\s\u3000-\u303f\uff00-\uffef，。！？、；：""''（）《》…—，,.!?;:() \t]+",
        "",
        s,
    )


class TranslateService:
    """方言↔普通话 文本互译服务（基于平行句对的映射规则）。

    线程安全：数据懒加载（带锁），翻译串行执行。
    """

    def __init__(
        self,
        pairs_json: str | Path = "data/translate_pairs.json",
    ) -> None:
        self.pairs_json = Path(pairs_json)
        self._lock = threading.Lock()
        self._data: Optional[dict] = None
        self._mtime: float = 0

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    @property
    def is_loaded(self) -> bool:
        return self._data is not None

    def load(self) -> None:
        """加载翻译数据（幂等，可安全并发调用）。"""
        if self._data is not None:
            return
        with self._lock:
            if self._data is not None:
                return
            self._reload()

    def _reload(self) -> None:
        """重新加载翻译数据。"""
        path = self.pairs_json
        mtime = path.stat().st_mtime if path.exists() else 0
        if self._data is not None and mtime == self._mtime:
            return

        if not path.exists():
            logger.warning("翻译数据文件不存在: %s，翻译功能不可用", path)
            self._data = {
                "pairs": [],
                "rules_dz2zh": {},
                "rules_zh2dz": {},
                "built_at": None,
                "count": 0,
            }
            self._mtime = 0
            return

        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._mtime = mtime
        self._compile()
        logger.info(
            "翻译数据加载完成: %d 句对, %d 条方言→普通话规则, %d 条普通话→方言规则",
            self._data.get("count", 0),
            len(self._data.get("rules_dz2zh", {})),
            len(self._data.get("rules_zh2dz", {})),
        )

    def _compile(self) -> None:
        """预编译精确匹配映射和正则。"""
        d = self._data
        d["_exact_dz2zh"] = {}
        d["_exact_zh2dz"] = {}
        for p in d.get("pairs", []):
            d["_exact_dz2zh"].setdefault(_norm(p["dialect"]), p["mandarin"])
            d["_exact_zh2dz"].setdefault(_norm(p["mandarin"]), p["dialect"])

        # 词级规则正则（最长优先，一趟替换，避免级联）
        for key in ("rules_dz2zh", "rules_zh2dz"):
            rules = d.get(key, {})
            pat = None
            if rules:
                pat = re.compile(
                    "|".join(
                        re.escape(k)
                        for k in sorted(rules.keys(), key=lambda k: -len(k))
                    )
                )
            d["_" + key + "_re"] = pat

    def unload(self) -> None:
        """卸载翻译数据。"""
        with self._lock:
            self._data = None
            self._mtime = 0

    # ------------------------------------------------------------------ #
    # 翻译
    # ------------------------------------------------------------------ #
    def translate(self, text: str, direction: str = "dz2zh") -> dict:
        """翻译文本。

        Args:
            text: 源文本。
            direction: 'dz2zh' 方言→普通话 | 'zh2dz' 普通话→方言。

        Returns:
            {
                "success": bool,
                "source": str,  # 源文本
                "target": str,  # 目标文本
                "exact": bool,  # 是否整句精确匹配
                "applied": [{"from": str, "to": str}],  # 应用的规则
            }
        """
        text = (text or "").strip()
        if not text:
            return {"success": False, "error": "文本为空", "source": "", "target": ""}
        if direction not in ("dz2zh", "zh2dz"):
            return {
                "success": False,
                "error": "direction 必须为 dz2zh 或 zh2dz",
                "source": text,
                "target": "",
            }

        self.load()
        d = self._data

        if direction == "dz2zh":
            exact_map = d.get("_exact_dz2zh", {})
            rules = d.get("rules_dz2zh", {})
            pat_key = "_rules_dz2zh_re"
        else:
            exact_map = d.get("_exact_zh2dz", {})
            rules = d.get("rules_zh2dz", {})
            pat_key = "_rules_zh2dz_re"

        # 1) 整句精确匹配（忽略空格与末尾标点差异）
        key = _norm(text)
        if key in exact_map:
            return {
                "success": True,
                "source": text,
                "target": exact_map[key],
                "exact": True,
                "applied": [],
            }

        # 2) 词级规则替换
        pat = d.get(pat_key)
        applied = []
        if pat:

            def _repl(m):
                applied.append({"from": m.group(0), "to": rules[m.group(0)]})
                return rules[m.group(0)]

            target = pat.sub(_repl, text)
        else:
            target = text

        return {
            "success": True,
            "source": text,
            "target": target,
            "exact": False,
            "applied": applied,
        }

    def translate_dialect_to_mandarin(self, dialect_text: str) -> dict:
        """方言→普通话翻译（便捷方法）。"""
        return self.translate(dialect_text, direction="dz2zh")

    # ------------------------------------------------------------------ #
    # 数据查询
    # ------------------------------------------------------------------ #
    def get_pairs(self, limit: int = 200) -> dict:
        """获取平行句对（供前端展示或调试）。"""
        self.load()
        d = self._data
        pairs = [
            {
                "audio": p.get("audio"),
                "dialect": p["dialect"],
                "mandarin": p["mandarin"],
            }
            for p in d.get("pairs", [])
        ]
        return {
            "count": len(pairs),
            "built_at": d.get("built_at"),
            "source_csv": d.get("source_csv"),
            "rules_dz2zh": d.get("rules_dz2zh", {}),
            "rules_zh2dz": d.get("rules_zh2dz", {}),
            "pairs": pairs[:limit],
        }

    def get_stats(self) -> dict:
        """获取翻译数据统计。"""
        self.load()
        d = self._data
        return {
            "count": d.get("count", 0),
            "rules_dz2zh": len(d.get("rules_dz2zh", {})),
            "rules_zh2dz": len(d.get("rules_zh2dz", {})),
            "built_at": d.get("built_at"),
            "is_loaded": self.is_loaded,
        }
