import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit.testing.v1 import AppTest

import dashboard_data as data
import fx_monitor as fx
import nbu_rates as nbu
import chat_report as chat

ROOT = Path(__file__).resolve().parents[1]


class DashboardUITests(unittest.TestCase):
    def setUp(self):
        raw = (ROOT / "tests/fixtures/norges_bank_with_sek_2026-10-16.json").read_text(encoding="utf-8")
        uah_raw = (ROOT / "tests/fixtures/nbu_nok_2026-10.json").read_text(encoding="utf-8")
        uah = nbu.parse(uah_raw, date(2026, 10, 12), date(2026, 10, 23))
        uah = {d: v for d, v in uah.items() if d <= date(2026, 10, 16)}
        self.snapshot = data.Snapshot(fx.parse_sdmx(raw), "2026-10-16T16:07:00+00:00", uah)
        self.clock = patch.object(fx, "oslo_now", return_value=datetime(2026, 10, 16, 18, tzinfo=ZoneInfo("Europe/Oslo")))
        self.loader = patch.object(data, "read_snapshot", return_value=self.snapshot)
        # The real database is absent on a clean checkout; all app data is mocked.
        self.database = patch.object(data, "DB_PATH", ROOT / "tests/fixtures/nbu_nok_2026-10.json")
        self.clock.start()
        self.loader.start()
        self.database.start()
        st.cache_data.clear()

    def tearDown(self):
        self.loader.stop()
        self.clock.stop()
        self.database.stop()
        st.cache_data.clear()

    def app(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        return app

    def test_quotes_and_ten_day_table(self):
        app = self.app()
        self.assertEqual([m.label for m in app.metric[:4]], ["USD/NOK", "EUR/NOK", "USD/EUR", "NOK/SEK"])
        self.assertEqual([m.value for m in app.metric[:4]], ["9.4410", "10.6240", "0.8886", "1.0490"])
        table = app.dataframe[0].value
        self.assertEqual(len(table), 10)
        self.assertTrue(any("Last 10 business days" == h.value for h in app.subheader))
        self.assertEqual(table.iloc[-1]["NOK/SEK"], "1.0490")
        self.assertEqual(app.metric[4].label, "NOK/UAH")
        self.assertEqual(app.metric[4].value, format(self.snapshot.uah_values[date(2026, 10, 16)], ".4f"))
        self.assertIn("observations", app.metric[0].help)
        self.assertTrue(any("latest 7 published" in c.value for c in app.caption))
        self.assertFalse(any("Latest 12" in c.value for c in app.caption))

    def test_header_clocks_show_local_time_and_follow_language(self):
        app = self.app()
        captions = [caption.value for caption in app.caption]
        self.assertIn("Norges Bank · NBU", captions)
        self.assertIn("Oslo · 18:00:00", captions)
        self.assertIn("Kyiv · 19:00:00", captions)
        app.get_by_key("language").set_value("ru").run()
        self.assertFalse(app.exception)
        self.assertIn("Осло · 18:00:00", [caption.value for caption in app.caption])
        self.assertIn("Киев · 19:00:00", [caption.value for caption in app.caption])
        with patch.object(fx, "oslo_now", return_value=datetime.fromisoformat("2026-12-16T22:30:45+00:00")):
            app.run()
        self.assertFalse(app.exception)
        captions = [caption.value for caption in app.caption]
        self.assertIn("Осло · 23:30:45", captions)
        self.assertIn("Киев · 00:30:45", captions)

    def test_unsupported_streamlit_version_shows_install_instructions(self):
        with patch.object(st, "__version__", "1.41.1"):
            app = self.app()
        self.assertTrue(app.error)
        self.assertIn("requires Streamlit 1.66.1 or newer", app.error[0].value)
        self.assertIn("python -m streamlit run streamlit_app.py", app.error[0].value)

    def test_inverse_converter_and_comparison_chart(self):
        app = self.app()
        app.button(key="swap_direction").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[-1].value, "953.30")
        app.toggle(key="compare").set_value(True).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Published observations only" in item.value for item in app.markdown))
        app.selectbox(key="convert_from").select("EUR").run()
        app.selectbox(key="convert_to").select("USD").run()
        self.assertFalse(app.exception)
        self.assertIn("USD", app.metric[-1].label)
        app.button(key="swap_direction").click().run()
        self.assertFalse(app.exception)
        self.assertIn("EUR", app.metric[-1].label)
        self.assertEqual(app.number_input(key="amount").value, 1000.0)

    def test_repeated_swaps_keep_both_currencies_and_converter_visible(self):
        app = self.app()
        self.assertEqual(app.selectbox(key="convert_from").value, "NOK")
        self.assertEqual(app.selectbox(key="convert_to").value, "SEK")
        with patch.object(data, "refresh_history") as refresh:
            for press in range(1, 13):
                with self.subTest(press=press):
                    app.button(key="swap_direction").click().run()
                    self.assertFalse(app.exception)
                    source, target = ("SEK", "NOK") if press % 2 else ("NOK", "SEK")
                    self.assertEqual(app.selectbox(key="convert_from").value, source)
                    self.assertEqual(app.selectbox(key="convert_to").value, target)
                    self.assertTrue(app.number_input(key="amount").label.endswith(source))
                    self.assertEqual(app.number_input(key="amount").value, 1000.0)
                    self.assertTrue(app.metric[-1].label.endswith(target))
                    self.assertEqual(app.metric[-1].value, "953.30" if press % 2 else "1,048.99")
                    self.assertEqual(len(app.dataframe), 1)
            refresh.assert_not_called()

    def test_source_selection_keeps_a_supported_target_and_swaps_uah(self):
        app = self.app()
        app.selectbox(key="convert_from").select("UAH").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_to").options, ["NOK"])
        self.assertEqual(app.selectbox(key="convert_to").value, "NOK")
        app.button(key="swap_direction").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_from").value, "NOK")
        self.assertEqual(app.selectbox(key="convert_to").value, "UAH")
        self.assertTrue(app.metric[-1].label.endswith("UAH"))
        app.selectbox(key="convert_from").select("USD").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_to").value, "NOK")
        app.selectbox(key="convert_to").select("EUR").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.metric[-1].label.endswith("EUR"))

    def test_existing_or_empty_old_pair_state_migrates_to_currency_fields(self):
        for previous, reverse, expected in [("NOK/SEK", True, ("SEK", "NOK")),
                                             (None, False, ("NOK", "SEK"))]:
            with self.subTest(previous=previous):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
                app.session_state["convert_pair"] = previous
                app.session_state["reverse"] = reverse
                app.run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="convert_from").value, expected[0])
                self.assertEqual(app.selectbox(key="convert_to").value, expected[1])
                app.button(key="swap_direction").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="convert_from").value, expected[1])
                self.assertEqual(app.selectbox(key="convert_to").value, expected[0])

    def test_cards_keep_only_unit_and_date_captions(self):
        app = self.app()
        app.get_by_key("language").set_value("ru").run()
        captions = [caption.value for caption in app.get_by_key("quote_cards").get("caption")]
        self.assertEqual(len(captions), 5)
        self.assertEqual(captions[-1], "UAH за 1 NOK · 16.10.2026")
        self.assertIn("Сравнение с", app.metric[4].help)
        self.assertIn("Источник: НБУ", app.metric[4].help)

    def test_refresh_shows_updated_values_in_the_same_run(self):
        app = self.app()
        latest = date(2026, 10, 16)
        rows = [fx.Rate(row.currency, row.day, fx.Decimal("10")
                        if row.currency == "USD" and row.day == latest else row.value)
                for row in self.snapshot.rows]
        updated = data.Snapshot(rows, "2026-10-16T17:00:00+00:00", self.snapshot.uah_values)
        with patch.object(data, "refresh_history", return_value=updated) as refresh:
            app.button(key="refresh").click().run()
        self.assertFalse(app.exception)
        refresh.assert_called_once_with()
        self.assertEqual(app.metric[0].value, "10.0000")

    def test_comparison_shows_percent_and_restores_the_single_pair_scale(self):
        app = self.app()
        for scale in ("rate", "percent"):
            with self.subTest(scale=scale):
                app.get_by_key("chart_scale").set_value(scale).run()
                app.toggle(key="compare").set_value(True).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.get_by_key("chart_scale").value, "percent")
                self.assertTrue(app.get_by_key("chart_scale").disabled)
                self.assertTrue(app.get_by_key("chart_pair").disabled)
                app.get_by_key("language").set_value("ru").run()
                self.assertEqual(app.get_by_key("chart_scale").value, "percent")
                app.toggle(key="compare").set_value(False).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.get_by_key("chart_scale").value, scale)
                self.assertFalse(app.get_by_key("chart_pair").disabled)

    def test_optional_mini_charts_do_not_change_quotes_or_fetch_data(self):
        app = self.app()
        original = [metric.value for metric in app.metric]
        with patch.object(data, "refresh_history") as refresh:
            app.toggle(key="show_mini").set_value(True).run()
            self.assertFalse(app.exception)
            self.assertEqual([metric.value for metric in app.metric], original)
            app.toggle(key="show_mini").set_value(False).run()
            self.assertFalse(app.exception)
            self.assertEqual([metric.value for metric in app.metric], original)
            refresh.assert_not_called()

    def test_failed_refresh_retains_quotes(self):
        app = self.app()
        with patch.object(data, "refresh_history", side_effect=fx.MonitorError("Test API offline")):
            app.button(key="refresh").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertIn("source is unavailable", app.warning[0].value)
        self.assertEqual(app.metric[0].value, "9.4410")

    def test_first_launch_downloads_once_and_reuses_returned_snapshot(self):
        missing = ROOT / "__test_missing_rates__.sqlite3"
        with patch.object(data, "DB_PATH", missing), patch.object(
                data, "refresh_history", return_value=self.snapshot) as refresh:
            data.read_snapshot.reset_mock()
            app = self.app()
            refresh.assert_called_once_with()
            data.read_snapshot.assert_not_called()
            self.assertEqual(app.metric[0].value, "9.4410")
            app.get_by_key("language").set_value("ru").run()
            self.assertFalse(app.exception)
            refresh.assert_called_once_with()

    def test_initial_failure_does_not_retry_on_filter_or_language_changes(self):
        missing = ROOT / "__test_missing_rates__.sqlite3"
        with patch.object(data, "DB_PATH", missing), patch.object(
                data, "read_snapshot", return_value=data.Snapshot([], None)), patch.object(
                data, "refresh_history", side_effect=fx.MonitorError("API offline")) as refresh:
            app = self.app()
            self.assertTrue(app.warning)
            self.assertFalse(app.metric)
            app.get_by_key("language").set_value("ru").run()
            self.assertFalse(app.exception)
            refresh.assert_called_once_with()
            app.button(key="refresh").click().run()
            self.assertEqual(refresh.call_count, 2)

    def test_snapshot_cache_expires_when_oslo_date_changes(self):
        data.read_snapshot.reset_mock()
        app = self.app()
        app.run()
        self.assertEqual(data.read_snapshot.call_count, 1)
        with patch.object(fx, "oslo_now", return_value=datetime(
                2026, 10, 19, 0, 1, tzinfo=ZoneInfo("Europe/Oslo"))):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(data.read_snapshot.call_count, 2)

    def test_chart_unit_switch_and_pair_selection(self):
        app = self.app()
        app.get_by_key("chart_scale").set_value("percent").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Y axis is in percent" in c.value for c in app.caption))
        app.get_by_key("chart_pair").set_value("NOK/SEK").run()
        self.assertFalse(app.exception)
        app.get_by_key("chart_scale").set_value("rate").run()
        self.assertFalse(app.exception)
        self.assertFalse(any("rather than starting at zero" in c.value for c in app.caption))

    def test_three_year_period_includes_older_quotes_and_filters_earlier_dates(self):
        included, excluded = date(2024, 2, 29), date(2023, 10, 15)
        rows = self.snapshot.rows + [
            fx.Rate(currency, day, fx.Decimal(value)) for day in (excluded, included)
            for currency, value in (("USD", "8"), ("EUR", "10"), ("SEK", "1"))]
        uah = {**self.snapshot.uah_values, included: fx.Decimal("4"), excluded: fx.Decimal("4")}
        extended = data.Snapshot(rows, self.snapshot.loaded_at, uah)
        with patch.object(data, "read_snapshot", return_value=extended), patch.object(data, "refresh_history") as refresh:
            app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
            app.session_state["period"] = "all"
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.get_by_key("period").value, "3y")
            app.get_by_key("period").set_value("3y").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("29.02.2024 — 16.10.2026" in item.value for item in app.markdown))
            app.toggle(key="compare").set_value(True).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("29.02.2024 — 16.10.2026" in item.value for item in app.markdown))
            app.get_by_key("language").set_value("ru").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.get_by_key("period").value, "3y")
            self.assertIn("3 года", app.get_by_key("period").options)
            self.assertNotIn("Всё", app.get_by_key("period").options)
            refresh.assert_not_called()


    def test_language_switch_preserves_filters_converter_and_does_not_refresh(self):
        app = self.app()
        app.get_by_key("period").set_value("3m").run()
        app.get_by_key("chart_pair").set_value("NOK/UAH").run()
        app.get_by_key("chart_scale").set_value("percent").run()
        app.selectbox(key="convert_from").select("USD").run()
        app.selectbox(key="convert_to").select("EUR").run()
        app.button(key="swap_direction").click().run()
        app.number_input(key="amount").set_value(2500.0).run()
        before = app.metric[-1].value
        with patch.object(data, "refresh_history") as refresh:
            app.get_by_key("language").set_value("nb").run()
            self.assertFalse(app.exception)
            refresh.assert_not_called()
            self.assertEqual(app.title[0].value, "Valutaoversikt")
            self.assertEqual(app.button(key="refresh").label, "Oppdater kurser")
            self.assertEqual(app.metric[0].value, "9,4410")
            self.assertEqual(app.get_by_key("period").value, "3m")
            self.assertEqual(app.get_by_key("chart_pair").value, "NOK/UAH")
            self.assertEqual(app.get_by_key("chart_scale").value, "percent")
            self.assertEqual(app.selectbox(key="convert_from").value, "EUR")
            self.assertEqual(app.selectbox(key="convert_to").value, "USD")
            self.assertEqual(app.number_input(key="amount").value, 2500.0)
            self.assertEqual(app.metric[-1].value.replace(" ", "").replace(",", "."), before.replace(",", ""))
            self.assertEqual(app.dataframe[0].value.columns[0], "Dato")
            app.get_by_key("language").set_value("ru").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "Валютный обзор")
            self.assertEqual(app.button(key="refresh").label, "Обновить курсы")
            self.assertEqual(app.metric[0].value, "9,4410")
            self.assertEqual(app.dataframe[0].value.columns[0], "Дата")
            self.assertEqual(app.get_by_key("period").value, "3m")
            self.assertEqual(app.get_by_key("chart_pair").value, "NOK/UAH")
            self.assertEqual(app.get_by_key("chart_scale").value, "percent")
            self.assertEqual(app.number_input(key="amount").value, 2500.0)
            app.get_by_key("language").set_value("en").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "Currency overview")
            self.assertEqual(app.metric[0].value, "9.4410")
            self.assertEqual(app.metric[-1].value, before)
            self.assertEqual(app.dataframe[0].value.columns[0], "Date")
            refresh.assert_not_called()

    def test_offline_warning_changes_language_without_losing_quotes(self):
        app = self.app()
        with patch.object(data, "refresh_history", side_effect=fx.MonitorError("API offline")):
            app.button(key="refresh").click().run()
        app.get_by_key("language").set_value("nb").run()
        self.assertFalse(app.exception)
        self.assertIn("Kurskilden er utilgjengelig", app.warning[0].value)
        self.assertEqual(app.metric[0].value, "9,4410")


if __name__ == "__main__":
    unittest.main()
