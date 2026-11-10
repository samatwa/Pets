"""USD/NOK and EUR/NOK monitoring against the official Norges Bank SDMX API."""
from __future__ import annotations

import argparse
import csv
import http.client
import io
import json
import logging
import math
import os
import socket
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://data.norges-bank.no/api/data/EXR/B.USD+EUR+SEK+PLN.NOK.SP"
CURRENCIES = ("USD", "EUR")
SUPPORTED_CURRENCIES = CURRENCIES + ("SEK", "PLN")
LOG = logging.getLogger("norges_bank_fx")
MAX_BYTES = 20 * 1024 * 1024


class MonitorError(Exception):
    """An expected, user-facing failure."""


class DataError(MonitorError):
    pass


class NoDataError(MonitorError):
    pass


@dataclass(frozen=True)
class Rate:
    currency: str
    day: date
    value: Decimal


def oslo_now() -> datetime:
    try:
        return datetime.now(ZoneInfo("Europe/Oslo"))
    except ZoneInfoNotFoundError as exc:
        raise MonitorError("The time-zone database is missing. Run: python -m pip install -r requirements.txt") from exc


def make_url(*, start: date | None = None, end: date | None = None,
             last: int | None = None) -> str:
    params = {"format": "sdmx-json", "locale": "en"}
    if last is not None:
        if last < 1 or start is not None:
            raise MonitorError("last must be positive and cannot be combined with start.")
        params["lastNObservations"] = str(last)
    if start is not None:
        params["startPeriod"] = start.isoformat()
    if end is not None:
        params["endPeriod"] = end.isoformat()
    return ENDPOINT + "?" + urlencode(params)


def fetch(url: str, *, timeout: float = 20, attempts: int = 3) -> str:
    """Retry transient HTTP/network errors only; TLS verification stays enabled."""
    for attempt in range(attempts):
        delay = min(2 ** attempt, 8)
        try:
            request = Request(url, headers={"Accept": "application/json",
                                           "User-Agent": "NorgesBankFXMonitor/1.0"})
            with urlopen(request, timeout=timeout) as response:
                if response.status == 204:
                    raise NoDataError("Norges Bank returned no observations for the selected period.")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise DataError("The API response exceeded the 20 MB limit; select a shorter period.")
                return raw.decode("utf-8-sig")
        except HTTPError as exc:
            if exc.code == 404:
                raise NoDataError("HTTP 404: data or series not found; check the period and API.") from exc
            if exc.code != 429 and not 500 <= exc.code <= 599:
                raise MonitorError(f"The API returned HTTP {exc.code}: {exc.reason}") from exc
            error = f"HTTP {exc.code}"
            try:
                delay = min(max(float(exc.headers.get("Retry-After", delay)), 0), 60)
            except (ValueError, TypeError):
                pass
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError, http.client.HTTPException) as exc:
            error = str(exc)
        except UnicodeDecodeError as exc:
            raise DataError("The API response is not UTF-8.") from exc
        if attempt + 1 < attempts:
            LOG.warning("API error: %s. Retry %s/%s in %.0f seconds.", error, attempt + 2, attempts, delay)
            time.sleep(delay)
    raise MonitorError(f"The API is unavailable after {attempts} attempts: {error}")


