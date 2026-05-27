from __future__ import annotations

import unittest
from datetime import date

from helper_bot.dacha6_service import _month_days_text, _parse_day


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


if __name__ == "__main__":
    unittest.main()
