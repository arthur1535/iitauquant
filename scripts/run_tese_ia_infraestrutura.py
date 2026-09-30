"""Tese Infraestrutura de IA: dos chips à energia que alimenta os data centers.

Estratégia sistemática multi-ativos construída sobre o motor oficial do
repositório (``backtest.engine.run_backtest``): sinal Momentum ATR no close de
t, execução no open de t+1, gap de stop na abertura e 15 bps por ponta.

A tese: a demanda por computação de IA puxa uma cadeia física inteira —
aceleradores e memória, servidores, energia crítica e refrigeração do data
center, rede elétrica e geração. A carteira distribui o risco nessas camadas em
vez de concentrar tudo no fabricante de GPUs.

Regras fixadas antes de observar os resultados (sem otimização):

1. Sinal por ativo: ``MomentumATRConfig(20, 14, 2.5)``, os mesmos parâmetros
   das pesquisas Global Leaders, Outliers, China e Bets.
2. Pesos-alvo por camada. Ativo sem histórico ou sem liquidez na data de
   decisão tem o peso redistribuído dentro da própria camada; camada vazia é
   redistribuída proporcionalmente entre as demais.
3. Liquidez: mediana de 63 pregões do volume financeiro >= US$ 5 milhões.
4. Rebalanceamento mensal: decisão no último pregão do mês (close t) e
   execução no close do pregão seguinte, com 15 bps sobre o giro.
5. Vol targeting: alvo de 25% a.a. (ordem de grandeza da volatilidade do QQQ),
   exposição em [0, 1] sem alavancagem, banda de 10 p.p.; decidido no close t
   e vigente a partir do retorno de t+2. O restante fica em caixa sem
   remuneração, mesma convenção do motor.

Uso:
    python scripts/run_tese_ia_infraestrutura.py            # usa o snapshot congelado
    python scripts/run_tese_ia_infraestrutura.py --refresh  # baixa de novo via yfinance
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.engine import BacktestResult, ExecutionConfig, run_backtest  # noqa: E402
from backtest.statistics import deflated_sharpe_probability, expected_maximum_sharpe  # noqa: E402
from backtest.stress import DEFAULT_STRESS_SCENARIOS  # noqa: E402
from strategies.momentum_atr import MomentumATRConfig, validate_ohlc  # noqa: E402


DATA_START = "2020-01-01"
SNAPSHOT_END = "2026-09-29"  # último pregão encerrado quando o snapshot foi gerado
REPORT_DATE = "2026-09-30"

RESULTS_DIR = ROOT / "results" / "tese_ia_infra"
MARKET_DIR = ROOT / "data" / "market"
RELATORIOS_DIR = ROOT / "relatorios"
GRAFICOS_DIR = RELATORIOS_DIR / "graficos"
SNAPSHOT_FILE = RESULTS_DIR / f"snapshot_ohlcv_{SNAPSHOT_END}.parquet"
REPORT_HTML = RELATORIOS_DIR / f"tese_ia_infraestrutura_analise_{REPORT_DATE}.html"

STRATEGY = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
EXECUTION = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)
CAPITAL = 100_000.0
TRADING_DAYS = 252

LIQUIDITY_MIN_USD = 5_000_000.0
LIQUIDITY_WINDOW = 63
LIQUIDITY_MIN_PERIODS = 20
VOL_TARGET = 0.25
VOL_WINDOW = 63
VOL_MIN_PERIODS = 20
VOL_BAND = 0.10
SPLIT_DATE = "2022-12-31"  # mesmo corte IS/pseudo-OOS da auditoria da Tarefa 1


@dataclass(frozen=True, slots=True)
class Ativo:
    ticker: str
    empresa: str
    camada: str
    peso: float
    papel: str
    risco: str


CAMADAS = {
    "computacao": "Chips e computação",
    "infraestrutura": "Infraestrutura do data center",
    "energia": "Geração de energia",
    "especulativo": "Satélites especulativos",
}

ATIVOS: tuple[Ativo, ...] = (
    Ativo("NVDA", "NVIDIA", "computacao", 0.20,
          "GPUs e aceleradores, ecossistema CUDA e rede (NVLink, InfiniBand, Ethernet) para clusters de IA",
          "Concentração em poucos hiperescaladores, ASICs próprios dos clientes, controles de exportação e múltiplo elevado"),
    Ativo("MU", "Micron Technology", "computacao", 0.10,
          "Memória HBM e DRAM para aceleradores e SSDs de data center",
          "Ciclo de preços de memória, capex pesado e competição com SK Hynix e Samsung"),
    Ativo("SMCI", "Super Micro Computer", "computacao", 0.05,
          "Servidores e racks de IA com refrigeração líquida direta",
          "Histórico de atraso de demonstrações e troca de auditor, margens estreitas e dependência de alocação de GPUs"),
    Ativo("STM", "STMicroelectronics", "computacao", 0.05,
          "Semicondutores de potência (SiC/GaN) e microcontroladores; entra na tese pela conversão de energia dos racks",
          "Receita dominada por automotivo e industrial: a ligação com IA é indireta e ainda pequena"),
    Ativo("VRT", "Vertiv", "infraestrutura", 0.12,
          "Energia crítica (UPS, distribuição) e refrigeração líquida para data centers",
          "Carteira de pedidos sensível ao capex dos hiperescaladores e execução de capacidade fabril"),
    Ativo("PWR", "Quanta Services", "infraestrutura", 0.10,
          "Engenharia e construção de linhas de transmissão, subestações e conexões elétricas de data centers",
          "Execução de projetos, mão de obra especializada e ciclo de investimento das utilities"),
    Ativo("GEV", "GE Vernova", "energia", 0.10,
          "Turbinas a gás, equipamentos de rede e eletrificação para a nova carga elétrica",
          "Histórico curto em bolsa (desde 2024), segmento eólico deficitário e expectativa alta já no preço"),
    Ativo("VST", "Vistra", "energia", 0.10,
          "Geração nuclear e a gás nos EUA, com contratos de energia para data centers",
          "Preço de energia no atacado, regulação de colocalização nuclear e alavancagem"),
    Ativo("BE", "Bloom Energy", "energia", 0.08,
          "Células a combustível de óxido sólido para energia local (behind-the-meter) em data centers",
          "Histórico de prejuízos, custo do gás natural e competição com a rede e turbinas"),
    Ativo("DGXX", "Digi Power X", "especulativo", 0.04,
          "Ex-minerador de bitcoin migrando para hospedagem de IA/HPC com geração própria",
          "Microcap, execução do pivô, diluição e dependência do preço do bitcoin"),
    Ativo("VIVO", "VivoPower", "especulativo", 0.03,
          "Microcap em pivô para terrenos energizados e data centers de IA (ticker VVPR até março de 2026)",
          "Pivôs sucessivos de negócio, liquidez historicamente mínima, diluição e risco de continuidade"),
    Ativo("RDW", "Redwire", "especulativo", 0.03,
          "Infraestrutura espacial e defesa; ligação com IA indireta (energia e sensoriamento orbital)",
          "Tese de IA fraca, dependência de contratos governamentais e histórico de prejuízos"),
)

TICKERS = tuple(a.ticker for a in ATIVOS)
BENCHMARKS = ("SMH", "QQQ", "SPY")
PESOS_CAMADAS = {t.ticker: t.peso for t in ATIVOS}
PESOS_IGUAIS = {t: 1.0 / len(TICKERS) for t in TICKERS}
GRUPO_CAMADA = {t.ticker: t.camada for t in ATIVOS}
GRUPO_UNICO = {t: "todos" for t in TICKERS}

VARIANTES = {
    "BH_EW": "Buy & Hold, pesos iguais",
    "BH_CAMADAS": "Buy & Hold, pesos por camada",
    "ATR_EW": "Momentum ATR, pesos iguais",
    "ATR_CAMADAS": "Momentum ATR, pesos por camada",
    "ATR_CAMADAS_VT": "Momentum ATR + camadas + vol target 25% (principal)",
}
PRINCIPAL = "ATR_CAMADAS_VT"


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

def _download(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    end = (pd.Timestamp(SNAPSHOT_END) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=DATA_START, end=end, progress=False, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"download vazio para {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(1):
            raw = raw.xs(ticker, axis=1, level=1)
        elif ticker in raw.columns.get_level_values(0):
            raw = raw[ticker]
    df = raw.rename(columns=lambda c: str(c).strip().lower()).copy()
    df = df.loc[df.index.notna()].sort_index()
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df = df.loc[df.index <= pd.Timestamp(SNAPSHOT_END)]
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df.index.name = "date"
    return validate_ohlc(df)


def load_snapshot(refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Carrega o snapshot congelado; baixa e congela apenas quando pedido ou ausente."""

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tickers = TICKERS + BENCHMARKS
    if refresh or not SNAPSHOT_FILE.exists():
        print(f"[dados] baixando {len(tickers)} séries via yfinance até {SNAPSHOT_END}...")
        frames = []
        for ticker in tickers:
            df = _download(ticker)
            frames.append(df.reset_index().assign(ticker=ticker))
            print(f"  - {ticker:5s} {len(df):5d} barras ({df.index[0]:%Y-%m-%d} a {df.index[-1]:%Y-%m-%d})")
        long = pd.concat(frames, ignore_index=True)[["ticker", "date", "open", "high", "low", "close", "volume"]]
        long.to_parquet(SNAPSHOT_FILE, index=False)

    long = pd.read_parquet(SNAPSHOT_FILE)
    datasets: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        part = long.loc[long["ticker"] == ticker].drop(columns="ticker").set_index("date").sort_index()
        part.index = pd.DatetimeIndex(part.index)
        if part.empty:
            raise RuntimeError(f"{ticker} ausente do snapshot {SNAPSHOT_FILE.name}")
        datasets[ticker] = validate_ohlc(part)

    # Espelha em data/market sem sobrescrever caches de outras pesquisas.
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    for ticker, df in datasets.items():
        target = MARKET_DIR / f"{ticker}.parquet"
        if not target.exists():
            df.to_parquet(target)
    return datasets


