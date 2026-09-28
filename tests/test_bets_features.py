"""Testes de causalidade e qualidade das entradas do preparador de bets."""

import unittest

import numpy as np
import pandas as pd

from scripts.build_bets_features import build_features


def observations(count=70):
    """Cria dados sintéticos exclusivamente para os testes."""
    weeks = pd.date_range("2023-01-01", periods=count, freq="W-SUN")
    return pd.DataFrame({
        "week_end": weeks.strftime("%Y-%m-%d"),
        "available_at": [(week + pd.Timedelta(days=2)).tz_localize("America/Sao_Paulo").isoformat() for week in weeks],
        "interest": 30 + 8 * np.sin(np.arange(count) * 0.6),
        "vintage_id": [f"synthetic-test-{index}" for index in range(count)],
    })


def regulation():
    return pd.DataFrame({
        "available_at": ["2023-01-02T12:00:00-03:00", "2023-10-01T12:00:00-03:00"],
        "regulation_score": [0.0, 0.5],
        "source": ["synthetic-test-source", "synthetic-test-source"],
    })


class BetsFeatureTests(unittest.TestCase):
    def test_future_mutation_does_not_change_past(self):
        trends, snapshots = observations(), regulation()
        original = build_features(trends, snapshots)
        future = trends.copy()
        future.loc[50:, "interest"] = 99
        updated = snapshots.copy()
        updated.loc[1, "regulation_score"] = -1
        changed = build_features(future, updated)
        cutoff = pd.Timestamp("2023-09-01T00:00:00Z")
        pd.testing.assert_frame_equal(original[original.available_at < cutoff], changed[changed.available_at < cutoff])

    def test_z_uses_previous_deltas_and_full_warmup(self):
        trends = observations()
        output = build_features(trends, regulation()).set_index("available_at")
        delta = np.log1p(trends.interest).diff()
        for index in (27, 60):
            previous = delta.iloc[max(0, index - 52):index].dropna()
            expected = -(delta.iloc[index] - previous.mean()) / previous.std(ddof=1)
            instant = pd.Timestamp(trends.loc[index, "available_at"]).tz_convert("UTC")
            self.assertAlmostEqual(output.loc[instant, "search_relief_z"], expected)
        warmup = pd.Timestamp(trends.loc[26, "available_at"]).tz_convert("UTC")
        self.assertTrue(output.loc[:warmup, "search_relief_z"].isna().all())

    def test_asof_waits_for_actual_publication(self):
        trends = observations(35)
        snapshots = pd.DataFrame({"available_at": ["2023-08-22T12:00:00-03:00"], "regulation_score": [0.6], "source": ["synthetic-test"]})
        output = build_features(trends, snapshots)
        instant = pd.Timestamp(snapshots.loc[0, "available_at"]).tz_convert("UTC")
        self.assertTrue(output.loc[output.available_at < instant, "regulation_score"].isna().all())
        self.assertEqual(output.loc[output.available_at == instant, "regulation_score"].iloc[0], 0.6)
        self.assertEqual(str(output.available_at.dt.tz), "UTC")
        self.assertEqual(instant.hour, 15)

    def test_historical_extraction_today_is_visible_only_today(self):
        trends = observations()
        trends["available_at"] = "2026-09-28T12:00:00-03:00"
        empty = pd.DataFrame(columns=["available_at", "regulation_score", "source"])
        output = build_features(trends, empty)
        self.assertEqual(len(output), 1)
        self.assertEqual(output.vintage_id.iloc[0], "synthetic-test-69")
        self.assertEqual(output.available_at.iloc[0], pd.Timestamp("2026-09-28T15:00:00Z"))

    def test_revisions_naive_times_and_early_publication_are_rejected(self):
        cases = []
        duplicate = pd.concat([observations(), observations().iloc[[0]]])
        cases.append(duplicate)
        naive = observations()
        naive.loc[0, "available_at"] = "2023-01-03"
        cases.append(naive)
        early = observations()
        early.loc[0, "available_at"] = "2023-01-01T23:00:00-03:00"
        cases.append(early)
        for invalid in cases:
            with self.subTest(invalid=invalid.iloc[0].to_dict()), self.assertRaises(ValueError):
                build_features(invalid, regulation())

    def test_missing_week_and_out_of_order_publication_are_rejected(self):
        with self.assertRaises(ValueError):
            build_features(observations().drop(index=4), regulation())
        unordered = observations()
        unordered.loc[0, "available_at"] = "2026-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            build_features(unordered, regulation())

    def test_constant_searches_do_not_create_infinite_signal(self):
        trends = observations()
        trends.interest = 50.0
        self.assertTrue(build_features(trends, regulation()).search_relief_z.isna().all())


if __name__ == "__main__":
    unittest.main()
