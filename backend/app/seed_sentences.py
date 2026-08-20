"""句子种子数据导入脚本（v2：去重 + 方言录音表）。

从 metadata.csv 读取句子：
1. 按普通话文本去重，写入 sentences 表（7 条唯一句）
2. 全部 27 条方言录音写入 dialect_recordings 表，关联到对应句子

字段映射（csv 表头：audio_path, text, mandarin_text）：
- sentences.text         <- mandarin_text（普通话）
- sentences.dialect_text <- text（方言，取第一条作为参考版本）
- dialect_recordings.sentence_id <- 关联到对应句子
- dialect_recordings.audio_path  <- audio_path
- dialect_recordings.speaker     <- 从文件名提取（如"陈5"）
- dialect_recordings.dialect_text <- text（方言）

幂等：按 mandarin_text 判断句子是否已存在，按 (sentence_id, audio_path) 判断录音是否已存在。
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import DialectRecording, Sentence

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(
    os.getenv("SENTENCES_CSV", "/home/rat/hailing_asr/data/metadata.csv")
)


def seed(csv_path: Path | str = DEFAULT_CSV) -> dict:
    """导入句子和方言录音；返回统计信息。"""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"句子源 csv 不存在: {csv_path}")

    init_db()

    # 读取 csv
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dialect = (row.get("text") or "").strip()
            mandarin = (row.get("mandarin_text") or "").strip()
            audio = (row.get("audio_path") or "").strip()
            if not dialect and not mandarin:
                continue
            rows.append({"audio": audio, "dialect": dialect, "mandarin": mandarin})

    # 按 mandarin 去重，保留顺序
    seen_mandarin: dict[str, dict] = {}
    for r in rows:
        if r["mandarin"] not in seen_mandarin:
            seen_mandarin[r["mandarin"]] = r  # 第一条作为参考方言版本

    unique_sentences = list(seen_mandarin.values())

    with SessionLocal() as db:
        # ── 导入 sentences（去重）──
        existing_texts = set(
            t[0] for t in db.execute(select(Sentence.text)).all()
        )
        added_sentences = 0
        sentence_map: dict[str, int] = {}  # mandarin_text -> sentence_id

        for s in unique_sentences:
            if s["mandarin"] in existing_texts:
                # 已存在，查 id
                row = db.execute(
                    select(Sentence.id).where(Sentence.text == s["mandarin"])
                ).first()
                sentence_map[s["mandarin"]] = row[0]
            else:
                new = Sentence(
                    text=s["mandarin"],
                    dialect_text=s["dialect"],
                    category="",
                    difficulty=1,
                )
                db.add(new)
                db.flush()
                sentence_map[s["mandarin"]] = new.id
                added_sentences += 1

        # ── 导入 dialect_recordings（全部 27 条）──
        existing_recordings = set(
            (r[0], r[1])
            for r in db.execute(
                select(DialectRecording.sentence_id, DialectRecording.audio_path)
            ).all()
        )
        added_recordings = 0

        for r in rows:
            sid = sentence_map.get(r["mandarin"])
            if sid is None:
                continue
            # 从文件名提取说话人（如 "陈5.WAV" -> "陈5"）
            speaker = Path(r["audio"]).stem if r["audio"] else ""
            if (sid, r["audio"]) not in existing_recordings:
                db.add(DialectRecording(
                    sentence_id=sid,
                    audio_path=r["audio"],
                    speaker=speaker,
                    dialect_text=r["dialect"],
                ))
                added_recordings += 1

        db.commit()

    return {
        "sentences_added": added_sentences,
        "recordings_added": added_recordings,
        "sentences_total": len(unique_sentences),
        "recordings_total": len(rows),
    }


if __name__ == "__main__":
    import sys

    result = seed()
    print(
        f"sentences: 新增 {result['sentences_added']}，共 {result['sentences_total']} 条唯一句\n"
        f"dialect_recordings: 新增 {result['recordings_added']}，共 {result['recordings_total']} 条方言录音"
    )
    sys.exit(0)
