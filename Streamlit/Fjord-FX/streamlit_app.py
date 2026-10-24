"""Fjord FX — multilingual local dashboard backed by the monitoring database."""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import logging
import sqlite3

import pandas as pd
import streamlit as st
from packaging.version import Version

import chat_report as chat
import dashboard_data as data
import dashboard_charts as charts
import dashboard_i18n as i18n
import fx_monitor as fx

st.set_page_config(page_title="Fjord FX", page_icon=":material/currency_exchange:", layout="wide")
if Version(st.__version__) < Version("1.66.1"):
    st.error(
        f"Fjord FX requires Streamlit 1.66.1 or newer; this environment has {st.__version__}. "
        "Install the dependencies with python -m pip install -r requirements.txt, "
        "then launch with python -m streamlit run streamlit_app.py."
    )
    st.stop()


# The user requested full rectangular flags rather than font-sized rounded icons.
# Scope every rule to this widget's public key class.
st.html("""
<style>
.st-key-quote_cards [data-testid="stMetric"] {
    text-align: center;
}
.st-key-quote_cards [data-testid="stMetricLabel"] {
    justify-content: center;
}
.st-key-quote_cards [data-testid="stMetricDelta"] {
    justify-content: center;
    margin-inline: auto;
}
.st-key-language [role="radiogroup"] {
    gap: 8px;
    padding: 3px;
    border-radius: 0 !important;
}
.st-key-language button {
    margin: 0 !important;
    padding: 0 !important;
    min-width: 0 !important;
    min-height: 28px !important;
    height: auto !important;
    border-radius: 0 !important;
    line-height: 0 !important;
}
.st-key-language button img {
    display: block !important;
    width: 27.7px !important;
    max-width: 27.7px !important;
    height: 20px !important;
    max-height: 20px !important;
    border-radius: 0 !important;
    object-fit: fill !important;
}
.st-key-language button p {
    margin: 0 !important;
    line-height: 0 !important;
}
.st-key-language button[data-selected] {
    outline: 2px solid var(--st-primary-color, #0c776b);
    outline-offset: 2px;
}
</style>
""")


@st.cache_data(ttl=30, max_entries=4, show_spinner=False)
def load_snapshot(signature, today):
    return data.read_snapshot()


def date_label(value):
    return value.strftime("%d.%m.%Y")


st.session_state.setdefault("refresh_error", None)
st.session_state.setdefault("verified_at", None)
st.session_state.setdefault("initial_load_attempted", False)
if st.session_state.get("period") == "all":
    st.session_state.period = "3y"
# Migrate an existing browser session from the former pair/reverse controls.
previous_pair = st.session_state.get("convert_pair")
if previous_pair not in chat.PAIRS:
    previous_pair = "NOK/SEK"
initial_from, initial_to = previous_pair.split("/")
if st.session_state.get("reverse", False):
    initial_from, initial_to = initial_to, initial_from
st.session_state.setdefault("convert_from", initial_from)
st.session_state.setdefault("convert_to", initial_to)


def swap_direction():
    st.session_state.convert_from, st.session_state.convert_to = (
        st.session_state.convert_to, st.session_state.convert_from)


def update_conversion_target():
    targets = data.conversion_targets(st.session_state.convert_from)
    if st.session_state.convert_to not in targets:
        st.session_state.convert_to = "NOK" if "NOK" in targets else targets[0]


def update_comparison_mode():
    """Keep the visible scale truthful and restore the single-pair view on exit."""
    if st.session_state.compare:
        st.session_state.single_pair_scale = st.session_state.get("chart_scale", "rate")
        st.session_state.chart_scale = "percent"
    else:
        st.session_state.chart_scale = st.session_state.get("single_pair_scale", "rate")


@st.fragment(run_every="1s")
def show_local_times(language):
    now = fx.oslo_now()
    with st.container(horizontal=True, gap="medium"):
        for city, zone in (("oslo", "Europe/Oslo"), ("kyiv", "Europe/Kyiv")):
            local_time = now.astimezone(ZoneInfo(zone)).strftime("%H:%M:%S")
            with st.container(horizontal=True, width="content", vertical_alignment="center", gap="xxsmall"):
                st.image(i18n.city_flag(city), width=20, alt="Norway" if city == "oslo" else "Ukraine")
                st.caption(f"{i18n.tr(language, city)} · {local_time}")


