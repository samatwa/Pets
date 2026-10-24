import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import fx_monitor as fx
import chat_report as chat


class ChatReportTests(unittest.TestCase):
    def setUp(self):
        self.raw = (Path(__file__).parent / "fixtures/norges_bank_with_sek_2026-10-16.json").read_text(encoding="utf-8")
        self.rows = fx.parse_sdmx(self.raw)

    def test_sek_units_storage_and_inverse(self):
        sek = next(r for r in self.rows if r.currency == "SEK" and r.day == date(2026, 10, 16))
        self.assertEqual(sek.value, Decimal("0.9533"))
        self.assertEqual(format(chat.pair_values(self.rows)["NOK/SEK"][sek.day], ".4f"), "1.0490")
        with tempfile.TemporaryDirectory() as root:
            db = fx.connect(Path(root) / "rates.sqlite3")
            try:
                fx.save(db, self.rows, "fixture")
                fx.save(db, self.rows, "fixture")
                self.assertEqual(len(fx.load(db)), len(self.rows))
                self.assertIn(sek, fx.load(db))
            finally:
                db.close()

    def test_cross_rates_never_mix_dates(self):
        rows = [fx.Rate("USD", date(2026, 10, 15), Decimal("10")),
                fx.Rate("EUR", date(2026, 10, 15), Decimal("5")),
                fx.Rate("USD", date(2026, 10, 16), Decimal("99"))]
        values = chat.pair_values(rows)
        self.assertEqual(values["USD/EUR"], {date(2026, 10, 15): Decimal("2")})

    def test_four_pairs_changes_and_seven_weekdays(self):
        text, data = chat.build_report(self.rows, date(2026, 10, 16))
        self.assertEqual(len(data["summary"]), 4)
        self.assertEqual(len(data["week"]), 7)
        self.assertEqual([r["date"] for r in data["week"]],
                         ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"])
        sek = data["summary"][-1]
        self.assertEqual(format(Decimal(sek["change"]), "+.4f"), "-0.0002")
        self.assertEqual(format(Decimal(sek["change_pct"]), "+.2f"), "-0.02")
        self.assertLess(text.index("| NOK/SEK |"), text.index("| Дата |"))

    def test_missing_and_offline_dates(self):
        filtered = [r for r in self.rows if r.currency != "SEK" or r.day != date(2026, 10, 16)]
        _, data = chat.build_report(filtered, date(2026, 10, 16))
        self.assertIsNone(data["week"][-1]["NOK/SEK"])
        self.assertEqual(data["summary"][-1]["date"], "2026-10-15")
        text, _ = chat.build_report(filtered, date(2026, 10, 16), offline=True)
        self.assertIn("нет данных", text)
        self.assertNotIn("нет публикации", text)


if __name__ == "__main__":
    unittest.main()
