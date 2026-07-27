#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把简报推送到自研办公软件。

目前支持两种模式：
1. WEBHOOK_URL：直接 POST JSON {"text": "markdown内容"}
2. 自定义：按贵司 API 修改 payload 结构。

如果你们办公软件是 Lark/飞书/企微/钉钉，可替换对应的模板。"""

import os
import json
import urllib.request
import urllib.error


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _post_json(url, payload, headers=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def push_to_webhook(title, markdown_text, webhook_url=None):
    """推送 Markdown 到通用 webhook。

    默认 payload：
        {
          "title": "三国杀竞品日报｜...",
          "text": "# markdown正文...",
          "markdown": true
        }
    """
    url = webhook_url or os.getenv("COMPETITOR_WEBHOOK_URL", "").strip()
    if not url:
        raise ValueError(
            "未配置 webhook 地址。请设置环境变量 COMPETITOR_WEBHOOK_URL "
            "或调用 push_to_webhook(url=...)"
        )

    token = os.getenv("COMPETITOR_WEBHOOK_TOKEN", "")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "title": title,
        "text": markdown_text,
        "markdown": True,
    }

    try:
        status, body = _post_json(url, payload, headers=headers)
        print(f"推送成功，HTTP {status}，响应：{body[:200]}")
        return {"ok": True, "status": status, "body": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"推送失败：HTTP {e.code}，响应：{body[:500]}")
        return {"ok": False, "status": e.code, "body": body}
    except Exception as e:
        print(f"推送异常：{type(e).__name__}: {e}")
        return {"ok": False, "error": str(e)}


def lark_template(title, markdown_text):
    """飞书/Lark webhook 格式（如贵司用这个，可把 push_to_webhook 里的 payload 替换为此字典）。"""
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": markdown_text[:3000]},
                }
            ],
        },
    }


def wecom_template(title, markdown_text):
    """企业微信 webhook 格式。"""
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n{markdown_text[:4000]}",
        },
    }


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "测试消息"
    push_to_webhook("测试推送", text)
