#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动采集：App Store 版本、榜单、评论。
七麦数据 / TapTap / 官网 / 社媒 因反爬或登录态，当前用 manual_overrides.json 人工补全。"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import Counter
from html.parser import HTMLParser
from config import COMPETITORS, CHART_FEEDS, REVIEW_PAGES
from sentiment_collector import collect_bilibili_sentiment


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CN_TZ = timezone(timedelta(hours=8))


def _request_json(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


class AppStorePageReviewParser(HTMLParser):
    """解析 App Store App 详情页中的精选评论（RSS 为空时的兜底）。"""

    def __init__(self):
        super().__init__()
        self.reviews = []
        self._in_review = False
        self._current = None
        self._stack = []
        self._capture_text = False
        self._text_tag = None
        self._buf = []

    def _find_review_id(self, attrs):
        for k, v in attrs:
            if k == "aria-labelledby" and v.startswith("review-") and v.endswith("-title"):
                return v[7:-6]
        return None

    def _get_attr(self, attrs, name):
        for k, v in attrs:
            if k == name:
                return v
        return None

    def handle_starttag(self, tag, attrs):
        rid = self._find_review_id(attrs)
        if rid:
            self._in_review = True
            self._current = {
                "id": rid,
                "title": "",
                "rating": None,
                "author": "",
                "date": "",
                "body": "",
            }
            self.reviews.append(self._current)
            self._stack = [tag]
            return

        if self._in_review:
            self._stack.append(tag)
            if tag == "ol":
                al = self._get_attr(attrs, "aria-label")
                if al and "星" in al:
                    m = re.search(r"(\d+)", al)
                    if m:
                        self._current["rating"] = int(m.group(1))
            if tag in ("h3", "p", "time"):
                self._capture_text = True
                self._text_tag = tag
                self._buf = []

    def handle_data(self, data):
        if self._capture_text:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if not self._in_review:
            return

        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        else:
            try:
                idx = len(self._stack) - 1 - self._stack[::-1].index(tag)
                self._stack = self._stack[:idx]
            except ValueError:
                pass

        if self._capture_text and self._text_tag == tag:
            text = "".join(self._buf).strip()
            if tag == "h3":
                self._current["title"] = text
            elif tag == "time":
                self._current["date"] = text
            elif tag == "p":
                if len(text) > len(self._current["body"]):
                    self._current["body"] = text
            self._capture_text = False
            self._text_tag = None

        if self._in_review and not self._stack:
            self._in_review = False
            self._current = None

    def get_reviews(self):
        return [r for r in self.reviews if r.get("rating") and r.get("title")]


def _fetch_app_page_reviews(itunes_id):
    """RSS 无数据时，抓取 App Store 详情页上的精选评论作为兜底。"""
    lookup_url = f"https://itunes.apple.com/cn/lookup?id={itunes_id}&country=CN"
    try:
        data = _request_json(lookup_url)
        results = data.get("results", [])
        if not results:
            return []
        app_url = results[0].get("trackViewUrl")
        if not app_url:
            return []
    except Exception:
        return []

    try:
        req = urllib.request.Request(app_url, headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception:
        return []

    parser = AppStorePageReviewParser()
    parser.feed(html)
    reviews = []
    for r in parser.get_reviews():
        date_raw = r.get("date", "")
        iso = ""
        if re.match(r"\d{4}/\d{2}/\d{2}", date_raw):
            iso = f"{date_raw[:4]}-{date_raw[5:7]}-{date_raw[8:10]}T00:00:00Z"
        reviews.append({
            "author": r.get("author", ""),
            "rating": r.get("rating", 0),
            "version": "",
            "title": r.get("title", ""),
            "content": r.get("body", ""),
            "updated": iso,
        })
    return reviews


def fetch_app_details(itunes_id):
    """通过 iTunes Lookup API 获取版本、更新说明、开发商、评分等。"""
    url = f"https://itunes.apple.com/cn/lookup?id={itunes_id}&country=CN"
    try:
        data = _request_json(url)
        results = data.get("results", [])
        if not results:
            return {"error": "iTunes 未返回结果"}
        r = results[0]
        return {
            "track_name": r.get("trackName"),
            "version": r.get("version"),
            "release_date": r.get("currentVersionReleaseDate", "")[:10],
            "release_notes": r.get("releaseNotes", "").strip(),
            "seller": r.get("sellerName"),
            "app_url": r.get("trackViewUrl"),
            "genres": r.get("genres", []),
            "rating": r.get("averageUserRatingForCurrentVersion") or r.get("averageUserRating"),
            "rating_count": r.get("userRatingCountForCurrentVersion") or r.get("userRatingCount"),
        }
    except Exception as e:
        return {"error": f"iTunes API 请求失败: {type(e).__name__}: {e}"}


def fetch_chart_rank(itunes_id):
    """从 Apple 公开 RSS 榜单查排名，仅支持 Top100。"""
    ranks = {}
    for chart_name, feed_url in CHART_FEEDS.items():
        try:
            data = _request_json(feed_url, timeout=20)
            entries = data.get("feed", {}).get("entry", [])
            for idx, e in enumerate(entries, start=1):
                app_id = e.get("id", {}).get("attributes", {}).get("id")
                if str(app_id) == str(itunes_id):
                    ranks[chart_name] = idx
                    break
            else:
                ranks[chart_name] = None
        except Exception as e:
            ranks[chart_name] = f"获取失败:{type(e).__name__}"
    return ranks


def fetch_reviews(itunes_id, pages=REVIEW_PAGES):
    """获取 App Store 评论。RSS 无数据时，自动兜底抓取详情页精选评论。"""
    reviews = []
    api_status = "ok"  # ok / empty / error / page_fallback
    api_error = None
    source = "rss"

    for page in range(1, pages + 1):
        url = (
            f"https://itunes.apple.com/cn/rss/customerreviews/"
            f"page={page}/id={itunes_id}/sortby=mostrecent/json?l=cn"
        )
        try:
            data = _request_json(url, timeout=20)
            entries = data.get("feed", {}).get("entry", [])
            if not entries and page == 1:
                api_status = "empty"
            for e in entries:
                if "author" not in e:  # 过滤 feed 头
                    continue
                reviews.append({
                    "author": e.get("author", {}).get("name", {}).get("label", ""),
                    "rating": int(e.get("im:rating", {}).get("label", 0)),
                    "version": e.get("im:version", {}).get("label", ""),
                    "title": e.get("title", {}).get("label", ""),
                    "content": e.get("content", {}).get("label", ""),
                    "updated": e.get("updated", {}).get("label", ""),
                })
        except Exception as e:
            api_status = "error"
            api_error = f"{type(e).__name__}: {e}"
            pass

    # RSS 为空或失败时，兜底抓取 App Store 页面精选评论
    if not reviews and api_status in ("empty", "error"):
        page_reviews = _fetch_app_page_reviews(itunes_id)
        if page_reviews:
            reviews = page_reviews
            api_status = "page_fallback"
            source = "app_store_page"

    if not reviews:
        return {
            "count": 0,
            "avg_rating": None,
            "rating_dist": {},
            "latest": [],
            "api_status": api_status,
            "api_error": api_error,
            "source": source,
        }

    ratings = [r["rating"] for r in reviews]
    dist = Counter(ratings)
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None

    # 最近 7 天内（页面兜底评的日期通常较旧，过滤后可能为 0）
    now_cn = datetime.now(CN_TZ)
    week_ago = now_cn - timedelta(days=7)
    recent = []
    for r in reviews:
        try:
            t = datetime.fromisoformat(r["updated"].replace("Z", "+00:00"))
            t = t.astimezone(CN_TZ)
        except Exception:
            continue
        if t >= week_ago:
            recent.append(r)

    positive = sum(1 for r in reviews if r["rating"] >= 4)
    neutral = sum(1 for r in reviews if r["rating"] == 3)
    negative = sum(1 for r in reviews if r["rating"] <= 2)

    negative_words = [
        "垃圾", "坑钱", "骗氪", "逼氪", "重氪", "氪金", "圈钱", "骗钱", "吃相", "割韭菜",
        "bug", "卡顿", "闪退", "掉线", "卡死", "延迟", "黑屏",
        "不平衡", "难玩", "恶心", "太黑", "诈骗", "失望", "烂", "坑", "肝", "贵", "不值",
        "退游", "弃坑", "卸载", "差评", "后悔", "上当",
        "阴间", "超模", "下水道", "天牢", "弱", "废", "打不过", "数值崩", "畸形", "离谱",
        "暗改", "爆率低", "抽不到", "保底", "人机", "演员", "环境差",
    ]
    neg_reviews = [
        r for r in reviews
        if r["rating"] <= 2 or any(w in r["content"] + r["title"] for w in negative_words)
    ]

    neg_keyword_count = {}
    for r in neg_reviews:
        text = r["content"] + r["title"]
        for w in negative_words:
            if w in text:
                neg_keyword_count[w] = neg_keyword_count.get(w, 0) + 1

    return {
        "count": len(reviews),
        "avg_rating": avg,
        "rating_dist": dict(sorted(dist.items())),
        "latest": reviews[:5],
        "recent_7d_count": len(recent),
        "sentiment": {"positive": positive, "neutral": neutral, "negative": negative},
        "negative_keywords": dict(sorted(neg_keyword_count.items(), key=lambda x: -x[1])),
        "negative_mentions": len(neg_reviews),
        "negative_samples": neg_reviews[:3],
        "api_status": api_status,
        "api_error": api_error,
        "source": source,
    }


def load_manual_overrides(path="manual_overrides.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def collect_all():
    """采集所有竞品数据并返回结构化字典。"""
    manual = load_manual_overrides()
    now = datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    result = {"generated_at": now, "competitors": []}

    for comp in COMPETITORS:
        itunes_id = comp["itunes_id"]
        details = fetch_app_details(itunes_id)
        ranks = fetch_chart_rank(itunes_id)
        reviews = fetch_reviews(itunes_id, pages=REVIEW_PAGES)

        override = manual.get(comp["key"], {})
        item = {
            "key": comp["key"],
            "name": comp.get("display_name", comp["name"]),
            "full_name": comp["name"],
            "itunes_id": itunes_id,
            "app_store": details,
            "chart_rank": ranks,
            "reviews": reviews,
            "manual": override,
            "bilibili_sentiment": None,
        }

        # 如果配置了 Bilibili 关键词，则采集 B 站舆情作为 App Store 评论的补充
        bilibili_keyword = comp.get("bilibili_keyword")
        if bilibili_keyword:
            try:
                item["bilibili_sentiment"] = collect_bilibili_sentiment(
                    bilibili_keyword,
                    max_videos=10,
                    max_comments_per_video=20,
                )
            except Exception:
                # B 站接口不稳定，失败不阻断主流程
                pass
        result["competitors"].append(item)

    return result


if __name__ == "__main__":
    data = collect_all()
    print(json.dumps(data, ensure_ascii=False, indent=2))
