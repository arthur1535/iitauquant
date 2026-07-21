"""Utilitários comuns de datas, padronização e carteiras."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def monthly_last(data: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Converte observações diárias/irregulares para o último valor de cada mês."""

    result = data.copy()
    result.index = pd.to_datetime(result.index, errors="raise")
    if isinstance(result.index, pd.DatetimeIndex) and result.index.tz is not None:
        result.index = result.index.tz_localize(None)
    result = result.sort_index()
    result.index = result.index.to_period("M").to_timestamp("M")
    return result.groupby(level=0).last()


def ensure_numeric_frame(data: pd.DataFrame, name: str) -> pd.DataFrame:
    """Normaliza uma matriz wide e rejeita colunas duplicadas."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError(f"{name} deve ser um DataFrame não vazio.")
    if data.columns.has_duplicates:
        raise ValueError(f"{name} contém tickers duplicados.")
    result = data.copy()
    result.columns = result.columns.astype(str)
    result = result.apply(pd.to_numeric, errors="coerce")
    if result.le(0).any(axis=None):
        raise ValueError(f"{name} contém preço não positivo.")
    return monthly_last(result)


def cross_sectional_zscore(
    values: pd.Series,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.Series:
    """Winsoriza e padroniza uma seção transversal com desvio populacional."""

    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = numeric.dropna()
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if valid.empty:
        return result
    lo = valid.quantile(lower)
    hi = valid.quantile(upper)
    clipped = valid.clip(lo, hi)
    std = float(clipped.std(ddof=0))
    if not np.isfinite(std) or std == 0:
        result.loc[clipped.index] = 0.0
    else:
        result.loc[clipped.index] = (clipped - clipped.mean()) / std
    return result


def ranked_selection(
    scores: pd.Series,
    *,
    top_n: int | None = None,
    fraction: float | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Retorna ranks e seleção, com desempate determinístico pelo ticker."""

    valid = pd.to_numeric(scores, errors="coerce").dropna()
    ranks = pd.Series(pd.NA, index=scores.index, dtype="Int64")
    selected = pd.Series(False, index=scores.index, dtype=bool)
    if valid.empty:
        return ranks, selected
    ordered = pd.DataFrame({"score": valid, "ticker_sort": valid.index.astype(str)}, index=valid.index)
    ordered = ordered.sort_values(
        ["score", "ticker_sort"], ascending=[False, True], kind="stable"
    )
    ranks.loc[ordered.index] = np.arange(1, len(ordered) + 1)
    if top_n is not None:
        count = min(top_n, len(ordered))
    elif fraction is not None:
        count = max(1, math.ceil(len(ordered) * fraction))
    else:
        raise ValueError("Defina top_n ou fraction.")
    selected.loc[ordered.index[:count]] = True
    return ranks, selected


def targets_to_monthly_weights(
    monthly_index: pd.DatetimeIndex,
    tickers: Iterable[str],
    targets: dict[pd.Timestamp, pd.Series],
) -> pd.DataFrame:
    """Aplica alvos no mês seguinte ao sinal e mantém pesos até o próximo alvo."""

    index = pd.DatetimeIndex(monthly_index).sort_values().unique()
    columns = pd.Index(sorted({str(ticker) for ticker in tickers}))
    weights = pd.DataFrame(np.nan, index=index, columns=columns, dtype=float)
    positions = {date: position for position, date in enumerate(index)}
    for signal_date, target in sorted(targets.items()):
        position = positions.get(pd.Timestamp(signal_date))
        if position is None or position + 1 >= len(index):
            continue
        effective_date = index[position + 1]
        row = pd.Series(0.0, index=columns)
        common = row.index.intersection(target.index.astype(str))
        target_copy = target.copy()
        target_copy.index = target_copy.index.astype(str)
        row.loc[common] = target_copy.loc[common].astype(float)
        weights.loc[effective_date] = row
    return weights.ffill().fillna(0.0)


def portfolio_returns(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    """Calcula retorno mensal sem tratar retorno faltante de posição ativa como zero."""

    monthly_prices = ensure_numeric_frame(prices, "prices")
    common_index = monthly_prices.index.intersection(weights.index)
    common_columns = monthly_prices.columns.intersection(weights.columns)
    aligned_prices = monthly_prices.reindex(index=common_index, columns=common_columns)
    aligned_weights = weights.reindex(index=common_index, columns=common_columns).fillna(0.0)
    asset_returns = aligned_prices.pct_change(fill_method=None)
    active_missing = asset_returns.isna() & aligned_weights.gt(0)
    result = (asset_returns * aligned_weights).sum(axis=1, min_count=1)
    valid = ~active_missing.any(axis=1) & aligned_weights.sum(axis=1).gt(0)
    result = result.where(valid)
    result.name = "return"
    return result


def weights_to_long(weights: pd.DataFrame, value_name: str = "weight") -> pd.DataFrame:
    """Converte pesos wide em tabela longa, preservando apenas posições positivas."""

    named = weights.copy()
    named.index.name = "date"
    named.columns.name = "ticker"
    long = named.stack(future_stack=True).rename(value_name).reset_index()
    return long.loc[long[value_name].gt(0)].reset_index(drop=True)
