from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Iterable, List

from ..models import Keyword, SourceItem


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def fetch(self, keywords: List[Keyword]) -> Iterable[SourceItem]:
        raise NotImplementedError


def collect_from_sources(sources: List[SourceAdapter], keywords: List[Keyword], delay_seconds: float = 0.3) -> List[SourceItem]:
    items: List[SourceItem] = []
    for source in sources:
        try:
            items.extend(list(source.fetch(keywords)))
        except Exception as exc:
            items.append(
                SourceItem(
                    source=f"{source.name}:error",
                    title=f"source fetch failed: {source.name}",
                    url="",
                    summary=str(exc),
                    published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                    heat=0,
                )
            )
        time.sleep(delay_seconds)
    return items
