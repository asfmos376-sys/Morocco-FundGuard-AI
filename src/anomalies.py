"""Chronological robust anomaly scoring for report series."""
from collections import deque
from math import isfinite
from statistics import median

import pandas as pd

from src.data_loader import AMOUNT
from src.validation import CATEGORY, DATE, parse_dates, parse_numeric, validate_keys

OBSERVED = "Observed value (%)"
CENTER = "Historical median (%)"
MAD = "Historical MAD (pp)"
SCORE = "Robust z-score"
STATUS = "Alert status"
HISTORY = "Prior valid observations"
ANOMALY = "Anomaly"
NORMAL = "Within threshold"
INSUFFICIENT = "Insufficient baseline"
UNDEFINED = "Undefined score"
MISSING = "Missing observation"
DEFAULT_WINDOW = 26
DEFAULT_MINIMUM = 8
DEFAULT_THRESHOLD = 3.5
MAD_SCALE = 0.6744897501960817


def ordered_records(frame):
    records = frame.copy()
    records[DATE] = parse_dates(records[DATE])
    validate_keys(records)
    return records.sort_values(DATE, kind="stable").reset_index(drop=True)


def calculated_weekly_change(frame):
    """Attach exact seven-day changes and retain the input evidence."""
    records = ordered_records(frame)
    records[AMOUNT] = parse_numeric(records[AMOUNT], AMOUNT)
    grouped = records.groupby(CATEGORY, sort=False)
    previous_date = grouped[DATE].shift()
    previous = grouped[AMOUNT].shift()
    elapsed = (records[DATE] - previous_date).dt.days
    valid = elapsed.eq(7) & previous.gt(0) & records[AMOUNT].ge(0)
    change = 100 * (records[AMOUNT].where(valid) / previous.where(valid) - 1)
    return records.assign(**{
        OBSERVED: change.where(~change.isin([float("inf"), float("-inf")])),
        "Previous report date": previous_date,
        "Days since previous report": elapsed,
        "Previous net assets": previous,
    })


def detect_anomalies(
    frame, metric=OBSERVED, *, window=DEFAULT_WINDOW, minimum=DEFAULT_MINIMUM,
    threshold=DEFAULT_THRESHOLD,
):
    """Score each category separately against its preceding valid observations."""
    if not isinstance(window, int) or not isinstance(minimum, int) or not 8 <= minimum <= window:
        raise ValueError("Use a baseline window at least as large as the minimum of 8.")
    if not isfinite(threshold) or threshold <= 0:
        raise ValueError("The score threshold must be positive and finite.")

    records = ordered_records(frame)
    records[OBSERVED] = parse_numeric(records[metric], metric)
    results = []
    for _, series in records.groupby(CATEGORY, sort=False):
        history = deque(maxlen=window)
        for index, observed in series[OBSERVED].items():
            center = spread = score = None
            if pd.isna(observed):
                status = MISSING
            elif len(history) < minimum:
                status = INSUFFICIENT
            else:
                center = median(history)
                spread = median(abs(value - center) for value in history)
                candidate = MAD_SCALE * (observed - center) / spread if spread > 0 else None
                if candidate is None or not all(map(isfinite, (center, spread, candidate))):
                    status = UNDEFINED
                else:
                    score = candidate
                    status = ANOMALY if abs(score) > threshold else NORMAL
            results.append((index, len(history), center, spread, score, status))
            if pd.notna(observed):
                history.append(float(observed))

    evidence = pd.DataFrame.from_records(
        results, columns=["index", HISTORY, CENTER, MAD, SCORE, STATUS],
    ).set_index("index")
    return records.join(evidence)
