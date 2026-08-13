#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把采集结果格式化为 Markdown 简报。"""

import glob
import html
import json
import os
import re
from datetime import datetime, timezone, timedelta

from history import load_history


CN_TZ = timezone(timedelta(hours=8))

# GitHub Pages 站点地址，扩展会从该地址读取线上简报
PAGES_BASE = "https://dyingyogurt.github.io/competitor_briefing"


def _rank_text(rank):
    if rank is None:
        return "未进入 Top100（Apple 公开 RSS 仅提供前 100 名）"
    if isinstance(rank, int):
        change = ""
        if rank <= 10:
            change = "🔥"
        return f"第 {rank} 名 {change}"
    return str(rank)


def _render_sampling_note():
    """生成 Markdown 数据取样说明。"""
    return [
        "## 📋 数据取样说明",
        "",
        "- **App Store 版本 / 评分**：通过 iTunes Lookup API（中国区）获取，包含最新版本号、更新日期、开发商、总评分及评分人数。",
        "- **iOS 榜单**：使用 Apple 公开 RSS 榜单（总畅销 / 总免费 / 游戏畅销 / 游戏免费），仅覆盖 Top100；超过 100 名显示「未进入 Top100」。",
        "- **App Store 评论**：优先抓取 RSS 最新评论（每页约 50 条，最多 2 页，共约 100 条）；当 RSS 无数据时，自动抓取 App Store 详情页「精选评论」作为兜底（通常 4 条，非实时）。",
        "- **Bilibili 舆情**：搜索竞品关键词，仅采集**前一天 0:00–23:59（北京时间）**发布的热门视频；取综合排序前 10 个视频，每个视频取热门评论前 20 条进行情感统计。",
        "- **情感统计规则**：评论命中正面词表记为正面，命中负面词表记为负面，否则为中性；典型差评从负面样本中按顺序展示。",
        "- **历史异动**：每天保存版本号和榜单排名快照；异动标准为版本号变化，或榜单变化绝对值 ≥ 5 位 / 进出榜。",
        "- **人工补充**：`manual_overrides.json` 中的 TapTap 评分、热度、市场动向、重点活动、备注等会直接展示在报告中。",
        "",
    ]


def _sampling_note_html():
    """生成 HTML 版取样说明。"""
    return """<details class="sampling-note" open>
  <summary>📋 数据取样说明</summary>
  <ul>
    <li><strong>App Store 版本 / 评分</strong>：通过 iTunes Lookup API（中国区）获取，包含最新版本号、更新日期、开发商、总评分及评分人数。</li>
    <li><strong>iOS 榜单</strong>：使用 Apple 公开 RSS 榜单（总畅销 / 总免费 / 游戏畅销 / 游戏免费），仅覆盖 Top100。</li>
    <li><strong>App Store 评论</strong>：优先抓取 RSS 最新评论（每页约 50 条，最多 2 页）；RSS 无数据时，自动抓取 App Store 详情页「精选评论」兜底（通常 4 条，非实时）。</li>
    <li><strong>Bilibili 舆情</strong>：搜索竞品关键词，仅采集<strong>前一天 0:00–23:59（北京时间）</strong>发布的热门视频；取综合排序前 10 个视频，每个视频取热门评论前 20 条。</li>
    <li><strong>情感统计</strong>：评论命中正面词表为正面，命中负面词表为负面，否则为中性。</li>
    <li><strong>历史异动</strong>：每天保存快照；异动标准为版本号变化，或榜单变化绝对值 ≥ 5 位 / 进出榜。</li>
    <li><strong>人工补充</strong>：<code>manual_overrides.json</code> 中的 TapTap 评分、热度、市场动向、重点活动、备注等会直接展示。</li>
  </ul>
</details>"""


def _render_competitor(item, idx):
    name = item["name"]
    full = item["full_name"]
    store = item["app_store"]
    rank = item["chart_rank"]
    rev = item["reviews"]
    manual = item.get("manual", {})

    lines = [f"## {idx}. {name}（{full}）", ""]

    if "error" in store:
        lines.append(f"⚠️ App Store 数据异常：{store['error']}")
        lines.append("")
        return "\n".join(lines)

    # 版本信息
    lines.append("### 📦 版本更新")
    lines.append(f"- **当前版本**：{store.get('version', '—')}")
    lines.append(f"- **更新日期**：{store.get('release_date', '—')}")
    lines.append(f"- **开发商**：{store.get('seller', '—')}")
    if store.get("rating") is not None:
        lines.append(f"- **App Store 总评分**：{store['rating']} 分（{store.get('rating_count', '—')} 个评分）")
    notes = store.get("release_notes") or "暂无更新说明"
    lines.append("- **更新内容**：")
    for line in notes.splitlines():
        if line.strip():
            lines.append(f"  - {line.strip()}")
    lines.append("")

    # 榜单
    lines.append("### 📊 iOS 榜单异动")
    if rank:
        for chart, r in rank.items():
            lines.append(f"- **{chart}**：{_rank_text(r)}")
    else:
        lines.append("- 暂无榜单数据")
    lines.append("")

    # 评论
    source_note = ""
    if rev.get("source") == "app_store_page":
        source_note = "（App Store RSS 近期评论为空，以下为页面精选评论兜底）"
    lines.append(f"### 💬 App Store 玩家舆论{source_note}")
    if rev.get("count", 0):
        lines.append(f"- **样本数**：{rev['count']} 条，近 7 天 {rev.get('recent_7d_count', 0)} 条")
        lines.append(f"- **平均评分**：{rev.get('avg_rating', '—')}")
        dist = rev.get("rating_dist", {})
        if dist:
            stars = "/".join([f"{s}星:{dist.get(s,0)}" for s in range(1, 6)])
            lines.append(f"- **评分分布**：{stars}")
        lines.append(f"- **负面/吐槽提及**：{rev.get('negative_mentions', 0)} 条")
        if rev.get("negative_samples"):
            lines.append("- **典型差评**：")
            for s in rev["negative_samples"]:
                title = s.get("title", "")
                content = s.get("content", "")[:80]
                lines.append(f"  - ⭐{s.get('rating')}「{title}」{content}")
    else:
        status = rev.get("api_status")
        if status == "empty":
            lines.append("- App Store 评论接口当前未返回数据（可能是因为中国区 RSS 评论接口暂时不可用）")
            lines.append("- 建议在 `manual_overrides.json` 中补充 TapTap 评分、玩家吐槽或社媒舆情")
        elif status == "error":
            lines.append(f"- App Store 评论获取失败：{rev.get('api_error', '未知错误')}")
        else:
            lines.append("- 暂无评论数据")
    lines.append("")

    # Bilibili 舆情补充
    bilibili = item.get("bilibili_sentiment")
    if bilibili and bilibili.get("comment_count"):
        lines.append("### ▶️ Bilibili 玩家舆情补充")
        sent = bilibili["sentiment"]
        lines.append(f"- **采样视频**：{len(bilibili['videos'])} 个，共 {bilibili['comment_count']} 条采样评论")
        lines.append(
            f"- **加权情感分布**（按点赞加权，含视频标题）："
            f"正面 {sent.get('positive', 0)} / 负面 {sent.get('negative', 0)} / 中性 {sent.get('neutral', 0)}"
        )
        neg_kw = bilibili.get("negative_keywords", {})
        if neg_kw:
            lines.append(f"- **负面高频词**：{', '.join([f'{k}({v})' for k, v in list(neg_kw.items())[:5]])}")
        if bilibili.get("top_comments"):
            lines.append("- **热门评论**：")
            for c in bilibili["top_comments"][:3]:
                content = c.get("content", "")[:70]
                lines.append(f"  - 👍{c.get('like', 0)}「{content}」")
        lines.append("")

    # 人工补充（TapTap / 官网 / 社媒）
    lines.append("### 🔍 其他渠道补充")
    if manual:
        if manual.get("taptap_rating"):
            lines.append(f"- **TapTap 评分**：{manual['taptap_rating']}")
        if manual.get("taptap_heat"):
            lines.append(f"- **TapTap 热度**：{manual['taptap_heat']}")
        if manual.get("marketing"):
            lines.append(f"- **市场动向**：{manual['marketing']}")
        if manual.get("events"):
            lines.append(f"- **重点活动**：{manual['events']}")
        if manual.get("notes"):
            lines.append(f"- **备注**：{manual['notes']}")
    else:
        lines.append("- 暂无人工补充（可在 manual_overrides.json 中维护）")
    lines.append("")

    return "\n".join(lines)


def generate_briefing(data, output_dir="output", changes=None, prev_date=None):
    date_str = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    title = f"三国杀竞品日报｜{date_str}"

    lines = [
        f"# {title}",
        "",
        f"> 数据生成时间：{data['generated_at']}（北京时间）",
        "> 来源：App Store（版本 / 榜单 / 评论）、Bilibili 玩家舆情、manual_overrides.json",
        "",
        "---",
        "",
    ]
    lines.extend(_render_sampling_note())
    lines.extend([
        "## 📌 今日摘要",
        "",
        _generate_summary(data, changes=changes, prev_date=prev_date),
        "",
        "---",
        "",
    ])

    for idx, item in enumerate(data["competitors"], start=1):
        lines.append(_render_competitor(item, idx))
        lines.append("---")
        lines.append("")

    lines.append("## 🎯 启示")
    lines.append("")
    lines.append(_generate_insights(data))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本简报由脚本自动生成，仅供参考。*")

    md = "\n".join(lines)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"daily_briefing_{date_str}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path, md


