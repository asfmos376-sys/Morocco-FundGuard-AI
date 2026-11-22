"""Forecast Lab presentation, independent of the earlier forecasting view."""
import plotly.graph_objects as go
import streamlit as st

from src.data_loader import AMOUNT, ASSETS
from src.forecast_lab import MIN_TRAINING, forecastable_categories, run_lab
from src.forecasting import MIN_FOLDS
from src.premium_ui import ACCENT, CHART_COLORS, kpi_cards, page_intro, section, source_badges, style_chart
from src.validation import DATE


def render_forecast_lab(assets):
    page_intro(
        "Forecast Lab",
        "Experimental seven-day estimates of reported OPCVM net assets. For research use only.",
        [("Forecast and backtest", "fg-lab-chart"), ("Error comparison", "fg-lab-errors")],
    )
    categories = forecastable_categories(assets)
    if not categories:
        st.info("No category has a valid consecutive weekly net asset pair.")
        return
    with st.container(border=True):
        left, middle, right = st.columns(3)
        category = left.selectbox("Lab category", categories, index=categories.index("TOTAL") if "TOTAL" in categories else 0)
        window = middle.number_input("Moving average window (weeks)", min_value=2, max_value=12, value=4, step=1)
        include_ridge = right.checkbox("Compare lagged ridge regression", value=True)
    with st.spinner("Running the chronological backtest…"):
        result = run_lab(assets, category, window=window, include_ridge=include_ridge)
    history, predictions = result.history, result.predictions
    source_badges(
        ("Source", f"{ASSETS} / {AMOUNT}"),
        ("Report dates", f"{history.index.min():%Y-%m-%d} to {history.index.max():%Y-%m-%d}"),
        ("Units", "Original workbook scale, currency unspecified"),
        ("Horizon", "7 days"),
    )
    kpi_cards([
        ("Valid reports", int(history.notna().sum()), f"{result.weekly_pairs} consecutive seven-day pairs"),
        ("Common backtest weeks", len(predictions), f"{result.contiguous_count} consecutive valid reports at the end"),
        ("Selected method", result.winner or "None", "Based on out-of-sample performance versus persistence"),
    ])
    if result.forecast is not None:
        st.success(f"Experimental estimate for {result.target_date:%Y-%m-%d} · {result.forecast:,.2f}")
    elif result.winner:
        st.info("A model passed the backtest screen, but the latest report block lacks the "
                "required consecutive inputs for a seven-day estimate.")
    else:
        st.info("Predictive evidence is insufficient to select a model over persistence.")
    if include_ridge:
        st.caption(
            f"Lagged ridge regression has {result.ridge_folds} comparable weeks out of "
            f"{result.baseline_folds} baseline weeks. At least {MIN_FOLDS} are required to compare it."
        )

    with st.container(border=True):
        section("Reported net assets and out-of-sample predictions", "fg-lab-chart")
        chart = go.Figure()
        chart.add_scatter(x=history.index, y=history, name="Reported actuals", mode="markers",
                          marker=dict(color=ACCENT, size=8))
        for index, model in enumerate(result.metrics.index, start=1):
            chart.add_scatter(
                x=predictions[DATE], y=predictions[model], name=model, mode="markers",
                marker=dict(color=CHART_COLORS[index], symbol="diamond-open" if index == 1 else "square-open", size=9),
            )
        if result.forecast is not None:
            chart.add_scatter(
                x=[result.target_date], y=[result.forecast], name="Experimental estimate",
                mode="markers", marker=dict(symbol="diamond", color=ACCENT, size=14),
            )
        chart.update_layout(xaxis_title="Report date", yaxis_title="Net assets (workbook scale)",
                            legend=dict(orientation="h", y=1.04))
        st.plotly_chart(style_chart(chart), theme=None, width="stretch")

    section("Out-of-sample error comparison", "fg-lab-errors")
    st.dataframe(result.metrics.style.format(precision=2, na_rep="—"))
    st.caption("MAE and RMSE use the workbook scale. sMAPE omits zero-denominator pairs. "
               "All displayed models use the same target dates.")
    if not predictions.empty:
        with st.expander("Review individual backtest predictions"):
            st.dataframe(predictions, hide_index=True)
    with st.expander("Methods and limitations"):
        st.write(
            "Rolling forecasts use strictly earlier reports. Dates other than seven days apart "
            "and missing amounts break a lag window. Ridge uses two recent weekly returns, "
            f"fits statistics on earlier training rows only, and needs at least {MIN_TRAINING} "
            "rows. Its penalty is fixed at 1."
        )
        st.write(
            f"Selection requires at least {MIN_FOLDS} common weeks, at least 5% lower MAE and "
            "RMSE than persistence, lower absolute error in at least 60% of weeks, and lower "
            "MAE in both chronological halves. These are screening rules on a short sample. "
            "Results are point estimates. This experiment provides no investment advice."
        )
