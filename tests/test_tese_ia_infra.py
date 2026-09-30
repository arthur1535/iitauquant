"""Regras de carteira da tese Infraestrutura de IA; dados artificiais não testam a tese econômica."""

import numpy as np
import pandas as pd
import pytest

from scripts.run_tese_ia_infraestrutura import (
    ATIVOS,
    GRUPO_CAMADA,
    PESOS_CAMADAS,
    allocate_targets,
    apply_volatility_target,
    decision_dates,
    simulate_rebalanced_portfolio,
    target_weight_schedule,
    volatility_target_decisions,
)


def _panel(seed: int = 7, days: int = 300):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2023-01-02", periods=days)
    tickers = ["A", "B", "C"]
    returns = pd.DataFrame(rng.normal(0.0005, 0.02, (days, 3)), index=index, columns=tickers)
    closes = 100 * (1 + returns).cumprod()
    volumes = pd.DataFrame(1_000_000.0, index=index, columns=tickers)
    return closes, volumes, returns


def test_base_weights_are_a_full_allocation():
    assert sum(PESOS_CAMADAS.values()) == pytest.approx(1.0)
    assert len({a.ticker for a in ATIVOS}) == len(ATIVOS)


def test_ineligible_weight_stays_inside_its_layer():
    eligible = [t for t in PESOS_CAMADAS if t != "GEV"]
    targets = allocate_targets(PESOS_CAMADAS, GRUPO_CAMADA, eligible)
    assert targets["GEV"] == 0.0
    assert sum(targets.values()) == pytest.approx(1.0)
    energia = sum(w for t, w in targets.items() if GRUPO_CAMADA[t] == "energia")
    assert energia == pytest.approx(0.28)
    assert targets["VST"] / targets["BE"] == pytest.approx(0.10 / 0.08)


def test_empty_layer_is_spread_pro_rata_across_other_layers():
    eligible = [t for t in PESOS_CAMADAS if GRUPO_CAMADA[t] != "especulativo"]
    targets = allocate_targets(PESOS_CAMADAS, GRUPO_CAMADA, eligible)
    assert sum(targets.values()) == pytest.approx(1.0)
    assert targets["NVDA"] == pytest.approx(0.20 / 0.90)
    assert allocate_targets(PESOS_CAMADAS, GRUPO_CAMADA, []) == {t: 0.0 for t in PESOS_CAMADAS}


def test_decision_dates_are_month_ends_with_a_following_session():
    index = pd.bdate_range("2024-01-02", "2024-04-30")
    dates = decision_dates(index)
    assert list(dates.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29", "2024-03-29"]


def test_liquidity_and_listing_use_only_information_up_to_the_decision():
    closes, volumes, _ = _panel()
    closes.loc[:"2023-03-15", "C"] = np.nan  # listado depois
    volumes.loc["2023-06-01":, "B"] = 1.0  # fica ilíquido depois
    base = {"A": 0.5, "B": 0.3, "C": 0.2}
    groups = {"A": "x", "B": "x", "C": "y"}
    schedule = target_weight_schedule(closes, volumes, base, groups, min_dollar_volume=5e6)
    assert schedule.loc["2023-02-28", "C"] == 0.0
    assert schedule.loc["2023-05-31", "C"] > 0.0
    assert schedule.loc["2023-05-31", "B"] > 0.0
    assert schedule.loc["2023-09-29", "B"] == 0.0

    changed = volumes.copy()
    changed.loc["2023-07-03":, :] = 0.0
    later = target_weight_schedule(closes, changed, base, groups, min_dollar_volume=5e6)
    pd.testing.assert_frame_equal(schedule.loc[:"2023-06-30"], later.loc[:"2023-06-30"])


def test_rebalance_executes_on_the_session_after_the_decision_and_charges_turnover():
    index = pd.bdate_range("2024-01-29", periods=6)
    returns = pd.DataFrame({"A": [0.0, 0.0, 0.0, 0.10, 0.0, 0.0], "B": 0.0}, index=index)
    targets = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=[index[2]])  # decisão em 31/01
    result = simulate_rebalanced_portfolio(returns, targets, cost_per_side=0.001, initial_capital=100.0)
    curve = result.curve
    assert curve.index[0] == index[3]
    assert curve["turnover"].iloc[0] == pytest.approx(1.0)
    # O retorno de A no dia da execução ainda pertence aos pesos antigos (zero).
    assert curve["nav"].iloc[0] == pytest.approx(100.0 * (1 - 0.001))
    assert result.weights.iloc[0].tolist() == [0.5, 0.5]


def test_future_returns_cannot_change_past_portfolio_values():
    closes, volumes, returns = _panel()
    volumes *= 100
    base = {"A": 0.5, "B": 0.3, "C": 0.2}
    groups = {"A": "x", "B": "x", "C": "y"}
    schedule = target_weight_schedule(closes, volumes, base, groups, min_dollar_volume=1e6)
    original = simulate_rebalanced_portfolio(returns, schedule)
    boundary = returns.index[180]
    shocked = returns.copy()
    shocked.loc[shocked.index > boundary] *= -3
    changed = simulate_rebalanced_portfolio(shocked, schedule)
    pd.testing.assert_frame_equal(original.curve.loc[:boundary], changed.curve.loc[:boundary])


def test_volatility_target_is_bounded_lagged_and_causal():
    rng = np.random.default_rng(3)
    index = pd.bdate_range("2024-01-01", periods=250)
    base = pd.Series(rng.normal(0, 0.01, 250), index=index)
    base.iloc[100:130] = rng.normal(0, 0.06, 30)  # regime turbulento
    decisions = volatility_target_decisions(base)
    assert decisions.between(0.0, 1.0).all()
    assert decisions.iloc[:100].eq(1.0).all()
    assert decisions.iloc[120:140].lt(1.0).any()

    scaled = apply_volatility_target(base, decisions, cost_per_side=0.0)
    pd.testing.assert_series_equal(scaled["multiplier"].iloc[2:], decisions.shift(2).iloc[2:], check_names=False)

    shocked = base.copy()
    shocked.iloc[200:] = 0.2
    later = volatility_target_decisions(shocked)
    pd.testing.assert_series_equal(decisions.iloc[:200], later.iloc[:200])
