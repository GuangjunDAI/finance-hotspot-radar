from datetime import datetime, timezone
import unittest

from finance_hotspot_radar.analyzer import HeuristicAnalyzer
from finance_hotspot_radar.models import Keyword, SourceItem


class AnalyzerTests(unittest.TestCase):
    def test_analyzer_scores_and_flags_rumor(self):
        analyzer = HeuristicAnalyzer()
        keywords = [Keyword("央行", ["降息"], "macro", 1.3)]
        items = [
            SourceItem("google-news", "网传央行即将降息", "https://a.test/1", datetime.now(timezone.utc), "未经证实", 3),
        ]

        hotspots = analyzer.analyze(items, keywords)

        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0].keywords, ["央行"])
        self.assertEqual(hotspots[0].status, "risk")
        self.assertLess(hotspots[0].credibility, 0.6)
