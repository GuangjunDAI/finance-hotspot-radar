from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Iterable, List

from ..models import Keyword, SourceItem
from .base import SourceAdapter


class WeiboHotSearchSource(SourceAdapter):
    name = "weibo-hot-search"
    url = "https://weibo.com/ajax/side/hotSearch"

    def __init__(self, user_agent: str = "finance-hotspot-radar/0.1"):
        self.user_agent = user_agent

    def fetch(self, keywords: List[Keyword]) -> Iterable[SourceItem]:
        data = _get_json(self.url, self.user_agent)
        realtime = data.get("data", {}).get("realtime", [])
        for rank, item in enumerate(realtime[:60], start=1):
            title = item.get("word") or item.get("note") or ""
            if not title:
                continue
            text = title.lower()
            matched = [kw.name for kw in keywords if any(term.lower() in text for term in kw.terms)]
            if not matched and keywords:
                continue
            heat = float(item.get("num") or max(1, 100 - rank))
            yield SourceItem(
                source=self.name,
                title=title,
                url=f"https://s.weibo.com/weibo?q={title}",
                summary=f"微博热搜 rank={rank}",
                published_at=datetime.now(timezone.utc),
                heat=heat,
                raw={"rank": str(rank), "matched_keywords": ",".join(matched)},
            )


class BilibiliHotSource(SourceAdapter):
    name = "bilibili-popular"
    url = "https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1"

    def __init__(self, user_agent: str = "finance-hotspot-radar/0.1"):
        self.user_agent = user_agent

    def fetch(self, keywords: List[Keyword]) -> Iterable[SourceItem]:
        data = _get_json(self.url, self.user_agent)
        items = data.get("data", {}).get("list", [])
        for rank, item in enumerate(items, start=1):
            title = item.get("title", "")
            desc = item.get("desc", "")
            text = f"{title} {desc}".lower()
            matched = [kw.name for kw in keywords if any(term.lower() in text for term in kw.terms)]
            if not matched and keywords:
                continue
            stat = item.get("stat", {})
            heat = float(stat.get("view") or max(1, 100 - rank))
            bvid = item.get("bvid", "")
            yield SourceItem(
                source=self.name,
                title=title,
                url=f"https://www.bilibili.com/video/{bvid}" if bvid else item.get("short_link_v2", ""),
                summary=desc[:500],
                published_at=datetime.now(timezone.utc),
                heat=heat,
                raw={"rank": str(rank), "matched_keywords": ",".join(matched)},
            )


def _get_json(url: str, user_agent: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))
