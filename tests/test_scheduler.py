from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from helper_bot.scheduler import send_daily_digest, send_diary_reminders, send_weekly_reviews
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


class DailyDigestSchedulerTest(unittest.IsolatedAsyncioTestCase):
    async def test_winter_digest_does_not_request_dacha_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
            storage.init()
            bot = SimpleNamespace(send_message=AsyncMock())
            settings = SimpleNamespace(
                allowed_user_ids=frozenset({222}),
                admin_user_ids=frozenset(),
                horoscope_sign="pisces",
                recipient_name="Павел Николаевич",
            )
            horoscope_service = SimpleNamespace(
                get_daily=AsyncMock(return_value=SimpleNamespace(text="Спокойный день"))
            )
            dacha6_service = SimpleNamespace(
                garden_text=AsyncMock(),
                folk_signs_text=AsyncMock(return_value="Примета дня"),
            )
            now = datetime(2026, 11, 4, 8, 0)

            await send_daily_digest(
                bot,
                storage,
                settings,
                horoscope_service,
                SimpleNamespace(),
                dacha6_service,
                now,
            )

            dacha6_service.garden_text.assert_not_awaited()
            dacha6_service.folk_signs_text.assert_awaited_once_with(now.date())
            sent_text = bot.send_message.await_args.args[1]
            self.assertNotIn("На даче сегодня", sent_text)
            self.assertIn("Народные приметы\nПримета дня", sent_text)


class WeeklyReviewSchedulerTest(unittest.IsolatedAsyncioTestCase):
    async def test_generates_once_and_sends_once_to_each_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
            storage.init()
            storage.add_entry(222, "Закончил ремонт полки", datetime(2026, 7, 22, 12, 0))
            bot = SimpleNamespace(send_message=AsyncMock())
            settings = SimpleNamespace(
                allowed_user_ids=frozenset({111, 222}),
                admin_user_ids=frozenset({111}),
            )
            service = SimpleNamespace(generate=AsyncMock(return_value="🗓 Итоги недели"))
            now = datetime(2026, 7, 26, 19, 0)

            await send_weekly_reviews(bot, storage, settings, service, now)
            await send_weekly_reviews(bot, storage, settings, service, now)

            service.generate.assert_awaited_once()
            self.assertEqual(bot.send_message.await_count, 2)
            self.assertTrue(storage.was_weekly_review_sent(now.date().replace(day=20), 111))
            self.assertTrue(storage.was_weekly_review_sent(now.date().replace(day=20), 222))

    async def test_empty_week_does_not_call_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
            storage.init()
            bot = SimpleNamespace(send_message=AsyncMock())
            settings = SimpleNamespace(
                allowed_user_ids=frozenset({222}),
                admin_user_ids=frozenset(),
            )
            service = SimpleNamespace(generate=AsyncMock())

            await send_weekly_reviews(
                bot,
                storage,
                settings,
                service,
                datetime(2026, 7, 26, 19, 0),
            )

            service.generate.assert_not_awaited()
            sent_text = bot.send_message.await_args.args[1]
            self.assertIn("не было записей", sent_text)


if __name__ == "__main__":
    unittest.main()
