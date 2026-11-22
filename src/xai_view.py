"""Streamlit presentation of SmartFlow alert explanations."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.anomalies import CENTER, HISTORY, INSUFFICIENT, MAD_SCALE, OBSERVED, SCORE, STATUS
from src.explanations import baseline_for, explain, number, rank_alerts, text_report
from src.validation import CATEGORY, DATE


def render_explainability(scored, alerts, metric, window, minimum, threshold):
    st.subheader("Explainable AI")
    st.caption("This page uses SmartFlow’s active date, category, metric and scoring settings.")
    if alerts.empty:
        st.info("No detected alerts match the current SmartFlow settings.")
        return

    ranked = rank_alerts(alerts)
    positions = {index: rank for rank, index in enumerate(ranked.index, start=1)}
    st.caption("Heuristic severity ranking uses descending absolute robust z-score within this "
               "selection. It measures statistical deviation and carries no financial risk probability.")

    def option(index):
        row = ranked.loc[index]
        return f"#{positions[index]} · {row[DATE]:%Y-%m-%d} · {row[CATEGORY]} · |z| {abs(row[SCORE]):.3f}"

    alert_control, language_control = st.columns([2, 1])
    selected = alert_control.selectbox("SmartFlow alert", ranked.index.tolist(), format_func=option)
    language = language_control.radio("Explanation language", ["English", "Français"], horizontal=True)
    row = ranked.loc[selected]
    explanation = explain(
        row, metric, window=window, minimum=minimum, threshold=threshold,
        language="fr" if language == "Français" else "en",
    )
    title, narrative, evidence, limits = explanation
    with st.container(border=True):
        st.markdown(f"#### {row[CATEGORY]} · {row[DATE]:%Y-%m-%d}")
        st.caption(f"{title} · {metric} · Heuristic rank {positions[selected]} of {len(ranked)}")
        observed_card, median_card, score_card = st.columns(3)
        observed_card.metric("Selected change", number(row[OBSERVED], "%"))
        median_card.metric("Baseline median", number(row[CENTER], "%"))
        score_card.metric("Robust z-score", number(row[SCORE]))
        st.write(narrative)
        st.caption(limits)

    baseline = baseline_for(scored, row)
    st.subheader("Historical comparison")
    st.write("Circles show the earlier values used to score this alert. The diamond marks the "
             "selected report. Hover over a circle to see its SmartFlow status on its own date.")
    figure = go.Figure()
    figure.add_scatter(
        x=baseline[DATE], y=baseline[OBSERVED], mode="markers",
        name="Prior observations used", marker=dict(color="#087e78", size=8),
        customdata=baseline[[STATUS, HISTORY]].to_numpy(),
        hovertemplate=(
            "%{x|%Y-%m-%d}<br>%{y:.3f}%<br>"
            "Status on that date · %{customdata[0]}<br>Valid prior values · %{customdata[1]}"
            "<extra>Prior observation</extra>"
        ),
    )
    figure.add_scatter(
        x=[row[DATE]], y=[row[OBSERVED]], mode="markers", name="Selected alert",
        marker=dict(symbol="diamond", color="#d73443", size=12),
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3f}%<extra>Selected alert</extra>",
    )
    figure.add_hline(y=row[CENTER], line_dash="dash", annotation_text="Historical median")
    figure.update_layout(
        xaxis_title="Report date", yaxis_title="Net asset change (%)",
        legend=dict(orientation="h", y=1.05), margin=dict(t=35, b=30, l=10, r=15),
    )
    figure.update_yaxes(ticksuffix="%", tickformat=".2f")
    st.plotly_chart(figure, width="stretch")
    st.caption(
        f"{len(baseline)} prior valid observations from "
        f"{baseline[DATE].min():%Y-%m-%d} to {baseline[DATE].max():%Y-%m-%d} "
        f"· Range {number(baseline[OBSERVED].min(), '%')} to {number(baseline[OBSERVED].max(), '%')}"
    )
    largest_prior = baseline.loc[baseline[OBSERVED].idxmax()]
    if largest_prior[OBSERVED] > row[OBSERVED]:
        earlier_value = number(largest_prior[OBSERVED], "%")
        earlier_date = largest_prior[DATE].strftime("%Y-%m-%d")
        earlier_status = largest_prior[STATUS]
        if earlier_status == INSUFFICIENT:
            earlier_status += f" ({largest_prior[HISTORY]} of {minimum} required prior values)"
        st.info(
            f"The earlier {earlier_value} change on {earlier_date} had status "
            f"**{earlier_status}** when evaluated. It is one input to the selected "
            "report’s baseline. Each observation is evaluated against its own earlier data."
        )
    with st.expander("How the robust z-score works"):
        st.write(
            f"The score is approximately {MAD_SCALE:.3f} × (observed change − historical median) ÷ MAD, "
            "using full precision. MAD is the median of the absolute distances from the "
            "historical median. A score’s sign shows the direction of deviation. "
            f"SmartFlow flags a report when the absolute score strictly exceeds {number(threshold)}."
        )
        st.caption("The baseline uses earlier valid values from the same category and metric. "
                   "The score expresses statistical deviation.")
    st.subheader("Structured evidence")
    st.dataframe(
        pd.DataFrame([(label, str(value)) for label, value in evidence], columns=["Field", "Value"]),
        hide_index=True,
    )
    st.download_button(
        "Download explanation (TXT)", text_report(explanation).encode("utf-8"),
        file_name=f"smartflow-{row[DATE]:%Y-%m-%d}-alert.txt", mime="text/plain; charset=utf-8",
    )
