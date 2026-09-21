"""Estatísticas para reduzir o otimismo causado por múltiplos testes."""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np


_NORMAL = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329


def expected_maximum_sharpe(sharpe_std: float, number_of_trials: int) -> float:
    """Aproxima o maior Sharpe esperado sob múltiplos testes ruidosos."""

    if number_of_trials < 1:
        raise ValueError("number_of_trials deve ser >= 1")
    if number_of_trials == 1 or sharpe_std <= 0 or not np.isfinite(sharpe_std):
        return 0.0
    n = float(number_of_trials)
    first = _NORMAL.inv_cdf(1.0 - 1.0 / n)
    second = _NORMAL.inv_cdf(1.0 - 1.0 / (n * math.e))
    return float(sharpe_std * ((1.0 - _EULER_MASCHERONI) * first + _EULER_MASCHERONI * second))


def deflated_sharpe_probability(
    observed_annualized_sharpe: float,
    benchmark_annualized_sharpe: float,
    *,
    n_observations: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    periods_per_year: int = 252,
) -> float:
    """Probabilidade DSR de o Sharpe superar o benchmark de data snooping.

    A assimetria e a curtose são estimadas na série de retornos da própria
    simulação. O retorno é uma probabilidade em ``[0, 1]``, não um Sharpe.
    """

    if n_observations < 2:
        return float("nan")
    if periods_per_year < 1:
        raise ValueError("periods_per_year deve ser >= 1")
    scale = math.sqrt(periods_per_year)
    observed = observed_annualized_sharpe / scale
    benchmark = benchmark_annualized_sharpe / scale
    denominator_term = 1.0 - skewness * observed + ((kurtosis - 1.0) / 4.0) * observed**2
    if denominator_term <= 0 or not np.isfinite(denominator_term):
        return float("nan")
    statistic = (observed - benchmark) * math.sqrt(n_observations - 1.0) / math.sqrt(denominator_term)
    return float(_NORMAL.cdf(statistic))
