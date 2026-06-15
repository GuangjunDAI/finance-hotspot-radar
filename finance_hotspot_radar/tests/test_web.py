import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from finance_hotspot_radar.config import Settings
from finance_hotspot_radar.models import Hotspot
from finance_hotspot_radar.storage import Store
from finance_hotspot_radar.web import RadarRequestHandler
from finance_hotspot_radar.service import RadarService
from http.server import HTTPServer


class WebTests(unittest.TestCase):
    def test_web_config_and_keywords_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(db_path=Path(tmp) / "radar.db", ai_api_key="x", ai_base_url="https://rehdasu.cn")
            service = RadarService(settings)
            service.init_db(seed=True)
            store = Store(settings.db_path)
            store.init()
            store.save_hotspots(
                [
                    Hotspot(
                        title="央行测试",
                        summary="summary",
                        sources=["rss"],
                        urls=["https://a.test/1"],
                        keywords=["央行"],
                        importance=1,
                        heat=1,
                        relevance=0.5,
                        credibility=0.8,
                        published_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                        reason="test",
                    )
                ]
            )

            class Handler(RadarRequestHandler):
                radar_settings = settings

            server = HTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"
                config = _get_json(base + "/api/config")
                self.assertTrue(config["ai_enabled"])
                self.assertEqual(config["ai_base_url"], "https://rehdasu.cn/v1/chat/completions")
                keywords = _get_json(base + "/api/keywords")
                self.assertTrue(any(item["name"] == "央行" for item in keywords))
                hotspots = _get_json(base + "/api/hotspots?" + urllib.parse.urlencode({"keyword": "医药"}))
                self.assertEqual(hotspots["items"], [])
                self.assertEqual(hotspots["fallback_7d_count"], 0)
                rows = _get_json(base + "/api/hotspots?" + urllib.parse.urlencode({"keyword": "央行", "hours": 87600}))
                self.assertIn("北京时间", rows["items"][0]["published_at_display"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


def _get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))
