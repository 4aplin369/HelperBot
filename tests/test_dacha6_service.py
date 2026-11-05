from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import AsyncMock, Mock

from helper_bot.dacha6_service import Dacha6Service, DailyGardenDetails, _month_days_text, _parse_day, _with_today_title


class FolkSignsTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_only_signs_and_caches_them(self) -> None:
        service = Dacha6Service(Mock(), Mock())
        service._get_cached_text = Mock(return_value=None)
        service._save_cached_text = Mock()
        service.get_daily_details = AsyncMock(return_value=DailyGardenDetails(
            good=("Полив",), medium=(), bad=(), folk_signs=("Примета дня",),
        ))
        today = date(2026, 11, 5)
        self.assertEqual(await service.folk_signs_text(today), "- Примета дня")
        service._save_cached_text.assert_called_once_with(
            "dacha6:folk:2026-11-05", "- Примета дня", "dacha6",
        )
        service._get_cached_text.return_value = "- Примета дня"
        self.assertEqual(await service.folk_signs_text(today), "- Примета дня")
        service.get_daily_details.assert_awaited_once()

    async def test_missing_signs_do_not_fall_back_to_garden_advice(self) -> None:
        for details in (None, DailyGardenDetails(("Полив",), (), (), ())):
            service = Dacha6Service(Mock(), Mock())
            service.get_daily_details = AsyncMock(return_value=details)
            text = await service.folk_signs_text(date(2026, 11, 5))
            self.assertIn("не удалось загрузить", text)
            self.assertNotIn("Полив", text)
            service.lunar_service.garden_text.assert_not_called()


class Dacha6ParserTest(unittest.TestCase):
    def test_parse_day_category_and_moon_info(self) -> None:
        html = """
        <ul>
          <li>Самые благоприятные дни – 1, 19, 20, 28, 29, 30 мая</li>
          <li>Благоприятные дни – 3, 6, 7, 8, 11, 12, 15, 16, 26, 27 мая</li>
          <li>Нейтральные дни – 4, 5, 18, 24, 25 мая</li>
          <li>Нежелательные дни – 9, 10, 13, 14, 21, 22, 23 мая</li>
          <li>Самые неблагоприятные (запрещенные) дни – 2, 17, 31 мая</li>
        </ul>
        <table>
          <tr style="background-color: #f5ffe0"><td>21 мая 2026<br>четверг</td>
          <td></td>
          <td>Луна в знаке:<br><span>Рак ♋</span><br><span>Лев ♌</span><br>
          <span>Дни Плода</span><br><span>Стихия: Огонь</span></td>
          <td><span>5, 6 лунный день</span><br>Растущая луна</td></tr>
        </table>
        """

        info = _parse_day(html, date(2026, 5, 21), "https://example.test")

        assert info is not None
        self.assertEqual(info.category, "Нежелательные дни")
        self.assertIn("5, 6 лунный день", info.moon_info)
        self.assertIn("Растущая луна", info.moon_info)

    def test_month_days_text_handles_june_without_day_31(self) -> None:
        html = """
        <ul>
          <li>Благоприятные дни – 1 июня</li>
        </ul>
        <table>
          <tr><td>1 июня 2026<br>понедельник</td>
          <td></td><td>Луна в знаке:<br><span>Стрелец ♐</span></td>
          <td><span>16, 17 лунный день</span><br>Убывающая луна</td></tr>
        </table>
        """

        text = _month_days_text(html, date(2026, 6, 1))

        self.assertIn("01: благоприятные дни", text)
        self.assertNotIn("31:", text)

    def test_today_title_has_full_date(self) -> None:
        text = _with_today_title(date(2026, 5, 27), "Хорошо:\n- Полив")

        self.assertTrue(text.startswith("Что сделать на даче: 27 мая 2026"))
        self.assertIn("Хорошо:\n- Полив", text)


if __name__ == "__main__":
    unittest.main()
