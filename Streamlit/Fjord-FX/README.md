# Fjord FX

Official exchange rates, historical charts and currency conversion.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fjord-fx.streamlit.app/)

## Features

- Six currency pairs: USD/NOK, EUR/NOK, SEK/NOK, UAH/NOK, PLN/NOK and USD/EUR.
- Historical charts for up to three years, with percentage comparisons.
- Currency conversion between USD, EUR, NOK, SEK, UAH and PLN.
- Recent rates and CSV downloads.

English, Norwegian (Bokmål), Polish and Ukrainian. Light and dark themes.

Rates come from Norges Bank and the National Bank of Ukraine. Bank fees are excluded.

## Run locally

Requires Python 3.11+. From `Streamlit/Fjord-FX`:

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open <http://localhost:8501>. History downloads automatically on the first visit.

## Documentation

[Setup, usage, deployment and technical details](docs/GUIDE.md) · [Interface checks](tests_ui/MANUAL_CHECKS.md)
