"""Regressões de calendário e informação disponível nos rankings LASTRO."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from quant_fund.adapters import sec_facts_to_fundamentals
from quant_fund.config import Sleeve1Config, Sleeve2Config
from quant_fund.sleeve1 import build_sleeve1
from quant_fund.sleeve2 import build_sleeve2
from quant_fund.utils import monthly_last, portfolio_returns


def _fundamentals(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["fiscal_date", "available_date", "total_assets"])
    frame["ticker"] = "AAA"
    frame["book_equity"] = 40.0
    frame["gross_profit"] = 20.0
    frame["market_cap"] = 100.0
    return frame


def _prices() -> pd.DataFrame:
    dates = pd.date_range("2021-01-31", "2023-08-31", freq="ME")
    return pd.DataFrame({"AAA": np.linspace(100.0, 140.0, len(dates))}, index=dates)


def test_sec_adapter_accepts_documented_columns_without_tag_priority() -> None:
    facts = pd.DataFrame(
        [
            (metric, value)
            for metric, value in {
                "assets": 100.0,
                "equity": 40.0,
                "gross_profit": 20.0,
                "shares_outstanding": 10.0,
            }.items()
        ],
        columns=["metric", "value"],
    )
    facts["ticker"] = "AAA"
    facts["fiscal_period_end"] = "2021-12-31"
    facts["availability_date"] = "2022-03-01"
    expected = sec_facts_to_fundamentals(facts.assign(tag_priority=0))
    assert_frame_equal(sec_facts_to_fundamentals(facts), expected)
    assert expected.loc[0, "total_assets"] == 100.0


def test_future_revision_cannot_change_past_factors_or_portfolio() -> None:
    fundamentals = _fundamentals(
        [
            ("2019-12-31", "2020-03-01", 90.0),
            ("2020-12-31", "2021-03-01", 100.0),
            ("2021-12-31", "2022-03-01", 110.0),
        ]
    )
    revised = pd.concat(
        [fundamentals, _fundamentals([("2020-12-31", "2023-03-01", 500.0)])],
        ignore_index=True,
    )
    config = Sleeve1Config(top_n=1, max_statement_age_months=None)
    baseline = build_sleeve1(_prices(), fundamentals, config)
    actual = build_sleeve1(_prices(), revised, config)
    assert_frame_equal(actual.signals, baseline.signals)
    assert_frame_equal(actual.weights, baseline.weights)
    assert_series_equal(actual.returns, baseline.returns)
    june = actual.signals.loc[actual.signals["signal_date"].eq("2022-06-30")].iloc[0]
    assert june["investment_raw"] == pytest.approx(-0.10)
    assert june["fiscal_date"] == pd.Timestamp("2021-12-31")


def test_asset_growth_waits_for_disclosure_of_both_statements() -> None:
    fundamentals = _fundamentals(
        [
            ("2020-12-31", "2022-09-01", 100.0),
            ("2021-12-31", "2022-03-01", 110.0),
        ]
    )
    result = build_sleeve1(
        _prices(), fundamentals, Sleeve1Config(top_n=1, max_statement_age_months=None)
    )
    assert not result.signals["signal_date"].eq("2022-06-30").any()
    june = result.signals.loc[result.signals["signal_date"].eq("2023-06-30")].iloc[0]
    assert june["available_date"] == pd.Timestamp("2022-09-01")
    assert june["fiscal_date"] == pd.Timestamp("2021-12-31")
    assert june["investment_raw"] == pytest.approx(-0.10)


def test_missing_calendar_month_cannot_be_reported_as_one_month_return() -> None:
    dates = pd.to_datetime(["2024-01-31", "2024-03-31", "2024-04-30"])
    prices = pd.DataFrame({"AAA": [100.0, 121.0, 133.1]}, index=dates)
    weights = pd.DataFrame({"AAA": 1.0}, index=dates)
    with pytest.raises(ValueError, match="meses ausentes: 2024-02"):
        portfolio_returns(prices, weights)


def test_missing_month_cannot_compress_twelve_month_momentum_window() -> None:
    dates = pd.date_range("2022-01-31", periods=16, freq="ME")
    dates = dates.delete(6)
    prices = pd.DataFrame({"AAA": 100.0 * 1.01 ** np.arange(len(dates))}, index=dates)
    credit = pd.Series(1.0, index=dates)
    with pytest.raises(ValueError, match="meses ausentes: 2022-07"):
        build_sleeve2(prices, credit, config=Sleeve2Config(spread_window_months=2))


def test_explicit_missing_month_preserves_missing_returns_without_imputation() -> None:
    dates = pd.date_range("2024-01-31", periods=4, freq="ME")
    prices = pd.DataFrame({"AAA": [100.0, np.nan, 121.0, 133.1]}, index=dates)
    weights = pd.DataFrame({"AAA": 1.0}, index=dates)
    returns = portfolio_returns(prices, weights)
    assert returns.iloc[:3].isna().all()
    assert returns.iloc[3] == pytest.approx(0.10)
    assert pd.isna(monthly_last(prices).iloc[1, 0])
