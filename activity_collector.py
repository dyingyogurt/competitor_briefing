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

from taptap_collector import _request_json as _taptap_request_json


CN_TZ = timezone(timedelta(hours=8))


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://x.sanguosha.com"

_EVENT_TIME_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
)
# 中文时间：2026年8月14日10:00开启，到2026年9月24日24:00点结束
# 中文时间：2026年8月14日10:00开启，到2026年9月24日24:00点结束
_EVENT_TIME_CN_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r".*?"
    r"到\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*点?(?:结束|截止)?",
    re.S,
)
# 活动时间：2026年8月25日-9月23日23:59 或 2026年8月25日~2026年9月23日
_EVENT_TIME_CN_DASH_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日"
    r"(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
    r"\s*[\-~到]\s*"
    r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日"
    r"(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*点?(?:结束|截止)?",
    re.S,
)
# 2026年9月7日00:00开启 / 9月7日00:00开始
_EVENT_TIME_START_RE = re.compile(
    r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[:\uff1a](\d{2})\s*(?:开启|开始|起)",
    re.S,
)


def _cache_path(key):
    return os.path.join("data", f"activity_nodes_{key}.json")


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


def _request_json(url, timeout=20, max_retries=2):
    text = _request_text(url, timeout=timeout, max_retries=max_retries)
    return json.loads(text)


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


