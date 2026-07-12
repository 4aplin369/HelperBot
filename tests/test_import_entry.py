from __future__ import annotations

import unittest
from zoneinfo import ZoneInfo

from helper_bot.bot import parse_import_entry_command


class ImportEntryCommandTest(unittest.TestCase):
    def test_parse_import_entry_with_text(self) -> None:
        parsed = parse_import_entry_command(
            "/import_entry 2026-06-03 14:30 Посадил редиску",
            ZoneInfo("Asia/Barnaul"),
        )

        assert parsed is not None
        created_at, text = parsed
        self.assertEqual(created_at.isoformat(), "2026-06-03T14:30:00+07:00")
        self.assertEqual(text, "Посадил редиску")

    def test_parse_import_entry_without_text(self) -> None:
        parsed = parse_import_entry_command("/import_entry 2026-06-03 14:30", ZoneInfo("Asia/Barnaul"))

        assert parsed is not None
        created_at, text = parsed
        self.assertEqual(created_at.isoformat(), "2026-06-03T14:30:00+07:00")
        self.assertEqual(text, "")

    def test_parse_import_entry_with_russian_date_format(self) -> None:
        parsed = parse_import_entry_command(
            "/import_entry 08.07.2026 17:06 папа работал у Колиного шефа",
            ZoneInfo("Asia/Barnaul"),
        )

        assert parsed is not None
        created_at, text = parsed
        self.assertEqual(created_at.isoformat(), "2026-07-08T17:06:00+07:00")
        self.assertEqual(text, "папа работал у Колиного шефа")

    def test_parse_import_entry_rejects_bad_date(self) -> None:
        self.assertIsNone(parse_import_entry_command("/import_entry 2026/06/03 14:30 текст", ZoneInfo("Asia/Barnaul")))


if __name__ == "__main__":
    unittest.main()
