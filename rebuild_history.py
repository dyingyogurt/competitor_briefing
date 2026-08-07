#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从历史简报 HTML 中提取关键指标，重建 data/history.json"""

import json
import os
import re
import glob
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
HISTORY_DIR = os.path.join("edge-extension", "history")
OUTPUT_PATH = os.path.join("data", "history.json")


def extract_date(filename):
    m = re.match(r"briefing_(\d{4}-\d{2}-\d{2})\.html", os.path.basename(filename))
    return m.group(1) if m else None


def extract_competitor_data(html, comp_key):
    """从 HTML 中提取某个竞品的关键指标。"""
    # 找到该竞品的 section
    # 竞品名称映射
    names = {
        "yjc": "三国杀一将成名",
        "mjs": "名将杀",
        "yxs": "英雄杀",
        "bjp": "百将牌",
    }
    name = names.get(comp_key, "")
    
    # 提取 App Store 总评分 (从 overview card)
    # 格式: ⭐ 2.63 或类似的
    rating = None
    review_avg = None
    bili_pos = 0
    bili_neg = 0
    bili_neu = 0
    bili_count = 0

    # 找到该竞品的 section 块
    section_pattern = rf'id="{re.escape(name)}"'
    if not re.search(section_pattern, html):
        return None

    # 提取 App Store 评分 (从 trend chart "App Store 总评分最新 X")
    # 但趋势图里的是累计评分，我们需要当天的
    # 从 overview card 提取: ⭐ X.XX
    rating_match = re.search(r'⭐\s*([\d.]+)', html)
    if rating_match:
        rating = float(rating_match.group(1))

    # 提取评论均分 (从 "平均评分" metric)
    avg_match = re.search(r'class="metric-value">([\d.]+)</div>\s*<div class="metric-label">平均评分', html)
    if avg_match:
        review_avg = float(avg_match.group(1))

    # 提取 Bilibili 情感 (从 sentiment bar)
    # 格式: 正面 169 (32.4%)
    pos_match = re.search(r'正面\s+(\d+)\s*\(', html)
    neg_match = re.search(r'负面\s+(\d+)\s*\(', html)
    neu_match = re.search(r'中性\s+(\d+)\s*\(', html)
    if pos_match:
        bili_pos = int(pos_match.group(1))
    if neg_match:
        bili_neg = int(neg_match.group(1))
    if neu_match:
        bili_neu = int(neu_match.group(1))

    # 提取采样评论数
    count_match = re.search(r'class="metric-value">(\d+)</div>\s*<div class="metric-label">采样评论数', html)
    if count_match:
        bili_count = int(count_match.group(1))

    return {
        "name": name,
        "version": None,
        "ranks": {},
        "app_store_rating": rating,
        "review_avg_rating": review_avg,
        "review_count": 100,
        "bilibili_sentiment": {
            "positive": bili_pos,
            "negative": bili_neg,
            "neutral": bili_neu,
        },
        "bilibili_comment_count": bili_count,
    }


def main():
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "briefing_*.html")))
    history = {}

    for f in files:
        date = extract_date(f)
        if not date:
            continue
        with open(f, "r", encoding="utf-8") as fh:
            html = fh.read()

        entry = {}
        for key in ["yjc", "mjs", "yxs", "bjp"]:
            data = extract_competitor_data(html, key)
            if data:
                entry[key] = data

        if entry:
            history[date] = entry
            print(f"  {date}: {list(entry.keys())}")

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"\n已重建 {OUTPUT_PATH}，共 {len(history)} 天")


if __name__ == "__main__":
    main()
