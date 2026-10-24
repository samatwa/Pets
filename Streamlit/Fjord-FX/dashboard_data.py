"""Data services for the Streamlit dashboard; calculations stay in Decimal."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import chat_report as chat
import fx_monitor as fx
import nbu_rates as nbu
import dashboard_i18n as i18n

DB_PATH = fx.ROOT / "data/rates.sqlite3"
REFRESH_INTERVAL = 300
RETRY_INTERVAL = 30
HISTORY_DAYS = 3 * 366
CONVERTER_CURRENCIES = ("USD", "EUR", "NOK", "SEK", "UAH")
_REFRESH_LOCK = threading.Lock()
PAIR_LABELS = {
    "USD/NOK": "NOK за 1 USD",
    "EUR/NOK": "NOK за 1 EUR",
    "USD/EUR": "EUR за 1 USD",
    "NOK/SEK": "SEK за 1 NOK",
    "NOK/UAH": "UAH за 1 NOK",
}


@dataclass(frozen=True)
class Snapshot:
    rows: list[fx.Rate]
    loaded_at: str | None
    uah_values: dict[date, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class _RefreshAttempt:
    key: tuple[Path, int, date]
    completed_at: float
    error: tuple[type[Exception], str] | None = None


# Shared official rates: coordinate refreshes across browser sessions in this process.
_last_refresh: _RefreshAttempt | None = None


def conversion_targets(currency: str) -> list[str]:
    """Offer only the five published pairs and their inverse directions."""
    return [target for target in CONVERTER_CURRENCIES
            if f"{currency}/{target}" in chat.PAIRS or f"{target}/{currency}" in chat.PAIRS]


def database_signature() -> tuple[str, int, int, str]:
    if not DB_PATH.exists():
        return str(DB_PATH), 0, 0, "nbu-v1"
    stat = DB_PATH.stat()
    return str(DB_PATH), stat.st_mtime_ns, stat.st_size, "nbu-v1"


def read_snapshot() -> Snapshot:
    if not DB_PATH.exists():
        return Snapshot([], None)
    today = fx.oslo_now().date()
    with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        rows = fx.load(db, end=today)
        stamp = db.execute("""SELECT MAX(fetched_at) FROM (
            SELECT fetched_at FROM rates UNION ALL SELECT fetched_at FROM sek_rates)""").fetchone()[0]
        uah_values = {d: v for d, v in nbu.load(db).items() if d <= today}
    return Snapshot(rows, stamp, uah_values)


def refresh_history(days: int = HISTORY_DAYS) -> Snapshot:
    """Share refreshes for five minutes; briefly back off after a failed attempt."""
    global _last_refresh
    with _REFRESH_LOCK:
        key = (DB_PATH.resolve(), days, fx.oslo_now().date())
        previous = _last_refresh
        interval = RETRY_INTERVAL if previous and previous.error else REFRESH_INTERVAL
        if previous and previous.key == key and time.monotonic() - previous.completed_at < interval:
            if previous.error:
                error_type, message = previous.error
                raise error_type(message)
            if DB_PATH.exists():
                return read_snapshot()
        try:
            snapshot = _refresh_history(days, key[2])
        except (fx.MonitorError, OSError, sqlite3.Error) as exc:
            _last_refresh = _RefreshAttempt(key, time.monotonic(), (type(exc), str(exc)))
            raise
        _last_refresh = _RefreshAttempt(key, time.monotonic())
        return snapshot


def _refresh_history(days: int, today: date) -> Snapshot:
    """Validate the full reply before modifying the existing database."""
    start = today - timedelta(days=days - 1)
    url = fx.make_url(start=start, end=today)
    raw = fx.fetch(url, timeout=20, attempts=3)
    rows = fx.parse_sdmx(raw)
    if set(fx.SUPPORTED_CURRENCIES) - {r.currency for r in rows}:
        raise fx.DataError("Источник вернул не все валюты. Сохранённая история не изменена.")
    if any(r.day < start or r.day > today for r in rows):
        raise fx.DataError("Источник вернул даты вне запрошенного периода.")
    if any(sum(r.currency == c for r in rows) < 2 for c in fx.SUPPORTED_CURRENCIES):
        raise fx.DataError("Для сравнения нужны два наблюдения по каждой валюте.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    fx.atomic_text(fx.ROOT / "data/raw" / f"{stamp}.json", raw)
    with closing(fx.connect(DB_PATH)) as db:
        fx.save(db, rows, url)
        fx.export_csv(db, fx.ROOT / "data/rates.csv")
        try:
            nbu.refresh(db, start, today)
        except (fx.MonitorError, OSError) as exc:
            raise fx.MonitorError(f"Norges Bank обновлён, НБУ недоступен; прежний NOK/UAH сохранён. {exc}") from exc
        text, report = chat.build_report(fx.load(db, end=today), today, uah_values=nbu.load(db))
        fx.atomic_text(fx.ROOT / "data/chat_report.md", text)
        fx.atomic_text(fx.ROOT / "data/chat_report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return read_snapshot()


def weekdays(today: date, count: int = 7) -> list[date]:
    days = []
    while len(days) < count:
        if today.weekday() < 5:
            days.append(today)
        today -= timedelta(days=1)
    return list(reversed(days))


def quote_summary(values: dict[date, Decimal]) -> dict | None:
    history = sorted(values.items())
    if not history:
        return None
    day, rate = history[-1]
    previous = history[-2] if len(history) > 1 else None
    change = rate - previous[1] if previous else None
    return {"day": day, "rate": rate, "previous_day": previous[0] if previous else None,
            "change": change, "percent": change / previous[1] * 100 if previous else None}


def history_records(pairs: dict, start: date | None = None) -> list[dict]:
    dates = sorted({d for series in pairs.values() for d in series if start is None or d >= start})
    return [{"Дата": day, **{pair: pairs[pair].get(day) for pair in chat.PAIRS}} for day in dates]


def comparison_records(pairs: dict, start: date) -> list[dict]:
    """Use a shared baseline date; never compare nominal quotes in different units."""
    if any(not pairs[p] for p in chat.PAIRS):
        return []
    common = set.intersection(*(set(pairs[p]) for p in chat.PAIRS))
    baseline = min((d for d in common if d >= start), default=None)
    if baseline is None:
        return []
    return [{"Дата": d, "Пара": p, "Изменение, %": float((v / pairs[p][baseline] - 1) * 100)}
            for p in chat.PAIRS for d, v in sorted(pairs[p].items()) if d >= baseline]


def csv_bytes(records: list[dict], *, language: str | None = None) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([i18n.tr(language, "date") if language else "Дата", *chat.PAIRS])
    for record in records:
        writer.writerow([record["Дата"].strftime("%d.%m.%Y"), *[
            (i18n.number(record[p], language=language) if language else chat.format_number(record[p]))
            if record[p] is not None else "" for p in chat.PAIRS]])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
