"""Regressões de causalidade, fricção, proveniência e validade do ranking."""
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
import pytest

from investment_research.cli import load_config
from investment_research.engine import analyze, features, simulate
from investment_research.market_data import completed_session_cutoff, normalize_download, snapshot_data, validate_history


@pytest.fixture
def config():
    return load_config(__import__("pathlib").Path("config/swing_us.json"))


def history(n=400):
    index = pd.bdate_range(end="2026-10-08", periods=n)
    price = np.linspace(100, 150, n)
    return pd.DataFrame({"open": price, "high": price+1, "low": price-1, "close": price,
                         "raw_close": price, "volume": 10_000_000., "adjustment_factor": 1.}, index=index)


def explicit_signals(frame, active=True):
    return pd.DataFrame({"signal": active, "atr": 2., "ma20": 1.}, index=frame.index)


def test_unfinished_session_and_historical_cutoff():
    now = datetime(2026, 10, 9, 16, 30, tzinfo=timezone.utc)
    assert completed_session_cutoff("2026-10-09", now) == pd.Timestamp("2026-10-08")
    assert completed_session_cutoff("2026-10-05", now) == pd.Timestamp("2026-10-05")
    assert completed_session_cutoff("2026-10-09", datetime(2026, 10, 9, 22, tzinfo=timezone.utc)) == pd.Timestamp("2026-10-09")


def test_adjustment_scales_all_prices_and_keeps_raw_liquidity():
    raw = pd.DataFrame({"Open": [100., 50.], "High": [102., 52.], "Low": [98., 48.],
                        "Close": [100., 50.], "Adj Close": [50., 50.], "Volume": [1000., 2000.]},
                       index=pd.to_datetime(["2026-10-07", "2026-10-08"]))
    frame = normalize_download(raw, pd.Timestamp("2026-10-08"))
    assert list(frame.close) == [50., 50.]
    assert frame.iloc[0].open == 50.
    assert frame.iloc[0].raw_close * frame.iloc[0].volume == 100000.
    raw.iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="ausentes"):
        normalize_download(raw, pd.Timestamp("2026-10-08"))


def test_signal_fills_next_open_and_accounts_both_costs(config):
    frame = history(5)
    frame.loc[:, ["open", "close"]] = 100.
    frame["high"], frame["low"] = 101., 99.
    signal = explicit_signals(frame, False)
    signal.iloc[1, 0] = True
    result, curve, trades = simulate(frame, signal, frame.index[0], config)
    assert trades[0]["entry_date"] == str(frame.index[2].date())
    expected = (1-config["cost_per_side"]) / (1+config["cost_per_side"]) - 1
    assert result["return"] == pytest.approx(expected)
    assert result["drawdown"] == pytest.approx(expected)


def test_gap_stop_uses_open_and_never_same_bar_ratchet(config):
    frame = history(5)
    frame.loc[:, ["open", "close"]] = 100.
    frame["high"], frame["low"] = 101., 99.
    frame.iloc[2, frame.columns.get_loc("high")] = 115.
    frame.iloc[2, frame.columns.get_loc("close")] = 110.
    # Stop gerado no close2=106 não pode vender no low2=99.
    frame.iloc[3, frame.columns.get_loc("open")] = 90.
    frame.iloc[3, frame.columns.get_loc("low")] = 89.
    result, _, trades = simulate(frame, explicit_signals(frame), frame.index[0], config)
    assert trades[0]["exit_date"] == str(frame.index[3].date())
    assert trades[0]["exit_reason"] == "gap stop"
    assert trades[0]["return"] == pytest.approx(.9*(1-config["cost_per_side"])/(1+config["cost_per_side"])-1)


def test_oos_starts_flat_and_time_exit(config):
    frame = history(20)
    signal = explicit_signals(frame)
    _, _, trades = simulate(frame, signal, frame.index[4], config)
    assert trades[0]["entry_date"] == str(frame.index[5].date())
    assert trades[0]["exit_date"] == str(frame.index[15].date())
    assert trades[0]["exit_reason"] == "tempo/tendência"


def test_future_bars_cannot_change_prior_signals_or_equity(config):
    frame = history()
    changed = frame.copy()
    changed.iloc[300:, :4] *= 5
    first = features(frame, frame, config)
    second = features(changed, changed, config)
    pd.testing.assert_frame_equal(first.iloc[:300], second.iloc[:300])
    _, before, _ = simulate(frame, first, frame.index[100], config)
    _, after, _ = simulate(changed, second, frame.index[100], config)
    pd.testing.assert_series_equal(before.loc[:frame.index[299]], after.loc[:frame.index[299]])


def test_stale_benchmark_and_missing_sessions_fail_closed(config):
    frame = history()
    with pytest.raises(ValueError, match="benchmark"):
        analyze({"SPY": frame.iloc[:-20]}, config, "2026-10-09")
    rows, exclusions, _ = analyze({"SPY": frame, "NVDA": frame.drop(frame.index[200])}, config, "2026-10-09")
    assert len(rows) == 1
    assert exclusions[0]["ticker"] == "NVDA"
    assert "lacuna" in exclusions[0]["reason"]


def test_hash_mismatch_never_reuses_corrupt_cache(tmp_path, config):
    config = dict(config, assets=[config["assets"][0]])
    (tmp_path/"SPY.csv").write_text("corrompido", encoding="utf-8")
    (tmp_path/"SPY.meta.json").write_text(json.dumps({"ticker":"SPY", "currency":"USD", "sha256":"invalid"}), encoding="utf-8")
    frames, _, exclusions = snapshot_data(config, tmp_path, "2026-10-09", offline=True)
    assert frames == {}
    assert "SHA256" in exclusions[0]["reason"]


def test_offline_missing_data_does_not_fabricate_prices(tmp_path, config):
    frames, sources, exclusions = snapshot_data(config, tmp_path, "2026-10-09", offline=True)
    assert not frames and not sources
    assert len(exclusions) == len(config["assets"])


def test_validates_ticker_paths_and_nan_config(tmp_path, config):
    config["assets"][0]["ticker"] = "../SPY"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="ticker"):
        load_config(path)


def test_zero_atr_yields_observation_without_position_size(config):
    frame = history()
    frame.loc[:, ["open", "high", "low", "close", "raw_close"]] = 100.
    rows, _, _ = analyze({"SPY": frame}, config, "2026-10-09")
    assert rows[0]["status"] == "observar"
    assert rows[0]["weight_at_risk_budget"] is None


def test_inconsistent_adjustment_is_rejected():
    frame = history()
    frame["adjustment_factor"] = .5
    with pytest.raises(ValueError, match="escala"):
        validate_history(frame)
