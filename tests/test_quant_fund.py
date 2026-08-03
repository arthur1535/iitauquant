from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_series_equal

from quant_fund.adapters import long_prices_to_wide, sec_facts_to_fundamentals
from quant_fund.config import FundConfig, Sleeve1Config, Sleeve2Config
from quant_fund.portfolio import (
    build_fund_allocations,
    combine_security_weights,
    validate_fully_invested,
)
from quant_fund.pipeline import run_pipeline
from quant_fund.sleeve1 import build_sleeve1
from quant_fund.sleeve2 import apply_hysteresis, build_sleeve2
from quant_fund.sleeve3 import build_sleeve3
from quant_fund.utils import cross_sectional_zscore, targets_to_buy_and_hold_weights


class CrossSectionTests(unittest.TestCase):
    def test_zscore_winsorizes_and_standardizes(self) -> None:
        values = pd.Series({"A": 1.0, "B": 2.0, "C": 3.0, "OUT": 1_000_000.0})
        result = cross_sectional_zscore(values, 0.01, 0.99)
        self.assertAlmostEqual(float(result.mean()), 0.0, places=12)
        self.assertAlmostEqual(float(result.std(ddof=0)), 1.0, places=12)
        self.assertTrue(np.isfinite(result).all())


class AdapterTests(unittest.TestCase):
    def test_long_prices_adapter(self) -> None:
        frame = pd.DataFrame(
            {
                "month_end": ["2022-01-31", "2022-01-31", "2022-02-28", "2022-02-28"],
                "ticker": ["A", "B", "A", "B"],
                "adjusted_close": [10.0, 20.0, 11.0, 19.0],
            }
        )
        wide = long_prices_to_wide(frame)
        self.assertEqual(wide.shape, (2, 2))
        self.assertEqual(float(wide.loc["2022-02-28", "A"]), 11.0)

    def test_sec_adapter_keeps_first_filing_and_annual_facts(self) -> None:
        rows = []
        for metric, value in {
            "assets": 100.0,
            "equity": 40.0,
            "gross_profit": 20.0,
            "shares_outstanding": 10.0,
        }.items():
            rows.append(("AAA", metric, value, "2021-12-31", "2022-03-01", "FY", 0))
        rows.extend(
            [
                ("AAA", "assets", 999.0, "2021-12-31", "2022-06-01", "FY", 0),
                ("AAA", "gross_profit", 999.0, "2021-12-31", "2022-02-01", "Q4", 0),
            ]
        )
        facts = pd.DataFrame(
            rows,
            columns=[
                "ticker",
                "metric",
                "value",
                "fiscal_period_end",
                "availability_date",
                "fiscal_period",
                "tag_priority",
            ],
        )
        result = sec_facts_to_fundamentals(facts)
        self.assertEqual(float(result.loc[0, "total_assets"]), 100.0)
        self.assertEqual(float(result.loc[0, "gross_profit"]), 20.0)
        self.assertEqual(pd.Timestamp(result.loc[0, "available_date"]), pd.Timestamp("2022-03-01"))


