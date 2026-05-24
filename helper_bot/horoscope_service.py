from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

import aiohttp

from .config import Settings
from .storage import Storage

logger = logging.getLogger(__name__)

SIGN_NAMES_RU = {
    "pisces": "Рыбы",
}

API_SIGN_NAMES = {
    "pisces": "Pisces",
}


@dataclass(frozen=True)
class HoroscopeResult:
    text: str
    source: str


class HoroscopeService:
    def __init__(self, storage: Storage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    async def get_daily(self, today: date, force_refresh: bool = False) -> HoroscopeResult:
        sign = self.settings.horoscope_sign
        if not force_refresh:
            cached = self.storage.get_horoscope(today, sign)
            if cached is not None:
                text, source = cached
                if source != "fallback" or not self.settings.horoscope_api_key:
                    return HoroscopeResult(text=text, source=source)

        result = await self._fetch_from_api(sign, today)
        if result is None:
            result = HoroscopeResult(text=self._fallback_text(sign), source="fallback")

        self.storage.save_horoscope(
            horoscope_date=today,
            sign=sign,
            text=result.text,
            source=result.source,
            fetched_at=datetime.now(self.settings.timezone),
        )
        return result

    async def _fetch_from_api(self, sign: str, today: date) -> HoroscopeResult | None:
        if self.settings.horoscope_provider == "freehoroscopeapi":
            return await self._fetch_free_horoscope_api(sign)
        return await self._fetch_astrology_api(sign, today)

    async def _fetch_astrology_api(self, sign: str, today: date) -> HoroscopeResult | None:
        if not self.settings.horoscope_api_key:
            logger.warning("HOROSCOPE_API_KEY is empty; using fallback horoscope")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.settings.horoscope_api_url,
                    json={
                        "sign": API_SIGN_NAMES.get(sign, sign.title()),
                        "date": today.isoformat(),
                        "language": self.settings.horoscope_language,
                        "format": "paragraph",
                        "use_emoji": False,
                    },
                    headers={"Authorization": f"Bearer {self.settings.horoscope_api_key}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except Exception:
            logger.exception("Failed to fetch horoscope from Astrology API")
            return None

        text = self._extract_text(payload)
        if not text:
            logger.warning("Astrology API returned no text: %s", payload)
            return None
        return HoroscopeResult(text=text, source="astrology_api")

    async def _fetch_free_horoscope_api(self, sign: str) -> HoroscopeResult | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.settings.horoscope_api_url,
                    params={"sign": sign},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except Exception:
            logger.exception("Failed to fetch horoscope from Free Horoscope API")
            return None

        text = self._extract_text(payload)
        if not text:
            logger.warning("Free Horoscope API returned no text: %s", payload)
            return None
        return HoroscopeResult(text=text, source="freehoroscopeapi")

    @staticmethod
    def _extract_text(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        if isinstance(data, dict):
            text = data.get("text")
            extracted = HoroscopeService._extract_text_from_text_field(text)
            if extracted:
                return extracted

            horoscope = data.get("horoscope")
            if isinstance(horoscope, str):
                return horoscope.strip()

        horoscope = payload.get("horoscope")
        if isinstance(horoscope, dict):
            text = horoscope.get("text")
            return HoroscopeService._extract_text_from_text_field(text)
        if isinstance(horoscope, str):
            return horoscope.strip()

        text = payload.get("text")
        return HoroscopeService._extract_text_from_text_field(text)

    @staticmethod
    def _extract_text_from_text_field(text: object) -> str | None:
        if isinstance(text, str):
            return text.strip()
        if not isinstance(text, dict):
            return None

        parts: list[str] = []
        for key in ("general", "home", "creativity", "personal_growth", "spirituality"):
            value = text.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        return "\n\n".join(parts) if parts else None
        return None

    @staticmethod
    def _fallback_text(sign: str) -> str:
        sign_name = SIGN_NAMES_RU.get(sign, "Рыбы")
        return (
            f"{sign_name}: сегодня хороший день для спокойных дел, порядка и небольших задач без спешки. "
            "Лучше выбрать одно главное дело и спокойно довести его до конца."
        )
