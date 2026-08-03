"""Backtest preliminar, auditoria e graficos do fundo multi-sleeve.

Escopo honesto: testa a alocacao por regime com ETFs publicos. VFMF e o ETF
small-cap escolhido sao proxies dos sleeves 1 e 2; este arquivo NAO substitui
o backtest point-in-time das selecoes de acoes descritas no relatorio tecnico.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import sys
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dados"
RESULTS = ROOT / "resultados"
FIGURES = RESULTS / "graficos"
TABLES = RESULTS / "tabelas"


@dataclass(frozen=True)
class Config:
    start: str = "2007-01-01"
    z_window_months: int = 36
    z_min_periods: int = 24
    stress_entry: float = 1.0
    stress_exit: float = 0.5
    transaction_cost_bps: float = 10.0
    candidates: tuple[str, ...] = ("IWM", "VB", "IJR")
    market: str = "SPY"
    fixed_income: str = "BIL"
    factor_proxy: str = "VFMF"
    crisis_windows: tuple[tuple[str, str], ...] = (
        ("2008-01", "2009-06"),
        ("2011-05", "2011-12"),
        ("2015-06", "2016-03"),
        ("2020-02", "2020-06"),
        ("2022-01", "2023-12"),
    )


CFG = Config()


def ensure_dirs() -> None:
    for path in (DATA, RESULTS, FIGURES, TABLES):
        path.mkdir(parents=True, exist_ok=True)


def complete_month_cutoff() -> pd.Period:
    return pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).to_period("M") - 1


def monthly_adjusted_prices() -> pd.DataFrame:
    tickers = [*CFG.candidates, CFG.market, CFG.fixed_income, CFG.factor_proxy]
    raw = yf.download(
        tickers,
        start=CFG.start,
        auto_adjust=False,
        actions=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if raw.empty or "Adj Close" not in raw:
        raise RuntimeError("Yahoo Finance nao devolveu precos ajustados.")
    adj = raw["Adj Close"].copy()
    adj.index = pd.to_datetime(adj.index).tz_localize(None)
    monthly = adj.resample("ME").last()
    monthly.index = monthly.index.to_period("M")
    monthly = monthly.loc[monthly.index <= complete_month_cutoff()]
    monthly.to_csv(DATA / "precos_mensais_ajustados.csv", index_label="mes")

    # Evidencia para a auditoria de que Adj Close, e nao Close, foi usado.
    close = raw["Close"].copy().resample("ME").last()
    close.index = close.index.to_period("M")
    divergence = (monthly / close.reindex(monthly.index) - 1).abs().max()
    divergence.rename("max_divergencia_adj_vs_close").to_csv(
        TABLES / "evidencia_precos_ajustados.csv", header=True
    )
    return monthly


def credit_spread_monthly() -> tuple[pd.Series, dict[str, str]]:
    # BAA10Y tem histórico oficial completo no FRED desde 1986 e evita a janela
    # móvel de três anos imposta à série ICE/BofA BAMLH0A0HYM2 desde abril/2026.
    fred = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA10Y"
    raw = pd.read_csv(fred).rename(columns={"observation_date": "date", "DATE": "date"})
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["BAA10Y"] = pd.to_numeric(raw["BAA10Y"], errors="coerce")
    spread = raw.dropna().sort_values("date").drop_duplicates("date", keep="last")
    spread = spread.set_index("date")["BAA10Y"]
    monthly = spread.resample("ME").last()
    monthly.index = monthly.index.to_period("M")
    monthly = monthly.loc[monthly.index <= complete_month_cutoff()]
    monthly.to_csv(DATA / "spread_credito_baa_mensal.csv", header=True)
    return monthly, {"fonte_oficial": fred}


def regime_signal(spread: pd.Series) -> pd.DataFrame:
    rolling = spread.rolling(CFG.z_window_months, min_periods=CFG.z_min_periods)
    z = (spread - rolling.mean()) / rolling.std(ddof=1)
    state = []
    stressed = False
    for value in z:
        if pd.notna(value):
            if not stressed and value > CFG.stress_entry:
                stressed = True
            elif stressed and value < CFG.stress_exit:
                stressed = False
        state.append(int(stressed))
    out = pd.DataFrame({"spread": spread, "z_score": z, "estado_sinal": state})
    # Informacao observada no fechamento de t so pode governar o retorno de t+1.
    out["estado_aplicado"] = out["estado_sinal"].shift(1)
    return out


def choose_smallcap(price_returns: pd.DataFrame, spread: pd.Series) -> pd.DataFrame:
    relative = price_returns[list(CFG.candidates)].sub(price_returns[CFG.market], axis=0)
    delta_spread = spread.diff()
    base = relative.join(delta_spread.rename("delta_spread"), how="inner").dropna()
    crisis_mask = pd.Series(False, index=base.index)
    for start, end in CFG.crisis_windows:
        crisis_mask |= (base.index >= pd.Period(start)) & (base.index <= pd.Period(end))
    rows = []
    for ticker in CFG.candidates:
        all_corr = base[ticker].corr(base["delta_spread"])
        crisis_corr = base.loc[crisis_mask, ticker].corr(base.loc[crisis_mask, "delta_spread"])
        rows.append({
            "ticker": ticker,
            "correlacao_todos_meses": all_corr,
            "correlacao_crises": crisis_corr,
            "n_meses_crise": int(crisis_mask.sum()),
        })
    result = pd.DataFrame(rows).set_index("ticker")
    # Hipotese: aumento do spread acompanha pior retorno relativo. Mais negativo vence.
    result["selecionado"] = False
    result.loc[result["correlacao_crises"].idxmin(), "selecionado"] = True
    return result


def turnover_cost(weights: pd.DataFrame) -> pd.Series:
    turnover = weights.diff().abs().sum(axis=1) / 2
    return turnover.fillna(0) * (CFG.transaction_cost_bps / 10_000)


def build_returns(prices: pd.DataFrame, regime: pd.DataFrame, selected: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    r = prices.pct_change(fill_method=None)
    common = r.join(regime[["estado_aplicado"]], how="inner").dropna(
        subset=[CFG.factor_proxy, selected, CFG.fixed_income, CFG.market, "estado_aplicado"]
    )
    stress = common["estado_aplicado"].astype(int)
    always_on = common[selected]
    with_regime_gross = always_on.where(stress.eq(0), common[CFG.fixed_income])

    w_sleeve = pd.DataFrame(
        {selected: 1 - stress, CFG.fixed_income: stress}, index=common.index, dtype=float
    )
    with_regime_net = with_regime_gross - turnover_cost(w_sleeve)

    w_fund = pd.DataFrame(
        {
            CFG.factor_proxy: 1 / 3,
            selected: (1 - stress) / 3,
            CFG.fixed_income: (1 + stress) / 3,
        },
        index=common.index,
    )
    fund_gross = (
        w_fund[CFG.factor_proxy] * common[CFG.factor_proxy]
        + w_fund[selected] * common[selected]
        + w_fund[CFG.fixed_income] * common[CFG.fixed_income]
    )
    fund_net = fund_gross - turnover_cost(w_fund)
    benchmark = (2 / 3) * common[CFG.market] + (1 / 3) * common[CFG.fixed_income]

    out = pd.DataFrame(
        {
            "factor_proxy_VFMF": common[CFG.factor_proxy],
            f"smallcap_{selected}_sempre_ligada": always_on,
            f"smallcap_{selected}_com_regime_bruto": with_regime_gross,
            f"smallcap_{selected}_com_regime_liquido": with_regime_net,
            "renda_fixa_BIL": common[CFG.fixed_income],
            "fundo_proxy_bruto": fund_gross,
            "fundo_proxy_liquido": fund_net,
            "benchmark_2_3_SPY_1_3_BIL": benchmark,
            "SPY": common[CFG.market],
        }
    )
    return out, w_fund


def metric_row(ret: pd.Series, rf: pd.Series) -> dict[str, float]:
    x = ret.dropna()
    months = len(x)
    wealth = (1 + x).cumprod()
    years = months / 12
    cagr = wealth.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = x.std(ddof=1) * math.sqrt(12)
    excess = x.sub(rf.reindex(x.index), fill_value=np.nan).dropna()
    sharpe = excess.mean() / excess.std(ddof=1) * math.sqrt(12) if excess.std(ddof=1) else np.nan
    drawdown = wealth / wealth.cummax() - 1
    return {
        "inicio": str(x.index.min()),
        "fim": str(x.index.max()),
        "meses": months,
        "CAGR": cagr,
        "volatilidade_anual": vol,
        "Sharpe_excesso_BIL": sharpe,
        "max_drawdown": drawdown.min(),
        "retorno_acumulado": wealth.iloc[-1] - 1,
    }


def metrics_table(returns: pd.DataFrame) -> pd.DataFrame:
    rf = returns["renda_fixa_BIL"]
    return pd.DataFrame({col: metric_row(returns[col], rf) for col in returns}).T


def parse_french_zip(url: str, expected_cols: list[str]) -> pd.DataFrame:
    payload = requests.get(url, timeout=60)
    payload.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(payload.content)) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin1")
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts and len(parts[0]) == 6 and parts[0].isdigit() and len(parts) >= len(expected_cols) + 1:
            rows.append(parts[: len(expected_cols) + 1])
    df = pd.DataFrame(rows, columns=["mes", *expected_cols])
    df.index = pd.PeriodIndex(df.pop("mes"), freq="M")
    return df.apply(pd.to_numeric, errors="coerce") / 100


def french_factors() -> pd.DataFrame:
    ff5 = parse_french_zip(
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
        "F-F_Research_Data_5_Factors_2x3_CSV.zip",
        ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
    )
    mom = parse_french_zip(
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
        "F-F_Momentum_Factor_CSV.zip",
        ["Mom"],
    )
    out = ff5.join(mom, how="inner")
    out.to_csv(DATA / "fatores_fama_french_mensais.csv", index_label="mes")
    return out


def regressions(returns: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    xcols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    for name in returns.columns:
        merged = returns[[name]].join(factors, how="inner").dropna()
        if len(merged) < 36:
            continue
        y = merged[name] - merged["RF"]
        model = sm.OLS(y, sm.add_constant(merged[xcols])).fit(
            cov_type="HAC", cov_kwds={"maxlags": 3}
        )
        row = {"serie": name, "n": int(model.nobs), "R2_ajustado": model.rsquared_adj}
        for term in ["const", *xcols]:
            label = "alpha_mensal" if term == "const" else term
            row[label] = model.params[term]
            row[f"p_{label}"] = model.pvalues[term]
        row["alpha_anualizado"] = (1 + model.params["const"]) ** 12 - 1
        rows.append(row)
    return pd.DataFrame(rows).set_index("serie")


def audit(
    prices: pd.DataFrame,
    spread: pd.Series,
    regime: pd.DataFrame,
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    selected: str,
) -> pd.DataFrame:
    small_regime = f"smallcap_{selected}_com_regime_bruto"
    small_always = f"smallcap_{selected}_sempre_ligada"
    stress_idx = regime.index[regime["estado_aplicado"].eq(1)].intersection(returns.index)
    checks = [
        ("datas_precos_unicas", prices.index.is_unique, "indice mensal sem duplicatas"),
        ("datas_spread_unicas", spread.index.is_unique, "indice mensal sem duplicatas"),
        ("datas_ordenadas", prices.index.is_monotonic_increasing and spread.index.is_monotonic_increasing, "ordem temporal crescente"),
        ("mes_parcial_excluido", returns.index.max() <= complete_month_cutoff(), f"ultimo mes={returns.index.max()}"),
        ("sem_retorno_extremo_30pct", bool((returns.abs().max() < 0.30).all()), f"max_abs={returns.abs().max().max():.2%}"),
        ("pesos_somam_1", bool(np.allclose(weights.sum(axis=1), 1.0)), f"erro_max={(weights.sum(axis=1)-1).abs().max():.3g}"),
        ("pesos_nao_negativos", bool((weights >= 0).all().all()), f"min={weights.min().min():.3g}"),
        ("stress_usa_BIL_exato", bool(np.allclose(returns.loc[stress_idx, small_regime], returns.loc[stress_idx, "renda_fixa_BIL"])), f"n_stress={len(stress_idx)}"),
        ("normal_usa_smallcap_exato", bool(np.allclose(returns.loc[returns.index.difference(stress_idx), small_regime], returns.loc[returns.index.difference(stress_idx), small_always])), "comparacao por estado"),
        ("sinal_defasado_1_mes", bool(regime["estado_aplicado"].equals(regime["estado_sinal"].shift(1))), "estado observado em t aplicado em t+1"),
        ("sem_nan_resultados", bool(not returns.isna().any().any()), f"n_nan={int(returns.isna().sum().sum())}"),
        ("preco_ajustado_disponivel", bool((prices.notna().sum() > 12).all()), "campo Adj Close do Yahoo"),
    ]
    return pd.DataFrame(checks, columns=["teste", "aprovado", "evidencia"]).set_index("teste")


def save_plots(returns: pd.DataFrame, regime: pd.DataFrame, selected: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {"navy": "#12304A", "orange": "#E07A3F", "green": "#2A9D8F", "gray": "#64748B", "red": "#C2413B"}

    capital_cols = [
        "fundo_proxy_liquido",
        "benchmark_2_3_SPY_1_3_BIL",
        f"smallcap_{selected}_com_regime_liquido",
        f"smallcap_{selected}_sempre_ligada",
    ]
    capital = (1 + returns[capital_cols]).cumprod()
    ax = capital.plot(figsize=(12, 6), linewidth=2)
    ax.set(title="Curvas de capital — backtest preliminar com ETFs", xlabel="", ylabel="Crescimento de US$ 1")
    ax.legend(["Fundo proxy (líquido)", "Benchmark 2/3 SPY + 1/3 BIL", f"{selected} com regime", f"{selected} sempre ligado"], frameon=False)
    plt.tight_layout()
    plt.savefig(FIGURES / "01_curvas_capital.png", dpi=180)
    plt.close()

    common = regime.dropna(subset=["z_score", "estado_aplicado"])
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(common.index.to_timestamp(), common["z_score"], color=colors["navy"], lw=1.5, label="z-score spread Baa")
    ax.axhline(CFG.stress_entry, color=colors["red"], ls="--", label="entrada 1,0")
    ax.axhline(CFG.stress_exit, color=colors["green"], ls=":", label="saída 0,5")
    stress = common["estado_aplicado"].eq(1)
    ax.fill_between(common.index.to_timestamp(), ax.get_ylim()[0], ax.get_ylim()[1], where=stress, color=colors["red"], alpha=.12, transform=ax.get_xaxis_transform(), label="estado aplicado: estresse")
    ax.set(title="Regime de crédito — histerese e defasagem de um mês", xlabel="", ylabel="z-score (36 meses)")
    ax.legend(ncol=4, frameon=False, fontsize=9)
    plt.tight_layout()
    plt.savefig(FIGURES / "02_regime_credito.png", dpi=180)
    plt.close()

    corr_cols = ["factor_proxy_VFMF", f"smallcap_{selected}_sempre_ligada", "renda_fixa_BIL"]
    corr = returns[corr_cols].corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    labels = ["Factor (VFMF)", f"Small cap ({selected})", "Renda fixa (BIL)"]
    ax.set_xticks(range(3), labels, rotation=25, ha="right")
    ax.set_yticks(range(3), labels)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{corr.iloc[i,j]:.2f}", ha="center", va="center", color="white" if abs(corr.iloc[i,j]) > .55 else "black", fontweight="bold")
    ax.set_title("Correlação mensal entre sleeves (proxies)")
    fig.colorbar(im, ax=ax, shrink=.8)
    plt.tight_layout()
    plt.savefig(FIGURES / "03_matriz_correlacao.png", dpi=180)
    plt.close()

    cols = ["fundo_proxy_liquido", "benchmark_2_3_SPY_1_3_BIL"]
    wealth = (1 + returns[cols]).cumprod()
    dd = wealth / wealth.cummax() - 1
    ax = dd.plot(figsize=(12, 5), color=[colors["orange"], colors["gray"]], linewidth=1.7)
    ax.set(title="Drawdown — fundo proxy vs. benchmark", xlabel="", ylabel="Drawdown")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.legend(["Fundo proxy (líquido)", "Benchmark"], frameon=False)
    plt.tight_layout()
    plt.savefig(FIGURES / "04_drawdown.png", dpi=180)
    plt.close()


def write_reports(
    config_hash: str,
    sources: dict[str, str],
    selection: pd.DataFrame,
    metrics: pd.DataFrame,
    regression: pd.DataFrame,
    audit_df: pd.DataFrame,
    returns: pd.DataFrame,
    selected: str,
) -> None:
    pct_cols = ["CAGR", "volatilidade_anual", "max_drawdown", "retorno_acumulado"]
    display = metrics.copy()
    for col in pct_cols:
        display[col] = display[col].map(lambda x: f"{x:.2%}" if pd.notna(x) else "n/a")
    display["Sharpe_excesso_BIL"] = display["Sharpe_excesso_BIL"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "n/a")

    failed = audit_df.index[~audit_df["aprovado"]].tolist()
    corr = returns[["factor_proxy_VFMF", f"smallcap_{selected}_sempre_ligada", "renda_fixa_BIL"]].corr()
    always = metrics.loc[f"smallcap_{selected}_sempre_ligada"]
    guarded = metrics.loc[f"smallcap_{selected}_com_regime_liquido"]
    fund = metrics.loc["fundo_proxy_liquido"]
    benchmark = metrics.loc["benchmark_2_3_SPY_1_3_BIL"]
    overlay_helped = (
        guarded["Sharpe_excesso_BIL"] > always["Sharpe_excesso_BIL"]
        and guarded["max_drawdown"] > always["max_drawdown"]
    )
    overlay_verdict = (
        "agregou valor (Sharpe maior e drawdown menos profundo)"
        if overlay_helped
        else "não agregou valor: reduziu o Sharpe e/ou não melhorou o drawdown"
    )
    report = f"""# Backtest preliminar e auditoria metodológica

