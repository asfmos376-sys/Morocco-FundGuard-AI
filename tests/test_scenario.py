from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.data_loader import AMOUNT, ASSETS, PROVENANCE, load_workbook
from src.metrics import TOTAL, snapshot
from src.scenario import apply_shock, latest_baseline, market_share, validate_snapshot
from src.validation import CATEGORY, DATE


def report(amounts, day="2026-01-02"):
    return pd.DataFrame({
        DATE: [pd.Timestamp(day)] * len(amounts), CATEGORY: list(amounts), AMOUNT: list(amounts.values()),
        PROVENANCE[2]: [f"report-{day}.xlsx"] * len(amounts),
        PROVENANCE[3]: range(1, len(amounts) + 1),
    })


@pytest.mark.parametrize(("shock", "change", "after", "market"), [
    (0, 0, 40, 100), (25, 10, 50, 110), (-25, -10, 30, 90), (-100, -40, 0, 60),
])
def test_shocks_apply_only_the_selected_category(shock, change, after, market):
    baseline = validate_snapshot(report({"Actions": 40, "Monétaire": 60, TOTAL: 100}), ["Actions", "Monétaire"])
    result = apply_shock(baseline, "Actions", shock)
    assert result.change == change
    assert result.category_after == after
    assert result.market_after == market
    assert result.market_after - result.category_after == 60
    assert result.share_after == pytest.approx(after / market)


def test_invalid_denominators_and_shocks():
    baseline = validate_snapshot(report({"Actions": 100, TOTAL: 100}), ["Actions"])
    result = apply_shock(baseline, "Actions", -100)
    assert result.market_after == 0 and result.share_after is None
    for denominator in (0, -1, float("nan"), float("inf"), None):
        assert market_share(1, denominator) is None
    assert market_share(101, 100) is None
    with pytest.raises(ValueError, match="category is unavailable"):
        apply_shock(baseline, "Missing category", 0)
    for shock in (-101, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="finite shock"):
            apply_shock(baseline, "Actions", shock)


def test_mismatched_dates_missing_categories_and_mixed_source():
    records = report({"Actions": 40, "Monétaire": 60, TOTAL: 100})
    changed_date = records.copy()
    changed_date.loc[2, DATE] = pd.Timestamp("2026-01-09")
    with pytest.raises(ValueError, match="same report date"):
        validate_snapshot(changed_date, ["Actions", "Monétaire"])
    with pytest.raises(ValueError, match="every expected fund category"):
        validate_snapshot(records.drop(index=1), ["Actions", "Monétaire"])
    mixed = records.copy()
    mixed.loc[2, PROVENANCE[2]] = "another-report.xlsx"
    with pytest.raises(ValueError, match="common report and amount scale"):
        validate_snapshot(mixed, ["Actions", "Monétaire"])


def test_latest_eligible_baseline_rejects_bad_aggregation():
    first = report({"Actions": 40, "Monétaire": 60, TOTAL: 100})
    latest = report({"Actions": 50, "Monétaire": 60, TOTAL: 200}, "2026-01-09")
    with pytest.raises(ValueError, match="do not reconcile"):
        validate_snapshot(latest, ["Actions", "Monétaire"])
    baseline, skipped = latest_baseline(pd.concat([latest, first]))
    assert baseline.report_date.date() == date(2026, 1, 2)
    assert len(skipped) == 1 and "do not reconcile" in skipped[0][1]
    assert latest_baseline(latest)[0] is None


def test_workbook_baseline_matches_published_totals_and_provenance():
    assets = load_workbook()[ASSETS]
    baseline, skipped = latest_baseline(assets)
    assert not skipped and baseline.report_date.date() == date(2026, 11, 9)
    report_rows = snapshot(assets, baseline.report_date)
    assert baseline.market_total == report_rows.loc[report_rows[CATEGORY].eq(TOTAL), AMOUNT].item()
    assert len(baseline.categories) == 6 and TOTAL not in dict(baseline.categories)
    assert dict(baseline.export_lines)[TOTAL] == 2564
    assert baseline.original_file == "stat_opcvm_hebdo_ammc_09-11-2026.xlsx"
    assert abs(baseline.reconciliation_gap) < 0.0002
    scenario = apply_shock(baseline, "Actions", 10)
    assert scenario.market_after == pytest.approx(839966205270.9546)
    assert scenario.share_after == pytest.approx(scenario.category_after / scenario.market_after)


def test_scenario_tab_inputs_update_verified_output():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "Scenario Studio")
    tab.selectbox[0].select("Actions")
    tab.number_input[0].set_value(10.0).run(timeout=30)
    assert not app.exception
    tab = next(tab for tab in app.tabs if tab.label == "Scenario Studio")
    markup = "\n".join(item.proto.body for item in tab.get("html"))
    assert "839,966,205,270.95" in markup
    assert "2026-11-09" in markup and "stat_opcvm_hebdo_ammc_09-11-2026.xlsx" in markup
    assert tab.get("plotly_chart")
