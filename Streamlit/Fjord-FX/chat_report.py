"""Fetch and format the five-pair chat summary and seven-weekday history."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import fx_monitor as fx
import nbu_rates as nbu

PAIRS = ("USD/NOK", "EUR/NOK", "USD/EUR", "NOK/SEK", "NOK/UAH")
UNITS = {"USD/NOK": "NOK", "EUR/NOK": "NOK", "USD/EUR": "EUR", "NOK/SEK": "SEK", "NOK/UAH": "UAH"}


def format_number(value: Decimal, pattern: str = ".4f") -> str:
    return format(value, pattern).replace("-", "−").replace(".", ",")


def pair_values(rows: list[fx.Rate], uah_values: dict[date, Decimal] | None = None) -> dict[str, dict[date, Decimal]]:
    source = {(r.day, r.currency): r.value for r in rows}
    pairs = {pair: {} for pair in PAIRS}
    for (day, currency), value in source.items():
        if currency == "USD":
            pairs["USD/NOK"][day] = value
            if (day, "EUR") in source:
                pairs["USD/EUR"][day] = value / source[day, "EUR"]
        elif currency == "EUR":
            pairs["EUR/NOK"][day] = value
        elif currency == "SEK":
            # Stored value is NOK per 1 SEK; invert to SEK per 1 NOK.
            pairs["NOK/SEK"][day] = Decimal(1) / value
    # Keep the chat's Monday-Friday convention; NBU also returns effective weekend rates.
    pairs["NOK/UAH"] = {d: v for d, v in (uah_values or {}).items() if d.weekday() < 5}
    return pairs


def build_report(rows: list[fx.Rate], today: date, *, offline: bool = False,
                 uah_values: dict[date, Decimal] | None = None) -> tuple[str, dict]:
    pairs = pair_values([r for r in rows if r.day <= today],
                        {d: v for d, v in (uah_values or {}).items() if d <= today})
    lines = ["| Пара | Курс за 1 единицу | Изменение |", "|---|---:|---:|"]
    dates = []
    summary = []
    for pair in PAIRS:
        history = sorted(pairs[pair].items())
        if not history:
            lines.append(f"| {pair} | нет данных | нет данных для сравнения |")
            continue
        day, value = history[-1]
        previous = history[-2] if len(history) > 1 else None
        change = value - previous[1] if previous else None
        pct = change / previous[1] * 100 if previous else None
        change_text = (f"{format_number(change, '+.4f')} ({format_number(pct, '+.2f')}%)"
                       if previous else "нет данных для сравнения")
        lines.append(f"| {pair} | {format_number(value)} {UNITS[pair]} | {change_text} |")
        dates.append((pair, day, previous[0] if previous else None))
        summary.append({"pair": pair, "date": str(day), "rate": str(value),
                        "quote_currency": UNITS[pair],
                        "previous_date": str(previous[0]) if previous else None,
                        "change": str(change) if change is not None else None,
                        "change_pct": str(pct) if pct is not None else None})
    lines.append("")
    if dates and len({(d, p) for _, d, p in dates}) == 1:
        _, day, previous = dates[0]
        lines.append(f"Курсы за {day:%d.%m.%Y}; изменение относительно "
                     f"{previous.strftime('%d.%m.%Y') if previous else 'неизвестной даты'}.")
    else:
        for pair, day, previous in dates:
            lines.append(f"{pair}: {day:%d.%m.%Y}; предыдущая дата — "
                         f"{previous.strftime('%d.%m.%Y') if previous else 'нет данных'}.")
    days = []
    day = today
    while len(days) < 7:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    lines += ["", "| Дата | " + " | ".join(PAIRS) + " |",
              "|---|" + "---:|" * len(PAIRS)]
    week = []
    missing = False
    for day in reversed(days):
        values = {pair: pairs[pair].get(day) for pair in PAIRS}
        missing = missing or any(v is None for v in values.values())
        cells = [format_number(values[p]) if values[p] is not None
                 else ("нет данных" if offline else "нет публикации") for p in PAIRS]
        lines.append(f"| {day:%d.%m.%Y} | " + " | ".join(cells) + " |")
        week.append({"date": str(day), **{p: str(v) if v is not None else None for p, v in values.items()}})
    if offline:
        lines += ["", "Не все источники сейчас перепроверены; показаны сохранённые данные."]
    elif missing:
        lines += ["", "Нет публикации — отсутствует исходный курс за указанную дату."]
    checked = fx.oslo_now().isoformat()
    lines += ["", "Источник: https://www.norges-bank.no/en/topics/Statistics/exchange_rates/",
              "Источник NOK/UAH: https://bank.gov.ua/ua/markets/exchangerates — UAH за 1 NOK, дата действия курса НБУ.",
              "USD/EUR рассчитан через курсы к NOK; NOK/SEK — SEK за 1 NOK "
              "(обратная котировка Norges Bank с учётом 100 SEK).",
              f"Проверено: {checked} (Europe/Oslo).", ""]
    return "\n".join(lines), {"checked_at": checked, "offline": offline, "summary": summary, "week": week}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=fx.Path)
    parser.add_argument("--input-nbu-json", type=fx.Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(fx.sys.stdout, "reconfigure"):
        fx.sys.stdout.reconfigure(encoding="utf-8")
        fx.sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    db = None
    failed = False
    try:
        today = fx.oslo_now().date()
        start = today - timedelta(days=29)
        db = fx.connect(fx.ROOT / "data/rates.sqlite3")
        if not args.offline:
            try:
                url = fx.make_url(start=start, end=today)
                raw = args.input_json.read_text(encoding="utf-8-sig") if args.input_json else fx.fetch(url)
                rows = fx.parse_sdmx(raw)
                if set(fx.SUPPORTED_CURRENCIES) - {r.currency for r in rows}:
                    raise fx.DataError("Для сводки нужны USD, EUR и SEK.")
                if any(r.day < start or r.day > today for r in rows):
                    raise fx.DataError("Ответ содержит даты вне запрошенного периода.")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                fx.atomic_text(fx.ROOT / "data/raw" / f"{stamp}.json", raw)
                fx.save(db, rows, f"import:{args.input_json.resolve()}" if args.input_json else url)
                fx.export_csv(db, fx.ROOT / "data/rates.csv")
            except (fx.MonitorError, OSError) as exc:
                logging.error("%s", exc)
                failed = True
        if not args.offline and (not args.input_json or args.input_nbu_json):
            try:
                nbu.refresh(db, start, today, args.input_nbu_json)
            except (fx.MonitorError, OSError) as exc:
                logging.error("НБУ: %s", exc)
                failed = True
        text, data = build_report(fx.load(db, end=today), today, uah_values=nbu.load(db),
                                  offline=args.offline or bool(args.input_json) or bool(args.input_nbu_json) or failed)
        fx.atomic_text(fx.ROOT / "data/chat_report.md", text)
        fx.atomic_text(fx.ROOT / "data/chat_report.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(text)
        return 1 if failed else 0
    except (fx.MonitorError, OSError, fx.sqlite3.Error) as exc:
        logging.error("%s", exc)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
