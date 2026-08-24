#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapTap 舆情采集：从 taptap.cn webapiv2 获取评分与热门评论。

当前仅接入「三国杀：一将成名」做跑通验证，后续可在 config.py 中补充其他竞品的
`taptap_app_id` 后批量采集。
"""

import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta


CN_TZ = timezone(timedelta(hours=8))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

API_BASE = "https://www.taptap.cn/webapiv2"


def _xua():
    uid = str(uuid.uuid4())
    return (
        f"V=1&PN=WebApp&LANG=zh_CN&VN_CODE=100000000&LOC=CN"
        f"&PLT=PC&DS=Android&UID={uid}&OS=Windows&OSV=10&DT=PC"
    )


def _request_json(endpoint, params, max_retries=2, timeout=20):
    """调用 TapTap webapiv2 端点，失败时简单重试。"""
    query = urllib.parse.urlencode(params, safe="") + "&X-UA=" + urllib.parse.quote(_xua(), safe="")
    url = f"{API_BASE}/{endpoint}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.taptap.cn/",
            "Origin": "https://www.taptap.cn",
            "Accept-Encoding": "identity",
        },
    )
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", "ignore")
                data = json.loads(text)
                if data.get("success"):
                    return data.get("data", {})
                # 某些接口返回 success:false 但 data 里包含错误信息
                return data.get("data", {})
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise last_err


def _clean_html(text):
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_review(moment_item):
    """从 moment 结构中解析出一条结构化评论。"""
    moment = moment_item.get("moment") or moment_item
    review = moment.get("review") or {}
    contents = review.get("contents") or {}
    author = (moment.get("author") or {}).get("user") or {}
    text = _clean_html(contents.get("text", ""))
    return {
        "id": moment.get("id_str"),
        "review_id": review.get("id"),
        "author": author.get("name", "匿名"),
        "score": review.get("score"),
        "text": text,
        "created_time": moment.get("created_time"),
        "link": f"https://www.taptap.cn/moment/{moment.get('id_str')}",
    }


def fetch_app_stats(app_id):
    """获取 App 评分、总评数、最新版本评分等统计信息。"""
    data = _request_json("review/v1/init-by-app", {"app_id": app_id})
    stat = (data.get("init_data") or {}).get("stat_info") or {}
    rating = stat.get("rating") or {}
    return {
        "review_count": stat.get("count", 0),
        "rating": float(rating["score"]) if rating.get("score") else None,
        "rating_max": rating.get("max", 10),
        "latest_score": float(rating["latest_score"]) if rating.get("latest_score") else None,
        "latest_version_score": float(rating["latest_version_score"]) if rating.get("latest_version_score") else None,
        "latest_review_count": rating.get("latest_review_count", 0),
        "latest_version_review_count": rating.get("latest_version_review_count", 0),
        "vote_info": stat.get("vote_info", {}),
    }


def fetch_hot_reviews(app_id, limit=5):
    """获取 App 的热门评价。"""
    data = _request_json(
        "review/v2/list-by-app",
        {"app_id": app_id, "limit": limit, "sort": "hot", "stage_type": 2},
    )
    items = data.get("list", [])
    return [_parse_review(item) for item in items]


def collect_taptap(app_id):
    """采集单个 App 的 TapTap 数据。"""
    if not app_id:
        return {"source": "taptap", "app_id": app_id, "error": "未配置 app_id"}

    try:
        stats = fetch_app_stats(app_id)
        reviews = fetch_hot_reviews(app_id, limit=5)
        return {
            "source": "taptap",
            "app_id": app_id,
            "collected_at": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "app_url": f"https://www.taptap.cn/app/{app_id}",
            "review_count": stats.get("review_count", 0),
            "rating": stats.get("rating"),
            "rating_max": stats.get("rating_max", 10),
            "latest_score": stats.get("latest_score"),
            "latest_version_score": stats.get("latest_version_score"),
            "latest_review_count": stats.get("latest_review_count", 0),
            "latest_version_review_count": stats.get("latest_version_review_count", 0),
            "vote_info": stats.get("vote_info", {}),
            "hot_reviews": reviews,
        }
    except Exception as e:
        return {
            "source": "taptap",
            "app_id": app_id,
            "error": str(e),
        }


if __name__ == "__main__":
    result = collect_taptap(145396)
    print(json.dumps(result, ensure_ascii=False, indent=2))