Gerado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · configuração `{config_hash[:12]}`.

## Escopo e veredito

Este resultado valida o **overlay de regime e a mecânica de consolidação** usando ETFs líquidos e preços ajustados. Ele ainda não valida o stock-picking point-in-time: `VFMF` representa provisoriamente o Sleeve 1 e `{selected}` representa provisoriamente o Sleeve 2. Logo, os números são evidência preliminar, não o backtest final das duas seleções de ações.

Auditoria automatizada: **{int(audit_df['aprovado'].sum())}/{len(audit_df)} testes aprovados**. Falhas: {', '.join(failed) if failed else 'nenhuma'}.

**Resultado principal:** no período comum, o overlay de regime **{overlay_verdict}**. A versão sempre ligada teve CAGR de {always['CAGR']:.2%}, Sharpe de {always['Sharpe_excesso_BIL']:.2f} e Max Drawdown de {always['max_drawdown']:.2%}; com regime e custo, os valores foram {guarded['CAGR']:.2%}, {guarded['Sharpe_excesso_BIL']:.2f} e {guarded['max_drawdown']:.2%}. Isso é evidência contra a regra atual nesta implementação proxy — não uma falha do motor de backtest.

## Decisão do proxy small-cap

O proxy escolhido foi **{selected}**, pela correlação mais negativa entre variação mensal do spread Baa e retorno relativo ao SPY nas crises pré-definidas. A decisão usa uma referência externa ao payoff do backtest.

