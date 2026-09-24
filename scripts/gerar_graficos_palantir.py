"""Geração de gráficos técnicos e quantitativos de alta resolução para Palantir (P2LT34 / PLTR)."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "market"
OUTPUT_DIR = ROOT / "results" / "palantir_research"
RELATORIOS_DIR = ROOT / "relatorios"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_trade_setup():
    df_p2lt = pd.read_csv(DATA_DIR / "P2LT34.SA.csv", index_col=0, parse_dates=True)
    df_recent = df_p2lt.loc["2026-03-01":].copy()

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
    ax1.plot(df_recent.index, df_recent["close"], label="P2LT34 (Fechamento)", color="#0f172a", lw=2.2)
    ax1.plot(df_recent.index, df_recent["sma20"], label="Média Móvel 20d (Curto)", color="#0284c7", lw=1.5, ls="--")
    ax1.plot(df_recent.index, df_recent["sma50"], label="Média Móvel 50d (Médio)", color="#f59e0b", lw=1.5, ls="--")

    # Linha da compra do usuário: R$ 309,03
    user_entry = 309.03
    last_price = df_recent["close"].iloc[-1]
    last_date = df_recent.index[-1]

    ax1.axhline(user_entry, color="#2563eb", lw=2.0, ls="-.", label=f"Entrada Usuário (R$ {user_entry:.2f})")
    ax1.axhline(350.00, color="#10b981", lw=1.6, ls=":", label="Alvo 1: R$ 350,00 (+13,3%)")
    ax1.axhline(373.83, color="#059669", lw=1.8, ls=":", label="Alvo 2: R$ 373,83 (+21,0% Topo Anual)")
    ax1.axhline(420.00, color="#047857", lw=2.0, ls=":", label="Alvo 3: R$ 420,00 (+35,9% Superciclo)")

    # Stop 2.5x ATR e 2.0x ATR
    last_stop25 = df_recent["stop25"].iloc[-1]
    last_stop20 = df_recent["stop20"].iloc[-1]
    ax1.scatter([last_date], [last_stop25], color="#dc2626", s=100, zorder=5, label=f"Trailing Stop 2.5x ATR (R$ {last_stop25:.2f})")
    ax1.scatter([last_date], [last_stop20], color="#ea580c", s=100, zorder=5, label=f"Stop Lucro 2.0x ATR (R$ {last_stop20:.2f})")

    # Área de Lucro Atual do Usuário
    ax1.axhspan(user_entry, last_price, color="#10b981", alpha=0.15, label=f"Lucro Atual (+8,1% / +R$ 25,00)")

    # Anotações
    ax1.annotate(
        f"Preço Atual: R$ {last_price:.2f}\n(+8,1% sobre compra)",
        xy=(last_date, last_price),
        xytext=(last_date - pd.Timedelta(days=28), last_price + 18),
        arrowprops=dict(facecolor="#059669", arrowstyle="->", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.4", fc="#d1fae5", ec="#059669", lw=1.5),
        fontweight="bold",
        fontsize=10,
    )

    ax1.annotate(
        f"Compra: R$ {user_entry:.2f}\n(Gatilho Quant iitauquant)",
        xy=(pd.Timestamp("2026-09-21"), user_entry),
        xytext=(pd.Timestamp("2026-09-21") - pd.Timedelta(days=32), user_entry - 35),
        arrowprops=dict(facecolor="#2563eb", arrowstyle="->", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.4", fc="#dbeafe", ec="#2563eb", lw=1.5),
        fontweight="bold",
        fontsize=10,
    )

    ax1.set_title("Palantir BDR (P2LT34.SA) — Mapa Tático da Posição e Gestão de Risco", fontsize=14, fontweight="bold", pad=15)
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
    trade_path = OUTPUT_DIR / "p2lt34_trade_setup.png"
    plt.savefig(trade_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Salvo: {trade_path}")


def plot_equity_curves():
    # Carregar equity curves geradas pelo backtest
    eq_pltr = pd.read_csv(OUTPUT_DIR / "PLTR_equity.csv", index_col=0, parse_dates=True)
    eq_p2lt = pd.read_csv(OUTPUT_DIR / "P2LT34_equity.csv", index_col=0, parse_dates=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [2.5, 1.5]})
    fig.patch.set_facecolor("#ffffff")
    ax1.set_facecolor("#fafbfc")
    ax2.set_facecolor("#fafbfc")

    # Normalizar para Base 100
    eq_pltr_norm = (eq_pltr["equity"] / eq_pltr["equity"].iloc[0]) * 100
    eq_p2lt_norm = (eq_p2lt["equity"] / eq_p2lt["equity"].iloc[0]) * 100

    ax1.plot(eq_pltr_norm.index, eq_pltr_norm, label="PLTR — Momentum ATR (Sistemático iitauquant)", color="#0284c7", lw=2.2)
    ax1.plot(eq_p2lt_norm.index, eq_p2lt_norm, label="P2LT34.SA — Momentum ATR (BDR em Reais)", color="#8b5cf6", lw=2.0)

    ax1.set_title("Curva de Patrimônio (Base 100) — Estratégia Momentum ATR em Palantir", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Patrimônio Acumulado (Base 100)", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=10, framealpha=0.9)

    # Drawdowns
    ax2.plot(eq_pltr.index, eq_pltr["drawdown"] * 100, label="Drawdown PLTR Mom ATR (Max: -53,5%)", color="#0284c7", lw=1.5)
    ax2.plot(eq_p2lt.index, eq_p2lt["drawdown"] * 100, label="Drawdown P2LT34 Mom ATR (Max: -46,5%)", color="#8b5cf6", lw=1.5)
    ax2.axhline(-84.62, color="#ef4444", ls=":", lw=1.8, label="Drawdown Buy & Hold PLTR (-84,6% Inverno Tech)")

    ax2.set_title("Perfil de Drawdown: Preservação de Capital vs Colapso de Buy & Hold", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Ano", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    eq_path = OUTPUT_DIR / "palantir_equity_drawdown.png"
    plt.savefig(eq_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Salvo: {eq_path}")


def main():
    plot_trade_setup()
    plot_equity_curves()


if __name__ == "__main__":
    main()