def parse_sdmx(raw: str) -> list[Rate]:
    """Resolve SDMX indices using dimension IDs, never currency/series order."""
    try:
        payload = json.loads(raw, parse_float=Decimal)
        body = payload.get("data", payload)
        structure = body["structure"]
        dimensions = structure["dimensions"]["series"]
        observation_dims = structure["dimensions"]["observation"]
        if len(observation_dims) != 1 or observation_dims[0]["id"] != "TIME_PERIOD":
            raise DataError("Unsupported SDMX observation dimensions.")
        periods = observation_dims[0]["values"]
        attributes = structure["attributes"]["series"]
        multiplier_pos = next(i for i, a in enumerate(attributes) if a["id"] == "UNIT_MULT")
        rates = {}

        def indexed(values, key):
            index = int(key)
            if index < 0:
                raise DataError("Negative SDMX index.")
            return values[index]

        for dataset in body["dataSets"]:
            for key, series in dataset.get("series", {}).items():
                indices = key.split(":")
                if len(indices) != len(dimensions):
                    raise DataError("The number of SDMX series indices has changed.")
                ids = {dim["id"]: indexed(dim["values"], idx)["id"]
                       for dim, idx in zip(dimensions, indices)}
                currency = ids["BASE_CUR"]
                if (currency not in SUPPORTED_CURRENCIES or ids["QUOTE_CUR"] != "NOK"
                        or ids["FREQ"] != "B" or ids["TENOR"] != "SP"):
                    raise DataError(f"Unexpected series: {ids}")
                multiplier = indexed(attributes[multiplier_pos]["values"],
                                     series["attributes"][multiplier_pos])["id"]
                expected_multiplier = "2" if currency == "SEK" else "0"
                if str(multiplier) != expected_multiplier:
                    raise DataError(f"Unexpected UNIT_MULT for {currency}; check the API units.")
                for index, values in series.get("observations", {}).items():
                    if not values or values[0] is None or values[0] == "":
                        continue
                    day = date.fromisoformat(indexed(periods, index)["id"])
                    value = Decimal(str(values[0]))
                    if not value.is_finite() or value <= 0:
                        raise DataError("The rate must be a finite positive number.")
                    # Norges Bank quotes SEK per 100 units. Store NOK per 1 SEK.
                    value /= Decimal(10) ** int(multiplier)
                    identity = (currency, day)
                    if identity in rates and rates[identity].value != value:
                        raise DataError("The API contains conflicting observations for the same date.")
                    rates[identity] = Rate(currency, day, value)
        if not rates:
            raise NoDataError("The API response contains no rates.")
        missing = set(CURRENCIES) - {r.currency for r in rates.values()}
        if missing:
            raise DataError("The response is missing a currency: " + ", ".join(sorted(missing)))
        return sorted(rates.values(), key=lambda r: (r.day, r.currency))
    except (DataError, NoDataError):
        raise
    except (KeyError, IndexError, TypeError, ValueError, AttributeError,
            StopIteration, InvalidOperation) as exc:
        raise DataError(f"Invalid JSON or SDMX API structure: {exc}") from exc


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("""CREATE TABLE IF NOT EXISTS rates (
        currency TEXT NOT NULL CHECK(currency IN ('USD','EUR')),
        date TEXT NOT NULL, rate TEXT NOT NULL, fetched_at TEXT NOT NULL,
        source TEXT NOT NULL, PRIMARY KEY(currency, date))""")
    # Preserve the original table and its constraint; add SEK without migration.
    db.execute("""CREATE TABLE IF NOT EXISTS sek_rates (
        currency TEXT NOT NULL CHECK(currency = 'SEK'),
        date TEXT NOT NULL, rate TEXT NOT NULL, fetched_at TEXT NOT NULL,
        source TEXT NOT NULL, PRIMARY KEY(currency, date))""")
    db.execute("""CREATE TABLE IF NOT EXISTS pln_rates (
        currency TEXT NOT NULL CHECK(currency = 'PLN'),
        date TEXT NOT NULL, rate TEXT NOT NULL, fetched_at TEXT NOT NULL,
        source TEXT NOT NULL, PRIMARY KEY(currency, date))""")
    db.commit()
    return db


def save(db: sqlite3.Connection, rates: list[Rate], source: str) -> None:
    fetched = datetime.now(timezone.utc).isoformat()
    with db:
        db.executemany("""INSERT INTO rates VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(currency,date) DO UPDATE SET rate=excluded.rate,
            fetched_at=excluded.fetched_at, source=excluded.source""",
            [(r.currency, r.day.isoformat(), str(r.value), fetched, source)
             for r in rates if r.currency in CURRENCIES])
        db.executemany("""INSERT INTO sek_rates VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(currency,date) DO UPDATE SET rate=excluded.rate,
            fetched_at=excluded.fetched_at, source=excluded.source""",
            [(r.currency, r.day.isoformat(), str(r.value), fetched, source)
             for r in rates if r.currency == "SEK"])
        db.executemany("""INSERT INTO pln_rates VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(currency,date) DO UPDATE SET rate=excluded.rate,
            fetched_at=excluded.fetched_at, source=excluded.source""",
            [(r.currency, r.day.isoformat(), str(r.value), fetched, source)
             for r in rates if r.currency == "PLN"])


def load(db: sqlite3.Connection, start: date | None = None,
         end: date | None = None) -> list[Rate]:
    # Older saved databases remain readable before their first PLN refresh.
    pln_query = (" UNION ALL SELECT currency,date,rate FROM pln_rates"
                 if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pln_rates'").fetchone()
                 else "")
    rows = db.execute("""SELECT currency,date,rate FROM (
        SELECT currency,date,rate FROM rates
        UNION ALL SELECT currency,date,rate FROM sek_rates""" + pln_query + """ )
        WHERE date >= ? AND date <= ? ORDER BY date,currency""",
        ((start or date.min).isoformat(), (end or date.max).isoformat()))
    return [Rate(c, date.fromisoformat(d), Decimal(v)) for c, d, v in rows]


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_csv(db: sqlite3.Connection, path: Path, start=None, end=None) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["date", "currency", "quote_currency", "rate_per_unit"])
    for r in load(db, start, end):
        writer.writerow([r.day.isoformat(), r.currency, "NOK", str(r.value)])
    atomic_text(path, "\ufeff" + buffer.getvalue())


