from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from .models import Hotspot, Keyword, SourceItem


RISK_WORDS = ("传", "网传", "未经证实", "爆料", "rumor", "unconfirmed")
IMPORTANT_WORDS = (
    "央行", "美联储", "降息", "加息", "监管", "制裁", "财报", "暴跌", "暴涨", "破产",
    "并购", "回购", "通胀", "CPI", "PPI", "PMI", "war", "fed", "inflation", "bankruptcy",
)


class HeuristicAnalyzer:
    """Offline analyzer used when no model provider is configured."""

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def expand_keywords(self, keywords: Sequence[Keyword]) -> Dict[str, List[str]]:
        expansions: Dict[str, List[str]] = {}
        for kw in keywords:
            terms = set(kw.terms)
            if kw.category == "macro":
                terms.update(["通胀", "政策", "就业", "利率"])
            if kw.category == "crypto":
                terms.update(["BTC", "ETH", "ETF"])
            expansions[kw.name] = sorted(terms)
        if self.ai_provider:
            try:
                ai_terms = self.ai_provider.expand_keywords(list(keywords))
            except Exception:
                ai_terms = None
            if ai_terms:
                for name, terms in ai_terms.items():
                    expansions[name] = sorted(set(expansions.get(name, []) + terms))
        return expansions

    def analyze(self, items: Iterable[SourceItem], keywords: Sequence[Keyword]) -> List[Hotspot]:
        groups: Dict[str, List[SourceItem]] = defaultdict(list)
        keyword_map = self.expand_keywords(keywords)
        for item in items:
            matched = self._match_keywords(item, keywords, keyword_map)
            if not matched:
                continue
            key = self._cluster_key(item.title, matched)
            item.raw["matched_keywords"] = ",".join(matched)
            groups[key].append(item)

        hotspots: List[Hotspot] = []
        for grouped in groups.values():
            hotspots.append(self._build_hotspot(grouped, keywords))
        hotspots.sort(key=lambda h: (h.importance, h.heat, h.published_at), reverse=True)
        if self.ai_provider:
            try:
                hotspots = self.ai_provider.annotate_hotspots(hotspots)
            except Exception:
                pass
        return hotspots

    def _match_keywords(self, item: SourceItem, keywords: Sequence[Keyword], expanded: Dict[str, List[str]]) -> List[str]:
        text = f"{item.title} {item.summary}".lower()
        matched = []
        for kw in keywords:
            if any(term.lower() in text for term in expanded.get(kw.name, kw.terms)):
                matched.append(kw.name)
        return matched

    def _cluster_key(self, title: str, matched: List[str]) -> str:
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", title.lower())
        strong = [token for token in tokens if len(token) >= 2][:8]
        return "|".join(sorted(set(matched))[:3] + strong[:5])

    def _build_hotspot(self, items: List[SourceItem], keywords: Sequence[Keyword]) -> Hotspot:
        newest = max(items, key=lambda item: item.published_at)
        sources = sorted(set(item.source for item in items if not item.source.endswith(":error")))
        urls = []
        for item in sorted(items, key=lambda item: item.heat, reverse=True):
            if item.url and item.url not in urls:
                urls.append(item.url)
        matched = sorted(set(",".join(item.raw.get("matched_keywords", "").split(",")).split(",")) - {""})
        weight = sum(kw.weight for kw in keywords if kw.name in matched) or 1.0
        source_bonus = min(len(sources), 4) * 0.8
        text = f"{newest.title} {newest.summary}"
        important_bonus = sum(1 for word in IMPORTANT_WORDS if word.lower() in text.lower()) * 0.35
        heat = math.log10(sum(max(item.heat, 1.0) for item in items) + 10)
        importance = min(10.0, weight + source_bonus + important_bonus + heat)
        credibility = min(1.0, 0.45 + len(sources) * 0.18)
        if any(word.lower() in text.lower() for word in RISK_WORDS):
            credibility = min(credibility, 0.55)
        relevance = min(1.0, 0.25 + len(matched) * 0.18 + len(sources) * 0.12)
        status = "risk" if credibility < 0.6 else "normal"
        reason = f"{len(sources)} 个来源，命中关键词：{', '.join(matched) or '未标注'}；重要性={importance:.1f}，可信度={credibility:.2f}"
        return Hotspot(
            title=newest.title,
            summary=newest.summary or newest.title,
            sources=sources,
            urls=urls[:5],
            keywords=matched,
            importance=importance,
            heat=heat,
            relevance=relevance,
            credibility=credibility,
            published_at=_latest_time(items),
            reason=reason,
            status=status,
        )


def _latest_time(items: List[SourceItem]) -> datetime:
    return max(item.published_at for item in items)
