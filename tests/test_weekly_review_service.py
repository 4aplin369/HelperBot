from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from helper_bot.storage import DiaryEntry
from helper_bot.weekly_review_service import (
    WeeklyReviewError,
    WeeklyReviewService,
    build_weekly_review_prompt,
    current_week_period,
)


def _entry(text: str) -> DiaryEntry:
    return DiaryEntry(
        id=1,
        user_id=222,
        text=text,
        photo_file_id=None,
        photo_local_path=None,
        created_at=datetime(2026, 7, 22, 10, 30),
    )


class WeeklyReviewServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            amvera_api_token="token",
            amvera_llm_base_url="https://inference.waw0.amvera.ru/v1",
            amvera_llm_model="llama70b",
        )

    async def test_generates_review_from_openai_compatible_response(self) -> None:
        service = WeeklyReviewService(self.settings)
        service._request = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "choices": [
                    {"message": {"content": "🗓 Итоги недели\n✅ Починили полку."}}
                ]
            }
        )

        result = await service.generate(
            [_entry("Починил полку")],
            datetime(2026, 7, 20),
            datetime(2026, 7, 26, 19, 0),
        )

        self.assertIn("Починили полку", result)
        payload = service._request.await_args.args[0]
        self.assertEqual(payload["model"], "llama70b")
        self.assertIn("Починил полку", payload["messages"][1]["content"])

    async def test_requires_token(self) -> None:
        settings = SimpleNamespace(
            amvera_api_token="",
            amvera_llm_base_url="https://inference.waw0.amvera.ru/v1",
            amvera_llm_model="llama70b",
        )

        with self.assertRaises(WeeklyReviewError):
            await WeeklyReviewService(settings).generate(
                [_entry("Запись")],
                datetime(2026, 7, 20),
                datetime(2026, 7, 26),
            )

    def test_period_starts_on_monday(self) -> None:
        start, end = current_week_period(datetime(2026, 7, 26, 19, 0))

        self.assertEqual(start, datetime(2026, 7, 20, 0, 0))
        self.assertEqual(end, datetime(2026, 7, 26, 19, 0))

    def test_prompt_contains_period_and_entries(self) -> None:
        prompt = build_weekly_review_prompt(
            [_entry("Полил цветы")],
            datetime(2026, 7, 20),
            datetime(2026, 7, 26),
        )

        self.assertIn("20.07.2026–26.07.2026", prompt)
        self.assertIn("Полил цветы", prompt)


if __name__ == "__main__":
    unittest.main()