with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
    brand = st.container(width="content", gap="xxsmall")
    language_control = st.container(width="content")
with language_control:
    with st.container(horizontal=True, horizontal_alignment="right"):
        language = st.segmented_control("Language / Språk / Язык", list(i18n.LANGUAGES),
                                       format_func=i18n.flag_label, default="en",
                                       required=True, key="language", label_visibility="collapsed")
with brand:
    st.markdown("## :primary[FJORD / FX]", anchors=False)
    st.caption("Norges Bank · NBU")
show_local_times(language)


def t(key, **values):
    return i18n.tr(language, key, **values)


def number(value, spec=".4f"):
    return i18n.number(value, spec, language=language)


labels = {pair: i18n.pair_label(pair, language) for pair in chat.PAIRS}
st.title(t("title"))
with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    refresh = st.button(t("refresh"), icon=":material/refresh:", type="primary",
                        key="refresh", help=t("saved_note"))
    status_area = st.container(width="content", gap="xxsmall")
notice_area = st.container()
show_mini = st.toggle(t("show_mini"), value=False, key="show_mini", help=t("mini_note"))
cards_area = st.container(horizontal=True, horizontal_alignment="center", gap="small", key="quote_cards")

refreshed_snapshot = None
initial_load = not data.DB_PATH.exists() and not st.session_state.initial_load_attempted
if refresh or initial_load:
    st.session_state.initial_load_attempted = True
    try:
        with st.spinner(t("loading")):
            refreshed_snapshot = data.refresh_history()
        load_snapshot.clear()
        st.session_state.refresh_error = None
        st.session_state.verified_at = refreshed_snapshot.loaded_at
        if refresh:
            st.toast(t("updated"), icon=":material/check_circle:")
    except (fx.MonitorError, OSError, sqlite3.Error) as exc:
        logging.getLogger(__name__).warning("Rate update failed: %s", exc)
        if "Norges Bank обновлён" in str(exc):
            reason = "error_nbu"
        elif isinstance(exc, (fx.DataError, fx.NoDataError)):
            reason = "error_data"
        elif isinstance(exc, (OSError, sqlite3.Error)):
            reason = "error_storage"
        else:
            reason = "error_api"
        st.session_state.refresh_error = reason

try:
    snapshot = (refreshed_snapshot if refreshed_snapshot is not None else
                load_snapshot(data.database_signature(), fx.oslo_now().date()))
except (OSError, sqlite3.Error, ValueError) as exc:
    logging.getLogger(__name__).warning("Cannot read rate history: %s", exc)
    st.error(t("read_error"), icon=":material/error:")
    st.stop()

if st.session_state.refresh_error:
    reason = st.session_state.refresh_error
    with notice_area:
        st.warning(t("refresh_error") + " " + t(reason if reason in i18n.TEXT else "error_api"),
                   icon=":material/cloud_off:")

if not snapshot.rows:
    with cards_area:
        st.info(t("empty"), icon=":material/download:")
    st.stop()

today = fx.oslo_now().date()
pairs = chat.pair_values(snapshot.rows, snapshot.uah_values)
summaries = {p: data.quote_summary(pairs[p]) for p in chat.PAIRS}
latest_day = max(item["day"] for item in summaries.values() if item)
stamp = snapshot.loaded_at or st.session_state.verified_at
stamp_label = datetime.fromisoformat(stamp).astimezone(fx.oslo_now().tzinfo).strftime("%d.%m.%Y, %H:%M") if stamp else t("unknown")
with status_area.container(gap="xxsmall"):
    st.caption(":material/calendar_today: " + t("latest_date", date=date_label(latest_day))
               + " · " + t("loaded", stamp=stamp_label))

if (today - latest_day).days > 4:
    notice_area.warning(t("old_data"), icon=":material/history:")
