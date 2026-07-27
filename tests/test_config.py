from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from helper_bot.config import load_settings


class DiaryReminderSettingsTest(unittest.TestCase):
    def test_defaults_to_six_pm(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "ALLOWED_USER_IDS": "111,222",
            "ADMIN_USER_IDS": "111",
            "TIMEZONE": "Asia/Barnaul",
        }

        with patch("helper_bot.config.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(
            (settings.diary_reminder_hour, settings.diary_reminder_minute),
            (18, 0),
        )
        self.assertFalse(settings.weekly_review_enabled)
        self.assertEqual(settings.weekly_review_weekday, 6)
        self.assertEqual(
            (settings.weekly_review_hour, settings.weekly_review_minute),
            (19, 0),
        )
        self.assertEqual(settings.amvera_llm_model, "llama70b")

    def test_barnaul_timezone_is_the_default(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "ALLOWED_USER_IDS": "222",
        }

        with patch("helper_bot.config.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.timezone.key, "Asia/Barnaul")


if __name__ == "__main__":
    unittest.main()
