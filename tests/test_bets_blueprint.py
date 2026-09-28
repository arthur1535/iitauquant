"""Verificacao do blueprint; dados artificiais nao testam a tese economica."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from scripts.backtest_bets import Config, align_features, demo_inputs, prepare, run_backtest, targets


@pytest.fixture(scope="module")
def sample():
    return demo_inputs()


@pytest.fixture(scope="module")
def result(sample):
    return run_backtest(*sample, exploratory=True)


def test_features_after_cutoff_wait_for_next_snapshot():
    dates = pd.to_datetime(["2025-01-06", "2025-01-07"])
    features = pd.DataFrame({"available_at":["2025-01-06T18:01:00-03:00"],
                            "search_relief_z":[1],"regulation_score":[1],"vintage_id":["x"]})
    aligned = align_features(dates,features,exploratory=True)
    assert pd.isna(aligned.search_relief_z.iloc[0])
    assert aligned.search_relief_z.iloc[1] == 1
    with pytest.raises(ValueError,match="exploratory"):
        align_features(dates,features)
    features["available_at"] = "2025-01-06T18:01:00"
    with pytest.raises(ValueError,match="timezone"):
        align_features(dates,features,True)


def test_future_prices_and_features_cannot_change_history(sample,result):
    prices,benchmark,features = [x.copy() for x in sample]
    boundary = benchmark.date.iloc[400]
    mask = prices.date > boundary
    for col in ["open","high","low","close","raw_close"]:
        prices.loc[mask,col] *= 2
    cutoff = (boundary+pd.Timedelta(hours=18)).tz_localize("America/Sao_Paulo").tz_convert("UTC")
    features.loc[pd.to_datetime(features.available_at,utc=True) > cutoff,"search_relief_z"] = -8
    changed = run_backtest(prices,benchmark,features,exploratory=True)
    pd.testing.assert_frame_equal(changed["curve"].loc[:boundary],result["curve"].loc[:boundary])
    old = result["orders"].loc[result["orders"].date.le(boundary)].reset_index(drop=True)
    new = changed["orders"].loc[changed["orders"].date.le(boundary)].reset_index(drop=True)
    pd.testing.assert_frame_equal(old,new)


def test_actual_orders_next_session_shared_cash_costs(sample,result):
    ledger = result["orders"]
    assert len(ledger) > 20
    assert (ledger.date > ledger.signal_date).all()
    assert result["curve"].cash.min() >= -1e-7
    np.testing.assert_allclose(ledger.fee,ledger.amount.abs()*ledger.price*Config().cost)
    assert result["curve"].costs.sum() == pytest.approx(ledger.fee.sum())
    dates = pd.DatetimeIndex(sample[1].date)
    for row in ledger.itertuples():
        assert dates.get_loc(row.date) == dates.get_loc(row.signal_date)+1


def test_gate_false_is_cdi_cash_only(sample):
    p,b,f = [x.copy() for x in sample]
    f["regulation_score"] = -1
    result = run_backtest(p,b,f,exploratory=True)
    assert result["orders"].empty
    rf = b.cdi_return.copy()
    rf.iloc[0] = 0
    np.testing.assert_allclose(result["curve"].nav,Config().capital*(1+rf).cumprod())


def test_risk_targets_and_beta_are_computed(sample):
    panel,_ = prepare(sample[0],sample[1])
    cfg = Config()
    assert panel["beta"].iloc[-1].between(0.7,1.8).any()
    populated = []
    for i in range(252,len(sample[1])):
        w = targets(panel,i,cfg)
        assert w.max() <= cfg.name_cap+1e-12
        assert w.sum() <= cfg.gross_cap+1e-12
        assert (w > 0).sum() <= cfg.max_names
        sector = panel["sector"].iloc[i]
        assert w.groupby(sector).sum().max() <= cfg.sector_cap+1e-12
        populated.append(w.sum())
    assert max(populated) > 0


def test_gap_stop_uses_open_not_stop(sample,result):
    p,b,f = [x.copy() for x in sample]
    buy = result["orders"].loc[result["orders"].amount.gt(0)].iloc[0]
    next_day = b.date.iloc[pd.Index(b.date).get_loc(buy.date)+1]
    mask = p.ticker.eq(buy.ticker) & p.date.eq(next_day)
    original_open = p.loc[mask,"open"].iloc[0]
    p.loc[mask,"open"] = original_open*0.5
    p.loc[mask,"low"] = original_open*0.49
    changed = run_backtest(p,b,f,exploratory=True)
    order = changed["orders"].loc[changed["orders"].date.eq(next_day)&changed["orders"].ticker.eq(buy.ticker)].iloc[0]
    assert order.reason == "gap_stop"
    assert order.price == pytest.approx(original_open*0.5*(1-Config().stop_slippage))


def test_missing_held_quote_fails_explicitly(sample,result):
    p,b,f = [x.copy() for x in sample]
    buy = result["orders"].loc[result["orders"].amount.gt(0)].iloc[0]
    next_day = b.date.iloc[pd.Index(b.date).get_loc(buy.date)+1]
    p = p.loc[~(p.date.eq(next_day)&p.ticker.eq(buy.ticker))]
    with pytest.raises(ValueError,match="sem cotacao"):
        run_backtest(p,b,f,exploratory=True)


def test_vectorbt_real_replay_if_compatibility_target_present():
    root = Path(__file__).resolve().parents[1]
    compat = root/"tmp"/"bets_plotly_compat"
    if not (compat/"plotly"/"__init__.py").exists() or importlib.util.find_spec("vectorbt") is None:
        pytest.skip("Replay opcional: vectorbt e target Plotly compativel nao instalados")
    program = "from scripts.backtest_bets import *; p,b,f=demo_inputs(); r=run_backtest(p,b,f,exploratory=True); v=vectorbt_replay(r,p,b); np.testing.assert_allclose(v,r['curve'].nav,rtol=1e-8,atol=.01); print(len(r['orders']))"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(compat)+os.pathsep+str(root)
    completed = subprocess.run([sys.executable,"-c",program],cwd=root,env=env,capture_output=True,text=True,timeout=180)
    assert completed.returncode == 0, completed.stderr
