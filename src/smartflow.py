"""Streamlit view for explainable weekly OPCVM anomaly monitoring."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.anomalies import (
    ANOMALY, CENTER, DEFAULT_MINIMUM, DEFAULT_THRESHOLD, DEFAULT_WINDOW, HISTORY,
    INSUFFICIENT, MAD, MISSING, NORMAL, OBSERVED, SCORE, STATUS, UNDEFINED,
    calculated_weekly_change, detect_anomalies,
)
from src.data_loader import AMOUNT, ASSETS, VARIATIONS
from src.metrics import TOTAL, filter_records
from src.validation import CATEGORY, DATE

CALCULATED = "Calculated seven-day net asset change"
PUBLISHED = "Published weekly net asset change"
STATUSES = [ANOMALY, NORMAL, INSUFFICIENT, UNDEFINED, MISSING]


def render_smartflow(assets):
    st.subheader("SmartFlow · OPCVM anomaly monitoring")
    st.caption(
        "Scores measure statistical deviation from recent reports. "
        "They do not estimate financial risk probabilities."
    )
    start = assets[DATE].min().date()
    end = assets[DATE].max().date()
    date_filter, category_filter = st.columns(2)
    dates = date_filter.date_input(
        "SmartFlow report dates", (start, end), min_value=start, max_value=end,
    )
    categories = sorted(set(assets[CATEGORY]) - {TOTAL})
    chosen = category_filter.multiselect(
        "SmartFlow categories", [*categories, TOTAL], default=categories,
        help="TOTAL monitors the published market aggregate as a separate series.",
    )
    metric_filter, status_filter = st.columns(2)
    metric = metric_filter.selectbox("SmartFlow metric", [CALCULATED, PUBLISHED])
    statuses = status_filter.multiselect("Alert status", STATUSES, default=STATUSES)
    with st.expander("Scoring settings"):
        window_control, minimum_control, threshold_control = st.columns(3)
        window = window_control.number_input(
            "Rolling window (valid observations)", min_value=8, value=DEFAULT_WINDOW, step=1,
        )
        minimum = minimum_control.number_input(
            "Minimum prior observations", min_value=8, value=DEFAULT_MINIMUM, step=1,
        )
        threshold = threshold_control.number_input(
            "Absolute score threshold", min_value=0.1, value=DEFAULT_THRESHOLD, step=0.1,
        )
        st.caption("Scores use the rolling median and median absolute deviation of earlier "
                   "valid observations in the same category. Alerts require a score magnitude "
                   "strictly greater than the threshold.")
    if len(dates) != 2:
        st.info("Select a start and end report date.")
        return
    if minimum > window:
        st.info("Set the rolling window at least as large as the minimum prior observations.")
        return

    records = calculated_weekly_change(assets) if metric == CALCULATED else assets
    value = OBSERVED if metric == CALCULATED else VARIATIONS[0]
    scored = detect_anomalies(records, value, window=window, minimum=minimum, threshold=threshold)
    period = filter_records(scored, *dates, chosen)
    visible = period.loc[period[STATUS].isin(statuses)].copy()
    anomalies = period.loc[period[STATUS].eq(ANOMALY)]
    st.metric("Detected anomalies in selected period", len(anomalies))
    st.caption(
        f"Source · {ASSETS} | Selected report dates · {dates[0]:%d %b %Y} to "
        f"{dates[1]:%d %b %Y} | Unit · % change | "
        "The count uses the date, category and metric filters."
    )
    if metric == CALCULATED:
        st.caption("Calculated from Montant using consecutive reports exactly seven days apart. "
                   "Missing amounts, nonpositive prior amounts and other report gaps leave the change blank.")
    else:
        st.caption(f"Uses the workbook's {VARIATIONS[0]} column on its published scale.")
    show_chart(period, visible)
    show_alerts(visible, metric, threshold)
    return dict(
        scored=scored, alerts=anomalies, metric=metric,
        window=window, minimum=minimum, threshold=threshold,
    )


def show_chart(period, visible):
    if visible.empty or visible[OBSERVED].isna().all():
        st.info("No numeric observations match these filters.")
        return
    # Keep the dates in masked traces so unavailable or filtered values leave gaps.
    displayed = period.assign(**{OBSERVED: period[OBSERVED].where(period.index.isin(visible.index))})
    figure = px.line(displayed, x=DATE, y=OBSERVED, color=CATEGORY, markers=True)
    figure.update_traces(connectgaps=False, hovertemplate="%{x|%d %b %Y}<br>%{y:.3f}%")
    flagged = visible.loc[visible[STATUS].eq(ANOMALY)]
    if not flagged.empty:
        figure.add_trace(go.Scatter(
            x=flagged[DATE], y=flagged[OBSERVED], mode="markers", name="Anomaly",
            text=flagged[CATEGORY], hovertemplate="%{text}<br>%{x|%d %b %Y}<br>%{y:.3f}%",
            marker=dict(symbol="diamond-open", size=14, color="#d73443", line=dict(width=2)),
        ))
    figure.update_layout(
        xaxis_title="Report date", yaxis_title="Net asset change (%)",
        legend=dict(title_text="", orientation="h", y=1.02), margin=dict(t=35, b=30, l=10, r=15),
    )
    figure.update_yaxes(ticksuffix="%")
    st.plotly_chart(figure, width="stretch")


def show_alerts(visible, metric, threshold):
    table = visible.assign(Metric=metric, Source=ASSETS).sort_values(DATE, ascending=False)
    columns = [DATE, CATEGORY, "Metric", OBSERVED, CENTER, SCORE, STATUS, "Source"]
    st.subheader("Alert records")
    st.dataframe(
        table[columns], hide_index=True,
        column_config={
            DATE: st.column_config.DateColumn("Report date", format="YYYY-MM-DD"),
            CATEGORY: "Category",
            OBSERVED: st.column_config.NumberColumn(format="%.3f"),
            CENTER: st.column_config.NumberColumn(format="%.3f"),
            SCORE: st.column_config.NumberColumn(format="%.3f"),
        },
    )
    export_columns = [*columns, MAD, HISTORY, "Fichier d’origine", "Ligne export"]
    if metric == CALCULATED:
        export_columns += [AMOUNT, "Previous net assets", "Previous report date",
                           "Days since previous report"]
    st.download_button(
        "Download filtered SmartFlow CSV",
        table[export_columns].to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig"),
        file_name="smartflow_alerts.csv", mime="text/csv", disabled=table.empty,
    )

    flagged = table.loc[table[STATUS].eq(ANOMALY)]
    if flagged.empty:
        st.caption("No detected anomalies match the alert filters.")
        return
    selected = st.selectbox(
        "Alert evidence", flagged.index.tolist(),
        format_func=lambda index: f"{flagged.at[index, DATE]:%Y-%m-%d} · {flagged.at[index, CATEGORY]}",
    )
    row = flagged.loc[selected]
    difference = row[OBSERVED] - row[CENTER]
    st.write(
        f"The observed change was **{row[OBSERVED]:+.3f}%**, "
        f"**{difference:+.3f} percentage points** from the historical median "
        f"of **{row[CENTER]:+.3f}%**. The baseline uses **{row[HISTORY]}** prior valid "
        f"observations and has a MAD of **{row[MAD]:.3f} percentage points**. "
        f"The robust score was **{row[SCORE]:+.3f}** (absolute threshold **>{threshold:g}**)."
    )
    if metric == CALCULATED:
        st.caption(
            f"Net assets moved from {row['Previous net assets']:,.2f} on "
            f"{row['Previous report date']:%d %b %Y} to {row[AMOUNT]:,.2f} on "
            f"{row[DATE]:%d %b %Y}. Amounts use the workbook scale with unspecified currency."
        )
    st.caption(f"Source · {ASSETS} | {row['Fichier d’origine']} | Export line {row['Ligne export']}")
