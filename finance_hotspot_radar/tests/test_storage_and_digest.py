from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from finance_hotspot_radar.formatter import digest_text
from finance_hotspot_radar.models import Hotspot, SourceItem
from finance_hotspot_radar.storage import Store


class StorageDigestTests(unittest.TestCase):
    def test_source_item_dedupe_and_hotspot_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "radar.db")
            store.init()
            item = SourceItem("rss", "央行降息", "https://a.test/1", datetime.now(timezone.utc), "summary", 2)

            self.assertEqual(store.save_source_items([item, item]), 1)
            self.assertEqual(len(store.recent_items(hours=24)), 1)

            hotspot = Hotspot(
                title="央行降息",
                summary="summary",
                sources=["rss"],
                urls=["https://a.test/1"],
                keywords=["央行"],
                importance=8,
                heat=3,
                relevance=0.8,
                credibility=0.7,
                published_at=datetime.now(timezone.utc),
                reason="test",
            )
            self.assertEqual(store.save_hotspots([hotspot, hotspot]), 1)
            rows = store.query_hotspots(keyword="央行", min_importance=7)
            self.assertEqual(len(rows), 1)
            self.assertIn("央行降息", digest_text(rows))


    def test_notification_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "radar.db")
            store.init()

            self.assertIs(store.mark_notified("console", 1, "alert"), True)
            self.assertIs(store.mark_notified("console", 1, "alert"), False)

    def test_hotspot_sort_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "radar.db")
            store.init()
            now = datetime.now(timezone.utc)
            early = Hotspot(
                title="早",
                summary="early",
                sources=["rss"],
                urls=["https://a.test/early"],
                keywords=["央行"],
                importance=2,
                heat=1,
                relevance=0.5,
                credibility=0.7,
                published_at=now - timedelta(hours=2),
                reason="test",
            )
            late = Hotspot(
                title="晚",
                summary="late",
                sources=["rss"],
                urls=["https://a.test/late"],
                keywords=["央行"],
                importance=8,
                heat=5,
                relevance=0.9,
                credibility=0.8,
                published_at=now,
                reason="test",
            )
            store.save_hotspots([early, late])

            self.assertEqual(store.query_hotspots(sort="time", order="asc", limit=2)[0].title, "早")
            self.assertEqual(store.query_hotspots(sort="time", order="desc", limit=2)[0].title, "晚")
            self.assertEqual(store.query_hotspots(sort="importance", order="asc", limit=2)[0].title, "早")
