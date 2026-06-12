from __future__ import annotations

import hashlib
from typing import List, Optional

from .ai import OpenAICompatibleProvider
from .analyzer import HeuristicAnalyzer
from .config import Settings, default_rss_feeds
from .formatter import digest_text
from .models import Hotspot, Keyword
from .notify import ConsoleNotifier, OneBotNotifier, WebhookNotifier
from .notify.base import Notifier
from .sources import BilibiliHotSource, RssSource, WeiboHotSearchSource, collect_from_sources
from .sources.rss import google_news_source
from .storage import Store


class RadarService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.db_path)
        ai_provider = None
        if settings.ai_api_key:
            ai_provider = OpenAICompatibleProvider(settings.ai_api_key, settings.ai_base_url, settings.ai_model)
        self.analyzer = HeuristicAnalyzer(ai_provider=ai_provider)

    def init_db(self, seed: bool = True) -> None:
        self.store.init()
        if seed:
            self.store.seed_defaults()

    def scan(self, include_social: bool = True, extra_keyword: Optional[str] = None) -> int:
        self.init_db(seed=True)
        keywords = self.store.list_keywords(active=True)
        if extra_keyword:
            keywords = keywords + [Keyword(extra_keyword, [], "adhoc", 1.0, True)]
        sources = self._sources(include_social=include_social, keywords=keywords)
        items = collect_from_sources(sources, keywords)
        clean_items = [item for item in items if not item.source.endswith(":error") and item.title]
        self.store.save_source_items(clean_items)
        hotspots = self.analyzer.analyze(clean_items + self.store.recent_items(hours=24), keywords)
        return self.store.save_hotspots(hotspots)

    def digest(
        self,
        hours: int = 24,
        limit: int = 8,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        min_importance: float = 0.0,
        sort: str = "heat",
    ) -> List[Hotspot]:
        self.init_db(seed=True)
        return self.store.query_hotspots(hours, source, keyword, min_importance, sort, limit)

    def notify_digest(self, hotspots: List[Hotspot], channel: str = "console", title: str = "金融热点雷达") -> bool:
        digest_key = hashlib.sha1("|".join(str(h.id) for h in hotspots if h.id).encode("utf-8")).hexdigest()
        if not self.store.mark_notified(channel, None, digest_key):
            return False
        notifier = self._notifier(channel)
        notifier.send(digest_text(hotspots, title=title))
        return True

    def notify_alerts(self, hotspots: List[Hotspot], channel: str = "console", min_importance: float = 7.0) -> int:
        notifier = self._notifier(channel)
        sent = 0
        for hotspot in hotspots:
            if hotspot.importance < min_importance or hotspot.id is None:
                continue
            if self.store.mark_notified(channel, hotspot.id, "alert"):
                notifier.send(digest_text([hotspot], title="金融突发热点"))
                sent += 1
        return sent

    def _sources(self, include_social: bool, keywords: Optional[List[Keyword]] = None) -> list:
        sources = [RssSource(f"rss:{idx}", url, self.settings.user_agent) for idx, url in enumerate(default_rss_feeds(), start=1)]
        sources.extend(
            [
                google_news_source("金融 OR 股市 OR 央行 OR 美联储 OR 财报", self.settings.user_agent),
                google_news_source("A股 OR 港股 OR 美股 OR 加密 OR 黄金 OR 原油", self.settings.user_agent),
            ]
        )
        for keyword in (keywords or [])[:12]:
            sources.append(google_news_source(keyword.name, self.settings.user_agent))
        if include_social:
            sources.extend([WeiboHotSearchSource(self.settings.user_agent), BilibiliHotSource(self.settings.user_agent)])
        return sources

    def _notifier(self, channel: str) -> Notifier:
        if channel == "webhook":
            if not self.settings.webhook_url:
                raise ValueError("FINANCE_RADAR_WEBHOOK_URL is required for webhook notifications")
            return WebhookNotifier(self.settings.webhook_url, self.settings.webhook_token)
        if channel in ("qq", "qq-onebot"):
            if not self.settings.qq_onebot_url or not self.settings.qq_target_id:
                raise ValueError("FINANCE_RADAR_QQ_ONEBOT_URL and FINANCE_RADAR_QQ_TARGET_ID are required for QQ notifications")
            return OneBotNotifier(
                self.settings.qq_onebot_url,
                self.settings.qq_target_type,
                self.settings.qq_target_id,
                self.settings.qq_access_token,
            )
        return ConsoleNotifier()
