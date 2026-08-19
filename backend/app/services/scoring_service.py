"""评分服务：文本相似度计算（识别文本 ↔ 参考文本）。

使用编辑距离（Levenshtein distance）计算字符级相似度，输出 0~100 整数分。
及格线 = 60（score >= 60 计入正确数）。
"""

from __future__ import annotations


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离（动态规划）。"""
    len1, len2 = len(s1), len(s2)
    # 空间优化：只保留两行
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,      # 删除
                curr[j - 1] + 1,  # 插入
                prev[j - 1] + cost,  # 替换
            )
        prev, curr = curr, prev

    return prev[len2]


def compute_similarity(recognized: str, reference: str) -> int:
    """计算识别文本与参考文本的相似度，返回 0~100 整数分。

    算法：1 - edit_distance / max(len1, len2)，乘 100 后四舍五入取整。
    两个空字符串视为完全匹配（100 分）。
    """
    if not recognized and not reference:
        return 100
    max_len = max(len(recognized), len(reference))
    if max_len == 0:
        return 100
    distance = _levenshtein_distance(recognized, reference)
    score = round((1 - distance / max_len) * 100)
    return max(0, min(100, score))
