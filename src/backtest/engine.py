"""Motor orientado a eventos para simulação, sem qualquer rota de trading real."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from strategies.momentum_atr import (
    MomentumATRConfig,
    build_momentum_atr_signals,
    validate_ohlc,
)


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Premissas de execução exclusivamente simulada.

    ``cost_per_side`` representa a fricção consolidada aplicada tanto na
    compra quanto na venda. ``stop_slippage`` é uma penalidade adicional no
    preço de preenchimento de stops e pode ser elevada nos testes de estresse.
    """

    initial_capital: float = 1.0
    cost_per_side: float = 0.0015
    stop_slippage: float = 0.0
    annual_risk_free_rate: float = 0.0
    trading_days_per_year: int = 252
    liquidate_at_end: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite(self.initial_capital) or self.initial_capital <= 0:
            raise ValueError("initial_capital deve ser positivo e finito")
        if not 0 <= self.cost_per_side < 1:
            raise ValueError("cost_per_side deve estar em [0, 1)")
        if not 0 <= self.stop_slippage < 1:
            raise ValueError("stop_slippage deve estar em [0, 1)")
        if self.annual_risk_free_rate <= -1 or not np.isfinite(self.annual_risk_free_rate):
            raise ValueError("annual_risk_free_rate deve ser finita e maior que -1")
        if self.trading_days_per_year < 1:
            raise ValueError("trading_days_per_year deve ser >= 1")


@dataclass(slots=True)
class BacktestResult:
    """Artefatos completos de uma simulação auditável."""

    equity_curve: pd.DataFrame
    orders: pd.DataFrame
    trades: pd.DataFrame
    signals: pd.DataFrame
    metrics: dict[str, float | int]
    strategy_config: dict[str, Any]
    execution_config: dict[str, Any]


ORDER_COLUMNS = (
    "signal_time",
    "fill_time",
    "side",
    "reason",
    "signal_price",
    "fill_price",
    "quantity",
    "transaction_cost",
    "stop_price",
)

TRADE_COLUMNS = (
    "entry_signal_time",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "quantity",
    "entry_cost",
    "exit_cost",
    "net_return",
    "holding_bars",
    "exit_reason",
)


def _resolve_boundary(index: pd.DatetimeIndex, value: Any, default: int, side: str) -> int:
    if value is None:
        return default
    timestamp = pd.Timestamp(value)
    return int(index.searchsorted(timestamp, side=side))


