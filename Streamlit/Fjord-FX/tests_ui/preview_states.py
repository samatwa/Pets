"""Isolated visual fixtures. Run from the project root:

python -m streamlit run tests_ui/preview_states.py --server.address 127.0.0.1 --server.port 8502

Open ?scenario=normal, empty, offline, first_error, loading, or storage_error.
All data access is mocked; this preview never calls the APIs or writes a database.
"""
from datetime import date, datetime
from pathlib import Path
import runpy
import sys
import time
from unittest.mock import patch
from zoneinfo import ZoneInfo

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dashboard_data as data
import fx_monitor as fx
import nbu_rates as nbu

SCENARIOS = {"normal", "empty", "offline", "first_error", "loading", "storage_error"}
scenario = st.query_params.get("scenario", "normal")
if scenario not in SCENARIOS:
    st.error("Unknown preview scenario.")
    st.stop()

st.set_page_config(page_title="Fjord FX · visual test", layout="wide")
st.sidebar.info(f"Visual test: {scenario}. Fixture data; real history is untouched.")
fixtures = ROOT / "tests/fixtures"
rows = fx.parse_sdmx((fixtures / "norges_bank_with_pln_2026-10-16.json").read_text(encoding="utf-8"))
uah = nbu.parse((fixtures / "nbu_nok_2026-10.json").read_text(encoding="utf-8"),
                date(2026, 10, 12), date(2026, 10, 23))
snapshot = data.Snapshot(rows, "2026-10-16T16:07:00+00:00",
                         {day: value for day, value in uah.items() if day <= date(2026, 10, 16)})
empty = data.Snapshot([], None)
saved = empty if scenario in {"empty", "first_error"} else snapshot


def refresh():
    if scenario == "loading":
        time.sleep(12)
    if scenario in {"offline", "first_error"}:
        raise fx.MonitorError("Visual fixture: API unavailable")
    if scenario == "storage_error":
        raise OSError("Visual fixture: storage unavailable")
    return saved


def read():
    if scenario == "storage_error":
        raise OSError("Visual fixture: storage unavailable")
    return saved


with patch.object(data, "DB_PATH", ROOT / "data" / f"__visual_{scenario}_absent__.sqlite3"), \
        patch.object(data, "refresh_history", side_effect=refresh), \
        patch.object(data, "read_snapshot", side_effect=read), \
        patch.object(fx, "oslo_now", return_value=datetime(2026, 10, 16, 18, tzinfo=ZoneInfo("Europe/Oslo"))):
    runpy.run_path(str(ROOT / "streamlit_app.py"), run_name="__main__")