class Sleeve1Tests(unittest.TestCase):
    def test_reporting_lag_and_next_month_execution(self) -> None:
        dates = pd.date_range("2020-01-31", "2022-08-31", freq="ME")
        prices = pd.DataFrame(
            {
                "AAA": np.linspace(10, 20, len(dates)),
                "BBB": np.linspace(20, 25, len(dates)),
            },
            index=dates,
        )
        fundamentals = pd.DataFrame(
            [
                # O primeiro registro de cada empresa fornece o ativo anterior.
                ("AAA", "2019-12-31", "2020-03-31", 100, 20, 50, 10),
                ("AAA", "2020-12-31", "2021-03-31", 90, 25, 48, 12),
                # Este balanço seria excelente, mas ainda não existia em junho/2022.
                ("AAA", "2021-12-31", "2022-09-01", 10, 100, 40, 30),
                ("BBB", "2019-12-31", "2020-03-31", 120, 30, 60, 10),
                ("BBB", "2020-12-31", "2021-03-31", 110, 35, 58, 11),
                ("BBB", "2021-12-31", "2022-03-31", 105, 40, 56, 12),
            ],
            columns=[
                "ticker",
                "fiscal_date",
                "available_date",
                "market_cap",
                "book_equity",
                "total_assets",
                "gross_profit",
            ],
        )
        result = build_sleeve1(
            prices,
            fundamentals,
            Sleeve1Config(top_n=1, rebalance_month=6, max_statement_age_months=None),
        )
        june_2022 = result.signals.loc[result.signals["signal_date"].eq("2022-06-30")]
        aaa = june_2022.loc[june_2022["ticker"].eq("AAA")].iloc[0]
        self.assertEqual(pd.Timestamp(aaa["fiscal_date"]), pd.Timestamp("2020-12-31"))
        self.assertTrue((june_2022["available_date"] <= june_2022["signal_date"]).all())
        # O alvo de junho só pode valer a partir do mês terminado em julho.
        self.assertAlmostEqual(float(result.weights.loc["2022-07-31"].sum()), 1.0)

    def test_weights_drift_with_prices_until_next_annual_rebalance(self) -> None:
        dates = pd.date_range("2021-06-30", periods=4, freq="ME")
        prices = pd.DataFrame(
            {
                "AAA": [100.0, 200.0, 300.0, 300.0],
                "BBB": [100.0, 100.0, 100.0, 100.0],
            },
            index=dates,
        )
        targets = {
            dates[0]: pd.Series({"AAA": 0.5, "BBB": 0.5}),
        }
        weights = targets_to_buy_and_hold_weights(prices, targets)
        self.assertAlmostEqual(float(weights.loc[dates[1], "AAA"]), 0.5)
        self.assertAlmostEqual(float(weights.loc[dates[2], "AAA"]), 2.0 / 3.0)
        self.assertAlmostEqual(float(weights.loc[dates[2], "BBB"]), 1.0 / 3.0)
        self.assertAlmostEqual(float(weights.loc[dates[2]].sum()), 1.0)


class Sleeve2Tests(unittest.TestCase):
    def test_hysteresis_has_memory(self) -> None:
        index = pd.date_range("2020-01-31", periods=5, freq="ME")
        zscore = pd.Series([0.0, 1.1, 0.8, 0.5, 0.4], index=index)
        expected = pd.Series(
            ["normal", "stress", "stress", "stress", "normal"],
            index=index,
            name="regime_signal",
            dtype="string",
        )
        assert_series_equal(apply_hysteresis(zscore), expected)

    def test_momentum_is_executed_next_month_and_stress_uses_bil(self) -> None:
        dates = pd.date_range("2020-01-31", periods=18, freq="ME")
        prices = pd.DataFrame(
            {
                "A": 100 * 1.03 ** np.arange(len(dates)),
                "B": 100 * 1.02 ** np.arange(len(dates)),
                "C": 100 * 1.01 ** np.arange(len(dates)),
                "D": 100 * 0.99 ** np.arange(len(dates)),
            },
            index=dates,
        )
        spread = pd.Series(
            [1.0] * 13 + [10.0] * 5,
            index=dates,
            name="spread",
        )
        bil = pd.Series(100 * 1.001 ** np.arange(len(dates)), index=dates, name="BIL")
        result = build_sleeve2(
            prices,
            spread,
            bil_prices=bil,
            config=Sleeve2Config(
                selection_fraction=0.25,
                spread_window_months=2,
                stress_entry_z=0.5,
                stress_exit_z=0.0,
            ),
        )
        first_signal = pd.Timestamp(result.signals["signal_date"].min())
        first_position = result.risky_weights.sum(axis=1).gt(0).idxmax()
        expected_position = dates[dates.get_loc(first_signal) + 1]
        self.assertEqual(first_position, expected_position)
        stress_dates = result.regime.index[result.regime["regime_effective"].eq("stress")]
        self.assertGreater(len(stress_dates), 0)
        self.assertTrue(result.weights_with_regime.loc[stress_dates, "BIL"].eq(1.0).all())
        self.assertTrue(result.weights_with_regime.loc[stress_dates, prices.columns].eq(0.0).all().all())


