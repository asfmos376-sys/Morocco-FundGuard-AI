"""FundPulse dashboard for the consolidated 2026 OPCVM workbook."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import (
    AMOUNT, ASSETS, COUNT, FLOWS, HOLDINGS, INDICES, REDS, SHARE, SUBS,
    VARIATIONS, WORKBOOK, load_workbook,
)
from src.metrics import NET_FLOW, TOTAL, add_net_flows, filter_records, snapshot
from src.copilot_view import render_fundcopilot
from src.forecast_lab_view import render_forecast_lab
from src.forecast_view import render_predictive_analytics
from src.investigation_view import render_investigation
from src.premium_ui import CHART_COLORS, kpi_cards, page_intro, section, source_badges, style_chart
from src.risk_radar import render_risk_radar
from src.scenario_view import render_scenario_studio
from src.smartflow import render_smartflow
from src.xai_view import render_explainability
from src.validation import CATEGORY, DATE

PALETTE = ["#087e78", "#294d89", "#c26d2a", "#794d9c", "#b43c5b", "#47742f"]
SOURCE_SCALE = "Original workbook scale (currency unspecified)"

st.set_page_config(page_title="FundPulse | Morocco FundGuard AI", layout="wide")


@st.cache_data(max_entries=2)
def get_data(path, modified_at):
    return load_workbook(path)


def source(sheet, frame, unit):
    dates = frame[DATE]
    if frame.empty:
        period = "No matching report dates"
    elif dates.min() == dates.max():
        period = f"{dates.min():%d %b %Y}"
    else:
        period = f"{dates.min():%d %b %Y} to {dates.max():%d %b %Y}"
    st.caption(f"Source · {sheet} | Report dates · {period} | Unit · {unit}")


def download(sheet, frame, key):
    st.download_button(
        "Download filtered CSV", frame.to_csv(index=False, date_format="%Y-%m-%d")
        .encode("utf-8-sig"), file_name=f"{sheet}.csv", mime="text/csv", key=key,
        disabled=frame.empty,
    )


def premium_source(sheet, frame, unit):
    dates = frame[DATE]
    period = "No matching report dates"
    if not frame.empty:
        period = f"{dates.min():%d %b %Y}"
        if dates.max() != dates.min():
            period += f" to {dates.max():%d %b %Y}"
    source_badges(("Source", sheet), ("Report dates", period), ("Unit", unit))


def chart(frame, value, unit, kind="line", *, premium=False):
    if frame.empty or frame[value].isna().all():
        st.info("This measure is unavailable for the selected reports and categories.")
        return
    if kind == "line":
        figure = px.line(
            frame, x=DATE, y=value, color=CATEGORY, markers=True,
            color_discrete_sequence=CHART_COLORS if premium else PALETTE,
        )
        suffix = "%" if unit == "%" else ""
        figure.update_traces(
            connectgaps=False,
            hovertemplate=f"%{{x|%d %b %Y}}<br>{value} · %{{y:,.2f}}{suffix}",
        )
        figure.update_xaxes(title="Report date", tickformat="%d %b %Y")
        figure.update_yaxes(title="Reported value", ticksuffix=suffix)
        figure.update_layout(legend=dict(title_text="", orientation="h", y=1.02))
    else:
        figure = px.bar(
            frame.sort_values(value), x=value, y=CATEGORY, orientation="h",
            text=value, color_discrete_sequence=CHART_COLORS if premium else PALETTE,
        )
        figure.update_traces(
            texttemplate="%{x:.2f}%", textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>Reported market share · %{x:.2f}%<extra></extra>",
        )
        figure.update_xaxes(title="Share of total market", ticksuffix="%", rangemode="tozero")
        figure.update_yaxes(title=None)
    figure.update_layout(margin=dict(t=30, b=32, l=8, r=55), hovermode="closest")
    if premium:
        st.plotly_chart(style_chart(figure), width="stretch", theme=None)
    else:
        st.plotly_chart(figure, width="stretch")


def display_value(value, decimals=2):
    return "Unavailable" if pd.isna(value) else f"{value:,.{decimals}f}"


def main():
    st.title("FundPulse")
    st.caption("Morocco FundGuard AI · 2026 OPCVM market dashboard")
    try:
        tables = get_data(WORKBOOK, WORKBOOK.stat().st_mtime_ns)
    except (OSError, ValueError) as error:
        st.error(f"Unable to load the consolidated workbook. {error}")
        return

    assets = tables[ASSETS]
    dates = assets[DATE]
    start, end = dates.min().date(), dates.max().date()
    selection = st.sidebar.date_input(
        "Report date range", (start, end), min_value=start, max_value=end,
    )
    if len(selection) != 2:
        st.info("Select the start and end dates to show matching reports.")
        return
    start, end = selection
    categories = sorted(set(assets[CATEGORY]) - {TOTAL})
    chosen = st.sidebar.multiselect("Fund categories", categories, default=categories)
    st.sidebar.caption("Fund categories apply to category charts. Market totals follow the date range.")
    st.sidebar.caption(f"Workbook · {WORKBOOK.name}")

    st.markdown(
        """
        <style>
        [data-testid="stTabs"] [role="tablist"] { gap: .35rem; }
        [data-testid="stTabs"] [role="tab"] { padding-inline: .75rem; }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            font-weight: 700;
            text-decoration: underline;
            text-underline-offset: .28em;
        }
        [data-testid="stTabs"] [role="tab"]:focus-visible {
            outline: 2px solid currentColor;
            outline-offset: -2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    overview, indices, flows, holdings, smartflow, xai, copilot, predictive, radar, investigation, forecast_lab, scenario_studio = st.tabs(
        ["Overview", "Performance indices", "Subscriptions & redemptions", "Portfolio composition", "SmartFlow", "Explainable AI", "FundCopilot", "Predictive Analytics", "Risk Radar", "AI Investigation Center", "Forecast Lab", "Scenario Studio"]
    )
    with overview:
        page_intro(
            "OPCVM market overview",
            "The published market snapshot and category trends for the selected report dates.",
            [("Market snapshot", "fg-overview-snapshot"), ("Market trend", "fg-overview-trend"),
             ("Category breakdown", "fg-overview-categories")],
        )
        source_badges(
            ("Report range", f"{start:%d %b %Y} to {end:%d %b %Y}"),
            ("Fund categories", len(chosen)),
        )
        scoped = filter_records(assets, start, end, [TOTAL])
        latest = snapshot(scoped, scoped[DATE].max())
        section("Market-wide snapshot", "fg-overview-snapshot")
        if latest.empty:
            st.info("No published market snapshot in the selected date range.")
        else:
            row = latest.iloc[0]
            variation = row[VARIATIONS[0]]
            kpi_cards([
                ("Market net assets", display_value(row[AMOUNT]), SOURCE_SCALE),
                ("Market OPCVM count", display_value(row[COUNT], 0), "Funds in published TOTAL"),
                ("Reported weekly change",
                 "Unavailable" if pd.isna(variation) else f"{variation:+.2f}%",
                 "Published market net asset variation"),
            ])
            premium_source(ASSETS, latest, f"{SOURCE_SCALE} · funds · %")
        st.caption("Market KPIs and trend use the published TOTAL across all fund categories.")
        with st.container(border=True):
            section("Market net assets by report", "fg-overview-trend")
            chart(scoped, AMOUNT, SOURCE_SCALE, premium=True)
            premium_source(ASSETS, scoped, SOURCE_SCALE)
            download(ASSETS, scoped, "market_csv")
        selected_assets = filter_records(assets, start, end, chosen)
        with st.container(border=True):
            section("Net assets by fund category", "fg-overview-categories")
            chart(selected_assets, AMOUNT, SOURCE_SCALE, premium=True)
            premium_source(ASSETS, selected_assets, SOURCE_SCALE)
        breakdown = snapshot(selected_assets, scoped[DATE].max())
        with st.container(border=True):
            st.subheader("Reported market share at the latest report")
            chart(breakdown, SHARE, "Percent of published market net assets", kind="bar", premium=True)
            premium_source(ASSETS, breakdown, "Percent of published market net assets")
            st.caption("Shares are published in Structure (%). The denominator is the full market on "
                       "that report date. Selecting fewer categories preserves their market shares.")
            download(ASSETS, selected_assets, "assets_csv")

    with indices:
        data = filter_records(tables[INDICES], start, end, chosen)
        available = set(tables[INDICES][CATEGORY])
        unavailable = sorted(set(chosen) - available)
        if unavailable:
            st.info(f"No published index for {', '.join(unavailable)}.")
        metric = st.selectbox("Index measure", ["Indice", *VARIATIONS])
        unit = "Reported index level (base unspecified)" if metric == "Indice" else "%"
        chart(data, metric, unit)
        source(INDICES, data, unit)
        download(INDICES, data, "indices_csv")

    with flows:
        include_market = st.checkbox(
            "Show market TOTAL across all fund categories", value=False,
            help="Use the published market total for each selected report date.",
        )
        data = filter_records(tables[FLOWS], start, end, [TOTAL] if include_market else chosen)
        data = add_net_flows(data)
        metric = st.selectbox("Flow measure", [SUBS, REDS, NET_FLOW])
        chart(data, metric, SOURCE_SCALE)
        source(FLOWS, data, SOURCE_SCALE)
        st.caption("Net subscriptions subtract reported redemptions from subscriptions for each row. "
                   "The reporting period is unspecified, so volumes are shown per report date.")
        download(FLOWS, data, "flows_csv")

    with holdings:
        st.caption("Portfolio composition uses the report date range and the security categories below.")
        universe = tables[HOLDINGS]
        choices = universe[CATEGORY].unique().tolist()
        selected = st.multiselect("Security categories", choices, default=["Actif total"])
        data = filter_records(universe, start, end, selected)
        measure = st.selectbox("Portfolio measure", [AMOUNT, SHARE, *VARIATIONS])
        unit = SOURCE_SCALE if measure == AMOUNT else "%"
        chart(data, measure, unit)
        source(HOLDINGS, data, unit)
        missing = data.loc[data[AMOUNT].isna(), [DATE, CATEGORY]]
        if not missing.empty:
            st.caption("The source leaves these amounts blank.")
            st.dataframe(missing, hide_index=True)
        st.caption("Security categories include parent groups, subgroups and a published total.")
        download(HOLDINGS, data, "holdings_csv")

    with smartflow:
        context = render_smartflow(assets)
    with xai:
        if context is None:
            st.info("Complete the SmartFlow date and scoring settings to view alert explanations.")
        else:
            render_explainability(**context)
    with copilot:
        render_fundcopilot(tables)
    with predictive:
        render_predictive_analytics(assets)
    with radar:
        observation = render_risk_radar(assets)
    with investigation:
        render_investigation(observation)
    with forecast_lab:
        render_forecast_lab(assets)
    with scenario_studio:
        render_scenario_studio(assets)


main()
