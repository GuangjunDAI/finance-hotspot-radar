import os
import unittest
from pathlib import Path

from finance_hotspot_radar.config import Settings, load_env_file


class ConfigTests(unittest.TestCase):
    def test_load_env_file_and_normalize_ai_base_url(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("FINANCE_RADAR_TEST_VALUE=ok\n", encoding="utf-8")
            os.environ.pop("FINANCE_RADAR_TEST_VALUE", None)
            load_env_file(str(env))
            self.assertEqual(os.environ["FINANCE_RADAR_TEST_VALUE"], "ok")

        settings = Settings(ai_base_url="https://rehdasu.cn")
        self.assertEqual(settings.ai_base_url, "https://rehdasu.cn/v1/chat/completions")
