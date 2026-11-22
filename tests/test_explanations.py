from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.anomalies import (
    ANOMALY, CENTER, HISTORY, MAD, OBSERVED, SCORE, STATUS,
    calculated_weekly_change, detect_anomalies,
)
from src.data_loader import ASSETS, VARIATIONS, load_workbook
from src.explanations import baseline_for, explain, rank_alerts, text_report
from src.metrics import TOTAL
from src.smartflow import CALCULATED, PUBLISHED
from src.validation import CATEGORY, DATE

SETTINGS = dict(window=8, minimum=8, threshold=3.5)


def scored_series(values):
    frame = pd.DataFrame({
        DATE: pd.date_range("2026-01-02", periods=len(values), freq="7D"),
        CATEGORY: "Actions",
        OBSERVED: values,
    })
    return detect_anomalies(frame, **SETTINGS)


@pytest.mark.parametrize(("observed", "difference"), [(20, "19.500 pp"), (-20, "-20.500 pp")])
def test_alert_explains_direction_threshold_units_and_date(observed, difference):
    row = scored_series([0, 1] * 4 + [observed]).iloc[-1]
    title, narrative, fields, limits = explain(row, CALCULATED, **SETTINGS)
    evidence = dict(fields)
    assert row[STATUS] == ANOMALY
    assert evidence["Report date"] == "2026-02-27"
    assert evidence["Source sheet"] == ASSETS
    assert evidence["Observed change"] == f"{observed:.3f}%"
    assert evidence["Historical median"] == "0.500%"
    assert evidence["Historical MAD"] == "0.500 pp"
    assert evidence["Difference from median"] == difference
    assert float(evidence["Robust z-score"]) == pytest.approx(row[SCORE], abs=0.0005)
    assert evidence["Rolling window capacity"] == evidence["Valid prior values used"] == 8
    assert difference in narrative and "exceeds 3.5" in narrative
    assert "causal attribution" in limits
    assert narrative == explain(row, CALCULATED, **SETTINGS)[1]
    assert "fraud" not in narrative.lower() and "because |" in narrative


@pytest.mark.parametrize(
    ("values", "message", "mad"),
    [
        ([0, 1, 2], "only 2", "—"),
        ([1] * 8 + [5], "MAD is zero", "0.000 pp"),
        ([0, 1] * 4 + [None], "observed change is unavailable", "—"),
    ],
)
def test_unavailable_baseline_or_observation(values, message, mad):
    row = scored_series(values).iloc[-1]
    _, narrative, fields, _ = explain(row, CALCULATED, **SETTINGS)
    assert message in narrative
    assert dict(fields)["Historical MAD"] == mad
    assert dict(fields)["Robust z-score"] == "—"


def test_language_consistency_and_text_export():
    row = scored_series([0, 1] * 4 + [-20]).iloc[-1]
    english = explain(row, PUBLISHED, **SETTINGS)
    french = explain(row, PUBLISHED, language="fr", **SETTINGS)
    assert english[1] != french[1]
    assert "dépasse 3.5" in french[1]
    for index, ((_, en), (_, fr)) in enumerate(zip(english[2], french[2], strict=True)):
        if index != 2:  # Metric titles are translated; source and numeric evidence stay fixed.
            assert en == fr
    report = text_report(french)
    assert "2026-02-27" in report and "-20.500 pp" in report and ASSETS in report
    assert french[3] in report


@pytest.mark.parametrize(("metric", "expected"), [(CALCULATED, 7), (PUBLISHED, 10)])
def test_all_workbook_alerts_have_exact_prior_baselines(metric, expected):
    assets = load_workbook()[ASSETS]
    if metric == CALCULATED:
        frame = calculated_weekly_change(assets)
        column = OBSERVED
    else:
        frame = assets
        column = VARIATIONS[0]
    scored = detect_anomalies(frame, column)
    alerts = rank_alerts(scored.loc[scored[STATUS].eq(ANOMALY) & scored[CATEGORY].ne(TOTAL)])
    assert len(alerts) == expected
    assert alerts[SCORE].abs().is_monotonic_decreasing
    for _, row in alerts.iterrows():
        baseline = baseline_for(scored, row)
        assert len(baseline) == row[HISTORY]
        assert baseline[DATE].lt(row[DATE]).all()
        assert baseline[OBSERVED].median() == pytest.approx(row[CENTER])
        assert (baseline[OBSERVED] - row[CENTER]).abs().median() == pytest.approx(row[MAD])
        report = text_report(explain(row, metric, window=26, minimum=8, threshold=3.5))
        assert row["Fichier d’origine"] in report
        assert str(row[DATE].date()) in report