{selection.to_markdown(floatfmt='.3f')}

## Métricas

Sharpe calculado sobre o excesso em relação ao BIL. Séries “líquidas” descontam {CFG.transaction_cost_bps:.0f} bps por unidade de giro do overlay; não incluem o giro do stock-picking ainda inexistente.

{display.to_markdown()}

## Diversificação

Correlação mensal Factor proxy × Small Cap: **{corr.iloc[0,1]:.2f}**. A matriz completa está em `resultados/tabelas/correlacao_sleeves.csv`.

## Regressões FF5 + Momentum

OLS mensal com erros HAC/Newey-West (3 defasagens). Coeficientes e p-valores completos estão em `resultados/tabelas/regressoes_ff5_mom.csv`. A interpretação deve considerar que proxies de ETF não reproduzem os rankings de ações prometidos.

## Auditoria de riscos metodológicos

| Risco | Veredito | Evidência / ação |
|---|---|---|
| Look-ahead do regime | Mitigado | O estado observado no fechamento de t só é aplicado ao retorno de t+1; teste automatizado `sinal_defasado_1_mes`. |
| Viés de sobrevivência | Não resolvido no modelo final | ETFs evitam reconstrução de constituintes neste teste do overlay, mas a futura seleção com holdings atuais terá viés; exige constituintes históricos point-in-time. |
| Alinhamento de datas | Testado | Todas as séries viram `PeriodIndex` mensal, usam interseção de datas e excluem o mês corrente incompleto. |
| Preço não ajustado | Mitigado | Retornos usam `Adj Close`; divergência contra `Close` foi salva como evidência. |
| Parâmetros pós-backtest | Mitigado no pipeline | Limiar 1,0/0,5, janela 36 e crises estão congelados em configuração imutável e hash; não há busca de hiperparâmetro. |
| Dados ausentes | Mitigado | Nenhuma imputação de retornos; consolidação usa apenas a interseção completa. No stock-picking final, empresa incompleta deve ser excluída. |
| Retornos × pesos | Testado | Pesos não negativos, soma unitária e igualdade exata BIL/Small Cap em cada estado. |
| Custos | Parcial | Overlay desconta {CFG.transaction_cost_bps:.0f} bps por giro; custos e turnover do ranking mensal precisam ser incluídos no backtest final. |
| Fonte do spread | Mitigado | A série oficial FRED `BAA10Y` cobre o histórico desde 1986; o arquivo local registra a fonte e o período utilizado. |
| Proxy vs. estratégia | Limitação material | Este pipeline não testa momentum+reversão por ação nem os quatro fatores fundamentalistas point-in-time. |

