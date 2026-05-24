from __future__ import annotations

import unittest

from helper_bot.dacha6_service import _parse_sowing_days


class SowingDaysParserTest(unittest.TestCase):
    def test_parse_sowing_days_table(self) -> None:
        html = """
        <table class="tb2_1">
          <tr><td>Культура</td><td>Благоприятные дни для посева</td></tr>
          <tr><td>Зелень и салаты</td><td><span>1</span>, 3, <b>6</b></td></tr>
          <tr><td>Томаты</td><td>1, 3, 6</td></tr>
        </table>
        """

        self.assertEqual(
            _parse_sowing_days(html),
            [("Зелень и салаты", "1, 3, 6"), ("Томаты", "1, 3, 6")],
        )


if __name__ == "__main__":
    unittest.main()
