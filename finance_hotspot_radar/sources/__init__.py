from .base import SourceAdapter, collect_from_sources
from .rss import RssSource
from .social import BilibiliHotSource, WeiboHotSearchSource

__all__ = ["SourceAdapter", "RssSource", "BilibiliHotSource", "WeiboHotSearchSource", "collect_from_sources"]
