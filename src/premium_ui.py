"""Scoped presentation components for the V2 dashboard views."""
from html import escape

import streamlit as st

BACKGROUND = "#0B1220"
SURFACE = "#172235"
ACCENT = "#53D6B1"
TEXT = "#F1F5F9"
MUTED = "#9BAFC3"
WARNING = "#E5A34C"
DANGER = "#D96B72"
CHART_COLORS = (ACCENT, "#81B5F2", WARNING, "#C6AAF0", DANGER, "#D1DB9A")

CSS = f"""
<style>
.fg-v2 {{ color: {TEXT}; font-family: system-ui, "Segoe UI", sans-serif; }}
.fg-v2-banner {{
    background: linear-gradient(125deg, {BACKGROUND}, {SURFACE});
    border: 1px solid #34465C; border-radius: 1rem;
    padding: clamp(1rem, 3vw, 2rem); margin-bottom: .4rem;
}}
.fg-v2-banner h2 {{ color: {TEXT}; margin: 0 0 .4rem; padding: 0; font-size: clamp(1.5rem, 4vw, 2.2rem); }}
.fg-v2-banner p {{ color: {MUTED}; margin: 0; max-width: 66ch; }}
.fg-v2-nav {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .85rem; }}
.fg-v2-nav a {{
    color: {ACCENT}; border: 1px solid #486577; border-radius: .5rem;
    padding: .4rem .7rem; text-decoration: none;
}}
.fg-v2-nav a:hover {{ background: {SURFACE}; text-decoration: underline; }}
.fg-v2-nav a:focus-visible {{ outline: 2px solid {ACCENT}; outline-offset: 3px; }}
.fg-v2-kpis {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
    gap: .75rem; margin: 0;
}}
.fg-v2-kpi {{ background: {SURFACE}; border: 1px solid #34465C; border-radius: .8rem; padding: .9rem 1rem; min-width: 0; }}
.fg-v2-kpi dt {{ color: {MUTED}; font-size: .92rem; margin: 0 0 .3rem; }}
.fg-v2-kpi dd {{
    color: {TEXT}; font-size: clamp(1.2rem, 2.5vw, 1.65rem); font-weight: 650;
    line-height: 1.25; margin: 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums;
}}
.fg-v2-kpi small {{ display: block; color: {MUTED}; margin-top: .5rem; }}
.fg-v2-tags {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.fg-v2-tag {{
    background: {SURFACE}; border: 1px solid #34465C; border-radius: .45rem;
    color: {TEXT}; line-height: 1.4; padding: .23rem .55rem; font-size: .83rem;
    overflow-wrap: anywhere;
}}
.fg-v2-tag strong {{ color: {ACCENT}; }}
.fg-v2-anchor {{ scroll-margin-top: 5rem; }}
</style>
"""


def page_intro(title, description, links):
    navigation = "".join(
        f'<a href="#{escape(target, quote=True)}">{escape(label)}</a>' for label, target in links
    )
    st.html(
        f'{CSS}<header class="fg-v2 fg-v2-banner"><h2>{escape(title)}</h2>'
        f'<p>{escape(description)}</p><nav class="fg-v2-nav" aria-label="{escape(title)} sections">'
        f'{navigation}</nav></header>'
    )


def section(title, anchor):
    st.html(f'<div id="{escape(anchor, quote=True)}" class="fg-v2-anchor"></div>')
    st.subheader(title)


def kpi_cards(metrics):
    cards = "".join(
        f'<div class="fg-v2-kpi"><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd>'
        f'<small>{escape(detail)}</small></div>'
        for label, value, detail in metrics
    )
    st.html(f'<dl class="fg-v2 fg-v2-kpis">{cards}</dl>')


def source_badges(*fields):
    badges = "".join(
        f'<span class="fg-v2-tag"><strong>{escape(label)}</strong> · {escape(str(value))}</span>'
        for label, value in fields
    )
    st.html(f'<div class="fg-v2 fg-v2-tags">{badges}</div>')


def style_chart(figure):
    """Apply a chart-local palette while keeping the caller's data and axes."""
    figure.update_layout(
        paper_bgcolor=BACKGROUND, plot_bgcolor=SURFACE,
        font=dict(family="system-ui, Segoe UI, sans-serif", size=13, color=TEXT),
        hoverlabel=dict(bgcolor=SURFACE, font_color=TEXT, bordercolor=MUTED),
        margin=dict(l=22, r=64, t=42, b=55),
    )
    figure.update_xaxes(automargin=True, gridcolor="#34465C", zerolinecolor="#486577")
    figure.update_yaxes(automargin=True, gridcolor="#34465C", zerolinecolor="#486577")
    return figure
