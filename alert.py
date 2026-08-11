#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""失败告警与运行状态记录。

支持通过环境变量 COMPETITOR_ALERT_WEBHOOK_URL 配置一个通用 webhook。
消息会以 JSON {"title": ..., "text": ...} 的形式 POST 过去。
可适配飞书/Lark/企微/钉钉/自研 webhook，也可只写本地状态文件。
"""

import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta


CN_TZ = timezone(timedelta(hours=8))
STATUS_PATH = os.path.join("edge-extension", "last_run_status.json")
DEFAULT_WEBHOOK = os.getenv("COMPETITOR_ALERT_WEBHOOK_URL", "").strip()


def _now_str():
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _today_str():
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def write_status(success, message, detail=None, competitors_count=None, history_days=None):
    """把最近一次运行结果写入 last_run_status.json，供 Edge 扩展读取。"""
    payload = {
        "success": success,
        "message": message,
        "date": _today_str(),
        "checked_at": _now_str(),
        "detail": detail or "",
        "competitors_count": competitors_count,
        "history_days": history_days,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def notify_failure(error_message, detail=None):
    """运行失败时写入状态并发送告警。"""
    title = f"竞品日报生成失败｜{_today_str()}"
    text = error_message
    write_status(False, error_message, detail)
    send_alert(title, text)


def notify_success(briefing_date, competitors_count, history_days=None):
    """运行成功时写入状态。"""
    msg = f"已生成 {briefing_date} 日报，共 {competitors_count} 个竞品"
    write_status(True, msg, competitors_count=competitors_count, history_days=history_days)


if __name__ == "__main__":
    # 简单自测
    notify_success("2026-07-27", 4)
    notify_failure("测试告警：模拟生成失败", "iTunes RSS 返回空且反爬失败")