def _generate_summary(data, changes=None, prev_date=None):
    bullets = []
    for c in data["competitors"]:
        name = c["name"]
        store = c.get("app_store", {})
        if "error" in store:
            bullets.append(f"- **{name}**：App Store 数据异常，需人工检查")
            continue
        version = store.get("version", "—")
        release = store.get("release_date", "—")
        rank_info = c.get("chart_rank", {})
        top_rank = None
        top_chart = None
        for chart, r in rank_info.items():
            if isinstance(r, int):
                if top_rank is None or r < top_rank:
                    top_rank = r
                    top_chart = chart
        rank_str = f"iOS Top100 最高第 {top_rank} 名（{top_chart}）" if top_rank else "未进入 iOS Top100"
        avg = c.get("reviews", {}).get("avg_rating")
        rating_str = f"App Store 近100条均分 {avg}" if avg else "暂无评论"

        extra = []
        if changes:
            ch = changes.get(c.get("key", {}), {})
            if ch.get("version_changed"):
                extra.append("🆕 版本较昨日更新")
            rank_ch = ch.get("rank_changes", {})
            if rank_ch:
                parts = []
                for chart2, det in rank_ch.items():
                    delta = det.get("delta")
                    if delta is not None:
                        arrow = "↑" if delta > 0 else "↓"
                        parts.append(f"{chart2}: {arrow}{abs(delta)}")
                    else:
                        parts.append(f"{chart2}: 新上榜/掉榜")
                extra.append("📈 榜单异动：" + "，".join(parts))

        line = f"- **{name}**：版本 {version}（{release}），{rank_str}，{rating_str}。"
        if extra:
            line += " " + "；".join(extra)
        bullets.append(line)

    if prev_date and not any(ch.get("rank_changes") or ch.get("version_changed")
                              for ch in (changes or {}).values()):
        bullets.append(f"- 较 {prev_date} 暂无显著版本或榜单异动")

    return "\n".join(bullets)


def _product_negative_count(item):
    """汇总 App Store + Bilibili 负面提及数。"""
    rev = item.get("reviews", {})
    sent = (item.get("bilibili_sentiment") or {}).get("sentiment", {})
    return rev.get("negative_mentions", 0) + sent.get("negative", 0)


NEGATIVE_KEYWORD_CATEGORIES = {
    "氪金/付费": ["氪金", "逼氪", "重氪", "坑钱", "骗氪", "圈钱", "骗钱", "吃相", "割韭菜", "贵", "不值", "保底", "爆率低", "抽不到"],
    "数值平衡": ["阴间", "超模", "下水道", "天牢", "弱", "废", "打不过", "数值崩", "不平衡", "畸形", "离谱"],
    "体验/稳定性": ["bug", "卡顿", "闪退", "掉线", "卡死", "延迟", "黑屏"],
    "社区/环境": ["人机", "演员", "环境差", "退游", "弃坑", "卸载", "差评", "后悔", "上当", "失望", "垃圾", "烂", "恶心", "坑"],
}


def _get_product_negative_keywords(item, top_n=3):
    """合并 App Store + Bilibili 的负面高频词。"""
    rev_kw = item.get("reviews", {}).get("negative_keywords", {})
    bilibili_kw = (item.get("bilibili_sentiment") or {}).get("negative_keywords", {})
    merged = {}
    for k, v in {**rev_kw, **bilibili_kw}.items():
        merged[k] = merged.get(k, 0) + v
    return sorted(merged.items(), key=lambda x: -x[1])[:top_n]


def _classify_negative_keywords(keywords):
    """根据负面高频词归属到具体类别，并返回类别 + 代表性关键词。"""
    if not keywords:
        return "玩家满意度", []
    scores = {cat: 0 for cat in NEGATIVE_KEYWORD_CATEGORIES}
    for kw, count in keywords:
        for cat, words in NEGATIVE_KEYWORD_CATEGORIES.items():
            if any(w in kw for w in words):
                scores[cat] += count
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    top_cats = [cat for cat, score in sorted_scores if score > 0][:2]
    category = "、".join(top_cats) if top_cats else "玩家满意度"
    return category, [kw for kw, _ in keywords]


def _generate_insights(data):
    """基于负面高频词生成具体归因的启示。"""
    parts = []
    for c in data["competitors"]:
        name = c["name"]
        neg = _product_negative_count(c)
        if neg < 5:
            continue

        top_kw = _get_product_negative_keywords(c, top_n=3)
        category, kw_list = _classify_negative_keywords(top_kw)
        kw_text = "、".join([f"{k}（{v}次）" for k, v in top_kw]) if top_kw else "未提取到明确关键词"

        if name == "三国杀一将成名":
            parts.append(
                f"- **{name}** 自身负面反馈较多（{neg} 条），玩家主要围绕 **{category}** 发声，"
                f"高频词包括 {kw_text}。建议相关团队重点关注社区情绪，评估是否需要公告回应或针对性调整。"
            )
        else:
            parts.append(
                f"- **{name}** 近期负面声音较多（{neg} 条），集中在 **{category}**，"
                f"玩家高频吐槽 {kw_text}。三国杀一将成名可提前排查是否存在同类问题，并在宣发/运营中规避敏感点。"
            )

    if not parts:
        parts.append("- 今日数据相对平稳，建议持续观察榜单与版本节奏。")
    return "\n".join(parts)


def _per_product_insight(item):
    """为单个竞品生成一条洞察，用于放在该游戏概览卡片前。"""
    name = item["name"]
    neg = _product_negative_count(item)
    if neg < 5:
        return f"舆情相对平稳，建议持续关注榜单与版本节奏。"

    top_kw = _get_product_negative_keywords(item, top_n=3)
    category, _ = _classify_negative_keywords(top_kw)
    kw_text = "、".join([f"{k}（{v}次）" for k, v in top_kw]) if top_kw else "未提取到明确关键词"

    if name == "三国杀一将成名":
        return (
            f"负面反馈较多（{neg} 条），集中在 **{category}**，"
            f"高频词：{kw_text}。建议关注社区情绪并及时回应。"
        )
    return (
        f"负面反馈较多（{neg} 条），集中在 **{category}**，"
        f"高频词：{kw_text}。可提前排查同类问题并在宣发/运营中规避。"
    )


def _generate_highlights(data, changes=None, prev_date=None):
    """生成今日重点关注条目，用于顶部高优提示。"""
    highlights = []
    today = datetime.now(CN_TZ).date()

    for item in data["competitors"]:
        name = item["name"]
        key = item.get("key", name)
        store = item.get("app_store", {})
        rev = item.get("reviews", {})
        neg = _product_negative_count(item)
        avg = rev.get("avg_rating")
        change = (changes or {}).get(key, {})

        # 负面舆情
        if neg >= 30:
            highlights.append({"level": "danger", "text": f"**{name}** 负面舆情较高（{neg} 条），建议重点关注。"})
        elif neg >= 10:
            highlights.append({"level": "warning", "text": f"**{name}** 出现一定负面声音（{neg} 条），可留意避免同类节奏。"})

        # 版本更新（最近 3 天或历史对比有变更）
        version = store.get("version")
        release_date = store.get("release_date")
        version_changed = False
        try:
            release = datetime.strptime(release_date, "%Y-%m-%d").date()
            days_since = (today - release).days
            version_changed = days_since <= 3 or change.get("version_changed")
        except Exception:
            version_changed = change.get("version_changed", False)
        if version_changed and version:
            highlights.append({"level": "info", "text": f"**{name}** 更新至版本 {version}（{release_date}）。"})

        # 评分极低
        if avg is not None and avg <= 2.0:
            highlights.append({"level": "danger", "text": f"**{name}** App Store 均分较低（{avg}），玩家满意度明显下降。"})

        # 榜单异动
        for chart, rc in change.get("rank_changes", {}).items():
            delta = rc.get("delta")
            if isinstance(delta, int):
                if delta >= 10:
                    highlights.append({"level": "info", "text": f"**{name}** 在 {chart} 上升 {delta} 名（#{rc['from']} → #{rc['to']}）。"})
                elif delta <= -10:
                    highlights.append({"level": "warning", "text": f"**{name}** 在 {chart} 下滑 {abs(delta)} 名（#{rc['from']} → #{rc['to']}）。"})
            elif delta is None:
                if rc["to"] is not None:
                    highlights.append({"level": "info", "text": f"**{name}** 在 {chart} 进入 Top100（#{rc['to']}）。"})

    if not highlights:
        highlights.append({"level": "ok", "text": "今日竞品数据相对平稳，暂无显著异动。"})
    return highlights


def _rank_text_html(rank):
    if rank is None:
        return "未进入 Top100（Apple 公开 RSS 仅提供前 100 名）"
    if isinstance(rank, int):
        badge = "<span class='badge hot'>Top10</span>" if rank <= 10 else ""
        return f"第 {rank} 名 {badge}"
    return str(rank)


def _update_notes_html(notes):
    if not notes or not notes.strip():
        return "<p class='empty'>暂无更新说明</p>"
    lines = [line.strip() for line in notes.splitlines() if line.strip()]
    if not lines:
        return "<p class='empty'>暂无更新说明</p>"

    MAX_VISIBLE = 5
    if len(lines) <= MAX_VISIBLE:
        return "<ul class='update-list'>" + "".join(f"<li>{line}</li>" for line in lines) + "</ul>"

    visible = "".join(f"<li>{line}</li>" for line in lines[:MAX_VISIBLE])
    hidden = "".join(f"<li>{line}</li>" for line in lines[MAX_VISIBLE:])
    return f"""
    <ul class='update-list'>{visible}</ul>
    <details class='update-details'>
        <summary>展开全部 {len(lines)} 条更新说明</summary>
        <ul class='update-list'>{hidden}</ul>
    </details>
    """


def _rank_card_html(chart_name, rank):
    if rank is None:
        return f"""
        <div class="rank-card rank-missing">
            <div class="rank-title">{chart_name}</div>
            <div class="rank-number">—</div>
            <div class="rank-tag">未进 Top100</div>
        </div>
        """
    if isinstance(rank, int):
        tag = "<div class='rank-tag hot'>Hot</div>" if rank <= 10 else ""
        number_class = "rank-number" if rank > 10 else "rank-number hot-number"
        return f"""
        <div class="rank-card rank-ok">
            <div class="rank-title">{chart_name}</div>
            <div class="{number_class}">#{rank}</div>
            {tag}
        </div>
        """
    return f"""
    <div class="rank-card rank-error">
        <div class="rank-title">{chart_name}</div>
        <div class="rank-number">{rank}</div>
    </div>
    """


