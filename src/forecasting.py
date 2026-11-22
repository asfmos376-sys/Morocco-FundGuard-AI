"""Exact seven-day, expanding-origin net asset forecast experiment."""
from dataclasses import dataclass
from math import sqrt

import pandas as pd

from src.anomalies import ordered_records
from src.data_loader import AMOUNT
from src.validation import CATEGORY, DATE, parse_numeric

WEEK = pd.Timedelta(days=7)
WINDOW = 4
NAIVE = "Persistence"
AVERAGE = "Moving average (4 weeks)"
SMOOTH = "Exponential smoothing (α = 0.5)"
MODELS = (NAIVE, AVERAGE, SMOOTH)
ACTUAL = "Actual"
ORIGIN = "Forecast origin"
MIN_FOLDS = 12


@dataclass
class Experiment:
    history: pd.DataFrame
    predictions: pd.DataFrame
    metrics: pd.DataFrame
    winner: str | None
    next_date: pd.Timestamp
    next_value: float | None


def model_predictions(values):
    recent = values[-WINDOW:]
    return {
        NAIVE: recent.iloc[-1],
        AVERAGE: recent.mean(),
        SMOOTH: values.ewm(alpha=0.5, adjust=False).mean().iloc[-1],
    }


def error_metrics(actual, predicted):
    error = (actual - predicted).abs()
    denominator = actual.abs() + predicted.abs()
    valid = denominator.gt(0)
    return {
        "MAE": error.mean(), "RMSE": sqrt(error.pow(2).mean()),
        "sMAPE (%)": (200 * error[valid] / denominator[valid]).mean(),
        "sMAPE folds": int(valid.sum()),
    }


def select_model(predictions, metrics):
    """Apply a predefined consistency screen against persistence."""
    if len(predictions) < MIN_FOLDS or metrics.at[NAIVE, "MAE"] <= 0:
        return None
    abs_errors = predictions[list(MODELS)].sub(predictions[ACTUAL], axis=0).abs()
    midpoint = len(abs_errors) // 2
    baseline = abs_errors[NAIVE]
    candidates = [
        model for model in MODELS[1:]
        if metrics.at[model, "MAE"] <= 0.95 * metrics.at[NAIVE, "MAE"]
        and metrics.at[model, "RMSE"] <= 0.95 * metrics.at[NAIVE, "RMSE"]
        and (abs_errors[model] < baseline).mean() >= 0.60
        and abs_errors[model].iloc[:midpoint].mean() < baseline.iloc[:midpoint].mean()
        and abs_errors[model].iloc[midpoint:].mean() < baseline.iloc[midpoint:].mean()
    ]
    return min(candidates, key=lambda model: metrics.at[model, "MAE"], default=None)


def run_experiment(assets, category):
    records = ordered_records(assets.loc[assets[CATEGORY].eq(category), [DATE, CATEGORY, AMOUNT]])
    if records.empty:
        raise ValueError("No net asset series for the selected category.")
    amounts = parse_numeric(records[AMOUNT], AMOUNT)
    if amounts.lt(0).any():
        raise ValueError("Net assets must be nonnegative for this experiment.")
    history = records.assign(**{AMOUNT: amounts}).set_index(DATE)
    values = history[AMOUNT]
    dates = values.index.to_series()
    # Missing values and nonweekly intervals split the series into independent blocks.
    groups = (dates.diff().ne(WEEK) | values.isna() | values.shift().isna()).cumsum()
    rows = []
    latest_block = values.iloc[:0]
    for _, block in values.groupby(groups):
        latest_block = block.dropna()
        for offset in range(WINDOW, len(latest_block)):
            past = latest_block.iloc[:offset]
            rows.append({
                DATE: latest_block.index[offset], ORIGIN: past.index[-1],
                ACTUAL: latest_block.iloc[offset], **model_predictions(past),
            })
    predictions = pd.DataFrame(rows, columns=[DATE, ORIGIN, ACTUAL, *MODELS])
    metrics = pd.DataFrame.from_dict(
        {model: error_metrics(predictions[ACTUAL], predictions[model]) for model in MODELS},
        orient="index",
    )
    metrics["MAE improvement vs persistence (%)"] = (
        100 * (1 - metrics["MAE"] / metrics.at[NAIVE, "MAE"])
        if metrics.at[NAIVE, "MAE"] > 0 else float("nan")
    )
    winner = select_model(predictions, metrics)
    next_date = values.index[-1] + WEEK
    forecast = model_predictions(latest_block)[winner] if winner and len(latest_block) >= WINDOW else None
    return Experiment(history, predictions, metrics, winner, next_date, forecast)
