from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from quant_fund.risk_overlay import (
    RiskOverlayConfig,
    build_risk_overlay,
    graded_allocations,
    hysteresis_state,
    insurance_ledger,
    rolling_zscore,
)


def months(n: int, start: str = "2010-01") -> pd.PeriodIndex:
    return pd.period_range(start, periods=n, freq="M")


class ConfigTests(unittest.TestCase):
    def test_rejects_exit_above_entry(self) -> None:
        with self.assertRaises(ValueError):
            RiskOverlayConfig(stress_entry_z=0.5, stress_exit_z=1.0)

    def test_rejects_derisk_outside_unit_interval(self) -> None:
        for value in (0.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                RiskOverlayConfig(max_derisk=value)

    def test_rejects_min_periods_larger_than_window(self) -> None:
        with self.assertRaises(ValueError):
            RiskOverlayConfig(zscore_window_months=12, zscore_min_periods=24)


class ZScoreTests(unittest.TestCase):
    def test_uses_only_past_observations(self) -> None:
        index = months(40)
        series = pd.Series(np.arange(40.0), index=index, name="x")
        result = rolling_zscore(series, window=12, min_periods=12)
        # Nenhum valor antes de completar a janela mínima.
        self.assertTrue(result.iloc[:11].isna().all())
        # O z-score em t não pode mudar quando o futuro muda.
        alterada = series.copy()
        alterada.iloc[30:] = 999.0
        recalculado = rolling_zscore(alterada, window=12, min_periods=12)
        pd.testing.assert_series_equal(result.iloc[:30], recalculado.iloc[:30])

    def test_constant_series_yields_nan_not_infinity(self) -> None:
        series = pd.Series(np.full(30, 2.5), index=months(30), name="x")
        result = rolling_zscore(series, window=12, min_periods=12)
        self.assertTrue(result.iloc[12:].isna().all())


class HysteresisTests(unittest.TestCase):
    def test_enters_above_entry_and_holds_until_exit(self) -> None:
        z = pd.Series([0.0, 1.2, 0.8, 0.6, 0.4, 0.9], index=months(6))
        state = hysteresis_state(z, entry_z=1.0, exit_z=0.5)
        # Acende em t1; segue aceso em 0,8 e 0,6; apaga só em 0,4; 0,9 não reacende.
        self.assertEqual(list(state), [0, 1, 1, 1, 0, 0])

    def test_nan_preserves_previous_state(self) -> None:
        z = pd.Series([0.0, 1.5, np.nan, np.nan, 0.2], index=months(5))
        self.assertEqual(list(hysteresis_state(z, 1.0, 0.5)), [0, 1, 1, 1, 0])

    def test_rejects_invalid_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            hysteresis_state(pd.Series([0.0]), entry_z=0.5, exit_z=0.5)


class OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = months(60)
        rng = np.random.default_rng(7)
        self.axes = {
            "a": pd.Series(rng.normal(size=60), index=self.index),
            "b": pd.Series(rng.normal(size=60), index=self.index),
        }
        self.config = RiskOverlayConfig(
            zscore_window_months=12, zscore_min_periods=12, max_derisk=0.5
        )

    def test_signal_is_lagged_by_exactly_one_month(self) -> None:
        overlay = build_risk_overlay(self.axes, self.index, self.config)
        expected = overlay["derisk_sinal"].shift(1).fillna(0.0)
        pd.testing.assert_series_equal(
            overlay["derisk_aplicado"], expected, check_names=False
        )

    def test_derisk_levels_are_discrete_and_bounded(self) -> None:
        overlay = build_risk_overlay(self.axes, self.index, self.config)
        levels = set(np.round(overlay["derisk_sinal"].unique(), 10))
        self.assertTrue(levels.issubset({0.0, 0.25, 0.5}))
        self.assertLessEqual(overlay["derisk_sinal"].max(), self.config.max_derisk)

    def test_single_axis_reproduces_binary_behaviour(self) -> None:
        config = RiskOverlayConfig(
            zscore_window_months=12, zscore_min_periods=12, max_derisk=1.0
        )
        overlay = build_risk_overlay({"a": self.axes["a"]}, self.index, config)
        self.assertTrue(overlay["derisk_sinal"].isin([0.0, 1.0]).all())

    def test_requires_at_least_one_axis(self) -> None:
        with self.assertRaises(ValueError):
            build_risk_overlay({}, self.index, self.config)


class AllocationTests(unittest.TestCase):
    def test_weights_sum_to_one_and_stay_non_negative(self) -> None:
        level = pd.Series([0.0, 0.25, 0.5, 1.0], index=months(4))
        allocations = graded_allocations(level)
        self.assertTrue(np.allclose(allocations.sum(axis=1), 1.0))
        self.assertTrue((allocations >= 0).all().all())

    def test_factor_sleeve_never_reacts_to_the_trigger(self) -> None:
        level = pd.Series([0.0, 0.5, 1.0], index=months(3))
        allocations = graded_allocations(level)
        self.assertTrue(np.allclose(allocations["factor"], 1 / 3))

    def test_full_derisk_empties_the_tactical_sleeve(self) -> None:
        allocations = graded_allocations(pd.Series([1.0], index=months(1)))
        self.assertAlmostEqual(float(allocations["small_caps"].iloc[0]), 0.0)
        self.assertAlmostEqual(float(allocations["fixed_income"].iloc[0]), 2 / 3)

    def test_migration_is_exactly_proportional(self) -> None:
        allocations = graded_allocations(pd.Series([0.5], index=months(1)))
        self.assertAlmostEqual(float(allocations["small_caps"].iloc[0]), 1 / 6)
        self.assertAlmostEqual(float(allocations["fixed_income"].iloc[0]), 1 / 2)

    def test_rejects_weights_that_do_not_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            graded_allocations(pd.Series([0.0], index=months(1)), (0.5, 0.5, 0.5))


class InsuranceLedgerTests(unittest.TestCase):
    def test_premium_is_zero_when_overlay_never_fires(self) -> None:
        index = months(12)
        risky = pd.Series(np.linspace(0.01, 0.03, 12), index=index)
        cash = pd.Series(np.full(12, 0.002), index=index)
        ledger = insurance_ledger(risky, cash, pd.Series(0.0, index=index))
        self.assertAlmostEqual(ledger["premio_anual"], 0.0)
        self.assertEqual(ledger["meses_ativos"], 0)
        self.assertAlmostEqual(ledger["giro_anual"], 0.0)

    def test_full_hedge_in_a_crash_lifts_the_tail(self) -> None:
        index = months(6)
        risky = pd.Series([0.01, 0.01, -0.20, 0.01, 0.01, 0.01], index=index)
        cash = pd.Series(np.full(6, 0.001), index=index)
        derisk = pd.Series([0.0, 0.0, 1.0, 0.0, 0.0, 0.0], index=index)
        ledger = insurance_ledger(risky, cash, derisk, tail_months=1)
        self.assertAlmostEqual(ledger["cauda_sem_overlay"], -0.20)
        self.assertAlmostEqual(ledger["cauda_com_overlay"], 0.001)
        self.assertGreater(ledger["premio_anual"], 0.0)  # protegeu: prêmio positivo aqui
        self.assertEqual(ledger["meses_ativos"], 1)


if __name__ == "__main__":
    unittest.main()
