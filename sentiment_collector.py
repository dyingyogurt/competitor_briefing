#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilibili 舆情采集：用公开 API 抓取视频评论，作为 App Store 评论的替代来源。"""

import json
import re
import time
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta


CN_TZ = timezone(timedelta(hours=8))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
)

# 简单情感词库（后续可扩展为更准的模型）
POSITIVE_WORDS = [
    "好玩", "不错", "良心", "强", "推荐", "加油", "支持", "喜欢", "优秀", "香", "值", "可以",
    "很棒", "有意思", "爱了", "好评", "良心游戏", "上头", "爽", "稳", "强",
]
NEGATIVE_WORDS = [
    "垃圾", "坑钱", "骗氪", "逼氪", "重氪", "氪金", "圈钱", "骗钱", "吃相", "割韭菜",
    "bug", "卡顿", "闪退", "掉线", "卡死", "延迟", "黑屏",
    "不平衡", "难玩", "恶心", "失望", "烂", "坑", "黑", "贵", "肝", "不值",
    "退游", "弃坑", "卸载", "差评", "后悔", "上当",
    "阴间", "超模", "下水道", "天牢", "弱", "废", "打不过", "数值崩", "畸形", "离谱",
    "暗改", "爆率低", "抽不到", "保底", "人机", "演员", "环境差",
    "坑人", "垃圾游戏",
]

# 否定词：命中关键词时，若其前面很近的位置出现否定词，则跳过该命中
NEGATION_WORDS = ["不", "没", "无", "并非", "不是", "没有", "不算"]


def _find_keywords(text, keyword_list):
    """返回文本中命中的关键词列表（不含被否定词修饰的命中）。"""
    hits = []
    for kw in keyword_list:
        start = 0
        while True:
            idx = text.find(kw, start)
            if idx == -1:
                break
            window = text[max(0, idx - 6): idx]
            if not any(nw in window for nw in NEGATION_WORDS):
                hits.append(kw)
            start = idx + len(kw)
    return hits


def _buvid():
    return "XY" + str(uuid.uuid4()).upper().replace("-", "")[:30] + "infoc"


def _request_json(url, referer, timeout=15, max_retries=2):
    """请求 B 站 API，携带基础反反爬 headers，失败时简单重试。"""
    b3 = _buvid()
    cookies = {
        "buvid3": b3,
        "b_nut": "100",
        "buvid4": f"{uuid.uuid4().hex}023-3e7f947f0663",
        "_uuid": str(uuid.uuid4()).upper(),
    }
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": referer,
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie_str,
    }

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise last_err


