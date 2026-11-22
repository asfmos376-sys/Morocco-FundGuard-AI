import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_premium_components_are_scoped_to_overview_and_radar():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    tabs = {tab.label: tab for tab in app.tabs}
    for name, tab in tabs.items():
        markup = [item.proto.body for item in tab.get("html")]
        palettes = [
            json.loads(chart.proto.spec)["layout"].get("paper_bgcolor")
            for chart in tab.get("plotly_chart")
        ]
        if name in {"Overview", "Risk Radar", "Forecast Lab", "Scenario Studio"}:
            assert any("fg-v2-banner" in body and "aria-label=" in body for body in markup)
            assert any("fg-v2-tag" in body and "<strong>Source" in body for body in markup)
            assert palettes and all(color == "#0B1220" for color in palettes)
        elif name != "AI Investigation Center":
            assert not any("fg-v2-" in body for body in markup)
            assert "#0B1220" not in palettes
    overview_markup = [item.proto.body for item in tabs["Overview"].get("html")]
    assert any("grid-template-columns: repeat(auto-fit" in body and ":focus-visible" in body
               for body in overview_markup)
    assert any('id="fg-overview-snapshot"' in body for body in overview_markup)
