"""Sleeve 1: fatores fundamentalistas, seleção anual e pesos mensais."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Sleeve1Config
from .utils import (
    cross_sectional_zscore,
    ensure_numeric_frame,
    portfolio_returns,
    ranked_selection,
    targets_to_buy_and_hold_weights,
)


REQUIRED_FUNDAMENTAL_COLUMNS = {
    "ticker",
    "fiscal_date",
    "book_equity",
    "total_assets",
    "gross_profit",
}


@dataclass
class Sleeve1Result:
    """Artefatos auditáveis produzidos pelo Sleeve 1."""

    signals: pd.DataFrame
    weights: pd.DataFrame
    returns: pd.Series


def prepare_fundamentals(
    fundamentals: pd.DataFrame,
    config: Sleeve1Config,
) -> pd.DataFrame:
    """Calcula fatores brutos e datas point-in-time de cada balanço."""

    missing = REQUIRED_FUNDAMENTAL_COLUMNS.difference(fundamentals.columns)
    if missing:
        raise ValueError(f"Fundamentos sem colunas obrigatórias: {sorted(missing)}")
    if "market_cap" not in fundamentals and "shares_outstanding" not in fundamentals:
        raise ValueError("Fundamentos precisam de market_cap ou shares_outstanding.")
    data = fundamentals.copy()
    data["ticker"] = data["ticker"].astype(str)
    data["fiscal_date"] = pd.to_datetime(data["fiscal_date"], errors="raise")
    if "available_date" in data:
        data["available_date"] = pd.to_datetime(data["available_date"], errors="coerce")
        fallback = data["fiscal_date"] + pd.DateOffset(months=config.reporting_lag_months)
        data["available_date"] = data["available_date"].fillna(fallback)
    else:
        data["available_date"] = data["fiscal_date"] + pd.DateOffset(
            months=config.reporting_lag_months
        )
    if data["available_date"].lt(data["fiscal_date"]).any():
        raise ValueError("available_date não pode ser anterior a fiscal_date.")
    numeric_columns = ["book_equity", "total_assets", "gross_profit"]
    for optional_column in ("market_cap", "shares_outstanding"):
        if optional_column not in data:
            data[optional_column] = np.nan
        numeric_columns.append(optional_column)
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.sort_values(["ticker", "fiscal_date", "available_date"], kind="stable")
    data["previous_total_assets"] = data.groupby("ticker", sort=False)["total_assets"].shift(1)
    previous_fiscal_date = data.groupby("ticker", sort=False)["fiscal_date"].shift(1)
    annual_gap_days = (data["fiscal_date"] - previous_fiscal_date).dt.days

    positive_assets = data["total_assets"].where(data["total_assets"].gt(0))
    positive_previous_assets = data["previous_total_assets"].where(
        data["previous_total_assets"].gt(0) & annual_gap_days.between(300, 430)
    )
    data["profitability_raw"] = data["gross_profit"] / positive_assets
    data["investment_raw"] = -(data["total_assets"] / positive_previous_assets - 1.0)
    data = data.replace([np.inf, -np.inf], np.nan)
    return data


def build_sleeve1(
    adjusted_prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    config: Sleeve1Config | None = None,
    market_prices: pd.DataFrame | None = None,
) -> Sleeve1Result:
    """Constrói sinais anuais e posições mensais, vigentes no mês após o sinal."""

    config = config or Sleeve1Config()
    prices = ensure_numeric_frame(adjusted_prices, "adjusted_prices do Sleeve 1")
    prepared = prepare_fundamentals(fundamentals, config)
    close_prices: pd.DataFrame | None = None
    if market_prices is not None:
        close_prices = ensure_numeric_frame(market_prices, "market_prices do Sleeve 1").reindex(
            index=prices.index, columns=prices.columns
        )
    elif prepared["market_cap"].isna().any():
        raise ValueError(
            "market_prices (Close não ajustado) é obrigatório quando market_cap não é fornecido."
        )
    prepared = prepared.loc[prepared["ticker"].isin(prices.columns)]
    signal_dates = prices.index[prices.index.month == config.rebalance_month]
    factor_names = ["size", "value", "profitability", "investment"]
    raw_columns = [f"{name}_raw" for name in factor_names]
    signal_frames: list[pd.DataFrame] = []
    targets: dict[pd.Timestamp, pd.Series] = {}

    for signal_date in signal_dates:
        known = prepared.loc[prepared["available_date"].le(signal_date)]
        if known.empty:
            continue
        latest = (
            known.sort_values(["ticker", "available_date", "fiscal_date"], kind="stable")
            .groupby("ticker", sort=False, as_index=False)
            .tail(1)
            .set_index("ticker")
        )
        if config.max_statement_age_months is not None:
            oldest = signal_date - pd.DateOffset(months=config.max_statement_age_months)
            latest = latest.loc[latest["fiscal_date"].ge(oldest)]
        if close_prices is None:
            derived_market_cap = pd.Series(np.nan, index=latest.index)
        else:
            price_as_of = close_prices.loc[signal_date].reindex(latest.index)
            derived_market_cap = latest["shares_outstanding"] * price_as_of
        latest["market_cap_used"] = latest["market_cap"].where(
            latest["market_cap"].gt(0), derived_market_cap
        )
        positive_market_cap = latest["market_cap_used"].where(latest["market_cap_used"].gt(0))
        latest["size_raw"] = -positive_market_cap
        latest["value_raw"] = latest["book_equity"] / positive_market_cap
        eligible = latest.dropna(subset=raw_columns).copy()
        if eligible.empty:
            continue
        for factor in factor_names:
            eligible[f"{factor}_z"] = cross_sectional_zscore(
                eligible[f"{factor}_raw"], config.winsor_lower, config.winsor_upper
            )
        z_columns = [f"{name}_z" for name in factor_names]
        eligible["composite_score"] = eligible[z_columns].mean(axis=1)
        ranks, selected = ranked_selection(
            eligible["composite_score"],
            top_n=config.top_n,
            fraction=config.selection_fraction,
        )
        eligible["rank"] = ranks
        eligible["selected"] = selected
        eligible.insert(0, "signal_date", signal_date)
        keep = [
            "signal_date",
            "fiscal_date",
            "available_date",
            "market_cap_used",
            *raw_columns,
            *z_columns,
            "composite_score",
            "rank",
            "selected",
        ]
        signal_frames.append(eligible[keep].reset_index())
        selected_tickers = eligible.index[eligible["selected"]]
        target = pd.Series(0.0, index=prices.columns, dtype=float)
        if len(selected_tickers):
            target.loc[selected_tickers] = 1.0 / len(selected_tickers)
        targets[signal_date] = target

    signal_columns = [
        "ticker",
        "signal_date",
        "fiscal_date",
        "available_date",
        "market_cap_used",
        *raw_columns,
        *(f"{name}_z" for name in factor_names),
        "composite_score",
        "rank",
        "selected",
    ]
    signals = (
        pd.concat(signal_frames, ignore_index=True)
        if signal_frames
        else pd.DataFrame(columns=signal_columns)
    )
    weights = targets_to_buy_and_hold_weights(prices, targets)
    returns = portfolio_returns(prices, weights)
    returns.name = "sleeve1_return"
    return Sleeve1Result(signals=signals, weights=weights, returns=returns)