def _clean_html(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def search_videos(keyword, max_results=5, pubtime_begin_s=None, pubtime_end_s=None):
    """搜索 Bilibili 视频，返回视频列表。

    当提供 pubtime_begin_s / pubtime_end_s 时，只搜索该时间区间内发布的视频
    （单位：秒，Unix 时间戳）。
    """
    encoded = urllib.parse.quote(keyword)
    url = (
        f"https://api.bilibili.com/x/web-interface/search/type"
        f"?keyword={encoded}&search_type=video&page=1"
    )
    if pubtime_begin_s is not None and pubtime_end_s is not None:
        url += f"&pubtime_begin_s={pubtime_begin_s}&pubtime_end_s={pubtime_end_s}"
    try:
        data = _request_json(url, "https://search.bilibili.com/")
        if data.get("code") != 0:
            return []
        results = data.get("data", {}).get("result", [])
        videos = []
        for r in results[:max_results]:
            videos.append({
                "bvid": r.get("bvid"),
                "aid": r.get("aid"),
                "title": _clean_html(r.get("title", "")),
                "author": r.get("author"),
                "play": r.get("play", 0),
                "review": r.get("review", 0),
                "link": f"https://www.bilibili.com/video/{r.get('bvid')}",
            })
        return videos
    except Exception:
        return []


def fetch_top_comments(aid, max_comments=5):
    """抓取某个视频的热门评论。"""
    if not aid:
        return []
    url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&ps={max_comments}"
    try:
        data = _request_json(url, f"https://www.bilibili.com/video/av{aid}")
        if data.get("code") != 0:
            return []
        replies = data.get("data", {}).get("replies") or []
        comments = []
        for r in replies[:max_comments]:
            content = r.get("content", {}).get("message", "")
            member = r.get("member", {})
            comments.append({
                "author": member.get("uname", ""),
                "content": content,
                "like": r.get("like", 0),
                "ctime": r.get("ctime"),
            })
        return comments
    except Exception:
        return []


def analyze_sentiment(comments):
    """对评论列表做情感统计。

    规则：
    - 将视频标题和评论内容一起纳入关键词匹配；
    - 按点赞数加权（点赞为 0 时权重为 1），让高赞热评更有代表性；
    - 正面、负面独立计数：一条评论可以同时计入正面和负面（混合评论）；
    - 命中关键词时，若其前面很近的位置出现否定词，则忽略该关键词，减少误判。
    """
    positive, negative, neutral = 0, 0, 0
    raw_positive, raw_negative, raw_neutral, raw_mixed = 0, 0, 0, 0
    mixed = 0
    neg_keyword_count = {}
    negative_samples = []

    for c in comments:
        content = c.get("content", "")
        title = c.get("video_title", "")
        text = f"{title} {content}".strip()
        weight = max(1, int(c.get("like", 0)))

        neg_hits = _find_keywords(text, NEGATIVE_WORDS)
        pos_hits = _find_keywords(text, POSITIVE_WORDS)
        is_neg = bool(neg_hits)
        is_pos = bool(pos_hits)

        if is_pos:
            raw_positive += 1
            positive += weight
        if is_neg:
            raw_negative += 1
            negative += weight
            for w in neg_hits:
                neg_keyword_count[w] = neg_keyword_count.get(w, 0) + weight
            negative_samples.append(c)
        if is_pos and is_neg:
            raw_mixed += 1
            mixed += weight
        if not is_pos and not is_neg:
            raw_neutral += 1
            neutral += weight

    # 负面样本按点赞数排序，保留热度最高的 5 条
    negative_samples = sorted(negative_samples, key=lambda x: -x.get("like", 0))[:5]

    return {
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "mixed": mixed,
        "raw_positive": raw_positive,
        "raw_negative": raw_negative,
        "raw_neutral": raw_neutral,
        "raw_mixed": raw_mixed,
        "negative_keywords": dict(sorted(neg_keyword_count.items(), key=lambda x: -x[1])),
        "negative_samples": negative_samples,
    }


def collect_bilibili_sentiment(keyword, max_videos=3, max_comments_per_video=5):
    """针对关键词采集 Bilibili 舆情。默认只采集前一天（北京时间）发布的热门视频。"""
    now = datetime.now(CN_TZ)
    today = datetime(now.year, now.month, now.day, tzinfo=CN_TZ)
    yesterday = today - timedelta(days=1)
    # 放宽到最近 3 天，避免某天内新视频太少导致无数据
    start_day = today - timedelta(days=3)
    pubtime_begin_s = int(start_day.timestamp())
    pubtime_end_s = int(today.timestamp()) - 1

    videos = search_videos(
        keyword,
        max_results=max_videos,
        pubtime_begin_s=pubtime_begin_s,
        pubtime_end_s=pubtime_end_s,
    )
    all_comments = []
    sources = []

    for idx, v in enumerate(videos):
        # 相邻视频评论请求间隔，降低被风控概率
        if idx > 0:
            time.sleep(0.8)
        comments = fetch_top_comments(v["aid"], max_comments=max_comments_per_video)
        for c in comments:
            c["video_title"] = v["title"]
            c["video_link"] = v["link"]
        all_comments.extend(comments)
        sources.append({
            "title": v["title"],
            "link": v["link"],
            "author": v["author"],
            "comments_fetched": len(comments),
        })

    sentiment = analyze_sentiment(all_comments)

    return {
        "source": "bilibili",
        "keyword": keyword,
        "collected_at": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "videos": sources,
        "comment_count": len(all_comments),
        "sentiment": {
            "positive": sentiment["positive"],
            "negative": sentiment["negative"],
            "neutral": sentiment["neutral"],
            "mixed": sentiment["mixed"],
        },
        "negative_keywords": sentiment["negative_keywords"],
        "top_comments": sorted(all_comments, key=lambda x: -x.get("like", 0))[:5],
        "negative_samples": sentiment["negative_samples"],
    }


if __name__ == "__main__":
    result = collect_bilibili_sentiment("三国杀一将成名", max_videos=3, max_comments_per_video=5)
    print(json.dumps(result, ensure_ascii=False, indent=2))
