"""Charts with explicit, labelled data-range scales instead of a zero baseline."""
from decimal import Decimal
import math

import altair as alt
import pandas as pd

import chat_report as chat
import dashboard_i18n as i18n


def padded_domain(values, *, percent=False):
    values = [float(v) for v in values]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("Для шкалы нужны конечные значения.")
    low, high = min(values), max(values)
    # Flat series still need a non-degenerate scale, without inventing movement.
    minimum_padding = 0.01 if percent else max(abs(low), abs(high), 1) * 0.00005
    padding = max((high - low) * 0.15, minimum_padding)
    lower = low - padding
    if low > 0 and not percent:
        lower = max(0, lower)
    return [lower, high + padding]


def value_axis(values, *, percent=False, language="en"):
    """Adapt tick precision to the visible range, including large rate moves."""
    low, high = padded_domain(values, percent=percent)
    step = (high - low) / 5
    digits = max(2, min(8, -math.floor(math.log10(step))))
    number_format = ("+" if percent else "") + f".{digits}f"
    expression = f"format(datum.value, '{number_format}')"
    if language in ("nb", "ru"):
        expression = f"replace({expression}, '.', ',')"
    return alt.Axis(tickCount=6, labelOverlap=True, labelExpr=expression)


def observation_x(frame, *, mini=False):
    """Equal-width publication slots; never synthesize weekend observations."""
    days = sorted(frame["День"].unique())
    long_period = not mini and (pd.Timestamp(days[-1]) - pd.Timestamp(days[0])).days > 180
    # Month/year labels need one tick per month, not several identical month labels.
    first_in_month = {}
    for day in days:
        first_in_month.setdefault(day[:7], day)
    candidates = list(first_in_month.values()) if long_period else days
    stride = max(1, math.ceil(len(candidates) / 8))
    ticks = days if mini else candidates[::stride]
    if not mini:
        if long_period and ticks[-1][:7] == days[-1][:7]:
            ticks[-1] = days[-1]
        elif ticks[-1] != days[-1]:
            ticks.append(days[-1])
    date_expression = ("slice(datum.label, 5, 7) + '.' + slice(datum.label, 0, 4)" if long_period else
                       "slice(datum.label, 8, 10) + '.' + slice(datum.label, 5, 7)")
    return alt.X("День:O", title=None, sort=days,
                 scale=alt.Scale(type="band", domain=days, paddingInner=0, paddingOuter=0),
                 axis=alt.Axis(values=ticks, grid=False, ticks=False, domain=False,
                               labelAngle=0, labelOverlap=True, labelPadding=8,
                               labelFontSize=11 if mini else 12,
                               labelColor="#445d54", labelExpr=date_expression))


def hover_layers(frame, x, y, tooltip):
    """Full-height hit areas show the nearest observation even away from its dot."""
    hover = alt.selection_point(fields=["День"], on="pointerover", clear="pointerout", empty=False)
    base = alt.Chart(frame)
    rule = base.mark_rule(color="#9ca3af", strokeDash=[3, 3], strokeWidth=1).encode(x=x).transform_filter(hover)
    point = base.mark_circle(color="#0c776b", size=75).encode(x=x, y=y).transform_filter(hover)
    # Transparent date bands cover the gaps between dots and the full plot height.
    # Keep this last so line marks cannot intercept the pointer and lose the tooltip.
    hit = base.mark_rect(fillOpacity=0).encode(x=x, tooltip=tooltip).add_params(hover)
    return [rule, point, hit]


def mini_chart(values, title, *, language="en"):
    """Seven actual observations with their own dates and a data-range scale."""
    history = sorted(values.items())[-7:]
    if not history:
        raise ValueError("Нет наблюдений для мини-графика.")
    frame = pd.DataFrame([{"Дата": day, "День": day.isoformat(), "Курс": float(rate),
                           "Дата курса": day.strftime("%d.%m.%Y"),
                           "Курс для показа": i18n.number(rate, language=language)} for day, rate in history])
    frame["Дата"] = pd.to_datetime(frame["Дата"])
    x = observation_x(frame, mini=True)
    y = alt.Y("Курс:Q", axis=None, title=None,
              scale=alt.Scale(domain=padded_domain(frame["Курс"]), zero=False, nice=False))
    tooltip = [alt.Tooltip("Дата курса:N", title=i18n.tr(language, "date")),
               alt.Tooltip("Курс для показа:N", title=title)]
    line = alt.Chart(frame).mark_line(
        color="#0c776b", strokeWidth=2,
        point=alt.OverlayMarkDef(size=28, filled=True), interpolate="linear"
    ).encode(
        x=x, y=y
    )
    return alt.layer(line, *hover_layers(frame, x, y, tooltip)).properties(height=76).configure_view(stroke=None)


