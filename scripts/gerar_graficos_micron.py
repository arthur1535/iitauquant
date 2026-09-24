"""Geração de gráficos técnicos e quantitativos de alta resolução para Micron Technology (MUTC34 / MU)."""

from __future__ import annotations

import base64
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "market"
OUTPUT_DIR = ROOT / "results" / "micron_research"
RELATORIOS_DIR = ROOT / "relatorios"
GRAFICOS_DIR = RELATORIOS_DIR / "graficos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GRAFICOS_DIR.mkdir(parents=True, exist_ok=True)


def plot_trade_setup():
    df_mutc = pd.read_csv(DATA_DIR / "MUTC34.SA.csv", index_col=0, parse_dates=True)
    df_recent = df_mutc.loc["2026-01-01":].copy()

    df_recent["sma20"] = df_recent["close"].rolling(20).mean()
    df_recent["sma50"] = df_recent["close"].rolling(50).mean()

    # Cálculo do ATR de 14 dias
    high_low = df_recent["high"] - df_recent["low"]
    high_close = (df_recent["high"] - df_recent["close"].shift(1)).abs()
    low_close = (df_recent["low"] - df_recent["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_recent["atr14"] = tr.rolling(14).mean()
    df_recent["stop25"] = df_recent["close"] - 2.5 * df_recent["atr14"]
    df_recent["stop20"] = df_recent["close"] - 2.0 * df_recent["atr14"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor("#ffffff")
    ax1.set_facecolor("#fafbfc")
    ax2.set_facecolor("#fafbfc")

    # Preço e Médias
    ax1.plot(df_recent.index, df_recent["close"], label="MUTC34 (Fechamento B3)", color="#0f172a", lw=2.2)
    ax1.plot(df_recent.index, df_recent["sma20"], label="Média Móvel 20d (R$ 843,59)", color="#0284c7", lw=1.5, ls="--")
    ax1.plot(df_recent.index, df_recent["sma50"], label="Média Móvel 50d (R$ 802,59)", color="#f59e0b", lw=1.5, ls="--")

    last_price = df_recent["close"].iloc[-1]
    last_date = df_recent.index[-1]
    last_stop25 = df_recent["stop25"].iloc[-1]
    last_stop20 = df_recent["stop20"].iloc[-1]

    # Níveis de Alvos e Resistências
    ax1.axhline(980.00, color="#10b981", lw=1.5, ls=":", label="Alvo 1: R$ 980,00 (+5,8%)")
    ax1.axhline(1083.08, color="#059669", lw=1.8, ls=":", label="Alvo 2: R$ 1.083,08 (+16,9% Topo 52 Semanas)")
    ax1.axhline(1200.00, color="#047857", lw=2.0, ls=":", label="Alvo 3: R$ 1.200,00 (+29,5% Superciclo HBM)")

    # Stops
    ax1.scatter([last_date], [last_stop25], color="#dc2626", s=100, zorder=5, label=f"Trailing Stop 2.5x ATR (R$ {last_stop25:.2f})")
    ax1.scatter([last_date], [last_stop20], color="#ea580c", s=100, zorder=5, label=f"Stop Curto 2.0x ATR (R$ {last_stop20:.2f})")

    # Área de Suporte Dinâmico
    ax1.fill_between(df_recent.index, df_recent["stop25"], df_recent["close"], color="#0284c7", alpha=0.08, label="Canal de Proteção ATR")

    # Anotação Preço Atual
    ax1.annotate(
        f"Preço Atual: R$ {last_price:.2f}\n(Pico em Confluência de MMs)",
        xy=(last_date, last_price),
        xytext=(last_date - pd.Timedelta(days=45), last_price + 35),
        arrowprops=dict(facecolor="#059669", arrowstyle="->", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.4", fc="#d1fae5", ec="#059669", lw=1.5),
        fontweight="bold",
        fontsize=10,
    )

    ax1.set_title("Micron Technology BDR (MUTC34.SA) — Mapa Tático da Posição e Gestão de Risco", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Cotação em Reais (R$)", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # Gráfico inferior de Volume
    colors = ["#10b981" if c >= o else "#ef4444" for c, o in zip(df_recent["close"], df_recent["open"])]
    ax2.bar(df_recent.index, df_recent["volume"] / 1000, color=colors, alpha=0.75, width=0.8)
    ax2.set_ylabel("Vol (Milhares)", fontsize=10, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b/%y"))

    plt.tight_layout()
    trade_path = OUTPUT_DIR / "mutc34_trade_setup.png"
    plt.savefig(trade_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Salvo: {trade_path}")


def plot_equity_curves():
    eq_mu = pd.read_csv(OUTPUT_DIR / "MU_equity.csv", index_col=0, parse_dates=True)
    eq_mutc = pd.read_csv(OUTPUT_DIR / "MUTC34_equity.csv", index_col=0, parse_dates=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [2.5, 1.5]})
    fig.patch.set_facecolor("#ffffff")
    ax1.set_facecolor("#fafbfc")
    ax2.set_facecolor("#fafbfc")

    # Normalizar para Base 100
    eq_mu_norm = (eq_mu["equity"] / eq_mu["equity"].iloc[0]) * 100
    eq_mutc_norm = (eq_mutc["equity"] / eq_mutc["equity"].iloc[0]) * 100

    ax1.plot(eq_mu_norm.index, eq_mu_norm, label="MU — Momentum ATR (Sistemático iitauquant)", color="#0284c7", lw=2.2)
    ax1.plot(eq_mutc_norm.index, eq_mutc_norm, label="MUTC34.SA — Momentum ATR (BDR em Reais)", color="#10b981", lw=2.0)

    ax1.set_title("Curva de Patrimônio (Base 100) — Estratégia Momentum ATR em Micron Technology", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Patrimônio Acumulado (Base 100)", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=10, framealpha=0.9)

    # Drawdowns
    ax2.plot(eq_mu.index, eq_mu["drawdown"] * 100, label="Drawdown MU Mom ATR (Max: -75,2%)", color="#0284c7", lw=1.5)
    ax2.plot(eq_mutc.index, eq_mutc["drawdown"] * 100, label="Drawdown MUTC34 Mom ATR (Max: -56,6%)", color="#10b981", lw=1.5)

    ax2.set_title("Perfil de Drawdown: Preservação de Capital no Inverno de Semicondutores", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Ano", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    eq_path = OUTPUT_DIR / "micron_equity_drawdown.png"
    plt.savefig(eq_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Salvo: {eq_path}")


def plot_peers_comparison():
    tickers = ["MU", "NVDA", "SMH", "SOXX", "QQQ", "SPY"]
    series = {}
    for t in tickers:
        p = DATA_DIR / f"{t}.csv"
        if p.exists():
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            series[t] = df["close"]

    df_comp = pd.DataFrame(series).dropna()
    df_comp_norm = (df_comp / df_comp.iloc[0]) * 100

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafbfc")

    colors = {
        "MU": "#0284c7",
        "NVDA": "#10b981",
        "SMH": "#8b5cf6",
        "SOXX": "#f59e0b",
        "QQQ": "#64748b",
        "SPY": "#94a3b8",
    }
    widths = {"MU": 2.5, "NVDA": 2.0, "SMH": 1.6, "SOXX": 1.6, "QQQ": 1.2, "SPY": 1.2}

    for t in tickers:
        if t in df_comp_norm.columns:
            ax.plot(
                df_comp_norm.index,
                df_comp_norm[t],
                label=f"{t} ({df_comp_norm[t].iloc[-1]:.0f})",
                color=colors.get(t, "#333333"),
                lw=widths.get(t, 1.5),
            )

    ax.set_title("Performance Comparativa Acumulada (Base 100, 2020–2026): Micron vs Pares de IA e Semicondutores", fontsize=13, fontweight="bold", pad=15)
    ax.set_ylabel("Crescimento do Capital (Base 100)", fontsize=11, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    peers_path = OUTPUT_DIR / "micron_peers_comparison.png"
    plt.savefig(peers_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Salvo: {peers_path}")


def main():
    plot_trade_setup()
    plot_equity_curves()
    plot_peers_comparison()


if __name__ == "__main__":
    main()
