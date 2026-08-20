#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方言↔普通话 映射生成脚本。

移植自 dialect_asr_system/make_translate_map.py，适配 taizhou-voice 项目结构。

输入: data/translate_pairs.csv（text, mandarin_text 列）
输出: data/translate_pairs.json（平行句对 + 自动提取的词级替换规则）

规则提取: 逐字符对齐（difflib）自动发现 方言词↔普通话词 对应，
         可被 data/translate_overrides.json 人工覆盖。

用法:
    uv run python scripts/make_translate_map.py
    uv run python scripts/make_translate_map.py --csv path/to/pairs.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# 默认路径
DEFAULT_CSV = DATA_DIR / "translate_pairs.csv"
DEFAULT_JSON = DATA_DIR / "translate_pairs.json"
DEFAULT_OVERRIDES = DATA_DIR / "translate_overrides.json"


def load_rows(csv_path: Path) -> list[dict]:
    """加载 CSV 平行语料。"""
    import csv

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f)):
            dz = (r.get("text") or "").strip()
            zh = (r.get("mandarin_text") or "").strip()
            if not dz or not zh:
                print(f"[warn] 第 {i + 2} 行缺少文本，跳过")
                continue
            rows.append({"dialect": dz, "mandarin": zh})
    return rows


def extract_rules(pairs: list[tuple[str, str]]) -> tuple[dict, dict]:
    """逐字符对齐提取词级替换规则（双向）。"""
    cnt_dz2zh: dict[str, dict[str, int]] = {}
    cnt_zh2dz: dict[str, dict[str, int]] = {}

    for dz, zh in pairs:
        sm = SequenceMatcher(None, dz, zh, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and i2 > i1 and j2 > j1:
                d, z = dz[i1:i2], zh[j1:j2]
                if d != z:
                    bucket = cnt_dz2zh.setdefault(d, {})
                    bucket[z] = bucket.get(z, 0) + 1
                    bucket = cnt_zh2dz.setdefault(z, {})
                    bucket[d] = bucket.get(d, 0) + 1

    # 每个源片段取出现次数最多的目标；过滤：
    #  - 含标点碎片（对齐噪音）
    #  - 单字规则（对齐易错位，单字映射只信任人工覆盖表）
    _punct = set("，。！？、；：""''（）《》…—，,.!?;:() \t")

    def _pick(counter: dict[str, dict[str, int]]) -> dict[str, str]:
        rules = {}
        for src, targets in counter.items():
            if not any(c.isalnum() or "\u4e00" <= c <= "\u9fff" for c in src):
                continue
            if any(c in _punct for c in src):
                continue
            if len(src) < 2:
                continue
            tgt = max(targets.items(), key=lambda kv: kv[1])[0]
            if tgt and src != tgt:
                rules[src] = tgt
        return rules

    return _pick(cnt_dz2zh), _pick(cnt_zh2dz)


def main():
    ap = argparse.ArgumentParser(description="生成方言↔普通话翻译映射")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="平行语料 CSV 路径")
    ap.add_argument("--output", type=Path, default=DEFAULT_JSON, help="输出 JSON 路径")
    ap.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES, help="人工覆盖规则 JSON")
    a = ap.parse_args()

    if not a.csv.exists():
        print(f"[error] CSV 不存在: {a.csv}")
        sys.exit(1)

    rows = load_rows(a.csv)
    if not rows:
        print("[error] CSV 没有有效数据")
        sys.exit(1)

    pairs = [{"dialect": r["dialect"], "mandarin": r["mandarin"]} for r in rows]

    rules_dz2zh, rules_zh2dz = extract_rules(
        [(p["dialect"], p["mandarin"]) for p in pairs]
    )

    # 人工覆盖（可选）: {"dz2zh": {...}, "zh2dz": {...}}，值为 null 表示删除该规则
    overrides = {"dz2zh": {}, "zh2dz": {}}
    if a.overrides.exists():
        with open(a.overrides, "r", encoding="utf-8") as f:
            overrides = json.load(f)

    for key, rules in (("dz2zh", rules_dz2zh), ("zh2dz", rules_zh2dz)):
        for k, v in overrides.get(key, {}).items():
            if v is None:
                rules.pop(k, None)
            else:
                rules[k] = v

    out = {
        "source_csv": str(a.csv),
        "built_at": datetime.now().isoformat(),
        "count": len(pairs),
        "pairs": pairs,
        "rules_dz2zh": rules_dz2zh,
        "rules_zh2dz": rules_zh2dz,
        "overrides": overrides,
    }

    a.output.parent.mkdir(parents=True, exist_ok=True)
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("=" * 56)
    print(f"平行句对: {len(pairs)}")
    print(f"词级规则: 方言→普通话 {len(rules_dz2zh)} 条, 普通话→方言 {len(rules_zh2dz)} 条")
    print(f"输出: {a.output}")
    print("样例规则(方言→普通话):")
    for i, (k, v) in enumerate(
        sorted(rules_dz2zh.items(), key=lambda kv: -len(kv[0]))[:15]
    ):
        print(f"   {k}  →  {v}")
    print("=" * 56)


if __name__ == "__main__":
    main()
