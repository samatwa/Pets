import csv
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import chat_report as chat
import dashboard_data as data
import fx_monitor as fx
import nbu_rates as nbu


class DashboardDataTests(unittest.TestCase):
    def test_comparison_uses_one_shared_date(self):
        a, b = date(2026, 10, 15), date(2026, 10, 16)
        pairs = {p: {a: Decimal("10"), b: Decimal("11")} for p in chat.PAIRS}
        del pairs["NOK/SEK"][a]
        records = data.comparison_records(pairs, a)
        self.assertEqual(len(records), len(chat.PAIRS))
        self.assertTrue(all(r["Дата"] == b and r["Изменение, %"] == 0 for r in records))

    def test_weekday_export_keeps_missing_values_empty(self):
        days = data.weekdays(date(2026, 10, 19))
        self.assertEqual(days[-2:], [date(2026, 10, 16), date(2026, 10, 19)])
        record = {"Дата": days[-1], **{p: None for p in chat.PAIRS}}
        record["NOK/SEK"] = Decimal("1.0490")
        exported = data.csv_bytes([record])
        self.assertTrue(exported.startswith(b"\xef\xbb\xbf"))
        parsed = list(csv.reader(io.StringIO(exported.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(parsed[1], ["19.10.2026", "", "", "", "1,0490", ""])

    def test_read_only_snapshot_and_rejected_refresh(self):
        raw = (Path(__file__).parent / "fixtures/norges_bank_with_sek_2026-10-16.json").read_text(encoding="utf-8")
        rates = fx.parse_sdmx(raw)
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "rates.sqlite3"
            db = fx.connect(db_path)
            fx.save(db, rates, "test")
            db.close()
            with patch.object(data, "DB_PATH", db_path):
                snapshot = data.read_snapshot()
                self.assertEqual(snapshot.rows, rates)
                with patch.object(fx, "fetch", return_value=raw.replace('"SEK"', '"XYZ"')):
                    with self.assertRaises(fx.DataError):
                        data.refresh_history()
                self.assertEqual(data.read_snapshot().rows, rates)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.db_path = self.root / "data/rates.sqlite3"
        fixtures = Path(__file__).parent / "fixtures"
        self.raw = (fixtures / "norges_bank_with_sek_2026-10-16.json").read_text(encoding="utf-8")
        self.nbu_raw = (fixtures / "nbu_nok_2026-10.json").read_text(encoding="utf-8")
        self.now = 1000.0
        self.clock = datetime.fromisoformat("2026-10-23T18:00:00+02:00")
        for patcher in (
            patch.object(data, "DB_PATH", self.db_path),
            patch.object(fx, "ROOT", self.root),
            patch.object(fx, "oslo_now", side_effect=lambda: self.clock),
            patch.object(data.time, "monotonic", side_effect=lambda: self.now),
            patch.object(data, "_last_refresh", None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.fetcher = patch.object(fx, "fetch", side_effect=lambda url, **kwargs:
                                    self.nbu_raw if "bank.gov.ua" in url else self.raw)
        self.fetch = self.fetcher.start()
        self.addCleanup(self.fetcher.stop)

    def test_concurrent_visitors_share_one_download_and_saved_snapshot(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: data.refresh_history(), range(4)))
        self.assertEqual(self.fetch.call_count, 2)  # One request per bank.
        urls = [call.args[0] for call in self.fetch.call_args_list]
        self.assertTrue(any("startPeriod=2023-" in url for url in urls))
        self.assertTrue(any("start=2023" in url for url in urls))
        self.assertTrue(results[0].rows)
        self.assertEqual(results[0].uah_values[date(2026, 10, 23)], Decimal("4.8068"))
        self.assertTrue(all(snapshot == results[0] for snapshot in results))

    def test_refresh_interval_expires_and_missing_database_is_rebuilt(self):
        first = data.refresh_history()
        self.now += data.REFRESH_INTERVAL - 1
        self.assertEqual(data.refresh_history(), first)
        self.assertEqual(self.fetch.call_count, 2)
        self.now += 1
        data.refresh_history()
        self.assertEqual(self.fetch.call_count, 4)
        self.db_path.unlink()
        self.assertEqual(data.refresh_history().rows, first.rows)
        self.assertEqual(self.fetch.call_count, 6)

    def test_failures_back_off_and_retry_without_losing_error_type(self):
        self.fetch.side_effect = fx.DataError("Invalid source data")
        for _ in range(2):
            with self.assertRaisesRegex(fx.DataError, "Invalid source data"):
                data.refresh_history()
        self.assertEqual(self.fetch.call_count, 1)
        self.now += data.RETRY_INTERVAL
        self.fetch.side_effect = lambda url, **kwargs: self.nbu_raw if "bank.gov.ua" in url else self.raw
        self.assertTrue(data.refresh_history().rows)
        self.assertEqual(self.fetch.call_count, 3)

    def test_new_day_or_different_history_period_triggers_download(self):
        data.refresh_history()
        data.refresh_history(days=400)
        self.assertEqual(self.fetch.call_count, 4)
        self.clock = datetime.fromisoformat("2026-10-24T00:01:00+02:00")
        data.refresh_history(days=400)
        self.assertEqual(self.fetch.call_count, 6)

    def test_nbu_failure_keeps_norges_update_and_previous_uah(self):
        db = fx.connect(self.db_path)
        try:
            nbu.save(db, {date(2026, 10, 22): Decimal("4.7")}, "saved")
        finally:
            db.close()
        def fetch(url, **kwargs):
            if "bank.gov.ua" in url:
                raise fx.MonitorError("NBU offline")
            return self.raw
        self.fetch.side_effect = fetch
        for _ in range(2):
            with self.assertRaisesRegex(fx.MonitorError, "Norges Bank обновлён"):
                data.refresh_history()
        self.assertEqual(self.fetch.call_count, 2)
        snapshot = data.read_snapshot()
        self.assertEqual(snapshot.rows, fx.parse_sdmx(self.raw))
        self.assertEqual(snapshot.uah_values, {date(2026, 10, 22): Decimal("4.7")})


if __name__ == "__main__":
    unittest.main()
