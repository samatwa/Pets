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

    def test_sek_units_storage_and_nok_direction(self):
        sek = next(r for r in self.rows if r.currency == "SEK" and r.day == date(2026, 10, 16))
        self.assertEqual(sek.value, Decimal("0.9533"))
        self.assertEqual(format(chat.pair_values(self.rows)["SEK/NOK"][sek.day], ".4f"), "0.9533")
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

    def test_pln_units_storage_and_report(self):
        raw = (Path(__file__).parent / "fixtures/norges_bank_with_pln_2026-10-16.json").read_text(encoding="utf-8")
        rows = fx.parse_sdmx(raw)
        pln = next(r for r in rows if r.currency == "PLN" and r.day == date(2026, 10, 16))
        self.assertEqual(pln.value, Decimal("2.5100"))
        with tempfile.TemporaryDirectory() as root:
            db = fx.connect(Path(root) / "rates.sqlite3")
            try:
                fx.save(db, self.rows, "old history")
                fx.save(db, rows, "fixture")
                fx.save(db, rows, "fixture")
                self.assertEqual(fx.load(db), rows)
                text, report = chat.build_report(fx.load(db), pln.day)
                item = next(r for r in report["summary"] if r["pair"] == "PLN/NOK")
                self.assertEqual(Decimal(item["change"]), Decimal("0.0100"))
                self.assertEqual(report["week"][-1]["PLN/NOK"], "2.5100")
                self.assertIn("| PLN/NOK | 2.5100 NOK |", text)
            finally:
                db.close()
        payload = json.loads(raw)
        payload["data"]["dataSets"][0]["series"]["0:3:0:0"]["attributes"][2] = 1
        with self.assertRaisesRegex(fx.DataError, "Unexpected UNIT_MULT for PLN"):
            fx.parse_sdmx(json.dumps(payload))

    def test_four_pairs_changes_and_seven_weekdays(self):
        text, data = chat.build_report(self.rows, date(2026, 10, 16))
        self.assertEqual(len(data["summary"]), 4)
        self.assertEqual(len(data["week"]), 7)
        self.assertEqual([r["date"] for r in data["week"]],
                         ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"])
        sek = next(item for item in data["summary"] if item["pair"] == "SEK/NOK")
        self.assertEqual(format(Decimal(sek["change"]), "+.4f"), "+0.0002")
        self.assertEqual(format(Decimal(sek["change_pct"]), "+.2f"), "+0.02")
        self.assertLess(text.index("| SEK/NOK |"), text.index("| Date |"))

    def test_missing_and_offline_dates(self):
        filtered = [r for r in self.rows if r.currency != "SEK" or r.day != date(2026, 10, 16)]
        _, data = chat.build_report(filtered, date(2026, 10, 16))
        self.assertIsNone(data["week"][-1]["SEK/NOK"])
        self.assertEqual(next(item for item in data["summary"] if item["pair"] == "SEK/NOK")["date"], "2026-10-15")
        text, _ = chat.build_report(filtered, date(2026, 10, 16), offline=True)
        self.assertIn("no data", text)
        self.assertNotIn("no publication", text)


if __name__ == "__main__":
    unittest.main()
