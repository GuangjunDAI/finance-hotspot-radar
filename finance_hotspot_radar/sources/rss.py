from __future__ import annotations

import email.utils
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from ..models import Keyword, SourceItem
from .base import SourceAdapter


class RssSource(SourceAdapter):
    def __init__(self, name: str, url: str, user_agent: str = "finance-hotspot-radar/0.1"):
        self.name = name
        self.url = url
        self.user_agent = user_agent

    def fetch(self, keywords: List[Keyword]) -> Iterable[SourceItem]:
        req = urllib.request.Request(self.url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        channel_items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in channel_items[:80]:
            title = _text(entry, "title")
            link = _text(entry, "link") or _atom_link(entry)
            summary = html.unescape(_text(entry, "description") or _text(entry, "summary"))
            published = _parse_date(_text(entry, "pubDate") or _text(entry, "published") or _text(entry, "updated"))
            text = f"{title} {summary}".lower()
            matched = [kw.name for kw in keywords if any(term.lower() in text for term in kw.terms)]
            if not matched and keywords:
                continue
            yield SourceItem(
                source=self.name,
                title=html.unescape(title).strip(),
                url=link.strip(),
                summary=_strip_tags(summary).strip()[:500],
                published_at=published,
                heat=max(1.0, len(matched) * 1.5),
                raw={"matched_keywords": ",".join(matched)},
            )


def google_news_source(query: str, user_agent: str) -> RssSource:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    return RssSource(f"google-news:{query}", url, user_agent)


def _text(entry: ET.Element, tag: str) -> str:
    found = entry.find(tag)
    if found is None:
        found = entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    return found.text if found is not None and found.text else ""


def _atom_link(entry: ET.Element) -> str:
    link = entry.find("{http://www.w3.org/2005/Atom}link")
    return link.attrib.get("href", "") if link is not None else ""


def _parse_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed: Optional[datetime] = None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    if parsed is None:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _strip_tags(value: str) -> str:
    output = []
    inside = False
    for ch in value:
        if ch == "<":
            inside = True
        elif ch == ">":
            inside = False
        elif not inside:
            output.append(ch)
    return "".join(output)
