"""Sinais causais da estratégia long-only de momentum com stop ATR.

Este módulo calcula informações disponíveis no fechamento de cada barra. Ele
não decide preços de execução; o motor orientado a eventos em ``backtest``
consome os sinais somente na abertura da barra seguinte.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


REQUIRED_OHLC_COLUMNS = ("open", "high", "low", "close")


@dataclass(frozen=True, slots=True)
class MomentumATRConfig:
    """Parâmetros imutáveis da formulação do sinal."""

    momentum_window: int = 20
    atr_window: int = 14
    stop_multiplier: float = 2.5
    momentum_threshold: float = 0.0

    def __post_init__(self) -> None:
        if self.momentum_window < 1:
            raise ValueError("momentum_window deve ser >= 1")
        if self.atr_window < 1:
            raise ValueError("atr_window deve ser >= 1")
        if not np.isfinite(self.stop_multiplier) or self.stop_multiplier <= 0:
            raise ValueError("stop_multiplier deve ser positivo e finito")
        if not np.isfinite(self.momentum_threshold):
            raise ValueError("momentum_threshold deve ser finito")


def validate_ohlc(data: pd.DataFrame) -> pd.DataFrame:
    """Valida e devolve uma cópia OHLC numérica, ordenada e sem ambiguidades.

    Ausências não são preenchidas automaticamente. Isso é intencional: preencher
    o histórico quebrado de um ativo suspenso ou deslistado fabricaria preços.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data deve ser um pandas.DataFrame")
    missing = [column for column in REQUIRED_OHLC_COLUMNS if column not in data]
    if missing:
        raise ValueError(f"colunas OHLC ausentes: {', '.join(missing)}")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("o índice OHLC deve ser um pandas.DatetimeIndex")
    if data.index.has_duplicates:
        raise ValueError("o índice OHLC não pode conter timestamps duplicados")
    if not data.index.is_monotonic_increasing:
        raise ValueError("o índice OHLC deve estar em ordem crescente")
    if data.empty:
        raise ValueError("a série OHLC está vazia")

    result = data.copy()
    for column in REQUIRED_OHLC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    values = result.loc[:, REQUIRED_OHLC_COLUMNS]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("OHLC contém valor ausente ou não finito")
    if (values <= 0).any(axis=None):
        raise ValueError("preços OHLC devem ser estritamente positivos")
    if (result["high"] < result[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("high deve ser maior ou igual a open, close e low")
    if (result["low"] > result[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("low deve ser menor ou igual a open, close e high")
    return result


def true_range(data: pd.DataFrame) -> pd.Series:
    """Calcula True Range sem usar informação futura."""

    frame = validate_ohlc(data)
    previous_close = frame["close"].shift(1)
    ranges = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    result = ranges.max(axis=1)
    result.name = "true_range"
    return result


def average_true_range(data: pd.DataFrame, window: int = 14) -> pd.Series:
    """ATR por média móvel simples, equivalente a ``ta.sma(TR, window)``.

    A janela precisa estar completa. O comportamento evita que os primeiros
    candles recebam uma estimativa de volatilidade artificialmente curta.
    """

    if window < 1:
        raise ValueError("window deve ser >= 1")
    result = true_range(data).rolling(window=window, min_periods=window).mean()
    result.name = "atr"
    return result


def build_momentum_atr_signals(
    data: pd.DataFrame,
    config: MomentumATRConfig | None = None,
) -> pd.DataFrame:
    """Produz momentum, ATR e decisões confirmadas no fechamento da barra.

    ``entry_signal`` marca apenas o cruzamento de baixo para cima do limiar. A
    saída de momentum permanece verdadeira enquanto o fator estiver abaixo do
    limiar, mas o motor a considera apenas quando existe posição.
    """

    strategy = config or MomentumATRConfig()
    frame = validate_ohlc(data)
    momentum = frame["close"].div(frame["close"].shift(strategy.momentum_window)).sub(1.0)
    atr = average_true_range(frame, strategy.atr_window)
    previous_momentum = momentum.shift(1)
    entry = (
        momentum.gt(strategy.momentum_threshold)
        & previous_momentum.le(strategy.momentum_threshold)
        & atr.notna()
    )
    exit_signal = momentum.lt(strategy.momentum_threshold) & momentum.notna()

    return pd.DataFrame(
        {
            "momentum": momentum,
            "atr": atr,
            "entry_signal": entry.astype(bool),
            "exit_signal": exit_signal.astype(bool),
        },
        index=frame.index,
    )