def _parse_event_windows(text, now=None):
    """从文本中解析所有活动时间窗口，返回 (start, end) 字符串列表。"""
    if now is None:
        now = _now()
    matches = []
    # ISO 格式：2026-09-01 10:00:00 ~ 2026-09-07 23:59:59
    for m in _EVENT_TIME_RE.finditer(text):
        matches.append((m.group(1), m.group(2)))
    # 中文日期：2026年8月14日10:00 到 2026年9月24日24:00结束
    m = _EVENT_TIME_CN_RE.search(text)
    if m:
        start_dt = _normalize_cn_datetime(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6) or 0)
        end_dt = _normalize_cn_datetime(m.group(7), m.group(8), m.group(9), m.group(10), m.group(11), m.group(12) or 0)
        matches.append((start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")))
    # 中文日期：2026年8月25日-9月23日23:59 / 2026年8月25日~2026年9月23日
    for m in _EVENT_TIME_CN_DASH_RE.finditer(text):
        start_year, start_month, start_day = m.group(1), m.group(2), m.group(3)
        start_hour = m.group(4) or "0"
        start_minute = m.group(5) or "0"
        start_second = m.group(6) or "0"
        end_year = m.group(7) or start_year
        end_month, end_day = m.group(8), m.group(9)
        end_hour = m.group(10) or "23"
        end_minute = m.group(11) or "59"
        end_second = m.group(12) or "59"
        try:
            start_dt = _normalize_cn_datetime(start_year, start_month, start_day, start_hour, start_minute, start_second)
            end_dt = _normalize_cn_datetime(end_year, end_month, end_day, end_hour, end_minute, end_second)
            matches.append((start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception:
            pass
    # 开始时间：2026年9月7日00:00开启 / 9月7日00:00开始
    for m in _EVENT_TIME_START_RE.finditer(text):
        year = m.group(1) or str(now.year)
        month, day = m.group(2), m.group(3)
        hour, minute = m.group(4), m.group(5)
        try:
            start_dt = _normalize_cn_datetime(year, month, day, hour, minute, 0)
            # 没有明确结束时间时，默认持续 7 天
            end_dt = start_dt + timedelta(days=7)
            matches.append((start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception:
            pass
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


def _parse_mjs_list_page(source, page, per_page=10, days_back=30):
    """解析名将杀官网 UCMS API 新闻列表，返回节点列表。"""
    api_base = source.get("api_base", "https://ucmsv2api.ztgame.com/api/news/list").rstrip("/")
    site = source.get("site", "mjs")
    url = f"{api_base}?site={site}&type=&page={page}&per_page={per_page}"
    try:
        data = _request_json(url)
    except Exception:
        return []
    items = data.get("data", {}).get("list", [])
    if not items:
        return []

    now = _now()
    nodes = []
    for item in items:
        title = item.get("title", "").strip()
        raw_content = item.get("content", "")
        summary = _strip_tags(raw_content)[:200]
        # API 里 type=="activity" 的才是活动，公告/ update 不解析活动时间
        if item.get("type") == "activity":
            windows = _parse_event_windows(raw_content, now=now)
            event_start, event_end = _merge_windows(windows)
        else:
            windows = []
            event_start, event_end = None, None
        defaulturl = item.get("defaulturl", "")
        source_url = f"https://mjs.ztgame.com/news/{defaulturl}" if defaulturl else ""
        catalogue = item.get("catalogue") or {}
        category = catalogue.get("name") or catalogue.get("simp") or item.get("type", "资讯")
        publish_date = item.get("publishdate", "")[:10]
        if not publish_date:
            publish_date = now.strftime("%Y-%m-%d")
        nodes.append({
            "title": title,
            "category": category,
            "publish_date": publish_date,
            "event_start": event_start,
            "event_end": event_end,
            "source_url": source_url,
            "summary": summary,
        })
    return nodes


def _parse_taptap_apk(source, days_back=30, max_pages=3):
    """解析 TapTap APK 更新日志，作为版本/公告节点来源。"""
    app_id = source.get("app_id")
    if not app_id:
        return {}
    per_page = source.get("per_page", 5)
    now = _now()
    cutoff = now - timedelta(days=days_back)
    all_nodes = {}
    first_node_key = None
    next_page = ""
    for _ in range(max_pages):
        params = {"app_id": app_id, "limit": per_page}
        if next_page:
            # next_page 已经是完整的 query string 路径，如 /webapiv2/apk/v1/list-by-app?...
            # 拆出参数
            query = next_page.split("?", 1)[1]
            params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        try:
            data = _taptap_request_json("apk/v1/list-by-app", params)
        except Exception:
            break
        items = data.get("list", [])
        if not items:
            break
        for item in items:
            ts = item.get("update_date")
            try:
                pub_dt = datetime.fromtimestamp(ts, CN_TZ)
            except Exception:
                pub_dt = now
            publish_date = pub_dt.strftime("%Y-%m-%d")
            version = item.get("version_label", "")
            title = f"版本更新 {version}" if version else "版本更新"
            raw_text = (item.get("whatsnew") or {}).get("text", "")
            summary = _strip_tags(raw_text)[:200]
            # TapTap 某些返回的中文是乱码（含 replacement char），直接置空摘要
            if "\ufffd" in summary:
                summary = ""
            source_url = f"https://www.taptap.cn/app/{app_id}"
            windows = _parse_event_windows(raw_text, now=now) if raw_text else []
            event_start, event_end = _merge_windows(windows)
            node = {
                "title": title,
                "category": "版本更新",
                "publish_date": publish_date,
                "event_start": event_start,
                "event_end": event_end,
                "source_url": source_url,
                "summary": summary,
            }
            key = f"{source_url}#{version}#{publish_date}"
            if first_node_key is None:
                first_node_key = key
                all_nodes[key] = node
            if pub_dt >= cutoff:
                all_nodes[key] = node
        next_page = data.get("next_page", "")
        if not next_page:
            break
        # 如果本页最旧条目已超窗口且已有结果，提前结束
        if all_nodes:
            oldest_ts = min((i.get("update_date") or 0) for i in items)
            try:
                oldest_dt = datetime.fromtimestamp(oldest_ts, CN_TZ)
            except Exception:
                oldest_dt = now
            if oldest_dt < cutoff:
                break
    return all_nodes


def _collect_sgs_nodes(source, days_back=30, max_pages=2):
    """采集三国杀一将成名官网节点。"""
    now = _now()
    cutoff = now - timedelta(days=days_back)
    base_url = source.get("base_url", BASE_URL).rstrip("/")
    categories = ["activity", "notice"]
    all_nodes = {}
    for category_slug in categories:
        for page in range(1, max_pages + 1):
            nodes = _parse_list_page(category_slug, page, base_url=base_url)
            if not nodes:
                break
            for node in nodes:
                all_nodes[node["source_url"]] = node
            try:
                oldest_pub = min(datetime.strptime(n["publish_date"], "%Y-%m-%d").replace(tzinfo=CN_TZ) for n in nodes)
            except Exception:
                oldest_pub = now
            if oldest_pub < cutoff:
                break
    return all_nodes


def _collect_mjs_nodes(source, days_back=30, max_pages=5):
    """采集名将杀官网节点。"""
    now = _now()
    cutoff = now - timedelta(days=days_back)
    all_nodes = {}
    for page in range(1, max_pages + 1):
        nodes = _parse_mjs_list_page(source, page, per_page=10, days_back=days_back)
        if not nodes:
            break
        for node in nodes:
            all_nodes[node["source_url"]] = node
        try:
            oldest_pub = min(datetime.strptime(n["publish_date"], "%Y-%m-%d").replace(tzinfo=CN_TZ) for n in nodes)
        except Exception:
            oldest_pub = now
        if oldest_pub < cutoff:
            break
    return all_nodes


def collect_activity_nodes(competitor_key, sources, days_back=30, max_pages=2):
    """采集单个竞品近 N 天的官网活动/公告节点。

    sources 示例：
        [{"type": "sgs_official", "base_url": "https://x.sanguosha.com/news"}]
        [{"type": "mjs_official", "api_base": "https://ucmsv2api.ztgame.com/api/news/list", "site": "mjs"}]
        [{"type": "taptap_apk", "app_id": 6985}]
    """
    if not sources:
        return {"source": None, "competitor_key": competitor_key, "nodes": []}

    now = _now()
    cutoff = now - timedelta(days=days_back)
    source = sources[0]
    source_type = source.get("type", "sgs_official")

    if source_type == "mjs_official":
        all_nodes = _collect_mjs_nodes(source, days_back=days_back, max_pages=max_pages)
    elif source_type == "taptap_apk":
        all_nodes = _parse_taptap_apk(source, days_back=days_back, max_pages=max_pages)
    else:
        # 默认按一将成名官网处理
        all_nodes = _collect_sgs_nodes(source, days_back=days_back, max_pages=max_pages)

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
    # TapTap 版本更新比较稀疏，若 30 天内没有，至少保留最新一条
    if not nodes and source_type == "taptap_apk" and all_nodes:
        nodes = [max(all_nodes.values(), key=lambda x: x["publish_date"])]
    # 按发布时间倒序
    nodes.sort(key=lambda x: x["publish_date"], reverse=True)

    result = {
        "source": source_type,
        "competitor_key": competitor_key,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "days_back": days_back,
        "nodes": nodes,
    }

    cache_path = _cache_path(competitor_key)
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    res = collect_activity_nodes("yjc", [{"type": "sgs_official", "base_url": "https://x.sanguosha.com/news"}], days_back=30)
    print(json.dumps(res, ensure_ascii=False, indent=2))
