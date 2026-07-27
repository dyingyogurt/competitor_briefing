#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日竞品简报入口。

用法：
    python main.py              # 生成 Markdown 文件，并更新 edge-extension/briefing.html
"""

import argparse
import traceback
from collector import collect_all
from formatter import generate_briefing, generate_briefing_html
from history import compare_with_previous, record
from alert import notify_success, notify_failure


def main():
    parser = argparse.ArgumentParser(description="三国杀竞品日报自动生成")
    parser.add_argument("--output-dir", default="output", help="Markdown 输出目录")
    args = parser.parse_args()

    try:
        print("[1/3] 正在采集数据...")
        data = collect_all()

        print("[2/3] 正在对比历史异动...")
        prev_date, changes = compare_with_previous(data)

        print("[3/3] 正在生成 Markdown / HTML 简报...")
        path, md = generate_briefing(data, output_dir=args.output_dir, changes=changes, prev_date=prev_date)
        html_path = generate_briefing_html(data, output_dir="edge-extension", changes=changes, prev_date=prev_date)
        print(f"      Markdown：{path}")
        print(f"      Edge 简报：{html_path}")

        print("[+] 正在保存今日快照...")
        record(data)

        date_str = data.get("generated_at", "")[:10]
        notify_success(date_str, len(data.get("competitors", [])))
        print("完成。打开 Edge 新标签页即可查看简报。")
    except Exception as e:
        tb = traceback.format_exc()
        notify_failure(f"生成日报失败：{type(e).__name__}: {e}", detail=tb)
        raise


if __name__ == "__main__":
    main()