def _empty_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def calculate_performance_metrics(
    equity: pd.DataFrame,
    trades: pd.DataFrame,
    initial_capital: float,
    annual_risk_free_rate: float = 0.0,
    trading_days_per_year: int = 252,
) -> dict[str, float | int]:
    """Calcula métricas a partir da mesma contabilidade usada nas operações."""

    if equity.empty:
        raise ValueError("equity não pode estar vazia")
    returns = equity["daily_return"].astype(float)
    final_equity = float(equity["equity"].iloc[-1])
    total_return = final_equity / initial_capital - 1.0
    daily_rf = (1.0 + annual_risk_free_rate) ** (1.0 / trading_days_per_year) - 1.0
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return_skewness = float(returns.skew()) if len(returns) > 2 else 0.0
    return_kurtosis = float(returns.kurt() + 3.0) if len(returns) > 3 else 3.0
    if not np.isfinite(return_skewness):
        return_skewness = 0.0
    if not np.isfinite(return_kurtosis):
        return_kurtosis = 3.0
    mean_excess = float((returns - daily_rf).mean())
    sharpe = np.sqrt(trading_days_per_year) * mean_excess / volatility if volatility > 1e-15 else 0.0
    downside = np.minimum(returns.to_numpy(dtype=float) - daily_rf, 0.0)
    downside_deviation = float(np.sqrt(np.mean(np.square(downside))))
    sortino = (
        np.sqrt(trading_days_per_year) * mean_excess / downside_deviation
        if downside_deviation > 1e-15
        else 0.0
    )
    years = len(returns) / trading_days_per_year
    annualized_return = (final_equity / initial_capital) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    closed_trades = len(trades)
    if closed_trades:
        trade_returns = trades["net_return"].astype(float)
        win_rate = float(trade_returns.gt(0).mean())
        gross_profit = float(trade_returns.clip(lower=0).sum())
        gross_loss = float(-trade_returns.clip(upper=0).sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 1e-15 else (float("inf") if gross_profit else 0.0)
    else:
        win_rate = 0.0
        profit_factor = 0.0

    return {
        "bars": int(len(equity)),
        "total_trades": int(closed_trades),
        "win_rate": win_rate,
        "total_return": total_return,
        "annualized_return": float(annualized_return),
        "annualized_volatility": volatility * np.sqrt(trading_days_per_year),
        "return_skewness": return_skewness,
        "return_kurtosis": return_kurtosis,
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown": float(equity["drawdown"].min()),
        "profit_factor": float(profit_factor),
        "exposure": float(equity["position"].mean()),
        "final_equity": final_equity,
    }


def run_backtest(
    data: pd.DataFrame,
    strategy_config: MomentumATRConfig | None = None,
    execution_config: ExecutionConfig | None = None,
    *,
    trade_start: Any = None,
    trade_end: Any = None,
) -> BacktestResult:
    """Executa uma simulação causal long-only sobre candles OHLC.

    Ordem dos eventos de cada barra:

    1. o stop carregado é testado contra o ``open`` (gap);
    2. ordens de momentum decididas no fechamento anterior executam no ``open``;
    3. o stop é testado contra a mínima intradiária;
    4. somente no fechamento o stop sofre ratchet e vale a partir da próxima barra.

    Essa convenção não tenta adivinhar a sequência ``high/low`` dentro de um
    candle. Um stop nunca usa ATR, fechamento ou máxima ainda desconhecidos.
    """

    strategy = strategy_config or MomentumATRConfig()
    execution = execution_config or ExecutionConfig()
    frame = validate_ohlc(data)
    signals = build_momentum_atr_signals(frame, strategy)
    index = frame.index

    start = _resolve_boundary(index, trade_start, 0, "left")
    end_exclusive = _resolve_boundary(index, trade_end, len(index), "right")
    if start >= len(index) or end_exclusive <= start:
        raise ValueError("intervalo negociável não contém barras")
    end = min(end_exclusive, len(index)) - 1

    cash = float(execution.initial_capital)
    quantity = 0.0
    stop_price = np.nan
    entry_price = np.nan
    entry_cost = 0.0
    entry_capital = np.nan
    entry_time: pd.Timestamp | None = None
    entry_signal_time: pd.Timestamp | None = None
    entry_bar = -1
    orders: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    def close_position(
        *,
        bar_number: int,
        raw_fill_price: float,
        reason: str,
        signal_time: pd.Timestamp | None,
        signal_price: float | None,
        apply_stop_slippage: bool,
    ) -> None:
        nonlocal cash, quantity, stop_price
        fill_price = raw_fill_price * (1.0 - execution.stop_slippage) if apply_stop_slippage else raw_fill_price
        gross_proceeds = quantity * fill_price
        exit_cost = gross_proceeds * execution.cost_per_side
        cash = gross_proceeds - exit_cost
        orders.append(
            {
                "signal_time": signal_time,
                "fill_time": index[bar_number],
                "side": "SELL",
                "reason": reason,
                "signal_price": signal_price,
                "fill_price": fill_price,
                "quantity": quantity,
                "transaction_cost": exit_cost,
                "stop_price": float(stop_price) if np.isfinite(stop_price) else np.nan,
            }
        )
        trades.append(
            {
                "entry_signal_time": entry_signal_time,
                "entry_time": entry_time,
                "exit_time": index[bar_number],
                "entry_price": entry_price,
                "exit_price": fill_price,
                "quantity": quantity,
                "entry_cost": entry_cost,
                "exit_cost": exit_cost,
                "net_return": cash / entry_capital - 1.0,
                "holding_bars": bar_number - entry_bar + 1,
                "exit_reason": reason,
            }
        )
        quantity = 0.0
        stop_price = np.nan

    previous_equity = float(execution.initial_capital)
    for i in range(start, end + 1):
        bar = frame.iloc[i]
        prior_signal_i = i - 1
        exited_this_bar = False

        # Stops que já existiam antes da abertura têm precedência em gaps.
        if quantity > 0 and float(bar["open"]) <= stop_price:
            close_position(
                bar_number=i,
                raw_fill_price=float(bar["open"]),
                reason="gap_stop",
                signal_time=None,
                signal_price=float(stop_price),
                apply_stop_slippage=True,
            )
            exited_this_bar = True

        # Sinal formado no close t-1; o primeiro preço executável é open t.
        if quantity > 0 and not exited_this_bar and prior_signal_i >= 0 and bool(signals["exit_signal"].iloc[prior_signal_i]):
            close_position(
                bar_number=i,
                raw_fill_price=float(bar["open"]),
                reason="momentum_exit",
                signal_time=index[prior_signal_i],
                signal_price=float(frame["close"].iloc[prior_signal_i]),
                apply_stop_slippage=False,
            )
            exited_this_bar = True

        if quantity == 0 and not exited_this_bar and prior_signal_i >= 0 and bool(signals["entry_signal"].iloc[prior_signal_i]):
            signal_atr = float(signals["atr"].iloc[prior_signal_i])
            if np.isfinite(signal_atr):
                fill_price = float(bar["open"])
                entry_capital = cash
                quantity = cash / (fill_price * (1.0 + execution.cost_per_side))
                notional = quantity * fill_price
                entry_cost = notional * execution.cost_per_side
                cash = 0.0
                entry_price = fill_price
                entry_time = index[i]
                entry_signal_time = index[prior_signal_i]
                entry_bar = i
                stop_price = fill_price - strategy.stop_multiplier * signal_atr
                orders.append(
                    {
                        "signal_time": entry_signal_time,
                        "fill_time": entry_time,
                        "side": "BUY",
                        "reason": "momentum_cross",
                        "signal_price": float(frame["close"].iloc[prior_signal_i]),
                        "fill_price": fill_price,
                        "quantity": quantity,
                        "transaction_cost": entry_cost,
                        "stop_price": stop_price,
                    }
                )

        # Um stop inicial colocado junto da compra também protege a barra de entrada.
        if quantity > 0 and float(bar["low"]) <= stop_price:
            close_position(
                bar_number=i,
                raw_fill_price=float(stop_price),
                reason="intraday_stop",
                signal_time=None,
                signal_price=float(stop_price),
                apply_stop_slippage=True,
            )
            exited_this_bar = True

        # O candle atual só altera o stop depois de sobreviver integralmente a ele.
        if quantity > 0:
            current_atr = float(signals["atr"].iloc[i])
            if np.isfinite(current_atr):
                close_based_stop = float(bar["close"]) - strategy.stop_multiplier * current_atr
                stop_price = max(float(stop_price), close_based_stop)

        if i == end and quantity > 0 and execution.liquidate_at_end:
            close_position(
                bar_number=i,
                raw_fill_price=float(bar["close"]),
                reason="end_of_data",
                signal_time=index[i],
                signal_price=float(bar["close"]),
                apply_stop_slippage=False,
            )

        equity_value = cash if quantity == 0 else quantity * float(bar["close"])
        daily_return = equity_value / previous_equity - 1.0
        curve_rows.append(
            {
                "timestamp": index[i],
                "equity": equity_value,
                "daily_return": daily_return,
                "position": int(quantity > 0),
                "stop_price": float(stop_price) if quantity > 0 else np.nan,
            }
        )
        previous_equity = equity_value

    equity_curve = pd.DataFrame(curve_rows).set_index("timestamp")
    running_peak = equity_curve["equity"].cummax().clip(lower=execution.initial_capital)
    equity_curve["drawdown"] = equity_curve["equity"].div(running_peak).sub(1.0)
    order_frame = pd.DataFrame(orders, columns=list(ORDER_COLUMNS)) if orders else _empty_frame(ORDER_COLUMNS)
    trade_frame = pd.DataFrame(trades, columns=list(TRADE_COLUMNS)) if trades else _empty_frame(TRADE_COLUMNS)
    metrics = calculate_performance_metrics(
        equity_curve,
        trade_frame,
        execution.initial_capital,
        execution.annual_risk_free_rate,
        execution.trading_days_per_year,
    )
    return BacktestResult(
        equity_curve=equity_curve,
        orders=order_frame,
        trades=trade_frame,
        signals=signals,
        metrics=metrics,
        strategy_config=asdict(strategy),
        execution_config=asdict(execution),
    )