def report(db: sqlite3.Connection, today: date, *, offline: bool = False,
           warning: str | None = None) -> tuple[str, dict]:
    rows = load(db, end=today)
    result = {"checked_at": oslo_now().isoformat(), "as_of": today.isoformat(),
              "source": "Norges Bank", "offline": offline, "warning": warning, "rates": []}
    lines = [f"Norges Bank — checked {today.isoformat()} (Europe/Oslo)", ""]
    if offline:
        lines += ["WARNING: locally saved data; the API has not been checked.", ""]
    if warning:
        lines += [f"WARNING: {warning}", ""]
    lines += ["| Pair | Rate date | NOK per 1 unit | Previous date | Change, NOK | Change, % |",
              "|---|---|---:|---|---:|---:|"]
    notices = []
    for currency in CURRENCIES:
        history = [r for r in rows if r.currency == currency]
        if not history:
            raise NoDataError(f"No saved data for {currency} as of {today}.")
        current = history[-1]
        previous = history[-2] if len(history) > 1 else None
        change = current.value - previous.value if previous else None
        percent = change / previous.value * 100 if previous else None
        item = {"currency": currency, "quote_currency": "NOK", "date": str(current.day),
                "rate": str(current.value), "previous_date": str(previous.day) if previous else None,
                "previous_rate": str(previous.value) if previous else None,
                "change": str(change) if change is not None else None,
                "change_pct": str(percent) if percent is not None else None,
                "age_days": (today - current.day).days}
        result["rates"].append(item)
        lines.append(f"| {currency}/NOK | {current.day} | {current.value:.4f} | "
                     f"{previous.day if previous else '—'} | "
                     f"{format(change, '+.4f') if change is not None else '—'} | "
                     f"{format(percent, '+.2f') if percent is not None else '—'} |")
        if current.day < today:
            notices.append(f"{currency}: no new value for {today}; latest published value — "
                           f"{current.day}, age {(today-current.day).days} days.")
        if (today - current.day).days > 4:
            notices.append(f"WARNING: {currency} has not been updated for more than 4 calendar days; check the source.")
    lines += [""] + notices + ["", "Changes compare with the previous published observation, not the previous run.",
              "Source: https://www.norges-bank.no/en/topics/Statistics/exchange_rates/", ""]
    return "\n".join(lines), result


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("A date in YYYY-MM-DD format is required") from exc


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1 or number > 10:
        raise argparse.ArgumentTypeError("An integer from 1 to 10 is required")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("A finite positive number is required")
    return number


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data/rates.sqlite3")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--timeout", type=positive_float, default=20)
    parser.add_argument("--attempts", type=positive_int, default=3)
    sub = parser.add_subparsers(dest="command", required=True)
    latest = sub.add_parser("latest", help="Fetch the latest two observations for each currency")
    latest.add_argument("--input-json", type=Path, help="Import a saved API response without network access")
    history = sub.add_parser("history", help="Download historical rates for a date range")
    history.add_argument("--start", type=iso_date, required=True)
    history.add_argument("--end", type=iso_date, required=True)
    history.add_argument("--input-json", type=Path)
    sub.add_parser("report", help="Build a summary from the local database without an API request")
    export = sub.add_parser("export", help="Export the local database to CSV")
    export.add_argument("--start", type=iso_date)
    export.add_argument("--end", type=iso_date)
    export.add_argument("--file", type=Path, default=ROOT / "data/rates.csv")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    db = None
    try:
        today = oslo_now().date()
        if args.command in ("history", "export"):
            if args.start and args.end and args.start > args.end:
                raise MonitorError("The start date must not be later than the end date.")
        if args.command == "history" and args.end > today:
            raise MonitorError("The history end date cannot be in the future (Europe/Oslo).")
        db = connect(args.db)
        if args.command == "export":
            export_csv(db, args.file, args.start, args.end)
            print(f"CSV: {args.file.resolve()}")
            return 0
        if args.command in ("latest", "history"):
            url = (make_url(last=2, end=today) if args.command == "latest"
                   else make_url(start=args.start, end=args.end))
            imported = args.input_json is not None
            try:
                raw = args.input_json.read_text(encoding="utf-8-sig") if imported else fetch(
                    url, timeout=args.timeout, attempts=args.attempts)
                rates = parse_sdmx(raw)
                if any(r.day > today for r in rates):
                    raise DataError("The response contains future dates; import rejected.")
                if args.command == "history" and any(
                        r.day < args.start or r.day > args.end for r in rates):
                    raise DataError("The response contains dates outside the requested period.")
                if args.command == "latest" and any(
                        sum(r.currency == c for r in rates) < 2 for c in CURRENCIES):
                    raise DataError("The API must return two observations for each currency.")
                # Validate everything before the first write to the rates table.
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                atomic_text(args.output_dir / "raw" / f"{stamp}.json", raw)
                save(db, rates, f"import:{args.input_json.resolve()}" if imported else url)
                export_csv(db, args.output_dir / "rates.csv")
                if args.command == "history":
                    print(f"Saved {len(rates)} observations for {args.start} — {args.end}.")
                    return 0
            except MonitorError as exc:
                LOG.error("%s", exc)
                try:
                    text, data = report(db, today, offline=True, warning=str(exc))
                    atomic_text(args.output_dir / "last_error_report.md", text)
                    print(text)
                except NoDataError:
                    pass
                return 1
            text, data = report(db, today, offline=imported)
        else:
            text, data = report(db, today, offline=True)
        atomic_text(args.output_dir / "latest_report.md", text)
        atomic_text(args.output_dir / "latest_report.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(text)
        return 0
    except (MonitorError, OSError, sqlite3.Error) as exc:
        LOG.error("%s", exc)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
