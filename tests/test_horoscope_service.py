from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from helper_bot.horoscope_service import HoroscopeResult, HoroscopeService, _extract_mail_ru_text
from helper_bot.storage import Storage


class HoroscopeServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_extract_mail_ru_text(self) -> None:
        page = """
        <main itemProp="articleBody">
          <div><p><span>Первый абзац для Рыб.</span></p></div>
          <div><p><span>Второй &amp; важный абзац.</span></p></div>
        </main>
        """

        self.assertEqual(
            _extract_mail_ru_text(page),
            "Первый абзац для Рыб.\n\nВторой & важный абзац.",
        )

    async def test_provider_change_ignores_old_cached_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            storage = Storage(root / "bot.sqlite3", root / "photos", root / "backups")
            storage.init()
            storage.save_horoscope(date(2026, 6, 12), "pisces", "Старый текст", "astrology_api", date(2026, 6, 12))

            settings = SimpleNamespace(
                horoscope_sign="pisces",
                horoscope_provider="mail_ru",
                horoscope_api_key="",
                timezone=ZoneInfo("Asia/Barnaul"),
            )
            service = _FakeHoroscopeService(storage, settings)

            result = await service.get_daily(date(2026, 6, 12))

        self.assertEqual(result, HoroscopeResult(text="Новый текст", source="mail_ru"))


class _FakeHoroscopeService(HoroscopeService):
    async def _fetch_from_api(self, sign: str, today: date) -> HoroscopeResult | None:
        return HoroscopeResult(text="Новый текст", source="mail_ru")


if __name__ == "__main__":
    unittest.main()
