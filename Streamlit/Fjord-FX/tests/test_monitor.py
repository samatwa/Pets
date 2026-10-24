import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import fx_monitor as fx

FIXTURE = Path(__file__).parent / "fixtures/norges_bank_2026-10-15.json"
RAW = FIXTURE.read_text(encoding="utf-8")


class ParserTests(unittest.TestCase):
    def test_real_bank_response_and_precision(self):
        rates = fx.parse_sdmx(RAW)
        self.assertEqual(len(rates), 4)
        self.assertEqual(next(r.value for r in rates if r.currency == "USD" and r.day.day == 14),
                         Decimal("9.4716"))

    def test_dimension_order_is_not_hardcoded(self):
        doc = json.loads(RAW)
        dims = doc["data"]["structure"]["dimensions"]["series"]
        dims[0], dims[1] = dims[1], dims[0]
        series = doc["data"]["dataSets"][0]["series"]
        series["1:0:0:0"] = series.pop("0:1:0:0")
        self.assertEqual(fx.parse_sdmx(json.dumps(doc)), fx.parse_sdmx(RAW))

    def test_missing_currency_is_rejected(self):
        doc = json.loads(RAW)
        del doc["data"]["dataSets"][0]["series"]["0:1:0:0"]
        with self.assertRaises(fx.DataError):
            fx.parse_sdmx(json.dumps(doc))

    def test_bad_unit_is_rejected(self):
        doc = json.loads(RAW)
        doc["data"]["structure"]["attributes"]["series"][2]["values"][0]["id"] = "2"
        with self.assertRaises(fx.DataError):
            fx.parse_sdmx(json.dumps(doc))

    def test_null_is_skipped_not_zero(self):
        doc = json.loads(RAW)
        doc["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]["1"] = [None]
        self.assertEqual(len(fx.parse_sdmx(json.dumps(doc))), 3)

    def test_invalid_values_and_indices(self):
        for value in ["NaN", "Infinity", "-1", "0", "not-a-number"]:
            with self.subTest(value=value):
                doc = json.loads(RAW)
                doc["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]["1"] = [value]
                with self.assertRaises(fx.DataError):
                    fx.parse_sdmx(json.dumps(doc))
        doc = json.loads(RAW)
        doc["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]["-1"] = ["9"]
        with self.assertRaises(fx.DataError):
            fx.parse_sdmx(json.dumps(doc))

    def test_empty_and_malformed(self):
        for raw in ["<html>Unavailable</html>", "[]", "{}"]:
            with self.subTest(raw=raw), self.assertRaises(fx.DataError):
                fx.parse_sdmx(raw)
        doc = json.loads(RAW)
        doc["data"]["dataSets"] = []
        with self.assertRaises(fx.NoDataError):
            fx.parse_sdmx(json.dumps(doc))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = fx.connect(self.root / "rates.sqlite3")
        self.rates = fx.parse_sdmx(RAW)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_rerun_and_revision(self):
        fx.save(self.db, self.rates, "fixture")
        fx.save(self.db, self.rates, "fixture")
        self.assertEqual(len(fx.load(self.db)), 4)
        revised = fx.Rate("USD", date(2026, 10, 14), Decimal("9.4001"))
        fx.save(self.db, [revised], "revision")
        self.assertEqual(len(fx.load(self.db)), 4)
        self.assertIn(revised, fx.load(self.db))

    def test_previous_observation_and_weekend(self):
        fx.save(self.db, self.rates, "fixture")
        text, data = fx.report(self.db, date(2026, 10, 18))
        usd = data["rates"][0]
        self.assertEqual(usd["previous_date"], "2026-10-13")
        self.assertEqual(usd["change"], "-0.0641")
        self.assertEqual(usd["age_days"], 4)
        self.assertIn("нового значения нет", text)
        self.assertIn("-0.67", text)

    def test_export_range_and_empty_report(self):
        with self.assertRaises(fx.NoDataError):
            fx.report(self.db, date(2026, 10, 15))
        fx.save(self.db, self.rates, "fixture")
        target = self.root / "export.csv"
        fx.export_csv(self.db, target, date(2026, 10, 14), date(2026, 10, 14))
        self.assertEqual(len(target.read_text(encoding="utf-8-sig").splitlines()), 3)


class TransportTests(unittest.TestCase):
    def test_latest_and_history_query(self):
        url = fx.make_url(last=2, end=date(2026, 10, 15))
        self.assertIn("B.USD+EUR+SEK.NOK.SP", url)
        self.assertEqual(parse_qs(urlsplit(url).query)["lastNObservations"], ["2"])
        query = parse_qs(urlsplit(fx.make_url(start=date(2026, 1, 1), end=date(2026, 10, 14))).query)
        self.assertEqual(query["startPeriod"], ["2026-01-01"])
        self.assertEqual(query["endPeriod"], ["2026-10-14"])

    @patch.object(fx.time, "sleep")
    @patch.object(fx, "urlopen")
    def test_retry_then_real_payload(self, open_mock, sleep_mock):
        response = open_mock.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = RAW.encode()
        open_mock.side_effect = [URLError("temporary"), open_mock.return_value]
        self.assertEqual(len(fx.parse_sdmx(fx.fetch(fx.make_url(last=2)))), 4)
        self.assertEqual(open_mock.call_count, 2)
        sleep_mock.assert_called_once()

    @patch.object(fx.time, "sleep")
    @patch.object(fx, "urlopen")
    def test_429_and_503_retry(self, open_mock, sleep_mock):
        open_mock.side_effect = [HTTPError("url", 429, "limit", {"Retry-After": "0"}, None),
                                HTTPError("url", 503, "unavailable", {}, None)]
        with self.assertRaises(fx.MonitorError):
            fx.fetch(fx.ENDPOINT, attempts=2)
        self.assertEqual(open_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0)

    @patch.object(fx, "urlopen")
    def test_400_no_retry_and_204_no_data(self, open_mock):
        open_mock.side_effect = HTTPError("url", 400, "bad query", {}, None)
        with self.assertRaises(fx.MonitorError):
            fx.fetch(fx.ENDPOINT)
        self.assertEqual(open_mock.call_count, 1)
        open_mock.side_effect = None
        open_mock.return_value.__enter__.return_value.status = 204
        with self.assertRaises(fx.NoDataError):
            fx.fetch(fx.ENDPOINT)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.options = ["--db", str(self.root / "rates.sqlite3"), "--output-dir", str(self.root)]

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, args):
        with redirect_stdout(io.StringIO()) as out:
            status = fx.main(self.options + args)
        return status, out.getvalue()

    def test_import_and_failure_preserve_data(self):
        args = ["latest", "--input-json", str(FIXTURE)]
        self.assertEqual(self.run_cli(args)[0], 0)
        self.assertEqual(self.run_cli(args)[0], 0)
        with patch.object(fx, "fetch", side_effect=fx.MonitorError("network down")):
            status, text = self.run_cli(["latest"])
        self.assertEqual(status, 1)
        self.assertIn("network down", text)
        self.assertTrue((self.root / "last_error_report.md").exists())
        with closing(sqlite3.connect(self.root / "rates.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM rates").fetchone()[0], 4)

    def test_history_range_import(self):
        status, _ = self.run_cli(["history", "--start", "2026-10-13", "--end", "2026-10-14",
                                  "--input-json", str(FIXTURE)])
        self.assertEqual(status, 0)
        status, _ = self.run_cli(["history", "--start", "2026-10-14", "--end", "2026-10-14",
                                  "--input-json", str(FIXTURE)])
        self.assertEqual(status, 1)

    def test_partial_payload_does_not_write_rates(self):
        bad = json.loads(RAW)
        del bad["data"]["dataSets"][0]["series"]["0:1:0:0"]
        with patch.object(fx, "fetch", return_value=json.dumps(bad)):
            self.assertEqual(self.run_cli(["latest"])[0], 1)
        with closing(sqlite3.connect(self.root / "rates.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM rates").fetchone()[0], 0)

    def test_future_period_rejected(self):
        self.assertEqual(self.run_cli(["history", "--start", "2099-01-01", "--end", "2099-01-02"])[0], 1)


if __name__ == "__main__":
    unittest.main()
