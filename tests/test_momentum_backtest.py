from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


from backtest.engine import ExecutionConfig, run_backtest
from backtest.grid_search import GridSearchConfig, GridSearchRunner, parquet_supported
from backtest.statistics import deflated_sharpe_probability, expected_maximum_sharpe
from backtest.stress import StressScenario, run_stress_matrix
from backtest.universe import load_universe_manifest
from backtest.validation import chronological_split, purged_walk_forward_splits
from strategies.momentum_atr import MomentumATRConfig, average_true_range, build_momentum_atr_signals


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def execution_fixture() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=8, freq="B")
    return pd.DataFrame(
        {
            "open": [100, 99, 98, 100, 110, 104, 102, 99],
            "high": [101, 100, 99, 102, 111, 105, 103, 100],
            "low": [99, 98, 97, 99, 103, 102, 99, 98],
            "close": [100, 99, 98, 101, 104, 103, 100, 99],
        },
        index=dates,
    )


def stop_fixture(last_open: float, last_low: float, last_close: float) -> pd.DataFrame:
    dates = pd.date_range("2024-02-01", periods=6, freq="B")
    return pd.DataFrame(
        {
            "open": [100, 99, 98, 100, 102, last_open],
            "high": [101, 100, 99, 102, 103, max(last_open, last_close) + 1],
            "low": [99, 98, 97, 99, 101, last_low],
            "close": [100, 99, 98, 101, 102, last_close],
        },
        index=dates,
    )


class MomentumSignalTests(unittest.TestCase):
    def test_atr_uses_complete_simple_window(self) -> None:
        data = execution_fixture()
        atr = average_true_range(data, window=2)
        self.assertTrue(np.isnan(atr.iloc[0]))
        self.assertAlmostEqual(float(atr.iloc[1]), 2.0)
        self.assertAlmostEqual(float(atr.iloc[3]), 3.0)

    def test_future_mutation_does_not_change_past_signals(self) -> None:
        data = execution_fixture()
        config = MomentumATRConfig(momentum_window=2, atr_window=2, stop_multiplier=2)
        original = build_momentum_atr_signals(data, config)
        changed = data.copy()
        changed.loc[changed.index[-1], ["open", "high", "low", "close"]] = [300, 310, 290, 305]
        mutated = build_momentum_atr_signals(changed, config)
        pd.testing.assert_frame_equal(original.iloc[:-1], mutated.iloc[:-1])


class ExecutionTests(unittest.TestCase):
    def test_momentum_orders_fill_at_next_open_and_account_for_both_costs(self) -> None:
        data = execution_fixture()
        strategy = MomentumATRConfig(momentum_window=2, atr_window=2, stop_multiplier=100)
        execution = ExecutionConfig(cost_per_side=0.0015)
        result = run_backtest(data, strategy, execution)

        self.assertEqual(result.orders["side"].tolist(), ["BUY", "SELL"])
        self.assertEqual(result.orders.iloc[0]["signal_time"], data.index[3])
        self.assertEqual(result.orders.iloc[0]["fill_time"], data.index[4])
        self.assertEqual(float(result.orders.iloc[0]["fill_price"]), 110.0)
        self.assertEqual(result.orders.iloc[1]["signal_time"], data.index[6])
        self.assertEqual(result.orders.iloc[1]["fill_time"], data.index[7])
        self.assertEqual(float(result.orders.iloc[1]["fill_price"]), 99.0)

        expected = (99.0 * (1.0 - 0.0015)) / (110.0 * (1.0 + 0.0015))
        self.assertAlmostEqual(float(result.metrics["final_equity"]), expected, places=12)
        self.assertAlmostEqual(float(result.trades.iloc[0]["net_return"]), expected - 1.0, places=12)
        compounded = float((1.0 + result.equity_curve["daily_return"]).prod())
        self.assertAlmostEqual(compounded, float(result.metrics["final_equity"]), places=12)

    def test_gap_through_stop_fills_at_open_not_at_magic_stop_price(self) -> None:
        data = stop_fixture(last_open=95, last_low=94, last_close=96)
        strategy = MomentumATRConfig(momentum_window=2, atr_window=2, stop_multiplier=1)
        result = run_backtest(data, strategy, ExecutionConfig(stop_slippage=0.002))

        sell = result.orders.loc[result.orders["side"].eq("SELL")].iloc[0]
        self.assertEqual(sell["reason"], "gap_stop")
        self.assertAlmostEqual(float(sell["stop_price"]), 99.0)
        self.assertAlmostEqual(float(sell["fill_price"]), 95.0 * (1.0 - 0.002))

    def test_intraday_low_triggers_carried_stop(self) -> None:
        data = stop_fixture(last_open=101, last_low=98, last_close=101)
        strategy = MomentumATRConfig(momentum_window=2, atr_window=2, stop_multiplier=1)
        result = run_backtest(data, strategy, ExecutionConfig())

        sell = result.orders.loc[result.orders["side"].eq("SELL")].iloc[0]
        self.assertEqual(sell["reason"], "intraday_stop")
        self.assertAlmostEqual(float(sell["fill_price"]), 99.0)

    def test_default_cost_is_fifteen_basis_points_per_side(self) -> None:
        self.assertEqual(ExecutionConfig().cost_per_side, 0.0015)


