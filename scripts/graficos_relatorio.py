"""Gera os gráficos do relatório final a partir dos artefatos já auditados.

Um gráfico por argumento. Cada figura existe para sustentar uma afirmação
específica do relatório; nenhuma é decorativa.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant_fund.risk_overlay import RiskOverlayConfig  # noqa: E402

DATA = ROOT / "dados"
TABLES = ROOT / "resultados" / "tabelas"
FIGURES = ROOT / "resultados" / "graficos"
CFG = RiskOverlayConfig()

# Paleta validada para daltonismo (ver scripts/validate_palette.js do guia de dataviz):
# separação CVD ΔE 9.2 no pior par, visão normal 24.0. Cinzas são referência, não série.
INK = "#12161c"
MUTED = "#6b7280"
GRID = "#e3e5e8"
SURFACE = "#ffffff"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RED = "#c2413b"
SLATE = "#9aa3ae"

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Lato", "Liberation Sans", "DejaVu Sans"],
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "legend.frameon": False,
        "savefig.facecolor": SURFACE,
        "savefig.bbox": "tight",
    }
)


def save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / name, dpi=200, pad_inches=0.16)
    plt.close(fig)
    print(f"  {name}")


def br(value: float, decimals: int = 2, signed: bool = False) -> str:
    """Formata número na convenção brasileira com vírgula decimal."""
    text = f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"
    return text.replace(".", ",")


def pct_br(value: float, decimals: int = 1, signed: bool = False) -> str:
    return br(value * 100, decimals, signed) + "%"


def pct(axis, decimals: int = 0) -> None:
    axis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: pct_br(v, decimals)))


def load() -> dict:
    prices = pd.read_csv(DATA / "precos_mensais_ajustados.csv", index_col=0)
    prices.index = pd.PeriodIndex(prices.index, freq="M")
    factors = pd.read_csv(DATA / "fatores_fama_french_mensais.csv", index_col=0)
    factors.index = pd.PeriodIndex(factors.index, freq="M")
    pit_path = DATA / "macro_point_in_time_mensal.csv"
    pit = pd.read_csv(pit_path, index_col="mes")
    pit.index = pd.PeriodIndex(pit.index, freq="M")
    required = {
        "BAA10Y_z_36_point_in_time",
        "NFCI_z_36_point_in_time",
        "BAA10Y_state_point_in_time",
        "NFCI_state_point_in_time",
        "derisk_applied_point_in_time",
    }
    missing = required.difference(pit.columns)
    if missing:
        raise ValueError(f"{pit_path.name}: colunas point-in-time ausentes: {sorted(missing)}")
    if pit.index.has_duplicates or not pit.index.is_monotonic_increasing:
        raise ValueError(f"{pit_path.name}: meses devem ser únicos e crescentes")

    returns = prices.pct_change(fill_method=None)
    panel = returns.dropna(subset=["VFMF", "VB", "BIL", "SPY"])
    states, zs = {}, {}
    for label, sid in {"credito": "BAA10Y", "condicoes": "NFCI"}.items():
        zs[label] = pd.to_numeric(
            pit[f"{sid}_z_36_point_in_time"], errors="raise"
        ).rename(label)
        state_signal = pd.to_numeric(
            pit[f"{sid}_state_point_in_time"], errors="raise"
        )
        states[label] = state_signal.shift(1).reindex(panel.index).fillna(0).astype(int)

    derisk = pd.to_numeric(
        pit["derisk_applied_point_in_time"], errors="raise"
    ).reindex(panel.index).fillna(0.0)
    reconstructed = CFG.max_derisk * (states["credito"] + states["condicoes"]) / 2
    if not np.allclose(derisk, reconstructed, rtol=0.0, atol=1e-12):
        raise ValueError("de-risking PIT diverge dos estados defasados dos dois eixos")

    return {
        "panel": panel,
        "factors": factors,
        "z": zs,
        "states": states,
        "derisk": derisk,
        "pit": pit,
    }


def cost(weights: pd.DataFrame) -> pd.Series:
    return (weights.diff().abs().sum(axis=1) / 2).fillna(0.0) * 10 / 10_000


# --------------------------------------------------------------------------- 1
def fig_ponto_cego(ctx) -> None:
    """O gatilho de crédito não vê um choque de taxa, usando vintages reais."""
    panel, z = ctx["panel"], ctx["z"]
    idx = panel.index.to_timestamp()
    wealth = (1 + panel["SPY"]).cumprod()
    drawdown = wealth / wealth.cummax() - 1

    fig, (ax0, ax1) = plt.subplots(
        2, 1, figsize=(11.4, 5.6), sharex=True, gridspec_kw={"height_ratios": [1, 1.85], "hspace": 0.16}
    )
    ax0.fill_between(idx, drawdown, 0, color=SLATE, alpha=0.55, lw=0)
    ax0.plot(idx, drawdown, color=MUTED, lw=1.2)
    ax0.set_ylabel("Drawdown\ndo mercado", fontsize=10.5)
    pct(ax0.yaxis)
    ax0.set_ylim(drawdown.min() * 1.18, 0.012)
    ax0.grid(axis="y", alpha=0.6)
    ax0.set_title("Dados disponíveis na época: crédito não capturou o choque de juros", pad=10)

    ax1.axhline(CFG.stress_entry_z, color=RED, ls="--", lw=1.3, zorder=1)
    ax1.axhline(0, color=GRID, lw=1, zorder=1)
    ax1.plot(idx, z["credito"].reindex(panel.index), color=BLUE, lw=2.1, zorder=3)
    ax1.plot(idx, z["condicoes"].reindex(panel.index), color=ORANGE, lw=2.1, zorder=3)
    ax1.set_ylabel("z-score (36 meses)", fontsize=10.5)
    ax1.grid(axis="y", alpha=0.6)
    ax1.set_ylim(-2.6, 5.6)

    ax1.text(pd.Timestamp("2018-05"), CFG.stress_entry_z + 0.22, "limiar de estresse (z = 1,0)",
             color=RED, fontsize=10, fontweight="bold")
    ax1.text(pd.Timestamp("2019-02"), 3.5, "Crédito\n(spread Baa - Treasury 10a)",
             color=BLUE, fontsize=11, fontweight="bold", ha="center")
    ax1.text(pd.Timestamp("2024-10"), 2.2, "Condições financeiras\n(índice amplo)",
             color=ORANGE, fontsize=11, fontweight="bold", ha="center")

    for a in (ax0, ax1):
        a.axvspan(pd.Timestamp("2022-01"), pd.Timestamp("2023-01"), color=RED, alpha=0.07, lw=0, zorder=0)
    year_2022 = pd.period_range("2022-01", "2022-12", freq="M")
    credit_2022 = z["credito"].reindex(year_2022)
    peak_month = credit_2022.idxmax()
    peak_credit = credit_2022.max()
    market_dd_2022 = drawdown.reindex(panel.index).reindex(year_2022).min()
    ax1.annotate(
        f"2022: mercado {pct_br(market_dd_2022, 0)};\ncrédito PIT máx. z = {br(peak_credit, 2)}",
        xy=(peak_month.to_timestamp(), peak_credit), xytext=(pd.Timestamp("2022-11"), -2.1),
        color=INK, fontsize=10.5, fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2, connectionstyle="arc3,rad=-0.25"),
    )
    ax1.annotate(
        "2020: os dois eixos acendem",
        xy=(pd.Timestamp("2020-04"), 4.6), xytext=(pd.Timestamp("2020-10"), 4.9),
        color=INK, fontsize=10.5, fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2),
    )
    ax1.text(
        0.5,
        -0.20,
        "Cada ponto usa a vintage disponível no fechamento daquele mês (ALFRED); sem revisão retroativa.",
        transform=ax1.transAxes,
        ha="center",
        fontsize=9.5,
        color=MUTED,
        style="italic",
    )
    save(fig, "R1_ponto_cego.png")


# --------------------------------------------------------------------------- 2
def fig_atribuicao(ctx) -> None:
    """De onde veio o desempenho abaixo do benchmark."""
    attr = pd.read_csv(TABLES / "atribuicao_vs_benchmark.csv", index_col=0)["pp_ao_ano"] * 100
    labels = {
        "selecao_sleeve1": "Seleção\nSleeve 1",
        "selecao_sleeve2": "Seleção\nSleeve 2",
        "overlay_regime": "Overlay\nde regime",
        "custos": "Custos",
    }
    order = ["selecao_sleeve1", "selecao_sleeve2", "overlay_regime", "custos"]
    values = [attr[k] for k in order]
    colors = [SLATE, SLATE, ORANGE, SLATE]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars = ax.bar([labels[k] for k in order], values, color=colors, width=0.62, zorder=3)
    for rect, value in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value - 0.09, br(value, 2, signed=True),
                ha="center", va="top", fontsize=12, fontweight="bold", color=INK)
    ax.axhline(0, color=INK, lw=1.1)
    ax.set_ylabel("pontos percentuais ao ano")
    ax.set_ylim(min(values) * 1.32, 0.30)
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: br(v, 1)))
    ax.grid(axis="y", alpha=0.6, zorder=0)
    ax.set_title(f"Diferença vs. benchmark: {br(sum(values), 2, signed=True)} pp ao ano", pad=12)
    ax.text(0.5, -0.19, "A maior perda isolada veio da única peça inteiramente sob nosso controle.",
            transform=ax.transAxes, ha="center", fontsize=10.5, color=MUTED, style="italic")
    save(fig, "R2_atribuicao.png")


# --------------------------------------------------------------------------- 3
def fig_curvas(ctx) -> None:
    """Curvas de capital com sinais reconstruídos por vintage ALFRED."""
    panel, states = ctx["panel"], ctx["states"]
    idx = panel.index
    credit_only = states["credito"]
    graded = ctx["derisk"]

    def fund(derisk):
        w = pd.DataFrame({"VFMF": 1 / 3, "VB": (1 - derisk) / 3, "BIL": (1 + derisk) / 3}, index=idx)
        return (w * panel[["VFMF", "VB", "BIL"]]).sum(axis=1) - cost(w)

    series = {
        "Benchmark 2/3 SPY + 1/3 BIL": ((2 / 3) * panel["SPY"] + (1 / 3) * panel["BIL"], SLATE, 2.0, "--"),
        "LASTRO - capital sem overlay": (fund(pd.Series(0.0, index=idx)), INK, 2.4, "-"),
        "LASTRO - especificação original": (fund(credit_only), ORANGE, 2.2, "-"),
        "LASTRO - especificação revisada": (fund(graded), BLUE, 2.6, "-"),
    }
    fig, ax = plt.subplots(figsize=(11.4, 4.9))
    ts = idx.to_timestamp()
    for name, (ret, color, lw, ls) in series.items():
        wealth = (1 + ret).cumprod()
        ax.plot(ts, wealth, color=color, lw=lw, ls=ls, zorder=3)
        ax.text(ts[-1] + pd.Timedelta(days=26), wealth.iloc[-1], f" {br(wealth.iloc[-1])}x",
                color=color, fontsize=11.5, fontweight="bold", va="center")
    ax.axhline(1, color=GRID, lw=1)
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: br(v, 1)))
    ax.set_ylabel("Crescimento de US$ 1")
    ax.grid(axis="y", alpha=0.6, zorder=0)
    ax.set_xlim(ts[0], ts[-1] + pd.Timedelta(days=260))
    ax.legend(list(series), loc="upper left", fontsize=11)
    ax.set_title(
        "Curvas de capital - ETFs, sinais ALFRED point-in-time e custos de 10 bps",
        pad=10,
    )
    save(fig, "R3_curvas.png")


# --------------------------------------------------------------------------- 4
def fig_robustez(ctx) -> None:
    """Painel dos gates PIT e estatísticos, sem transformar exploração em prova."""
    audit = json.loads((ROOT / "resultados" / "auditoria_vintages_macro.json").read_text())
    validation = json.loads((ROOT / "resultados" / "validacao_estatistica.json").read_text())
    grid = pd.read_csv(TABLES / "sensibilidade_overlay.csv")
    panel = ctx["panel"]
    base_wealth = (1 + panel["VB"]).cumprod()
    base_dd = (base_wealth / base_wealth.cummax() - 1).min()
    base_excess = panel["VB"] - panel["BIL"]
    base_sharpe = base_excess.mean() / base_excess.std(ddof=1) * np.sqrt(12)
    better_dd = float((grid["max_drawdown"] > base_dd).mean())
    better_sharpe = float((grid["Sharpe"] > base_sharpe).mean())

    sample = audit["amostra_backtest"]
    changed = audit["meses_com_derisk_aplicado_diferente"]
    bootstrap = validation["bootstrap_bloco_6_media_ativa_anual"]
    dsr = validation["deflated_sharpe_ratio"]
    psr = validation["probabilistic_sharpe_ratio"]
    placebo_sharpe = validation["percentis_placebo"]["sharpe"]

    cards = [
        (
            "VINTAGES ALFRED",
            f"{changed} / {sample['meses']}",
            "meses mudaram o de-risking\nvs. a vintage final",
            BLUE,
        ),
        (
            f"GRID · {len(grid)} CONFIGURAÇÕES",
            f"{pct_br(better_dd, 0)} / {pct_br(better_sharpe, 0)}",
            "melhoram drawdown / Sharpe\nvs. VB sem overlay",
            ORANGE,
        ),
        (
            f"DSR · {validation['tentativas_grid']} TENTATIVAS",
            pct_br(dsr, 2),
            f"gate ≥ 95%: REPROVADO\nPSR = {pct_br(psr, 2)}",
            RED,
        ),
        (
            "BOOTSTRAP + PLACEBOS",
            f"{pct_br(bootstrap['ci_lower'], 1)} a {pct_br(bootstrap['ci_upper'], 1)}",
            f"IC95% do alfa anual\nSharpe no {placebo_sharpe:.0f}º pct. placebo",
            RED,
        ),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 3.3))
    for ax, (heading, value, note, color) in zip(axes.flat, cards):
        ax.set_axis_off()
        card = mpl.patches.FancyBboxPatch(
            (0.02, 0.06),
            0.96,
            0.88,
            boxstyle="round,pad=0.018,rounding_size=0.035",
            transform=ax.transAxes,
            facecolor=SURFACE,
            edgecolor=GRID,
            linewidth=1.2,
        )
        ax.add_patch(card)
        ax.add_patch(
            mpl.patches.Rectangle(
                (0.02, 0.06), 0.018, 0.88, transform=ax.transAxes, color=color, lw=0
            )
        )
        ax.text(0.08, 0.79, heading, transform=ax.transAxes, color=color,
                fontsize=8.5, fontweight="bold", va="top")
        ax.text(0.08, 0.52, value, transform=ax.transAxes, color=INK,
                fontsize=17, fontweight="bold", va="center")
        ax.text(0.08, 0.13, note, transform=ax.transAxes, color=MUTED,
                fontsize=8.5, va="bottom", linespacing=1.25)

    fig.suptitle("Robustez: a reconstrução PIT passa; a hipótese de alfa, não", y=1.02)
    fig.text(
        0.5,
        0.005,
        "Testes exploratórios in-sample; o gate exige DSR ≥ 95% e não substitui holdout.",
        ha="center",
        fontsize=8.3,
        color=MUTED,
        style="italic",
    )
    fig.subplots_adjust(hspace=0.16, wspace=0.08, bottom=0.08, top=0.90)
    save(fig, "R4_seguro.png")


# --------------------------------------------------------------------------- 5
def fig_duration(ctx) -> None:
    """No choque de juros, duration não é refúgio; é o choque."""
    path = DATA / "refugio_2022.csv"
    if path.exists():
        data = pd.read_csv(path, index_col=0)["retorno_2022_2023"]
    else:  # coleta única, depois versionada
        import json
        rows = {}
        for ticker in ("BIL", "SHY", "IEF", "TLT"):
            url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                   "?range=20y&interval=1mo&events=div%2Csplit")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            res = json.loads(urllib.request.urlopen(req, timeout=40).read())["chart"]["result"][0]
            s = pd.Series(res["indicators"]["adjclose"][0]["adjclose"],
                          index=pd.to_datetime(res["timestamp"], unit="s")).dropna()
            s.index = s.index.to_period("M")
            s = s[~s.index.duplicated(keep="last")]
            window = s.pct_change(fill_method=None).loc[pd.Period("2022-01"): pd.Period("2023-10")]
            rows[ticker] = (1 + window).prod() - 1
        data = pd.Series(rows, name="retorno_2022_2023")
        data.to_csv(path, index_label="instrumento")

    labels = {"BIL": "BIL · T-bill 1-3m", "SHY": "SHY · Treasury 1-3a",
              "IEF": "IEF · Treasury 7-10a", "TLT": "TLT · Treasury 20a+"}
    keys = list(labels)[::-1]
    values = [data[t] for t in keys]
    colors = [BLUE if v > 0 else RED for v in values]

    fig, ax = plt.subplots(figsize=(7.4, 2.75))
    bars = ax.barh([labels[k] for k in keys], values, color=colors, height=0.62, zorder=3)
    for rect, value in zip(bars, values):
        off = 0.014 if value > 0 else -0.014
        ax.text(value + off, rect.get_y() + rect.get_height() / 2, pct_br(value, 1, signed=True),
                va="center", ha="left" if value > 0 else "right",
                fontsize=12, fontweight="bold", color=INK)
    ax.axvline(0, color=INK, lw=1.1)
    pct(ax.xaxis, 0)
    ax.set_xlim(min(values) - 0.10, max(values) + 0.07)
    ax.grid(axis="x", alpha=0.6, zorder=0)
    ax.tick_params(labelsize=11)
    ax.set_title("Refúgio no aperto monetário · 2022-01 a 2023-10", pad=9, fontsize=13)
    save(fig, "R5_duration.png")


# --------------------------------------------------------------------------- 6
def fig_diversificacao(ctx) -> None:
    """A correlação medida errada refuta uma tese que não foi testada."""
    data = pd.read_csv(TABLES / "diversificacao_por_medida.csv", index_col=0)["correlacao"]
    labels = ["Retorno total\n(o que reportamos antes)",
              "Retorno ativo\nvs. mercado",
              "Resíduo após\nmercado e tamanho"]
    values = [data["retorno_total"], data["retorno_ativo_vs_SPY"],
              data["residual_pos_mercado_e_tamanho"]]
    colors = [SLATE, SLATE, BLUE]

    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], height=0.58, zorder=3)
    for rect, value in zip(bars, values[::-1]):
        ax.text(value - 0.02, rect.get_y() + rect.get_height() / 2, br(value),
                ha="right", va="center", fontsize=13, fontweight="bold", color=SURFACE)
    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: br(v, 1)))
    ax.set_xlim(0, 1.04)
    ax.set_xlabel("Correlação entre os dois motores de retorno")
    ax.grid(axis="x", alpha=0.6, zorder=0)
    ax.tick_params(labelsize=10.5)
    ax.set_title("A mesma carteira, três medidas de correlação", pad=10)
    save(fig, "R6_diversificacao.png")


# --------------------------------------------------------------------------- 7
def fig_premios(ctx) -> None:
    """O prêmio que a estratégia compra não pagou na janela testada."""
    ctx_tab = pd.read_csv(TABLES / "contexto_premios_fator.csv", index_col=0)
    order = ["SMB", "HML", "RMW", "CMA", "Mom"]
    x = np.arange(len(order))
    width = 0.38
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    ax.bar(x - width / 2, ctx_tab.loc[order, "media_anual_1963_2017"], width,
           color=SLATE, zorder=3, label="Média 1963-2017")
    ax.bar(x + width / 2, ctx_tab.loc[order, "media_anual_na_amostra"], width,
           color=BLUE, zorder=3, label="Janela do backtest (2018-2026)")
    ax.axhline(0, color=INK, lw=1.1)
    ax.set_xticks(x, order)
    pct(ax.yaxis, 0)
    ax.set_ylim(-0.036, 0.098)
    ax.grid(axis="y", alpha=0.6, zorder=0)
    ax.legend(fontsize=10.5, loc="upper left", ncol=2, columnspacing=1.1, handlelength=1.2)
    ax.set_title("Prêmio anual dos fatores comprados pelo Sleeve 1", pad=10)
    ax.text(0.5, -0.20, "Tamanho e valor entregaram prêmio negativo exatamente na janela testada.",
            transform=ax.transAxes, ha="center", fontsize=10.5, color=MUTED, style="italic")
    save(fig, "R7_premios.png")


def main() -> int:
    ctx = load()
    print("gerando figuras:")
    fig_ponto_cego(ctx)
    fig_atribuicao(ctx)
    fig_curvas(ctx)
    fig_robustez(ctx)
    fig_duration(ctx)
    fig_diversificacao(ctx)
    fig_premios(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
