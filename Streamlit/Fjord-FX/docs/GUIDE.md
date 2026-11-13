# Fjord FX — detailed guide

[Back to the project overview](../README.md)

Python 3.11+; Windows, macOS and Linux. The main cards show **NOK per 1 USD, 1 EUR, 1 SEK, 1 UAH and 1 PLN**.
USD/EUR appears alongside them as EUR per 1 USD. Green decreases mean foreign
currency costs fewer kroner (NOK strengthens); red increases mean it costs more
(NOK weakens). The APIs are public and require no key. Norges Bank supplies
USD, EUR, SEK and PLN quotes; UAH/NOK is the inverse of the official National Bank
of Ukraine rate in UAH per 1 NOK.

## English / Norwegian / Polish / Ukrainian

Use the **🇬🇧 / 🇳🇴 / 🇵🇱 / 🇺🇦** flag selector at the top of the sidebar to choose
English, Norwegian, Polish or Ukrainian. Language names appear on hover. Embedded flag
images work offline and display at approximately 28 × 20 pixels, preserving
their proportions without rounded corners. A rectangular border marks the selection.
The Norwegian translation uses **Bokmål**; English is the default.

The selection changes buttons, explanations, the converter, table, axis labels
and chart tooltips. Displayed results use a decimal point in English and a decimal
comma in Norwegian, Polish and Ukrainian. **Amount input uses a decimal point in all languages.**
CSV downloads follow the current interface language. Filters and the amount remain
selected when switching languages within an open session; switching does not fetch
the API again. Terminal messages and generated text reports use English and decimal points.
Existing sessions with the removed Russian selection return to English automatically.

To update from an archive, stop Streamlit, replace the application files and
restart the dashboard. Keep the existing **data** directory and **.venv**
environment; neither is included in the archive.

## PLN/NOK

PLN/NOK shows NOK per 1 Polish zloty from the official Norges Bank API.
It is available in cards, charts, percentage comparison, the PLN ↔ NOK converter
and CSV downloads. PLN history is stored in `pln_rates`, preserving existing tables.
Older databases remain readable; select **Update rates** to load PLN history.

## UAH/NOK and mini charts

UAH/NOK means **NOK per 1 UAH**. It is calculated as 1 divided by the official
NBU rate in UAH per 1 NOK. Each historical observation is inverted before
calculating the change and percentage; simply negating the original percentage
would be incorrect. It does not combine quotes from different banks. NBU effective
dates can differ from Norges Bank publication dates and are labeled separately.

