"""Risk Radar uses SmartFlow scores and the shared statistical evidence service."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.anomalies import (
    ANOMALY, CENTER, DEFAULT_MINIMUM, DEFAULT_THRESHOLD, DEFAULT_WINDOW, OBSERVED,
    SCORE, STATUS, calculated_weekly_change, detect_anomalies,
)
from src.data_loader import AMOUNT, ASSETS, PROVENANCE, VARIATIONS
from src.explanations import baseline_for, explain
from src.investigation import build_evidence
from src.metrics import TOTAL, filter_records
from src.premium_ui import ACCENT, page_intro, section, source_badges, style_chart
from src.smartflow import CALCULATED, PUBLISHED
from src.validation import CATEGORY, DATE

NO_RECORD = "No report row for this category"


def score_radar(assets, metric, threshold):
    if metric == CALCULATED:
        return detect_anomalies(calculated_weekly_change(assets), threshold=threshold)
    if metric == PUBLISHED:
        return detect_anomalies(assets, VARIATIONS[0], threshold=threshold)
    raise ValueError("Unsupported Risk Radar metric.")


def radar_grid(scored, start, end, categories):
    """Keep actual report dates and distinguish absent rows from unscored rows."""
    reports = scored.loc[scored[DATE].between(pd.Timestamp(start), pd.Timestamp(end)), DATE]
    dates = pd.DatetimeIndex(reports.unique()).sort_values()
    period = filter_records(scored, start, end, categories).set_index([CATEGORY, DATE])
    keys = pd.MultiIndex.from_product([categories, dates], names=[CATEGORY, DATE])
    grid = period.reindex(keys)
    grid[STATUS] = grid[STATUS].fillna(NO_RECORD)
    return grid.reset_index()


def heatmap(grid, categories):
    dates = pd.DatetimeIndex(grid[DATE].unique()).strftime("%Y-%m-%d").tolist()
    labels = grid[STATUS].to_numpy().reshape(len(categories), len(dates))
    magnitude = grid[SCORE].abs().to_numpy(dtype=float).reshape(labels.shape)
    no_score = grid[SCORE].isna().where(grid[SCORE].isna()).astype(float).to_numpy()
    figure = go.Figure()
    figure.add_heatmap(
        x=dates, y=categories, z=no_score.reshape(labels.shape), zmin=0, zmax=1,
        colorscale=[[0, "#818994"], [1, "#818994"]], showscale=False, customdata=labels,
        xgap=2, ygap=2, hoverongaps=False,
        hovertemplate="%{y} · %{x}<br>%{customdata}<extra>No score</extra>",
    )
    figure.add_heatmap(
        x=dates, y=categories, z=magnitude, zmin=0,
        colorscale=[[0, "#f1f5f9"], [0.45, ACCENT], [1, "#214c79"]],
        colorbar=dict(title="|Robust z|"), customdata=labels,
        xgap=2, ygap=2, hoverongaps=False,
        hovertemplate="%{y} · %{x}<br>|Robust z| %{z:.3f}<br>%{customdata}<extra></extra>",
    )
    figure.update_xaxes(title="Report date", type="category", tickangle=-45)
    figure.update_yaxes(
        title=None, categoryorder="array", categoryarray=list(categories), autorange="reversed",
    )
    figure.update_layout(height=max(290, 150 + 34 * len(categories)), margin=dict(t=10, l=10, r=10, b=90))
    return figure


def render_risk_radar(assets):
    page_intro(
        "Risk Radar",
        "Explore statistical anomaly intensity across OPCVM categories and report dates.",
        [("Intensity map", "fg-radar-map"), ("Observation evidence", "fg-radar-evidence")],
    )
    st.caption(
        "Scores do not measure fraud or investment risk probabilities and do not establish misconduct."
    )
    first, last = assets[DATE].min().date(), assets[DATE].max().date()
    categories = sorted(set(assets[CATEGORY]) - {TOTAL})
    with st.container(border=True):
        left, right = st.columns(2)
        dates = left.date_input("Radar report dates", (first, last), min_value=first, max_value=last)
        selected = right.multiselect(
            "Radar categories", [*categories, TOTAL], default=categories,
            help="TOTAL is the published market aggregate and can be displayed separately.",
        )
        metric = left.selectbox("Radar metric", [CALCULATED, PUBLISHED])
        threshold = right.number_input(
            "Radar absolute score threshold", value=DEFAULT_THRESHOLD, min_value=0.1, step=0.1,
            help="An alert requires a score magnitude strictly above this threshold.",
        )
    if len(dates) != 2 or not selected:
        st.info("Select a report date range and at least one category.")
        return
    with st.spinner("Preparing the statistical score grid…"):
        scored = score_radar(assets, metric, threshold)
        grid = radar_grid(scored, *dates, selected)
    if grid.empty:
        st.info("No workbook report dates fall in this range.")
        return

    scored_count = int(grid[SCORE].notna().sum())
    alert_count = int(grid[STATUS].eq(ANOMALY).sum())
    valid_widget, alert_widget, blank_widget = st.columns(3)
    valid_widget.metric("Valid scores", scored_count, border=True)
    alert_widget.metric("Flagged alerts", alert_count, border=True)
    blank_widget.metric("Cells without a score", len(grid) - scored_count, border=True)
    source_column = AMOUNT if metric == CALCULATED else VARIATIONS[0]
    source_badges(
        ("Source", f"{ASSETS} / {source_column}"), ("Change unit", "%"),
        ("Baseline", f"Up to {DEFAULT_WINDOW} prior valid values, minimum {DEFAULT_MINIMUM}"),
    )
    with st.container(border=True):
        section("Statistical intensity by report date", "fg-radar-map")
        st.plotly_chart(style_chart(heatmap(grid, selected)), width="stretch", theme=None)
        st.caption("Gray cells have no score. Near-white cells can represent a valid zero. "
                   "Hover for the status, or select a cell by category and report date below.")

    section("Observation evidence", "fg-radar-evidence")
    left, right = st.columns(2)
    category = left.selectbox("Radar observation category", selected)
    options = sorted(grid[DATE].unique(), reverse=True)
    report = right.selectbox("Radar observation date", options, format_func=lambda d: d.strftime("%Y-%m-%d"))
    row = grid.loc[grid[CATEGORY].eq(category) & grid[DATE].eq(report)].iloc[0]
    if row[STATUS] == NO_RECORD:
        st.info(f"{category} · {report:%Y-%m-%d} · {NO_RECORD}.")
        return
    _, narrative, evidence, _ = explain(
        row, metric, window=DEFAULT_WINDOW, minimum=DEFAULT_MINIMUM, threshold=threshold,
    )
    with st.container(border=True):
        st.markdown(f"**{row[STATUS]}**")
        st.write(narrative)
        fields = [*evidence, ("Workbook extract", row[PROVENANCE[1]])]
        previous = row.get("Previous report date")
        if pd.notna(previous):
            fields.append(("Previous report date", previous.strftime("%Y-%m-%d")))
        st.dataframe(
            pd.DataFrame([(name, str(value)) for name, value in fields], columns=["Field", "Value"]),
            hide_index=True,
        )

    st.subheader("Historical comparison")
    baseline = baseline_for(scored, row)
    investigation = build_evidence(row, metric, threshold, baseline)
    if baseline.empty:
        st.info("No valid prior observations are available for this report.")
        return investigation
    figure = go.Figure(go.Scatter(
        x=baseline[DATE], y=baseline[OBSERVED], mode="markers", name="Prior observations",
        marker=dict(color=ACCENT, size=8),
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3f}%<extra></extra>",
    ))
    if pd.notna(row[CENTER]):
        figure.add_hline(y=row[CENTER], line_dash="dash", annotation_text="Historical median")
    figure.update_layout(xaxis_title="Prior report date", yaxis_title="Net asset change (%)")
    figure.update_yaxes(ticksuffix="%")
    st.plotly_chart(style_chart(figure), width="stretch", theme=None)
    st.caption("Only prior valid observations from the selected category and metric are shown. "
               "The baseline can include dates before the display range.")
    return investigation