def quote_chart(records, title, *, percent=False, language="en"):
    ordered = sorted(records, key=lambda row: row["Дата"])
    if not ordered:
        raise ValueError("Нет наблюдений для графика.")
    baseline = Decimal(str(ordered[0]["Курс"]))
    if baseline <= 0:
        raise ValueError("Начальный курс должен быть положительным.")
    points = []
    for row in ordered:
        rate = Decimal(str(row["Курс"]))
        change = (rate / baseline - 1) * 100
        points.append({"Дата": row["Дата"], "День": row["Дата"].isoformat(),
                       "Дата курса": row["Дата"].strftime("%d.%m.%Y"),
                       "Значение": float(change if percent else rate),
                       "Курс": i18n.number(rate, language=language),
                       "Изменение за период": i18n.number(change, "+.2f", language=language) + "%"})
    frame = pd.DataFrame(points)
    frame["Дата"] = pd.to_datetime(frame["Дата"])
    domain = padded_domain(frame["Значение"], percent=percent)
    y = alt.Y("Значение:Q", title=i18n.tr(language, "percent_axis") if percent else title,
              scale=alt.Scale(domain=domain, zero=False, nice=False),
              axis=value_axis(frame["Значение"], percent=percent, language=language))
    x = observation_x(frame)
    tooltip = [alt.Tooltip("Дата курса:N", title=i18n.tr(language, "date")),
               alt.Tooltip("Курс:N", title=title),
               alt.Tooltip("Изменение за период:N", title=i18n.tr(language, "period_change"))]
    line = alt.Chart(frame).mark_line(
        color="#0c776b", strokeWidth=3,
        point=alt.OverlayMarkDef(size=32, filled=True) if len(points) <= 60 else False,
        interpolate="linear"
    ).encode(
        x=x, y=y)
    layers = [line, *hover_layers(frame, x, y, tooltip)]
    if percent:
        zero = alt.Chart(pd.DataFrame({"Ноль": [0]})).mark_rule(
            color="#8c9f97", strokeDash=[4, 4], strokeWidth=1
        ).encode(y=alt.Y("Ноль:Q", scale=alt.Scale(domain=domain, zero=False, nice=False)))
        return alt.layer(zero, *layers).properties(height=340)
    # An area mark's implicit y2=0 can force zero back into a shared domain.
    # A line-only quote chart avoids that baseline and accurately shows the range.
    return alt.layer(*layers).properties(height=340)


def comparison_chart(records, *, language="en"):
    frame = pd.DataFrame(records)
    frame["Дата"] = pd.to_datetime(frame["Дата"])
    frame["День"] = frame["Дата"].dt.strftime("%Y-%m-%d")
    frame["Дата курса"] = frame["Дата"].dt.strftime("%d.%m.%Y")
    domain = padded_domain(frame["Изменение, %"], percent=True)
    zero = alt.Chart(pd.DataFrame({"Ноль": [0]})).mark_rule(
        color="#8c9f97", strokeDash=[4, 4], strokeWidth=1
    ).encode(y=alt.Y("Ноль:Q", scale=alt.Scale(domain=domain, zero=False, nice=False)))
    x = observation_x(frame)
    y = alt.Y("Изменение, %:Q", title=i18n.tr(language, "view_percent"),
              scale=alt.Scale(domain=domain, zero=False, nice=False),
              axis=value_axis(frame["Изменение, %"], percent=True, language=language))
    legend = alt.Legend(orient="bottom", columns=3, labelFontSize=12, labelColor="#445d54",
                        symbolStrokeWidth=2.5, labelLimit=100)
    lines = alt.Chart(frame).mark_line(strokeWidth=2.5).encode(
        x=x,
        y=y,
        color=alt.Color("Пара:N", title=None, legend=legend, scale=alt.Scale(domain=list(chat.PAIRS),
            range=["#0c776b", "#6663ce", "#c9822e", "#487fa2", "#b15c92"])),
        strokeDash=alt.StrokeDash("Пара:N", title=None, legend=legend,
                                 scale=alt.Scale(domain=list(chat.PAIRS),
                                                 range=[[], [6, 3], [2, 2], [8, 3, 2, 3], [10, 4]])),
        tooltip=[alt.Tooltip("Дата курса:N", title=i18n.tr(language, "date")),
                 alt.Tooltip("Пара:N", title=i18n.tr(language, "pair")),
                 alt.Tooltip("Изменение, %:Q", title=i18n.tr(language, "view_percent"), format="+.2f")])
    dates = []
    for day, group in frame.groupby("День", sort=True):
        values = dict(zip(group["Пара"], group["Изменение, %"]))
        dates.append({"День": day, "Дата курса": group["Дата курса"].iloc[0], **{
            pair: i18n.number(Decimal(str(values[pair])), "+.2f", language=language) + "%"
            if pair in values else i18n.tr(language, "no_data") for pair in chat.PAIRS}})
    tooltip = [alt.Tooltip("Дата курса:N", title=i18n.tr(language, "date")),
               *[alt.Tooltip(field=pair, type="nominal", title=pair) for pair in chat.PAIRS]]
    hover = alt.selection_point(fields=["День"], on="pointerover", clear="pointerout", empty=False)
    bands = alt.Chart(pd.DataFrame(dates))
    rule = bands.mark_rule(color="#9ca3af", strokeDash=[3, 3]).encode(x=x).transform_filter(hover)
    hit = bands.mark_rect(fillOpacity=0).encode(x=x, tooltip=tooltip).add_params(hover)
    return alt.layer(zero, lines, rule, hit).properties(height=340)
