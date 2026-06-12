from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from finance_hotspot_radar.analyzer import HeuristicAnalyzer
from finance_hotspot_radar.models import Keyword, SourceItem
from finance_hotspot_radar.storage import Store


class IntegrationTests(unittest.TestCase):
    def test_mock_scan_analyze_store_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "radar.db")
            store.init()
            store.add_keyword("美联储", ["FOMC", "降息"], "macro", 1.5)
            keywords = store.list_keywords(active=True)
            items = [
                SourceItem("mock-rss", "美联储释放降息信号", "https://a.test/fed", datetime.now(timezone.utc), "美股和黄金关注", 5),
                SourceItem("mock-social", "FOMC 降息讨论升温", "https://b.test/fomc", datetime.now(timezone.utc), "热搜", 20),
            ]

            self.assertEqual(store.save_source_items(items), 2)
            hotspots = HeuristicAnalyzer().analyze(store.recent_items(hours=24), keywords)
            self.assertGreaterEqual(store.save_hotspots(hotspots), 1)

            result = store.query_hotspots(keyword="美联储", sort="importance", limit=5)
            self.assertTrue(result)
            self.assertGreaterEqual(result[0].importance, 1.5)
            self.assertGreaterEqual(len(result[0].sources), 1)
