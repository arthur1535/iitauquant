"""Fixtures sintéticas explícitas; nenhum teste consulta dados de mercado."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from automation.research import ResearchConfig, run_research
from backtest.engine import ExecutionConfig, run_backtest
from strategies.momentum_atr import MomentumATRConfig


def _fixture_manifest(tmp_path: Path, *, missing: bool = False, bars: int = 180) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True)
    data_dir.mkdir()
    dates = pd.date_range("2020-01-02", periods=bars, freq="B")
    positions = np.arange(bars, dtype=float)
    for ticker, trend in (("AAA", 0.015), ("ZZZ", -0.018)):
        if missing and ticker == "ZZZ":
            continue
        close = 100 + trend * positions + 8 * np.sin(positions / 6)
        opening = close + 0.3 * np.cos(positions / 3)
        pd.DataFrame({
            "date": dates,
            "open": opening,
            "high": np.maximum(opening, close) + 0.8,
            "low": np.minimum(opening, close) - 0.8,
            "close": close,
        }).to_csv(data_dir / f"{ticker}.csv", index=False)
    manifest = config_dir / "universe.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "as_of": "2024-01-01",
        "data_policy": {"source": "synthetic_fixture", "adjustment": "none (synthetic)", "network_download": False},
        "universes": {"survivor_baseline": ["AAA"], "adverse_distressed": ["ZZZ"]},
        "assets": {
            "AAA": {"local_file": "../data/AAA.csv", "status": "baseline"},
            "ZZZ": {"local_file": "../data/ZZZ.csv", "status": "adverse"},
        },
    }), encoding="utf-8")
    return manifest


def test_missing_adverse_member_blocks_even_with_asset_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _fixture_manifest(tmp_path, missing=True)

    def forbidden_grid(*args: object, **kwargs: object) -> None:
        pytest.fail("grid não deve executar com universo incompleto")

    monkeypatch.setattr("automation.research.GridSearchRunner.run", forbidden_grid)
    report = run_research(manifest, tmp_path / "reports", max_assets=1)
    assert report["status"] == "blocked"
    assert report["grid_tasks"] == 0
    assert report["coverage"]["required_count"] == 2
    assert report["coverage"]["issues"][0]["ticker"] == "ZZZ"
    assert report["coverage"]["issues"][0]["status"] == "missing"
    assert not list((tmp_path / "reports").glob("*.parquet"))
    assert json.loads(Path(report["artifacts"]["summary"]).read_text(encoding="utf-8")) == report


@pytest.mark.parametrize("problem", ["short", "invalid"])
def test_data_quality_fails_closed(tmp_path: Path, problem: str) -> None:
    manifest = _fixture_manifest(tmp_path, bars=20 if problem == "short" else 180)
    if problem == "invalid":
        data_path = tmp_path / "data" / "ZZZ.csv"
        frame = pd.read_csv(data_path)
        frame.loc[10, "close"] = np.nan
        frame.to_csv(data_path, index=False)
    report = run_research(manifest, tmp_path / "reports")
    assert report["status"] == "blocked"
    assert report["config"]["minimum_bars"] == ResearchConfig().minimum_bars
    assert report["coverage"]["issues"][0]["status"] == ("insufficient_bars" if problem == "short" else "invalid")


def test_complete_research_preserves_all_statuses_and_causal_warmup(tmp_path: Path) -> None:
    manifest = _fixture_manifest(tmp_path)
    report = run_research(manifest, tmp_path / "reports")
    assert report["status"] == "completed"
    assert report["data_kind"] == "synthetic_fixture"
    assert report["promotion_allowed"] is False
    assert report["network_access"] is False
    assert report["coverage"]["selected_tickers"] == ["AAA", "ZZZ"]
    assert report["coverage"]["full_universe_researched"] is True
    assert report["grid_tasks"] == 12
    assert report["config"]["cost_per_side"] == 0.0015
    assert report["config"]["optuna_enabled"] is False
    json.dumps(report, allow_nan=False)
    for path in report["artifacts"].values():
        assert Path(path).exists()
    wfa = pd.read_csv(report["artifacts"]["walk_forward"])
    assert wfa["scope"].eq("in_sample_only").all()
    for row in report["holdout"]:
        ticker = row["ticker"]
        data = pd.read_csv(tmp_path / "data" / f"{ticker}.csv", parse_dates=["date"]).set_index("date")
        strategy = MomentumATRConfig(row["momentum_window"], row["atr_window"], row["stop_multiplier"])
        expected = run_backtest(data, strategy, ExecutionConfig(), trade_start=row["oos_start"])
        assert row["oos_total_return"] == pytest.approx(expected.metrics["total_return"])
        assert pd.to_datetime(wfa.loc[wfa["ticker"].eq(ticker), "test_end"]).max() < pd.Timestamp(row["oos_start"])
    repeated = run_research(manifest, tmp_path / "reports")
    assert repeated["run_id"] == report["run_id"]
    assert repeated["holdout"] == report["holdout"]
    assert repeated["artifact_sha256"] == report["artifact_sha256"]


def test_oos_mutation_cannot_change_is_selection_or_wfa(tmp_path: Path) -> None:
    manifest = _fixture_manifest(tmp_path)
    before = run_research(manifest, tmp_path / "before", max_assets=1)
    path = tmp_path / "data" / "AAA.csv"
    frame = pd.read_csv(path)
    split = int(len(frame) * 0.70)
    # Só o futuro cego muda. Multiplicar os quatro preços preserva OHLC válido.
    frame.loc[split:, ["open", "high", "low", "close"]] *= np.linspace(1.3, 0.4, len(frame) - split)[:, None]
    frame.to_csv(path, index=False)
    after = run_research(manifest, tmp_path / "after", max_assets=1)
    for field in ("momentum_window", "atr_window", "stop_multiplier", "is_sharpe", "is_dsr"):
        assert before["holdout"][0][field] == after["holdout"][0][field]
    pd.testing.assert_frame_equal(
        pd.read_csv(before["artifacts"]["walk_forward"]),
        pd.read_csv(after["artifacts"]["walk_forward"]),
    )
    assert before["run_id"] != after["run_id"]
    assert after["coverage"]["full_universe_researched"] is False


@pytest.mark.parametrize("kwargs", [{"workers": 0}, {"workers": 5}, {"workers": True}, {"max_assets": 0}])
def test_invalid_resource_arguments_rejected(tmp_path: Path, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        run_research(tmp_path / "absent.json", tmp_path / "reports", **kwargs)
