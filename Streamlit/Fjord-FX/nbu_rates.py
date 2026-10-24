"""Official NBU NOK/UAH rates, in UAH per 1 NOK, with effective dates."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import fx_monitor as fx

SOURCE_URL = "https://bank.gov.ua/ua/markets/exchangerates"


def make_url(start: date, end: date) -> str:
    return "https://bank.gov.ua/NBU_Exchange/exchange_site?" + urlencode({
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "valcode": "nok", "sort": "exchangedate", "order": "asc"}) + "&json"


def parse(raw: str, start: date, end: date) -> dict[date, Decimal]:
    try:
        payload = json.loads(raw, parse_float=Decimal)
        if not isinstance(payload, list):
            raise fx.DataError("НБУ вернул неверную структуру JSON.")
        result = {}
        for item in payload:
            if item["cc"] != "NOK" or str(item["r030"]) != "578":
                raise fx.DataError("В ответе НБУ обнаружена другая валюта.")
            day = datetime.strptime(item["exchangedate"], "%d.%m.%Y").date()
            if not start <= day <= end:
                raise fx.DataError("Дата НБУ вне запрошенного периода.")
            value = Decimal(str(item["rate_per_unit"]))
            units = Decimal(str(item["units"]))
            total = Decimal(str(item["rate"]))
            if any(not n.is_finite() or n <= 0 for n in (value, units, total)):
                raise fx.DataError("НБУ вернул недопустимый курс или единицы.")
            if abs(total / units - value) > Decimal("0.0000001"):
                raise fx.DataError("Единицы и курс НБУ не согласованы.")
            if day in result and result[day] != value:
                raise fx.DataError("НБУ вернул разные курсы за одну дату.")
            result[day] = value
        if not result:
            raise fx.NoDataError("НБУ не вернул значений NOK/UAH за этот период.")
        return dict(sorted(result.items()))
    except (fx.DataError, fx.NoDataError):
        raise
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation) as exc:
        raise fx.DataError(f"Неверный ответ НБУ: {exc}") from exc


def load(db) -> dict[date, Decimal]:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nbu_nok_rates'").fetchone()
    if not exists:
        return {}
    return {date.fromisoformat(day): Decimal(value) for day, value in db.execute(
        "SELECT date,rate FROM nbu_nok_rates ORDER BY date")}


def save(db, values: dict[date, Decimal], source: str) -> None:
    with db:
        db.execute("""CREATE TABLE IF NOT EXISTS nbu_nok_rates (
            date TEXT PRIMARY KEY, rate TEXT NOT NULL,
            fetched_at TEXT NOT NULL, source TEXT NOT NULL)""")
        stamp = datetime.now(timezone.utc).isoformat()
        db.executemany("""INSERT INTO nbu_nok_rates VALUES (?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET rate=excluded.rate,
            fetched_at=excluded.fetched_at, source=excluded.source""",
            [(str(day), str(value), stamp, source) for day, value in values.items()])


def refresh(db, start: date, end: date, input_json=None) -> dict[date, Decimal]:
    url = make_url(start, end)
    raw = input_json.read_text(encoding="utf-8-sig") if input_json else fx.fetch(url)
    values = parse(raw, start, end)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    fx.atomic_text(fx.ROOT / "data/raw" / f"nbu_{stamp}.json", raw)
    save(db, values, f"import:{input_json.resolve()}" if input_json else url)
    return load(db)
