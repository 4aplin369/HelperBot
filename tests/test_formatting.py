from __future__ import annotations

import unittest

from helper_bot.formatting import long_entry_warning


class FormattingTest(unittest.TestCase):
    def test_long_entry_warning_for_telegram_limit(self) -> None:
        warning = long_entry_warning("а" * 3800)

        assert warning is not None
        self.assertIn("Telegram", warning)

    def test_long_entry_warning_for_ellipsis(self) -> None:
        warning = long_entry_warning("Починил теплицу и потом...")

        assert warning is not None
        self.assertIn("многоточием", warning)

    def test_no_warning_for_regular_entry(self) -> None:
        self.assertIsNone(long_entry_warning("Починил теплицу"))


if __name__ == "__main__":
    unittest.main()
