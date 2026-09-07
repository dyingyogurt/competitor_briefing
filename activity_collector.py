#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一将成名官网活动节点采集。

目前仅接入「三国杀：一将成名」，从官网新闻列表抓取近一个月（可配置）的活动/公告，
解析活动时间、标题和来源链接，用于竞品日报展示。
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse


CN_TZ = timezone(timedelta(hours=8))
CACHE_PATH = os.path.join("data", "activity_nodes_yjc.json")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://x.sanguosha.com"

_EVENT_TIME_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
)
# 中文时间：2026年8月14日10:00开启，到2026年9月24日24:00点结束
_EVENT_TIME_CN_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r".*?"
    r"到\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*点?(?:结束|截止)?",
    re.S,
)


def _now():
    return datetime.now(CN_TZ)


def _request_text(url, timeout=20, max_retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise last_err


def _strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text).strip()


def _normalize_cn_datetime(year, month, day, hour, minute, second=0):
    """处理 24:00 这种中文写法，自动进位到次日。"""
    h = int(hour)
    # Python datetime 不支持 24 点，先按 0 点构造再进位
    dt = datetime(int(year), int(month), int(day), 0, int(minute), int(second))
    if h == 24:
        dt = dt + timedelta(days=1)
    else:
        dt = dt + timedelta(hours=h)
    return dt


def _parse_event_windows(text):
    """从文本中解析所有活动时间窗口，返回 (start, end) 字符串列表。"""
    matches = []
    for m in _EVENT_TIME_RE.finditer(text):
        matches.append((m.group(1), m.group(2)))
    # 中文日期：整体匹配一次；取第一对日期
    m = _EVENT_TIME_CN_RE.search(text)
    if m:
        start_dt = _normalize_cn_datetime(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6) or 0)
        end_dt = _normalize_cn_datetime(m.group(7), m.group(8), m.group(9), m.group(10), m.group(11), m.group(12) or 0)
        matches.append((start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")))
    return matches


def _merge_windows(windows):
    """多个时间窗口取最早开始和最晚结束，作为整体活动时间。"""
    if not windows:
        return None, None
    starts = [datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ) for s, _ in windows]
    ends = [datetime.strptime(e, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ) for _, e in windows]
    return min(starts).strftime("%Y-%m-%d %H:%M:%S"), max(ends).strftime("%Y-%m-%d %H:%M:%S")


def _host_from_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_list_page(category_slug, page, base_url=BASE_URL):
    """解析官网某个分类的列表页，返回文章元信息列表。"""
    host = _host_from_url(base_url)
    if category_slug:
        url = f"{host}/news/{category_slug}?page={page}"
    else:
        url = f"{host}/news?page={page}"
    try:
        text = _request_text(url)
    except Exception:
        return []

    results = []
    # 匹配每条新闻的 <a> 块
    for m in re.finditer(r'<a[^>]+href="(/news/(\d{8})_\d+_\d+\.html)"[^>]*>(.*?)</a>', text, re.S):
        path, pub_str, block = m.group(1), m.group(2), m.group(3)

        # 分类标签
        cat_match = re.search(r'<em[^>]*>\s*(.*?)\s*</em>', block)
        category = (cat_match.group(1).strip() if cat_match else "").replace("\n", " ")
        if not category:
            category = "公告" if category_slug == "notice" else ("活动" if category_slug == "activity" else "资讯")

        # 标题
        name_match = re.search(r'<div class="press-name">(.*?)</div>', block, re.S)
        title = ""
        if name_match:
            raw_name = _strip_tags(name_match.group(1))
            # 去掉开头的分类标签
            if raw_name.startswith(category):
                title = raw_name[len(category):].strip()
            else:
                title = raw_name

        if not title:
            title = path

        # 摘要/正文预览
        intro_match = re.search(r'<div class="press-intro">(.*?)</div>', block, re.S)
        intro = intro_match.group(1) if intro_match else ""
        summary = _strip_tags(intro)[:200]

        # 活动时间
        windows = _parse_event_windows(intro)
        event_start, event_end = _merge_windows(windows)

        results.append({
            "title": title,
            "category": category,
            "publish_date": f"{pub_str[:4]}-{pub_str[4:6]}-{pub_str[6:]}",
            "event_start": event_start,
            "event_end": event_end,
            "source_url": f"{_host_from_url(base_url)}{path}",
            "summary": summary,
        })
    return results


def collect_activity_nodes(competitor_key, sources, days_back=30, max_pages=2):
    """采集单个竞品近 N 天的官网活动/公告节点。

    sources 示例：
        [{"type": "sgs_official", "base_url": "https://x.sanguosha.com/news"}]
    """
    if not sources:
        return {"source": None, "competitor_key": competitor_key, "nodes": []}

    now = _now()
    cutoff = now - timedelta(days=days_back)

    source = sources[0]
    base_url = source.get("base_url", BASE_URL).rstrip("/")
    # 对于 sgs 官方案例，base_url 如 https://x.sanguosha.com/news
    categories = ["activity", "notice"]

    all_nodes = {}
    for category_slug in categories:
        for page in range(1, max_pages + 1):
            nodes = _parse_list_page(category_slug, page, base_url=base_url)
            if not nodes:
                break
            for node in nodes:
                all_nodes[node["source_url"]] = node
            # 如果本页最旧的文章已经超出窗口，停止翻页
            try:
                oldest_pub = min(datetime.strptime(n["publish_date"], "%Y-%m-%d").replace(tzinfo=CN_TZ) for n in nodes)
            except Exception:
                oldest_pub = now
            if oldest_pub < cutoff:
                break

    # 按活动时间口径过滤：
    # 1. 活动未结束超过 days_back 天；2. 活动尚未开始；3. 公告类按发布时间兜底
    def _keep(node):
        pub = datetime.strptime(node["publish_date"], "%Y-%m-%d").replace(tzinfo=CN_TZ)
        if node["event_start"] and node["event_end"]:
            end = datetime.strptime(node["event_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
            start = datetime.strptime(node["event_start"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
            return end >= cutoff or start >= now
        # 没有活动时间：公告类，按发布时间兜底
        return pub >= cutoff

    nodes = [n for n in all_nodes.values() if _keep(n)]
    # 按发布时间倒序
    nodes.sort(key=lambda x: x["publish_date"], reverse=True)

    result = {
        "source": source.get("type"),
        "competitor_key": competitor_key,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "days_back": days_back,
        "nodes": nodes,
    }

    os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    res = collect_activity_nodes("yjc", [{"type": "sgs_official", "base_url": "https://x.sanguosha.com/news"}], days_back=30)
    print(json.dumps(res, ensure_ascii=False, indent=2))
