from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import aiohttp

from .config import Settings
from .storage import DiaryEntry, Storage

logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 12_000
MAX_TELEGRAM_CHARS = 3_900

WEEKLY_REVIEW_PROMPT_CACHE_KEY = "weekly_review:system_prompt"

DEFAULT_WEEKLY_REVIEW_PROMPT = """Ты составляешь доброжелательный еженедельный обзор семейного дневника дел.

Правила:
- пиши по-русски, тепло, спокойно и уважительно;
- используй только факты из записей, ничего не придумывай;
- не приписывай планы, эмоции и результаты, которых нет в дневнике;
- объедини похожие дела и выдели действительно важное;
- не упоминай внутренние идентификаторы пользователей;
- уложись примерно в 1200–2200 знаков;
- верни только готовый текст обзора без служебных комментариев.

Структура:
🗓 Итоги недели
✅ Что удалось
🌟 Чем запомнилась неделя
🧩 Что осталось в процессе — только если это явно следует из записей
🌱 Небольшой фокус на следующую неделю — только осторожный вывод из незавершённых дел

Если данных для раздела нет, пропусти раздел. Не используй шаблонные похвалы."""

PROMPT_EDITOR_SYSTEM_PROMPT = """Ты помогаешь переписать системный промт для другого AI, который еженедельно \
готовит тёплый обзор семейного дневника дел на русском языке по фактам из записей.

Тебе дают текущий промт и пожелание, что в нём изменить. Перепиши промт целиком с учётом пожелания.

Правила:
- сохрани общее назначение промта — инструкция для AI, который составляет еженедельный обзор дневника;
- верни только новый текст промта целиком, без пояснений, кавычек и комментариев к своей работе;
- пиши по-русски."""


def get_custom_prompt(storage: Storage) -> str | None:
    cached = storage.get_cached_text(WEEKLY_REVIEW_PROMPT_CACHE_KEY)
    if cached is None:
        return None
    text, _source = cached
    return text


def save_custom_prompt(storage: Storage, text: str, saved_at: datetime) -> None:
    storage.save_cached_text(WEEKLY_REVIEW_PROMPT_CACHE_KEY, text.strip(), "admin_edit", saved_at)


def current_prompt_text(storage: Storage) -> str:
    return get_custom_prompt(storage) or DEFAULT_WEEKLY_REVIEW_PROMPT


class WeeklyReviewError(RuntimeError):
    pass


def current_week_period(now: datetime) -> tuple[datetime, datetime]:
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def empty_weekly_review_text(start: datetime, end: datetime) -> str:
    return (
        f"🗓 Итоги недели · {start:%d.%m}–{end:%d.%m}\n\n"
        "На этой неделе в дневнике пока не было записей. "
        "Ничего страшного — начнём следующую неделю с чистого листа."
    )


def build_weekly_review_prompt(entries: list[DiaryEntry], start: datetime, end: datetime) -> str:
    lines: list[str] = []
    used_chars = 0
    omitted = 0
    for entry in entries:
        text = re.sub(r"\s+", " ", entry.text).strip()
        if not text and entry.photo_file_id:
            text = "Добавлено фото без подписи."
        if not text:
            continue
        text = text[:600]
        line = f"- {entry.created_at:%d.%m %H:%M}: {text}"
        if used_chars + len(line) > MAX_SOURCE_CHARS:
            omitted += 1
            continue
        lines.append(line)
        used_chars += len(line)

    if omitted:
        lines.append(f"- Ещё записей, не поместившихся в запрос: {omitted}.")

    return (
        f"Период обзора: {start:%d.%m.%Y}–{end:%d.%m.%Y}.\n"
        f"Количество записей: {len(entries)}.\n\n"
        "Записи дневника:\n"
        + "\n".join(lines)
    )


class WeeklyReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self,
        entries: list[DiaryEntry],
        start: datetime,
        end: datetime,
        system_prompt: str | None = None,
    ) -> str:
        if not self.settings.amvera_api_token:
            raise WeeklyReviewError("AMVERA_API_TOKEN is not configured")
        if not entries:
            return empty_weekly_review_text(start, end)

        payload = {
            "model": self.settings.amvera_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_WEEKLY_REVIEW_PROMPT},
                {"role": "user", "content": build_weekly_review_prompt(entries, start, end)},
            ],
            "temperature": 0.35,
            "max_tokens": 700,
        }
        response_payload = await self._request(payload)
        text = self._extract_text(response_payload)
        if not text:
            raise WeeklyReviewError("Amvera LLM returned an empty response")
        return self._fit_for_telegram(text)

    async def revise_prompt(self, current_prompt: str, instruction: str) -> str:
        if not self.settings.amvera_api_token:
            raise WeeklyReviewError("AMVERA_API_TOKEN is not configured")

        payload = {
            "model": self.settings.amvera_llm_model,
            "messages": [
                {"role": "system", "content": PROMPT_EDITOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Текущий промт:\n\n{current_prompt}\n\nПожелание: {instruction}",
                },
            ],
            "temperature": 0.4,
            "max_tokens": 700,
        }
        response_payload = await self._request(payload)
        text = self._extract_text(response_payload)
        if not text:
            raise WeeklyReviewError("Amvera LLM returned an empty response")
        return text.strip()

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
            logger.exception("Failed to generate weekly review with Amvera LLM")
            raise WeeklyReviewError("Amvera LLM request failed") from exc

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

    @staticmethod
    def _fit_for_telegram(text: str) -> str:
        clean = text.strip()
        if len(clean) <= MAX_TELEGRAM_CHARS:
            return clean
        return clean[: MAX_TELEGRAM_CHARS - 1].rstrip() + "…"