class TemporalValidationTests(unittest.TestCase):
    def test_chronological_split_is_exactly_floor_70_30(self) -> None:
        data = pd.concat([execution_fixture()] * 3).iloc[:20].copy()
        data.index = pd.date_range("2024-01-02", periods=20, freq="B")
        split = chronological_split(data)
        self.assertEqual(len(split.train), 14)
        self.assertEqual(len(split.test), 6)
        self.assertLess(split.train.index[-1], split.test.index[0])

    def test_walk_forward_has_purge_and_embargo_gaps(self) -> None:
        folds = purged_walk_forward_splits(
            50,
            train_size=20,
            test_size=5,
            purge=2,
            embargo=3,
        )
        self.assertGreaterEqual(len(folds), 2)
        first = folds[0]
        self.assertEqual(first.train_indices[-1], 19)
        np.testing.assert_array_equal(first.purge_indices, [20, 21])
        np.testing.assert_array_equal(first.test_indices, [22, 23, 24, 25, 26])
        np.testing.assert_array_equal(first.embargo_indices, [27, 28, 29])
        self.assertEqual(folds[1].test_indices[0], 30)
        for fold in folds:
            self.assertTrue(set(fold.train_indices).isdisjoint(fold.test_indices))
            self.assertTrue(set(fold.purge_indices).isdisjoint(fold.test_indices))


class UniverseAndStatisticsTests(unittest.TestCase):
    def test_local_manifest_includes_adverse_and_historical_members(self) -> None:
        manifest = load_universe_manifest(PROJECT_ROOT / "config" / "momentum_universe.json")
        self.assertIn("AMER3.SA", [asset.ticker for asset in manifest.members("adverse_distressed")])
        historical = manifest.members("historical_delisted_or_renamed")
        self.assertTrue(all(asset.valid_to for asset in historical))

    def test_deflated_sharpe_is_a_probability(self) -> None:
        benchmark = expected_maximum_sharpe(0.25, 55)
        probability = deflated_sharpe_probability(
            1.2,
            benchmark,
            n_observations=504,
            skewness=-0.2,
            kurtosis=4.0,
        )
        self.assertGreaterEqual(probability, 0.0)
        self.assertLessEqual(probability, 1.0)

    def test_stress_matrix_consumes_generator_for_every_asset(self) -> None:
        data = execution_fixture()
        scenarios = (
            scenario
            for scenario in (
                StressScenario("base", 0.0015),
                StressScenario("severe", 0.0050, 0.0030),
            )
        )
        result = run_stress_matrix(
            {"AAA": data, "BBB": data},
            {"mixed": ("AAA", "BBB")},
            strategy_config=MomentumATRConfig(2, 2, 100),
            scenarios=scenarios,
        )
        self.assertEqual(len(result), 4)
        self.assertEqual(set(result["scenario"]), {"base", "severe"})


@unittest.skipUnless(parquet_supported(), "pyarrow/fastparquet não instalado")
class GridCheckpointTests(unittest.TestCase):
    def test_checkpoint_is_parquet_atomic_and_resumable(self) -> None:
        data = execution_fixture()
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.parquet"
            config = GridSearchConfig(
                momentum_windows=(2,),
                atr_windows=(2,),
                stop_multipliers=(1.0, 100.0),
                workers=1,
                batch_size=1,
                checkpoint_path=checkpoint,
            )
            first = GridSearchRunner(config).run({"TEST3.SA": data})
            second = GridSearchRunner(config).run({"TEST3.SA": data})
            self.assertEqual(len(first), 2)
            pd.testing.assert_frame_equal(first, second)
            self.assertTrue(checkpoint.exists())
            self.assertFalse(list(checkpoint.parent.glob("*.tmp.parquet")))

    def test_process_pool_produces_complete_deterministic_grid(self) -> None:
        data = execution_fixture()
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "parallel.parquet"
            config = GridSearchConfig(
                momentum_windows=(2, 3),
                atr_windows=(2,),
                stop_multipliers=(1.0, 100.0),
                workers=2,
                batch_size=2,
                checkpoint_path=checkpoint,
            )
            result = GridSearchRunner(config).run({"TEST3.SA": data})
            self.assertEqual(len(result), 4)
            self.assertEqual(result["task_id"].nunique(), 4)
            self.assertTrue(result["deflated_sharpe_ratio"].between(0, 1).all())


if __name__ == "__main__":
    unittest.main()
