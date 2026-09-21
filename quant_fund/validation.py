"""Validações estatísticas para resultados de backtest.

O módulo separa três perguntas que uma métrica pontual não responde:

* PSR/DSR: quão compatível o Sharpe observado é com um benchmark, levando em
  conta tamanho da amostra, assimetria, curtose e, no DSR, múltiplas tentativas;
* bootstrap em blocos móveis: qual a incerteza da média sem destruir toda a
  dependência temporal de curto prazo;
* placebo por deslocamento circular: se o timing histórico do sinal foi melhor
  que o mesmo caminho de sinal aplicado em outros meses da mesma amostra.

O placebo é um teste de falsificação *in-sample*. Ele não cria observações
novas, não é validação out-of-sample e não substitui walk-forward ou holdout.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import TypeAlias

import numpy as np
import pandas as pd


ArrayLike1D: TypeAlias = pd.Series | np.ndarray | Sequence[float]
METRICS = ("cagr", "sharpe", "max_drawdown", "mean_worst_months")
_EULER_MASCHERONI = 0.5772156649015329
_STANDARD_NORMAL = NormalDist()


@dataclass(frozen=True)
class BootstrapMeanResult:
    """Resultado anualizado do bootstrap em blocos móveis.

    ``estimate``, os limites do intervalo e ``standard_error`` estão todos na
    mesma unidade anualizada (média por período multiplicada por
    ``periods_per_year``).
    """

    estimate: float
    ci_lower: float
    ci_upper: float
    standard_error: float
    confidence_level: float
    periods_per_year: float
    n_bootstrap: int
    block_length: int
    seed: int


@dataclass(frozen=True)
class CircularShiftPlaceboResult:
    """Resultado do teste placebo por rotações do caminho de de-risking.

    Os percentis variam de 0 a 100 e usam mid-rank para empates. Como as quatro
    métricas são orientadas para cima (drawdown é reportado como número
    negativo), um percentil maior indica resultado verdadeiro mais favorável.
    """

    true_metrics: pd.Series
    placebo_metrics: pd.DataFrame
    percentiles: pd.Series
    cost_bps: float
    periods_per_year: float
    worst_periods: int


def _finite_float(value: float, name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser numérico e finito.") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} deve ser numérico e finito.")
    return numeric


def _positive_int(value: int, name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} deve ser um inteiro >= {minimum}.")
    numeric = int(value)
    if numeric < minimum:
        raise ValueError(f"{name} deve ser um inteiro >= {minimum}.")
    return numeric


def _positive_periods_per_year(value: float) -> float:
    numeric = _finite_float(value, "periods_per_year")
    if numeric <= 0:
        raise ValueError("periods_per_year deve ser positivo.")
    return numeric


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float = 0.0,
    *,
    observations: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    periods_per_year: float = 1.0,
) -> float:
    """Calcula o Probabilistic Sharpe Ratio de Bailey e López de Prado.

    A fórmula usa curtose de Pearson (3 para uma Normal), não excesso de
    curtose. ``observed_sharpe`` e ``benchmark_sharpe`` podem ser anualizados;
    ``periods_per_year`` os converte para a frequência das observações antes
    de aplicar a equação. Use 12 para retornos mensais e 1 para Sharpes já
    expressos por período.

    O retorno é a probabilidade assintótica de o Sharpe verdadeiro exceder o
    benchmark, ajustada pelos terceiro e quarto momentos da distribuição.
    """

    observed = _finite_float(observed_sharpe, "observed_sharpe")
    benchmark = _finite_float(benchmark_sharpe, "benchmark_sharpe")
    n_obs = _positive_int(observations, "observations", minimum=2)
    skew = _finite_float(skewness, "skewness")
    raw_kurtosis = _finite_float(kurtosis, "kurtosis")
    annualization = _positive_periods_per_year(periods_per_year)
    if raw_kurtosis < 1.0:
        raise ValueError("kurtosis deve ser curtose de Pearson >= 1.")

    scale = math.sqrt(annualization)
    observed_periodic = observed / scale
    benchmark_periodic = benchmark / scale
    variance_term = (
        1.0
        - skew * observed_periodic
        + ((raw_kurtosis - 1.0) / 4.0) * observed_periodic**2
    )
    if variance_term <= 0 or not math.isfinite(variance_term):
        raise ValueError("Os momentos informados produzem variância de Sharpe inválida.")

    statistic = (
        (observed_periodic - benchmark_periodic)
        * math.sqrt(n_obs - 1)
        / math.sqrt(variance_term)
    )
    probability = _STANDARD_NORMAL.cdf(statistic)
    return float(min(1.0, max(0.0, probability)))


def expected_maximum_sharpe_ratio(
    mean_sharpe: float,
    sharpe_std: float,
    num_trials: int,
) -> float:
    """Aproxima o maior Sharpe esperado entre tentativas independentes.

    Implementa a aproximação de extremos usada no Deflated Sharpe Ratio.
    Média e desvio devem estar na mesma escala (anualizada ou por período) e
    ``num_trials`` deve representar tentativas *independentes efetivas*.
    """

    mean = _finite_float(mean_sharpe, "mean_sharpe")
    std = _finite_float(sharpe_std, "sharpe_std")
    trials = _positive_int(num_trials, "num_trials")
    if std < 0:
        raise ValueError("sharpe_std não pode ser negativo.")
    if trials == 1 or std == 0:
        return mean

    first_quantile = _STANDARD_NORMAL.inv_cdf(1.0 - 1.0 / trials)
    second_quantile = _STANDARD_NORMAL.inv_cdf(1.0 - 1.0 / (trials * math.e))
    max_standard_normal = (
        (1.0 - _EULER_MASCHERONI) * first_quantile
        + _EULER_MASCHERONI * second_quantile
    )
    return float(mean + std * max_standard_normal)


def deflated_sharpe_ratio(
    observed_sharpe: float,
    *,
    observations: int,
    num_trials: int,
    sharpe_std: float,
    mean_sharpe: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    periods_per_year: float = 1.0,
) -> float:
    """Calcula o Deflated Sharpe Ratio de Bailey e López de Prado.

    O benchmark do PSR é substituído pelo maior Sharpe esperado sob
    ``num_trials`` tentativas independentes efetivas. ``sharpe_std`` é o
    desvio transversal dos Sharpes testados, e deve usar a mesma anualização
    de ``observed_sharpe`` e ``mean_sharpe``.
    """

    benchmark = expected_maximum_sharpe_ratio(mean_sharpe, sharpe_std, num_trials)
    return probabilistic_sharpe_ratio(
        observed_sharpe,
        benchmark,
        observations=observations,
        skewness=skewness,
        kurtosis=kurtosis,
        periods_per_year=periods_per_year,
    )


def _finite_array(values: ArrayLike1D, name: str, *, minimum_size: int) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve conter somente números finitos.") from exc
    if array.ndim != 1:
        raise ValueError(f"{name} deve ser unidimensional.")
    if array.size < minimum_size:
        raise ValueError(f"{name} deve ter ao menos {minimum_size} observações.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} deve conter somente números finitos.")
    return array.astype(float, copy=True)


def moving_block_bootstrap_mean(
    returns: ArrayLike1D,
    *,
    periods_per_year: float = 12.0,
    block_length: int | None = None,
    n_bootstrap: int = 5_000,
    confidence_level: float = 0.95,
    seed: int = 0,
) -> BootstrapMeanResult:
    """Estima média anualizada e IC por moving-block bootstrap.

    São sorteados, com reposição, blocos contíguos dentre os ``n-L+1``
    blocos sobrepostos da amostra. Cada replicação é truncada ao tamanho
    original. A semente explícita torna o resultado reprodutível.

    A estatística anualizada é a média aritmética por período multiplicada
    por ``periods_per_year``; ela não é CAGR.
    """

    values = _finite_array(returns, "returns", minimum_size=2)
    annualization = _positive_periods_per_year(periods_per_year)
    repetitions = _positive_int(n_bootstrap, "n_bootstrap", minimum=2)
    confidence = _finite_float(confidence_level, "confidence_level")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence_level deve estar em (0, 1).")
    random_seed = _positive_int(seed, "seed", minimum=0)

    if block_length is None:
        length = max(1, int(round(values.size ** (1.0 / 3.0))))
    else:
        length = _positive_int(block_length, "block_length")
    if length > values.size:
        raise ValueError("block_length não pode exceder o tamanho da amostra.")

    rng = np.random.default_rng(random_seed)
    blocks_per_replication = math.ceil(values.size / length)
    last_start = values.size - length
    estimates = np.empty(repetitions, dtype=float)
    for replication in range(repetitions):
        starts = rng.integers(0, last_start + 1, size=blocks_per_replication)
        sample = np.concatenate([values[start : start + length] for start in starts])
        estimates[replication] = sample[: values.size].mean() * annualization

    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [alpha, 1.0 - alpha])
    return BootstrapMeanResult(
        estimate=float(values.mean() * annualization),
        ci_lower=float(lower),
        ci_upper=float(upper),
        standard_error=float(estimates.std(ddof=1)),
        confidence_level=confidence,
        periods_per_year=annualization,
        n_bootstrap=repetitions,
        block_length=length,
        seed=random_seed,
    )


def _validate_placebo_inputs(
    risky_returns: ArrayLike1D,
    cash_returns: ArrayLike1D,
    derisk_levels: ArrayLike1D,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    inputs = (risky_returns, cash_returns, derisk_levels)
    are_series = tuple(isinstance(value, pd.Series) for value in inputs)
    if any(are_series) and not all(are_series):
        raise ValueError("Use três Series indexadas ou três vetores posicionais.")
    if all(are_series):
        risky_series = risky_returns
        cash_series = cash_returns
        derisk_series = derisk_levels
        assert isinstance(risky_series, pd.Series)
        assert isinstance(cash_series, pd.Series)
        assert isinstance(derisk_series, pd.Series)
        if not risky_series.index.is_unique:
            raise ValueError("Os índices das Series devem ser únicos.")
        if not (
            risky_series.index.equals(cash_series.index)
            and risky_series.index.equals(derisk_series.index)
        ):
            raise ValueError("As Series devem ter índices idênticos e na mesma ordem.")

    risky = _finite_array(risky_returns, "risky_returns", minimum_size=3)
    cash = _finite_array(cash_returns, "cash_returns", minimum_size=3)
    derisk = _finite_array(derisk_levels, "derisk_levels", minimum_size=3)
    if not (risky.size == cash.size == derisk.size):
        raise ValueError("Retornos e níveis de de-risking devem ter o mesmo tamanho.")
    if np.any(risky <= -1.0) or np.any(cash <= -1.0):
        raise ValueError("Retornos simples devem ser maiores que -100%.")
    if np.any((derisk < 0.0) | (derisk > 1.0)):
        raise ValueError("derisk_levels deve permanecer no intervalo [0, 1].")
    return risky, cash, derisk


def _returns_with_derisk(
    risky: np.ndarray,
    cash: np.ndarray,
    derisk: np.ndarray,
    cost_rate: float,
) -> np.ndarray:
    # Convenção do backtest do projeto: não há custo de posição inicial;
    # depois, uma mudança delta em de-risking representa giro unilateral delta.
    turnover = np.empty_like(derisk)
    turnover[0] = 0.0
    turnover[1:] = np.abs(np.diff(derisk))
    result = risky * (1.0 - derisk) + cash * derisk - turnover * cost_rate
    if np.any(result <= -1.0):
        raise ValueError("Custo e retornos geram retorno de estratégia <= -100%.")
    return result


def _performance_metrics(
    strategy_returns: np.ndarray,
    cash_returns: np.ndarray,
    periods_per_year: float,
    worst_periods: int,
) -> dict[str, float]:
    growth = float(np.prod(1.0 + strategy_returns))
    cagr = growth ** (periods_per_year / strategy_returns.size) - 1.0

    excess = strategy_returns - cash_returns
    excess_std = float(excess.std(ddof=1))
    sharpe = (
        float(excess.mean() / excess_std * math.sqrt(periods_per_year))
        if excess_std > 0.0
        else math.nan
    )

    wealth = np.concatenate(([1.0], np.cumprod(1.0 + strategy_returns)))
    drawdowns = wealth / np.maximum.accumulate(wealth) - 1.0
    mean_worst = float(np.partition(strategy_returns, worst_periods - 1)[:worst_periods].mean())
    return {
        "cagr": float(cagr),
        "sharpe": sharpe,
        "max_drawdown": float(drawdowns.min()),
        "mean_worst_months": mean_worst,
    }


def _midrank_percentile(true_value: float, placebo_values: pd.Series) -> float:
    values = placebo_values.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if not math.isfinite(true_value) or finite.size == 0:
        return math.nan
    equal = np.isclose(finite, true_value, rtol=1e-12, atol=1e-14)
    strictly_lower = (finite < true_value) & ~equal
    return float(100.0 * (strictly_lower.sum() + 0.5 * equal.sum()) / finite.size)


def circular_shift_placebo_test(
    risky_returns: ArrayLike1D,
    cash_returns: ArrayLike1D,
    derisk_levels: ArrayLike1D,
    *,
    cost_bps: float = 0.0,
    periods_per_year: float = 12.0,
    worst_periods: int = 5,
) -> CircularShiftPlaceboResult:
    """Compara o sinal verdadeiro com todos os deslocamentos circulares não nulos.

    Cada placebo é ``np.roll(derisk_levels, shift)`` para ``shift`` entre 1 e
    ``n-1``. Assim, preserva-se a distribuição dos níveis, a ordem cíclica, a
    persistência e as durações dos regimes; muda apenas o alinhamento com os
    retornos. O custo é recalculado depois de cada rotação, com custo inicial
    zero, para reproduzir a convenção do backtest.

    O resultado informa CAGR, Sharpe anualizado sobre caixa, max drawdown e
    média dos piores períodos. Os percentis comparam o sinal verdadeiro a todos
    os ``n-1`` placebos. Este é um teste de falsificação in-sample, não uma
    validação out-of-sample.
    """

    risky, cash, derisk = _validate_placebo_inputs(risky_returns, cash_returns, derisk_levels)
    bps = _finite_float(cost_bps, "cost_bps")
    if bps < 0:
        raise ValueError("cost_bps não pode ser negativo.")
    annualization = _positive_periods_per_year(periods_per_year)
    tail_size = _positive_int(worst_periods, "worst_periods")
    if tail_size > risky.size:
        raise ValueError("worst_periods não pode exceder o tamanho da amostra.")
    cost_rate = bps / 10_000.0

    true_returns = _returns_with_derisk(risky, cash, derisk, cost_rate)
    true_metrics = pd.Series(
        _performance_metrics(true_returns, cash, annualization, tail_size),
        index=METRICS,
        name="true_signal",
        dtype=float,
    )
    true_metrics.index.name = "metric"

    rows: list[dict[str, float]] = []
    for shift in range(1, risky.size):
        shifted_derisk = np.roll(derisk, shift)
        shifted_returns = _returns_with_derisk(risky, cash, shifted_derisk, cost_rate)
        row = _performance_metrics(shifted_returns, cash, annualization, tail_size)
        row["shift"] = shift
        rows.append(row)

    placebo_metrics = pd.DataFrame(rows).set_index("shift").loc[:, METRICS]
    placebo_metrics.index = placebo_metrics.index.astype(int)
    placebo_metrics.index.name = "shift"
    percentiles = pd.Series(
        {
            metric: _midrank_percentile(float(true_metrics[metric]), placebo_metrics[metric])
            for metric in METRICS
        },
        name="percentile",
        dtype=float,
    )
    percentiles.index.name = "metric"

    return CircularShiftPlaceboResult(
        true_metrics=true_metrics,
        placebo_metrics=placebo_metrics,
        percentiles=percentiles,
        cost_bps=bps,
        periods_per_year=annualization,
        worst_periods=tail_size,
    )


__all__ = [
    "BootstrapMeanResult",
    "CircularShiftPlaceboResult",
    "circular_shift_placebo_test",
    "deflated_sharpe_ratio",
    "expected_maximum_sharpe_ratio",
    "moving_block_bootstrap_mean",
    "probabilistic_sharpe_ratio",
]