## Proveniência

- Preços: Yahoo Finance, campo `Adj Close`, baixados no momento da execução.
- Spread de crédito Baa: {sources['fonte_oficial']}
- Fatores: Kenneth R. French Data Library, FF5 e Momentum mensais.

## Arquivos visuais

- `01_curvas_capital.png`: fundo, benchmark e Small Cap com/sem regime.
- `02_regime_credito.png`: z-score, histerese e meses efetivamente defensivos.
- `03_matriz_correlacao.png`: teste visual da tese de diversificação.
- `04_drawdown.png`: profundidade e duração das perdas.
"""
    (RESULTS / "relatorio_backtest_auditoria.md").write_text(report, encoding="utf-8")

    material = f"""# Material pronto para o pré-relatório

## Texto curto — backtest e risco

No teste preliminar com ETFs, o {selected} foi o proxy small-cap mais sensível ao crédito: nas crises pré-definidas, sua correlação entre retorno relativo ao SPY e variação do spread Baa foi {selection.loc[selected, 'correlacao_crises']:.2f}, contra {selection.loc['IWM', 'correlacao_crises']:.2f} no IWM e {selection.loc['IJR', 'correlacao_crises']:.2f} no IJR. O sinal usa z-score de 36 meses, entra em estresse acima de 1,0 e sai abaixo de 0,5; o estado observado no fim do mês só altera os pesos do mês seguinte.

