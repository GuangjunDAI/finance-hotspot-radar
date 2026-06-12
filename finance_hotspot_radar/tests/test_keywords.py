import unittest

from finance_hotspot_radar.storage import Store


class KeywordTests(unittest.TestCase):
    def test_keyword_pause_activate(self):
        with __import__("tempfile").TemporaryDirectory() as tmp:
            store = Store(__import__("pathlib").Path(tmp) / "radar.db")
            store.init()
            store.add_keyword("央行", ["降息"], "macro", 1.2)

            self.assertEqual([kw.name for kw in store.list_keywords(active=True)], ["央行"])
            self.assertEqual(store.set_keyword_active("央行", False), 1)
            self.assertEqual(store.list_keywords(active=True), [])
            self.assertEqual(store.set_keyword_active("央行", True), 1)
            self.assertIs(store.list_keywords(active=True)[0].active, True)
