from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from helper_bot.formatting import format_entries_export
from helper_bot.storage import Storage


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
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

    def test_reinitialization_preserves_existing_diary_entries(self) -> None:
        created_at = datetime(2026, 8, 27, 18, 30)
        self.storage.add_entry(111, "Старая папина запись", created_at)

        self.storage.init()

        entries = self.storage.all_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].text, "Старая папина запись")
        self.assertEqual(entries[0].created_at, created_at)

    def test_digest_marker(self) -> None:
        digest_date = date(2026, 5, 21)

        self.assertFalse(self.storage.was_digest_sent(digest_date, 111))
        self.storage.mark_digest_sent(digest_date, 111, datetime(2026, 5, 21, 8, 0))
        self.assertTrue(self.storage.was_digest_sent(digest_date, 111))

    def test_diary_reminder_marker_and_last_text(self) -> None:
        reminder_date = date(2026, 5, 21)

        self.assertFalse(self.storage.was_diary_reminder_sent(reminder_date, 111))
        self.assertIsNone(self.storage.last_diary_reminder_text(111))

        self.storage.mark_diary_reminder_sent(
            reminder_date,
            111,
            "Как прошёл день?",
            datetime(2026, 5, 21, 18, 0),
        )

        self.assertTrue(self.storage.was_diary_reminder_sent(reminder_date, 111))
        self.assertEqual(self.storage.last_diary_reminder_text(111), "Как прошёл день?")

    def test_all_entries_and_export(self) -> None:
        self.storage.add_entry(111, "Починил розетку", datetime(2026, 5, 22, 15, 0))
        self.storage.add_entry(222, "Посадил редиску", datetime(2026, 5, 21, 9, 30))

        entries = self.storage.all_entries()
        self.assertEqual([entry.text for entry in entries], ["Посадил редиску", "Починил розетку"])

        export_text = format_entries_export(entries)
        self.assertIn("Дневник дел", export_text)
        self.assertIn("21.05.2026", export_text)
        self.assertIn("09:30 Посадил редиску", export_text)
        self.assertIn("15:00 Починил розетку", export_text)

    def test_entries_between(self) -> None:
        self.storage.add_entry(111, "До недели", datetime(2026, 7, 19, 23, 59))
        self.storage.add_entry(111, "На этой неделе", datetime(2026, 7, 22, 10, 0))
        self.storage.add_entry(111, "После периода", datetime(2026, 7, 27, 0, 1))

        entries = self.storage.entries_between(
            datetime(2026, 7, 20, 0, 0),
            datetime(2026, 7, 26, 19, 0),
        )

        self.assertEqual([entry.text for entry in entries], ["На этой неделе"])

    def test_weekly_review_cache_and_marker(self) -> None:
        week_start = date(2026, 7, 20)
        sent_at = datetime(2026, 7, 26, 19, 0)

        self.assertIsNone(self.storage.get_weekly_review(week_start))
        self.assertFalse(self.storage.was_weekly_review_sent(week_start, 111))

        self.storage.save_weekly_review(week_start, sent_at, "Итоги недели", sent_at)
        self.storage.mark_weekly_review_sent(week_start, 111, sent_at)

        self.assertEqual(self.storage.get_weekly_review(week_start), "Итоги недели")
        self.assertTrue(self.storage.was_weekly_review_sent(week_start, 111))

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

    def test_content_cache(self) -> None:
        self.assertIsNone(self.storage.get_cached_text("dacha6:garden:2026-05-27:folk=1"))

        self.storage.save_cached_text(
            "dacha6:garden:2026-05-27:folk=1",
            "Что сделать на даче: 27 мая 2026",
            "dacha6",
            datetime(2026, 5, 27, 9, 0),
        )

        self.assertEqual(
            self.storage.get_cached_text("dacha6:garden:2026-05-27:folk=1"),
            ("Что сделать на даче: 27 мая 2026", "dacha6"),
        )

    def test_ai_chat_history_is_separate_and_persistent(self) -> None:
        started_at = datetime(2026, 8, 28, 10, 0)
        first_conversation = self.storage.get_or_start_ai_conversation(111, started_at)
        self.storage.add_ai_chat_message(first_conversation, 111, "user", "Как дела?", started_at)
        self.storage.add_ai_chat_message(first_conversation, 111, "assistant", "Хорошо", started_at)

        self.assertEqual(
            [message.content for message in self.storage.ai_chat_messages(first_conversation)],
            ["Как дела?", "Хорошо"],
        )
        self.assertEqual(
            self.storage.get_or_start_ai_conversation(111, datetime(2026, 8, 28, 11, 0)),
            first_conversation,
        )
        second_conversation = self.storage.start_ai_conversation(111, datetime(2026, 8, 28, 12, 0))
        other_user_conversation = self.storage.get_or_start_ai_conversation(222, started_at)

        self.assertNotEqual(second_conversation, first_conversation)
        self.assertNotEqual(other_user_conversation, second_conversation)
        self.assertEqual(self.storage.active_ai_conversation_id(111), second_conversation)
        self.assertEqual(self.storage.ai_chat_messages(second_conversation), [])

    def test_ai_chat_rejects_unknown_role(self) -> None:
        conversation_id = self.storage.start_ai_conversation(111, datetime(2026, 8, 28, 10, 0))

        with self.assertRaises(ValueError):
            self.storage.add_ai_chat_message(
                conversation_id,
                111,
                "system",
                "Нельзя сохранять системное сообщение",
                datetime(2026, 8, 28, 10, 0),
            )


if __name__ == "__main__":
    unittest.main()
