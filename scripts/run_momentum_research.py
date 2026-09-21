"""Executa a pesquisa, simulações, Grid Search, Optuna e estresse do Momentum ATR."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.engine import ExecutionConfig, run_backtest
from backtest.grid_search import GridSearchConfig, GridSearchRunner, atomic_write_parquet
from backtest.optimize import OptunaConfig, optimize_with_optuna
from backtest.statistics import deflated_sharpe_probability, expected_maximum_sharpe
from backtest.stress import StressScenario, run_stress_matrix
from backtest.universe import load_universe_manifest, load_local_universe
from backtest.validation import chronological_split
from strategies.momentum_atr import MomentumATRConfig, validate_ohlc

DATA_DIR = ROOT / "data" / "market"
RESULTS_DIR = ROOT / "results"
CHECKPOINTS_DIR = RESULTS_DIR / "checkpoints"
GRID_DIR = RESULTS_DIR / "grid_search"
OPTUNA_DIR = RESULTS_DIR / "optuna"
STRESS_DIR = RESULTS_DIR / "stress"
BASELINE_DIR = RESULTS_DIR / "baseline"
REPORTS_DIR = RESULTS_DIR / "test_reports"


def ensure_directories() -> None:
    for folder in (DATA_DIR, RESULTS_DIR, CHECKPOINTS_DIR, GRID_DIR, OPTUNA_DIR, STRESS_DIR, BASELINE_DIR, REPORTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def download_and_curate_market_data() -> dict[str, pd.DataFrame]:
    """Baixa da Yahoo Finance e grava Parquet com validação rigorosa de OHLC."""
    ensure_directories()
    manifest_path = ROOT / "config" / "momentum_universe.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets_config = manifest_data.get("assets", {})

    print("[1/5] Verificando e curando dados de mercado locais em data/market/...")
    market_data: dict[str, pd.DataFrame] = {}

    for ticker, meta in assets_config.items():
        destination = (manifest_path.parent / meta["local_file"]).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            try:
                frame = pd.read_parquet(destination)
                if not isinstance(frame.index, pd.DatetimeIndex):
                    date_col = next((c for c in ("date", "datetime", "timestamp", "Date") if c in frame.columns), None)
                    if date_col is not None:
                        frame.index = pd.to_datetime(frame.pop(date_col))
                    elif "index" in frame.columns:
                        frame.index = pd.to_datetime(frame.pop("index"))
                clean = validate_ohlc(frame)
                market_data[ticker] = clean
                print(f"  - {ticker}: Carregado do cache local ({len(clean)} barras)")
                continue
            except Exception as e:
                print(f"  - {ticker}: Cache inválido ({e}), baixando novamente...")

        # Download do Yahoo Finance
        start_date = meta.get("valid_from", "2020-01-01")
        try:
            download = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
            if download.empty:
                print(f"  - {ticker}: [AVISO] Download vazio ou ativo deslistado.")
                continue

            # Se for MultiIndex, extrair o nível correspondente
            if isinstance(download.columns, pd.MultiIndex):
                if ticker in download.columns.get_level_values(1):
                    download = download.xs(ticker, axis=1, level=1)
                elif ticker in download.columns.get_level_values(0):
                    download = download[ticker]

            df = download.rename(columns=lambda c: str(c).strip().lower()).copy()
            df = df.loc[df.index.notna()].sort_index()

            # Garantir colunas obrigatórias
            cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
            df = df[cols].dropna()

            # Assegurar integridade física dos candles
            df["high"] = df[["high", "open", "close"]].max(axis=1)
            df["low"] = df[["low", "open", "close"]].min(axis=1)
            df = df.loc[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]

            if meta.get("valid_to"):
                df = df.loc[df.index <= pd.Timestamp(meta["valid_to"])]

            clean = validate_ohlc(df)
            to_save = clean.reset_index().rename(columns={"index": "date", "Date": "date"})
            atomic_write_parquet(to_save, destination)
            market_data[ticker] = clean
            print(f"  - {ticker}: Salvo {len(clean)} barras em {destination.name}")
        except Exception as exc:
            print(f"  - {ticker}: [ERRO] Não foi possível obter dados: {exc}")

    return market_data


def run_baseline_backtest(data_by_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Executa simulação de referência para os ativos da carteira baseline."""
    print("\n[2/5] Executando Backtest Causal Baseline (sem look-ahead)...")
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    summary_rows = []
    for ticker, data in data_by_ticker.items():
        res = run_backtest(data, strategy, execution)
        
        # Salvar curvas de equity e trades
        equity_file = BASELINE_DIR / f"{ticker}_equity.csv"
        trades_file = BASELINE_DIR / f"{ticker}_trades.csv"
        res.equity_curve.to_csv(equity_file)
        res.trades.to_csv(trades_file, index=False)

        metrics = {
            "ticker": ticker,
            "bars": res.metrics["bars"],
            "total_trades": res.metrics["total_trades"],
            "win_rate": res.metrics["win_rate"],
            "total_return": res.metrics["total_return"],
            "annualized_return": res.metrics["annualized_return"],
            "annualized_volatility": res.metrics["annualized_volatility"],
            "sharpe_ratio": res.metrics["sharpe_ratio"],
            "max_drawdown": res.metrics["max_drawdown"],
            "profit_factor": res.metrics["profit_factor"],
            "exposure": res.metrics["exposure"],
        }
        summary_rows.append(metrics)

    summary_df = pd.DataFrame(summary_rows).sort_values("sharpe_ratio", ascending=False)
    summary_df.to_csv(BASELINE_DIR / "baseline_summary.csv", index=False)
    print(f"  -> Concluído para {len(summary_rows)} ativos. Resumo gravado em results/baseline/baseline_summary.csv")
    return summary_df


