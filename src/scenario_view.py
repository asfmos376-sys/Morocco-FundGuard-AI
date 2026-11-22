"""Scenario Studio controls and before/after presentation."""
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.data_loader import AMOUNT, ASSETS
from src.metrics import TOTAL
from src.premium_ui import ACCENT, MUTED, kpi_cards, page_intro, section, source_badges, style_chart
from src.scenario import RECONCILIATION_TOLERANCE, apply_shock, latest_baseline


def amount_text(value):
    return f"{value:,.2f}" if value is not None else "Unavailable"


def render_scenario_studio(assets):
    page_intro(
        "Scenario Studio",
        "Apply a hypothetical shock to a single fund category. All other categories remain unchanged.",
        [("Assumptions", "fg-scenario-assumptions"), ("Before and after", "fg-scenario-comparison")],
    )
    baseline, skipped = latest_baseline(assets)
    if baseline is None:
        st.error("No report has a complete, reconciled category breakdown and market total.")
    if skipped:
        with st.expander("Reports excluded from the baseline", expanded=True):
            for report_date, reason in skipped:
                st.write(f"{report_date:%Y-%m-%d} · {reason}")
    if baseline is None:
        return

    source_badges(
        ("Source", f"{ASSETS} / {AMOUNT}"),
        ("Baseline report", f"{baseline.report_date:%Y-%m-%d}"),
        ("Units", "Original workbook scale, currency unspecified"),
    )
    with st.container(border=True):
        left, right = st.columns(2)
        category = left.selectbox("Scenario category", [name for name, _ in baseline.categories])
        shock = right.number_input(
            "Hypothetical category shock (%)", min_value=-100.0, value=0.0, step=1.0,
            help="A negative percentage reduces the selected category. −100% reduces it to zero.",
        )
    try:
        result = apply_shock(baseline, category, shock)
    except ValueError as error:
        st.warning(str(error))
        return

    share_after = f"{100 * result.share_after:.3f}%" if result.share_after is not None else "Unavailable"
    share_before = f"{100 * result.share_before:.3f}%" if result.share_before is not None else "Unavailable"
    kpi_cards([
        ("Category absolute change", f"{result.change:+,.2f}", "Hypothetical change on the workbook scale"),
        ("Hypothetical category", amount_text(result.category_after), category),
        ("Hypothetical market total", amount_text(result.market_after), "Published TOTAL plus category change"),
        ("Hypothetical market share", share_after, f"Baseline share from amounts · {share_before}"),
    ])
    if result.share_after is None:
        st.info("A valid market share requires a positive hypothetical market total at least as large as the category amount.")

    with st.container(border=True):
        section("Net assets before and after", "fg-scenario-comparison")
        chart = make_subplots(rows=1, cols=2, subplot_titles=(category, "Market TOTAL"))
        for name, color, values in (
            ("Reported baseline", MUTED, (result.category_before, result.market_before)),
            ("Hypothetical", ACCENT, (result.category_after, result.market_after)),
        ):
            for index, value in enumerate(values, start=1):
                chart.add_bar(
                    x=[name], y=[value], name=name, marker_color=color, showlegend=index == 1,
                    hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>", row=1, col=index,
                )
        chart.update_yaxes(title_text="Workbook scale", rangemode="tozero")
        chart.update_layout(legend=dict(orientation="h", y=-0.20), height=410)
        st.plotly_chart(style_chart(chart), width="stretch", theme=None)
        st.caption("Each panel has its own amount scale.")

    section("Scenario assumptions and source checks", "fg-scenario-assumptions")
    st.write(
        "The selected category’s amount is multiplied by the shock percentage to get the change. "
        "That same change is added to the category and the published market total. "
        "All other categories and the baseline reconciliation difference stay fixed. "
        "Market share is calculated from the scenario amounts."
    )
    st.caption(
        f"The category sum differs from published TOTAL by {baseline.reconciliation_gap:+.6f} "
        f"on the workbook scale. Eligibility requires an absolute difference of at most "
        f"{RECONCILIATION_TOLERANCE:.2f} and amounts from the same source report and column."
    )
    lines = dict(baseline.export_lines)
    source_badges(
        ("Original file", baseline.original_file), ("Category export line", lines[category]),
        ("TOTAL export line", lines[TOTAL]),
    )
    st.caption("These are hypothetical scenario results. They provide no forecast or investment advice.")