def _overview_version_card(store):
    version = store.get("version", "—")
    release = store.get("release_date", "—")
    notes = store.get("release_notes", "") or ""
    first_line = notes.strip().splitlines()[0] if notes.strip() else "暂无详细说明"
    # 截断到一行
    summary = first_line[:40] + "…" if len(first_line) > 40 else first_line
    return f"""
    <div class="overview-card">
        <div class="overview-header"><span class="overview-icon">📦</span><span class="overview-title">版本更新</span></div>
        <div class="overview-value">v{version}</div>
        <div class="overview-summary">{release}<br>{summary}</div>
    </div>
    """


def _overview_rank_card(rank):
    if not rank:
        return """
        <div class="overview-card">
            <div class="overview-header"><span class="overview-icon">📊</span><span class="overview-title">iOS 榜单</span></div>
            <div class="overview-value">—</div>
            <div class="overview-summary">暂无榜单数据</div>
        </div>
        """
    ranked = [r for r in rank.values() if isinstance(r, int)]
    best_rank = min(ranked) if ranked else None
    value = f"#{best_rank}" if best_rank is not None else "未上榜"

    items = []
    for chart, r in rank.items():
        short = chart.replace('iOS ', '').replace('榜', '')
        if r is None:
            items.append(f"{short} 未上榜")
        elif isinstance(r, int):
            items.append(f"{short} #{r}")
        else:
            items.append(f"{short} {r}")
    summary = " / ".join(items)
    return f"""
    <div class="overview-card">
        <div class="overview-header"><span class="overview-icon">📊</span><span class="overview-title">iOS 榜单</span></div>
        <div class="overview-value">{value}</div>
        <div class="overview-summary">{summary}</div>
    </div>
    """


def _overview_appstore_card(rev):
    if not rev.get("count"):
        return """
        <div class="overview-card">
            <div class="overview-header"><span class="overview-icon">💬</span><span class="overview-title">App Store</span></div>
            <div class="overview-value">—</div>
            <div class="overview-summary">暂无评论数据</div>
        </div>
        """
    avg = rev.get("avg_rating", "—")
    neg = rev.get("negative_mentions", 0)
    kw = rev.get("negative_keywords", {})
    kw_text = "、".join([k for k, _ in list(kw.items())[:3]]) if kw else "暂无明确关键词"
    return f"""
    <div class="overview-card">
        <div class="overview-header"><span class="overview-icon">💬</span><span class="overview-title">App Store</span></div>
        <div class="overview-value">⭐ {avg}</div>
        <div class="overview-summary">负面吐槽 {neg} 条<br>高频词：{kw_text}</div>
    </div>
    """


def _overview_bilibili_card(bilibili):
    if not bilibili or not bilibili.get("comment_count"):
        return """
        <div class="overview-card">
            <div class="overview-header"><span class="overview-icon">▶️</span><span class="overview-title">Bilibili</span></div>
            <div class="overview-value">—</div>
            <div class="overview-summary">暂无 Bilibili 数据</div>
        </div>
        """
    sent = bilibili["sentiment"]
    total = sum(sent.values())
    pos = sent.get("positive", 0)
    neg = sent.get("negative", 0)
    neu = sent.get("neutral", 0)
    pos_pct = round(pos / total * 100, 1) if total else 0
    neg_pct = round(neg / total * 100, 1) if total else 0
    neu_pct = round(neu / total * 100, 1) if total else 0
    kw = bilibili.get("negative_keywords", {})
    kw_text = "、".join([k for k, _ in list(kw.items())[:2]]) if kw else "暂无"
    return f"""
    <div class="overview-card">
        <div class="overview-header"><span class="overview-icon">▶️</span><span class="overview-title">Bilibili</span></div>
        <div class="overview-mini-sentiment">
            <div class="mini-sentiment-bar" title="正面 {pos} / 中性 {neu} / 负面 {neg}">
                <div class="mini-segment mini-positive" style="width: {pos_pct}%"></div>
                <div class="mini-segment mini-neutral" style="width: {neu_pct}%"></div>
                <div class="mini-segment mini-negative" style="width: {neg_pct}%"></div>
            </div>
            <div class="mini-sentiment-label">正 {pos_pct}% · 中 {neu_pct}% · 负 {neg_pct}%</div>
        </div>
        <div class="overview-summary">{bilibili['comment_count']} 条采样评论，高频负面词：{kw_text}</div>
    </div>
    """


def _sentiment_bar_html(sentiment):
    total = sum(sentiment.values())
    if total == 0:
        return "<p class='empty'>暂无情感分布数据</p>"
    pos = sentiment.get('positive', 0)
    neg = sentiment.get('negative', 0)
    neu = sentiment.get('neutral', 0)
    pos_pct = round(pos / total * 100, 1)
    neg_pct = round(neg / total * 100, 1)
    neu_pct = round(neu / total * 100, 1)
    return f"""
    <div class="sentiment-bar-wrap">
        <div class="sentiment-bar" title="正面 {pos} / 中性 {neu} / 负面 {neg}">
            <div class="sentiment-segment sentiment-positive" style="width: {pos_pct}%"></div>
            <div class="sentiment-segment sentiment-neutral" style="width: {neu_pct}%"></div>
            <div class="sentiment-segment sentiment-negative" style="width: {neg_pct}%"></div>
        </div>
        <div class="sentiment-legend">
            <span><span class="dot dot-positive"></span> 正面 {pos} ({pos_pct}%)</span>
            <span><span class="dot dot-neutral"></span> 中性 {neu} ({neu_pct}%)</span>
            <span><span class="dot dot-negative"></span> 负面 {neg} ({neg_pct}%)</span>
        </div>
    </div>
    """


def _keywords_html(keywords, label="负面高频词"):
    if not keywords:
        return ""
    chips = " ".join(
        f'<span class="keyword-chip">{k} <small>{v}</small></span>'
        for k, v in list(keywords.items())[:8]
    )
    return f'<div class="keywords-wrap"><strong>{label}：</strong>{chips}</div>'


def _appstore_comments_html(rev, limit=5):
    samples = rev.get("negative_samples", [])
    if not samples:
        return "<p class='empty'>暂无典型差评</p>"
    bubbles = []
    for s in samples[:limit]:
        title = s.get("title", "")
        content = s.get("content", "")[:120]
        rating = s.get("rating", "")
        bubbles.append(
            f'<div class="comment-bubble"><span class="comment-rating">⭐{rating}</span> <strong>{title}</strong> {content}</div>'
        )
    return "".join(bubbles)


def _bilibili_comments_html(bilibili, limit=5):
    comments = bilibili.get("top_comments", [])
    if not comments:
        return "<p class='empty'>暂无热门评论</p>"
    bubbles = []
    for c in comments[:limit]:
        content = c.get("content", "")[:140]
        like = c.get("like", 0)
        bubbles.append(
            f'<div class="comment-bubble"><span class="comment-like">👍 {like}</span> {content}</div>'
        )
    return "".join(bubbles)


def _bilibili_video_list_html(bilibili):
    videos = bilibili.get("videos", [])
    if not videos:
        return ""
    items = []
    for v in videos:
        title = (v.get("title") or "无标题").replace('"', '&quot;')
        author = v.get("author") or "未知作者"
        link = v.get("link") or "#"
        fetched = v.get("comments_fetched", 0)
        items.append(f"""
        <a href="{link}" target="_blank" class="video-item" title="{title}">
            <div class="video-title">{title}</div>
            <div class="video-author">@{author} · 已采 {fetched} 条</div>
        </a>
        """)
    return f"""
    <details class='video-details'>
        <summary>查看 {len(videos)} 个采样视频</summary>
        <div class='video-list'>{"".join(items)}</div>
    </details>
    """


def _detail_version_section(store):
    version = store.get("version", "—")
    release = store.get("release_date", "—")
    seller = store.get("seller") or ""
    notes_html = _update_notes_html(store.get("release_notes", ""))
    return f"""
    <div class="detail-section">
        <h3>📦 版本更新</h3>
        <div class="detail-row">
            <div class="detail-col-left">
                <div class="version-line">
                    <span class="version-badge">v{version}</span>
                    <span class="date-label">{release}</span>
                </div>
                <p class="seller">{seller}</p>
            </div>
            <div class="detail-col-right">
                {notes_html}
            </div>
        </div>
    </div>
    """


def _detail_rank_section(rank_cards):
    return f"""
    <div class="detail-section">
        <h3>📊 iOS 榜单</h3>
        <div class="rank-grid">
            {rank_cards}
        </div>
    </div>
    """


def _detail_appstore_section(rev, store):
    if not rev.get("count"):
        return f"""
        <div class="detail-section">
            <h3>💬 App Store 玩家舆论</h3>
            <p class="empty">暂无评论数据</p>
        </div>
        """
    url = store.get("app_url") or "#"
    avg = rev.get("avg_rating", "—")
    count = rev["count"]
    recent_7d = rev.get("recent_7d_count", 0)
    sent = rev.get("sentiment", {"positive": 0, "neutral": 0, "negative": 0})
    return f"""
    <div class="detail-section">
        <h3>💬 App Store 玩家舆论</h3>
        <div class="detail-row">
            <div class="detail-col-left">
                <div class="metrics-row compact">
                    <div class="metric"><div class="metric-value">{count}</div><div class="metric-label">样本数</div></div>
                    <div class="metric"><div class="metric-value">{avg}</div><div class="metric-label">平均评分</div></div>
                    <div class="metric"><div class="metric-value">{recent_7d}</div><div class="metric-label">近 7 天</div></div>
                </div>
                <a class="store-link" href="{url}" target="_blank">打开 App Store →</a>
            </div>
            <div class="detail-col-right">
                {_sentiment_bar_html(sent)}
                {_keywords_html(rev.get("negative_keywords"), "负面高频词")}
                <h4 class="sub-section-title">代表评论</h4>
                {_appstore_comments_html(rev)}
            </div>
        </div>
    </div>
    """