[Official NBU API documentation](https://bank.gov.ua/admin_uploads/article/Instr_API_KURS_VAL_data_Full_eng.pdf).

History endpoint:
`https://bank.gov.ua/NBU_Exchange/exchange_site?start=YYYYMMDD&end=YYYYMMDD&valcode=nok&sort=exchangedate&order=asc&json`.

The application uses `rate_per_unit` in UAH per 1 NOK and validates `cc`,
currency code 578, positive units, consistency between `rate/units` and dates.
Rates are stored in the `nbu_nok_rates` table in the same database, preserving
the Norges Bank history. The summary compares Monday–Friday dates; NBU weekend
rates are not treated as new weekday publications. Import with
`chat_report.py --input-json FILE --input-nbu-json NBU_FILE`.

Each card always shows the last seven published observations as a mini chart.
Rate help includes the period and the previous
comparison date. A line below each chart shows the quote unit and date,
for example, `NOK per 1 UAH · 23.10.2026`. Dates appear below the seven points.
Hovering anywhere in a chart shows the nearest date and rate to four decimal places.
If fewer than seven observations exist, all available values are shown without
filling gaps.

The arrow and percentage compare only with the previous rate date, so the latest
daily increase can occur while the mini chart declines over its full period.
Cards have separate scales; their visual amplitudes cannot be compared.
Use the main chart with its labeled scale or percentage mode for precise changes.

## Streamlit dashboard — Fjord FX

The interactive dashboard includes five NOK rate cards and a USD/EUR card in an equal-width grid, with changes and
sparklines, a chart with 1-month / 3-month / 1-year / 3-year / 5-year / 10-year periods, percentage
comparison of the five NOK pairs, a converter with reverse directions, the latest ten weekdays and CSV
downloads.

The collapsible sidebar contains language and visible-card selection,
chart pair, period, rate/percentage view, comparison and chart help. It starts
collapsed; use the sidebar arrow at the top left to open settings. Hiding cards
preserves their table order and keeps all pairs available in the chart, converter
and CSV. Changing settings or language preserves selections without fetching rates.
The main chart shows its active pair/view and period even when the sidebar is closed.

Choose light or dark appearance using **⋮ → Settings → App theme** at the top
right. Cards, tables and charts follow the selected palette.

The expandable section above the table and column-header help explain publication
times: Norges Bank quotes are published around 16:00 Oslo time on business days.
NBU NOK/UAH is set by 15:30 Kyiv time on the setting date and takes effect on the
following business day. These are bank schedules; **Update rates** fetches newly
published values subject to a shared five-minute check interval. CSV data retains
the original currency-pair names.

Schedule sources: [Norges Bank](https://www.norges-bank.no/tema/Statistikk/Valutakurser/valutakurser/),
[NBU, paragraph 13](https://bank.gov.ua/admin_uploads/law/Regulation_10122019_148_24032025.pdf?v=13),
[NBU effective-date metadata](https://bank.gov.ua/en/file/download?file=ER_metadata_en.pdf).

All six cards follow the table order: USD/NOK, EUR/NOK, SEK/NOK, UAH/NOK, PLN/NOK, USD/EUR.
Cards, the chart/converter row and the table share the full content width.
Cards have equal widths with an 8 px gap and always include mini charts.
The chart and converter use proportional columns with matching heights.
The columns stack on screens up to 640 px wide.
**Update rates** sits beside **Download CSV** in the **Last 10 business days**
header. The rate date and download time remain above the cards.
Pair and period options are available without hidden horizontal scrolling.

Flags remain rectangular. Sources appear below the logo; local Oslo, Kyiv and Warsaw
times share a compact line with country flags. Clocks show seconds, update every
second without fetching rates again, and observe daylight saving time using
`Europe/Oslo`, `Europe/Kyiv` and `Europe/Warsaw`.

The converter has **From currency** and **To currency** selectors.
It starts with SEK → NOK, matching the quote direction in the SEK/NOK card.
**⇄** swaps the currencies while keeping the amount. The second selector offers
available destinations for the chosen source currency, using the dashboard's
six pairs and their inverse quotes.

Below the converter are links to the official [SpareBank 1 currency calculator](https://www.sparebank1.no/nb/bank/privat/kundeservice/verktoy/valutakalkulator.html)
and [DNB currency calculator](https://www.dnb.no/markets/valuta-og-renter/valutakalkulator).

The comparison includes only USD/NOK, EUR/NOK, SEK/NOK, UAH/NOK and PLN/NOK; USD/EUR
remains available in the single-pair chart. The multiyear chart shows month and
year on the X axis. Dense point markers are
hidden while exact values remain available in tooltips. Comparison series use
both colors and line patterns, with a legend below the chart. Enabling comparison
selects percentage change; disabling it restores the previous single-pair view.
The table date stays pinned during horizontal scrolling. Amount input always
uses a decimal point; result and CSV formatting follow the selected language.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open `http://localhost:8501`. Run from the project directory so that
`.streamlit/config.toml` supplies the theme. To use another port, add
`--server.port 8502` to the launch command.

The dashboard reads the existing database. If none exists, it automatically
downloads history on the first visit. **Update rates** downloads approximately
ten years of official Norges Bank and NBU history and updates the same database,
CSV files and reports.

Updates are shared by all visitors within one application process. Saved data
is reused for five minutes after a successful download, and concurrent requests
do not start duplicate downloads. After a failure, another network attempt becomes
available in 30 seconds. Changing filters or language does not download data.
These limits apply to the dashboard; terminal commands make a request on each run.
Offline, the dashboard shows saved values and their dates. A refresh error does
not clear history.

A dash in the table means no saved value exists for that date, including today
before publication. Chart periods are measured from the current date in Oslo;
changing the period does not change the latest card values. **3 years**, **5 years**
and **10 years** use calendar years, accounting for leap dates. If the database
contains a shorter history, use **Update rates** to download the remainder.

Ten years contain roughly 3.3 times as many observations as three years. SQLite
updates existing currency/date records without duplicating them, and CSV exports
are replaced. Each refresh also retains new raw JSON responses in `data/raw`, so
that folder grows with the number of refreshes as well as the history length.

The rate chart uses the selected period's minimum and maximum plus a small margin,
rather than starting at zero, so small movements remain visible in the original
quote units. It has no fill down to zero and explicitly labels the enlarged scale.
Percentage mode shows movement from the first observation of the period (0%).
The period's minimum, maximum and overall change appear below the chart.
Refreshing data or changing the pair or period recalculates the scale from all
visible values, including sharp moves. Axis precision adapts to the range.

Publication dates are evenly spaced on all charts, without empty weekend slots
or invented missing rates. The vertical guide and tooltip work across the full
chart height, including between points. Comparison tooltips show every pair for
the selected date and explicitly identify missing values. Comparison uses one
common starting date and percentage changes rather than mixing different quote
units. Both converter selectors offer USD, EUR, NOK, SEK, UAH and PLN, and any
combination can be converted in either direction. Cross-rates are calculated
through NOK using the latest date with published quotes for both currencies;
that date appears below the result. Selecting the same currency gives a 1:1
rate. The converter excludes bank fees.

The local dashboard requires no account. To make it available online, deploy it
to Streamlit Community Cloud as described below.

Run interface tests after installing `requirements.txt`:

```powershell
python -m unittest discover -s tests_ui -v
```

For loading, empty history and error states without API calls or database writes,
see the [isolated preview and phone/keyboard checklist](../tests_ui/MANUAL_CHECKS.md).

## Streamlit Community Cloud deployment

1. Upload the project to a GitHub repository, including `requirements.txt` and
   `.streamlit/config.toml`.
2. Create an application in [Streamlit Community Cloud](https://share.streamlit.io/).
   Select the repository, branch and `streamlit_app.py` entry point.
3. In advanced settings, select a supported Python version that you have tested
   locally, then deploy.
4. Open the application. History loads automatically if no database exists.
   If a source fails, retry with **Update rates** after 30 seconds.
   The local `data/` directory is excluded from Git.

Dependencies are installed from `requirements.txt`; rate API keys are unnecessary.
The local SQLite database serves as a cache in Cloud and is not guaranteed to
persist. Lost history can be downloaded again with the refresh button.
Persistent history requires an external database.

[Official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
[Local-storage limitations](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).

## Windows quick start

Extract the archive, open PowerShell in `Fjord-FX` and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe chat_report.py

# Open the browser dashboard instead of the text summary
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Environment activation is optional. If `python` is unavailable, install
Python 3.11+ from [python.org](https://www.python.org/downloads/) and retry.
The shared `requirements.txt` installs `tzdata` (the Windows time-zone database),
Streamlit, Altair and pandas for the dashboard. Streamlit Cloud uses the same file.
HTTP, SQLite, CSV, JSON and calculations use the Python standard library.

On macOS/Linux, use `python3 -m venv .venv`, then `.venv/bin/python`
instead of `.\.venv\Scripts\python.exe`.

## Commands

Run these examples from the project directory with your environment's Python:

```powershell
# Full summary: six pairs, changes and seven weekdays of history
python chat_report.py

# The same summary from saved data, without network access
python chat_report.py --offline

# Basic USD/NOK and EUR/NOK summary; the download also stores SEK
python fx_monitor.py latest

# History for an inclusive date range
python fx_monitor.py history --start 2026-01-01 --end 2026-10-14

# Summary from the saved database, without network access
python fx_monitor.py report

# Export all saved values
python fx_monitor.py export --file data/export.csv

# Export only the selected period
python fx_monitor.py export --start 2026-10-01 --end 2026-10-14 --file data/october.csv

# Configure timeout and attempts; global options go BEFORE the command
python fx_monitor.py --timeout 15 --attempts 3 latest

# Use a different database and output directory
python fx_monitor.py --db data/another.sqlite3 --output-dir data/another latest
```

`latest` fetches the last two observations for each currency. To fill gaps after
a long pause or download older values, run `history` for the required period.
Large histories are easier to download one year at a time.
An empty period, such as a weekend-only range, returns an explanatory error
rather than zero rates. `history` writes history and updates CSV; run `report`
or `latest` afterward to update the summary.

## Stored files

Default paths are relative to **the program file**, so running from another
directory does not accidentally create a new database.

| File | Contents |
|---|---|
| `data/rates.sqlite3` | History keyed by currency and date, UTC download time and source |
| `data/rates.csv` | Complete accumulated history, UTF-8 BOM, decimal point |
| `data/latest_report.md` | Latest successful basic summary |
| `data/latest_report.json` | The same summary in machine-readable form |
| `data/raw/*.json` | Accepted API responses for source verification |
| `data/last_error_report.md` | Database summary with the latest error message |

SQLite stores rates as decimal strings; calculations use `Decimal`.
JSON also represents rates and absolute/percentage changes as strings.
Repeated runs do not create duplicates. If the bank revises a date's value,
the next download of that date updates it; accepted source responses are retained.
A separate `export` CSV contains only the selected range.

## Change calculations

```text
change_NOK = current_rate − previous_published_rate
change_%   = change_NOK / previous_published_rate × 100
```

The comparison uses the previous **observation date**, regardless of how many
times the program runs. On Monday, that is usually Friday. Repeating a run on
the same day does not reset the change to zero.

On weekends, holidays and before the next publication, the latest available date
is shown with a note that no new value exists for today. Rates are not interpolated.
Values older than four calendar days trigger a warning; this technical threshold
does not replace a bank-holiday calendar. The current date uses `Europe/Oslo`,
including daylight saving time.

## Verified official API format

Verified on October 15, 2026:

- The [Norges Bank API guide](https://www.norges-bank.no/en/topics/Statistics/open-data/guide-data-warehouse/)
  documents the `EXR` flow, the `B.USD.NOK.SP` example, `startPeriod` / `endPeriod`
  and supported download formats.
- The [official query builder](https://query.norges-bank.no/) states that the
  service is freely available without authentication.
- The [exchange-rate page](https://www.norges-bank.no/en/topics/Statistics/exchange_rates/)
  describes indicative middle rates and publication around 16:00 CET.
- Actual responses to the two queries below were checked in a browser: the latest
  two observations and the October 1–14 history. This verified the API itself
  in addition to its documentation.

```text
https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP?format=sdmx-json&locale=en&lastNObservations=2

https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP?format=sdmx-json&locale=en&startPeriod=2026-10-01&endPeriod=2026-10-14
```

| Component | Meaning |
|---|---|
| `EXR` | Exchange rates |
| `B` | Business-day observations |
| `USD+EUR+SEK+PLN` | Four base currencies |
| `NOK` | Quote currency |
| `SP` | Spot |
| `lastNObservations=2` | Two observations **per series** |
| `startPeriod`, `endPeriod` | Dates in `YYYY-MM-DD` format |

The SDMX-JSON response contains `data`, with `dataSets` and `structure` inside.
The program decodes series keys using `structure.dimensions.series` IDs
`FREQ`, `BASE_CUR`, `QUOTE_CUR` and `TENOR`, and observation indices using
`TIME_PERIOD`. Currency and dimension order is not hard-coded.

`UNIT_MULT` is validated: USD, EUR and PLN require 0; SEK requires 2 (a quote per 100 SEK).
SEK is divided by 100 before storage, so the database and CSV contain NOK per
1 SEK. The summary uses this same direction as SEK/NOK: NOK per 1 SEK.
Unexpected units or series prevent writes. The separate `sek_rates` table stores
SEK in the same database while preserving the original `rates` table.
`data/chat_report.md` and `data/chat_report.json` contain the full six-pair summary.

## Errors and reliability

- The default timeout is 20 seconds per attempt, with up to three attempts.
- Network failures, HTTP 429 and 5xx are retried with a delay. Numeric `Retry-After`
  is honored up to 60 seconds. HTTP 400 and other permanent 4xx errors are not retried.
- HTTP 204/404, invalid JSON, missing currencies, future dates, invalid units and
  negative, zero or infinite values are handled explicitly.
- The entire response is validated before changing the rate table. SQLite writes
  are transactional; reports and CSV files are replaced atomically. A CSV write
  failure does not undo a committed database transaction; repeat the export after
  resolving the disk problem.
- An unavailable API preserves existing history. If both currencies have saved
  values, a database summary is shown with a warning and is not labeled as fresh.
  The latest successful summary remains in `latest_report.*`; the error goes to
  `last_error_report.md` and standard error. An old error file may remain after
  recovery; check its date and the current process exit code.
- Exit codes: `0` for success, `1` for fetch/storage failure and `2` for invalid arguments.
- TLS certificate verification is enabled. No API keys or third-party sources are used.

## Terminal summary

Run `python chat_report.py`. Output starts with a compact table of pair, rate per
unit and change for USD/NOK, EUR/NOK, SEK/NOK, UAH/NOK, PLN/NOK and USD/EUR.
Quote units are NOK for the first five pairs and EUR for USD/EUR. Changes use the appropriate
quote currency and percentages relative to the previous published date; dates are
included. A second table covers the latest **seven weekdays**, including the run
date, with date and all six currency-pair columns, ordered from oldest to newest.

USD/EUR = USD/NOK ÷ EUR/NOK for the same date.
SEK/NOK = the original Norges Bank SEK quote / 100.
UAH/NOK = 1 / the official NBU NOK/UAH rate.
Calculations use `Decimal`; only display values are rounded.
A cross rate is not calculated if a source value for that date is missing.

`python chat_report.py` downloads 30 days, stores four original Norges Bank
series and NBU NOK/UAH rates, then builds both tables. `fx_monitor.py latest/report`
remain available for the basic NOK summary.

Weekdays mean Monday through Friday. A missing publication is explicitly marked
without borrowing a value from another date. If the API is unavailable, saved
values are labeled as unverified and missing values as unavailable.
The summary is printed to the terminal and saved to `data/chat_report.md`
and `data/chat_report.json`.

## Offline tests and demonstration

```powershell
python -m unittest discover -s tests -v

python fx_monitor.py history --start 2026-10-01 --end 2026-10-14 --input-json examples/history_2026-10-01_2026-10-14.json
python fx_monitor.py latest --input-json tests/fixtures/norges_bank_2026-10-15.json
```

The project includes verified October 15 API responses and a history fixture with
20 observations for October 1–14. File imports are always identified as local data;
the program does not contact the API in this mode. This allows testing before
network access is configured. `examples/history_*.json` contains a historical
response with only JSON indentation changed.

The original baseline comprised 39 calculation/storage tests and 26 chart/interface
tests. Coverage includes API format, SEK units per 100 kronor, SEK/NOK and inverse UAH/NOK
quotes, changes, cross-rate date alignment, seven weekdays, missing data,
duplicate-free storage, revisions, HTTP failures and retries, shared refresh
intervals, concurrent visitors, first load without a database and cache date changes.
Subsequent interface and state-preview checks are recorded in
[the manual-check status](../tests_ui/MANUAL_CHECKS.md).

On October 16, 2026, a direct network run of `python chat_report.py` against the
official API succeeded: all four pairs supported at that time were stored and
displayed. Requests use `Accept: application/json`, which is compatible with
the API response.
