from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return utc_now()
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return utc_now()


@dataclass
class Keyword:
    name: str
    aliases: List[str] = field(default_factory=list)
    category: str = "general"
    weight: float = 1.0
    active: bool = True
    id: Optional[int] = None

    @property
    def terms(self) -> List[str]:
        return [self.name] + [item for item in self.aliases if item]


@dataclass
class SourceItem:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str = ""
    heat: float = 1.0
    raw: Dict[str, str] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return self.url or f"{self.source}:{self.title}".lower()


@dataclass
class Hotspot:
    title: str
    summary: str
    sources: List[str]
    urls: List[str]
    keywords: List[str]
    importance: float
    heat: float
    relevance: float
    credibility: float
    published_at: datetime
    reason: str
    status: str = "normal"
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "sources": self.sources,
            "urls": self.urls,
            "keywords": self.keywords,
            "importance": round(self.importance, 2),
            "heat": round(self.heat, 2),
            "relevance": round(self.relevance, 2),
            "credibility": round(self.credibility, 2),
            "published_at": self.published_at.isoformat(),
            "reason": self.reason,
            "status": self.status,
        }