class Sleeve3AndFundTests(unittest.TestCase):
    def test_bil_adjusted_return(self) -> None:
        dates = pd.date_range("2022-01-31", periods=3, freq="ME")
        result = build_sleeve3(pd.Series([100.0, 101.0, 102.01], index=dates))
        self.assertAlmostEqual(float(result.returns.iloc[1]), 0.01)
        self.assertTrue(result.weights["BIL"].eq(1.0).all())

    def test_fund_migration_preserves_full_investment(self) -> None:
        dates = pd.date_range("2022-01-31", periods=2, freq="ME")
        regime = pd.Series(["normal", "stress"], index=dates)
        allocations = build_fund_allocations(regime, FundConfig())
        sleeve1 = pd.DataFrame({"VALUE": [1.0, 1.0]}, index=dates)
        sleeve2 = pd.DataFrame({"SMALL": [1.0, 1.0]}, index=dates)
        combined = combine_security_weights(sleeve1, sleeve2, allocations)
        self.assertTrue(validate_fully_invested(combined).all())
        self.assertAlmostEqual(float(combined.loc[dates[0], "SMALL"]), 1 / 3)
        self.assertAlmostEqual(float(combined.loc[dates[1], "SMALL"]), 0.0)
        self.assertAlmostEqual(float(combined.loc[dates[1], "BIL"]), 2 / 3)


class PipelineTests(unittest.TestCase):
    def test_end_to_end_produces_fully_invested_monthly_portfolios(self) -> None:
        dates = pd.date_range("2017-01-31", periods=72, freq="ME")
        factor_tickers = [f"F{i}" for i in range(6)]
        small_tickers = [f"S{i}" for i in range(10)]
        factor_prices = pd.DataFrame(
            {
                ticker: 50 * (1 + 0.005 + position * 0.0005) ** np.arange(len(dates))
                for position, ticker in enumerate(factor_tickers)
            },
            index=dates,
        )
        small_prices = pd.DataFrame(
            {
                ticker: 20
                * np.exp(
                    np.cumsum(
                        0.004
                        + position * 0.0002
                        + 0.015 * np.sin(np.arange(len(dates)) / (position + 2))
                    )
                )
                for position, ticker in enumerate(small_tickers)
            },
            index=dates,
        )
        rows = []
        for ticker_position, ticker in enumerate(factor_tickers):
            for year in range(2016, 2022):
                rows.append(
                    (
                        ticker,
                        f"{year}-12-31",
                        100 + ticker_position * 20 + year - 2016,
                        40 + ticker_position * 3,
                        80 + ticker_position * 5 + (year - 2016) * 2,
                        15 + ticker_position,
                    )
                )
        fundamentals = pd.DataFrame(
            rows,
            columns=[
                "ticker",
                "fiscal_date",
                "market_cap",
                "book_equity",
                "total_assets",
                "gross_profit",
            ],
        )
        spread = pd.Series(
            4.0 + 0.2 * np.sin(np.arange(len(dates)) / 5), index=dates, name="spread"
        )
        bil = pd.Series(100 * 1.002 ** np.arange(len(dates)), index=dates, name="BIL")
        result = run_pipeline(
            factor_prices,
            fundamentals,
            small_prices,
            spread,
            bil,
            sleeve1_config=Sleeve1Config(top_n=2, rebalance_month=6),
            sleeve2_config=Sleeve2Config(
                selection_fraction=0.2,
                spread_window_months=12,
            ),
        )
        self.assertGreater(len(result.fund_security_weights), 0)
        self.assertTrue(validate_fully_invested(result.fund_security_weights).all())
        self.assertTrue(result.fund_allocations.sum(axis=1).sub(1.0).abs().lt(1e-12).all())


if __name__ == "__main__":
    unittest.main()
