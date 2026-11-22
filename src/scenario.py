"""Single-category shocks anchored to a reconciled net asset report."""
from dataclasses import dataclass
from math import fsum, isfinite

import pandas as pd

from src.data_loader import AMOUNT, PROVENANCE
from src.metrics import TOTAL, snapshot
from src.validation import CATEGORY, DATE, validate_keys

# Absolute tolerance on the original scale. The consolidated reports exhibit
# residuals up to about 0.02 between category sums and the published TOTAL.
RECONCILIATION_TOLERANCE = 0.05


@dataclass(frozen=True)
class Baseline:
    report_date: pd.Timestamp
    original_file: str
    market_total: float
    categories: tuple[tuple[str, float], ...]
    export_lines: tuple[tuple[str, int], ...]
    reconciliation_gap: float


@dataclass(frozen=True)
class Scenario:
    category_before: float
    market_before: float
    change: float
    category_after: float
    market_after: float | None
    share_before: float | None
    share_after: float | None


def validate_snapshot(records, categories):
    """Require the full category breakdown and one published TOTAL from a common report."""
    if records.empty or records[DATE].nunique(dropna=False) != 1:
        raise ValueError("The category amounts and market total must come from the same report date.")
    validate_keys(records)
    if not categories or TOTAL in categories or set(records[CATEGORY]) != set(categories) | {TOTAL}:
        raise ValueError("The report must contain the published TOTAL and every expected fund category.")
    # A single source report and one schema column establish a common workbook scale.
    filenames = records[PROVENANCE[2]]
    if filenames.isna().any() or filenames.nunique() != 1 or not str(filenames.iloc[0]).strip():
        raise ValueError("Source provenance does not establish a common report and amount scale.")
    if records[PROVENANCE[3]].isna().any():
        raise ValueError("Source export lines are missing.")
    amounts = records.set_index(CATEGORY)[AMOUNT]
    if amounts.isna().any() or any(not isfinite(value) or value < 0 for value in amounts):
        raise ValueError("All category and market amounts must be finite and nonnegative.")
    total = float(amounts[TOTAL])
    if total <= 0:
        raise ValueError("The published market total must be positive.")
    values = tuple((category, float(amounts[category])) for category in categories)
    gap = fsum(value for _, value in values) - total
    if abs(gap) > RECONCILIATION_TOLERANCE or any(value > total for _, value in values):
        raise ValueError("Category amounts do not reconcile with the published market TOTAL.")
    return Baseline(
        records[DATE].iloc[0], str(filenames.iloc[0]), total, values,
        tuple((category, int(line)) for category, line in zip(records[CATEGORY], records[PROVENANCE[3]], strict=True)),
        gap,
    )


def latest_baseline(assets):
    """Find the latest eligible report, retaining earlier rejection reasons for display."""
    expected = sorted(set(assets[CATEGORY].dropna()) - {TOTAL})
    skipped = []
    for report_date in sorted(assets[DATE].dropna().unique(), reverse=True):
        try:
            return validate_snapshot(snapshot(assets, report_date), expected), tuple(skipped)
        except ValueError as error:
            skipped.append((report_date, str(error)))
    return None, tuple(skipped)


def market_share(category_amount, total):
    """Return a share fraction only for a positive, compatible denominator."""
    if total is None or not isfinite(total) or total <= 0 or not 0 <= category_amount <= total:
        return None
    return category_amount / total


def apply_shock(baseline, category, shock):
    values = dict(baseline.categories)
    if category not in values:
        raise ValueError("The category is unavailable in the eligible baseline.")
    if not isfinite(shock) or shock < -100:
        raise ValueError("Enter a finite shock of at least −100%.")
    before = values[category]
    change = before * (shock / 100)
    after = before + change
    adjusted_total = baseline.market_total + change
    if not all(map(isfinite, (change, after, adjusted_total))):
        raise ValueError("The shock exceeds the supported numeric range.")
    market_after = adjusted_total if adjusted_total >= 0 else None
    return Scenario(
        before, baseline.market_total, change, after, market_after,
        market_share(before, baseline.market_total), market_share(after, market_after),
    )
