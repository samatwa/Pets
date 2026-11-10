# Fjord FX — Norges Bank and NBU exchange rates

A Python 3.11+ command-line monitor and Streamlit dashboard for Windows, macOS and Linux.

## Currency pairs

| Pair | Displayed quote | Source |
|---|---|---|
| USD/NOK | NOK per 1 USD | Norges Bank |
| EUR/NOK | NOK per 1 EUR | Norges Bank |
| USD/EUR | EUR per 1 USD | Calculated from same-date Norges Bank quotes |
| NOK/SEK | SEK per 1 NOK | Inverse of the normalized Norges Bank SEK quote |
| NOK/UAH | UAH per 1 NOK | Direct official NBU quote |

The public APIs require no key. NOK/UAH is not a cross rate between banks. NBU effective dates may differ from Norges Bank publication dates and are labeled separately.

## Quick start

From this project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open `http://localhost:8501`. Use `--server.port 8502` for another port. Environment activation is optional. On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

The shared requirements install Streamlit, Altair, pandas and `tzdata`. HTTP, SQLite, JSON, CSV and decimal calculations use the Python standard library. Run from the project directory so `.streamlit/config.toml` supplies the theme.

## Dashboard

The dashboard provides rate cards, seven-observation mini charts, a historical chart with 1-month / 3-month / 1-year / 3-year periods, percentage comparison, a converter with inverse directions, the latest ten weekdays and CSV downloads.

English, Norwegian Bokmål and Russian interface translations are included in this published snapshot; English is the default. Documentation is maintained in English. Language switching preserves filters and amount within the session and does not fetch rates again. CSV formatting follows the selected language.

Mini charts use the latest seven actual observations, or all available observations when fewer exist. Missing dates are not synthesized. Each card has its own scale, so visual amplitudes cannot be compared. The daily arrow and percentage compare with the previous observation, which can differ from the mini chart's overall direction.

The converter uses the latest published rate and excludes bank fees and markups. Its currency selectors expose the supported pairs and inverse directions. Swapping direction preserves the amount.

## Refresh and offline behavior

The first visit downloads history when no database exists. **Update rates** downloads approximately three years of official history and updates the database, CSV files and reports.

Successful refreshes are shared across visitors in the same process for five minutes. Concurrent requests do not launch duplicate downloads. After a failure, another network attempt is available after 30 seconds. Filter and language changes do not fetch data. Terminal commands make a request on each run.

Offline, saved values remain visible with their actual dates. Refresh errors do not clear history. A dash means no saved value exists for the displayed date, including today before publication.

Chart periods are measured from the current Oslo date. Three years means three calendar years with leap-date handling. Cards always show the latest available quotes, independently of the selected chart period.

Rate charts use the visible minimum and maximum plus a margin, with an explicit enlarged-scale explanation. Percentage charts start from the period's first observation at zero. Comparison uses a common starting date and percentage changes so incompatible quote units are not mixed. Publication dates are equally spaced without empty weekend slots. Tooltips expose exact dates and values, including explicit missing values.

## Publication schedules and sources

Norges Bank normally publishes around 16:00 Oslo time on business days. NBU sets NOK/UAH by 15:30 Kyiv time on the setting date, effective on the following business day. Fetching is controlled by the application's refresh interval, independently of the banks' publication schedules.

