"""Validate source records without filling missing measurements."""
from datetime import date

import pandas as pd

DATE = "Date"
CATEGORY = "Catégorie"


def parse_dates(values):
    dates = pd.to_datetime(values.astype("string"), format="%Y-%m-%d", errors="coerce")
    # Excel date cells arrive as datetime objects. Text dates must be ISO.
    native = values.map(lambda value: isinstance(value, date))
    dates.loc[native] = pd.to_datetime(values.loc[native], errors="coerce").dt.normalize()
    if dates.isna().any():
        raise ValueError("Date contains missing or invalid report dates.")
    return dates


def parse_numeric(values, column):
    numeric = pd.to_numeric(values, errors="coerce")
    invalid = (values.notna() & numeric.isna()) | numeric.isin([float("inf"), float("-inf")])
    if invalid.any():
        raise ValueError(f"{column} contains invalid numeric measurements.")
    return numeric


def validate_keys(frame):
    keys = [DATE, CATEGORY]
    if frame[keys].isna().any().any():
        raise ValueError("Missing report date or category.")
    duplicates = frame.duplicated(keys, keep=False)
    if duplicates.any():
        raise ValueError(f"{duplicates.sum()} records share a report date and category.")
