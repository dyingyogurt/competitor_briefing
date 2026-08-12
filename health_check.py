#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 日报生成后的健康自检脚本。

检查项：
1. last_run_status.json 存在且 success
2. 当天日期与北京时间今天一致
3. history_days 没有减少（与 PREV_HISTORY_COUNT 环境变量比较）
4. competitors_count >= 1

异常时通过 alert.send_alert 发送告警（依赖 COMPETITOR_ALERT_WEBHOOK_URL），
并以非零状态码退出，阻止后续 Pages 部署。
"""

import json
import os
import sys

from alert import _today_str, send_alert


def load_status(path="edge-extension/last_run_status.json"):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    status = load_status()
    errors = []
    today = _today_str()

    if status is None:
        errors.append("缺少 last_run_status.json，main.py 可能未成功执行")
    else:
        if not status.get("success"):
            errors.append(f"main.py 报告失败：{status.get('message', '')}")

        if status.get("date") != today:
            errors.append(
                f"数据日期异常：status.date={status.get('date')}，今天={today}"
            )

        competitors_count = status.get("competitors_count")
        if competitors_count is None or competitors_count < 1:
            errors.append(f"竞品数量异常：{competitors_count}")

        history_days = status.get("history_days")
        if history_days is None or history_days < 1:
            errors.append(f"历史天数异常：{history_days}")

        prev_count = os.getenv("PREV_HISTORY_COUNT")
        if prev_count is not None and history_days is not None:
            try:
                prev = int(prev_count)
            except ValueError:
                prev = -1
            if history_days < prev:
                errors.append(
                    f"历史天数回退：生成前 {prev} 天，生成后 {history_days} 天"
                )

    if errors:
        title = f"竞品日报健康检查失败｜{today}"
        text = "\n".join(f"- {e}" for e in errors)
        print(f"[HEALTH CHECK] {title}\n{text}", file=sys.stderr)
        send_alert(title, text)
        sys.exit(1)

    print(
        f"[HEALTH CHECK] OK: date={today}, "
        f"competitors={status['competitors_count']}, "
        f"history_days={status['history_days']}"
    )


if __name__ == "__main__":
    main()
