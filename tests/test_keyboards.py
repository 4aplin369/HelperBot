from __future__ import annotations

import unittest
from datetime import date

from helper_bot.keyboards import (
    BTN_AI_CHAT,
    BTN_AI_EXIT,
    BTN_AI_NEW_CHAT,
    BTN_CALENDAR,
    BTN_SOWING_DAYS,
    BTN_TEST,
    BTN_TEST_DIARY_REMINDER,
    BTN_TEST_DIGEST,
    BTN_TEST_WEEKLY_REVIEW,
    CALLBACK_OPEN_DIARY,
    ai_chat_menu,
    dacha_months_menu,
    diary_reminder_actions,
    main_menu,
    records_months_menu,
    test_menu,
)


def _button_texts(markup: object) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


class AdminTestMenuTest(unittest.TestCase):
    def test_admin_main_menu_has_single_test_entry(self) -> None:
        markup = main_menu(True)
        texts = _button_texts(markup)

        self.assertIn(BTN_TEST, texts)
        self.assertNotIn(BTN_TEST_DIGEST, texts)
        self.assertIn(BTN_AI_CHAT, texts)
        self.assertTrue(markup.is_persistent)

    def test_test_menu_has_all_actions(self) -> None:
        texts = _button_texts(test_menu())

        self.assertIn(BTN_TEST_DIGEST, texts)
        self.assertIn(BTN_TEST_DIARY_REMINDER, texts)
        self.assertIn(BTN_TEST_WEEKLY_REVIEW, texts)

    def test_diary_reminder_has_open_diary_inline_button(self) -> None:
        markup = diary_reminder_actions()
        button = markup.inline_keyboard[0][0]

        self.assertEqual(button.text, "📖 Открыть дневник")
        self.assertEqual(button.callback_data, CALLBACK_OPEN_DIARY)

    def test_ai_chat_menu_has_new_chat_and_exit(self) -> None:
        texts = _button_texts(ai_chat_menu())

        self.assertEqual(texts, [BTN_AI_NEW_CHAT, BTN_AI_EXIT])


class MonthKeyboardsTest(unittest.TestCase):
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
