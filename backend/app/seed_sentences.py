"""句子种子数据导入脚本。

从 ``hailing_asr/data/metadata.csv`` 读取句子，写入 ``sentences`` 表。
可重复执行：按（普通话文本）去重，已存在则跳过，不产生重复行。

字段映射（csv 表头：audio_path, text, mandarin_text）：
- sentences.text         <- mandarin_text（普通话列）
- sentences.dialect_text <- text（方言列）
- category / difficulty  该 csv 未提供，取默认值（"" / 1）。

用法：
    uv run python -m app.seed_sentences
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Sentence

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(
    os.getenv("SENTENCES_CSV", "/home/rat/hailing_asr/data/metadata.csv")
)


def load_sentences(csv_path: Path | str = DEFAULT_CSV) -> list[Sentence]:
    """读取 csv，构造（尚未入库的）Sentence 对象列表。"""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"句子源 csv 不存在: {csv_path}")

    sentences: list[Sentence] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dialect = (row.get("text") or "").strip()
            mandarin = (row.get("mandarin_text") or "").strip()
            if not dialect and not mandarin:
                continue  # 跳过空行
            sentences.append(
                Sentence(text=mandarin, dialect_text=dialect, category="", difficulty=1)
            )
    return sentences


def seed(csv_path: Path | str = DEFAULT_CSV) -> int:
    """导入句子到 sentences 表；返回本次新增条数（可重复执行）。

    每个 csv 行对应一条句子（同一句可能被不同说话人录制多次，故含重复文本）。
    幂等策略：同一个 (text, dialect_text) 组合，已入库条数 >= csv 期望条数时跳过，
    只补齐差额——首次运行入库 27 条，重复运行不重复、仍保持 27 条。
    """
    init_db()
    sentences = load_sentences(csv_path)

    # 每个 (text, dialect_text) 组合在 csv 中的期望条数
    desired: dict[tuple[str, str], int] = {}
    for s in sentences:
        key = (s.text, s.dialect_text)
        desired[key] = desired.get(key, 0) + 1

    with SessionLocal() as db:
        existing = db.execute(select(Sentence.text, Sentence.dialect_text)).all()
        from collections import Counter

        got = Counter((t, d) for t, d in existing)

        added = 0
        for (text, dialect), want in desired.items():
            key = (text, dialect)
            missing = want - got.get(key, 0)
            for _ in range(max(missing, 0)):
                db.add(Sentence(text=text, dialect_text=dialect, category="", difficulty=1))
                added += 1
        db.commit()
    return added


if __name__ == "__main__":
    import sys

    added = seed()
    with SessionLocal() as db:
        total = db.query(Sentence).count()
    print(f"新增 {added} 条，sentences 表当前共 {total} 条")
    sys.exit(0)