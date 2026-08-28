from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from helper_bot.ai_chat_service import AIChatError, AIChatService, build_context
from helper_bot.storage import AIChatMessage


def _message(message_id: int, role: str, content: str) -> AIChatMessage:
    return AIChatMessage(
        id=message_id,
        conversation_id=1,
        user_id=111,
        role=role,
        content=content,
        created_at=datetime(2026, 8, 28, 10, message_id),
    )


class AIChatServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            amvera_api_token="token",
            amvera_llm_base_url="https://inference.waw0.amvera.ru/v1",
            amvera_llm_model="gpt-4.1",
        )

    def test_context_contains_history_and_new_question(self) -> None:
        context = build_context(
            [_message(1, "user", "Первый вопрос"), _message(2, "assistant", "Первый ответ")],
            "Уточнение",
        )

        self.assertEqual([message["role"] for message in context], ["system", "user", "assistant", "user"])
        self.assertEqual(context[-1]["content"], "Уточнение")

    async def test_answer_uses_configured_model(self) -> None:
        service = AIChatService(self.settings)
        service._request = AsyncMock(  # type: ignore[method-assign]
            return_value={"choices": [{"message": {"content": "Ответ"}}]}
        )
        result = await service.answer([], "Вопрос")

        self.assertEqual(result, "Ответ")
        payload = service._request.await_args.args[0]
        self.assertEqual(payload["model"], "gpt-4.1")
        self.assertEqual(payload["messages"][-1]["content"], "Вопрос")

    async def test_requires_token(self) -> None:
        settings = SimpleNamespace(
            amvera_api_token="",
            amvera_llm_base_url="https://inference.waw0.amvera.ru/v1",
            amvera_llm_model="gpt-4.1",
        )

        with self.assertRaises(AIChatError):
            await AIChatService(settings).answer([], "Вопрос")


if __name__ == "__main__":
    unittest.main()
