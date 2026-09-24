"""Gráficos históricos de Micron a partir do snapshot local, sem buscar dados."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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
    # Calcular antes do recorte preserva o aquecimento das janelas.
    df_mutc["sma20"] = df_mutc["close"].rolling(20).mean()
    df_mutc["sma50"] = df_mutc["close"].rolling(50).mean()

    # Cálculo do ATR de 14 dias
    high_low = df_mutc["high"] - df_mutc["low"]
    high_close = (df_mutc["high"] - df_mutc["close"].shift(1)).abs()
    low_close = (df_mutc["low"] - df_mutc["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_mutc["atr14"] = tr.rolling(14).mean()
    df_mutc["distance25"] = df_mutc["close"] - 2.5 * df_mutc["atr14"]
    df_mutc["distance20"] = df_mutc["close"] - 2.0 * df_mutc["atr14"]
    df_recent = df_mutc.loc["2026-01-01":].copy()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor("#ffffff")
    ax1.set_facecolor("#fafbfc")
    ax2.set_facecolor("#fafbfc")

    # Preço e Médias
    ax1.plot(df_recent.index, df_recent["close"], label="MUTC34 (coluna close do snapshot)", color="#0f172a", lw=2.2)
    ax1.plot(df_recent.index, df_recent["sma20"], label=f"Média móvel 20 pregões (R$ {df_recent['sma20'].iloc[-1]:.2f})", color="#0284c7", lw=1.5, ls="--")
    ax1.plot(df_recent.index, df_recent["sma50"], label=f"Média móvel 50 pregões (R$ {df_recent['sma50'].iloc[-1]:.2f})", color="#f59e0b", lw=1.5, ls="--")

    last_price = df_recent["close"].iloc[-1]
    last_date = df_recent.index[-1]
    last_distance25 = df_recent["distance25"].iloc[-1]
    last_distance20 = df_recent["distance20"].iloc[-1]

    # Referência histórica de preço; não é alvo ou estimativa de valor justo.
    high_252 = df_mutc["high"].tail(252).max()
    ax1.axhline(high_252, color="#64748b", lw=1.5, ls=":", label=f"Máxima dos últimos 252 pregões (R$ {high_252:.2f})")

    # Distâncias pontuais: não são o stop cumulativo do motor de backtest.
    ax1.scatter([last_date], [last_distance25], color="#dc2626", s=100, zorder=5, label=f"Preço − 2,5 × ATR14: hipótese (R$ {last_distance25:.2f})")
    ax1.scatter([last_date], [last_distance20], color="#ea580c", s=100, zorder=5, label=f"Preço − 2,0 × ATR14: hipótese (R$ {last_distance20:.2f})")

    ax1.fill_between(df_recent.index, df_recent["distance25"], df_recent["close"], color="#0284c7", alpha=0.08, label="Distância ilustrativa de 2,5 × ATR14")

    # Anotação Preço Atual
    ax1.annotate(
        f"Snapshot {last_date:%d/%m/%Y}: R$ {last_price:.2f}",
        xy=(last_date, last_price),
        xytext=(last_date - pd.Timedelta(days=75), last_price + 55),
        arrowprops=dict(facecolor="#059669", arrowstyle="->", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.4", fc="#d1fae5", ec="#059669", lw=1.5),
        fontweight="bold",
        fontsize=10,
    )

    ax1.set_title("MUTC34 — Histórico local e distâncias ATR ilustrativas", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Cotação em Reais (R$)", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # Gráfico inferior de Volume
    colors = ["#10b981" if c >= o else "#ef4444" for c, o in zip(df_recent["close"], df_recent["open"])]
    ax2.bar(df_recent.index, df_recent["volume"] / 1000, color=colors, alpha=0.75, width=0.8)
    ax2.set_ylabel("Vol (Milhares)", fontsize=10, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b/%y"))

    fig.text(0.5, 0.01, "Snapshot local; última barra sem confirmação de encerramento. Distâncias ATR não garantem preço de saída ou perda máxima.", ha="center", fontsize=9)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
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

    ax1.set_title("Simulação histórica local (Base 100) — Momentum ATR em Micron", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Patrimônio Acumulado (Base 100)", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=10, framealpha=0.9)

    # Drawdowns
    ax2.plot(eq_mu.index, eq_mu["drawdown"] * 100, label=f"Drawdown MU (mínimo: {eq_mu['drawdown'].min():.1%})", color="#0284c7", lw=1.5)
    ax2.plot(eq_mutc.index, eq_mutc["drawdown"] * 100, label=f"Drawdown MUTC34 (mínimo: {eq_mutc['drawdown'].min():.1%})", color="#10b981", lw=1.5)

    ax2.set_title("Queda histórica desde o pico da carteira simulada", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Ano", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.text(0.5, 0.01, "MU em USD; MUTC34 em BRL. Custo de 0,15% por lado; caixa sem remuneração. Não representa resultado futuro.", ha="center", fontsize=9)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
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

    ax.set_title(f"Histórico local de preços em USD (Base 100): {df_comp.index[0]:%d/%m/%Y} a {df_comp.index[-1]:%d/%m/%Y}", fontsize=13, fontweight="bold", pad=15)
    ax.set_ylabel("Preço normalizado (Base 100; escala log)", fontsize=11, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.text(0.5, 0.01, "Coluna close dos arquivos locais; sem reinvestimento de dividendos, custos ou impostos. Não é projeção de retorno.", ha="center", fontsize=9)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
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
