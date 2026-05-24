from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from helper_bot.storage import Storage


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
        self.storage.init()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_add_search_and_month_entries(self) -> None:
        created_at = datetime(2026, 5, 21, 10, 30)
        self.storage.add_entry(111, "Починил розетку на кухне", created_at)
        self.storage.add_entry(111, "Посадил редиску у теплицы", datetime(2026, 6, 1, 9, 0))

        search_result = self.storage.search_entries("РОЗЕТКУ")
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result[0].text, "Починил розетку на кухне")

        may_entries = self.storage.entries_for_month(2026, 5)
        self.assertEqual(len(may_entries), 1)
        self.assertEqual(may_entries[0].created_at, created_at)

    def test_digest_marker(self) -> None:
        digest_date = date(2026, 5, 21)

        self.assertFalse(self.storage.was_digest_sent(digest_date, 111))
        self.storage.mark_digest_sent(digest_date, 111, datetime(2026, 5, 21, 8, 0))
        self.assertTrue(self.storage.was_digest_sent(digest_date, 111))

    def test_horoscope_cache(self) -> None:
        horoscope_date = date(2026, 5, 21)
        self.assertIsNone(self.storage.get_horoscope(horoscope_date, "pisces"))

        self.storage.save_horoscope(
            horoscope_date=horoscope_date,
            sign="pisces",
            text="Рыбы: спокойный день.",
            source="test",
            fetched_at=datetime(2026, 5, 21, 8, 0),
        )

        self.assertEqual(
            self.storage.get_horoscope(horoscope_date, "pisces"),
            ("Рыбы: спокойный день.", "test"),
        )


if __name__ == "__main__":
    unittest.main()
