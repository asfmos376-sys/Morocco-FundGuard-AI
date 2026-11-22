from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.anomalies import (
    ANOMALY, CENTER, HISTORY, INSUFFICIENT, MISSING, NORMAL, OBSERVED, SCORE,
    STATUS, UNDEFINED, calculated_weekly_change, detect_anomalies,
)
from src.data_loader import AMOUNT
from src.validation import CATEGORY, DATE


def series(values, category="Actions", metric=OBSERVED):
    return pd.DataFrame({
        DATE: pd.date_range("2026-01-02", periods=len(values), freq="7D"),
        CATEGORY: category, metric: values,
    })


def test_normal_extreme_and_insufficient_baseline():
    scored = detect_anomalies(series([0, 1] * 4 + [0.5, 20]))
    assert scored[STATUS].tolist() == [INSUFFICIENT] * 8 + [NORMAL, ANOMALY]
    assert scored[SCORE].iloc[:8].isna().all()
    assert scored.iloc[8][SCORE] == 0
    assert scored.iloc[9][CENTER] == 0.5
    assert scored.iloc[9][SCORE] == pytest.approx(26.305100257647186)
    strict = detect_anomalies(series([0, 1] * 4 + [0.5, 20]), threshold=scored.iloc[9][SCORE])
    assert strict.iloc[9][STATUS] == NORMAL


def test_zero_mad_and_missing_values():
    scored = detect_anomalies(series([1] * 8 + [None, 0]))
    assert scored[STATUS].tail(2).tolist() == [MISSING, UNDEFINED]
    assert scored[HISTORY].tail(2).tolist() == [8, 8]
    assert scored[SCORE].isna().all()
    assert scored.iloc[-1][OBSERVED] == 0


def test_duplicate_report_dates_within_category_are_rejected():
    observations = series([1, 2])
    observations.loc[1, DATE] = observations.loc[0, DATE]
    with pytest.raises(ValueError, match="share a report date and category"):
        detect_anomalies(observations)


def test_category_separation_and_chronological_no_lookahead():
    first = series([0, 1] * 4 + [10])
    second = series([100, 101] * 4 + [100.5], "Monétaire")
    future = series([0, 1] * 4 + [10, 500]).tail(1)
    combined = pd.concat([second, future, first]).sample(frac=1, random_state=42)
    scored = detect_anomalies(combined, window=8)
    actual = scored.loc[scored[CATEGORY].eq("Actions")].iloc[:-1].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, detect_anomalies(first, window=8), check_dtype=False)
    assert scored.loc[scored[CATEGORY].eq("Monétaire")].iloc[-1][STATUS] == NORMAL
    assert scored.iloc[-1][HISTORY] == 8


def test_calculated_change_requires_exact_week_with_valid_amounts():
    amounts = series([100, 110, None, 125, 0, 150, 160], metric=AMOUNT)
    amounts.loc[6, DATE] += pd.Timedelta(days=3)
    calculated = calculated_weekly_change(amounts)
    assert calculated[OBSERVED].notna().tolist() == [False, True, False, False, True, False, False]
    assert calculated.loc[1, OBSERVED] == pytest.approx(10)
    assert calculated.loc[4, OBSERVED] == -100
    assert calculated.loc[6, "Days since previous report"] == 10


def test_smartflow_filters_keep_history_outside_selected_dates():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    tab = next(tab for tab in app.tabs if tab.label == "SmartFlow")
    assert tab.label == "SmartFlow"
    assert tab.metric[0].value == "7"
    tab.selectbox[0].select("Published weekly net asset change").run(timeout=30)
    assert not app.exception
    assert next(tab for tab in app.tabs if tab.label == "SmartFlow").metric[0].value == "10"
    next(tab for tab in app.tabs if tab.label == "SmartFlow").selectbox[0].select("Calculated seven-day net asset change").run(timeout=30)
    tab = next(tab for tab in app.tabs if tab.label == "SmartFlow")
    alert = tab.dataframe[0].value.query("`Alert status` == 'Anomaly'").iloc[0]
    report_date = alert[DATE].date()
    category = alert[CATEGORY]
    tab.date_input[0].set_value((report_date, report_date))
    next(widget for widget in tab.multiselect if widget.label == "SmartFlow categories").set_value([category])
    next(widget for widget in tab.multiselect if widget.label == "Alert status").set_value([ANOMALY])
    app.run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "SmartFlow")
    assert tab.metric[0].value == "1"
    assert tab.dataframe[0].value.iloc[0][SCORE] == alert[SCORE]
    assert any("percentage points" in element.value for element in tab.markdown)
    assert tab.get("download_button")
