#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记录每天榜单/版本快照，用于次日的"异动"对比。"""

import json
import os
from datetime import datetime, timezone, timedelta


CN_TZ = timezone(timedelta(hours=8))
HISTORY_PATH = os.path.join("data", "history.json")


def _today():
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def load_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def snapshot(data):
    """从采集结果生成当天的快照，用于趋势图和异动对比。"""
    snap = {}
    for c in data["competitors"]:
        reviews = c.get("reviews", {})
        bilibili = c.get("bilibili_sentiment") or {}
        taptap = c.get("taptap") or {}
        snap[c["key"]] = {
            "name": c["name"],
            "version": c.get("app_store", {}).get("version"),
            "ranks": c.get("chart_rank", {}),
            "app_store_rating": c.get("app_store", {}).get("rating"),
            "review_avg_rating": reviews.get("avg_rating"),
            "review_count": reviews.get("count", 0),
            "bilibili_sentiment": bilibili.get("sentiment", {}),
            "bilibili_comment_count": bilibili.get("comment_count", 0),
            "taptap_rating": taptap.get("rating"),
            "taptap_review_count": taptap.get("review_count", 0),
        }
    return snap


def compare_with_previous(current_data):
    """返回（上一个有数据的日期，对比结果 dict）。"""
    today = _today()
    history = load_history()
    prev_date = None
    for d in sorted(history.keys(), reverse=True):
        if d != today:
            prev_date = d
            break

    if not prev_date:
        return None, {}

    prev = history[prev_date]
    cur = snapshot(current_data)
    changes = {}
    for key, cur_item in cur.items():
        prev_item = prev.get(key, {})
        changes[key] = {
            "name": cur_item["name"],
            "version_changed": cur_item.get("version") != prev_item.get("version"),
            "rank_changes": {},
        }
        for chart, cur_rank in cur_item.get("ranks", {}).items():
            prev_rank = prev_item.get("ranks", {}).get(chart)
            if isinstance(cur_rank, int) and isinstance(prev_rank, int):
                delta = prev_rank - cur_rank  # 正数表示上升
                if abs(delta) >= 5:
                    changes[key]["rank_changes"][chart] = {"from": prev_rank, "to": cur_rank, "delta": delta}
            elif (cur_rank is None) != (prev_rank is None):
                changes[key]["rank_changes"][chart] = {"from": prev_rank, "to": cur_rank, "delta": None}

    return prev_date, changes


def record(data):
    history = load_history()
    history[_today()] = snapshot(data)
    save_history(history)
