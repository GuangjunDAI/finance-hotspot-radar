from datetime import datetime, timezone
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