- [Norges Bank exchange rates](https://www.norges-bank.no/en/topics/Statistics/exchange_rates/)
- [Norges Bank publication information](https://www.norges-bank.no/tema/Statistikk/Valutakurser/valutakurser/)
- [NBU regulation, paragraph 13](https://bank.gov.ua/admin_uploads/law/Regulation_10122019_148_24032025.pdf?v=13)
- [NBU effective-date metadata](https://bank.gov.ua/en/file/download?file=ER_metadata_en.pdf)
- [Official NBU API documentation](https://bank.gov.ua/admin_uploads/article/Instr_API_KURS_VAL_data_Full_eng.pdf)

## Terminal commands

Run from this directory with your environment's Python:

```powershell
# Five-pair summary and seven weekdays
python chat_report.py

# Saved summary without network access
python chat_report.py --offline

# Basic USD/NOK and EUR/NOK summary; also downloads SEK
python fx_monitor.py latest

# Inclusive history range
python fx_monitor.py history --start 2026-01-01 --end 2026-10-14

# Basic summary from the local database
python fx_monitor.py report

# Export all saved values
python fx_monitor.py export --file data/export.csv

# Export a selected period
python fx_monitor.py export --start 2026-10-01 --end 2026-10-14 --file data/october.csv

# Global options go before the command
python fx_monitor.py --timeout 15 --attempts 3 latest

# Alternate database and output directory
python fx_monitor.py --db data/another.sqlite3 --output-dir data/another latest
```

`latest` fetches two observations per currency. Use `history` to fill gaps or obtain older data; download large histories by year. Empty periods return an explanatory error rather than zero rates. After importing history, run `report` or `latest` to refresh the summary.

`chat_report.py` downloads 30 days and builds the latest-rate table and seven-weekday history. Its weekday convention is Monday–Friday; unavailable publications are marked without borrowing rates from another date.

USD/EUR = USD/NOK ÷ EUR/NOK on the same date. NOK/SEK = 100 ÷ the original SEK quote, or 1 ÷ the normalized database value. Calculations use `Decimal` and round only for display. A missing input prevents the corresponding cross-rate calculation.

## Storage and precision

Default paths are relative to the program file, so launching elsewhere does not create an accidental new database.

| Path | Contents |
|---|---|
| `data/rates.sqlite3` | Rate history, currency/date keys, UTC fetch timestamps and sources |
| `data/rates.csv` | Complete accumulated history, UTF-8 BOM, decimal-point rates |
| `data/latest_report.md` and `data/latest_report.json` | Latest successful basic summary |
| `data/chat_report.md` and `data/chat_report.json` | Five-pair summary and weekday table |
| `data/raw/*.json` | Accepted original API responses |
| `data/last_error_report.md` | Saved-data summary with the latest error |

Rates are decimal strings in SQLite and JSON. Repeated runs do not duplicate records. Revisions update the same currency/date key when that date is downloaded again. Accepted original replies remain available for verification. Exported date ranges do not change the stored history.

Changes compare with the previous published observation, not the previous program run:

```text
absolute_change = current_rate - previous_published_rate
percentage_change = absolute_change / previous_published_rate * 100
```

On Mondays the comparison date is usually Friday. Repeated runs do not reset the change to zero. Weekends, holidays and dates before publication show the latest actual observation. Nothing is interpolated. Values older than four calendar days trigger a technical warning; this is not a bank-holiday calendar. Dates use `Europe/Oslo` with daylight saving time.

## API validation

The [Norges Bank API guide](https://www.norges-bank.no/en/topics/Statistics/open-data/guide-data-warehouse/) documents the `EXR` flow. The [query builder](https://query.norges-bank.no/) is publicly accessible.

```text
https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP?format=sdmx-json&locale=en&lastNObservations=2

https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP?format=sdmx-json&locale=en&startPeriod=2026-10-01&endPeriod=2026-10-14
```

`B` denotes business-day observations, `NOK` the quote currency and `SP` spot rates. Date parameters use `YYYY-MM-DD`; `lastNObservations=2` applies per series.

SDMX replies are decoded through `data.dataSets` and `structure.dimensions.series` using `FREQ`, `BASE_CUR`, `QUOTE_CUR`, `TENOR` and `TIME_PERIOD`. Dimension and currency order are not hard-coded. `UNIT_MULT` must be 0 for USD/EUR and 2 for SEK, which is quoted per 100 SEK. SEK is divided by 100 before storage in `sek_rates`.

NBU history uses:

```text
https://bank.gov.ua/NBU_Exchange/exchange_site?start=YYYYMMDD&end=YYYYMMDD&valcode=nok&sort=exchangedate&order=asc&json
```

`rate_per_unit` is UAH per 1 NOK. Validation checks currency identifiers including code 578, dates, positive units and consistency with `rate/units`. Data is stored in `nbu_nok_rates`. NBU weekend effective rates are not presented as new weekday publications.

Import both sources with `chat_report.py --input-json FILE --input-nbu-json NBU_FILE`.

## Errors and reliability

The default is a 20-second timeout per attempt and up to three attempts. Network failures, HTTP 429 and 5xx are retried with delays. Numeric `Retry-After` is capped at 60 seconds. Permanent 4xx failures are not retried.

HTTP 204/404, malformed JSON, missing currencies, future dates, invalid units, conflicting observations and nonpositive or nonfinite rates are handled explicitly. The whole response is validated before changing rate tables.

SQLite writes are transactional. Reports and CSV files are replaced atomically. A failed CSV write does not undo a committed database transaction; export again after resolving the file problem.

An unavailable API preserves history. A saved basic summary is explicitly marked as unverified; the last successful report remains in `latest_report.*`, while failures go to `last_error_report.md` and standard error. An old error file can remain after recovery, so check its date and the current exit code.

Exit codes are 0 for success, 1 for fetch/storage failure, and 2 for invalid arguments. TLS verification is enabled.

## Streamlit Community Cloud

1. Select this repository and its `main` branch in [Streamlit Community Cloud](https://share.streamlit.io/).
2. Set the entry point to `Streamlit/Fjord-FX/streamlit_app.py`.
3. Choose a supported Python version tested with the dependencies.
4. Open the application; initial history loads automatically. Retry a failed first fetch after 30 seconds.

Dependencies come from `requirements.txt`. No API keys are required. The root theme configuration supports the nested deployment entry point.

Cloud's local SQLite files are a cache and may be lost. Refresh can rebuild history; persistent storage requires an external database. See the [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [data-connection guidance](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).

## Offline checks

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests_ui -v

python fx_monitor.py history --start 2026-10-01 --end 2026-10-14 --input-json examples/history_2026-10-01_2026-10-14.json
python fx_monitor.py latest --input-json tests/fixtures/norges_bank_2026-10-15.json
```

File imports are identified as local data and do not contact the API. The historical example contains 20 observations for October 1–14, 2026. Fixtures include verified October 15 replies. The original published baseline recorded 39 core and 26 interface/chart checks; this documentation update does not claim a new application test run.

When updating application files, keep any existing local `data/` and `.venv/` directories.
