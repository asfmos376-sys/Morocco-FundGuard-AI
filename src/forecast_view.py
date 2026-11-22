"""Streamlit forecast experiment with common out-of-sample dates."""
import plotly.graph_objects as go
import streamlit as st

from src.data_loader import AMOUNT, ASSETS
from src.forecasting import ACTUAL, MODELS, ORIGIN, run_experiment
from src.validation import CATEGORY, DATE


def render_predictive_analytics(assets):
    st.subheader("Predictive Analytics")
    st.caption("Experimental one-week-ahead net asset estimates. For research use only.")
    category = st.selectbox("Forecast category", assets[CATEGORY].drop_duplicates().tolist())
    experiment = run_experiment(assets, category)
    history, predictions = experiment.history, experiment.predictions
    st.caption(
        f"Source · {ASSETS} / {AMOUNT} | {category} | "
        f"{history.index.min():%Y-%m-%d} to {history.index.max():%Y-%m-%d} | "
        "Workbook scale, currency unspecified"
    )
    score_col, evidence_col = st.columns(2)
    score_col.metric("Comparable out-of-sample weeks", len(predictions))
    evidence_col.metric("Model passing the reliability screen", experiment.winner or "None")
    if experiment.next_value is not None:
        st.metric(
            f"Experimental estimate for {experiment.next_date:%Y-%m-%d}",
            f"{experiment.next_value:,.2f}",
        )
    elif experiment.winner:
        st.info("Too few consecutive observations at the latest report to issue an estimate.")
    else:
        st.info("Predictive evidence is insufficient. No alternative reliably improved on persistence in this backtest.")

    chart = go.Figure()
    chart.add_scatter(x=history.index, y=history[AMOUNT], name="Reported actuals", mode="markers")
    for model in MODELS:
        chart.add_scatter(x=predictions[DATE], y=predictions[model], name=model, mode="markers")
    if experiment.next_value is not None:
        chart.add_scatter(
            x=[experiment.next_date], y=[experiment.next_value], name="Experimental estimate",
            mode="markers", marker=dict(symbol="diamond", size=12),
        )
    chart.update_layout(
        xaxis_title="Report date", yaxis_title="Net assets (workbook scale)",
        legend=dict(orientation="h", y=1.1), margin=dict(t=40, b=25, l=10, r=10),
    )
    st.plotly_chart(chart, width="stretch")
    st.subheader("Walk-forward errors")
    st.dataframe(experiment.metrics.style.format(precision=2, na_rep="—"))
    st.caption("MAE and RMSE use the original workbook scale. sMAPE uses only folds "
               "with a nonzero denominator.")
    if not predictions.empty:
        with st.expander("Historical predictions and absolute errors"):
            detail = predictions.assign(**{
                f"{model} absolute error": (predictions[model] - predictions[ACTUAL]).abs()
                for model in MODELS
            })
            st.dataframe(detail, hide_index=True, column_config={
                DATE: st.column_config.DateColumn("Target report date", format="YYYY-MM-DD"),
                ORIGIN: st.column_config.DateColumn(format="YYYY-MM-DD"),
            })
    with st.expander("Method and limitations"):
        st.write(
            "Models use only information available at the forecast origin. Each evaluation needs "
            "four consecutive, valid weekly reports before the target. Gaps or missing values "
            "start a new block. Exponential smoothing uses a fixed weight of 0.5."
        )
        st.write(
            "A model qualifies with at least 12 common test weeks, at least 5% improvement "
            "in both MAE and RMSE, lower absolute error on at least 60% of weeks, and lower "
            "MAE in each chronological half. This screen is heuristic and uses a short "
            "evaluation sample. The experiment reports point estimates only."
        )
