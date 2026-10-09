"""Sinais fixos, ranking transparente e teste cronológico sem otimização."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.momentum_atr import average_true_range


def features(frame: pd.DataFrame, benchmark: pd.DataFrame, config: dict) -> pd.DataFrame:
    close = frame["close"]
    out = pd.DataFrame(index=frame.index)
    for days in (5, 20, 60):
        out[f"return_{days}d"] = close.pct_change(days, fill_method=None)
    out["ma20"] = close.rolling(20).mean()
    out["ma50"] = close.rolling(50).mean()
    out["atr"] = average_true_range(frame, 14)
    out["atr_pct"] = out["atr"] / close
    out["volatility_20d"] = close.pct_change(fill_method=None).rolling(20).std(ddof=1) * np.sqrt(252)
    out["adv_usd"] = (frame["raw_close"] * frame["volume"]).rolling(20).mean()
    out["relative_20d"] = out["return_20d"] - benchmark["close"].pct_change(20, fill_method=None).reindex(frame.index)
    out["drawdown_60d"] = close / close.rolling(60).max() - 1
    market_trend = benchmark["close"] > benchmark["close"].rolling(50).mean()
    out["market_trend"] = market_trend.reindex(frame.index).fillna(False)
    # SPY é comparador e também pode ser negociado sem exigir superar a si mesmo.
    relative_ok = out["relative_20d"].ge(0) if frame.attrs.get("ticker") == config["benchmark"] else out["relative_20d"].gt(0)
    out["signal"] = ((close > out["ma20"]) & (out["ma20"] > out["ma50"])
                     & (out["return_20d"] > 0) & relative_ok & out["market_trend"]
                     & ((close - out["ma20"]) <= 3 * out["atr"])
                     & (out["adv_usd"] >= config["min_dollar_volume"]))
    return out


def metrics(equity: pd.Series, trades: list[dict]) -> dict:
    # equity inclui ponto inicial 1.0: o primeiro custo nunca é omitido.
    returns = equity.pct_change(fill_method=None).dropna()
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {"return": float(equity.iloc[-1] - 1),
            "sharpe": float(returns.mean() / std * np.sqrt(252)) if std > 0 else None,
            "drawdown": float((equity / equity.cummax() - 1).min()),
            "trades": len(trades),
            "win_rate": float(np.mean([t["return"] > 0 for t in trades])) if trades else None}


def simulate(frame: pd.DataFrame, signals: pd.DataFrame, start: pd.Timestamp, config: dict,
             cost: float | None = None) -> tuple[dict, pd.Series, list[dict]]:
    """Long-only 100% nocional, cash zero, no máx. holding_days sessões.

    Decisão close[t] -> open[t+1]. Stop existente avaliado antes de ratchet
    conhecido somente em close[t]. Gap preenche no open, custo por ponta.
    OOS começa zerado e não usa sinal anterior à sua primeira sessão.
    Última posição é liquidada no close para incluir seu custo de saída.
    """
    fee = config["cost_per_side"] if cost is None else cost
    locs = np.flatnonzero(frame.index >= start)
    if len(locs) < 2:
        raise ValueError("janela de teste insuficiente")
    first = int(locs[0])
    cash, units, stop, holding = 1.0, 0.0, 0.0, 0
    entry_value, entry_date = 0.0, None
    values, trades = [1.0], []
    for i in locs:
        row, feature = frame.iloc[i], signals.iloc[i]
        previous = signals.iloc[i - 1] if i > 0 else None
        exited = False

        def sell(price: float, reason: str) -> None:
            nonlocal cash, units, exited
            cash = units * price * (1 - fee)
            trades.append({"entry_date": str(entry_date.date()), "exit_date": str(frame.index[i].date()),
                           "return": cash / entry_value - 1, "exit_reason": reason})
            units, exited = 0.0, True

        if units > 0 and (holding >= config["holding_days"] or frame.iloc[i-1]["close"] < previous["ma20"]):
            sell(float(row["open"]), "tempo/tendência")
        if units == 0 and not exited and i > first and bool(previous["signal"]):
            entry_value, entry_date = cash, frame.index[i]
            units, cash = cash / (float(row["open"]) * (1 + fee)), 0.0
            stop = float(row["open"] - config["stop_atr"] * previous["atr"])
            holding = 0
        if units > 0:
            if row["open"] <= stop:
                sell(float(row["open"]), "gap stop")
            elif row["low"] <= stop:
                sell(float(stop), "stop")
        if units > 0:
            holding += 1
            stop = max(stop, float(row["close"] - config["stop_atr"] * feature["atr"]))
            if i == locs[-1]:
                sell(float(row["close"]), "fim da amostra")
        values.append(cash + units * float(row["close"]))
    curve = pd.Series(values, index=[frame.index[first] - pd.Timedelta(nanoseconds=1), *frame.index[locs]], name="equity")
    return metrics(curve, trades), curve, trades


def buy_hold(frame: pd.DataFrame, start: pd.Timestamp, cost: float) -> float:
    window = frame.loc[start:]
    return float(window["close"].iloc[-1] / window["open"].iloc[0] * (1 - cost) / (1 + cost) - 1)


def analyze(frames: dict[str, pd.DataFrame], config: dict, as_of: str) -> tuple[list[dict], list[dict], dict]:
    benchmark_ticker = config["benchmark"]
    if benchmark_ticker not in frames:
        raise ValueError("SPY/benchmark ausente: comparação indisponível; nenhuma classificação emitida")
    exclusions, usable = [], {}
    for ticker, frame in frames.items():
        stale = int(np.busday_count(frame.index[-1].date(), pd.Timestamp(as_of).date()))
        reason = None
        if len(frame) < config["min_history"]:
            reason = "histórico abaixo do mínimo"
        elif stale > config["max_stale_business_days"]:
            reason = f"dados defasados: {stale} dias úteis aproximados"
        if reason:
            exclusions.append({"ticker": ticker, "reason": reason})
        else:
            usable[ticker] = frame
    if benchmark_ticker not in usable:
        raise ValueError("benchmark defasado/insuficiente; atualize o snapshot")
    benchmark = usable[benchmark_ticker]
    # Um corte e calendário comuns impedem comparar datas e regimes diferentes.
    common_start = max(frame.index[0] for frame in usable.values())
    dates = benchmark.index[benchmark.index >= common_start]
    if len(dates) < config["min_history"]:
        raise ValueError("janela comum abaixo do mínimo")
    oos_start = dates[int(len(dates) * .7)]
    benchmark = benchmark.loc[dates]
    rows, returns = [], {}
    assets = {asset["ticker"]: asset for asset in config["assets"]}
    for ticker, original in usable.items():
        if not dates.isin(original.index).all() or original.index[-1] != dates[-1]:
            exclusions.append({"ticker": ticker, "reason": "lacuna ou fechamento desalinhado do benchmark"})
            continue
        frame = original.loc[dates].copy()
        frame.attrs["ticker"] = ticker
        feat = features(frame, benchmark, config)
        last, price = feat.iloc[-1], float(frame["close"].iloc[-1])
        reasons = []
        for condition, reason in [
            (price > last["ma20"], "fechamento abaixo da média de 20 pregões"),
            (last["ma20"] > last["ma50"], "média 20 abaixo da média 50"),
            (last["return_20d"] > 0, "momentum de 20 pregões não positivo"),
            (last["relative_20d"] > 0 or ticker == benchmark_ticker, "não supera o SPY em 20 pregões"),
            (price - last["ma20"] <= 3 * last["atr"], "preço esticado acima de 3 ATR da média 20"),
            (last["adv_usd"] >= config["min_dollar_volume"], "liquidez abaixo do mínimo"),
            (bool(last["market_trend"]), "SPY abaixo da média de 50 pregões")]:
            if not condition:
                reasons.append(reason)
        test, curve, trades = simulate(frame, feat, oos_start, config)
        stress, _, _ = simulate(frame, feat, oos_start, config, config["stress_cost_per_side"])
        stop_fraction = config["stop_atr"] * float(last["atr_pct"])
        if not np.isfinite(stop_fraction) or stop_fraction <= 0:
            reasons.append("ATR nulo/indisponível: tamanho de posição não estimável")
        row = dict(assets[ticker], as_of=str(dates[-1].date()), last_close=float(frame["raw_close"].iloc[-1]),
                   adjusted_close=price, status="observar" if reasons else "candidato", reasons=reasons,
                   stop_reference=(price - config["stop_atr"] * float(last["atr"])) / float(frame["adjustment_factor"].iloc[-1]),
                   weight_at_risk_budget=min(config["max_position_weight"], config["risk_budget"] / stop_fraction) if stop_fraction > 0 else None,
                   oos_start=str(oos_start.date()), oos_end=str(dates[-1].date()),
                   oos_buy_hold_return=buy_hold(frame, oos_start, config["cost_per_side"]),
                   oos_spy_return=buy_hold(benchmark, oos_start, config["cost_per_side"]),
                   cost_stress_return=stress["return"],
                   **{f"oos_{k}": v for k, v in test.items()})
        for key in ("return_5d", "return_20d", "return_60d", "relative_20d", "volatility_20d", "atr_pct", "adv_usd", "drawdown_60d"):
            row[key] = float(last[key])
        # Componentes dimensionais fixos; percentis transversais em [0,100].
        row["momentum20_risk"] = row["return_20d"] / max(row["volatility_20d"] * np.sqrt(20/252), 1e-9)
        row["momentum60_risk"] = row["return_60d"] / max(row["volatility_20d"] * np.sqrt(60/252), 1e-9)
        row["relative20_risk"] = row["relative_20d"] / max(row["volatility_20d"] * np.sqrt(20/252), 1e-9)
        rows.append(row)
        returns[ticker] = frame["close"].pct_change(fill_method=None).tail(60)
    ranked = pd.DataFrame(rows)
    if ranked.empty:
        raise ValueError("nenhum ativo elegível após validação")
    ranked["score"] = 0.0
    for column, weight in [("momentum20_risk", .35), ("momentum60_risk", .25), ("relative20_risk", .25), ("drawdown_60d", .15)]:
        ranked["score"] += ranked[column].rank(pct=True, method="average") * weight * 100
    ranked["_priority"] = ranked["status"].map({"candidato": 0, "observar": 1})
    ranked = ranked.sort_values(["_priority", "score", "ticker"], ascending=[True, False, True]).drop(columns="_priority")
    correlation = pd.DataFrame(returns).corr(min_periods=40).round(4).to_dict()
    return ranked.to_dict(orient="records"), exclusions, correlation