def test_explanation_tab_language_and_alert_selection():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    assert next(tab for tab in app.tabs if tab.label == "Explainable AI").label == "Explainable AI"
    tab = next(tab for tab in app.tabs if tab.label == "Explainable AI")
    assert len(tab.selectbox[0].options) == 7
    tab.selectbox[0].select_index(1)
    tab.radio[0].set_value("Français")
    app.run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "Explainable AI")
    selected = tab.selectbox[0].options[1]
    evidence = tab.dataframe[0].value.set_index("Field")["Value"]
    assert evidence["Date du rapport"] in selected
    assert evidence["Catégorie"] in selected
    assert tab.get("plotly_chart") and tab.get("download_button")
    assert any("a signalé" in item.value for item in tab.markdown)

    smartflow = next(tab for tab in app.tabs if tab.label == "SmartFlow")
    next(widget for widget in smartflow.multiselect if widget.label == "SmartFlow categories").set_value([])
    app.run(timeout=30)
    assert not app.exception
    assert any("No detected alerts" in item.value for item in next(tab for tab in app.tabs if tab.label == "Explainable AI").info)


@pytest.mark.parametrize(("metric", "prior", "score", "history", "january_history"), [
    (CALCULATED, 29.859, 7.372, 13, 0),
    (PUBLISHED, 29.860, 5.711, 16, 1),
])
def test_obligations_ct_alert_chronology_and_source(metric, prior, score, history, january_history):
    from src.anomalies import INSUFFICIENT
    from src.data_loader import AMOUNT, PROVENANCE

    assets = load_workbook()[ASSETS]
    category = assets.loc[assets[CATEGORY].eq("Obligations CT")].set_index(DATE)
    calculated = metric == CALCULATED
    frame = calculated_weekly_change(assets) if calculated else assets
    scored = detect_anomalies(frame, OBSERVED if calculated else VARIATIONS[0])
    alert = scored.loc[
        scored[CATEGORY].eq("Obligations CT") & scored[DATE].eq("2026-04-24")
    ].iloc[0]
    original = category.loc["2026-04-24"]
    assert alert[OBSERVED] == pytest.approx(
        100 * (original[AMOUNT] / category.loc["2026-04-17", AMOUNT] - 1)
        if calculated else original[VARIATIONS[0]]
    )
    assert alert[STATUS] == ANOMALY and alert[SCORE] == pytest.approx(score, abs=0.0005)
    baseline = baseline_for(scored, alert)
    assert len(baseline) == history and baseline[DATE].lt(alert[DATE]).all()
    peak = baseline.loc[baseline[OBSERVED].idxmax()]
    assert peak[DATE] == pd.Timestamp("2026-01-09")
    assert peak[OBSERVED] == pytest.approx(prior, abs=0.0005)
    assert peak[STATUS] == INSUFFICIENT and peak[HISTORY] == january_history
    report = text_report(explain(alert, metric, window=26, minimum=8, threshold=3.5))
    assert original[PROVENANCE[2]] in report and "Export line · 922" in report
    assert f"{alert[OBSERVED]:.3f}%" in report


def test_filtered_april_alert_shows_january_context_and_exports_txt(monkeypatch):
    from datetime import date

    import streamlit as st

    downloads = {}
    download_button = st.download_button

    def capture_download(label, data, *args, **kwargs):
        downloads[label] = (data, kwargs["file_name"])
        return download_button(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    smartflow = next(tab for tab in app.tabs if tab.label == "SmartFlow")
    smartflow.date_input[0].set_value((date(2026, 4, 24), date(2026, 4, 24)))
    next(w for w in smartflow.multiselect if w.label == "SmartFlow categories").set_value(
        ["Obligations CT"]
    )
    app.run(timeout=30)
    assert not app.exception
    xai = next(tab for tab in app.tabs if tab.label == "Explainable AI")
    assert len(xai.selectbox[0].options) == 1
    assert "2026-04-24 · Obligations CT" in xai.selectbox[0].options[0]
    assert any("29.859%" in message.value and "0 of 8" in message.value for message in xai.info)
    data, name = downloads["Download explanation (TXT)"]
    assert name.endswith("2026-04-24-alert.txt")
    report = data.decode("utf-8")
    assert "Report date · 2026-04-24" in report
    assert "Observed change · 18.923%" in report
    assert "Robust z-score · 7.372" in report
    assert "stat_opcvm_hebdo_ammc_24-04-2026.xls" in report
