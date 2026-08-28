from __future__ import annotations

import logging

import aiohttp

from .config import Settings
from .storage import AIChatMessage

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 20
MAX_CONTEXT_CHARS = 12_000
MAX_TELEGRAM_CHARS = 3_900

AI_CHAT_SYSTEM_PROMPT = """Ты доброжелательный и понятный AI-помощник в семейном Telegram-боте.

Отвечай по-русски, если пользователь не попросил другой язык. Давай конкретные, полезные ответы без лишней воды. Если для точного ответа не хватает данных, честно скажи об этом и задай уточняющий вопрос. Не утверждай, что выполнил действие вне этого чата. Для медицинских, юридических и финансовых вопросов явно отмечай важные ограничения и не выдавай предположения за профессиональную консультацию."""


class AIChatError(RuntimeError):
    pass


def build_context(history: list[AIChatMessage], user_text: str) -> list[dict[str, str]]:
    selected: list[AIChatMessage] = []
    used_chars = len(user_text)
    for message in reversed(history[-MAX_CONTEXT_MESSAGES:]):
        if used_chars + len(message.content) > MAX_CONTEXT_CHARS:
            break
        selected.append(message)
        used_chars += len(message.content)
    selected.reverse()
    return [
        {"role": "system", "content": AI_CHAT_SYSTEM_PROMPT},
        *[{"role": message.role, "content": message.content} for message in selected],
        {"role": "user", "content": user_text.strip()},
    ]


class AIChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def answer(self, history: list[AIChatMessage], user_text: str) -> str:
        if not self.settings.amvera_api_token:
            raise AIChatError("AMVERA_API_TOKEN is not configured")

        payload = {
            "model": self.settings.amvera_llm_model,
            "messages": build_context(history, user_text),
            "temperature": 0.6,
            "max_tokens": 900,
        }
        response_payload = await self._request(payload)
        text = self._extract_text(response_payload)
        if not text:
            raise AIChatError("Amvera LLM returned an empty response")
        if len(text) <= MAX_TELEGRAM_CHARS:
            return text
        return text[: MAX_TELEGRAM_CHARS - 1].rstrip() + "…"

    async def _request(self, payload: dict[str, object]) -> object:
        url = f"{self.settings.amvera_llm_base_url.rstrip('/')}/chat/completions"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.settings.amvera_api_token}"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as exc:
            logger.exception("Failed to get AI chat response from Amvera LLM")
            raise AIChatError("Amvera LLM request failed") from exc

    @staticmethod
    def _extract_text(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        choice = choices[0]
        if not isinstance(choice, dict):
            return None
        message = choice.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        return content.strip() if isinstance(content, str) and content.strip() else None
