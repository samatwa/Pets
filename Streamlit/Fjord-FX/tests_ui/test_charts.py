import math
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import chat_report as chat
import dashboard_charts as charts
import fx_monitor as fx
import nbu_rates as nbu


def line_spec(spec):
    return next(layer for layer in spec.get("layer", [spec]) if layer["mark"]["type"] == "line")


class ChartTests(unittest.TestCase):
    def test_scale_expands_after_a_jump_and_shrinks_for_a_new_period(self):
        records = [{"Дата": date(2026, 10, day), "Курс": Decimal(rate)}
                   for day, rate in [(13, "9.4"), (14, "9.5"), (15, "15.2")]]
        before = line_spec(charts.quote_chart(records[:2], "NOK").to_dict())["encoding"]["y"]["scale"]["domain"]
        after = line_spec(charts.quote_chart(records, "NOK").to_dict())["encoding"]["y"]["scale"]["domain"]
        self.assertLess(before[1], 10)
        self.assertGreater(after[1], 15.2)
        self.assertLess(after[0], 9.4)
        self.assertGreater(after[1] - after[0], before[1] - before[0])
        self.assertGreaterEqual(charts.padded_domain([1, 100])[0], 0)

    def test_mini_chart_keeps_seven_observations_with_real_dates_and_tooltips(self):
        # Missing calendar dates stay missing; the seven observations need not be seven days.
        series = {date(2026, 10, day): Decimal("9") + Decimal(day) / 100
                  for day in [1, 2, 5, 6, 7, 8, 9, 12, 13]}
        spec = charts.mini_chart(series, "NOK за 1 USD").to_dict()
        rows = next(iter(spec["datasets"].values()))
        self.assertEqual(len(rows), 7)
        self.assertEqual([r["Дата курса"] for r in rows],
                         ["05.10.2026", "06.10.2026", "07.10.2026", "08.10.2026",
                          "09.10.2026", "12.10.2026", "13.10.2026"])
        self.assertEqual(rows[-1]["Курс для показа"], "9.1300")
        self.assertEqual([t["title"] for t in spec["layer"][-1]["encoding"]["tooltip"]], ["Date", "NOK за 1 USD"])
        self.assertFalse(line_spec(spec)["encoding"]["y"]["scale"]["zero"])
        self.assertEqual(line_spec(spec)["encoding"]["x"]["scale"]["type"], "band")

    def test_single_observation_mini_chart_still_has_a_point_and_tooltip(self):
        spec = charts.mini_chart({date(2026, 10, 23): Decimal("4.8068")}, "UAH за 1 NOK").to_dict()
        self.assertTrue(line_spec(spec)["mark"]["point"]["filled"])
        self.assertEqual(len(next(iter(spec["datasets"].values()))), 1)

    def test_each_quote_uses_its_actual_range(self):
        raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/norges_bank_with_sek_2026-10-16.json").read_text(encoding="utf-8")
        uah_raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/nbu_nok_2026-10.json").read_text(encoding="utf-8")
        uah = nbu.parse(uah_raw, date(2026, 10, 12), date(2026, 10, 23))
        for pair, series in chat.pair_values(fx.parse_sdmx(raw), uah).items():
            with self.subTest(pair=pair):
                records = [{"Дата": day, "Курс": rate} for day, rate in series.items()]
                spec = charts.quote_chart(records, pair).to_dict()
                scale = line_spec(spec)["encoding"]["y"]["scale"]
                low, high = scale["domain"]
                values = [float(v) for v in series.values()]
                self.assertLess(low, min(values))
                self.assertGreater(high, max(values))
                self.assertGreater(low, 0)
                self.assertLess(high - low, max(values) * 0.1)
                self.assertFalse(scale["zero"])
                self.assertFalse(scale["nice"])
                # No area layer can silently introduce a y2=0 baseline.
                self.assertEqual(line_spec(spec)["mark"]["type"], "line")

    def test_percentage_view_has_correct_baseline_and_units(self):
        records = [{"Дата": date(2026, 10, day), "Курс": Decimal(rate)}
                   for day, rate in [(13, "10"), (14, "10.1"), (15, "9.9")]]
        spec = charts.quote_chart(records, "NOK за 1 USD", percent=True).to_dict()
        points = next(rows for rows in spec["datasets"].values() if rows and "Значение" in rows[0])
        self.assertEqual([row["Значение"] for row in points], [0.0, 1.0, -1.0])
        self.assertEqual([row["Курс"] for row in points], ["10.0000", "10.1000", "9.9000"])
        self.assertEqual(spec["layer"][1]["encoding"]["y"]["title"], "Change from start of period, %")

    def test_flat_series_remains_flat_on_a_valid_scale(self):
        records = [{"Дата": date(2026, 10, day), "Курс": Decimal("1.0490")} for day in [13, 14]]
        spec = charts.quote_chart(records, "SEK за 1 NOK").to_dict()
        low, high = line_spec(spec)["encoding"]["y"]["scale"]["domain"]
        self.assertTrue(math.isfinite(low) and math.isfinite(high))
        self.assertLess(low, 1.0490)
        self.assertGreater(high, 1.0490)
        points = next(iter(spec["datasets"].values()))
        self.assertEqual(points[0]["Значение"], points[1]["Значение"])

    def test_weekend_gap_is_compressed_and_whole_date_band_has_a_tooltip(self):
        records = [{"Дата": date(2026, 10, day), "Курс": Decimal("9.4")}
                   for day in [15, 16, 19, 20]]
        for spec in [charts.quote_chart(records, "NOK").to_dict(),
                     charts.mini_chart({r["Дата"]: r["Курс"] for r in records}, "NOK").to_dict()]:
            x = line_spec(spec)["encoding"]["x"]
            self.assertEqual(x["type"], "ordinal")
            self.assertEqual(x["scale"]["domain"], ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20"])
            hit = spec["layer"][-1]
            self.assertEqual(hit["mark"]["type"], "rect")
            self.assertNotIn("y", hit["encoding"])
            self.assertTrue(hit["encoding"]["tooltip"])
            self.assertEqual(spec["params"][0]["select"]["on"], "pointerover")

    def test_comparison_hover_shows_all_pairs_at_one_date(self):
        records = [{"Дата": date(2026, 10, day), "Пара": pair, "Изменение, %": day / 100}
                   for pair in chat.PAIRS for day in [16, 19]]
        spec = charts.comparison_chart(records).to_dict()
        hit = spec["layer"][-1]
        self.assertEqual([item["title"] for item in hit["encoding"]["tooltip"]], ["Date", *chat.PAIRS])
        self.assertEqual(hit["mark"]["type"], "rect")

    def test_multiyear_axis_includes_years_and_dense_series_keeps_exact_hover_data(self):
        start = date(2024, 1, 1)
        records = [{"Дата": start + timedelta(days=day), "Курс": Decimal("10") + Decimal(day) / 1000}
                   for day in range(800)]
        spec = charts.quote_chart(records, "NOK").to_dict()
        line = line_spec(spec)
        self.assertIn("slice(datum.label, 0, 4)", line["encoding"]["x"]["axis"]["labelExpr"])
        ticks = line["encoding"]["x"]["axis"]["values"]
        self.assertEqual(len({tick[:7] for tick in ticks}), len(ticks))
        self.assertFalse(line["mark"]["point"])
        rows = next(rows for rows in spec["datasets"].values() if rows and "Значение" in rows[0])
        self.assertEqual(len(rows), len(records))
        self.assertEqual(rows[-1]["Курс"], "10.7990")
        self.assertTrue(spec["layer"][-1]["encoding"]["tooltip"])
        short = line_spec(charts.quote_chart(records[:10], "NOK").to_dict())
        self.assertTrue(short["mark"]["point"]["filled"])
        self.assertNotIn("slice(datum.label, 0, 4)", short["encoding"]["x"]["axis"]["labelExpr"])


    def test_chart_language_changes_visible_titles_and_numbers(self):
        records = [{"Дата": date(2026, 10, day), "Курс": Decimal(rate)}
                   for day, rate in [(15, "9.4"), (16, "9.5")]]
        en = charts.quote_chart(records, "NOK per 1 USD", percent=True, language="en").to_dict()
        nb = charts.quote_chart(records, "NOK per 1 USD", percent=True, language="nb").to_dict()
        self.assertEqual(line_spec(en)["encoding"]["y"]["title"], "Change from start of period, %")
        self.assertEqual(line_spec(nb)["encoding"]["y"]["title"], "Endring fra periodens start, %")
        self.assertEqual(nb["layer"][-1]["encoding"]["tooltip"][0]["title"], "Dato")
        for spec, expected in [(en, "9.4000"), (nb, "9,4000")]:
            rows = next(rows for rows in spec["datasets"].values() if rows and "Курс" in rows[0])
            self.assertEqual(rows[0]["Курс"], expected)
        scale_en = line_spec(en)["encoding"]["y"]["scale"]
        scale_nb = line_spec(nb)["encoding"]["y"]["scale"]
        self.assertEqual(scale_en, scale_nb)
        ru = charts.quote_chart(records, "NOK за 1 USD", percent=True, language="ru").to_dict()
        self.assertEqual(line_spec(ru)["encoding"]["y"]["title"], "Изменение от начала периода, %")
        self.assertEqual(ru["layer"][-1]["encoding"]["tooltip"][0]["title"], "Дата")
        self.assertIn("replace", line_spec(ru)["encoding"]["y"]["axis"]["labelExpr"])
        self.assertEqual(line_spec(ru)["encoding"]["y"]["scale"], scale_en)


if __name__ == "__main__":
    unittest.main()