def run_grid_search(data_by_ticker: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Executa Grid Search paralelo com partição 70% In-Sample e 30% OOS cego."""
    print("\n[3/5] Executando Grid Search paralelo com checkpoints atômicos...")
    is_data: dict[str, pd.DataFrame] = {}
    oos_data: dict[str, pd.DataFrame] = {}

    for ticker, data in data_by_ticker.items():
        split = chronological_split(data, train_fraction=0.70)
        is_data[ticker] = split.train
        oos_data[ticker] = split.test

    checkpoint_file = CHECKPOINTS_DIR / "grid_search_checkpoint.parquet"
    grid_cfg = GridSearchConfig(
        momentum_windows=(10, 15, 20, 30, 45, 60),
        stop_multipliers=(1.5, 2.0, 2.5, 3.0),
        atr_windows=(14,),
        cost_per_side=0.0015,
        workers=min(os.cpu_count() or 2, 4),
        batch_size=20,
        checkpoint_path=checkpoint_file,
    )

    runner = GridSearchRunner(grid_cfg)
    grid_is = runner.run(is_data)

    grid_is.to_parquet(GRID_DIR / "grid_results_is.parquet", index=False)
    grid_is.to_csv(GRID_DIR / "grid_results_is.csv", index=False)
    print(f"  -> Grid In-Sample concluído: {len(grid_is)} combinações testadas.")

    oos_rows = []
    for ticker, group in grid_is.groupby("ticker"):
        best_is = group.sort_values("sharpe_ratio", ascending=False).iloc[0]
        strategy = MomentumATRConfig(
            momentum_window=int(best_is["momentum_window"]),
            atr_window=int(best_is["atr_window"]),
            stop_multiplier=float(best_is["stop_multiplier"]),
        )
        execution = ExecutionConfig(cost_per_side=0.0015)
        oos_res = run_backtest(oos_data[ticker], strategy, execution)

        oos_rows.append(
            {
                "ticker": ticker,
                "best_momentum_window": int(best_is["momentum_window"]),
                "best_stop_multiplier": float(best_is["stop_multiplier"]),
                "is_sharpe": float(best_is["sharpe_ratio"]),
                "is_dsr": float(best_is["deflated_sharpe_ratio"]),
                "oos_sharpe": float(oos_res.metrics["sharpe_ratio"]),
                "oos_annualized_return": float(oos_res.metrics["annualized_return"]),
                "oos_max_drawdown": float(oos_res.metrics["max_drawdown"]),
                "oos_trades": int(oos_res.metrics["total_trades"]),
                "oos_win_rate": float(oos_res.metrics["win_rate"]),
            }
        )

    oos_df = pd.DataFrame(oos_rows).sort_values("oos_sharpe", ascending=False)
    oos_df.to_csv(GRID_DIR / "oos_evaluation.csv", index=False)
    print("  -> Avaliação cega OOS concluída e salva em results/grid_search/oos_evaluation.csv")
    return grid_is, oos_df


def run_optuna_comparison(data_by_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Executa otimização Bayesiana local com Optuna e compara com o Grid Search."""
    print("\n[4/5] Executando otimização Bayesiana com Optuna (local, sem rede)...")
    optuna_rows = []
    
    for ticker, data in data_by_ticker.items():
        split = chronological_split(data, train_fraction=0.70)
        cfg = OptunaConfig(n_trials=40, seed=42)
        study, trials_df = optimize_with_optuna(split.train, config=cfg)

        trials_file = OPTUNA_DIR / f"{ticker}_trials.csv"
        trials_df.to_csv(trials_file, index=False)

        best = study.best_trial
        optuna_rows.append(
            {
                "ticker": ticker,
                "best_trial": best.number,
                "best_sharpe_is": best.value,
                "momentum_window": best.params["momentum_window"],
                "stop_multiplier": best.params["stop_multiplier"],
            }
        )

    optuna_summary = pd.DataFrame(optuna_rows).sort_values("best_sharpe_is", ascending=False)
    optuna_summary.to_csv(OPTUNA_DIR / "optuna_summary.csv", index=False)
    print("  -> Optuna concluído. Resumo gravado em results/optuna/optuna_summary.csv")
    return optuna_summary


def run_stress_analysis(data_by_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Roda matriz de estresse com slippage adicional e comissões elevadas."""
    print("\n[5/5] Executando Matriz de Estresse e Fricção Adicional...")
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    
    scenarios = [
        StressScenario("baseline_15bps", cost_per_side=0.0015, stop_slippage=0.0),
        StressScenario("slippage_20bps", cost_per_side=0.0015, stop_slippage=0.0020),
        StressScenario("stress_severe_50bps", cost_per_side=0.0030, stop_slippage=0.0050),
    ]

    universes = {"survivors": tuple(data_by_ticker.keys())}
    stress_results = run_stress_matrix(data_by_ticker, universes, strategy_config=strategy, scenarios=scenarios)
    stress_results.to_csv(STRESS_DIR / "stress_matrix.csv", index=False)
    print("  -> Matriz de estresse gravada em results/stress/stress_matrix.csv")
    return stress_results


def build_manifest(summary_df: pd.DataFrame, oos_df: pd.DataFrame) -> None:
    """Gera manifesto de execução para auditoria e reprodutibilidade."""
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project": "momentum-atr-laboratory",
        "system": "paper-only",
        "execution_rules": {
            "entry_execution": "open_next_bar (t+1)",
            "exit_momentum": "open_next_bar (t+1)",
            "stop_loss": "atr_trailing_ratchet",
            "gap_below_stop": "filled_at_open",
            "cost_per_side": 0.0015,
        },
        "assets_tested": list(summary_df["ticker"]),
        "median_sharpe_is": float(summary_df["sharpe_ratio"].median()),
        "median_sharpe_oos": float(oos_df["oos_sharpe"].median()),
        "governance_note": "OMS paper simulation only. Sem rotas de corretoras reais.",
    }
    manifest_path = RESULTS_DIR / "manifesto_momentum.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifesto de auditoria gerado em {manifest_path}")


def main() -> None:
    print("=" * 70)
    print("INICIANDO LABORATÓRIO QUANTITATIVO MOMENTUM ATR")
    print("=" * 70)
    
    market_data = download_and_curate_market_data()
    baseline_tickers = [t for t in ("PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "WEGE3.SA", "RENT3.SA", "PRIO3.SA", "VBBR3.SA", "SMTO3.SA", "RADL3.SA") if t in market_data]
    
    if not baseline_tickers:
        print("Nenhum ativo disponível para backtest.")
        sys.exit(1)

    baseline_data = {t: market_data[t] for t in baseline_tickers}
    summary_df = run_baseline_backtest(baseline_data)
    grid_is, oos_df = run_grid_search(baseline_data)
    run_optuna_comparison(baseline_data)
    run_stress_analysis(baseline_data)
    build_manifest(summary_df, oos_df)
    
    print("\n" + "=" * 70)
    print("LABORATÓRIO CONCLUÍDO COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    main()
