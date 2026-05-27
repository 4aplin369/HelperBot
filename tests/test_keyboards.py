from __future__ import annotations

import unittest
from datetime import date

from helper_bot.keyboards import BTN_CALENDAR, BTN_SOWING_DAYS, dacha_months_menu, records_months_menu


def _button_texts(markup) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


class KeyboardsTest(unittest.TestCase):
    def test_records_months_include_june_while_testing_in_may(self) -> None:
        texts = _button_texts(records_months_menu(date(2026, 5, 27)))

        self.assertIn("Май 2026", texts)
        self.assertIn("Июнь 2026", texts)

    def test_dacha_month_menus_have_distinct_buttons(self) -> None:
        calendar_texts = _button_texts(dacha_months_menu(BTN_CALENDAR, date(2026, 5, 27)))
        sowing_texts = _button_texts(dacha_months_menu(BTN_SOWING_DAYS, date(2026, 5, 27)))

        self.assertIn("Календарь: Июнь 2026", calendar_texts)
        self.assertIn("Дни для посева: Июнь 2026", sowing_texts)


if __name__ == "__main__":
    unittest.main()
