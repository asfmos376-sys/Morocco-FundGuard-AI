"""Independent investigation tab connected to the current Risk Radar observation."""
import streamlit as st

from src.copilot_view import gemini_config
from src.investigation import investigate, text_brief
from src.premium_ui import page_intro, section, source_badges


def render_investigation(evidence):
    page_intro(
        "AI Investigation Center",
        "Build a sourced brief for the observation selected in Risk Radar.",
        [("Investigation brief", "fg-investigation-brief")],
    )
    if evidence is None:
        st.info("Select a category and report date with a source row in Risk Radar.")
        return
    source_badges(
        ("Category", evidence.category), ("Report date", evidence.report_date),
        ("Metric", evidence.metric), ("SmartFlow status", evidence.status),
    )
    language = st.radio("Brief language", ["English", "Français"], horizontal=True)
    locale = "fr" if language == "Français" else "en"
    section("Investigation brief", "fg-investigation-brief")
    identity = (evidence, locale)
    if st.button("Generate investigation brief", type="primary"):
        with st.spinner("Preparing the verified brief…"):
            sections, assisted = investigate(evidence, locale, gemini_config())
        st.session_state["investigation_brief"] = (identity, sections, assisted)

    saved = st.session_state.get("investigation_brief")
    if saved is None or saved[0] != identity:
        st.caption("Generate a brief for this selection.")
        return
    _, sections, assisted = saved
    st.caption("Gemini-assisted report structure · verified evidence" if assisted else "Workbook report · deterministic")
    with st.container(border=True):
        for heading, body in sections:
            st.markdown(f"#### {heading}")
            st.text(body)
    st.download_button(
        "Download investigation brief (TXT)", text_brief(sections).encode("utf-8"),
        file_name=f"investigation-{evidence.report_date}-{locale}.txt",
        mime="text/plain; charset=utf-8",
    )
