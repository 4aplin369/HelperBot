from __future__ import annotations

import unittest
from datetime import date

from helper_bot.content import DIARY_REMINDERS, dacha_topics_active, diary_reminder, morning_digest


class DiaryReminderTest(unittest.TestCase):
    def test_returns_known_reminder(self) -> None:
        self.assertIn(diary_reminder(), DIARY_REMINDERS)

    def test_does_not_repeat_previous_reminder(self) -> None:
        previous = DIARY_REMINDERS[0]

        for _ in range(100):
            self.assertNotEqual(diary_reminder(previous), previous)


class DachaSeasonTest(unittest.TestCase):
    def test_dacha_topics_pause_from_november_through_february(self) -> None:
        self.assertFalse(dacha_topics_active(date(2026, 11, 4)))
        self.assertFalse(dacha_topics_active(date(2027, 2, 28)))
        self.assertTrue(dacha_topics_active(date(2027, 3, 1)))
        self.assertTrue(dacha_topics_active(date(2027, 10, 31)))

    def test_winter_digest_omits_dacha_block(self) -> None:
        text = morning_digest(date(2026, 11, 4), horoscope_text="Спокойный день")

        self.assertNotIn("На даче сегодня", text)
        self.assertIn("Гороскоп", text)

    def test_spring_digest_contains_dacha_block(self) -> None:
        text = morning_digest(
            date(2027, 3, 1),
            horoscope_text="Спокойный день",
            garden_today_text="Проверить участок",
        )

        self.assertIn("На даче сегодня", text)
        self.assertIn("Проверить участок", text)

    def test_winter_digest_keeps_folk_signs_without_garden_advice(self) -> None:
        text = morning_digest(
            date(2026, 11, 5),
            garden_today_text="Полить грядки",
            folk_signs_text="Примета дня",
        )
        self.assertIn("Народные приметы\nПримета дня", text)
        self.assertNotIn("Полить грядки", text)
        self.assertNotIn("На даче сегодня", text)


if __name__ == "__main__":
    unittest.main()