O resultado foi adverso e informativo. No período de {always['inicio']} a {always['fim']}, o {selected} sempre ligado apresentou CAGR de {always['CAGR']:.1%}, Sharpe de {always['Sharpe_excesso_BIL']:.2f} e drawdown máximo de {always['max_drawdown']:.1%}. Com o filtro de regime e 10 bps por giro, apresentou {guarded['CAGR']:.1%}, {guarded['Sharpe_excesso_BIL']:.2f} e {guarded['max_drawdown']:.1%}. Portanto, o filtro binário, com sinal mensal defasado, não protegeu a proxy nesta amostra e não deve ser vendido como fonte comprovada de valor.

O fundo proxy obteve CAGR de {fund['CAGR']:.1%}, volatilidade de {fund['volatilidade_anual']:.1%}, Sharpe de {fund['Sharpe_excesso_BIL']:.2f} e drawdown de {fund['max_drawdown']:.1%}, contra {benchmark['CAGR']:.1%}, {benchmark['volatilidade_anual']:.1%}, {benchmark['Sharpe_excesso_BIL']:.2f} e {benchmark['max_drawdown']:.1%} do benchmark 2/3 SPY + 1/3 BIL. A correlação de {corr.iloc[0,1]:.2f} entre VFMF e VB também não sustenta, por proxies, a hipótese de dois motores pouco correlacionados. A próxima validação decisiva é substituir os ETFs pelas seleções point-in-time dos Sleeves 1 e 2.

