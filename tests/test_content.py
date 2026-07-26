from __future__ import annotations

import unittest

from helper_bot.content import DIARY_REMINDERS, diary_reminder


class DiaryReminderTest(unittest.TestCase):
    def test_returns_known_reminder(self) -> None:
        self.assertIn(diary_reminder(), DIARY_REMINDERS)

    def test_does_not_repeat_previous_reminder(self) -> None:
        previous = DIARY_REMINDERS[0]

        for _ in range(100):
            self.assertNotEqual(diary_reminder(previous), previous)


if __name__ == "__main__":
    unittest.main()
