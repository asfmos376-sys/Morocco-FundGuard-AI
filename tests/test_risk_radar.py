import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.anomalies import (
    ANOMALY, INSUFFICIENT, MISSING, OBSERVED, SCORE, STATUS, UNDEFINED,
    calculated_weekly_change, detect_anomalies,
)
from src.data_loader import ASSETS, VARIATIONS, load_workbook
from src.risk_radar import NO_RECORD, heatmap, radar_grid, score_radar
from src.smartflow import CALCULATED, PUBLISHED
from src.validation import CATEGORY, DATE


@pytest.fixture(scope="module")
def assets():
    return load_workbook()[ASSETS]


@pytest.mark.parametrize("metric", [CALCULATED, PUBLISHED])
@pytest.mark.parametrize("threshold", [3.5, 6.0])
def test_same_scores_and_alerts_as_smartflow(assets, metric, threshold):
    frame = calculated_weekly_change(assets) if metric == CALCULATED else assets
    column = OBSERVED if metric == CALCULATED else VARIATIONS[0]
    expected = detect_anomalies(frame, column, threshold=threshold)
    pd.testing.assert_frame_equal(score_radar(assets, metric, threshold), expected)
    april = radar_grid(expected, "2026-04-24", "2026-04-24", ["Obligations CT"]).iloc[0]
    assert april[SCORE] == pytest.approx(7.372385140484002 if metric == CALCULATED else 5.711172440853875)
    assert (april[STATUS] == ANOMALY) == (abs(april[SCORE]) > threshold)


def test_gray_cells_distinguish_missing_undefined_and_zero():
    dates = pd.date_range("2026-01-02", periods=10, freq="7D")
    frame = pd.DataFrame({
        DATE: list(dates) * 2,
        CATEGORY: ["Actions"] * len(dates) + ["Contractuel"] * len(dates),
        OBSERVED: [0, 2] * 4 + [1, None] + [1] * len(dates),
    })
    scored = detect_anomalies(frame)
    categories = ["Actions", "Contractuel", "Monétaire"]
    grid = radar_grid(scored, dates.min(), dates.max(), categories)
    assert grid.loc[grid[CATEGORY].eq("Actions"), STATUS].iloc[0] == INSUFFICIENT
    assert grid.loc[grid[CATEGORY].eq("Actions"), STATUS].iloc[-1] == MISSING
    assert grid.loc[grid[CATEGORY].eq("Contractuel"), STATUS].iloc[-1] == UNDEFINED
    assert grid.loc[grid[CATEGORY].eq("Monétaire"), STATUS].eq(NO_RECORD).all()
    no_score, magnitude = heatmap(grid, categories).data
    assert magnitude.z[0][8] == 0
    assert pd.isna(no_score.z[0][8])
    assert all(no_score.z[row][9] == 1 for row in range(3))
    assert all(pd.isna(magnitude.z[row][9]) for row in range(3))


def test_radar_ui_date_category_threshold_and_evidence(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_TIER_CONFIRMED", "false")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "Risk Radar")
    assert tab.label == "Risk Radar"
    initial = {m.label: m.value for m in tab.metric}
    assert initial == {"Valid scores": "150", "Flagged alerts": "7", "Cells without a score": "114"}

    tab.date_input[0].set_value((date(2026, 4, 24), date(2026, 4, 24)))
    tab.multiselect[0].set_value(["Obligations CT"])
    tab.selectbox[0].select(PUBLISHED)
    tab.number_input[0].set_value(6.0)
    app.run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "Risk Radar")
    assert [m.value for m in tab.metric] == ["1", "0", "0"]
    evidence = tab.dataframe[0].value.set_index("Field")["Value"]
    assert evidence["Report date"] == "2026-04-24"
    assert evidence["Category"] == "Obligations CT"
    assert evidence["Source sheet"] == ASSETS
    assert evidence["Original file"] == "stat_opcvm_hebdo_ammc_24-04-2026.xls"
    assert evidence["Export line"] == "922"
    assert evidence["Observed change"] == "18.920%"
    assert evidence["Robust z-score"] == "5.711"
    assert evidence["Absolute threshold"] == "> 6.000"
    history = json.loads(tab.get("plotly_chart")[1].proto.spec)["data"][0]["x"]
    assert len(history) == 16 and all(value[:10] < "2026-04-24" for value in history)

    tab.date_input[0].set_value((date(2026, 4, 25), date(2026, 4, 25))).run(timeout=30)
    assert not app.exception
    assert not next(tab for tab in app.tabs if tab.label == "Risk Radar").get("plotly_chart")
    assert any("No workbook report dates" in item.value for item in next(tab for tab in app.tabs if tab.label == "Risk Radar").info)
