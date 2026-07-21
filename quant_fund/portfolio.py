"""Integração dos sleeves e pesos do fundo consolidado."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FundConfig


ALLOCATION_COLUMNS = ["factor", "small_caps", "fixed_income"]


def build_fund_allocations(
    regime_effective: pd.Series,
    config: FundConfig | None = None,
) -> pd.DataFrame:
    """Produz 1/3-1/3-1/3 no normal e 1/3-0-2/3 no estresse."""

    config = config or FundConfig()
    regime = regime_effective.astype("string")
    invalid = set(regime.dropna().unique()).difference({"normal", "stress"})
    if invalid:
        raise ValueError(f"Estados de regime inválidos: {sorted(invalid)}")
    allocations = pd.DataFrame(index=regime.index, columns=ALLOCATION_COLUMNS, dtype=float)
    normal = regime.fillna("normal").eq("normal")
    allocations.loc[normal] = [
        config.normal_factor,
        config.normal_small_caps,
        config.normal_fixed_income,
    ]
    allocations.loc[~normal] = [
        config.stress_factor,
        config.stress_small_caps,
        config.stress_fixed_income,
    ]
    allocations.index.name = "date"
    return allocations


def combine_security_weights(
    sleeve1_weights: pd.DataFrame,
    sleeve2_risky_weights: pd.DataFrame,
    allocations: pd.DataFrame,
    bil_ticker: str = "BIL",
) -> pd.DataFrame:
    """Converte alocações entre sleeves em pesos mensais por instrumento."""

    required = set(ALLOCATION_COLUMNS)
    if not required.issubset(allocations.columns):
        raise ValueError(f"Alocações sem colunas: {sorted(required.difference(allocations.columns))}")
    index = allocations.index
    columns = sleeve1_weights.columns.union(sleeve2_risky_weights.columns).union([bil_ticker])
    result = pd.DataFrame(0.0, index=index, columns=columns)
    sleeve1 = sleeve1_weights.reindex(index=index, columns=columns, fill_value=0.0).fillna(0.0)
    sleeve2 = sleeve2_risky_weights.reindex(
        index=index, columns=columns, fill_value=0.0
    ).fillna(0.0)
    result = result.add(sleeve1.mul(allocations["factor"], axis=0), fill_value=0.0)
    result = result.add(sleeve2.mul(allocations["small_caps"], axis=0), fill_value=0.0)
    result.loc[:, bil_ticker] = result[bil_ticker] + allocations["fixed_income"]
    result.index.name = "date"
    return result


def build_fund_returns(
    sleeve1_returns: pd.Series,
    sleeve2_risky_returns: pd.Series,
    sleeve3_returns: pd.Series,
    allocations: pd.DataFrame,
) -> pd.Series:
    """Combina retornos e exige dado somente dos sleeves com peso positivo."""

    components = pd.concat(
        [
            sleeve1_returns.rename("factor"),
            sleeve2_risky_returns.rename("small_caps"),
            sleeve3_returns.rename("fixed_income"),
        ],
        axis=1,
    ).reindex(allocations.index)
    active_missing = components.isna() & allocations.gt(0)
    result = (components * allocations).sum(axis=1, min_count=1)
    result = result.where(~active_missing.any(axis=1))
    result.name = "fund_return"
    return result


def validate_fully_invested(weights: pd.DataFrame, tolerance: float = 1e-10) -> pd.Series:
    """Indica as linhas cujos pesos são finitos, não negativos e somam um."""

    finite = pd.DataFrame(np.isfinite(weights), index=weights.index, columns=weights.columns).all(axis=1)
    nonnegative = weights.ge(-tolerance).all(axis=1)
    sums_one = weights.sum(axis=1).sub(1.0).abs().le(tolerance)
    return finite & nonnegative & sums_one