elif latest_day < today and today.weekday() < 5:
    notice_area.caption(t("no_today", date=date_label(today)))

# Language changes never mutate stored rates, observation dates or widget values.
with cards_area:
    # Native wrapping containers keep a readable card width instead of shrinking
    # five columns until the rate and delta become ellipses.
    for pair in chat.PAIRS:
        with st.container(width=230, border=True, height="stretch", gap="xsmall"):
            item = summaries[pair]
            if item is None:
                st.metric(pair, "—", t("no_data"), delta_color="off")
                st.caption(labels[pair], text_alignment="center")
                continue
            change = item["change"]
            spark_history = sorted(pairs[pair].items())[-7:]
            previous_note = (t("compared_with", date=date_label(item["previous_day"]))
                             if item["previous_day"] else t("no_previous"))
            window = t("mini_period", count=len(spark_history),
                       start=spark_history[0][0].strftime("%d.%m"), end=spark_history[-1][0].strftime("%d.%m"))
            details = previous_note + "\n\n" + window
            if pair == "NOK/UAH":
                details += "\n\n" + t("nbu_caption")
            delta = 0 if change == 0 else (
                f"{number(change, '+.4f')} ({number(item['percent'], '+.2f')}%)"
                if change is not None else None)
            st.metric(pair, number(item["rate"]), delta, help=details,
                      delta_color="off",
                      delta_arrow="down" if change is not None and change < 0 else "up" if change else "off")
            if show_mini:
                st.altair_chart(charts.mini_chart(pairs[pair], labels[pair], language=language), width="stretch",
                                theme=None, key=f"mini_{pair}",
                                alt=t("mini_alt", pair=pair, count=len(spark_history)))
            st.caption(f"{labels[pair]} · {date_label(item['day'])}", text_alignment="center")

with st.container(horizontal=True, horizontal_alignment="center", gap="medium"):
    trend = st.container(width=980, border=True)
    calculator = st.container(width=360, border=True)
with trend:
    st.subheader(t("trend"))
    compare = st.session_state.get("compare", False)
    pair = st.pills(t("pair"), chat.PAIRS, default="USD/NOK", required=True, key="chart_pair",
                    wrap=True, disabled=compare)
    period = st.segmented_control(t("period"), ["1m", "3m", "1y", "3y"],
                                  format_func=lambda value: t("period_" + value),
                                  default=None if "period" in st.session_state else "1m",
                                  required=True, key="period", wrap=True)
    with st.container(horizontal=True, vertical_alignment="bottom", gap="small"):
        chart_scale = st.segmented_control(t("view"), ["rate", "percent"],
                                           format_func=lambda value: t("view_" + value),
                                           default=None if "chart_scale" in st.session_state else "rate",
                                           required=True, key="chart_scale",
                                           disabled=compare, wrap=True)
        compare = st.toggle(t("compare"), key="compare", on_change=update_comparison_mode)
    duration = {"1m": 30, "3m": 90, "1y": 366}
    if period == "3y":
        start = (pd.Timestamp(today) - pd.DateOffset(years=3)).date()
    else:
        start = today - timedelta(days=duration[period] - 1)
    if compare:
        records = data.comparison_records(pairs, start)
        if records:
            st.markdown(t("published_period", start=date_label(min(r["Дата"] for r in records)),
                          end=date_label(max(r["Дата"] for r in records))), text_alignment="center", width="stretch")
            st.altair_chart(charts.comparison_chart(records, language=language), width="stretch",
                            alt=t("comparison_alt"))
            st.caption(t("baseline", date=date_label(min(r["Дата"] for r in records))))
        else:
            st.info(t("no_common"))
    else:
        records = [{"Дата": d, "Курс": v} for d, v in sorted(pairs[pair].items()) if d >= start]
        if records:
            percent = chart_scale == "percent"
            st.markdown(t("published_period", start=date_label(records[0]["Дата"]),
                          end=date_label(records[-1]["Дата"])), text_alignment="center", width="stretch")
            st.altair_chart(charts.quote_chart(records, labels[pair], percent=percent, language=language), width="stretch",
                            alt=t("quote_alt", view=t("view_" + chart_scale), pair=pair))
            lowest = min(records, key=lambda record: record["Курс"])
            highest = max(records, key=lambda record: record["Курс"])
            period_change = (records[-1]["Курс"] / records[0]["Курс"] - 1) * 100
            st.caption(t("range", low_date=date_label(lowest["Дата"]), low=number(lowest["Курс"]),
                         high_date=date_label(highest["Дата"]), high=number(highest["Курс"]),
                         change=number(period_change, "+.2f")))
            if percent:
                st.caption(t("percent_note", date=date_label(records[0]["Дата"])))
        else:
            st.info(t("empty_period"))
    with st.expander(t("chart_help"), icon=":material/help:"):
        st.caption(t("horizontal_note"))
        st.caption(t("mini_note"))

