import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.parse
from pathlib import Path

from finance_hotspot_radar.config import Settings
from finance_hotspot_radar.web import RadarRequestHandler
from finance_hotspot_radar.service import RadarService
from http.server import HTTPServer


class WebTests(unittest.TestCase):
    def test_web_config_and_keywords_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(db_path=Path(tmp) / "radar.db", ai_api_key="x", ai_base_url="https://rehdasu.cn")
            service = RadarService(settings)
            service.init_db(seed=True)

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
                self.assertEqual(hotspots, [])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


def _get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))
