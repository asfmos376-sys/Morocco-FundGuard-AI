"""Leakage-safe, exact seven-day net asset forecasts."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.anomalies import ordered_records
from src.data_loader import AMOUNT
from src.forecasting import ACTUAL, MIN_FOLDS, NAIVE, ORIGIN, WEEK, error_metrics
from src.validation import CATEGORY, DATE, parse_numeric

MOVING = "Moving average"
RIDGE = "Lagged ridge regression"
MIN_TRAINING = 10
LAG_LEVELS = 3
TRAINING_COUNT = "Prior ridge training rows"
MAE_GAIN = "MAE improvement vs persistence (%)"
WIN_RATE = "Lower absolute error (%)"


@dataclass
class LabResult:
    history: pd.Series
    predictions: pd.DataFrame
    metrics: pd.DataFrame
    winner: str | None
    target_date: pd.Timestamp
    forecast: float | None
    contiguous_count: int
    weekly_pairs: int
    baseline_folds: int
    ridge_folds: int


def forecastable_categories(assets):
    """Expose categories with at least one exact weekly pair of valid net assets."""
    ordered = assets.sort_values(DATE, kind="stable")
    grouped = ordered.groupby(CATEGORY)
    weekly = grouped[DATE].diff().eq(WEEK)
    valid = ordered[AMOUNT].ge(0) & grouped[AMOUNT].shift().ge(0)
    return ordered.loc[weekly & valid, CATEGORY].drop_duplicates().tolist()


def lag_returns(values):
    levels = np.asarray(values[-LAG_LEVELS:], dtype=float)
    if len(levels) != LAG_LEVELS or np.any(levels <= 0):
        return None
    return levels[1:] / levels[:-1] - 1


def ridge_forecast(training, features, previous):
    if features is None or len(training) < MIN_TRAINING:
        return float("nan")
    x = np.stack([features for features, _ in training])
    y = np.array([target for _, target in training])
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1
    x = (x - center) / scale
    weights = np.linalg.solve(x.T @ x + np.eye(x.shape[1]), x.T @ (y - y.mean()))
    predicted_return = y.mean() + ((features - center) / scale) @ weights
    return float(max(0, previous * (1 + predicted_return)))


def comparison_metrics(predictions, models):
    metrics = pd.DataFrame.from_dict({
        model: error_metrics(predictions[ACTUAL], predictions[model]) for model in models
    }, orient="index")
    baseline_mae = metrics.at[NAIVE, "MAE"]
    metrics[MAE_GAIN] = 100 * (1 - metrics["MAE"] / baseline_mae) if baseline_mae > 0 else np.nan
    errors = predictions[list(models)].sub(predictions[ACTUAL], axis=0).abs()
    metrics[WIN_RATE] = 100 * errors.lt(errors[NAIVE], axis=0).mean()
    return metrics


def choose_model(predictions, metrics, models):
    """Require substantial, consistent out-of-sample gains over persistence."""
    if len(predictions) < MIN_FOLDS or metrics.at[NAIVE, "MAE"] <= 0:
        return None
    errors = predictions[list(models)].sub(predictions[ACTUAL], axis=0).abs()
    split = len(predictions) // 2
    baseline = errors[NAIVE]
    candidates = [
        model for model in models if model != NAIVE
        and metrics.at[model, MAE_GAIN] >= 5
        and metrics.at[model, "RMSE"] <= 0.95 * metrics.at[NAIVE, "RMSE"]
        and metrics.at[model, WIN_RATE] >= 60
        and errors[model].iloc[:split].mean() < baseline.iloc[:split].mean()
        and errors[model].iloc[split:].mean() < baseline.iloc[split:].mean()
    ]
    return min(candidates, key=lambda model: metrics.at[model, "MAE"], default=None)


def run_lab(assets, category, *, window=4, include_ridge=True):
    if not isinstance(window, int) or window < 2:
        raise ValueError("Moving average window must contain at least two weeks.")
    source = assets.loc[assets[CATEGORY].eq(category), [DATE, CATEGORY, AMOUNT]]
    if source.empty:
        raise ValueError("No net asset series for this category.")
    records = ordered_records(source)
    records[AMOUNT] = parse_numeric(records[AMOUNT], AMOUNT)
    if records[AMOUNT].lt(0).any():
        raise ValueError("Net assets must be nonnegative for this experiment.")
    history = records.set_index(DATE)[AMOUNT]
    training, recent, rows = [], [], []
    previous_date = None
    weekly_pairs = 0

    for date, actual in history.items():
        if previous_date is not None and date - previous_date != WEEK:
            recent.clear()
        if pd.isna(actual):
            recent.clear()
        else:
            weekly_pairs += int(bool(recent))
            features = lag_returns(recent) if include_ridge else None
            if len(recent) >= window:
                rows.append({
                    DATE: date, ORIGIN: previous_date, ACTUAL: actual,
                    NAIVE: recent[-1], MOVING: float(np.mean(recent[-window:])),
                    RIDGE: ridge_forecast(training, features, recent[-1]),
                    TRAINING_COUNT: len(training),
                })
            # The current target enters training only after all current predictions.
            if features is not None:
                training.append((features, actual / recent[-1] - 1))
            recent.append(actual)
        previous_date = date

    baseline = pd.DataFrame(rows, columns=[DATE, ORIGIN, ACTUAL, NAIVE, MOVING, RIDGE, TRAINING_COUNT])
    ridge_rows = baseline.dropna(subset=[RIDGE])
    models = (NAIVE, MOVING)
    predictions = baseline.drop(columns=[RIDGE, TRAINING_COUNT])
    if len(ridge_rows) >= MIN_FOLDS:
        models = (NAIVE, MOVING, RIDGE)
        predictions = ridge_rows.reset_index(drop=True)
    metrics = comparison_metrics(predictions, models)
    winner = choose_model(predictions, metrics, models)
    forecast = None
    if len(recent) >= window:
        if winner == MOVING:
            forecast = float(np.mean(recent[-window:]))
        elif winner == RIDGE:
            candidate = ridge_forecast(training, lag_returns(recent), recent[-1])
            if np.isfinite(candidate):
                forecast = candidate

    return LabResult(
        history, predictions, metrics, winner, history.index[-1] + WEEK, forecast,
        len(recent), weekly_pairs, len(baseline), len(ridge_rows),
    )
