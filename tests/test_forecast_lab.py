from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.data_loader import AMOUNT, ASSETS, load_workbook
from src.forecast_lab import MAE_GAIN, MOVING, RIDGE, TRAINING_COUNT, forecastable_categories, run_lab
from src.forecasting import ACTUAL, NAIVE, ORIGIN, WEEK
from src.validation import CATEGORY, DATE


def series(values):
    return pd.DataFrame({
        DATE: pd.date_range("2026-01-02", periods=len(values), freq="7D"),
        CATEGORY: "Actions", AMOUNT: values,
    })


def test_ridge_walk_forward_does_not_use_current_or_future_targets():
    data = series([100 + i + (i % 4) * 9 for i in range(45)])
    before = run_lab(data, "Actions")
    assert RIDGE in before.metrics.index
    assert (before.predictions[DATE] - before.predictions[ORIGIN]).eq(WEEK).all()
    assert before.predictions[TRAINING_COUNT].iloc[0] == 10
    target = data.at[30, DATE]
    data.loc[30:, AMOUNT] *= 3
    after = run_lab(data.sample(frac=1, random_state=5), "Actions")
    columns = [DATE, ORIGIN, NAIVE, MOVING, RIDGE, TRAINING_COUNT]
    pd.testing.assert_frame_equal(
        before.predictions.loc[before.predictions[DATE].le(target), columns],
        after.predictions.loc[after.predictions[DATE].le(target), columns],
    )
    assert before.predictions.loc[before.predictions[DATE].eq(target), ACTUAL].item() != (
        after.predictions.loc[after.predictions[DATE].eq(target), ACTUAL].item()
    )


def test_missing_dates_and_values_break_lag_windows():
    data = series(range(1, 19)).drop(index=6)
    data.loc[10, AMOUNT] = None
    result = run_lab(data, "Actions", window=3)
    assert result.predictions[DATE].tolist() == list(data.loc[[3, 4, 5, 14, 15, 16, 17], DATE])
    assert result.contiguous_count == 7
    assert RIDGE not in result.metrics.index and result.forecast is None


def test_short_series_and_zero_denominator():
    data = series([0, 0, 0])
    result = run_lab(data, "Actions", window=2)
    assert result.winner is None and result.forecast is None
    assert result.metrics.at[NAIVE, "MAE"] == 0
    assert pd.isna(result.metrics.at[NAIVE, "sMAPE (%)"])
    assert run_lab(data, "Actions", window=4).predictions.empty


def test_baselines_accuracy_model_selection_and_reproducibility():
    data = series([90, 110] * 18)
    first = run_lab(data, "Actions", window=2, include_ridge=False)
    second = run_lab(data.sample(frac=1, random_state=8), "Actions", window=2, include_ridge=False)
    pd.testing.assert_frame_equal(first.predictions, second.predictions)
    pd.testing.assert_frame_equal(first.metrics, second.metrics)
    assert first.metrics.at[NAIVE, "MAE"] == 20
    assert first.metrics.at[NAIVE, "RMSE"] == 20
    assert first.metrics.at[NAIVE, "sMAPE (%)"] == 20
    assert first.metrics.at[MOVING, "MAE"] == 10
    assert first.metrics.at[MOVING, MAE_GAIN] == 50
    assert first.winner == MOVING and first.forecast == 100
    assert first.target_date == data[DATE].max() + WEEK


def test_actual_workbook_coverage_and_selection():
    assets = load_workbook()[ASSETS]
    categories = forecastable_categories(assets)
    assert len(categories) == 7 and "TOTAL" in categories
    total = run_lab(assets, "TOTAL")
    assert total.history.notna().sum() == 44 and total.weekly_pairs == 33
    assert total.baseline_folds == 20 and total.ridge_folds == 12 and len(total.predictions) == 12
    assert total.metrics.at[NAIVE, "sMAPE (%)"] == pytest.approx(1.690159, abs=1e-6)
    assert all(run_lab(assets, cat).forecast is None for cat in categories)
    monetary = run_lab(assets, "Monétaire", include_ridge=False)
    assert monetary.winner == MOVING and monetary.contiguous_count == 1 and monetary.forecast is None


def test_lab_navigation_and_model_controls():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    lab = next(tab for tab in app.tabs if tab.label == "Forecast Lab")
    assert lab.selectbox[0].value == "TOTAL"
    assert RIDGE in lab.dataframe[0].value.index
    lab.selectbox[0].select("Monétaire")
    lab.checkbox[0].set_value(False).run(timeout=30)
    assert not app.exception
    lab = next(tab for tab in app.tabs if tab.label == "Forecast Lab")
    assert RIDGE not in lab.dataframe[0].value.index
    assert any("latest report block" in notice.value for notice in lab.info)
