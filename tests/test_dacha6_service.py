from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from helper_bot.dacha6_service import Dacha6Service, DailyGardenDetails, _month_days_text, _parse_day, _with_today_title, _page_matches_region


class RegionTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            lunar_city="Барнаул", lunar_region="Алтайский край",
            dacha6_calendar_url="https://www.dacha6.ru/lunnyi-kalendar-dachnika/altayskiy-kray/",
        )
        self.correct = '<h1>Календарь для г. Барнаул Алтайского края</h1><select><option>Москва</option><option selected>Алтайский край</option></select>'
        self.wrong = '<h1>Календарь для г. Москва</h1><select><option selected>Москва</option><option>Алтайский край</option></select><p>Барнаул</p>'

    def test_checks_selected_region_and_daily_heading(self) -> None:
        self.assertTrue(_page_matches_region(self.correct, self.settings, require_city=True))
        self.assertFalse(_page_matches_region(self.wrong, self.settings, require_city=True))
        self.assertFalse(_page_matches_region(self.wrong, self.settings))
        self.assertFalse(_page_matches_region(self.correct.replace('г. Барнаул', 'г. Москва'), self.settings, require_city=True))
        self.assertFalse(_page_matches_region(self.correct.replace(' selected', ''), self.settings))
        self.assertFalse(_page_matches_region('', self.settings))
        self.assertTrue(_page_matches_region(self.correct.replace('г. Барнаул', 'ноябрь'), self.settings))

    async def test_fetch_rejects_wrong_region_for_day_and_month(self) -> None:
        for page, valid in ((self.correct, True), (self.wrong, False)):
            response = Mock()
            response.read = AsyncMock()
            response.text = AsyncMock(return_value=page)
            request = AsyncMock()
            request.__aenter__.return_value = response
            session = Mock()
            session.get.return_value = request
            session_context = AsyncMock()
            session_context.__aenter__.return_value = session
            service = Dacha6Service(self.settings, Mock())
            with patch('helper_bot.dacha6_service.aiohttp.ClientSession', return_value=session_context), patch(
                'helper_bot.dacha6_service._parse_daily_details',
                return_value=DailyGardenDetails((), (), (), ('Примета',)),
            ) as parse_details:
                daily = await service.get_daily_details(date(2026, 11, 5))
                monthly = await service._fetch_month_page(2026, 11)
                self.assertEqual(parse_details.call_count, int(valid))
            self.assertEqual(daily is not None, valid)
            self.assertEqual(monthly is not None, valid)

    def test_cache_is_versioned_and_region_scoped(self) -> None:
        storage = Mock()
        storage.get_cached_text.return_value = None
        service = Dacha6Service(self.settings, Mock(), storage)
        service._get_cached_text('dacha6:folk:2026-11-05')
        key = storage.get_cached_text.call_args.args[0]
        self.assertTrue(key.startswith('region-v2:Барнаул:Алтайский край:'))
        self.assertNotEqual(key, 'dacha6:folk:2026-11-05')


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
