from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from helper_bot.config import load_settings
from helper_bot.lunar_service import LunarService


class LunarServiceTest(unittest.TestCase):
    def test_settings_prefers_railway_volume_for_default_data_dir(self) -> None:
        railway_volume_path = Path("railway_volume_data").resolve()
        env = {
            "BOT_TOKEN": "token",
            "ALLOWED_USER_IDS": "1",
            "DATA_DIR": "data",
            "RAILWAY_VOLUME_MOUNT_PATH": str(railway_volume_path),
        }
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.data_dir, railway_volume_path)

    def test_daily_text_contains_barnaul_and_lunar_day(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "ALLOWED_USER_IDS": "1",
            "TIMEZONE": "Asia/Barnaul",
            "LUNAR_REGION": "Алтайский край",
            "LUNAR_CITY": "Барнаул",
        }
        with patch("helper_bot.config.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        text = LunarService(settings).daily_text(date(2026, 5, 21))

        self.assertIn("Барнаул, Алтайский край", text)
        self.assertIn("лунный день", text)
        self.assertNotIn("посев", text.lower())

        garden_text = LunarService(settings).garden_text(date(2026, 5, 21))
        self.assertIn("садоводческому лунному календарю", garden_text)
        self.assertIn("растениями", garden_text)


if __name__ == "__main__":
    unittest.main()
