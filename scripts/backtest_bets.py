"""Blueprint de pesquisa B3/bets: causal, long-only, sem conexao com corretora.

CSV e parametros sao contratos de pesquisa; nenhum resultado sintetico e alpha.
Veja results/bets_research/README_BACKTEST.md. Usa pandas/numpy e replay vectorbt.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    capital: float = 1_000_000.0
    cost: float = 0.0015
    stop_slippage: float = 0.001
    atr_multiple: float = 2.5
    max_names: int = 6
    name_cap: float = 0.15
    sector_cap: float = 0.35
    gross_cap: float = 0.80
    target_vol: float = 0.12
    trade_risk: float = 0.005
    adv_min: float = 20_000_000.0
    participation: float = 0.01
    beta_min: float = 0.7
    beta_max: float = 1.8
    feature_max_age_days: int = 14


def align_features(dates, features, exploratory=False):
    """Apenas snapshots publicados ate 18h America/Sao_Paulo de cada sessao."""
    required = {"available_at", "search_relief_z", "regulation_score", "vintage_id"}
    if not required.issubset(features):
        raise ValueError(f"Features requerem {sorted(required)}")
    if not exploratory:
        raise ValueError("Use --exploratory: este blueprint nao certifica vintages nem universo PIT.")
    f = features.copy()
    if not all(pd.Timestamp(x).tzinfo is not None for x in f.available_at):
        raise ValueError("available_at exige timezone explicito")
    f["available_at"] = pd.to_datetime(f.available_at, utc=True)
    if f.available_at.duplicated().any():
        raise ValueError("Um snapshot completo por available_at; consolide duplicatas antes.")
    for col in ("search_relief_z", "regulation_score"):
        f[col] = pd.to_numeric(f[col], errors="raise")
    if not np.isfinite(f[["search_relief_z", "regulation_score"]]).all().all():
        raise ValueError("Features nao finitas")
    if not f.regulation_score.between(-1, 1).all() or f.vintage_id.isna().any():
        raise ValueError("regulation_score fora de [-1,1] ou vintage_id ausente")
    idx = pd.DatetimeIndex(dates)
    cutoffs = (idx + pd.Timedelta(hours=18)).tz_localize("America/Sao_Paulo").tz_convert("UTC")
    out = pd.merge_asof(pd.DataFrame({"cutoff": cutoffs}), f.sort_values("available_at"),
                        left_on="cutoff", right_on="available_at", direction="backward")
    out.index = idx
    out["age_days"] = (out.cutoff - out.available_at).dt.total_seconds() / 86400
    return out


def prepare(prices, benchmark):
    required = {"date", "ticker", "sector", "open", "high", "low", "close", "raw_close", "volume", "eligible"}
    if not required.issubset(prices):
        raise ValueError(f"Precos requerem {sorted(required)}")
    p, b = prices.copy(), benchmark.copy()
    p["date"] = pd.to_datetime(p.date).dt.normalize()
    b["date"] = pd.to_datetime(b.date).dt.normalize()
    if p.duplicated(["date", "ticker"]).any() or b.date.duplicated().any():
        raise ValueError("Datas/tickers duplicados")
    if not {"ibov", "cdi_return"}.issubset(b):
        raise ValueError("Benchmark requer date,ibov,cdi_return")
    b = b.set_index("date").sort_index()
    if len(b) < 2 or not p.date.isin(b.index).all():
        raise ValueError("Calendario do benchmark deve cobrir todos os precos")
    if not np.isfinite(b[["ibov", "cdi_return"]]).all().all() or (b.ibov <= 0).any() or (b.cdi_return <= -1).any():
        raise ValueError("Benchmark invalido")
    values = p[["open", "high", "low", "close", "raw_close", "volume"]]
    if not np.isfinite(values).all().all() or (values.drop(columns="volume") <= 0).any().any() or (p.volume < 0).any():
        raise ValueError("Precos/volume invalidos; nao preencher suspensoes")
    if (p.high < p[["open", "close", "low"]].max(axis=1)).any() or (p.low > p[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC incoerente")
    if not p.eligible.isin([0, 1, False, True]).all() or p.sector.isna().any():
        raise ValueError("eligible deve ser 0/1 e sector preenchido")
    panels = {c: p.pivot(index="date", columns="ticker", values=c).reindex(b.index)
              for c in ["open", "high", "low", "close", "raw_close", "volume", "eligible", "sector"]}
    c = panels["close"]
    r = c.pct_change(fill_method=None)
    market = b.ibov.pct_change(fill_method=None)
    tr = pd.DataFrame(np.maximum.reduce([(panels["high"]-panels["low"]).to_numpy(),
                         (panels["high"]-c.shift()).abs().to_numpy(),
                         (panels["low"]-c.shift()).abs().to_numpy()]), index=c.index, columns=c.columns)
    panels.update({"returns": r, "atr": tr.rolling(14).mean(), "mom20": c/c.shift(20)-1,
                   "mom12_1": c.shift(21)/c.shift(252)-1, "sma200": c.rolling(200).mean(),
                   "sma100": c.rolling(100).mean(), "vol60": r.rolling(60).std()*np.sqrt(252),
                   "adv60": (panels["raw_close"]*panels["volume"]).rolling(60).mean(),
                   "beta": r.rolling(252, min_periods=126).cov(market).div(
                       market.rolling(252, min_periods=126).var(), axis=0)})
    return panels, b


def targets(panel, pos, cfg):
    """Pesos no fechamento; caps reduzem exposicao, sem redistribuir sobras."""
    row = {k: v.iloc[pos] for k, v in panel.items() if k != "returns"}
    ok = ((row["eligible"] == 1) & (row["adv60"] >= cfg.adv_min)
          & row["beta"].between(cfg.beta_min, cfg.beta_max) & (row["mom20"] > 0)
          & (row["mom12_1"] > 0) & (row["close"] > row["sma200"])
          & (row["vol60"] > 0) & (row["atr"] > 0))
    score = (row["mom12_1"]/row["vol60"]).where(ok).dropna()
    selected = score.sort_values(ascending=False, kind="stable").head(cfg.max_names).index
    w = pd.Series(0.0, index=row["close"].index)
    if not len(selected):
        return w
    inverse = 1/row["vol60"][selected]
    w.loc[selected] = cfg.gross_cap*inverse/inverse.sum()
    risk_cap = cfg.trade_risk/(cfg.atr_multiple*row["atr"]/row["close"])
    w = pd.concat([w, risk_cap.rename("risk")], axis=1).min(axis=1).clip(upper=cfg.name_cap)
    w.loc[~w.index.isin(selected)] = 0
    for sector in row["sector"][selected].unique():
        names = row["sector"].index[row["sector"] == sector]
        total = w[names].sum()
        if total > cfg.sector_cap:
            w.loc[names] *= cfg.sector_cap/total
    history = panel["returns"].iloc[max(0, pos-59):pos+1][selected]
    covariance = history.cov().to_numpy()*252
    if not np.isfinite(covariance).all():
        return w*0
    vol = np.sqrt(max(0, w[selected].to_numpy() @ covariance @ w[selected].to_numpy()))
    if vol > cfg.target_vol:
        w *= cfg.target_vol/vol
    if w.sum() > cfg.gross_cap:
        w *= cfg.gross_cap/w.sum()
    return w


def metrics(curve):
    r = curve.nav.pct_change().fillna(0)
    rf = curve.cdi_return.copy()
    rf.iloc[0] = 0
    excess = r-rf
    downside = np.sqrt(np.mean(np.minimum(excess, 0)**2))
    std = excess.std(ddof=1)
    dd = curve.nav/curve.nav.cummax()-1
    years = (len(curve)-1)/252
    return {"total_return": float(curve.nav.iloc[-1]/curve.nav.iloc[0]-1),
            "cagr": float((curve.nav.iloc[-1]/curve.nav.iloc[0])**(1/years)-1),
            "sharpe_cdi": float(np.sqrt(252)*excess.mean()/std) if std > 1e-12 else None,
            "sortino_cdi": float(np.sqrt(252)*excess.mean()/downside) if downside > 1e-12 else None,
            "max_drawdown": float(dd.min()), "costs": float(curve.costs.sum())}


def run_backtest(prices, benchmark, features, cfg=None, *, exploratory=False, gate_mode="combined"):
    cfg = cfg or Config()
    if gate_mode not in {"combined", "price_only", "search_only", "regulation_only"}:
        raise ValueError("gate_mode invalido")
    p, b = prepare(prices, benchmark)
    f = align_features(b.index, features, exploratory)
    fresh = f.age_days.le(cfg.feature_max_age_days) & f.age_days.ge(0)
    if gate_mode == "price_only":
        gate = pd.Series(True, index=b.index)
    elif gate_mode == "search_only":
        gate = fresh & f.search_relief_z.gt(0)
    elif gate_mode == "regulation_only":
        gate = fresh & f.regulation_score.gt(0)
    else:
        gate = fresh & f.search_relief_z.gt(0) & f.regulation_score.gt(0)
    names = p["close"].columns
    qty = pd.Series(0.0, index=names)
    stops = pd.Series(np.nan, index=names)
    cash = cfg.capital
    records, orders = [], []
    day_cost = 0.0

    def trade(day, ticker, amount, price, reason, signal_date, stage):
        nonlocal cash, day_cost
        fee = abs(amount)*price*cfg.cost
        cash -= amount*price+fee
        qty.loc[ticker] += amount
        if abs(qty[ticker]) < 1e-9:
            qty.loc[ticker] = 0
            stops.loc[ticker] = np.nan
        day_cost += fee
        orders.append({"date": day, "ticker": ticker, "amount": amount, "price": price,
                       "fee": fee, "reason": reason, "signal_date": signal_date, "stage": stage})

    for i, day in enumerate(b.index):
        day_cost = 0.0
        if i:
            cash *= 1+b.cdi_return.iloc[i]
        opened, closed = p["open"].iloc[i], p["close"].iloc[i]
        held = qty.index[qty > 0]
        if opened[held].isna().any() or closed[held].isna().any():
            raise ValueError(f"Posicao sem cotacao em {day.date()}; tratar suspensao/delistagem explicitamente")
        exited = set()
        if i:
            yesterday = b.index[i-1]
            for ticker in list(held):
                if opened[ticker] <= stops[ticker]:
                    trade(day, ticker, -qty[ticker], opened[ticker]*(1-cfg.stop_slippage), "gap_stop", yesterday, "open")
                    exited.add(ticker)
                elif (not gate.iloc[i-1] or p["eligible"].iloc[i-1][ticker] != 1
                      or p["mom20"].iloc[i-1][ticker] <= 0
                      or p["close"].iloc[i-1][ticker] < p["sma100"].iloc[i-1][ticker]):
                    trade(day, ticker, -qty[ticker], opened[ticker], "signal_exit", yesterday, "open")
                    exited.add(ticker)
            weekly = day.to_period("W-SUN") != yesterday.to_period("W-SUN")
            if weekly and gate.iloc[i-1]:
                w = targets(p, i-1, cfg)
                nav_open = cash+(qty*opened).sum()
                desired = (w*nav_open/opened).fillna(0)
                # Revalidar o risco no preco de abertura; gap altera o notional.
                risk_quantity = cfg.trade_risk*nav_open/(cfg.atr_multiple*p["atr"].iloc[i-1])
                desired = pd.concat([desired, risk_quantity], axis=1).min(axis=1)
                desired.loc[w <= 0] = 0
                for ticker in exited:
                    desired.loc[ticker] = 0
                delta = desired-qty
                capacity = cfg.participation*p["adv60"].iloc[i-1]/opened
                for ticker in delta.index[delta < -1e-9]:
                    amount = -min(-delta[ticker], capacity[ticker])
                    if np.isfinite(amount) and amount < 0:
                        trade(day, ticker, amount, opened[ticker], "rebalance", yesterday, "open")
                for ticker in delta.index[delta > 1e-9]:
                    amount = min(delta[ticker], capacity[ticker], cash/(opened[ticker]*(1+cfg.cost)))
                    if np.isfinite(amount) and amount > 1e-9:
                        new = qty[ticker] == 0
                        trade(day, ticker, amount, opened[ticker], "rebalance", yesterday, "open")
                        candidate = opened[ticker]-cfg.atr_multiple*p["atr"].iloc[i-1][ticker]
                        stops.loc[ticker] = candidate if new else max(stops[ticker], candidate)
        for ticker in qty.index[qty > 0].tolist():
            if p["low"].iloc[i][ticker] <= stops[ticker]:
                trade(day, ticker, -qty[ticker], stops[ticker]*(1-cfg.stop_slippage), "intraday_stop", b.index[max(0,i-1)], "intraday")
            else:
                candidate = closed[ticker]-cfg.atr_multiple*p["atr"].iloc[i][ticker]
                if np.isfinite(candidate):
                    stops.loc[ticker] = max(stops[ticker], candidate)
        nav = cash+(qty*closed).sum()
        records.append({"date": day, "nav": nav, "cash": cash, "gross": (qty*closed).sum()/nav,
                        "costs": day_cost, "cdi_return": b.cdi_return.iloc[i], "gate": bool(gate.iloc[i])})
        if cash < -1e-7:
            raise AssertionError("Saldo negativo no caixa compartilhado")
    curve = pd.DataFrame(records).set_index("date")
    ledger = pd.DataFrame(orders, columns=["date","ticker","amount","price","fee","reason","signal_date","stage"])
    return {"curve": curve, "orders": ledger, "features": f, "metrics": metrics(curve),
            "config": asdict(cfg), "gate_mode": gate_mode, "classification": "exploratory_not_causal_evidence"}


def vectorbt_replay(result, prices, benchmark):
    """Replay concreto do ledger com Portfolio.from_orders em numeraire CDI.

    Linha por ordem + marcacao diaria: preserva ordem de vendas/compras/stops.
    CDI remunera o caixa ao dividir precos pelo indice CDI. Valor final volta a BRL.
    Nao e um segundo gerador de sinais e nao certifica os dados de entrada.
    """
    import vectorbt as vbt

    p, b = prepare(prices, benchmark)
    rf = b.cdi_return.copy()
    rf.iloc[0] = 0
    numeraire = (1+rf).cumprod()
    marks, sizes, fills, daily_rows = [], [], [], []
    current = pd.Series(1.0, index=p["close"].columns)
    for day in b.index:
        current = p["open"].loc[day].combine_first(current)
        for order in result["orders"].loc[result["orders"].date.eq(day)].itertuples():
            row = pd.Series(0.0, index=current.index)
            row.loc[order.ticker] = order.amount
            prices_row = current/numeraire.loc[day]
            prices_row.loc[order.ticker] = order.price/numeraire.loc[day]
            marks.append((current/numeraire.loc[day]).to_numpy())
            sizes.append(row.to_numpy())
            fills.append(prices_row.to_numpy())
        current = p["close"].loc[day].combine_first(current)
        marks.append((current/numeraire.loc[day]).to_numpy())
        sizes.append(np.zeros(len(current)))
        fills.append((current/numeraire.loc[day]).to_numpy())
        daily_rows.append(len(marks)-1)
    portfolio = vbt.Portfolio.from_orders(
        pd.DataFrame(marks, columns=current.index), size=np.asarray(sizes), price=np.asarray(fills),
        size_type="amount", direction="longonly", init_cash=result["config"]["capital"],
        fees=result["config"]["cost"], cash_sharing=True, group_by=True,
        # Pequenas diferenças de ponto flutuante entre quantidades vendidas pelo
        # livro pandas e a posição interna do vectorbt não devem transformar uma
        # liquidação válida em ordem rejeitada. O replay é conferido contra a
        # curva original logo abaixo; uma divergência deixa o comando falhar.
        allow_partial=True, raise_reject=False, freq="1D")
    value = np.asarray(portfolio.value()).reshape(-1)[daily_rows]*numeraire.to_numpy()
    return pd.Series(value, index=b.index, name="vectorbt_nav")


def demo_inputs(seed=7):
    """Dados inteiramente artificiais para testar software; nunca evidencia economica."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=520)
    market = rng.normal(0.0009, 0.008, len(dates))
    benchmark = pd.DataFrame({"date": dates, "ibov": 100000*np.cumprod(1+market), "cdi_return": 0.00035})
    frames = []
    for j in range(8):
        ret = market*(0.8+0.1*j)+rng.normal(0.0002,0.004,len(dates))
        close = 30*np.cumprod(1+ret)
        opened = np.r_[close[0],close[:-1]]*(1+rng.normal(0,0.001,len(dates)))
        frames.append(pd.DataFrame({"date": dates,"ticker": f"SYNTH{j}","sector": f"SETOR{j%3}",
                       "open": opened,"high": np.maximum(opened,close)*1.006,
                       "low": np.minimum(opened,close)*0.994,"close": close,"raw_close":close,
                       "volume": 3_000_000,"eligible":1}))
    snapshots = dates[::5]
    features = pd.DataFrame({"available_at": [x.tz_localize("America/Sao_Paulo").isoformat() for x in snapshots],
                            "search_relief_z":1.0,"regulation_score":1.0,"vintage_id":"SYNTHETIC"})
    return pd.concat(frames,ignore_index=True), benchmark, features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--exploratory", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--vectorbt-replay", action="store_true")
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("results/bets_research/run"))
    args = parser.parse_args()
    if args.demo:
        prices, benchmark, features = demo_inputs()
    else:
        if not all([args.prices,args.benchmark,args.features]):
            parser.error("Forneca --prices --benchmark --features ou --demo")
        prices,benchmark,features = [pd.read_csv(x) for x in (args.prices,args.benchmark,args.features)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    modes = ["combined","price_only","search_only","regulation_only"] if args.ablations else ["combined"]
    summaries = {}
    for mode in modes:
        result = run_backtest(prices,benchmark,features,exploratory=args.exploratory or args.demo,gate_mode=mode)
        for key in ("curve","orders","features"):
            result[key].to_csv(args.output_dir/f"{mode}_{key}.csv", index=key != "orders")
        summaries[mode] = result["metrics"]
        if args.vectorbt_replay:
            replay = vectorbt_replay(result,prices,benchmark)
            np.testing.assert_allclose(replay, result["curve"].nav, rtol=1e-8, atol=0.01)
            replay.to_csv(args.output_dir/f"{mode}_vectorbt_replay.csv")
    manifest = {"synthetic":args.demo,"classification":"synthetic_software_demo" if args.demo else "exploratory_not_causal_evidence",
                "config":asdict(Config()),"metrics":summaries,"vectorbt_reconciled":args.vectorbt_replay,
                "cutoff":"18:00 America/Sao_Paulo; executar na abertura da proxima sessao",
                "input_paths":{k:str(getattr(args,k)) for k in ("prices","benchmark","features")}}
    (args.output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"synthetic":args.demo,"modes":modes,"output":str(args.output_dir),"vectorbt_reconciled":args.vectorbt_replay}))


if __name__ == "__main__":
    main()
