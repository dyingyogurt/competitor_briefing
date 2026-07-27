# -*- coding: utf-8 -*-
"""竞品配置。这里只维护 App Store 的 appId，基本不会变。

注意：本项目负责监控的是「三国杀一将成名」，需要和以下两款产品严格区分：
- 三国杀手游（简称"手杀"、"三国杀"）：App ID 不同，对应移动端的《三国杀》
- 三国杀 Online（简称"OL"）：PC 端产品，无 iOS App Store 版本

因此配置中 bilibili_keyword 必须使用完整产品名，避免抓到手杀 / OL 的内容。
"""

COMPETITORS = [
    {
        "key": "yjc",
        "name": "三国杀：一将成名",
        "display_name": "三国杀一将成名",
        "itunes_id": 1389650592,
        # B 站搜索关键词必须精确到产品全名，防止和手杀 / OL 内容混淆
        "bilibili_keyword": "三国杀一将成名",
        "taptap_url": "",
        "official_news_url": "",
    },
    {
        "key": "mjs",
        "name": "名将杀",
        "display_name": "名将杀",
        "itunes_id": 6746475501,
        "bilibili_keyword": "名将杀",
        "taptap_url": "",
        "official_news_url": "",
    },
    {
        "key": "yxs",
        "name": "英雄杀",
        "display_name": "英雄杀",
        "itunes_id": 483330461,
        "bilibili_keyword": "英雄杀",
        "taptap_url": "",
        "official_news_url": "",
    },
    {
        "key": "bjp",
        "name": "三国：百将牌",
        "display_name": "百将牌",
        "itunes_id": 6741894810,
        "bilibili_keyword": "三国百将牌",
        "taptap_url": "",
        "official_news_url": "",
    },
]

# Apple 公开榜单 RSS，max=100
# 加上了游戏分类（genre=6014），卡牌/三国类更可能进入游戏榜 Top100
CHART_FEEDS = {
    "iOS 总畅销榜": "https://itunes.apple.com/cn/rss/topgrossingapplications/limit=100/json",
    "iOS 总免费榜": "https://itunes.apple.com/cn/rss/topfreeapplications/limit=100/json",
    "iOS 游戏畅销榜": "https://itunes.apple.com/cn/rss/topgrossingapplications/limit=100/genre=6014/json",
    "iOS 游戏免费榜": "https://itunes.apple.com/cn/rss/topfreeapplications/limit=100/genre=6014/json",
}

# 最近评论抓取页数（每页 50 条， pages=2 即 100 条）
REVIEW_PAGES = 2
