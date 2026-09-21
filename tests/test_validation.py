from __future__ import annotations

import math
import unittest
from statistics import NormalDist

import numpy as np
import pandas as pd

from quant_fund.validation import (
    circular_shift_placebo_test,
    deflated_sharpe_ratio,
    expected_maximum_sharpe_ratio,
    moving_block_bootstrap_mean,
    probabilistic_sharpe_ratio,
)


class ProbabilisticSharpeTests(unittest.TestCase):
    def test_probability_is_half_at_the_benchmark(self) -> None:
        result = probabilistic_sharpe_ratio(
            0.75,
            0.75,
            observations=60,
            skewness=-0.7,
            kurtosis=5.8,
            periods_per_year=12,
        )
        self.assertAlmostEqual(result, 0.5, places=15)

    def test_matches_bailey_lopez_de_prado_formula_for_annual_sharpe(self) -> None:
        annual_sharpe = 1.0
        periodic_sharpe = annual_sharpe / math.sqrt(12)
        skewness = -0.72
        kurtosis = 5.78
        observations = 60
        denominator = math.sqrt(
            1
            - skewness * periodic_sharpe
            + ((kurtosis - 1) / 4) * periodic_sharpe**2
        )
        expected = NormalDist().cdf(periodic_sharpe * math.sqrt(observations - 1) / denominator)
        result = probabilistic_sharpe_ratio(
            annual_sharpe,
            observations=observations,
            skewness=skewness,
            kurtosis=kurtosis,
            periods_per_year=12,
        )
        self.assertAlmostEqual(result, expected, places=15)

    def test_rejects_excess_kurtosis_in_place_of_raw_kurtosis(self) -> None:
        with self.assertRaisesRegex(ValueError, "Pearson"):
            probabilistic_sharpe_ratio(
                1.0,
                observations=60,
                kurtosis=0.0,
                periods_per_year=12,
            )


class DeflatedSharpeTests(unittest.TestCase):
    def test_expected_maximum_uses_extreme_value_approximation(self) -> None:
        mean = 0.10
        std = 0.25
        trials = 100
        gamma = 0.5772156649015329
        normal = NormalDist()
        expected = mean + std * (
            (1 - gamma) * normal.inv_cdf(1 - 1 / trials)
            + gamma * normal.inv_cdf(1 - 1 / (trials * math.e))
        )
        self.assertAlmostEqual(
            expected_maximum_sharpe_ratio(mean, std, trials), expected, places=15
        )

    def test_multiple_testing_lowers_probability(self) -> None:
        psr = probabilistic_sharpe_ratio(
            1.0,
            observations=72,
            periods_per_year=12,
        )
        dsr = deflated_sharpe_ratio(
            1.0,
            observations=72,
            num_trials=50,
            sharpe_std=0.30,
            periods_per_year=12,
        )
        self.assertLess(dsr, psr)

    def test_one_trial_reduces_to_psr_against_the_mean(self) -> None:
        expected = probabilistic_sharpe_ratio(
            0.8,
            0.2,
            observations=48,
            skewness=-0.3,
            kurtosis=4.0,
            periods_per_year=12,
        )
        result = deflated_sharpe_ratio(
            0.8,
            observations=48,
            num_trials=1,
            sharpe_std=99.0,
            mean_sharpe=0.2,
            skewness=-0.3,
            kurtosis=4.0,
            periods_per_year=12,
        )
        self.assertAlmostEqual(result, expected, places=15)


class MovingBlockBootstrapTests(unittest.TestCase):
    def test_full_length_block_has_degenerate_interval(self) -> None:
        returns = np.array([0.01, -0.02, 0.03, 0.04])
        result = moving_block_bootstrap_mean(
            returns,
            block_length=len(returns),
            n_bootstrap=100,
            confidence_level=0.90,
            seed=7,
        )
        expected = float(returns.mean() * 12)
        self.assertAlmostEqual(result.estimate, expected)
        self.assertAlmostEqual(result.ci_lower, expected)
        self.assertAlmostEqual(result.ci_upper, expected)
        self.assertAlmostEqual(result.standard_error, 0.0)

    def test_seed_makes_result_reproducible(self) -> None:
        returns = np.sin(np.arange(36) / 3) / 100
        first = moving_block_bootstrap_mean(
            returns,
            block_length=4,
            n_bootstrap=300,
            seed=123,
        )
        second = moving_block_bootstrap_mean(
            returns,
            block_length=4,
            n_bootstrap=300,
            seed=123,
        )
        self.assertEqual(first, second)
        self.assertLessEqual(first.ci_lower, first.estimate)
        self.assertGreaterEqual(first.ci_upper, first.estimate)

    def test_rejects_missing_values_and_invalid_blocks(self) -> None:
        with self.assertRaisesRegex(ValueError, "finitos"):
            moving_block_bootstrap_mean([0.01, np.nan, 0.02])
        with self.assertRaisesRegex(ValueError, "exceder"):
            moving_block_bootstrap_mean([0.01, 0.02], block_length=3)


class CircularShiftPlaceboTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.period_range("2020-01", periods=12, freq="M")

    def test_crash_timing_ranks_true_signal_above_every_shift(self) -> None:
        risky = pd.Series([0.01] * 5 + [-0.50] + [0.01] * 6, index=self.index)
        cash = pd.Series(0.0, index=self.index)
        derisk = pd.Series([0.0] * 5 + [1.0] + [0.0] * 6, index=self.index)
        result = circular_shift_placebo_test(
            risky,
            cash,
            derisk,
            worst_periods=1,
        )
        self.assertEqual(result.placebo_metrics.shape, (11, 4))
        self.assertTrue(result.percentiles.eq(100.0).all())
        self.assertAlmostEqual(result.true_metrics["max_drawdown"], 0.0)
        self.assertAlmostEqual(result.true_metrics["mean_worst_months"], 0.0)

    def test_no_signal_gets_midrank_for_all_defined_metrics(self) -> None:
        risky = pd.Series(np.linspace(-0.03, 0.04, 12), index=self.index)
        cash = pd.Series(0.001, index=self.index)
        derisk = pd.Series(0.0, index=self.index)
        result = circular_shift_placebo_test(risky, cash, derisk, worst_periods=3)
        self.assertTrue(result.percentiles.eq(50.0).all())

    def test_cost_is_charged_on_each_change_in_level(self) -> None:
        risky = np.zeros(4)
        cash = np.zeros(4)
        derisk = np.array([0.0, 1.0, 0.0, 0.0])
        result = circular_shift_placebo_test(
            risky,
            cash,
            derisk,
            cost_bps=100,
            worst_periods=1,
        )
        expected_cagr = (0.99 * 0.99) ** (12 / 4) - 1
        self.assertAlmostEqual(result.true_metrics["cagr"], expected_cagr)

    def test_rejects_misaligned_series_and_invalid_levels(self) -> None:
        risky = pd.Series(np.zeros(12), index=self.index)
        cash = pd.Series(np.zeros(12), index=self.index.shift(1))
        derisk = pd.Series(np.zeros(12), index=self.index)
        with self.assertRaisesRegex(ValueError, "índices idênticos"):
            circular_shift_placebo_test(risky, cash, derisk)

        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            circular_shift_placebo_test(np.zeros(3), np.zeros(3), [0.0, 1.1, 0.0])


if __name__ == "__main__":
    unittest.main()
