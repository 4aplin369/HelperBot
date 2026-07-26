from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from helper_bot.scheduler import send_diary_reminders
from helper_bot.storage import Storage


class DiaryReminderSchedulerTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_only_once_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
            storage.init()
            bot = SimpleNamespace(send_message=AsyncMock())
            settings = SimpleNamespace(
                allowed_user_ids=frozenset({222}),
                admin_user_ids=frozenset({111}),
            )
            now = datetime(2026, 7, 26, 18, 0)

            await send_diary_reminders(bot, storage, settings, now)
            await send_diary_reminders(bot, storage, settings, now)

            bot.send_message.assert_awaited_once()
            self.assertTrue(storage.was_diary_reminder_sent(now.date(), 222))
            markup = bot.send_message.await_args.kwargs["reply_markup"]
            self.assertEqual(markup.inline_keyboard[0][0].callback_data, "open_diary")


if __name__ == "__main__":
    unittest.main()