def _detail_bilibili_section(bilibili):
    if not bilibili or not bilibili.get("comment_count"):
        return """
        <div class="detail-section">
            <h3>▶️ Bilibili 玩家舆情补充</h3>
            <p class="empty">暂无 Bilibili 数据</p>
        </div>
        """
    sent = bilibili["sentiment"]
    video_count = len(bilibili.get("videos", []))
    comment_count = bilibili["comment_count"]
    return f"""
    <div class="detail-section">
        <h3>▶️ Bilibili 玩家舆情补充</h3>
            <div class="detail-row">
            <div class="detail-col-left">
                <div class="metrics-row compact">
                    <div class="metric"><div class="metric-value">{video_count}</div><div class="metric-label">采样视频</div></div>
                    <div class="metric"><div class="metric-value">{comment_count}</div><div class="metric-label">采样评论数</div></div>
                </div>
            </div>
            <div class="detail-col-right">
                {_sentiment_bar_html(sent)}
                {_keywords_html(bilibili.get("negative_keywords"), "负面高频词")}

                <h4 class="sub-section-title">代表评论</h4>
                {_bilibili_comments_html(bilibili)}
                {_bilibili_video_list_html(bilibili)}
            </div>
        </div>
    </div>
    """


def _detail_manual_section(manual_html):
    if not manual_html:
        return ""
    return f"""
    <div class="detail-section">
        <h3>🔍 其他渠道补充</h3>
        {manual_html}
    </div>
    """


def _trend_data_for_key(key, history, current_item=None, days=30):
    """从历史快照 + 当日数据中，提取某个竞品最近 N 天的趋势数据。"""
    dates = []
    today_str = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    end = datetime.now(CN_TZ)
    for i in range(days - 1, -1, -1):
        dates.append((end - timedelta(days=i)).strftime("%Y-%m-%d"))

    app_store_rating = []
    review_avg_rating = []
    bilibili_positive = []
    bilibili_negative = []
    game_rank = []

    for d in dates:
        if current_item and d == today_str and current_item.get("key") == key:
            snap_store = current_item.get("app_store", {})
            snap_rev = current_item.get("reviews", {})
            snap_bili = current_item.get("bilibili_sentiment") or {}
            app_store_rating.append(snap_store.get("rating"))
            review_avg_rating.append(snap_rev.get("avg_rating"))
            b_sent = snap_bili.get("sentiment", {})
            bilibili_positive.append(b_sent.get("positive"))
            bilibili_negative.append(b_sent.get("negative"))
            ranks = current_item.get("chart_rank", {})
            game_rank.append(ranks.get("iOS 游戏畅销榜"))
        else:
            snap = history.get(d, {}).get(key, {})
            app_store_rating.append(snap.get("app_store_rating"))
            review_avg_rating.append(snap.get("review_avg_rating"))
            b_sent = snap.get("bilibili_sentiment", {})
            bilibili_positive.append(b_sent.get("positive"))
            bilibili_negative.append(b_sent.get("negative"))
            ranks = snap.get("ranks", {})
            game_rank.append(ranks.get("iOS 游戏畅销榜"))

    return {
        "dates": dates,
        "app_store_rating": app_store_rating,
        "review_avg_rating": review_avg_rating,
        "bilibili_positive": bilibili_positive,
        "bilibili_negative": bilibili_negative,
        "game_rank": game_rank,
    }


