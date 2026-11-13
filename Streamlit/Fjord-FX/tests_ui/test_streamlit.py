import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit.testing.v1 import AppTest

import dashboard_data as data
import dashboard_charts as charts
import fx_monitor as fx
import nbu_rates as nbu
import chat_report as chat

ROOT = Path(__file__).resolve().parents[1]


class DashboardUITests(unittest.TestCase):
    def setUp(self):
        raw = (ROOT / "tests/fixtures/norges_bank_with_pln_2026-10-16.json").read_text(encoding="utf-8")
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
        self.assertEqual([m.label for m in app.metric[:6]], ["USD/NOK", "EUR/NOK", "SEK/NOK", "UAH/NOK", "PLN/NOK", "USD/EUR"])
        self.assertEqual([app.metric[i].value for i in (0, 1, 2, 5)], ["9.4410", "10.6240", "0.9533", "0.8886"])
        table = app.dataframe[0].value
        self.assertEqual(len(table), 10)
        self.assertTrue(any("Last 10 business days" == h.value for h in app.subheader))
        self.assertEqual(table.iloc[-1]["SEK/NOK"], "0.9533")
        self.assertEqual(app.metric[3].label, "UAH/NOK")
        self.assertEqual(app.metric[3].value, format(fx.Decimal(1) / self.snapshot.uah_values[date(2026, 10, 16)], ".4f"))
        self.assertIn("observations", app.metric[0].help)
        self.assertTrue(any("latest 7 published" in c.value for c in app.caption))
        self.assertFalse(any("Latest 12" in c.value for c in app.caption))

    def test_header_clocks_show_local_time_and_follow_language(self):
        app = self.app()
        captions = [caption.value for caption in app.caption]
        self.assertIn("Norges Bank · NBU", captions)
        self.assertIn("Oslo · 18:00:00", captions)
        self.assertIn("Kyiv · 19:00:00", captions)
        self.assertIn("Warsaw · 18:00:00", captions)
        app.get_by_key("language").set_value("nb").run()
        self.assertFalse(app.exception)
        self.assertIn("Oslo · 18:00:00", [caption.value for caption in app.caption])
        self.assertIn("Kyiv · 19:00:00", [caption.value for caption in app.caption])
        self.assertIn("Warszawa · 18:00:00", [caption.value for caption in app.caption])
        for language, city in (("pl", "Warszawa"), ("uk", "Варшава")):
            app.get_by_key("language").set_value(language).run()
            self.assertFalse(app.exception)
            self.assertIn(f"{city} · 18:00:00", [caption.value for caption in app.caption])
        app.get_by_key("language").set_value("en").run()
        with patch.object(fx, "oslo_now", return_value=datetime.fromisoformat("2026-12-16T22:30:45+00:00")):
            app.run()
        self.assertFalse(app.exception)
        captions = [caption.value for caption in app.caption]
        self.assertIn("Oslo · 23:30:45", captions)
        self.assertIn("Kyiv · 00:30:45", captions)
        self.assertIn("Warsaw · 23:30:45", captions)

    def test_removed_language_session_falls_back_to_english(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
        app.session_state["language"] = "ru"
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.get_by_key("language").value, "en")
        self.assertEqual(app.title[0].value, "Currency overview")
        self.assertEqual(app.metric[0].value, "9.4410")

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
        self.assertEqual(app.metric[-1].value, "1,048.99")
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
        self.assertEqual(app.selectbox(key="convert_from").value, "SEK")
        self.assertEqual(app.selectbox(key="convert_to").value, "NOK")
        with patch.object(data, "refresh_history") as refresh:
            for press in range(1, 13):
                with self.subTest(press=press):
                    app.button(key="swap_direction").click().run()
                    self.assertFalse(app.exception)
                    source, target = ("NOK", "SEK") if press % 2 else ("SEK", "NOK")
                    self.assertEqual(app.selectbox(key="convert_from").value, source)
                    self.assertEqual(app.selectbox(key="convert_to").value, target)
                    self.assertTrue(app.number_input(key="amount").label.endswith(source))
                    self.assertEqual(app.number_input(key="amount").value, 1000.0)
                    self.assertTrue(app.metric[-1].label.endswith(target))
                    self.assertEqual(app.metric[-1].value, "1,048.99" if press % 2 else "953.30")
                    self.assertEqual(len(app.dataframe), 1)
            refresh.assert_not_called()

    def test_source_selection_preserves_target_and_swaps_uah(self):
        app = self.app()
        app.selectbox(key="convert_from").select("UAH").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_to").options, list(data.CONVERTER_CURRENCIES))
        self.assertEqual(app.selectbox(key="convert_to").value, "NOK")
        app.button(key="swap_direction").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_from").value, "NOK")
        self.assertEqual(app.selectbox(key="convert_to").value, "UAH")
        self.assertTrue(app.metric[-1].label.endswith("UAH"))
        app.selectbox(key="convert_from").select("USD").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_to").value, "UAH")
        self.assertTrue(app.metric[-1].label.endswith("UAH"))
        app.selectbox(key="convert_to").select("EUR").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.metric[-1].label.endswith("EUR"))

    def test_both_selectors_offer_all_currencies_and_every_pair_converts(self):
        app = self.app()
        with patch.object(data, "refresh_history") as refresh:
            for source in data.CONVERTER_CURRENCIES:
                app.selectbox(key="convert_from").select(source).run()
                for target in data.CONVERTER_CURRENCIES:
                    with self.subTest(source=source, target=target):
                        app.selectbox(key="convert_to").select(target).run()
                        self.assertFalse(app.exception)
                        self.assertEqual(app.selectbox(key="convert_from").options, list(data.CONVERTER_CURRENCIES))
                        self.assertEqual(app.selectbox(key="convert_to").options, list(data.CONVERTER_CURRENCIES))
                        self.assertEqual(app.selectbox(key="convert_from").value, source)
                        self.assertEqual(app.number_input(key="amount").value, 1000.0)
                        self.assertTrue(app.number_input(key="amount").label.endswith(source))
                        self.assertEqual(len(app.metric), 7)
                        self.assertTrue(app.metric[-1].label.endswith(target))
                        if source == target:
                            self.assertEqual(app.metric[-1].value, "1,000.00")
            refresh.assert_not_called()

    def test_existing_or_empty_old_pair_state_migrates_to_currency_fields(self):
        for previous, reverse, expected in [("NOK/SEK", True, ("SEK", "NOK")),
                                             (None, False, ("SEK", "NOK"))]:
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

    def test_existing_converter_default_reverses_once_and_preserves_amount(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
        app.session_state["convert_from"] = "NOK"
        app.session_state["convert_to"] = "SEK"
        app.session_state["amount"] = 2500.0
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_from").value, "SEK")
        self.assertEqual(app.selectbox(key="convert_to").value, "NOK")
        self.assertEqual(app.number_input(key="amount").value, 2500.0)
        self.assertEqual(app.metric[-1].value, "2,383.25")
        app.button(key="swap_direction").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="convert_from").value, "NOK")
        self.assertEqual(app.selectbox(key="convert_to").value, "SEK")

    def test_cards_keep_only_unit_and_date_captions(self):
        app = self.app()
        app.get_by_key("language").set_value("en").run()
        captions = [caption.value for caption in app.get_by_key("quote_cards").get("caption")]
        self.assertEqual(len(captions), 6)
        self.assertEqual(captions[-1], "EUR per 1 USD · 16.10.2026")
        self.assertIn("Compared with", app.metric[3].help)
        self.assertIn("Source: NBU", app.metric[3].help)

    def test_cards_follow_table_order_and_keep_colors(self):
        app = self.app()
        cards = app.get_by_key("quote_cards").get("metric")
        self.assertEqual([m.label for m in cards], ["USD/NOK", "EUR/NOK", "SEK/NOK", "UAH/NOK", "PLN/NOK", "USD/EUR"])
        self.assertEqual([m.label for m in cards], list(app.dataframe[0].value.columns[1:]))
        self.assertEqual([m.proto.MetricColor.Name(m.proto.color) for m in cards],
                         ["GREEN", "GREEN", "RED", "RED", "RED", "GREEN"])

    def test_sidebar_filters_cards_without_hiding_other_pairs_or_fetching_rates(self):
        app = self.app()
        for key in ("language", "visible_pairs", "chart_pair", "period", "chart_scale", "compare"):
            self.assertIsNotNone(app.sidebar.get_by_key(key))
        self.assertFalse(app.main.toggle)
        self.assertFalse(app.main.multiselect)
        columns = list(app.dataframe[0].value.columns)
        converted = app.metric[-1].value
        with patch.object(data, "refresh_history") as refresh:
            app.multiselect(key="visible_pairs").set_value(["PLN/NOK", "USD/NOK"]).run()
            self.assertFalse(app.exception)
            cards = app.get_by_key("quote_cards").get("metric")
            self.assertEqual([card.label for card in cards], ["USD/NOK", "PLN/NOK"])
            self.assertEqual(list(app.dataframe[0].value.columns), columns)
            self.assertEqual(app.metric[-1].value, converted)
            app.get_by_key("chart_pair").set_value("UAH/NOK").run()
            app.get_by_key("period").set_value("3m").run()
            app.get_by_key("language").set_value("uk").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.sidebar.header[0].value, "Налаштування")
            self.assertEqual(set(app.multiselect(key="visible_pairs").value), {"PLN/NOK", "USD/NOK"})
            self.assertEqual(app.get_by_key("chart_pair").value, "UAH/NOK")
            self.assertEqual(app.get_by_key("period").value, "3m")
            app.multiselect(key="visible_pairs").set_value([]).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.get_by_key("quote_cards").get("metric"))
            self.assertTrue(app.get_by_key("quote_cards").get("info"))
            self.assertEqual(len(app.dataframe), 1)
            self.assertEqual(len(app.metric), 1)  # The converter remains usable.
            app.multiselect(key="visible_pairs").set_value(list(chat.PAIRS)).run()
            self.assertFalse(app.exception)
            self.assertEqual([m.label for m in app.get_by_key("quote_cards").get("metric")], list(chat.PAIRS))
            refresh.assert_not_called()

    def test_saved_chart_directions_migrate_without_changing_converter(self):
        for old, new in (("NOK/SEK", "SEK/NOK"), ("NOK/UAH", "UAH/NOK")):
            with self.subTest(old=old):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
                app.session_state["chart_pair"] = old
                app.session_state["convert_from"] = "NOK"
                app.session_state["convert_to"] = "UAH"
                app.run()
                self.assertFalse(app.exception)
                self.assertEqual(app.get_by_key("chart_pair").value, new)
                self.assertEqual(app.selectbox(key="convert_from").value, "NOK")
                self.assertEqual(app.selectbox(key="convert_to").value, "UAH")

    def test_refresh_shows_updated_values_in_the_same_run(self):
        app = self.app()
        history = app.get_by_key("recent_history")
        self.assertEqual(history.button(key="refresh").label, "Update rates")
        self.assertEqual(history.subheader[0].value, "Last 10 business days")
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
                app.get_by_key("language").set_value("nb").run()
                self.assertEqual(app.get_by_key("chart_scale").value, "percent")
                app.toggle(key="compare").set_value(False).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.get_by_key("chart_scale").value, scale)
                self.assertFalse(app.get_by_key("chart_pair").disabled)

    def test_mini_charts_are_always_visible_even_for_an_existing_disabled_session(self):
        with patch.object(data, "refresh_history") as refresh:
            app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
            app.session_state["show_mini"] = False
            app.run()
            self.assertFalse(app.exception)
            original = [metric.value for metric in app.metric]
            self.assertEqual(len(app.get_by_key("quote_cards").get("vega_lite_chart")), 6)
            self.assertEqual([toggle.key for toggle in app.toggle], ["compare"])
            app.get_by_key("language").set_value("nb").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get_by_key("quote_cards").get("vega_lite_chart")), 6)
            app.get_by_key("language").set_value("en").run()
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
            app.get_by_key("language").set_value("nb").run()
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
            self.assertIn("No saved values are available", app.warning[0].value)
            self.assertNotIn("Saved values are shown", app.warning[0].value)
            self.assertFalse(app.toggle)
            app.get_by_key("language").set_value("nb").run()
            self.assertFalse(app.exception)
            self.assertIn("Ingen lagrede verdier er tilgjengelige", app.warning[0].value)
            refresh.assert_called_once_with()
            app.button(key="refresh").click().run()
            self.assertEqual(refresh.call_count, 2)

    def test_empty_history_keeps_retry_available_without_nonfunctional_controls(self):
        with patch.object(data, "read_snapshot", return_value=data.Snapshot([], None)):
            app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        self.assertIn("Update rates", app.info[0].value)
        self.assertTrue(app.button(key="refresh"))
        self.assertFalse(app.metric)
        self.assertFalse(app.toggle)
        self.assertFalse(app.dataframe)
        self.assertFalse(app.warning)

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
        app.get_by_key("chart_pair").set_value("SEK/NOK").run()
        self.assertFalse(app.exception)
        app.get_by_key("chart_scale").set_value("rate").run()
        self.assertFalse(app.exception)
        self.assertFalse(any("rather than starting at zero" in c.value for c in app.caption))

    def test_chart_pair_selection_updates_rendered_data_and_units(self):
        histories = chat.pair_values(self.snapshot.rows, self.snapshot.uah_values)
        with patch.object(charts, "quote_chart", wraps=charts.quote_chart) as render_chart, \
                patch.object(data, "refresh_history") as refresh:
            app = self.app()
            for mode in ("all_cards", "filtered"):
                if mode == "filtered":
                    app.multiselect(key="visible_pairs").set_value(["EUR/NOK"]).run()
                for selected in chat.PAIRS:
                    with self.subTest(mode=mode, pair=selected):
                        app.get_by_key("chart_pair").set_value(selected).run()
                        self.assertFalse(app.exception)
                        expected = [{"Date": day, "Rate": rate}
                                    for day, rate in sorted(histories[selected].items())]
                        self.assertEqual(render_chart.call_args.args[0], expected)
                        base, quote = selected.split("/")
                        self.assertEqual(render_chart.call_args.args[1], f"{quote} per 1 {base}")
                        self.assertIn(f"{selected} · Rate · 1 month", [c.value for c in app.caption])
            refresh.assert_not_called()

    def test_three_year_period_includes_older_quotes_and_filters_earlier_dates(self):
        included, excluded = date(2024, 2, 29), date(2023, 10, 15)
        rows = self.snapshot.rows + [
            fx.Rate(currency, day, fx.Decimal(value)) for day in (excluded, included)
            for currency, value in (("USD", "8"), ("EUR", "10"), ("SEK", "1"), ("PLN", "2"))]
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
            app.get_by_key("language").set_value("nb").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.get_by_key("period").value, "3y")
            self.assertIn("3 år", app.get_by_key("period").options)
            self.assertNotIn("Alle", app.get_by_key("period").options)
            refresh.assert_not_called()


    def test_long_periods_filter_at_calendar_boundary_in_all_chart_modes(self):
        for years in (5, 10):
            with self.subTest(years=years):
                st.cache_data.clear()
                boundary = date(2026 - years, 10, 16)
                excluded = boundary - timedelta(days=1)
                first_weekday = boundary + timedelta(days=7 - boundary.weekday()) if boundary.weekday() >= 5 else boundary
                rows = self.snapshot.rows + [
                    fx.Rate(currency, day, fx.Decimal(value))
                    for day in {excluded, boundary, first_weekday, date(2024, 2, 29)}
                    for currency, value in (("USD", "8"), ("EUR", "10"), ("SEK", "1"), ("PLN", "2"))]
                uah = {**self.snapshot.uah_values, boundary: fx.Decimal("4"), excluded: fx.Decimal("4"),
                       first_weekday: fx.Decimal("4")}
                extended = data.Snapshot(rows, self.snapshot.loaded_at, uah)
                with patch.object(data, "read_snapshot", return_value=extended), \
                        patch.object(data, "refresh_history") as refresh, \
                        patch.object(charts, "quote_chart", wraps=charts.quote_chart) as quote, \
                        patch.object(charts, "comparison_chart", wraps=charts.comparison_chart) as comparison:
                    app = self.app()
                    app.get_by_key("period").set_value(f"{years}y").run()
                    self.assertFalse(app.exception)
                    self.assertEqual(quote.call_args.args[0][0]["Date"], boundary)
                    self.assertIn(date(2024, 2, 29), [row["Date"] for row in quote.call_args.args[0]])
                    app.get_by_key("chart_scale").set_value("percent").run()
                    self.assertFalse(app.exception)
                    self.assertTrue(quote.call_args.kwargs["percent"])
                    self.assertEqual(quote.call_args.args[0][0]["Date"], boundary)
                    app.toggle(key="compare").set_value(True).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(min(row["Date"] for row in comparison.call_args.args[0]), first_weekday)
                    for language, label in (("nb", f"{years} år"), ("pl", f"{years} lat"),
                                            ("uk", f"{years} років"), ("en", f"{years} years")):
                        app.get_by_key("language").set_value(language).run()
                        self.assertFalse(app.exception)
                        self.assertEqual(app.get_by_key("period").value, f"{years}y")
                        self.assertIn(label, app.get_by_key("period").options)
                    refresh.assert_not_called()

    def test_ten_year_comparison_renders_more_than_5000_observations(self):
        first, today = date(2016, 10, 16), date(2026, 10, 16)
        days = [first + timedelta(days=offset) for offset in range((today - first).days + 1)
                if (first + timedelta(days=offset)).weekday() < 5]
        rows = [fx.Rate(currency, day, fx.Decimal(value)) for day in days
                for currency, value in (("USD", "8"), ("EUR", "10"), ("SEK", "1"), ("PLN", "2"))]
        extended = data.Snapshot(rows, self.snapshot.loaded_at, {day: fx.Decimal("4") for day in days})
        with patch.object(data, "read_snapshot", return_value=extended), \
                patch.object(data, "refresh_history") as refresh, \
                patch.object(charts, "comparison_chart", wraps=charts.comparison_chart) as comparison:
            app = self.app()
            app.get_by_key("period").set_value("10y").run()
            self.assertFalse(app.exception)
            app.toggle(key="compare").set_value(True).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(comparison.call_args.args[0]), len(days) * len(chat.NOK_PAIRS))
            self.assertGreater(len(comparison.call_args.args[0]), 5000)
            refresh.assert_not_called()

    def test_language_switch_preserves_filters_converter_and_does_not_refresh(self):
        app = self.app()
        app.get_by_key("period").set_value("3m").run()
        app.get_by_key("chart_pair").set_value("UAH/NOK").run()
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
            self.assertEqual(app.get_by_key("chart_pair").value, "UAH/NOK")
            self.assertEqual(app.get_by_key("chart_scale").value, "percent")
            self.assertEqual(app.selectbox(key="convert_from").value, "EUR")
            self.assertEqual(app.selectbox(key="convert_to").value, "USD")
            self.assertEqual(app.number_input(key="amount").value, 2500.0)
            self.assertEqual(app.metric[-1].value.replace(" ", "").replace(",", "."), before.replace(",", ""))
            self.assertEqual(app.dataframe[0].value.columns[0], "Dato")
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

    def test_pln_converter_chart_and_new_languages_preserve_state(self):
        app = self.app()
        self.assertEqual(app.metric[4].value, "2.5100")
        self.assertEqual(app.dataframe[0].value.iloc[-1]["PLN/NOK"], "2.5100")
        app.selectbox(key="convert_from").select("PLN").run()
        self.assertEqual(app.selectbox(key="convert_to").options, list(data.CONVERTER_CURRENCIES))
        self.assertEqual(app.metric[-1].value, "2,510.00")
        app.button(key="swap_direction").click().run()
        self.assertEqual(app.selectbox(key="convert_to").value, "PLN")
        self.assertEqual(app.metric[-1].value, "398.41")
        app.get_by_key("chart_pair").set_value("PLN/NOK").run()
        app.get_by_key("period").set_value("3m").run()
        with patch.object(data, "refresh_history") as refresh:
            for language, title, heading, button in [
                ("pl", "Przegląd walut", "Data", "Aktualizuj kursy"),
                ("uk", "Огляд валют", "Дата", "Оновити курси"),
            ]:
                with self.subTest(language=language):
                    app.get_by_key("language").set_value(language).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.title[0].value, title)
                    self.assertEqual(app.button(key="refresh").label, button)
                    self.assertEqual(app.metric[4].value, "2,5100")
                    self.assertEqual(app.metric[-1].value, "398,41")
                    self.assertEqual(app.dataframe[0].value.columns[0], heading)
                    self.assertEqual(app.get_by_key("chart_pair").value, "PLN/NOK")
                    self.assertEqual(app.get_by_key("period").value, "3m")
                    self.assertEqual(app.selectbox(key="convert_to").value, "PLN")
                    app.toggle(key="compare").set_value(True).run()
                    self.assertFalse(app.exception)
                    self.assertFalse(any("no shared date" in item.value.lower() for item in app.info))
                    app.toggle(key="compare").set_value(False).run()
            refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