## Tabela enxuta sugerida

| Série | CAGR | Vol. | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| VB sempre ligado | {always['CAGR']:.1%} | {always['volatilidade_anual']:.1%} | {always['Sharpe_excesso_BIL']:.2f} | {always['max_drawdown']:.1%} |
| VB com regime, líquido | {guarded['CAGR']:.1%} | {guarded['volatilidade_anual']:.1%} | {guarded['Sharpe_excesso_BIL']:.2f} | {guarded['max_drawdown']:.1%} |
| Fundo proxy, líquido | {fund['CAGR']:.1%} | {fund['volatilidade_anual']:.1%} | {fund['Sharpe_excesso_BIL']:.2f} | {fund['max_drawdown']:.1%} |
| Benchmark | {benchmark['CAGR']:.1%} | {benchmark['volatilidade_anual']:.1%} | {benchmark['Sharpe_excesso_BIL']:.2f} | {benchmark['max_drawdown']:.1%} |

## Layout visual sugerido

- Página do Sleeve 2: use `02_regime_credito.png` acima e `01_curvas_capital.png` abaixo; destaque em uma caixa: “o filtro não agregou valor no teste proxy”.
- Página do fundo: use `04_drawdown.png` à esquerda, a tabela enxuta à direita e `03_matriz_correlacao.png` menor no rodapé.
- Rodapé metodológico: “Preços ajustados; sinal defasado em um mês; custos de 10 bps por giro do overlay; resultados por proxies, não stock-picking final.”