def _svg_line_chart(dates, values, color, title, y_min=0, y_max=None, width=360, height=90, help=None):
    """生成轻量级 SVG 折线图；values 中 None 的点会被跳过。"""
    clean = [(i, v) for i, v in enumerate(values) if isinstance(v, (int, float))]
    if not clean:
        return ""

    xs = [i for i, _ in clean]
    ys = [v for _, v in clean]
    if y_max is None:
        y_max = max(ys) if ys else 1
    if y_min is None:
        y_min = min(ys) if ys else 0
    if y_max == y_min:
        y_max = y_min + 1

    n = len(values)
    pad_left, pad_right, pad_top, pad_bottom = 28, 12, 18, 22
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def px(i, v):
        x = pad_left + (i / (n - 1)) * plot_w if n > 1 else pad_left + plot_w / 2
        y = pad_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h
        return round(x, 1), round(y, 1)

    points = []
    for i, v in clean:
        x, y = px(i, v)
        points.append(f"{x},{y}")

    polyline = " ".join(points)
    last_x, last_y = px(clean[-1][0], clean[-1][1])
    last_value = clean[-1][1]

    # 为每个数据点生成小圆点 + 更大的透明命中区，供 JS 悬停提示使用
    dot_svg = ""
    for i, v in clean:
        x, y = px(i, v)
        d_label = dates[i] if dates else ""
        if isinstance(d_label, str) and len(d_label) == 10:
            d_label = d_label[5:]  # YYYY-MM-DD -> MM-DD
        tip = f"{d_label}  {v:.2f}" if isinstance(v, float) else f"{d_label}  {v}"
        dot_svg += (
            f'<circle cx="{x}" cy="{y}" r="2.6" fill="{color}"/>'
            f'<circle class="dot-hit" cx="{x}" cy="{y}" r="9" fill="transparent" data-tip="{tip}"/>'
        )
    dot_svg += f'<circle class="dot-hit" cx="{last_x}" cy="{last_y}" r="9" fill="transparent" data-tip="最后 {last_value:.2f}"/><text x="{last_x}" y="{last_y - 10}" text-anchor="middle" font-size="9" font-weight="600" fill="{color}">{last_value:.2f}</text>'

    # 生成简单的 Y 轴网格线（3 条）
    grid_lines = ""
    for ratio in [0, 0.5, 1]:
        y_val = y_min + (y_max - y_min) * ratio
        gy = pad_top + plot_h - ratio * plot_h
        label = f"{y_val:.1f}" if isinstance(y_val, float) and y_val != int(y_val) else str(int(y_val))
        grid_lines += f'<line x1="{pad_left}" y1="{gy}" x2="{width - pad_right}" y2="{gy}" stroke="#e5e7eb" stroke-width="1"/>'
        grid_lines += f'<text x="{pad_left - 4}" y="{gy + 3}" text-anchor="end" font-size="9" fill="#9ca3af">{label}</text>'

    # 可选：标题旁的「i」说明按钮（悬停显示规则）
    help_html = ""
    if help:
        info_svg = (
            '<svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" aria-hidden="true">'
            '<path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 3a.75.75 0 1 1 0 1.5A.75.75 0 0 1 8 4zm1 8H7V7h2v5z"/>'
            '</svg>'
        )
        help_html = (
            f'<span class="i-help" aria-label="说明">{info_svg}<span class="i-tip">{help}</span></span>'
        )

    # X 轴日期标签：均匀显示最多 5 个，避免重叠
    def build_x_labels():
        m = len(dates)
        if m == 0:
            return ""
        if m == 1:
            idxs = [0]
        else:
            max_labels = 5
            step = max(1, (m + max_labels - 2) // (max_labels - 1))
            idxs = list(range(0, m, step))
            if idxs[-1] != m - 1:
                idxs.append(m - 1)
        labels = ""
        for i in idxs:
            x, _ = px(i, ys[0] if ys else y_min)
            label = dates[i][5:] if isinstance(dates[i], str) and len(dates[i]) == 10 else dates[i]
            anchor = "start" if i == 0 else ("end" if i == m - 1 else "middle")
            labels += f'<text x="{x}" y="{height - 4}" text-anchor="{anchor}" font-size="9" fill="#9ca3af">{label}</text>'
        return labels

    x_labels = build_x_labels()

    return f"""
    <div class="trend-chart">
        <div class="trend-title"><span class="trend-title-text">{title}{help_html}</span><span class="trend-current">最新 {last_value}</span></div>
        <svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;display:block;">
            {grid_lines}
            <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            {dot_svg}
            {x_labels}
        </svg>
    </div>
    """


def _trend_section_html(trend, key):
    """把趋势数据渲染为一组折线图。"""
    if not trend:
        return ""
    charts = []
    charts.append(_svg_line_chart(
        trend["dates"], trend["app_store_rating"], "#f59e0b",
        "App Store 总评分", y_min=1, y_max=5,
    ))
    charts.append(_svg_line_chart(
        trend["dates"], trend["review_avg_rating"], "#2563eb",
        "评论均分", y_min=1, y_max=5,
    ))
    charts.append(_svg_line_chart(
        trend["dates"], trend["bilibili_positive"], "#10b981",
        "B站 正面情感（加权）",
        help=(
            "正面分数 = 含正面关键词评论的点赞数之和（点赞为 0 计 1）。"
            "判定文本 = 视频标题 + 评论内容，命中任一正面词即计正面。"
        ),
    ))
    charts.append(_svg_line_chart(
        trend["dates"], trend["bilibili_negative"], "#ef4444",
        "B站 负面情感（加权）",
        help=(
            "负面分数 = 含负面关键词评论的点赞数之和（点赞为 0 计 1）。"
            "负面优先：命中任一负面词即判负面，即使同时含正面词。"
        ),
    ))
    charts = [c for c in charts if c]
    if not charts:
        return ""
    return f"""
    <div class="info-card wide trend-section">
        <h3>📈 近 30 天趋势</h3>
        <div class="trend-grid">{''.join(charts)}</div>
    </div>
    """


def _render_competitor_html(item, idx, history=None):
    history = history or {}
    name = item["name"]
    full = item["full_name"]
    store = item["app_store"]
    rank = item["chart_rank"]
    rev = item["reviews"]
    manual = item.get("manual", {})
    bilibili = item.get("bilibili_sentiment")
    trend = _trend_data_for_key(item.get("key", ""), history, current_item=item)
    trend_html = _trend_section_html(trend, item.get("key", ""))

    if "error" in store:
        return f"""
        <section class="competitor">
            <div class="competitor-header">
                <div class="competitor-rank">{idx}</div>
                <h2>{name} <span class="subtitle">{full}</span></h2>
            </div>
            <div class="error-card">
                <span class="error-icon">⚠️</span>
                <span>App Store 数据异常：{store['error']}</span>
            </div>
        </section>
        """

    # 榜单卡片
    rank_cards = ""
    if rank:
        for chart_name, r in rank.items():
            rank_cards += _rank_card_html(chart_name, r)
    else:
        rank_cards = "<p class='empty'>暂无榜单数据</p>"

    # App Store 评论
    reviews_html = ""
    if rev.get("count", 0):
        rating_dist = rev.get("rating_dist", {})
        rating_bar = ""
        for star in range(5, 0, -1):
            count = rating_dist.get(star, 0)
            pct = round(count / rev['count'] * 100, 1) if rev['count'] else 0
            rating_bar += f"""
            <div class="rating-row">
                <span class="star-label">{'⭐' * star}</span>
                <div class="rating-track"><div class="rating-fill" style="width: {pct}%"></div></div>
                <span class="count-label">{count}</span>
            </div>
            """
        neg_samples = ""
        if rev.get("negative_samples"):
            samples = []
            for s in rev["negative_samples"]:
                title = s.get("title", "")
                content = s.get("content", "")[:100]
                samples.append(f'<div class="comment-bubble"><span class="comment-rating">⭐{s.get("rating", "")}</span> <strong>{title}</strong> {content}</div>')
            neg_samples = "".join(samples)

        rev_sent = rev.get("sentiment", {"positive": 0, "neutral": 0, "negative": 0})
        reviews_summary = _summarize_comment_section(
            "App Store 评论区",
            rev['count'],
            rev_sent.get("positive", 0),
            rev_sent.get("negative", 0),
            rev_sent.get("neutral", 0),
            avg_rating=rev.get('avg_rating'),
            top_keywords=rev.get('negative_keywords'),
        )

        reviews_html = f"""
        <div class="info-card wide">
            <h3>💬 App Store 玩家舆论</h3>
            <div class="metrics-row">
                <div class="metric"><div class="metric-value">{rev['count']}</div><div class="metric-label">样本数</div></div>
                <div class="metric"><div class="metric-value">{rev.get('recent_7d_count', 0)}</div><div class="metric-label">近 7 天</div></div>
                <div class="metric"><div class="metric-value">{rev.get('avg_rating', '—')}</div><div class="metric-label">平均评分</div></div>
            </div>
            <p class="comment-summary">{reviews_summary}</p>
            <div class="rating-distribution">
                {rating_bar}
            </div>
            <p class="negative-count">负面/吐槽提及：<strong>{rev.get('negative_mentions', 0)} 条</strong></p>
            {neg_samples}
        </div>
        """
    else:
        status = rev.get("api_status")
        if status == "empty":
            reviews_html = """
            <div class="info-card wide">
                <h3>💬 App Store 玩家舆论</h3>
                <div class="notice">
                    <p>App Store 评论接口当前未返回数据（中国区 RSS 评论接口可能暂时不可用）。</p>
                    <p>建议在 <code>manual_overrides.json</code> 中补充 TapTap 评分、玩家吐槽或社媒舆情。</p>
                </div>
            </div>
            """
        elif status == "error":
            reviews_html = f"""
            <div class="info-card wide">
                <h3>💬 App Store 玩家舆论</h3>
                <div class="error-card"><span>App Store 评论获取失败：{rev.get('api_error', '未知错误')}</span></div>
            </div>
            """
        else:
            reviews_html = """
            <div class="info-card wide">
                <h3>💬 App Store 玩家舆论</h3>
                <p class="empty">暂无评论数据</p>
            </div>
            """

    # Bilibili 舆情
    bilibili_html = ""
    if bilibili and bilibili.get("comment_count"):
        sent = bilibili["sentiment"]
        neg_kw = bilibili.get("negative_keywords", {})
        bilibili_summary = _summarize_comment_section(
            "Bilibili 评论区",
            bilibili['comment_count'],
            sent.get("positive", 0),
            sent.get("negative", 0),
            sent.get("neutral", 0),
            top_keywords=neg_kw,
        )

        top_comments = ""
        if bilibili.get("top_comments"):
            comments = []
            for c in bilibili["top_comments"][:3]:
                content = html.escape(c.get("content", "")[:90])
                like = c.get("like", 0)
                vtitle = html.escape(c.get("video_title", "")[:30]) + ("…" if len(c.get("video_title", "")) > 30 else "")
                vtitle_full = html.escape(c.get("video_title", ""))
                vlink = html.escape(c.get("video_link", "#"), quote=True)
                comments.append(f'<a class="comment-bubble" href="{vlink}" target="_blank" rel="noopener noreferrer" title="{vtitle_full}"><span class="comment-like">👍 {like}</span> {content}<span class="comment-source-line">出自：{vtitle}</span></a>')
            top_comments = "".join(comments)

        videos = bilibili.get("videos", [])
        video_items = []
        for v in videos:
            title = (v.get("title") or "无标题").replace('"', '&quot;')
            author = v.get("author") or "未知作者"
            link = v.get("link") or "#"
            fetched = v.get("comments_fetched", 0)
            video_items.append(f"""
            <a href="{link}" target="_blank" class="video-item" title="{title}">
                <div class="video-title">{title}</div>
                <div class="video-author">@{author} · 已采 {fetched} 条</div>
            </a>
            """)
        videos_html = ""
        if video_items:
            videos_html = f"""
            <details class='video-details'>
                <summary>查看 {len(videos)} 个采样视频</summary>
                <div class='video-list'>{"".join(video_items)}</div>
            </details>
            """

        bilibili_html = f"""
        <div class="info-card wide">
            <h3>▶️ Bilibili 玩家舆情补充</h3>
            <div class="metrics-row">
                <div class="metric"><div class="metric-value">{len(bilibili['videos'])}</div><div class="metric-label">采样视频</div></div>
                <div class="metric"><div class="metric-value">{bilibili['comment_count']}</div><div class="metric-label">采样评论数</div></div>
            </div>
            {_sentiment_bar_html(sent)}
            <p class="comment-summary">{bilibili_summary}</p>
            {videos_html}
            {top_comments}
        </div>
        """
    else:
        bilibili_html = """
        <div class="info-card wide">
            <h3>▶️ Bilibili 玩家舆情补充</h3>
            <p class="empty">暂无 Bilibili 数据</p>
        </div>
        """

    # 人工补充（有数据才渲染，空则不显示）
    manual_items = []
    if manual:
        if manual.get("taptap_rating"):
            manual_items.append(f'<div class="metric small"><div class="metric-value">{manual["taptap_rating"]}</div><div class="metric-label">TapTap 评分</div></div>')
        if manual.get("taptap_heat"):
            manual_items.append(f'<div class="metric small"><div class="metric-value">{manual["taptap_heat"]}</div><div class="metric-label">TapTap 热度</div></div>')
        if manual.get("marketing"):
            manual_items.append(f'<div class="manual-item"><strong>市场动向：</strong>{manual["marketing"]}</div>')
        if manual.get("events"):
            manual_items.append(f'<div class="manual-item"><strong>重点活动：</strong>{manual["events"]}</div>')
        if manual.get("notes"):
            manual_items.append(f'<div class="manual-item"><strong>备注：</strong>{manual["notes"]}</div>')
    manual_body = "".join(manual_items)

    # 舆情明显异动时给启示框加红色警示（负面提及 ≥ 50 视为明显异动）
    neg_count = _product_negative_count(item)
    insight_class = "competitor-insight alert" if neg_count >= 50 else "competitor-insight"

    insight = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _per_product_insight(item))
    overview_html = f"""
    <div class="overview-grid">
        {_overview_version_card(store)}
        {_overview_rank_card(rank)}
        {_overview_appstore_card(rev)}
        {_overview_bilibili_card(bilibili)}
    </div>
    """

    release_date = store.get('release_date', '—')
    return f"""
    <section class="competitor" id="{name}">
        <div class="competitor-header">
            <div class="competitor-rank">{idx}</div>
            <div class="competitor-title">
                <h2>{name}</h2>
                <div class="subtitle">上次更新：{release_date}</div>
            </div>
        </div>

        <div class="{insight_class}">
            <span class="insight-icon">💡</span>
            <span class="insight-text">{insight}</span>
        </div>

        {overview_html}

        {trend_html}

        <details class="competitor-details">
            <summary class="expand-btn">
                <span class="expand-closed">展开详情 ▼</span>
                <span class="expand-open">收起 ▲</span>
            </summary>
            <div class="competitor-detail-body">
                {_detail_version_section(store)}
                {_detail_rank_section(rank_cards)}
                {_detail_appstore_section(rev, store)}
                {_detail_bilibili_section(bilibili)}
                {_detail_manual_section(manual_body)}
            </div>
        </details>
    </section>
    """


def _summarize_comment_section(source_label, total, positive, negative, neutral, avg_rating=None, top_keywords=None):
    """生成一段自然语言评论区总结。"""
    if total == 0:
        return f"{source_label}：未采集到有效评论。"
    parts = [f"{source_label}共采集 {total} 条样本"]
    if avg_rating is not None:
        parts.append(f"，平均评分 {avg_rating}")
    parts.append(f"。情绪分布：正面 {positive} 条、负面 {negative} 条、中性 {neutral} 条")
    if negative > positive and negative > neutral:
        parts.append("，整体偏负面")
    elif positive > negative and positive > neutral:
        parts.append("，整体偏正面")
    else:
        parts.append("，整体中性")
    if top_keywords:
        kw_items = [f"{k}（{v}次）" for k, v in list(top_keywords.items())[:5]]
        parts.append(f"。负面高频词：{'、'.join(kw_items)}")
    return "".join(parts) + "。"


def _insight_label_html(item):
    """为摘要卡片生成简短标签。"""
    parts = []
    rev = item.get("reviews", {})
    sent = (item.get("bilibili_sentiment") or {}).get("sentiment", {})
    neg = rev.get("negative_mentions", 0) + sent.get("negative", 0)
    if neg >= 3:
        parts.append(f'<span class="pill warning">负面 {neg}</span>')
    else:
        parts.append('<span class="pill ok">舆情平稳</span>')
    version = item.get("app_store", {}).get("version", "")
    if version:
        parts.append(f'<span class="pill info">v{version}</span>')
    return " ".join(parts)


