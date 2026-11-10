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
        raise ValueError("The scale requires finite values.")
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
    if language != "en":
        expression = f"replace({expression}, '.', ',')"
    return alt.Axis(tickCount=6, labelOverlap=True, labelExpr=expression)


def observation_x(frame, *, mini=False):
    """Equal-width publication slots; never synthesize weekend observations."""
    days = sorted(frame["Day"].unique())
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
    return alt.X("Day:O", title=None, sort=days,
                 scale=alt.Scale(type="band", domain=days, paddingInner=0, paddingOuter=0),
                 axis=alt.Axis(values=ticks, grid=False, ticks=False, domain=False,
                               labelAngle=0, labelOverlap=True, labelPadding=8,
                               labelFontSize=11 if mini else 12,
                               labelExpr=date_expression))


def hover_layers(frame, x, y, tooltip):
    """Full-height hit areas show the nearest observation even away from its dot."""
    hover = alt.selection_point(fields=["Day"], on="pointerover", clear="pointerout", empty=False)
    base = alt.Chart(frame)
    rule = base.mark_rule(color="#9ca3af", strokeDash=[3, 3], strokeWidth=1).encode(x=x).transform_filter(hover)
    point = base.mark_circle(size=75).encode(x=x, y=y).transform_filter(hover)
    # Transparent date bands cover the gaps between dots and the full plot height.
    # Keep this last so line marks cannot intercept the pointer and lose the tooltip.
    hit = base.mark_rect(fillOpacity=0).encode(x=x, tooltip=tooltip).add_params(hover)
    return [rule, point, hit]


def mini_chart(values, title, *, language="en"):
    """Seven actual observations with their own dates and a data-range scale."""
    history = sorted(values.items())[-7:]
    if not history:
        raise ValueError("No observations are available for the mini chart.")
    frame = pd.DataFrame([{"Date": day, "Day": day.isoformat(), "Rate": float(rate),
                           "RateDate": day.strftime("%d.%m.%Y"),
                           "DisplayRate": i18n.number(rate, language=language)} for day, rate in history])
    frame["Date"] = pd.to_datetime(frame["Date"])
    x = observation_x(frame, mini=True)
    y = alt.Y("Rate:Q", axis=None, title=None,
              scale=alt.Scale(domain=padded_domain(frame["Rate"]), zero=False, nice=False))
    tooltip = [alt.Tooltip("RateDate:N", title=i18n.tr(language, "date")),
               alt.Tooltip("DisplayRate:N", title=title)]
    line = alt.Chart(frame).mark_line(
        strokeWidth=2,
        point=alt.OverlayMarkDef(size=28, filled=True), interpolate="linear"
    ).encode(
        x=x, y=y
    )
    return alt.layer(line, *hover_layers(frame, x, y, tooltip)).properties(height=76).configure_view(stroke=None)


def quote_chart(records, title, *, percent=False, language="en"):
    ordered = sorted(records, key=lambda row: row["Date"])
    if not ordered:
        raise ValueError("No observations are available for the chart.")
    baseline = Decimal(str(ordered[0]["Rate"]))
    if baseline <= 0:
        raise ValueError("The initial rate must be positive.")
    points = []
    for row in ordered:
        rate = Decimal(str(row["Rate"]))
        change = (rate / baseline - 1) * 100
        points.append({"Date": row["Date"], "Day": row["Date"].isoformat(),
                       "RateDate": row["Date"].strftime("%d.%m.%Y"),
                       "Value": float(change if percent else rate),
                       "Rate": i18n.number(rate, language=language),
                       "PeriodChange": i18n.number(change, "+.2f", language=language) + "%"})
    frame = pd.DataFrame(points)
    frame["Date"] = pd.to_datetime(frame["Date"])
    domain = padded_domain(frame["Value"], percent=percent)
    y = alt.Y("Value:Q", title=i18n.tr(language, "percent_axis") if percent else title,
              scale=alt.Scale(domain=domain, zero=False, nice=False),
              axis=value_axis(frame["Value"], percent=percent, language=language))
    x = observation_x(frame)
    tooltip = [alt.Tooltip("RateDate:N", title=i18n.tr(language, "date")),
               alt.Tooltip("Rate:N", title=title),
               alt.Tooltip("PeriodChange:N", title=i18n.tr(language, "period_change"))]
    line = alt.Chart(frame).mark_line(
        strokeWidth=3,
        point=alt.OverlayMarkDef(size=32, filled=True) if len(points) <= 60 else False,
        interpolate="linear"
    ).encode(
        x=x, y=y)
    layers = [line, *hover_layers(frame, x, y, tooltip)]
    if percent:
        zero = alt.Chart(pd.DataFrame({"Zero": [0]})).mark_rule(
            color="#8c9f97", strokeDash=[4, 4], strokeWidth=1
        ).encode(y=alt.Y("Zero:Q", scale=alt.Scale(domain=domain, zero=False, nice=False)))
        return alt.layer(zero, *layers).properties(height=340)
    # An area mark's implicit y2=0 can force zero back into a shared domain.
    # A line-only quote chart avoids that baseline and accurately shows the range.
    return alt.layer(*layers).properties(height=340)


