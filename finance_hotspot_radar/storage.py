from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from .config import DEFAULT_KEYWORDS
from .models import Hotspot, Keyword, SourceItem, iso_now, parse_dt, utc_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    aliases TEXT NOT NULL DEFAULT '[]',
    category TEXT NOT NULL DEFAULT 'general',
    weight REAL NOT NULL DEFAULT 1.0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL,
    heat REAL NOT NULL DEFAULT 1.0,
    raw TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotspots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    sources TEXT NOT NULL,
    urls TEXT NOT NULL,
    keywords TEXT NOT NULL,
    importance REAL NOT NULL,
    heat REAL NOT NULL,
    relevance REAL NOT NULL,
    credibility REAL NOT NULL,
    published_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'normal',
    signature TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    hotspot_id INTEGER,
    digest_key TEXT,
    sent_at TEXT NOT NULL,
    UNIQUE(channel, hotspot_id, digest_key)
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def init(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def seed_defaults(self) -> None:
        for name, aliases, category, weight in DEFAULT_KEYWORDS:
            self.add_keyword(name, aliases.split(","), category, weight, active=True, ignore_existing=True)

    def add_keyword(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        category: str = "general",
        weight: float = 1.0,
        active: bool = True,
        ignore_existing: bool = False,
    ) -> None:
        now = iso_now()
        sql = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        self.conn.execute(
            f"{sql} INTO keywords (name, aliases, category, weight, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, json.dumps(aliases or [], ensure_ascii=False), category, weight, int(active), now, now),
        )
        self.conn.commit()

    def set_keyword_active(self, name: str, active: bool) -> int:
        cur = self.conn.execute(
            "UPDATE keywords SET active = ?, updated_at = ? WHERE name = ?",
            (int(active), iso_now(), name),
        )
        self.conn.commit()
        return cur.rowcount

    def list_keywords(self, active: Optional[bool] = None) -> List[Keyword]:
        sql = "SELECT * FROM keywords"
        params = []
        if active is not None:
            sql += " WHERE active = ?"
            params.append(int(active))
        sql += " ORDER BY category, name"
        return [self._keyword_from_row(row) for row in self.conn.execute(sql, params)]

    def save_source_items(self, items: Iterable[SourceItem]) -> int:
        inserted = 0
        for item in items:
            cur = self.conn.execute(
                """
                INSERT OR IGNORE INTO source_items
                (fingerprint, source, title, url, summary, published_at, heat, raw, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.fingerprint,
                    item.source,
                    item.title,
                    item.url,
                    item.summary,
                    item.published_at.isoformat(),
                    item.heat,
                    json.dumps(item.raw, ensure_ascii=False),
                    iso_now(),
                ),
            )
            inserted += cur.rowcount
        self.conn.commit()
        return inserted

    def recent_items(self, hours: int = 24, source: Optional[str] = None) -> List[SourceItem]:
        cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
        sql = "SELECT * FROM source_items WHERE published_at >= ?"
        params = [cutoff]
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY published_at DESC"
        return [self._item_from_row(row) for row in self.conn.execute(sql, params)]

    def save_hotspots(self, hotspots: Iterable[Hotspot]) -> int:
        inserted = 0
        for hotspot in hotspots:
            signature = self.hotspot_signature(hotspot)
            cur = self.conn.execute(
                """
                INSERT OR IGNORE INTO hotspots
                (title, summary, sources, urls, keywords, importance, heat, relevance, credibility,
                 published_at, reason, status, signature, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hotspot.title,
                    hotspot.summary,
                    json.dumps(hotspot.sources, ensure_ascii=False),
                    json.dumps(hotspot.urls, ensure_ascii=False),
                    json.dumps(hotspot.keywords, ensure_ascii=False),
                    hotspot.importance,
                    hotspot.heat,
                    hotspot.relevance,
                    hotspot.credibility,
                    hotspot.published_at.isoformat(),
                    hotspot.reason,
                    hotspot.status,
                    signature,
                    iso_now(),
                ),
            )
            inserted += cur.rowcount
        self.conn.commit()
        return inserted

    def query_hotspots(
        self,
        hours: int = 24,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        min_importance: float = 0.0,
        sort: str = "heat",
        limit: int = 20,
    ) -> List[Hotspot]:
        cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
        sql = "SELECT * FROM hotspots WHERE published_at >= ? AND importance >= ?"
        params: List[object] = [cutoff, min_importance]
        if source:
            sql += " AND sources LIKE ?"
            params.append(f"%{source}%")
        if keyword:
            sql += " AND keywords LIKE ?"
            params.append(f"%{keyword}%")
        order_col = {"heat": "heat", "relevance": "relevance", "time": "published_at", "importance": "importance"}.get(sort, "heat")
        sql += f" ORDER BY {order_col} DESC LIMIT ?"
        params.append(limit)
        return [self._hotspot_from_row(row) for row in self.conn.execute(sql, params)]

    def mark_notified(self, channel: str, hotspot_id: Optional[int], digest_key: Optional[str]) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO notifications (channel, hotspot_id, digest_key, sent_at) VALUES (?, ?, ?, ?)",
            (channel, hotspot_id, digest_key, iso_now()),
        )
        self.conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def hotspot_signature(hotspot: Hotspot) -> str:
        words = sorted(set(hotspot.keywords))
        url = hotspot.urls[0] if hotspot.urls else hotspot.title
        return f"{'|'.join(words)}::{url}".lower()

    @staticmethod
    def _keyword_from_row(row: sqlite3.Row) -> Keyword:
        return Keyword(
            id=row["id"],
            name=row["name"],
            aliases=json.loads(row["aliases"] or "[]"),
            category=row["category"],
            weight=row["weight"],
            active=bool(row["active"]),
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> SourceItem:
        return SourceItem(
            source=row["source"],
            title=row["title"],
            url=row["url"],
            summary=row["summary"],
            published_at=parse_dt(row["published_at"]),
            heat=row["heat"],
            raw=json.loads(row["raw"] or "{}"),
        )

    @staticmethod
    def _hotspot_from_row(row: sqlite3.Row) -> Hotspot:
        return Hotspot(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            sources=json.loads(row["sources"] or "[]"),
            urls=json.loads(row["urls"] or "[]"),
            keywords=json.loads(row["keywords"] or "[]"),
            importance=row["importance"],
            heat=row["heat"],
            relevance=row["relevance"],
            credibility=row["credibility"],
            published_at=parse_dt(row["published_at"]),
            reason=row["reason"],
            status=row["status"],
        )