def generate_briefing_html(data, output_dir="edge-extension", changes=None, prev_date=None):
    """生成供 Edge 扩展读取的 HTML 简报。"""
    import re

    date_str = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    title = f"三国杀竞品日报｜{date_str}"

    def _md_bold(text):
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    history = load_history()

    competitors_html = ""
    for idx, item in enumerate(data["competitors"], start=1):
        competitors_html += _render_competitor_html(item, idx, history=history)

    highlights = _generate_highlights(data, changes=changes, prev_date=prev_date)
    highlight_items = "".join(
        f'<div class="highlight-item highlight-{h["level"]}"><span class="highlight-dot"></span><span class="highlight-text">{_md_bold(h["text"])}</span></div>'
        for h in highlights
    )
    highlights_html = f"""
    <div class="highlights-bar">
        <div class="highlights-title">今日重点关注</div>
        <div class="highlights-list">
            {highlight_items}
        </div>
    </div>
    """

    sampling_note_html = _sampling_note_html()

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #f6f7f9;
            --surface: #ffffff;
            --surface-2: #f8f9fb;
            --surface-3: #f2f4f7;
            --text: #111827;
            --text-secondary: #4b5563;
            --muted: #6b7280;
            --accent: #1e5ad8;
            --accent-light: #eef4ff;
            --border: #e5e7eb;
            --hot: #ef4444;
            --hot-bg: #fef2f2;
            --success: #10b981;
            --warning: #f59e0b;
            --info: #3b82f6;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 22px;
            --shadow-card: 0 1px 2px rgba(0,0,0,0.04), 0 10px 30px rgba(0,0,0,0.06);
            --shadow-hover: 0 4px 12px rgba(0,0,0,0.08);
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0f1115;
                --surface: #1a1d23;
                --surface-2: #20242c;
                --surface-3: #252a33;
                --text: #f3f4f6;
                --text-secondary: #d1d5db;
                --muted: #9ca3af;
                --accent: #4b8df8;
                --accent-light: #1e293b;
                --border: #2d3139;
                --hot-bg: #3a1c1c;
            }}
            body {{ background: var(--bg); color: var(--text); }}
            .overview-card, .rank-card, .metric, .info-card,
            .update-details, .video-details, .comment-bubble {{
                background: var(--surface);
                border-color: var(--border);
            }}
            .competitor-header {{
                background: color-mix(in srgb, var(--surface) 96%, transparent);
                border-bottom-color: var(--border);
            }}
            .trend-current {{ background: var(--surface); border-color: var(--border); }}
            code {{ background: var(--surface-2); }}
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 1120px;
            margin: 0 auto;
            padding: 24px 28px 40px;
        }}

        /* Header */
        header {{
            background: var(--surface);
            border-radius: var(--radius-lg);
            padding: 20px 24px;
            box-shadow: var(--shadow-card);
            margin-bottom: 20px;
        }}
        header .date {{
            font-size: 1.75rem;
            color: var(--text);
            font-weight: 800;
            margin-bottom: 4px;
        }}
        header .meta {{
            color: var(--muted);
            font-size: 0.85rem;
            line-height: 1.5;
        }}

        /* Highlights */
        .highlights-bar {{
            background: var(--surface);
            border-radius: var(--radius-lg);
            padding: 18px 20px;
            box-shadow: var(--shadow-card);
            margin-bottom: 20px;
        }}
        .highlights-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 12px;
        }}
        .highlights-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .highlight-item {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px 14px;
            border-radius: var(--radius-md);
            background: var(--surface-2);
            border-left: 4px solid var(--border);
        }}
        .highlight-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
            flex-shrink: 0;
            margin-top: 6px;
            opacity: 0.7;
        }}
        .highlight-text {{
            font-size: 0.9rem;
            line-height: 1.55;
            color: var(--text-secondary);
        }}
        .highlight-text strong {{ color: var(--text); }}
        .highlight-danger {{ background: #fee2e2; border-left-color: #ef4444; }}
        .highlight-warning {{ background: #fef3c7; border-left-color: #f59e0b; }}
        .highlight-info {{ background: #dbeafe; border-left-color: #3b82f6; }}
        .highlight-ok {{ background: #d1fae5; border-left-color: #10b981; }}
        .highlight-danger .highlight-dot {{ color: #ef4444; }}
        .highlight-warning .highlight-dot {{ color: #f59e0b; }}
        .highlight-info .highlight-dot {{ color: #3b82f6; }}
        .highlight-ok .highlight-dot {{ color: #10b981; }}

        /* Section titles */
        .section-title {{
            font-size: 1.25rem;
            font-weight: 700;
            margin: 32px 0 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* Competitor insight */
        .competitor-insight {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            background: var(--accent-light);
            border: 1px solid color-mix(in srgb, var(--accent) 22%, transparent);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            margin: 12px 0;
            color: var(--accent);
            font-size: 0.9rem;
            line-height: 1.55;
        }}
        .competitor-insight.alert {{
            background: var(--hot-bg);
            border-color: color-mix(in srgb, var(--hot) 22%, transparent);
            color: var(--hot);
        }}
        .insight-icon {{
            flex-shrink: 0;
            font-size: 1.1rem;
        }}
        .insight-text strong {{
            font-weight: 700;
        }}

        /* Competitor */
        .competitor {{
            background: var(--surface);
            border-radius: var(--radius-xl);
            padding: 24px;
            margin: 20px 0;
            box-shadow: var(--shadow-card);
            border: 1px solid var(--border);
            transition: box-shadow 0.2s ease;
        }}
        .competitor:hover {{
            box-shadow: var(--shadow-hover);
        }}
        .competitor-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            background: color-mix(in srgb, var(--surface) 96%, transparent);
            backdrop-filter: blur(8px);
            z-index: 20;
            border-radius: var(--radius-xl) var(--radius-xl) 0 0;
            margin: -24px -24px 0;
            padding: 20px 24px 14px;
        }}

        /* Overview grid */
        .overview-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 16px 0 4px;
        }}
        .overview-card {{
            min-width: 0;
            min-height: 130px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 18px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
        }}
        .overview-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-hover);
            border-color: var(--accent);
        }}
        .overview-header {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.82rem;
            color: var(--muted);
            font-weight: 600;
        }}
        .overview-icon {{
            font-size: 1.05rem;
        }}
        .overview-value {{
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.2;
            margin: 8px 0;
        }}
        .overview-summary {{
            font-size: 0.8rem;
            color: var(--muted);
            line-height: 1.45;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .overview-mini-sentiment {{
            margin: 4px 0;
        }}
        .mini-sentiment-bar {{
            display: flex;
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
            background: var(--surface-3);
            margin-bottom: 6px;
        }}
        .mini-segment {{
            height: 100%;
        }}
        .mini-positive {{ background: var(--success); }}
        .mini-neutral {{ background: #9ca3af; }}
        .mini-negative {{ background: var(--hot); }}
        .mini-sentiment-label {{
            font-size: 0.72rem;
            color: var(--muted);
            text-align: center;
        }}

        /* Expand details */
        .competitor-details {{
            display: flex;
            flex-direction: column;
            margin-top: 14px;
        }}
        .expand-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            align-self: center;
            order: 2;
            width: auto;
            padding: 10px 18px;
            margin-top: 14px;
            background: var(--accent-light);
            color: var(--accent);
            border-radius: 999px;
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            list-style: none;
            transition: background 0.15s, transform 0.1s;
        }}
        .expand-btn::-webkit-details-marker {{
            display: none;
        }}
        .expand-btn:hover {{
            background: #dbeafe;
        }}
        .expand-btn:active {{
            transform: translateY(1px);
        }}
        .expand-open {{ display: none; }}
        .competitor-details[open] .expand-closed {{ display: none; }}
        .competitor-details[open] .expand-open {{ display: inline; }}
        .competitor-detail-body {{
            display: flex;
            flex-direction: column;
            order: 1;
            gap: 14px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }}

        /* Detail section */
        .detail-section {{
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 20px;
        }}
        .detail-section h3 {{
            margin: 0 0 12px;
            font-size: 0.98rem;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .sub-section-title {{
            font-size: 0.88rem;
            color: var(--text);
            margin: 14px 0 8px;
            font-weight: 700;
        }}
        .detail-row {{
            display: flex;
            gap: 16px;
            align-items: flex-start;
        }}
        .detail-col-left {{
            flex: 0 0 260px;
            min-width: 0;
        }}
        .detail-col-right {{
            flex: 1 1 auto;
            min-width: 0;
        }}
        .metrics-row {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}
        .metrics-row.compact {{
            flex-wrap: nowrap;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .metrics-row.compact .metric {{
            flex: 1 1 auto;
            min-width: 0;
            padding: 8px 10px;
        }}
        .metrics-row.compact .metric-value {{
            font-size: 1.2rem;
        }}
        .metric {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 8px 12px;
            text-align: center;
            min-width: 70px;
        }}
        .metric-value {{
            font-size: 1.3rem;
            font-weight: 800;
            color: var(--accent);
            line-height: 1.2;
        }}
        .metric-label {{
            font-size: 0.7rem;
            color: var(--muted);
            margin-top: 2px;
        }}
        .store-link {{
            display: inline-block;
            margin-top: 2px;
            color: var(--accent);
            font-size: 0.82rem;
            font-weight: 600;
            text-decoration: none;
        }}
        .store-link:hover {{
            text-decoration: underline;
        }}
        .keywords-wrap {{
            margin: 8px 0 10px;
            line-height: 1.6;
        }}
        .keyword-chip {{
            display: inline-flex;
            align-items: center;
            gap: 3px;
            background: #fff1f0;
            color: #c0392b;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.78rem;
            margin: 2px 4px 2px 0;
        }}
        .keyword-chip small {{
            color: #c0392b;
            font-weight: 700;
            opacity: 0.85;
        }}
        .competitor-rank {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, #4b8df8, #1e5ad8);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            font-weight: 700;
            flex-shrink: 0;
        }}
        .competitor-title h2 {{
            margin: 0;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
        }}
        .competitor-title .subtitle {{
            color: var(--muted);
            font-size: 0.85rem;
            font-weight: 400;
        }}

        /* Info grid */
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
        }}
        .info-card {{
            background: var(--surface-2);
            border-radius: var(--radius-md);
            padding: 18px;
            border: 1px solid var(--border);
        }}
        .info-card.wide {{
            grid-column: 1 / -1;
        }}
        .info-card h3 {{
            margin: 0 0 14px;
            font-size: 0.95rem;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .empty {{
            color: var(--muted);
            font-size: 0.9rem;
            margin: 8px 0;
        }}

        /* Version */
        .version-line {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 6px;
        }}
        .version-badge {{
            background: var(--accent);
            color: white;
            padding: 3px 10px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.9rem;
        }}
        .date-label {{
            color: var(--muted);
            font-size: 0.85rem;
        }}
        .seller {{
            color: var(--muted);
            font-size: 0.8rem;
            margin: 2px 0 8px;
        }}
        .update-list {{
            padding-left: 16px;
            margin: 6px 0 0;
            color: var(--text-secondary);
            font-size: 0.88rem;
        }}
        .update-list li {{
            margin: 4px 0;
        }}
        .update-details {{
            margin-top: 8px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
        }}
        .update-details summary {{
            color: var(--accent);
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }}
        .update-details summary:hover {{
            filter: brightness(0.9);
        }}
        .update-details[open] summary {{
            margin-bottom: 8px;
        }}
        .update-details .update-list {{
            margin-top: 0;
        }}

        /* Rank cards */
        .rank-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }}
        .rank-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px;
            text-align: center;
            transition: border-color 0.15s, box-shadow 0.15s;
        }}
        .rank-card:hover {{
            border-color: var(--accent);
            box-shadow: var(--shadow-hover);
        }}
        .rank-title {{
            font-size: 0.78rem;
            color: var(--muted);
            margin-bottom: 6px;
        }}
        .rank-number {{
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.2;
        }}
        .rank-number.hot-number {{
            color: var(--hot);
        }}
        .rank-tag {{
            display: inline-block;
            margin-top: 6px;
            font-size: 0.7rem;
            padding: 2px 8px;
            border-radius: 999px;
            background: var(--surface-3);
            color: var(--muted);
        }}
        .rank-tag.hot {{
            background: var(--hot);
            color: white;
            font-weight: 700;
        }}
        .rank-missing .rank-number {{
            color: var(--muted);
        }}

        /* Rating distribution */
        .rating-distribution {{
            max-width: 320px;
            margin-bottom: 10px;
        }}
        .rating-row {{
            display: grid;
            grid-template-columns: 80px 1fr 36px;
            align-items: center;
            gap: 8px;
            margin: 6px 0;
            font-size: 0.85rem;
        }}
        .star-label {{ text-align: right; color: var(--warning); }}
        .rating-track {{
            background: var(--surface-3);
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
        }}
        .rating-fill {{
            background: linear-gradient(90deg, #fbbf24, var(--warning));
            height: 100%;
            border-radius: 999px;
            min-width: 2px;
        }}
        .count-label {{
            color: var(--muted);
            font-size: 0.8rem;
        }}
        .negative-count {{
            color: var(--hot);
            background: var(--hot-bg);
            padding: 8px 12px;
            border-radius: 8px;
            display: inline-block;
            font-size: 0.9rem;
        }}

        /* Sentiment bar */
        .sentiment-bar-wrap {{
            margin: 6px 0 10px;
        }}
        .sentiment-bar {{
            display: flex;
            height: 12px;
            border-radius: 999px;
            overflow: hidden;
            background: var(--surface-3);
        }}
        .sentiment-segment {{
            height: 100%;
            transition: width 0.4s ease;
        }}
        .sentiment-positive {{ background: var(--success); }}
        .sentiment-neutral {{ background: #9ca3af; }}
        .sentiment-negative {{ background: var(--hot); }}
        .sentiment-legend {{
            display: flex;
            gap: 16px;
            margin-top: 8px;
            font-size: 0.8rem;
            color: var(--muted);
            flex-wrap: wrap;
        }}
        .dot {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 4px;
        }}
        .dot-positive {{ background: var(--success); }}
        .dot-neutral {{ background: #9ca3af; }}
        .dot-negative {{ background: var(--hot); }}

        /* Comments */
        .comment-bubble {{
            display: block;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            margin: 6px 0;
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-decoration: none;
            transition: border-color 0.15s, box-shadow 0.15s, transform 0.05s;
        }}
        a.comment-bubble:hover {{
            border-color: var(--accent);
            box-shadow: 0 2px 8px rgba(30, 90, 216, 0.12);
            transform: translateY(-1px);
        }}
        .comment-rating, .comment-like {{
            color: var(--warning);
            font-weight: 700;
            margin-right: 6px;
        }}
        .comment-source-line {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-top: 8px;
            font-size: 0.75rem;
            color: var(--muted);
        }}
        .comment-source-line::before {{
            content: "▶ ";
            color: var(--accent);
        }}
        .comment-source {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-top: 8px;
            font-size: 0.75rem;
            color: var(--muted);
            text-decoration: none;
            transition: color 0.15s;
        }}
        .comment-source::before {{
            content: "▶ ";
            color: var(--accent);
        }}
        .comment-source:hover {{
            color: var(--accent);
            text-decoration: underline;
        }}
        .keywords {{
            font-size: 0.85rem;
            color: var(--hot);
            background: var(--hot-bg);
            padding: 6px 10px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 10px;
        }}
        .comment-summary {{
            font-size: 0.88rem;
            line-height: 1.6;
            color: var(--text-secondary);
            background: var(--surface-2);
            border-left: 4px solid var(--accent);
            padding: 8px 12px;
            border-radius: 0 8px 8px 0;
            margin: 8px 0 10px;
        }}
        .video-details {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 10px 14px;
            margin: 8px 0 10px;
        }}
        .video-details summary {{
            color: var(--accent);
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }}
        .video-details summary:hover {{
            filter: brightness(0.9);
        }}
        .video-details[open] summary {{
            margin-bottom: 10px;
        }}
        .video-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
            margin: 12px 0 16px;
        }}
        .video-item {{
            display: block;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 10px 12px;
            text-decoration: none;
            color: inherit;
            transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
        }}
        .video-item:hover {{
            border-color: var(--accent);
            box-shadow: 0 2px 8px rgba(30, 90, 216, 0.12);
            transform: translateY(-1px);
        }}
        .video-title {{
            font-size: 0.88rem;
            color: var(--text);
            line-height: 1.45;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            margin-bottom: 6px;
        }}
        .video-author {{
            font-size: 0.72rem;
            color: var(--muted);
        }}
        .video-author::before {{
            content: "▶ ";
            color: var(--accent);
        }}

        /* Manual items */
        .manual-item {{
            margin: 6px 0;
            font-size: 0.88rem;
            color: var(--text-secondary);
        }}
        .manual-item strong {{
            color: var(--text);
        }}

        /* Error / notice */
        .error-card {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: var(--hot-bg);
            color: var(--hot);
            padding: 14px 16px;
            border-radius: 10px;
            font-size: 0.92rem;
        }}
        .error-icon {{
            font-size: 1.3rem;
        }}
        .notice {{
            background: var(--accent-light);
            border-left: 4px solid var(--accent);
            padding: 14px 16px;
            border-radius: 8px;
            color: var(--accent);
            font-size: 0.9rem;
        }}
        .notice p {{
            margin: 6px 0;
        }}
        code {{
            background: var(--surface-2);
            padding: 1px 5px;
            border-radius: 4px;
            font-family: Consolas, Monaco, monospace;
            font-size: 0.9em;
        }}

        /* Footer */
        footer {{
            text-align: center;
            color: var(--muted);
            font-size: 0.85rem;
            margin-top: 44px;
            padding-bottom: 20px;
        }}

        /* Trend */
        .trend-section {{ margin-top: 8px; }}
        .trend-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            margin-top: 10px;
        }}
        .trend-chart {{
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px;
        }}
        .trend-title {{
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--muted);
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }}
        .trend-title-text {{
            display: flex;
            align-items: center;
            gap: 4px;
            min-width: 0;
            white-space: nowrap;
        }}
        .trend-current {{
            font-size: 0.75rem;
            color: var(--text);
            background: var(--surface);
            padding: 2px 6px;
            border-radius: 6px;
            border: 1px solid var(--border);
        }}
        .trend-chart {{ position: relative; }}
        .dot-hit {{ cursor: pointer; pointer-events: all; }}
        .i-help {{
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            align-self: center;
            width: 16px;
            height: 16px;
            flex: 0 0 auto;
            border-radius: 50%;
            background: var(--surface-3);
            color: var(--muted);
            cursor: help;
            transition: background 0.15s, color 0.15s;
        }}
        .i-help svg {{
            display: block;
            pointer-events: none;
        }}
        .i-help:hover {{
            background: var(--accent);
            color: #fff;
        }}
        .i-help .i-tip {{
            display: none;
            position: absolute;
            left: 0;
            top: calc(100% + 6px);
            z-index: 100;
            width: 280px;
            padding: 10px 12px;
            background: #111827;
            color: #e5e7eb;
            font-size: 12px;
            font-weight: 400;
            line-height: 1.6;
            text-align: left;
            border-radius: 8px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, .25);
            white-space: normal;
        }}
        .i-help:hover .i-tip,
        .i-help:focus .i-tip {{ display: block; }}

        /* Sampling note */
        .sampling-note {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 16px 18px;
            margin: 16px 0 4px;
            font-size: 0.85rem;
            color: var(--muted);
            line-height: 1.6;
            box-shadow: var(--shadow-card);
        }}
        .sampling-note summary {{
            font-weight: 700;
            color: var(--text);
            cursor: pointer;
            outline: none;
        }}
        .sampling-note ul {{
            margin: 10px 0 0;
            padding-left: 18px;
        }}
        .sampling-note li {{
            margin-bottom: 6px;
        }}
        .sampling-note code {{
            background: var(--surface-2);
            padding: 1px 4px;
            border-radius: 4px;
            font-family: Consolas, Monaco, monospace;
        }}

        /* Responsive */
        @media (max-width: 980px) {{
            .overview-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .detail-row {{ flex-direction: column; gap: 16px; }}
            .detail-col-left, .detail-col-right {{ flex: 1 1 auto; width: 100%; }}
            .rank-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .trend-grid {{ grid-template-columns: 1fr; }}
        }}
        @media (max-width: 640px) {{
            .container {{ padding: 16px 18px 32px; }}
            header {{ padding: 16px 18px; }}
            header .date {{ font-size: 1.5rem; }}
            .highlights-bar {{ padding: 14px 16px; }}
            .info-grid {{ grid-template-columns: 1fr; }}
            .competitor {{ padding: 20px; }}
            .competitor-header {{
                margin: -20px -20px 0;
                padding: 18px 20px 14px;
                border-radius: var(--radius-xl) var(--radius-xl) 0 0;
            }}
            .detail-row {{ flex-direction: column; gap: 14px; }}
            .detail-col-left, .detail-col-right {{ width: 100%; }}
            .detail-col-left {{ flex: 1 1 auto; }}
        }}
        @media (max-width: 480px) {{
            .container {{ padding: 12px 14px 24px; }}
            .overview-grid {{
                grid-template-columns: 1fr;
                gap: 12px;
            }}
            .overview-card {{ min-height: 110px; padding: 14px; }}
            .overview-value {{ font-size: 1.3rem; }}
            .rank-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .metrics-row {{ gap: 8px; }}
            .metrics-row.compact {{ flex-wrap: wrap; }}
            .metric {{ padding: 8px 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="date">{date_str}</div>
            <div class="meta">生成时间：{data['generated_at']}（北京时间）</div>
            <div class="meta">来源：App Store · Bilibili · manual_overrides.json</div>
        </header>

        {highlights_html}

        {sampling_note_html}

        {competitors_html}

        <footer>
            本简报由脚本自动生成，仅供参考。
        </footer>
    </div>
    <script>
    // 趋势图悬停提示
    (function () {{
        function onload() {{
            var tip = document.createElement('div');
            tip.id = 'chart-tip';
            tip.style.cssText = 'position:fixed;display:none;z-index:99999;background:#111827;color:#fff;padding:5px 9px;border-radius:6px;font-size:12px;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,.25);white-space:nowrap;';
            document.body.appendChild(tip);
            document.querySelectorAll('.dot-hit').forEach(function (d) {{
                d.addEventListener('mouseenter', function () {{
                    tip.textContent = d.getAttribute('data-tip');
                    tip.style.display = 'block';
                }});
                d.addEventListener('mousemove', function (e) {{
                    tip.style.left = (e.clientX + 14) + 'px';
                    tip.style.top = (e.clientY + 14) + 'px';
                }});
                d.addEventListener('mouseleave', function () {{
                    tip.style.display = 'none';
                }});
            }});
        }}
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', onload);
        }} else {{
            onload();
        }}
    }})();
    </script>
</body>
</html>"""

    os.makedirs(output_dir, exist_ok=True)

    # 保存历史副本（每日只保留最后一次更新）
    history_dir = os.path.join(output_dir, "history")
    os.makedirs(history_dir, exist_ok=True)
    history_path = os.path.join(history_dir, f"briefing_{date_str}.html")
    with open(history_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 更新历史索引，只保留最近 30 天
    history_dates = _update_history_index(history_dir)

    # 写入带标签选项卡的浏览外壳
    viewer_html = _build_viewer_html(history_dates)
    path = os.path.join(output_dir, "briefing.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(viewer_html)
    return path


def _update_history_index(history_dir, keep_days=30):
    """扫描历史简报文件，生成索引并清理超过保留天数的内容。

    会合并已有 index.json 中的日期，避免云端运行时目录为空导致历史日期丢失。
    """
    files = glob.glob(os.path.join(history_dir, "briefing_*.html"))
    dates = []
    for f in files:
        name = os.path.basename(f)
        m = re.match(r"briefing_(\d{4}-\d{2}-\d{2})\.html", name)
        if m:
            dates.append(m.group(1))

    # 合并已有 index.json 中的日期，防止云端 history 目录不完整时丢历史
    index_path = os.path.join(history_dir, "index.json")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, list):
            dates.extend(existing)
    except (OSError, json.JSONDecodeError):
        pass

    dates = sorted(set(dates), reverse=True)

    # 删除超出保留期限的文件（只删本地有对应文件的）
    for d in dates[keep_days:]:
        try:
            os.remove(os.path.join(history_dir, f"briefing_{d}.html"))
        except OSError:
            pass
    dates = dates[:keep_days]

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False, indent=2)
    return dates


def _build_viewer_html(history_dates):
    """生成左侧日报切换 + 右侧游戏索引的浏览外壳。"""
    dates_json = json.dumps(history_dates, ensure_ascii=False)
    default_src = f"history/briefing_{history_dates[0]}.html" if history_dates else "about:blank"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>一将成名竞品日报</title>
    <style>
        :root {{
            --bg: #f6f7f9;
            --surface: #ffffff;
            --surface-2: #f8f9fb;
            --surface-3: #f2f4f7;
            --text: #111827;
            --text-secondary: #4b5563;
            --muted: #6b7280;
            --accent: #1e5ad8;
            --accent-light: #eef4ff;
            --border: #e5e7eb;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 22px;
            --shadow-card: 0 1px 2px rgba(0,0,0,0.04), 0 10px 30px rgba(0,0,0,0.06);
            --shadow-hover: 0 4px 12px rgba(0,0,0,0.08);
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0f1115;
                --surface: #1a1d23;
                --surface-2: #20242c;
                --surface-3: #252a33;
                --text: #f3f4f6;
                --text-secondary: #d1d5db;
                --muted: #9ca3af;
                --accent: #4b8df8;
                --accent-light: #1e293b;
                --border: #2d3139;
            }}
        }}
        * {{ box-sizing: border-box; }}
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg);
            color: var(--text);
        }}
        .app-layout {{
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        .left-nav {{
            width: 200px;
            flex-shrink: 0;
            background: var(--surface);
            border-right: 1px solid var(--border);
            padding: 18px 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .brand {{
            font-size: 1rem;
            font-weight: 800;
            color: var(--accent);
            line-height: 1.4;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .brand-icon {{
            font-size: 1.2rem;
            flex-shrink: 0;
        }}
        .nav-btn {{
            width: 100%;
            text-align: left;
            padding: 10px 12px;
            border: none;
            border-radius: var(--radius-sm);
            background: transparent;
            color: var(--muted);
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s, color 0.15s;
            display: flex;
            align-items: center;
            gap: 8px;
            position: relative;
        }}
        .nav-btn .nav-icon {{ font-size: 1rem; }}
        .nav-btn:hover {{ background: var(--accent-light); }}
        .nav-btn.active {{
            background: var(--accent-light);
            color: var(--accent);
        }}
        .nav-btn.active::before {{
            content: "";
            position: absolute;
            left: -16px;
            top: 50%;
            transform: translateY(-50%);
            width: 3px;
            height: 20px;
            background: var(--accent);
            border-radius: 0 2px 2px 0;
        }}
        .history-select {{
            display: none;
            width: 100%;
            padding: 8px 10px;
            margin-top: 6px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 0.85rem;
            background: var(--surface);
            color: var(--text);
            cursor: pointer;
        }}
        .main-area {{
            flex: 1;
            display: flex;
            overflow: hidden;
            padding: 16px;
        }}
        .viewer-wrap {{
            flex: 1;
            padding: 0;
            overflow: auto;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: none;
            border-radius: var(--radius-lg);
            background: var(--surface);
            box-shadow: var(--shadow-card);
        }}
        .right-index {{
            width: 180px;
            flex-shrink: 0;
            background: var(--surface);
            border-left: 1px solid var(--border);
            padding: 18px 16px;
            overflow-y: auto;
        }}
        .index-title {{
            font-size: 0.72rem;
            font-weight: 800;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 12px;
        }}
        .index-btn {{
            display: block;
            width: 100%;
            text-align: left;
            padding: 10px 12px;
            margin-bottom: 8px;
            border: none;
            border-radius: var(--radius-sm);
            background: var(--surface-2);
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.15s, color 0.15s;
        }}
        .index-btn:hover {{
            background: var(--accent-light);
            color: var(--accent);
        }}
        .empty-state {{
            display: none;
            padding: 64px 24px;
            text-align: center;
            color: var(--muted);
            background: var(--surface);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-card);
        }}
        .empty-state h3 {{
            margin: 0 0 8px;
            color: var(--text);
            font-size: 1rem;
        }}
        .empty-state p {{
            margin: 0;
            font-size: 0.85rem;
            line-height: 1.5;
        }}
        @media (max-width: 900px) {{
            .right-index {{ display: none; }}
        }}
        @media (max-width: 640px) {{
            .app-layout {{ flex-direction: column; }}
            .left-nav {{
                width: 100%;
                flex-direction: row;
                flex-wrap: wrap;
                border-right: none;
                border-bottom: 1px solid var(--border);
                padding: 14px;
                gap: 8px;
            }}
            .brand {{ width: 100%; margin-bottom: 4px; font-size: 0.95rem; }}
            .nav-btn {{
                width: auto;
                padding: 8px 12px;
            }}
            .nav-btn.active::before {{ display: none; }}
            .history-select {{ width: auto; min-width: 140px; margin-top: 0; }}
            .main-area {{ height: calc(100vh - 130px); padding: 10px; }}
        }}
        @media (max-width: 480px) {{
            .left-nav {{ padding: 12px; }}
            .brand {{ font-size: 0.9rem; }}
            .main-area {{ height: calc(100vh - 120px); padding: 8px; }}
        }}
    </style>
</head>
<body>
    <div class="app-layout">
        <aside class="left-nav">
            <div class="brand"><span class="brand-icon">📊</span> 一将成名竞品日报</div>
            <button class="nav-btn active" data-mode="today"><span class="nav-icon">📅</span> 每日日报</button>
            <button class="nav-btn" data-mode="history"><span class="nav-icon">📜</span> 历史日报</button>
            <select class="history-select" id="history-select"></select>
        </aside>
        <div class="main-area">
            <div class="viewer-wrap">
                <div class="empty-state" id="empty-state">
                    <h3>暂无日报</h3>
                    <p>请运行项目根目录的 <strong>双击运行.bat</strong><br>生成今日简报后再刷新本页。</p>
                </div>
                <iframe id="viewer" src="{default_src}"></iframe>
            </div>
            <aside class="right-index" id="right-index">
                <div class="index-title">游戏索引</div>
                <div id="index-list"></div>
            </aside>
        </div>
    </div>
    <div id="history-data" data-dates='{dates_json}' style="display:none"></div>
    <script src="viewer.js"></script>
</body>
</html>"""


if __name__ == "__main__":
    import json
    from collector import collect_all

    d = collect_all()
    path, md = generate_briefing(d)
    print(f"已生成 Markdown：{path}")
    html_path = generate_briefing_html(d)
    print(f"已生成 HTML：{html_path}")