def comparison_chart(records, *, language="en"):
    frame = pd.DataFrame(records)
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["Day"] = frame["Date"].dt.strftime("%Y-%m-%d")
    frame["RateDate"] = frame["Date"].dt.strftime("%d.%m.%Y")
    domain = padded_domain(frame["ChangePercent"], percent=True)
    zero = alt.Chart(pd.DataFrame({"Zero": [0]})).mark_rule(
        color="#8c9f97", strokeDash=[4, 4], strokeWidth=1
    ).encode(y=alt.Y("Zero:Q", scale=alt.Scale(domain=domain, zero=False, nice=False)))
    x = observation_x(frame)
    y = alt.Y("ChangePercent:Q", title=i18n.tr(language, "view_percent"),
              scale=alt.Scale(domain=domain, zero=False, nice=False),
              axis=value_axis(frame["ChangePercent"], percent=True, language=language))
    legend = alt.Legend(orient="bottom", columns=3, labelFontSize=12,
                        symbolStrokeWidth=2.5, labelLimit=100)
    lines = alt.Chart(frame).mark_line(strokeWidth=2.5).encode(
        x=x,
        y=y,
        color=alt.Color("Pair:N", title=None, legend=legend,
                        scale=alt.Scale(domain=list(chat.NOK_PAIRS))),
        strokeDash=alt.StrokeDash("Pair:N", title=None, legend=legend,
                                 scale=alt.Scale(domain=list(chat.NOK_PAIRS),
                                                 range=[[], [6, 3], [2, 2], [8, 3, 2, 3], [10, 3]])),
        tooltip=[alt.Tooltip("RateDate:N", title=i18n.tr(language, "date")),
                 alt.Tooltip("Pair:N", title=i18n.tr(language, "pair")),
                 alt.Tooltip("ChangePercent:Q", title=i18n.tr(language, "view_percent"), format="+.2f")])
    dates = []
    for day, group in frame.groupby("Day", sort=True):
        values = dict(zip(group["Pair"], group["ChangePercent"]))
        dates.append({"Day": day, "RateDate": group["RateDate"].iloc[0], **{
            pair: i18n.number(Decimal(str(values[pair])), "+.2f", language=language) + "%"
            if pair in values else i18n.tr(language, "no_data") for pair in chat.NOK_PAIRS}})
    tooltip = [alt.Tooltip("RateDate:N", title=i18n.tr(language, "date")),
               *[alt.Tooltip(field=pair, type="nominal", title=pair) for pair in chat.NOK_PAIRS]]
    hover = alt.selection_point(fields=["Day"], on="pointerover", clear="pointerout", empty=False)
    bands = alt.Chart(pd.DataFrame(dates))
    rule = bands.mark_rule(color="#9ca3af", strokeDash=[3, 3]).encode(x=x).transform_filter(hover)
    hit = bands.mark_rect(fillOpacity=0).encode(x=x, tooltip=tooltip).add_params(hover)
    return alt.layer(zero, lines, rule, hit).properties(height=340)
