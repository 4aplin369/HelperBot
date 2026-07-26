from __future__ import annotations

import unittest

from helper_bot.keyboards import (
    BTN_SETTINGS,
    BTN_TEST,
    BTN_TEST_DIARY_REMINDER,
    BTN_TEST_DIGEST,
    CALLBACK_OPEN_DIARY,
    diary_reminder_actions,
    main_menu,
    test_menu,
)


def _button_texts(markup: object) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.keyboard]


class AdminTestMenuTest(unittest.TestCase):
    def test_admin_main_menu_has_single_test_entry(self) -> None:
        rows = _button_texts(main_menu(True))

        self.assertIn([BTN_TEST, BTN_SETTINGS], rows)
        self.assertNotIn(BTN_TEST_DIGEST, [text for row in rows for text in row])

    def test_test_menu_has_both_actions(self) -> None:
        rows = _button_texts(test_menu())
        texts = [text for row in rows for text in row]

        self.assertIn(BTN_TEST_DIGEST, texts)
        self.assertIn(BTN_TEST_DIARY_REMINDER, texts)

    def test_diary_reminder_has_open_diary_inline_button(self) -> None:
        markup = diary_reminder_actions()
        button = markup.inline_keyboard[0][0]

        self.assertEqual(button.text, "📖 Открыть дневник")
        self.assertEqual(button.callback_data, CALLBACK_OPEN_DIARY)


if __name__ == "__main__":
    unittest.main()