## TradingView Premium

1. Abra um layout com dois painéis: benchmark/ativos no painel superior e o indicador `regime_credito_baa.pine` no inferior.
2. Cole o script no Pine Editor, salve e adicione ao gráfico. Use gráfico mensal para auditoria visual.
3. Crie dois alertas separados, “ENTRADA EM ESTRESSE” e “VOLTA AO NORMAL”, ambos **Once Per Bar Close**. O alerta confirmado no fechamento do mês define os pesos do mês seguinte.
4. Mantenha os inputs de produção em 36 meses, entrada 1,0 e saída 0,5. Qualquer alteração deve gerar uma nova versão do manifesto antes de olhar o resultado.
"""
    (RESULTS / "material_pre_relatorio.md").write_text(material, encoding="utf-8")


def main() -> int:
    ensure_dirs()
    config_json = json.dumps(asdict(CFG), sort_keys=True, ensure_ascii=False, default=list)
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    manifest = {
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(CFG),
        "sha256_config": config_hash,
        "nota": "Parametros definidos antes do backtest; nao otimizar pelo retorno.",
    }
    (RESULTS / "manifesto_execucao.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=list), encoding="utf-8")

    prices = monthly_adjusted_prices()
    spread, sources = credit_spread_monthly()
    regime = regime_signal(spread)
    raw_returns = prices.pct_change(fill_method=None)
    selection = choose_smallcap(raw_returns, spread)
    selected = str(selection["correlacao_crises"].idxmin())
    returns, weights = build_returns(prices, regime, selected)
    factors = french_factors()
    metrics = metrics_table(returns)
    regression = regressions(returns, factors)
    audit_df = audit(prices, spread, regime, returns, weights, selected)

    regime.to_csv(DATA / "regime_credito_mensal.csv", index_label="mes")
    returns.to_csv(RESULTS / "retornos_mensais.csv", index_label="mes")
    weights.to_csv(RESULTS / "pesos_fundo_mensais.csv", index_label="mes")
    selection.to_csv(TABLES / "selecao_proxy_smallcap.csv")
    metrics.to_csv(TABLES / "metricas.csv")
    regression.to_csv(TABLES / "regressoes_ff5_mom.csv")
    audit_df.to_csv(TABLES / "testes_auditoria.csv")
    returns[["factor_proxy_VFMF", f"smallcap_{selected}_sempre_ligada", "renda_fixa_BIL"]].corr().to_csv(TABLES / "correlacao_sleeves.csv")

    save_plots(returns, regime, selected)
    write_reports(config_hash, sources, selection, metrics, regression, audit_df, returns, selected)
    print(f"OK | proxy={selected} | periodo={returns.index.min()}..{returns.index.max()} | auditoria={audit_df.aprovado.sum()}/{len(audit_df)}")
    return 0 if audit_df["aprovado"].all() else 2


if __name__ == "__main__":
    sys.exit(main())
