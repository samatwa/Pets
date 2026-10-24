import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import chat_report as chat
import fx_monitor as fx
import nbu_rates as nbu

FIXTURE = Path(__file__).parent / "fixtures/nbu_nok_2026-10.json"


class NBUTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_text(encoding="utf-8")
        self.start, self.end = date(2026, 10, 12), date(2026, 10, 23)

    def test_official_rate_is_uah_per_one_nok(self):
        values = nbu.parse(self.raw, self.start, self.end)
        self.assertEqual(values[self.end], Decimal("4.8068"))
        self.assertEqual(len(values), 12)

    def test_dates_currency_and_units_are_validated(self):
        for field, bad in [("cc", "USD"), ("units", 0), ("rate_per_unit", "NaN"),
                           ("rate_per_unit", "99"), ("exchangedate", "24.10.2026")]:
            with self.subTest(field=field, value=bad):
                rows = json.loads(self.raw)
                rows[-1][field] = bad
                with self.assertRaises(fx.DataError):
                    nbu.parse(json.dumps(rows), self.start, self.end)

    def test_conflicting_duplicates_and_empty_payload(self):
        rows = json.loads(self.raw)
        changed = dict(rows[-1], rate=5, rate_per_unit=5)
        with self.assertRaises(fx.DataError):
            nbu.parse(json.dumps(rows + [changed]), self.start, self.end)
        with self.assertRaises(fx.NoDataError):
            nbu.parse("[]", self.start, self.end)

    def test_nbu_storage_preserves_norges_history_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            db = fx.connect(Path(folder) / "rates.sqlite3")
            try:
                base = [fx.Rate("USD", self.end, Decimal("9.36")),
                        fx.Rate("EUR", self.end, Decimal("10.48"))]
                fx.save(db, base, "Norges")
                values = nbu.parse(self.raw, self.start, self.end)
                nbu.save(db, values, "NBU")
                nbu.save(db, values, "NBU")
                self.assertEqual(nbu.load(db), values)
                self.assertEqual(len(fx.load(db)), 2)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM nbu_nok_rates").fetchone()[0], 12)
            finally:
                db.close()

    def test_nbu_weekends_are_not_compared_as_working_days(self):
        values = nbu.parse(self.raw, self.start, self.end)
        pairs = chat.pair_values([], values)
        self.assertNotIn(date(2026, 10, 18), pairs["NOK/UAH"])
        self.assertEqual(pairs["NOK/UAH"][date(2026, 10, 19)], Decimal("4.7544"))


if __name__ == "__main__":
    unittest.main()