def write_manifest(datasets: Mapping[str, pd.DataFrame]) -> dict:
    digest = hashlib.sha256(SNAPSHOT_FILE.read_bytes()).hexdigest()
    manifest = {
        "estudo": "tese_ia_infraestrutura",
        "snapshot": SNAPSHOT_FILE.name,
        "snapshot_sha256": digest,
        "fonte": "Yahoo Finance via yfinance (auto_adjust=False: OHLC ajustado por desdobramentos, sem dividendos)",
        "as_of": SNAPSHOT_END,
        "gerado_em": REPORT_DATE,
        "series": {
            t: {"barras": int(len(df)), "inicio": f"{df.index[0]:%Y-%m-%d}", "fim": f"{df.index[-1]:%Y-%m-%d}"}
            for t, df in datasets.items()
        },
        "regras": {
            "momentum_atr": {"momentum_window": STRATEGY.momentum_window, "atr_window": STRATEGY.atr_window,
                             "stop_multiplier": STRATEGY.stop_multiplier},
            "custo_por_ponta": EXECUTION.cost_per_side,
            "liquidez_minima_usd": LIQUIDITY_MIN_USD,
            "vol_target": VOL_TARGET,
            "vol_janela": VOL_WINDOW,
            "vol_banda": VOL_BAND,
            "pesos_camadas": PESOS_CAMADAS,
        },
        "governanca": {"modo": "paper", "ordens_reais": False, "parametros_otimizados": False,
                       "classificacao": "retrospective_pseudo_oos", "aprovado": False},
    }
    (RESULTS_DIR / "manifesto.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Construção da carteira (funções puras, cobertas por tests/test_tese_ia_infra.py)
# ---------------------------------------------------------------------------

def decision_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Último pregão de cada mês; o último pregão da amostra fica fora (sem execução)."""

    s = pd.Series(index, index=index)
    last = pd.DatetimeIndex(s.groupby([index.year, index.month]).max().to_numpy())
    return last[last < index[-1]]


def dollar_volume_median(closes: pd.DataFrame, volumes: pd.DataFrame) -> pd.DataFrame:
    """Mediana móvel do volume financeiro; usa somente barras até a data."""

    return (closes * volumes).rolling(LIQUIDITY_WINDOW, min_periods=LIQUIDITY_MIN_PERIODS).median()


def allocate_targets(
    base_weights: Mapping[str, float],
    groups: Mapping[str, str],
    eligible: Iterable[str],
) -> dict[str, float]:
    """Redistribui pesos de inelegíveis dentro do grupo; grupo vazio vai para os demais."""

    eligible = set(eligible)
    group_total: dict[str, float] = {}
    group_eligible: dict[str, float] = {}
    for ticker, weight in base_weights.items():
        group = groups[ticker]
        group_total[group] = group_total.get(group, 0.0) + weight
        if ticker in eligible:
            group_eligible[group] = group_eligible.get(group, 0.0) + weight
    active = {g for g, w in group_eligible.items() if w > 0}
    if not active:
        return {ticker: 0.0 for ticker in base_weights}
    active_total = sum(group_total[g] for g in active)
    targets = {}
    for ticker, weight in base_weights.items():
        group = groups[ticker]
        if ticker in eligible and group in active:
            targets[ticker] = weight / group_eligible[group] * group_total[group] / active_total
        else:
            targets[ticker] = 0.0
    return targets


def target_weight_schedule(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    base_weights: Mapping[str, float],
    groups: Mapping[str, str],
    *,
    min_dollar_volume: float = LIQUIDITY_MIN_USD,
    exclude: Iterable[str] = (),
) -> pd.DataFrame:
    """Pesos-alvo em cada data de decisão, com elegibilidade observável no close."""

    excluded = set(exclude)
    liquidity = dollar_volume_median(closes, volumes)
    rows = {}
    for date in decision_dates(closes.index):
        eligible = [
            t for t in base_weights
            if t not in excluded
            and pd.notna(closes.at[date, t])
            and pd.notna(liquidity.at[date, t])
            and liquidity.at[date, t] >= min_dollar_volume
        ]
        rows[date] = allocate_targets(base_weights, groups, eligible)
    return pd.DataFrame.from_dict(rows, orient="index")[list(base_weights)]


@dataclass(slots=True)
class PortfolioResult:
    curve: pd.DataFrame
    weights: pd.DataFrame


def simulate_rebalanced_portfolio(
    asset_returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    *,
    cost_per_side: float = EXECUTION.cost_per_side,
    initial_capital: float = CAPITAL,
) -> PortfolioResult:
    """Carteira de sub-contas com deriva diária e rebalanceamento no pregão seguinte à decisão.

    ``asset_returns`` são retornos close-to-close de cada sub-conta (NaN antes
    da listagem). Um alvo decidido no close de d passa a valer no close de
    d+1; o retorno de d+1 ainda pertence aos pesos antigos. O custo incide
    sobre todo o giro, mesmo quando a sub-conta está em caixa (conservador).
    """

    index = asset_returns.index
    columns = list(target_weights.columns)
    returns = asset_returns[columns].fillna(0.0).to_numpy(dtype=float)
    positions = index.get_indexer(target_weights.index)
    if (positions < 0).any():
        raise ValueError("data de decisão fora do índice de retornos")
    executions = {int(p) + 1: row for p, row in zip(positions, target_weights.to_numpy(dtype=float)) if p + 1 < len(index)}
    if not executions:
        raise ValueError("nenhuma decisão tem pregão seguinte para execução")
    start = min(executions)

    weights = np.zeros(len(columns))
    nav = float(initial_capital)
    curve_rows, weight_rows = [], []
    for k in range(start, len(index)):
        r = returns[k]
        previous_nav = nav
        gross = 1.0 + float(weights @ r)
        nav *= gross
        if gross > 0:
            weights = weights * (1.0 + r) / gross
        turnover = cost = 0.0
        if k in executions:
            target = executions[k]
            turnover = float(np.abs(target - weights).sum())
            cost = cost_per_side * turnover
            nav *= 1.0 - cost
            weights = target.copy()
        curve_rows.append({"date": index[k], "nav": nav, "daily_return": nav / previous_nav - 1.0,
                           "turnover": turnover, "cost": cost, "invested": float(weights.sum())})
        weight_rows.append(weights.copy())
    curve = pd.DataFrame(curve_rows).set_index("date")
    return PortfolioResult(curve=curve, weights=pd.DataFrame(weight_rows, index=curve.index, columns=columns))


def volatility_target_decisions(
    base_returns: pd.Series,
    *,
    target_vol: float = VOL_TARGET,
    window: int = VOL_WINDOW,
    band: float = VOL_BAND,
) -> pd.Series:
    """Multiplicador em [0, 1] decidido no close t com a volatilidade realizada até t."""

    realized = base_returns.rolling(window, min_periods=VOL_MIN_PERIODS).std(ddof=1) * math.sqrt(TRADING_DAYS)
    with np.errstate(divide="ignore"):
        raw = (target_vol / realized).clip(upper=1.0).fillna(1.0)
    decided, current = [], 1.0
    for value in raw.to_numpy(dtype=float):
        if abs(value - current) > band:
            current = value
        decided.append(current)
    return pd.Series(decided, index=base_returns.index, name="vol_multiplier")


def apply_volatility_target(
    base_returns: pd.Series,
    decisions: pd.Series,
    *,
    cost_per_side: float = EXECUTION.cost_per_side,
    initial_capital: float = CAPITAL,
) -> pd.DataFrame:
    """Decisão no close t, ajuste durante t+1 (custo em t+1), vigência no retorno de t+2."""

    effective = decisions.shift(2).fillna(1.0)
    change = (decisions.shift(1).fillna(1.0) - decisions.shift(2).fillna(1.0)).abs()
    returns = (1.0 + effective * base_returns) * (1.0 - cost_per_side * change) - 1.0
    nav = initial_capital * (1.0 + returns).cumprod()
    return pd.DataFrame({"nav": nav, "daily_return": returns, "multiplier": effective, "cost": cost_per_side * change})


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def performance_summary(returns: pd.Series) -> dict[str, float]:
    returns = returns.dropna().astype(float)
    nav = (1.0 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    total = float(nav.iloc[-1] - 1.0)
    cagr = float(nav.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and nav.iloc[-1] > 0 else float("nan")
    vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))
    sharpe = float(returns.mean() * TRADING_DAYS / vol) if vol > 1e-12 else 0.0
    downside = float(math.sqrt(np.mean(np.square(np.minimum(returns.to_numpy(), 0.0)))) * math.sqrt(TRADING_DAYS))
    sortino = float(returns.mean() * TRADING_DAYS / downside) if downside > 1e-12 else 0.0
    peak = nav.cummax().clip(lower=1.0)
    max_dd = float((nav / peak - 1.0).min())
    return {
        "retorno_total": total,
        "cagr": cagr,
        "volatilidade": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": float(cagr / abs(max_dd)) if abs(max_dd) > 1e-9 else float("nan"),
        "assimetria": float(returns.skew()),
        "curtose": float(returns.kurt() + 3.0),
        "pregoes": int(len(returns)),
    }


def annual_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.year).prod() - 1.0


def beta(asset: pd.Series, market: pd.Series) -> float:
    joined = pd.concat([asset, market], axis=1, sort=True).dropna()
    var = joined.iloc[:, 1].var()
    return float(joined.cov().iloc[0, 1] / var) if var > 0 else float("nan")


# ---------------------------------------------------------------------------
# Pesquisa
# ---------------------------------------------------------------------------

def run_sleeves(datasets: Mapping[str, pd.DataFrame], execution: ExecutionConfig) -> dict[str, BacktestResult]:
    return {t: run_backtest(datasets[t], STRATEGY, execution) for t in TICKERS}


def build_panels(datasets: Mapping[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    closes = pd.DataFrame({t: datasets[t]["close"] for t in TICKERS}).sort_index()
    volumes = pd.DataFrame({t: datasets[t]["volume"] for t in TICKERS}).reindex(closes.index)
    bh_returns = pd.DataFrame({t: datasets[t]["close"].pct_change() for t in TICKERS}).reindex(closes.index)
    return closes, volumes, bh_returns


def run_principal(
    atr_returns: pd.DataFrame,
    schedule: pd.DataFrame,
    cost_per_side: float = EXECUTION.cost_per_side,
) -> tuple[PortfolioResult, pd.DataFrame]:
    base = simulate_rebalanced_portfolio(atr_returns, schedule, cost_per_side=cost_per_side)
    decisions = volatility_target_decisions(base.curve["daily_return"])
    scaled = apply_volatility_target(base.curve["daily_return"], decisions, cost_per_side=cost_per_side)
    return base, scaled


def current_positions(datasets: Mapping[str, pd.DataFrame], open_results: Mapping[str, BacktestResult],
                      schedule: pd.DataFrame, closes: pd.DataFrame, volumes: pd.DataFrame) -> pd.DataFrame:
    """Postura do sinal no último pregão, a partir de rodadas sem liquidação artificial no fim."""

    liquidity = dollar_volume_median(closes, volumes).iloc[-1]
    last_date = closes.index[-1]
    eligible_now = [t for t in TICKERS if pd.notna(closes.at[last_date, t]) and liquidity.get(t, 0) >= LIQUIDITY_MIN_USD]
    indicative = allocate_targets(PESOS_CAMADAS, GRUPO_CAMADA, eligible_now)
    rows = []
    for ativo in ATIVOS:
        res = open_results[ativo.ticker]
        last = res.equity_curve.iloc[-1]
        sig = res.signals.iloc[-1]
        close = float(datasets[ativo.ticker]["close"].iloc[-1])
        in_position = bool(last["position"])
        entry_time = entry_price = None
        if in_position:
            buy = res.orders.loc[res.orders["side"] == "BUY"].iloc[-1]
            entry_time, entry_price = pd.Timestamp(buy["fill_time"]), float(buy["fill_price"])
        stop = float(last["stop_price"]) if in_position else float("nan")
        rows.append({
            "ticker": ativo.ticker,
            "empresa": ativo.empresa,
            "camada": CAMADAS[ativo.camada],
            "fechamento": close,
            "momentum_20d": float(sig["momentum"]),
            "atr14": float(sig["atr"]),
            "sinal": "comprado" if in_position else "fora (caixa)",
            "entrada": f"{entry_time:%Y-%m-%d}" if entry_time is not None else "",
            "preco_entrada": entry_price if entry_price is not None else float("nan"),
            "stop_atual": stop,
            "distancia_stop": close / stop - 1.0 if in_position else float("nan"),
            "liquidez_mediana_63d_usd": float(liquidity.get(ativo.ticker, float("nan"))),
            "peso_alvo_vigente": float(schedule.iloc[-1][ativo.ticker]),
            "peso_alvo_indicativo_proximo": float(indicative[ativo.ticker]),
        })
    return pd.DataFrame(rows)


def main(refresh: bool = False) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("IITAUQUANT — TESE INFRAESTRUTURA DE IA: CHIPS, MEMÓRIA, DATA CENTER E ENERGIA")
    print("=" * 80)

    datasets = load_snapshot(refresh=refresh)
    manifest = write_manifest(datasets)
    closes, volumes, bh_returns = build_panels(datasets)

    print("\n[1/5] Motor oficial por ativo (Momentum ATR, open t+1, 15 bps, gap stop)...")
    results = run_sleeves(datasets, EXECUTION)
    atr_returns = pd.DataFrame({t: r.equity_curve["daily_return"] for t, r in results.items()}).reindex(closes.index)
    # Métricas usam a liquidação no fim (conservador); a posição vem da rodada sem ela,
    # que é idêntica até o penúltimo pregão e preserva o estado do último.
    open_results = run_sleeves(datasets, replace(EXECUTION, liquidate_at_end=False))
    atr_position = pd.DataFrame({t: r.equity_curve["position"] for t, r in open_results.items()}).reindex(closes.index).fillna(0)

    print("[2/5] Carteiras: variantes pré-declaradas...")
    sched_camadas = target_weight_schedule(closes, volumes, PESOS_CAMADAS, GRUPO_CAMADA)
    sched_iguais = target_weight_schedule(closes, volumes, PESOS_IGUAIS, GRUPO_UNICO)
    portfolios = {
        "BH_EW": simulate_rebalanced_portfolio(bh_returns, sched_iguais),
        "BH_CAMADAS": simulate_rebalanced_portfolio(bh_returns, sched_camadas),
        "ATR_EW": simulate_rebalanced_portfolio(atr_returns, sched_iguais),
    }
    base, scaled = run_principal(atr_returns, sched_camadas)
    portfolios["ATR_CAMADAS"] = base
    variant_returns = {k: v.curve["daily_return"] for k, v in portfolios.items()}
    variant_returns[PRINCIPAL] = scaled["daily_return"]
    window = variant_returns[PRINCIPAL].index
    bench_returns = {b: datasets[b]["close"].pct_change().reindex(window).fillna(0.0) for b in BENCHMARKS}
    for b in BENCHMARKS:
        bench_returns[b].iloc[0] = 0.0

    rows = []
    for key, rets in {**variant_returns, **{f"{b}_BH": r for b, r in bench_returns.items()}}.items():
        summary = performance_summary(rets)
        rows.append({"variante": key, "descricao": VARIANTES.get(key, f"{key[:-3]} Buy & Hold (benchmark)"), **summary})
    variants_df = pd.DataFrame(rows)

    # Deflação do Sharpe pelas 5 variantes testadas (limite inferior do número real de tentativas).
    principal_stats = variants_df.set_index("variante").loc[PRINCIPAL]
    trial_sharpes = variants_df.loc[variants_df["variante"].isin(VARIANTES), "sharpe"].to_numpy()
    sr_star = expected_maximum_sharpe(float(np.std(trial_sharpes, ddof=1)), len(trial_sharpes))
    qqq_sharpe = float(variants_df.set_index("variante").loc["QQQ_BH", "sharpe"])
    stat_kwargs = dict(n_observations=int(principal_stats["pregoes"]), skewness=float(principal_stats["assimetria"]),
                       kurtosis=float(principal_stats["curtose"]))
    stats = {
        "sharpe_principal": float(principal_stats["sharpe"]),
        "sharpe_esperado_maximo_5_tentativas": sr_star,
        "dsr_5_tentativas": deflated_sharpe_probability(float(principal_stats["sharpe"]), sr_star, **stat_kwargs),
        "psr_vs_zero": deflated_sharpe_probability(float(principal_stats["sharpe"]), 0.0, **stat_kwargs),
        "psr_vs_qqq": deflated_sharpe_probability(float(principal_stats["sharpe"]), qqq_sharpe, **stat_kwargs),
        "sharpe_qqq": qqq_sharpe,
        "exposicao_media_mercado": float((scaled["multiplier"] * (base.weights * atr_position.reindex(base.weights.index)).sum(axis=1)).mean()),
        "multiplicador_vol_medio": float(scaled["multiplier"].mean()),
        "fracao_dias_vol_target_reduz_5pct": float((scaled["multiplier"] < 0.95).mean()),
        "giro_anual_rebalanceamento": float(base.curve["turnover"].sum() / (len(base.curve) / TRADING_DAYS)),
        "inicio": f"{window[0]:%Y-%m-%d}",
        "fim": f"{window[-1]:%Y-%m-%d}",
    }

    print("[3/5] Robustez: subperíodos, anos, exclusão de ativos e estresse de custos...")
    split = pd.Timestamp(SPLIT_DATE)
    sub_rows = []
    for key, rets in [(PRINCIPAL, variant_returns[PRINCIPAL]), ("BH_CAMADAS", variant_returns["BH_CAMADAS"]),
                      ("SMH_BH", bench_returns["SMH"]), ("QQQ_BH", bench_returns["QQQ"])]:
        for label, part in (("2020-2022", rets.loc[:split]), ("2023-2026", rets.loc[split + pd.Timedelta(days=1):])):
            sub_rows.append({"variante": key, "periodo": label, **performance_summary(part)})
    subperiods_df = pd.DataFrame(sub_rows)

    annual_df = pd.DataFrame({
        VARIANTES[PRINCIPAL]: annual_returns(variant_returns[PRINCIPAL]),
        VARIANTES["BH_CAMADAS"]: annual_returns(variant_returns["BH_CAMADAS"]),
        "SMH Buy & Hold": annual_returns(bench_returns["SMH"]),
        "QQQ Buy & Hold": annual_returns(bench_returns["QQQ"]),
    })
    annual_df.index.name = "ano"

    loo_rows = []
    for ticker in TICKERS:
        sched = target_weight_schedule(closes, volumes, PESOS_CAMADAS, GRUPO_CAMADA, exclude=[ticker])
        _, loo_scaled = run_principal(atr_returns, sched)
        loo_rows.append({"ativo_excluido": ticker, **performance_summary(loo_scaled["daily_return"])})
    loo_df = pd.DataFrame(loo_rows)

    stress_rows = []
    for scenario in DEFAULT_STRESS_SCENARIOS:
        execution = replace(EXECUTION, cost_per_side=scenario.cost_per_side, stop_slippage=scenario.stop_slippage)
        s_results = run_sleeves(datasets, execution)
        s_returns = pd.DataFrame({t: r.equity_curve["daily_return"] for t, r in s_results.items()}).reindex(closes.index)
        _, s_scaled = run_principal(s_returns, sched_camadas, cost_per_side=scenario.cost_per_side)
        stress_rows.append({"cenario": scenario.name, "custo_por_ponta": scenario.cost_per_side,
                            "slippage_stop": scenario.stop_slippage, **performance_summary(s_scaled["daily_return"])})
    stress_df = pd.DataFrame(stress_rows)

    print("[4/5] Métricas por ativo e postura atual do sinal...")
    qqq_daily = datasets["QQQ"]["close"].pct_change()
    smh_daily = datasets["SMH"]["close"].pct_change()
    asset_rows = []
    for ativo in ATIVOS:
        df = datasets[ativo.ticker]
        m = results[ativo.ticker].metrics
        bh = performance_summary(df["close"].pct_change().fillna(0.0))
        asset_rows.append({
            "ticker": ativo.ticker, "empresa": ativo.empresa, "camada": CAMADAS[ativo.camada], "peso_alvo": ativo.peso,
            "inicio": f"{df.index[0]:%Y-%m-%d}", "barras": int(m["bars"]), "trades": int(m["total_trades"]),
            "exposicao": float(m["exposure"]), "atr_retorno": float(m["total_return"]), "atr_cagr": float(m["annualized_return"]),
            "atr_sharpe": float(m["sharpe_ratio"]), "atr_max_dd": float(m["max_drawdown"]), "atr_win_rate": float(m["win_rate"]),
            "bh_retorno": bh["retorno_total"], "bh_cagr": bh["cagr"], "bh_sharpe": bh["sharpe"], "bh_max_dd": bh["max_drawdown"],
            "beta_qqq": beta(df["close"].pct_change(), qqq_daily),
            "correlacao_smh": float(pd.concat([df["close"].pct_change(), smh_daily], axis=1, sort=True).dropna().corr().iloc[0, 1]),
        })
    assets_df = pd.DataFrame(asset_rows)
    corr = bh_returns.loc[window].corr()
    stats["correlacao_media_pares"] = float(corr.to_numpy()[np.triu_indices(len(TICKERS), k=1)].mean())

    positions_df = current_positions(datasets, open_results, sched_camadas, closes, volumes)
    stats["multiplicador_vol_atual"] = float(scaled["multiplier"].iloc[-1])
    stats["exposicao_atual_mercado"] = float(
        scaled["multiplier"].iloc[-1] * (base.weights.iloc[-1] * atr_position.iloc[-1]).sum()
    )

    # Exposição efetiva por camada: peso da sub-conta × posição do sinal × multiplicador de vol.
    effective = base.weights * atr_position.reindex(base.weights.index)
    effective = effective.mul(scaled["multiplier"], axis=0)
    exposure_layers = pd.DataFrame({CAMADAS[c]: effective[[a.ticker for a in ATIVOS if a.camada == c]].sum(axis=1)
                                    for c in CAMADAS})
    total_exposure = exposure_layers.sum(axis=1)
    annual_exposure = total_exposure.groupby(total_exposure.index.year).mean()

    # Maior queda da cesta em Buy & Hold: comportamento da estratégia na queda e nos 63 pregões seguintes.
    nav_bh, nav_p = portfolios["BH_CAMADAS"].curve["nav"], scaled["nav"]
    trough = (nav_bh / nav_bh.cummax() - 1).idxmin()
    peak = nav_bh.loc[:trough].idxmax()
    recovery_end = nav_bh.index[min(nav_bh.index.get_loc(trough) + 63, len(nav_bh) - 1)]
    stats["episodio"] = {
        "pico": f"{peak:%Y-%m-%d}", "vale": f"{trough:%Y-%m-%d}", "fim_recuperacao": f"{recovery_end:%Y-%m-%d}",
        "cesta_queda": float(nav_bh[trough] / nav_bh[peak] - 1), "estrategia_queda": float(nav_p[trough] / nav_p[peak] - 1),
        "cesta_recuperacao": float(nav_bh[recovery_end] / nav_bh[trough] - 1),
        "estrategia_recuperacao": float(nav_p[recovery_end] / nav_p[trough] - 1),
    }

    assets_df.to_csv(RESULTS_DIR / "metricas_individuais.csv", index=False)
    variants_df.to_csv(RESULTS_DIR / "metricas_variantes.csv", index=False)
    subperiods_df.to_csv(RESULTS_DIR / "metricas_subperiodos.csv", index=False)
    annual_df.assign(**{"Exposição média (principal)": annual_exposure}).to_csv(RESULTS_DIR / "retornos_anuais.csv")
    loo_df.to_csv(RESULTS_DIR / "robustez_exclusao_ativo.csv", index=False)
    stress_df.to_csv(RESULTS_DIR / "estresse_custos.csv", index=False)
    sched_camadas.to_csv(RESULTS_DIR / "pesos_alvo_mensais.csv", index_label="data_decisao")
    positions_df.to_csv(RESULTS_DIR / "sinais_atuais.csv", index=False)
    pd.DataFrame({"nav": scaled["nav"], "retorno_diario": scaled["daily_return"], "multiplicador_vol": scaled["multiplier"],
                  "nav_sem_vol_target": base.curve["nav"]}).to_csv(RESULTS_DIR / "curva_estrategia_principal.csv", index_label="data")
    (RESULTS_DIR / "estatisticas.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    for _, row in variants_df.iterrows():
        print(f"  - {row['variante']:15s} | CAGR {row['cagr']:+7.2%} | Sharpe {row['sharpe']:5.2f} | "
              f"MaxDD {row['max_drawdown']:7.2%} | Vol {row['volatilidade']:6.2%}")
    print(f"  DSR (5 tentativas): {stats['dsr_5_tentativas']:.3f} | PSR vs QQQ: {stats['psr_vs_qqq']:.3f}")

    print("[5/5] Gráficos e relatórios...")
    nav_chart = {
        "Estratégia principal": variant_returns[PRINCIPAL],
        "B&H pesos por camada": variant_returns["BH_CAMADAS"],
        "SMH B&H": bench_returns["SMH"],
        "QQQ B&H": bench_returns["QQQ"],
    }
    charts = {
        "curvas": plot_equity(nav_chart, RESULTS_DIR / "ia_curvas_capital.png"),
        "exposicao": plot_exposure(exposure_layers, RESULTS_DIR / "ia_exposicao_camadas.png"),
        "ativos": plot_assets(assets_df, RESULTS_DIR / "ia_ativos_bh_vs_atr.png"),
    }
    GRAFICOS_DIR.mkdir(parents=True, exist_ok=True)
    for path in charts.values():
        shutil.copy2(path, GRAFICOS_DIR / path.name)

    context = dict(variants=variants_df, subperiods=subperiods_df, annual=annual_df, annual_exposure=annual_exposure,
                   loo=loo_df, stress=stress_df,
                   assets=assets_df, positions=positions_df, stats=stats, manifest=manifest, schedule=sched_camadas)
    (RESULTS_DIR / "relatorio_tese_ia_infraestrutura.md").write_text(build_markdown(**context), encoding="utf-8")
    REPORT_HTML.write_text(build_html(charts=charts, **context), encoding="utf-8")
    print(f"\n[OK] Artefatos em {RESULTS_DIR.relative_to(ROOT)}/ e {REPORT_HTML.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Gráficos (paleta categórica validada; rótulos diretos compensam contraste baixo)
# ---------------------------------------------------------------------------

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)


def plot_equity(series: Mapping[str, pd.Series], path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    fig.patch.set_facecolor(SURFACE)
    for ax in (ax1, ax2):
        _style_axes(ax)
    endpoints = []
    for (label, rets), color in zip(series.items(), SERIES):
        nav = 100 * (1 + rets).cumprod()
        dd = 100 * (nav / nav.cummax() - 1)
        lw = 2.2 if label == "Estratégia principal" else 1.5
        ax1.plot(nav.index, nav, color=color, lw=lw, label=label)
        ax2.plot(dd.index, dd, color=color, lw=1.2 if lw < 2 else 1.6)
        endpoints.append([math.log10(nav.iloc[-1]), label, nav.iloc[-1], nav.index[-1]])
    # Rótulos finais separados em escala log para não colidirem.
    endpoints.sort()
    for i in range(1, len(endpoints)):
        endpoints[i][0] = max(endpoints[i][0], endpoints[i - 1][0] + 0.055)
    for y_log, label, value, x in endpoints:
        ax1.annotate(f"{label}  {value:,.0f}".replace(",", "."), xy=(x, value), xytext=(x, 10 ** y_log),
                     textcoords="data", va="center", fontsize=8.5, color=INK_2,
                     xycoords="data", annotation_clip=False,
                     arrowprops=None)
    ax1.set_yscale("log")
    ax1.set_ylabel("Patrimônio (base 100, escala log)", color=INK_2, fontsize=10)
    ax1.set_title("Curvas de capital simuladas e quedas desde o pico", loc="left", fontsize=13, color=INK, fontweight="bold")
    ax1.legend(loc="upper left", fontsize=9, frameon=False)
    ax2.set_ylabel("Drawdown (%)", color=INK_2, fontsize=10)
    ax2.axhline(0, color=AXIS, lw=0.8)
    fig.text(0.01, 0.005, "Custos de 15 bps por ponta; caixa sem remuneração; B&H sem dividendos. Simulação histórica, não previsão.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 0.9, 1))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_exposure(layers: pd.DataFrame, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    monthly = layers.resample("ME").mean() * 100
    fig, ax = plt.subplots(figsize=(12, 4.8))
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    bottom = np.zeros(len(monthly))
    for column, color in zip(monthly.columns, SERIES):
        ax.bar(monthly.index, monthly[column], width=24, bottom=bottom, color=color, label=column,
               edgecolor=SURFACE, linewidth=0.8)
        bottom += monthly[column].to_numpy()
    ax.set_ylim(0, 100)
    ax.set_ylabel("% do patrimônio exposto (média do mês)", color=INK_2, fontsize=10)
    ax.set_title("Exposição efetiva a mercado por camada — o que falta para 100% está em caixa",
                 loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, frameon=False, ncol=4)
    fig.text(0.01, 0.01, "Exposição = peso da sub-conta × sinal Momentum ATR comprado × multiplicador de volatilidade.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_assets(assets: pd.DataFrame, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = assets.iloc[::-1]
    y = np.arange(len(ordered))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    h = 0.38
    for ax, (bh_col, atr_col, title) in zip(
        (ax1, ax2), (("bh_cagr", "atr_cagr", "CAGR (%)"), ("bh_max_dd", "atr_max_dd", "Drawdown máximo (%)"))
    ):
        _style_axes(ax)
        ax.grid(True, axis="x", color=GRID, linewidth=0.8)
        ax.grid(False, axis="y")
        ax.barh(y + h / 2, ordered[bh_col] * 100, height=h - 0.04, color=SERIES[1], label="Buy & Hold")
        ax.barh(y - h / 2, ordered[atr_col] * 100, height=h - 0.04, color=SERIES[0], label="Momentum ATR")
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold")
    ax1.set_yticks(y, ordered["ticker"])
    ax1.legend(loc="lower right", fontsize=9, frameon=False)
    fig.suptitle("Cada ativo isolado: Buy & Hold versus Momentum ATR (histórico disponível de cada um)",
                 x=0.01, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def pct(value: float, digits: int = 1, sign: bool = False) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    text = f"{value * 100:+.{digits}f}%" if sign else f"{value * 100:.{digits}f}%"
    return text.replace(".", ",")


def num(value: float, digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def esc(value: object) -> str:
    return html.escape(str(value))


def _row(df: pd.DataFrame, key: str, col: str = "variante") -> pd.Series:
    return df.set_index(col).loc[key]


def build_markdown(*, variants, subperiods, annual, annual_exposure, loo, stress, assets, positions, stats, manifest, schedule) -> str:
    p = _row(variants, PRINCIPAL)
    lines = [
        "# Tese Infraestrutura de IA — chips, memória, data center e energia",
        f"**Data**: {REPORT_DATE} · **Snapshot**: {SNAPSHOT_END} (`{manifest['snapshot']}`, SHA-256 `{manifest['snapshot_sha256'][:16]}…`)  ",
        f"**Janela simulada**: {stats['inicio']} a {stats['fim']} · **Motor**: Momentum ATR oficial, open t+1, 15 bps por ponta  ",
        "**Classificação**: pesquisa retrospectiva (`retrospective_pseudo_oos`), paper-only, sem aprovação para capital real.",
        "",
        "## 1. Resultado das variantes pré-declaradas",
        "",
        "| Variante | Retorno | CAGR | Vol. | Sharpe | Sortino | Max DD | Calmar |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, r in variants.iterrows():
        lines.append(f"| {r['descricao']} | {pct(r['retorno_total'], 1, True)} | {pct(r['cagr'], 1, True)} | "
                     f"{pct(r['volatilidade'])} | {num(r['sharpe'])} | {num(r['sortino'])} | {pct(r['max_drawdown'])} | {num(r['calmar'])} |")
    lines += [
        "",
        f"Sharpe da principal: **{num(p['sharpe'])}**; Sharpe máximo esperado ao acaso com 5 tentativas: {num(stats['sharpe_esperado_maximo_5_tentativas'])}; "
        f"DSR: **{num(stats['dsr_5_tentativas'], 3)}**; PSR contra o Sharpe do QQQ ({num(stats['sharpe_qqq'])}): {num(stats['psr_vs_qqq'], 3)}. "
        f"Exposição média a mercado: {pct(stats['exposicao_media_mercado'])}. Correlação média entre pares de ativos: {num(stats['correlacao_media_pares'])}.",
        "",
        "## 2. Subperíodos (corte em 31/12/2022)",
        "",
        "| Variante | Período | CAGR | Sharpe | Max DD |",
        "|---|---|---|---|---|",
    ]
    for _, r in subperiods.iterrows():
        lines.append(f"| {r['variante']} | {r['periodo']} | {pct(r['cagr'], 1, True)} | {num(r['sharpe'])} | {pct(r['max_drawdown'])} |")
    lines += ["", "## 3. Retornos por ano", "", "| Ano | " + " | ".join(annual.columns) + " | Exposição média (principal) |",
              "|---|" + "---|" * (len(annual.columns) + 1)]
    for year, r in annual.iterrows():
        lines.append(f"| {year} | " + " | ".join(pct(v, 1, True) for v in r) + f" | {pct(annual_exposure.loc[year], 0)} |")
    lines += ["", "## 4. Exclusão de um ativo por vez (estratégia principal)", "",
              "| Ativo excluído | CAGR | Sharpe | Max DD |", "|---|---|---|---|"]
    for _, r in loo.iterrows():
        lines.append(f"| {r['ativo_excluido']} | {pct(r['cagr'], 1, True)} | {num(r['sharpe'])} | {pct(r['max_drawdown'])} |")
    lines += ["", "## 5. Estresse de custos e slippage", "", "| Cenário | Custo/ponta | Slippage stop | CAGR | Sharpe | Max DD |",
              "|---|---|---|---|---|---|"]
    for _, r in stress.iterrows():
        lines.append(f"| {r['cenario']} | {pct(r['custo_por_ponta'], 2)} | {pct(r['slippage_stop'], 2)} | {pct(r['cagr'], 1, True)} | "
                     f"{num(r['sharpe'])} | {pct(r['max_drawdown'])} |")
    lines += ["", "## 6. Ativos individuais", "",
              "| Ticker | Camada | Peso-alvo | Início | ATR CAGR | ATR Max DD | B&H CAGR | B&H Max DD | Beta QQQ |",
              "|---|---|---|---|---|---|---|---|---|"]
    for _, r in assets.iterrows():
        lines.append(f"| `{r['ticker']}` | {r['camada']} | {pct(r['peso_alvo'], 0)} | {r['inicio']} | {pct(r['atr_cagr'], 1, True)} | "
                     f"{pct(r['atr_max_dd'])} | {pct(r['bh_cagr'], 1, True)} | {pct(r['bh_max_dd'])} | {num(r['beta_qqq'])} |")
    lines += ["", f"## 7. Postura do sinal em {SNAPSHOT_END} (paper, não é ordem)", "",
              "| Ticker | Sinal | Entrada | Stop atual | Distância ao stop | Peso-alvo vigente | Peso indicativo próximo mês |",
              "|---|---|---|---|---|---|---|"]
    for _, r in positions.iterrows():
        lines.append(f"| `{r['ticker']}` | {r['sinal']} | {r['entrada'] or '—'} | {num(r['stop_atual'])} | {pct(r['distancia_stop'])} | "
                     f"{pct(r['peso_alvo_vigente'])} | {pct(r['peso_alvo_indicativo_proximo'])} |")
    lines += [
        "",
        f"Multiplicador de volatilidade vigente: {num(stats['multiplicador_vol_atual'])}; exposição a mercado atual: {pct(stats['exposicao_atual_mercado'])}.",
        "",
        "## 8. Limitações",
        "",
        "- **Viés de seleção ex-post**: o universo foi escolhido em setembro de 2026, depois da alta dos nomes ligados à IA. O backtest mede o que teria acontecido com esta cesta, não a capacidade de escolhê-la em 2020.",
        "- Um único fator domina a carteira (capex de IA dos hiperescaladores); a diversificação entre camadas é menor do que o número de ativos sugere.",
        "- Microcaps (VIVO, DGXX) tiveram liquidez mínima em parte da amostra; o filtro de US$ 5 mi evita alocação nesses períodos, mas fills a 15 bps continuam otimistas para elas.",
        "- Preços sem dividendos, caixa sem remuneração, Sharpe com taxa livre de risco zero, sem impostos nem câmbio para investidor brasileiro.",
        "- Nenhum parâmetro foi otimizado, mas cinco variantes foram comparadas; o DSR considera apenas essas cinco tentativas.",
        "- Quando só um satélite especulativo é elegível, ele recebe os 10% da camada inteira (VIVO em 2021, RDW em 2025).",
        "- A banda de 10 p.p. do vol target pode deixar o multiplicador parado um pouco abaixo de 1 depois de um episódio volátil; o efeito médio é pequeno (multiplicador médio "
        + f"{num(stats['multiplicador_vol_medio'])}).",
    ]
    return "\n".join(lines) + "\n"


CSS = """
:root{--ink:#0f172a;--muted:#475569;--paper:#f8fafc;--card:#fff;--line:#e2e8f0;
--blue:#0369a1;--cyan:#38bdf8;--green:#047857;--red:#b91c1c;--amber:#b45309;
--shadow:0 10px 25px -5px rgba(15,23,42,.07),0 8px 10px -6px rgba(15,23,42,.04)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6}
a{color:var(--blue);text-underline-offset:2px}.wrap{max-width:1200px;margin:auto;padding:32px 24px}
header{background:linear-gradient(135deg,#071527,#0f172a 52%,#14532d);color:#fff;
border-top:6px solid #76b900;padding:42px;border-radius:8px;box-shadow:var(--shadow)}
.eyebrow{color:#a3e635;font-weight:750;letter-spacing:.09em;text-transform:uppercase;font-size:.78rem}
h1{font-size:clamp(2rem,3.8vw,3.2rem);line-height:1.1;margin:.45rem 0 1rem;max-width:1000px}
h2{font-size:1.5rem;line-height:1.25;margin:0 0 18px}h3{font-size:1.05rem;margin:0 0 8px}
.meta{color:#cbd5e1;font-size:.88rem}.verdict{margin-top:22px;padding:20px 24px;
border-left:5px solid #a3e635;background:rgba(255,255,255,.08);border-radius:0 8px 8px 0}
.grid{display:grid;gap:20px}.kpis{grid-template-columns:repeat(4,1fr);margin:24px 0}
.kpi,.card,section{background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
.kpi{padding:20px}.kpi b{display:block;font-size:1.6rem;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:.82rem}
section{padding:30px;margin:24px 0}.grid>*{min-width:0}.two{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.four{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}.card ul{padding-left:18px}
.card{padding:20px;box-shadow:none}.c-computacao{border-top:4px solid #2a78d6}.c-infraestrutura{border-top:4px solid #eb6834}
.c-energia{border-top:4px solid #1baf7a}.c-especulativo{border-top:4px solid #eda100}
.negative{border-top:4px solid var(--red)}.neutral{border-top:4px solid var(--blue)}
.tag{display:inline-block;padding:3px 9px;border-radius:4px;background:#e0f2fe;color:#075985;font-size:.73rem;
font-weight:750;text-transform:uppercase;letter-spacing:.04em}
.callout{padding:18px 20px;background:#f0f9ff;border-left:5px solid var(--blue);border-radius:0 6px 6px 0;margin:18px 0}
.warn{background:#fffbeb;border-left-color:var(--amber)}.small{font-size:.84rem;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:12px;font-variant-numeric:tabular-nums}
th,td{padding:9px 11px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}thead th{background:#f8fafc;color:#334155;font-weight:700}
tbody tr:last-child td{border-bottom:0}tr.hl td{background:#f0fdf4;font-weight:650}
td.l,th.l{text-align:left}.pos{color:var(--green)}.neg{color:var(--red)}
.img-box{text-align:center;margin:22px 0}.img-box img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px}
ol.rules li{margin-bottom:8px}code{background:#f1f5f9;padding:1px 6px;border-radius:4px;font-size:.85em}
.footer{color:var(--muted);font-size:.82rem;padding:14px 4px 40px;border-top:1px solid var(--line);margin-top:30px}
.scroll{overflow-x:auto}
@media(max-width:860px){.wrap{padding:16px}header,section{padding:22px}.kpis{grid-template-columns:1fr 1fr}.two,.four{grid-template-columns:1fr}
table{font-size:.8rem}th,td{padding:8px 6px}}
"""


def _cls(value: float) -> str:
    return "pos" if np.isfinite(value) and value > 0 else ("neg" if np.isfinite(value) and value < 0 else "")


def _usd_compact(value: float) -> str:
    return f"US$ {num(value / 1e9, 1)} bi" if value >= 1e9 else f"US$ {num(value / 1e6, 1)} mi"


def _img(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def build_html(*, charts, variants, subperiods, annual, annual_exposure, loo, stress, assets, positions, stats, manifest, schedule) -> str:
    p = _row(variants, PRINCIPAL)
    bh = _row(variants, "BH_CAMADAS")
    smh = _row(variants, "SMH_BH")
    qqq = _row(variants, "QQQ_BH")
    sub = subperiods.set_index(["variante", "periodo"])
    loo_sorted = loo.sort_values("sharpe")
    worst_loo = loo_sorted.iloc[0]
    best_loo = loo_sorted.iloc[-1]
    severe = stress.set_index("cenario").iloc[-1]
    n_long = int((positions["sinal"] == "comprado").sum())

    camada_cards = []
    for key, label in CAMADAS.items():
        members = [a for a in ATIVOS if a.camada == key]
        items = "".join(f"<li><strong>{esc(a.empresa)} ({a.ticker}, {pct(a.peso, 0)})</strong> — {esc(a.papel)}.</li>" for a in members)
        camada_cards.append(
            f"<div class='card c-{key}'><span class='tag'>{pct(sum(a.peso for a in members), 0)} da carteira</span>"
            f"<h3>{esc(label)}</h3><ul>{items}</ul></div>"
        )

    variant_rows = []
    for _, r in variants.iterrows():
        hl = " class='hl'" if r["variante"] == PRINCIPAL else ""
        variant_rows.append(
            f"<tr{hl}><td>{esc(r['descricao'])}</td><td class='{_cls(r['retorno_total'])}'>{pct(r['retorno_total'], 1, True)}</td>"
            f"<td>{pct(r['cagr'], 1, True)}</td><td>{pct(r['volatilidade'])}</td><td>{num(r['sharpe'])}</td>"
            f"<td>{num(r['sortino'])}</td><td class='neg'>{pct(r['max_drawdown'])}</td><td>{num(r['calmar'])}</td></tr>"
        )

    sub_rows = []
    labels = {PRINCIPAL: "Estratégia principal", "BH_CAMADAS": "B&amp;H pesos por camada", "SMH_BH": "SMH B&amp;H", "QQQ_BH": "QQQ B&amp;H"}
    for key, label in labels.items():
        a, b = sub.loc[(key, "2020-2022")], sub.loc[(key, "2023-2026")]
        sub_rows.append(
            f"<tr><td>{label}</td><td>{pct(a['cagr'], 1, True)}</td><td>{num(a['sharpe'])}</td><td class='neg'>{pct(a['max_drawdown'])}</td>"
            f"<td>{pct(b['cagr'], 1, True)}</td><td>{num(b['sharpe'])}</td><td class='neg'>{pct(b['max_drawdown'])}</td></tr>"
        )

    annual_head = "".join(f"<th>{esc(c)}</th>" for c in annual.columns) + "<th>Exposição média (principal)</th>"
    annual_rows = "".join(
        f"<tr><td>{year}{' (desde ' + stats['inicio'][5:7] + '/' + stats['inicio'][:4] + ')' if year == annual.index[0] else ''}"
        f"{' (até 29/09)' if year == annual.index[-1] else ''}</td>"
        + "".join(f"<td class='{_cls(v)}'>{pct(v, 1, True)}</td>" for v in r) + f"<td>{pct(annual_exposure.loc[year], 0)}</td></tr>"
        for year, r in annual.iterrows()
    )

    loo_rows = "".join(
        f"<tr><td>sem {esc(r['ativo_excluido'])}</td><td>{pct(r['cagr'], 1, True)}</td><td>{num(r['sharpe'])}</td>"
        f"<td class='neg'>{pct(r['max_drawdown'])}</td></tr>" for _, r in loo.iterrows()
    )
    stress_rows = "".join(
        f"<tr><td>{esc(r['cenario'])}</td><td>{pct(r['custo_por_ponta'], 2)}</td><td>{pct(r['slippage_stop'], 2)}</td>"
        f"<td>{pct(r['cagr'], 1, True)}</td><td>{num(r['sharpe'])}</td><td class='neg'>{pct(r['max_drawdown'])}</td></tr>"
        for _, r in stress.iterrows()
    )
    asset_rows = "".join(
        f"<tr><td><strong>{r['ticker']}</strong> <span class='small'>{esc(r['empresa'])}</span></td><td class='l'>{esc(r['camada'])}</td>"
        f"<td>{pct(r['peso_alvo'], 0)}</td><td>{r['inicio']}</td><td>{int(r['trades'])}</td><td>{pct(r['exposicao'], 0)}</td>"
        f"<td class='{_cls(r['atr_cagr'])}'>{pct(r['atr_cagr'], 1, True)}</td><td class='neg'>{pct(r['atr_max_dd'])}</td>"
        f"<td class='{_cls(r['bh_cagr'])}'>{pct(r['bh_cagr'], 1, True)}</td><td class='neg'>{pct(r['bh_max_dd'])}</td>"
        f"<td>{num(r['beta_qqq'])}</td></tr>"
        for _, r in assets.iterrows()
    )
    risk_rows = "".join(f"<tr><td><strong>{a.ticker}</strong></td><td class='l'>{esc(a.risco)}</td></tr>" for a in ATIVOS)
    position_rows = "".join(
        f"<tr><td><strong>{r['ticker']}</strong></td><td class='l'>{esc(r['sinal'])}</td><td>{r['entrada'] or '—'}</td>"
        f"<td>US$ {num(r['fechamento'])}</td><td>{pct(r['momentum_20d'], 1, True)}</td>"
        f"<td>{('US$ ' + num(r['stop_atual'])) if np.isfinite(r['stop_atual']) else '—'}</td><td>{pct(r['distancia_stop'])}</td>"
        f"<td>{_usd_compact(r['liquidez_mediana_63d_usd'])}</td><td>{pct(r['peso_alvo_vigente'])}</td>"
        f"<td>{pct(r['peso_alvo_indicativo_proximo'])}</td></tr>"
        for _, r in positions.iterrows()
    )

    janela = f"{stats['inicio'][5:7]}/{stats['inicio'][:4]}–{stats['fim'][5:7]}/{stats['fim'][:4]}"
    if p["max_drawdown"] > bh["max_drawdown"]:
        tradeoff = (f"O timing reduziu o drawdown máximo de {pct(bh['max_drawdown'])} para {pct(p['max_drawdown'])} e, em troca, "
                    f"abriu mão de {num((bh['cagr'] - p['cagr']) * 100, 1)} p.p. de retorno ao ano num período em que quase todos esses ativos dispararam. ")
    else:
        tradeoff = "O timing não reduziu o drawdown frente ao Buy &amp; Hold nesta amostra. "
    verdict = (
        f"Em {janela}, a estratégia principal teria composto {pct(p['cagr'], 1)} ao ano (Sharpe {num(p['sharpe'])}), com drawdown máximo de "
        f"{pct(p['max_drawdown'])}. A mesma cesta em Buy &amp; Hold rendeu {pct(bh['cagr'], 1)} ao ano, com quedas de até {pct(bh['max_drawdown'])}. "
        + tradeoff
        + f"Ajustado ao risco, o resultado ficou próximo do QQQ (CAGR {pct(qqq['cagr'], 1)}, Sharpe {num(qqq['sharpe'])}). "
        "Como a cesta foi escolhida depois da alta de IA, os números históricos superestimam o que se obteria escolhendo esses nomes em 2020."
    )
    rel = (annual.iloc[:, 0] - annual.iloc[:, 1]).sort_values()
    lagging = " e ".join(
        f"{int(y)} ({pct(annual.iloc[:, 0].loc[y], 1, True)} contra {pct(annual.iloc[:, 1].loc[y], 1, True)}, exposição média de {pct(annual_exposure.loc[y], 0)})"
        for y in sorted(rel.index[:2])
    )
    ep = stats["episodio"]
    fmt_date = lambda d: f"{d[8:]}/{d[5:7]}/{d[:4]}"
    worst_year_text = (
        f"Os anos de maior defasagem frente à cesta em Buy &amp; Hold foram {lagging}. Com exposição parcial, a estratégia fica atrás em altas fortes e contínuas. "
        f"Na maior queda da cesta ({fmt_date(ep['pico'])} a {fmt_date(ep['vale'])}), a estratégia variou {pct(ep['estrategia_queda'], 1, True)} contra "
        f"{pct(ep['cesta_queda'], 1, True)}; nos 63 pregões seguintes, {pct(ep['estrategia_recuperacao'], 1, True)} contra {pct(ep['cesta_recuperacao'], 1, True)}. "
        "Os stops protegem na queda, e a recompra só acontece depois que o momentum de 20 pregões volta a ficar positivo, o que deixa parte da recuperação para trás."
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tese Infraestrutura de IA — chips, memória, data center e energia</title><style>{CSS}</style></head>
<body><main class="wrap">
<header>
  <div class="eyebrow">Estratégia sistemática multi-ativos • NVDA, MU, STM, SMCI, VRT, PWR, GEV, VST, BE, DGXX, VIVO, RDW</div>
  <h1>Tese Infraestrutura de IA: dos chips à energia que alimenta os data centers</h1>
  <p class="meta">Relatório de {REPORT_DATE[8:]}/{REPORT_DATE[5:7]}/{REPORT_DATE[:4]} • Snapshot de preços até {SNAPSHOT_END[8:]}/{SNAPSHOT_END[5:7]}/{SNAPSHOT_END[:4]} (último pregão encerrado) •
  Motor oficial Momentum ATR (open t+1, 15 bps por ponta) • Paper-only, sem ordens reais</p>
  <div class="verdict"><strong>Postura de pesquisa: tese viável como carteira satélite com controle de risco; não aprovada para capital real.</strong><br>{verdict}</div>
</header>

<div class="grid kpis">
  <div class="kpi"><b>{pct(p['cagr'], 1, True)}</b><span>CAGR da estratégia principal ({stats['inicio'][:4]}–{stats['fim'][:4]})</span></div>
  <div class="kpi"><b>{num(p['sharpe'])}</b><span>Sharpe (rf = 0); QQQ B&amp;H: {num(qqq['sharpe'])} • SMH B&amp;H: {num(smh['sharpe'])}</span></div>
  <div class="kpi"><b>{pct(p['max_drawdown'])}</b><span>Drawdown máximo; B&amp;H da cesta: {pct(bh['max_drawdown'])}</span></div>
  <div class="kpi"><b>{pct(stats['exposicao_atual_mercado'], 0)}</b><span>Exposição a mercado em {SNAPSHOT_END[8:]}/{SNAPSHOT_END[5:7]} ({n_long} de {len(ATIVOS)} sinais comprados); média histórica {pct(stats['exposicao_media_mercado'], 0)}</span></div>
</div>

<section><h2>1. A tese em quatro camadas</h2>
<p>Treinar e rodar modelos de IA exige mais do que GPUs. Cada cluster precisa de memória de alta banda, servidores e racks, energia
ininterrupta, refrigeração líquida, conexão à rede elétrica e, cada vez mais, geração dedicada. A carteira compra essa cadeia física,
com peso maior onde a ligação com a IA é direta e a empresa é grande e líquida, e peso pequeno onde a tese é especulativa.</p>
<div class="grid four">{''.join(camada_cards)}</div>
<div class="callout warn"><strong>Ligação com IA desigual:</strong> NVDA, MU, SMCI e VRT vendem diretamente para data centers de IA.
PWR, GEV, VST e BE dependem da demanda elétrica que esses data centers criam. STM e RDW têm exposição indireta e pequena, e DGXX e VIVO são
pivôs de negócio ainda em execução. Os pesos refletem essa diferença.</div></section>

<section><h2>2. Regras da estratégia (fixadas antes do backtest)</h2>
<ol class="rules">
<li><strong>Sinal por ativo:</strong> Momentum ATR do repositório com os parâmetros padrão (momentum de 20 pregões, ATR de 14, stop de 2,5×ATR com ratchet).
Compra quando o momentum cruza zero para cima no fechamento e executa na abertura seguinte. Sai no stop (ou na abertura, se houver gap) ou quando o momentum fica negativo. Nenhum parâmetro foi otimizado.</li>
<li><strong>Pesos-alvo por camada:</strong> chips e computação 40%, infraestrutura do data center 22%, geração de energia 28%, satélites especulativos 10%. Cada ativo tem uma sub-conta; quando o sinal está fora, a sub-conta fica em caixa.</li>
<li><strong>Filtro de liquidez e histórico:</strong> entra no rebalanceamento só quem tem cotação na data e mediana de 63 pregões de volume financeiro de pelo menos US$ 5 milhões. O peso de quem não passa vai para os pares da mesma camada. Por isso GEV só entra em 2024 e VIVO fica fora na maior parte da amostra.</li>
<li><strong>Rebalanceamento mensal:</strong> decisão no último pregão do mês e execução no pregão seguinte, com 15 bps sobre todo o giro (inclusive o de sub-contas em caixa, o que é conservador).</li>
<li><strong>Controle de volatilidade:</strong> se a volatilidade realizada de 63 pregões passar de 25% ao ano, a exposição total é reduzida na proporção (sem alavancagem, banda de 10 p.p. para evitar giro excessivo). A decisão usa o fechamento de t e só afeta o retorno de t+2.</li>
</ol>
<p class="small">Giro médio anual do rebalanceamento: {pct(stats['giro_anual_rebalanceamento'], 0)} do patrimônio. Exposição média efetiva a mercado: {pct(stats['exposicao_media_mercado'], 0)}.
O controle de volatilidade raramente atua (multiplicador médio de {num(stats['multiplicador_vol_medio'])}; redução de pelo menos 5% em {pct(stats['fracao_dias_vol_target_reduz_5pct'], 0)} dos pregões) porque o próprio sinal Momentum ATR mantém a volatilidade perto de 20% ao ano; ele funciona como trava para episódios extremos.
Quando só um satélite especulativo passa no filtro, ele recebe os 10% da camada inteira (ocorreu com VIVO em 2021 e RDW em 2025; veja <code>pesos_alvo_mensais.csv</code>).</p>
</section>

<section><h2>3. Resultado histórico das variantes</h2>
<p>As cinco variantes foram declaradas antes da execução: duas sem timing (Buy &amp; Hold), duas com o sinal Momentum ATR e a principal, que acrescenta o controle de volatilidade.
Os benchmarks usam a mesma janela ({stats['inicio']} a {stats['fim']}).</p>
<div class="scroll"><table><thead><tr><th>Variante</th><th>Retorno</th><th>CAGR</th><th>Vol.</th><th>Sharpe</th><th>Sortino</th><th>Max DD</th><th>Calmar</th></tr></thead>
<tbody>{''.join(variant_rows)}</tbody></table></div>
<div class="img-box"><img src="data:image/png;base64,{_img(charts['curvas'])}" alt="Curvas de capital e drawdowns da estratégia principal, da cesta em Buy and Hold, do SMH e do QQQ"></div>
<div class="grid two">
<div class="card neutral"><h3>Versão sistemática (principal)</h3><p>Para quem quer a tese de IA com quedas parecidas com as do índice amplo. Ficou em média {pct(stats['exposicao_media_mercado'], 0)} exposta a mercado,
com volatilidade de {pct(p['volatilidade'], 0)} ao ano e drawdown máximo de {pct(p['max_drawdown'])}. O custo é ficar de fora de parte das altas.</p></div>
<div class="card negative"><h3>Cesta em Buy &amp; Hold por camadas</h3><p>Capturou toda a alta ({pct(bh['cagr'], 1)} ao ano), mas com volatilidade de {pct(bh['volatilidade'], 0)} e quedas de até {pct(bh['max_drawdown'])}.
Só faz sentido como posição pequena dentro de uma carteira maior, dimensionada para suportar metade do valor evaporando.</p></div>
</div>
<div class="callout"><strong>Teste de sorte (Deflated Sharpe):</strong> com 5 variantes testadas, o Sharpe máximo esperado ao acaso seria {num(stats['sharpe_esperado_maximo_5_tentativas'])}.
A probabilidade de o Sharpe da principal ({num(p['sharpe'])}) superar esse patamar é <strong>{num(stats['dsr_5_tentativas'], 3)}</strong>; contra o Sharpe do QQQ ({num(stats['sharpe_qqq'])}) é {num(stats['psr_vs_qqq'], 3)}.
Esse teste não corrige o viés de seleção do universo (seção 6).</div>
</section>

<section><h2>4. Exposição ao longo do tempo e postura atual do sinal</h2>
<div class="img-box"><img src="data:image/png;base64,{_img(charts['exposicao'])}" alt="Exposição efetiva a mercado por camada ao longo do tempo"></div>
<p>Tabela abaixo: estado do sinal no fechamento de {SNAPSHOT_END[8:]}/{SNAPSHOT_END[5:7]}/{SNAPSHOT_END[:4]}. O peso vigente veio da decisão de agosto. O peso indicativo usa a elegibilidade de hoje; a decisão oficial de setembro sai com o fechamento de 30/09 e é executada no pregão seguinte.
Multiplicador de volatilidade vigente: {num(stats['multiplicador_vol_atual'])}.</p>
<div class="scroll"><table><thead><tr><th>Ativo</th><th class="l">Sinal</th><th>Entrada</th><th>Fechamento</th><th>Momentum 20d</th><th>Stop atual</th><th>Folga até o stop</th><th>Liquidez (mediana 63d)</th><th>Peso vigente</th><th>Peso indicativo</th></tr></thead>
<tbody>{position_rows}</tbody></table></div>
<p class="small">Stops são níveis de referência da simulação: um gap de abertura pode executar abaixo deles. Isto é o estado de um modelo paper, não uma ordem nem uma recomendação individual.</p>
</section>

<section><h2>5. Cada ativo isolado</h2>
<div class="img-box"><img src="data:image/png;base64,{_img(charts['ativos'])}" alt="CAGR e drawdown máximo de cada ativo, Buy and Hold contra Momentum ATR"></div>
<div class="scroll"><table><thead><tr><th>Ativo</th><th class="l">Camada</th><th>Peso</th><th>Início</th><th>Trades</th><th>Exposição</th><th>ATR CAGR</th><th>ATR Max DD</th><th>B&amp;H CAGR</th><th>B&amp;H Max DD</th><th>Beta QQQ</th></tr></thead>
<tbody>{asset_rows}</tbody></table></div>
<p class="small">Cada linha usa todo o histórico disponível do ativo desde 2020 (GEV desde 2024, RDW e DGXX desde 2021), por isso não é comparável linha a linha. A correlação média entre pares de ativos na janela da carteira foi {num(stats['correlacao_media_pares'])}.</p>
</section>

<section><h2>6. Robustez e limites da evidência</h2>
<div class="grid two">
<div><h3>Subperíodos (corte em 31/12/2022)</h3><div class="scroll"><table><thead><tr><th></th><th colspan="3">2020–2022</th><th colspan="3">2023–2026</th></tr>
<tr><th>Série</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr></thead><tbody>{''.join(sub_rows)}</tbody></table></div>
<p class="small">2020–2022 inclui a alta pós-pandemia e o bear market de semicondutores de 2022. 2023–2026 é o ciclo pós-ChatGPT, período em que estes nomes ficaram conhecidos como beneficiários de IA.</p></div>
<div><h3>Estresse de custos (motor oficial)</h3><div class="scroll"><table><thead><tr><th>Cenário</th><th>Custo/ponta</th><th>Slippage stop</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr></thead><tbody>{stress_rows}</tbody></table></div>
<p class="small">No cenário severo (50 bps por ponta e 30 bps de slippage no stop), o CAGR fica em {pct(severe['cagr'], 1, True)}. O Momentum ATR gira bastante, então o custo real de execução é decisivo.</p></div>
</div>
<h3 style="margin-top:22px">Retornos por ano</h3>
<div class="scroll"><table><thead><tr><th>Ano</th>{annual_head}</tr></thead><tbody>{annual_rows}</tbody></table></div>
<p class="small">{worst_year_text}</p>
<h3 style="margin-top:22px">Dependência de um único ativo (exclusão de um por vez)</h3>
<p>Retirando um ativo por vez e redistribuindo o peso dentro da camada, o Sharpe da principal varia de {num(worst_loo['sharpe'])} (sem {esc(worst_loo['ativo_excluido'])}) a {num(best_loo['sharpe'])} (sem {esc(best_loo['ativo_excluido'])}).</p>
<div class="scroll"><table><thead><tr><th>Carteira</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr></thead><tbody>{loo_rows}</tbody></table></div>
<div class="callout warn"><strong>Viés de seleção ex-post:</strong> a lista de ativos foi escolhida em setembro de 2026, quando já se sabia quais empresas se beneficiaram da IA
(Vistra, Vertiv, GE Vernova, Bloom e NVIDIA estão entre as maiores altas do mercado americano no período). Nenhum teste estatístico aqui remove esse viés.
O backtest mostra como as regras de risco teriam se comportado nesta cesta, não quanto se ganharia escolhendo ações de IA em 2020.</div>
</section>

<section><h2>7. Riscos que invalidam a tese</h2>
<div class="grid two">
<div class="card negative"><h3>Riscos da carteira</h3><ul>
<li><strong>Um fator só:</strong> todas as camadas dependem do capex de IA dos hiperescaladores. Um corte de investimento derruba chips, data center e energia ao mesmo tempo.</li>
<li><strong>Valuation:</strong> vários nomes negociam a múltiplos que já pressupõem anos de crescimento; uma decepção de guidance pode gerar gaps que atravessam qualquer stop.</li>
<li><strong>Política e regulação:</strong> controles de exportação de chips, tarifas, licenciamento de geração, conexão à rede e regras de colocalização nuclear.</li>
<li><strong>Eficiência:</strong> ganhos de eficiência em modelos e chips podem reduzir a demanda por energia e hardware por unidade de computação.</li>
<li><strong>Investidor brasileiro:</strong> câmbio, tributação e, se via BDR, paridade e liquidez do BDR (confirme cada programa na B3/CVM antes de operar).</li>
</ul></div>
<div class="card neutral"><h3>Riscos por empresa</h3><div class="scroll"><table><tbody>{risk_rows}</tbody></table></div></div>
</div></section>

<section><h2>8. Como reproduzir e operar em paper</h2>
<ul>
<li><code>python scripts/run_tese_ia_infraestrutura.py</code> reproduz tudo offline a partir do snapshot congelado <code>results/tese_ia_infra/{esc(manifest['snapshot'])}</code> (SHA-256 <code>{esc(manifest['snapshot_sha256'][:16])}…</code>). Com <code>--refresh</code>, baixa de novo pelo yfinance.</li>
<li>Calendário: rebalanceamento no pregão seguinte ao último pregão de cada mês; sinais e stops são reavaliados diariamente no fechamento.</li>
<li>Universo registrado em <code>config/momentum_universe.json</code> como <code>tese_ia_infraestrutura</code>. Métricas, pesos mensais, sinais atuais e curvas estão em <code>results/tese_ia_infra/</code>.</li>
<li>Antes de qualquer capital real: validação walk-forward fora da amostra, paper trading pelo OMS do repositório e revisão humana dos fundamentos de cada empresa.</li>
</ul>
<p class="small">Fontes: preços diários — {esc(manifest['fonte'])}. A descrição dos negócios é qualitativa e deve ser confirmada nos arquivamentos de cada empresa na
<a href="https://www.sec.gov/edgar/search/">SEC EDGAR</a> (10-K/10-Q; 20-F/6-K para STM e VivoPower). VivoPower negociava como VVPR até 16/03/2026, quando passou a VIVO.</p>
</section>

<div class="footer">Fundo LASTRO &amp; Laboratório Momentum ATR — iitauquant • Relatório gerado por scripts/run_tese_ia_infraestrutura.py • Simulação histórica paper-only, sem ordens executadas •
Pesquisa educacional, não é recomendação individual de investimento; revisão humana necessária antes de qualquer decisão.</div>
</main></body></html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="baixa novamente o snapshot via yfinance")
    main(refresh=parser.parse_args().refresh)
