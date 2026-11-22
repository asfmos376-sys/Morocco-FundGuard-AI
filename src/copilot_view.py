"""Independent FundCopilot chat tab."""
import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from src.copilot_gemini import DEFAULT_MODEL, GeminiConfig, respond
from src.validation import DATE

EXAMPLES = (
    ("Net assets", "What are the latest net assets by category?"),
    ("Indices", "Compare the performance index for Actions and Monétaire on 2026-11-09"),
    ("Explain an alert", "Explain the SmartFlow alert for Obligations CT on 2026-04-24"),
)


def gemini_config():
    def value(name, default=""):
        environment = os.getenv(name)
        if environment is not None:
            return environment
        try:
            return str(st.secrets.get(name, default))
        except (StreamlitSecretNotFoundError, OSError):
            return default

    return GeminiConfig(
        key=value("GEMINI_API_KEY").strip(), model=value("GEMINI_MODEL", DEFAULT_MODEL).strip(),
        free_tier_confirmed=value("GEMINI_FREE_TIER_CONFIRMED").strip().lower() in {"true", "1"},
    )


def show_answer(response, mode):
    with st.chat_message("assistant"):
        st.write(response.answer)
        if response.source:
            st.caption(
                f"Source · {response.source} | Reports · {', '.join(response.reports)} | "
                f"Category · {', '.join(response.categories)} | Metric · {response.metric} | Unit · {response.unit}"
            )
        if response.limitation:
            st.caption(response.limitation)
        if response.evidence is not None and not response.evidence.empty:
            with st.expander(f"Supporting data · {min(12, len(response.evidence))} of {len(response.evidence)} rows"):
                st.dataframe(
                    response.evidence.head(12), hide_index=True,
                    column_config={DATE: st.column_config.DateColumn("Report date", format="YYYY-MM-DD")},
                )
        st.caption(mode)


def render_fundcopilot(tables):
    st.subheader("FundCopilot")
    st.caption("Ask about reported OPCVM data and SmartFlow alerts in English, French, Arabic or Darija.")
    config = gemini_config()
    if config.enabled:
        st.caption("Gemini interprets the submitted question. FundCopilot calculates the answer locally.")
    else:
        st.caption("Workbook mode · supported question templates are interpreted locally.")
    history = st.session_state.setdefault("fundcopilot_history", [])
    selected = None
    for column, (label, example) in zip(st.columns(len(EXAMPLES)), EXAMPLES):
        if column.button(label, key=f"copilot-example-{label}", width="stretch"):
            selected = example
    for question, response, mode in history:
        with st.chat_message("user"):
            st.text(question)
        show_answer(response, mode)

    question = st.chat_input(
        "Ask about a category, report date or SmartFlow alert", key="fundcopilot_input", max_chars=750,
    ) or selected
    if question:
        with st.chat_message("user"):
            st.text(question)
        with st.spinner("Checking the question and workbook evidence…"):
            response, mode = respond(question, tables, config)
        history.append((question, response, mode))
        show_answer(response, mode)
