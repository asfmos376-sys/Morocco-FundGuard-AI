import pandas as pd
import pytest

from src.data_loader import AMOUNT, ASSETS, load_workbook
from src.forecasting import ACTUAL, AVERAGE, MODELS, NAIVE, ORIGIN, WEEK, error_metrics, run_experiment
from src.validation import CATEGORY, DATE


def series(amounts):
    return pd.DataFrame({
        DATE: pd.date_range("2026-01-02", freq="7D", periods=len(amounts)),
        CATEGORY: "Actions", AMOUNT: amounts,
    })


def test_forecast_origins_and_no_future_leakage():
    data = series(list(range(1, 21)))
    first = run_experiment(data, "Actions")
    assert (first.predictions[DATE] - first.predictions[ORIGIN]).eq(WEEK).all()
    row = first.predictions.iloc[0]
    assert (row[ACTUAL], row[NAIVE], row[AVERAGE]) == (5, 4, 2.5)
    modified = data.copy()
    modified.loc[10:, AMOUNT] = 999999
    second = run_experiment(modified.sample(frac=1, random_state=5), "Actions")
    pd.testing.assert_frame_equal(first.predictions.iloc[:6], second.predictions.iloc[:6])
    assert first.predictions.iloc[6][list(MODELS)].tolist() == second.predictions.iloc[6][list(MODELS)].tolist()


def test_missing_values_and_dates_reset_training():
    data = series(list(range(1, 16)))
    data.loc[7, AMOUNT] = None
    data = data.drop(index=4)
    result = run_experiment(data, "Actions")
    assert result.predictions[DATE].tolist() == list(data.loc[12:, DATE])
    assert result.next_value is None


def test_short_and_empty_backtests():
    result = run_experiment(series([0, 0, 0]), "Actions")
    assert result.predictions.empty
    assert result.metrics["MAE"].isna().all()
    assert result.winner is None and result.next_value is None


def test_error_metrics_and_undefined_smape():
    errors = error_metrics(pd.Series([0.0, 10.0, 20.0]), pd.Series([0.0, 5.0, 25.0]))
    assert errors["MAE"] == pytest.approx(10 / 3)
    assert errors["RMSE"] == pytest.approx((50 / 3) ** 0.5)
    assert errors["sMAPE (%)"] == pytest.approx((1000 / 15 + 1000 / 45) / 2)
    assert errors["sMAPE folds"] == 2
    assert pd.isna(error_metrics(pd.Series([0.0]), pd.Series([0.0]))["sMAPE (%)"])


def test_workbook_backtest_and_publication_gate():
    assets = load_workbook()[ASSETS]
    experiments = {cat: run_experiment(assets, cat) for cat in assets[CATEGORY].unique()}
    assert all(len(exp.predictions) == 20 for exp in experiments.values())
    assert {cat: exp.winner for cat, exp in experiments.items() if exp.winner} == {"Monétaire": AVERAGE}
    assert all(exp.next_value is None for exp in experiments.values())
    assert experiments["TOTAL"].metrics.at[NAIVE, "sMAPE (%)"] == pytest.approx(1.7011874675299126)