with calculator:
    st.subheader(t("converter"))
    st.caption(t("latest_published"))
    with st.container(horizontal=True, vertical_alignment="bottom", horizontal_alignment="distribute", gap="xsmall"):
        base_code = st.selectbox(t("convert_from"), data.CONVERTER_CURRENCIES,
                                 key="convert_from", on_change=update_conversion_target, width=100)
        st.button("⇄", key="swap_direction", help=t("reverse"), on_click=swap_direction, width=40)
        quote_code = st.selectbox(t("convert_to"), data.conversion_targets(base_code), key="convert_to", width=100)
    amount = st.number_input(t("amount", code=base_code), min_value=0.0, max_value=1e12,
                             value=1000.0, step=100.0, key="amount", help=t("amount_help"))
    quote = summaries.get(f"{base_code}/{quote_code}")
    reverse = quote is None
    if reverse:
        quote = summaries.get(f"{quote_code}/{base_code}")
    if quote:
        rate = Decimal(1) / quote["rate"] if reverse else quote["rate"]
        converted = Decimal(str(amount)) * rate
        st.metric(t("receive", code=quote_code), number(converted, ",.2f"))
        st.caption(f"1 {base_code} = {number(rate)} {quote_code}")
        st.caption(t("converter_note", date=date_label(quote["day"])))
    else:
        st.info(t("empty_pair"))

with st.container(border=True):
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        table_heading = st.container(width="content")
        download = st.container(width="content")
    with table_heading:
        st.subheader(t("week_title"))
    with st.expander(t("publication_title"), icon=":material/schedule:"):
        st.markdown(t("publication_title"))
        st.caption(t("publication_nb"))
        st.caption(t("publication_nbu"))
    week = [{"Дата": day, **{p: pairs[p].get(day) for p in chat.PAIRS}}
            for day in data.weekdays(today, count=10)]
    display = pd.DataFrame([{t("date"): date_label(r["Дата"]), **{
        p: number(r[p]) if r[p] is not None else "—" for p in chat.PAIRS}} for r in week])
    with download:
        st.download_button(t("download"), data.csv_bytes(week, language=language), "fjord-fx-10-days.csv",
                           "text/csv", icon=":material/download:", width="stretch", on_click="ignore")
    st.caption(t("table_scroll"))
    st.dataframe(display, hide_index=True, height=432, row_height=38, width="stretch",
                 column_config={
                     t("date"): st.column_config.TextColumn(t("date"), width=105, pinned=True),
                     **{pair: st.column_config.TextColumn(
                         pair, width=130, alignment="right",
                         help=t("publication_nbu" if pair == "NOK/UAH" else "publication_nb"))
                        for pair in chat.PAIRS}},
                 alt=t("table_alt"))
    if any(r[p] is None for r in week for p in chat.PAIRS):
        st.caption(t("missing_note"))
    st.download_button(t("download_all"), data.csv_bytes(data.history_records(pairs), language=language),
                       "fjord-fx-history.csv", "text/csv", type="tertiary", icon=":material/history:", on_click="ignore")

with st.expander(t("sources"), icon=":material/info:"):
    st.caption(t("intro"))
    st.markdown(t("source_nb"))
    st.markdown(t("source_nbu"))
    st.caption(t("saved_note"))

st.caption(t("footer"))
