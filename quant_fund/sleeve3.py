"""Sleeve 3: posição integral no ETF BIL."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .utils import monthly_last


@dataclass
class Sleeve3Result:
    """Retorno ajustado e pesos mensais do BIL."""

    prices: pd.Series
    returns: pd.Series
    weights: pd.DataFrame


def build_sleeve3(bil_prices: pd.Series, ticker: str = "BIL") -> Sleeve3Result:
    """Calcula o carrego do BIL a partir de preços ajustados."""

    if not isinstance(bil_prices, pd.Series) or bil_prices.empty:
        raise ValueError("bil_prices deve ser uma Series não vazia.")
    prices = pd.to_numeric(bil_prices.copy(), errors="coerce")
    prices = monthly_last(prices).sort_index().rename(ticker)
    if prices.le(0).any():
        raise ValueError("bil_prices contém preço não positivo.")
    returns = prices.pct_change(fill_method=None).rename("sleeve3_return")
    weights = pd.DataFrame({ticker: 1.0}, index=prices.index)
    weights.index.name = "date"
    return Sleeve3Result(prices=prices, returns=returns, weights=weights)
