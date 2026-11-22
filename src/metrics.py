"""Calculations on measurements from the same report."""
import pandas as pd

from src.data_loader import REDS, SUBS
from src.validation import CATEGORY, DATE

TOTAL = "TOTAL"
NET_FLOW = "Net subscriptions"


def filter_records(frame, start, end, categories):
    dates = frame[DATE].between(pd.Timestamp(start), pd.Timestamp(end))
    return frame.loc[dates & frame[CATEGORY].isin(categories)].copy()


def snapshot(frame, report_date):
    return frame.loc[frame[DATE].eq(pd.Timestamp(report_date))]


def add_net_flows(frame):
    return frame.assign(**{NET_FLOW: frame[SUBS] - frame[REDS]})
