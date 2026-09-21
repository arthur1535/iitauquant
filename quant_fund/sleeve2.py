"""Sleeve 2: momentum 12–1, reversão mensal e overlay de risco."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Sleeve2Config
from .risk_overlay import RiskOverlayConfig, build_risk_overlay
from .utils import (
    cross_sectional_zscore,
    ensure_numeric_frame,
    monthly_last,
    portfolio_returns,
    ranked_selection,
    targets_to_monthly_weights,
)


@dataclass
class Sleeve2Result:
    """Sinais, estados e carteiras do Sleeve 2."""

    signals: pd.DataFrame
    regime: pd.DataFrame
    risky_weights: pd.DataFrame
    weights_with_regime: pd.DataFrame
    risky_returns: pd.Series
    returns_with_regime: pd.Series | None


def apply_hysteresis(
    zscore: pd.Series,
    entry_z: float = 1.0,
    exit_z: float = 0.5,
) -> pd.Series:
    """Transforma o z-score em estado persistente normal/estresse."""

    if exit_z >= entry_z:
        raise ValueError("exit_z deve ser menor que entry_z.")
    state = "normal"
    states: list[str] = []
    for value in zscore:
        if pd.notna(value):
            if state == "normal" and value > entry_z:
                state = "stress"
            elif state == "stress" and value < exit_z:
                state = "normal"
        states.append(state)
    return pd.Series(states, index=zscore.index, name="regime_signal", dtype="string")


def build_credit_regime(
    credit_spread: pd.Series,
    monthly_index: pd.DatetimeIndex,
    config: Sleeve2Config,
) -> pd.DataFrame:
    """Calcula z-score móvel, histerese e o regime efetivo defasado um mês."""

    if not isinstance(credit_spread, pd.Series) or credit_spread.empty:
        raise ValueError("credit_spread deve ser uma Series não vazia.")
    spread = pd.to_numeric(credit_spread.copy(), errors="coerce")
    spread = monthly_last(spread).sort_index()
    rolling = spread.rolling(config.spread_window_months, min_periods=config.spread_window_months)
    mean = rolling.mean()
    std = rolling.std(ddof=0).replace(0, np.nan)
    zscore = ((spread - mean) / std).rename("spread_zscore")
    state = apply_hysteresis(zscore, config.stress_entry_z, config.stress_exit_z)

    aligned = pd.DataFrame(index=pd.DatetimeIndex(monthly_index))
    aligned["credit_spread"] = spread.reindex(aligned.index)
    aligned["spread_zscore"] = zscore.reindex(aligned.index)
    aligned["regime_signal"] = state.reindex(aligned.index, method="ffill").fillna("normal")
    aligned["regime_effective"] = aligned["regime_signal"].shift(1).fillna("normal")
    return aligned


def _membership_mask(
    prices: pd.DataFrame,
    universe_membership: pd.DataFrame | None,
) -> pd.DataFrame:
    if universe_membership is None:
        return prices.notna()
    membership = universe_membership.copy()
    membership.index = pd.to_datetime(membership.index, errors="raise")
    membership = monthly_last(membership)
    membership.columns = membership.columns.astype(str)
    membership = membership.reindex(index=prices.index, columns=prices.columns).ffill().fillna(False)
    return membership.astype(bool) & prices.notna()


def build_sleeve2(
    adjusted_prices: pd.DataFrame,
    credit_spread: pd.Series,
    bil_prices: pd.Series | None = None,
    universe_membership: pd.DataFrame | None = None,
    config: Sleeve2Config | None = None,
    *,
    financial_conditions: pd.Series | None = None,
    risk_overlay_config: RiskOverlayConfig | None = None,
) -> Sleeve2Result:
    """Constrói rankings mensais e aplica o regime defensivo no mês seguinte.

    Sem ``financial_conditions``, preserva o regime histórico credit-only e a
    migração integral para BIL. Quando o segundo eixo é informado, aplica o
    overlay graduado configurado por ``RiskOverlayConfig``.
    """

    config = config or Sleeve2Config()
    prices = ensure_numeric_frame(adjusted_prices, "adjusted_prices do Sleeve 2")
    membership = _membership_mask(prices, universe_membership)

    # No fechamento t: momentum P(t-1)/P(t-12)-1 e reversão de t; posição em t+1.
    momentum = prices.shift(1).div(prices.shift(12)).sub(1.0)
    reversal = -prices.pct_change(fill_method=None)
    signal_frames: list[pd.DataFrame] = []
    targets: dict[pd.Timestamp, pd.Series] = {}

    for signal_date in prices.index:
        raw = pd.DataFrame(
            {
                "momentum_12_1_raw": momentum.loc[signal_date],
                "reversal_1m_raw": reversal.loc[signal_date],
            }
        )
        raw = raw.where(membership.loc[signal_date], np.nan).dropna()
        if raw.empty:
            continue
        raw["momentum_z"] = cross_sectional_zscore(
            raw["momentum_12_1_raw"], config.winsor_lower, config.winsor_upper
        )
        raw["reversal_z"] = cross_sectional_zscore(
            raw["reversal_1m_raw"], config.winsor_lower, config.winsor_upper
        )
        raw["composite_score"] = (
            config.momentum_weight * raw["momentum_z"]
            + config.reversal_weight * raw["reversal_z"]
        )
        ranks, selected = ranked_selection(
            raw["composite_score"], fraction=config.selection_fraction
        )
        raw["rank"] = ranks
        raw["selected"] = selected
        raw.insert(0, "signal_date", signal_date)
        raw.index.name = "ticker"
        signal_frames.append(raw.reset_index())

        selected_tickers = raw.index[raw["selected"]]
        target = pd.Series(0.0, index=prices.columns, dtype=float)
        target.loc[selected_tickers] = 1.0 / len(selected_tickers)
        targets[signal_date] = target

    signals = (
        pd.concat(signal_frames, ignore_index=True)
        if signal_frames
        else pd.DataFrame(
            columns=[
                "ticker",
                "signal_date",
                "momentum_12_1_raw",
                "reversal_1m_raw",
                "momentum_z",
                "reversal_z",
                "composite_score",
                "rank",
                "selected",
            ]
        )
    )
    risky_weights = targets_to_monthly_weights(prices.index, prices.columns, targets)
    risky_returns = portfolio_returns(prices, risky_weights)
    risky_returns.name = "sleeve2_risky_return"

    if financial_conditions is None:
        regime = build_credit_regime(credit_spread, prices.index, config)
        derisk_applied = regime["regime_effective"].eq("stress").astype(float)
    else:
        overlay_config = risk_overlay_config or RiskOverlayConfig()
        if len(overlay_config.axis_labels) != 2:
            raise ValueError("O overlay BAA10Y+NFCI exige exatamente dois rótulos de eixo.")
        axes = {
            overlay_config.axis_labels[0]: credit_spread,
            overlay_config.axis_labels[1]: financial_conditions,
        }
        regime = build_risk_overlay(axes, prices.index, overlay_config)
        derisk_applied = regime["derisk_aplicado"]

    regime_columns = prices.columns.union(pd.Index([config.bil_ticker]))
    weights_with_regime = pd.DataFrame(0.0, index=prices.index, columns=regime_columns)
    derisk_applied = derisk_applied.reindex(prices.index).fillna(0.0).clip(0.0, 1.0)
    weights_with_regime.loc[:, prices.columns] = risky_weights.mul(
        1.0 - derisk_applied, axis=0
    )
    weights_with_regime.loc[:, config.bil_ticker] = derisk_applied

    returns_with_regime: pd.Series | None = None
    if bil_prices is not None:
        bil = pd.to_numeric(bil_prices.copy(), errors="coerce").rename(config.bil_ticker)
        bil = monthly_last(bil).reindex(prices.index)
        combined_prices = prices.copy()
        combined_prices[config.bil_ticker] = bil
        returns_with_regime = portfolio_returns(combined_prices, weights_with_regime)
        returns_with_regime.name = "sleeve2_regime_return"

    return Sleeve2Result(
        signals=signals,
        regime=regime,
        risky_weights=risky_weights,
        weights_with_regime=weights_with_regime,
        risky_returns=risky_returns,
        returns_with_regime=returns_with_regime,
    )
