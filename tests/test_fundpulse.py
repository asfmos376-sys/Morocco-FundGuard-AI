from datetime import datetime

import pandas as pd
import pytest

from src.data_loader import AMOUNT, ASSETS, FLOWS, HOLDINGS, INDICES, load_workbook
from src.metrics import NET_FLOW, TOTAL, add_net_flows, filter_records, snapshot
from src.validation import CATEGORY, DATE, parse_dates, parse_numeric, validate_keys


@pytest.fixture(scope="module")
def tables():
    return load_workbook()


def test_workbook_loads_all_metric_tables(tables):
    assert {name: len(table) for name, table in tables.items()} == {
        ASSETS: 308, INDICES: 220, HOLDINGS: 528, FLOWS: 308,
    }
    for table in tables.values():
        assert table[DATE].nunique() == 44
        assert table[DATE].min() == pd.Timestamp("2026-01-02")
        assert table[DATE].max() == pd.Timestamp("2026-11-09")
        assert not table.duplicated([DATE, CATEGORY]).any()


def test_date_parsing():
    values = pd.Series([datetime(2026, 1, 2), "2026-11-09"])
    assert parse_dates(values).tolist() == [
        pd.Timestamp("2026-01-02"), pd.Timestamp("2026-11-09"),
    ]
    for invalid in ("2026-02-30", None, 46024):
        with pytest.raises(ValueError, match="invalid report dates"):
            parse_dates(pd.Series([invalid]))


def test_numeric_conversion():
    result = parse_numeric(pd.Series(["10.28", None, 0, -2]), "value")
    assert result.dropna().tolist() == [10.28, 0, -2]
    assert pd.isna(result.iloc[1])
    for invalid in ("unverified text", float("inf")):
        with pytest.raises(ValueError, match="invalid numeric"):
            parse_numeric(pd.Series([invalid]), "value")


def test_duplicate_key_with_different_measurements():
    frame = pd.DataFrame({
        DATE: [pd.Timestamp("2026-01-02")] * 2, CATEGORY: ["Actions"] * 2,
        AMOUNT: [1, 2],
    })
    with pytest.raises(ValueError, match="share a report date"):
        validate_keys(frame)


def test_missing_amounts_stay_missing(tables):
    holdings = tables[HOLDINGS]
    missing = holdings.loc[holdings[AMOUNT].isna()]
    assert missing[DATE].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-09", "2026-03-06", "2026-05-08", "2026-07-10",
    ]
    assert holdings[AMOUNT].eq(0).any()


def test_market_snapshot_and_net_flow(tables):
    day = "2026-01-02"
    assets = tables[ASSETS]
    market = snapshot(filter_records(assets, day, day, [TOTAL]), day)
    assert market[AMOUNT].item() == pytest.approx(738134446339.4608)
    actions = filter_records(tables[FLOWS], day, day, ["Actions"])
    assert add_net_flows(actions)[NET_FLOW].item() == pytest.approx(323487551.48)
    assert snapshot(market, "2026-01-03").empty


def test_net_flows_preserve_unknown_inputs():
    frame = pd.DataFrame({
        "Volume de souscriptions": [5, 0, None],
        "Volume de rachats": [None, 0, 5],
    })
    assert add_net_flows(frame)[NET_FLOW].isna().tolist() == [True, False, True]
    assert add_net_flows(frame)[NET_FLOW].iloc[1] == 0


def test_reported_market_share_uses_full_published_total(tables):
    from src.data_loader import SHARE

    assets = tables[ASSETS]
    market = assets.loc[assets[CATEGORY].eq(TOTAL)].set_index(DATE)
    funds = assets.loc[assets[CATEGORY].ne(TOTAL)]
    assert len(market) == 44
    assert funds.groupby(DATE)[CATEGORY].nunique().eq(6).all()
    assert funds[[AMOUNT, SHARE]].notna().all().all()
    assert (funds.groupby(DATE)[AMOUNT].sum() - market[AMOUNT]).abs().max() < 0.03
    expected = 100 * funds[AMOUNT] / funds[DATE].map(market[AMOUNT])
    assert (funds[SHARE] - expected).abs().max() < 0.005
    assert (funds.groupby(DATE)[SHARE].sum() - 100).abs().max() < 0.011


def test_dashboard_chart_filters_and_market_scope(tables):
    import json
    from datetime import date
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    def chart_traces(app):
        assert not app.exception
        return [json.loads(chart.proto.spec)["data"] for tab in app.tabs[:4] for chart in tab.get("plotly_chart")]

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    next(widget for widget in app.multiselect if widget.label == "Fund categories").set_value(
        ["Actions"]
    )
    date_filter = next(widget for widget in app.date_input if widget.label == "Report date range")
    date_filter.set_value((date(2026, 10, 16), date(2026, 10, 25))).run()
    market, category, share, index, flows, portfolio = chart_traces(app)
    dates = ["2026-10-16", "2026-10-23"]
    for trace, name in zip(
        (market, category, index, flows, portfolio),
        (TOTAL, "Actions", "Actions", "Actions", "Actif total"),
    ):
        assert len(trace) == 1
        assert trace[0]["name"] == name
        assert [value[:10] for value in trace[0]["x"]] == dates
    assert share[0]["y"] == ["Actions"]
    overview_html = [item.proto.body for item in app.tabs[0].get("html")]
    assert any("23 Oct 2026" in body and "Percent of published" in body for body in overview_html)
    published_total = snapshot(tables[ASSETS], dates[-1])
    amount = published_total.loc[published_total[CATEGORY].eq(TOTAL), AMOUNT].item()
    assert any(f"<dt>Market net assets</dt><dd>{amount:,.2f}</dd>" in body for body in overview_html)

    app.checkbox[0].set_value(True).run()
    assert [trace["name"] for trace in chart_traces(app)[4]] == [TOTAL]

    next(widget for widget in app.date_input if widget.label == "Report date range").set_value(
        (date(2026, 10, 24), date(2026, 10, 25))
    ).run()
    assert not chart_traces(app)
    assert not any("fg-v2-kpi" in item.proto.body and "<dl" in item.proto.body
                   for item in app.tabs[0].get("html"))
    assert any("No published market snapshot" in item.value for item in app.tabs[0].info)
