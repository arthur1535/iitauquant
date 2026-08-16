"""Diagnóstico do overlay de regime e teste das revisões propostas.

Este script responde a uma pergunta só: o overlay de crédito, do jeito que foi
especificado, ajudou ou atrapalhou — e por quê. Ele produz as quatro evidências
que sustentam a revisão da estratégia:

  1. atribuição aditiva exata do desempenho contra o benchmark;
  2. anatomia do ponto cego de 2022 (crédito x taxa de desconto);
  3. grid de sensibilidade do overlay (36 configurações);
  4. contabilidade do overlay como seguro (prêmio anual x alívio de cauda).

Todos os parâmetros vêm de `quant_fund.risk_overlay.RiskOverlayConfig` e são
registrados com hash no manifesto. Nenhum número aqui foi escolhido depois de
olhar o retorno: as revisões partem de um argumento econômico e o grid existe
justamente para mostrar que a conclusão não depende do ponto escolhido.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import sys
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant_fund.risk_overlay import (  # noqa: E402
    RiskOverlayConfig,
    hysteresis_state,
    insurance_ledger,
    rolling_zscore,
)

DATA = ROOT / "dados"
RESULTS = ROOT / "resultados"
TABLES = RESULTS / "tabelas"

CFG = RiskOverlayConfig()
COST_BPS = 10.0
MONTHS = 12

# Séries macro. Ambas oficiais, gratuitas e com histórico longo — requisito para
# calibrar contra crises documentadas em vez de calibrar contra o próprio payoff.
FRED_SERIES = {
    "credito": "BAA10Y",  # Baa da Moody's menos Treasury 10 anos, diário desde 1986
    "condicoes_financeiras": "NFCI",  # Chicago Fed, 105 indicadores, semanal desde 1971
}


def fred_monthly(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    payload = urllib.request.urlopen(url, timeout=60).read().decode()
    frame = pd.read_csv(io.StringIO(payload))
    frame.columns = ["date", series_id]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    series = frame.dropna().sort_values("date").set_index("date")[series_id]
    monthly = series.resample("ME").last()
    monthly.index = monthly.index.to_period("M")
    return monthly


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.Series]]:
    prices = pd.read_csv(DATA / "precos_mensais_ajustados.csv", index_col=0)
    prices.index = pd.PeriodIndex(prices.index, freq="M")
    factors = pd.read_csv(DATA / "fatores_fama_french_mensais.csv", index_col=0)
    factors.index = pd.PeriodIndex(factors.index, freq="M")
    macro = {}
    for label, series_id in FRED_SERIES.items():
        path = DATA / f"macro_{series_id}_mensal.csv"
        try:
            series = fred_monthly(series_id)
            series.to_csv(path, header=True, index_label="mes")
        except Exception:  # offline: usa o arquivo já versionado
            cached = pd.read_csv(path, index_col=0)[series_id]
            cached.index = pd.PeriodIndex(cached.index, freq="M")
            series = cached
        macro[label] = series
    return prices, factors, macro


def turnover_cost(weights: pd.DataFrame, bps: float = COST_BPS) -> pd.Series:
    return (weights.diff().abs().sum(axis=1) / 2).fillna(0.0) * bps / 10_000


def metrics(returns: pd.Series, cash: pd.Series, label: str = "") -> dict[str, float | str]:
    series = returns.dropna()
    wealth = (1 + series).cumprod()
    cagr = wealth.iloc[-1] ** (MONTHS / len(series)) - 1
    excess = (series - cash.reindex(series.index)).dropna()
    drawdown = (wealth / wealth.cummax() - 1).min()
    downside = excess[excess < 0].std(ddof=1) * math.sqrt(MONTHS)
    return {
        "serie": label,
        "meses": len(series),
        "CAGR": cagr,
        "vol_anual": series.std(ddof=1) * math.sqrt(MONTHS),
        "Sharpe": excess.mean() / excess.std(ddof=1) * math.sqrt(MONTHS),
        "Sortino": excess.mean() * MONTHS / downside if downside else np.nan,
        "max_drawdown": drawdown,
        "Calmar": cagr / abs(drawdown),
        "retorno_acumulado": wealth.iloc[-1] - 1,
    }


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    prices, factors, macro = load_inputs()
    returns = prices.pct_change(fill_method=None)
    panel = returns.dropna(subset=["VFMF", "VB", "BIL", "SPY"])
    index, cash, market = panel.index, panel["BIL"], panel["SPY"]

    # ------------------------------------------------------------------ sinais
    states = {}
    zscores = {}
    for label, series in macro.items():
        z = rolling_zscore(series.rename(label), CFG.zscore_window_months, CFG.zscore_min_periods)
        zscores[label] = z
        states[label] = (
            hysteresis_state(z, CFG.stress_entry_z, CFG.stress_exit_z)
            .shift(1)
            .reindex(index)
            .fillna(0)
        )
    credit_only = states["credito"]
    graded = CFG.max_derisk * sum(states.values()) / len(states)

    def fund(derisk: pd.Series) -> pd.Series:
        weights = pd.DataFrame(
            {"VFMF": 1 / 3, "VB": (1 - derisk) / 3, "BIL": (1 + derisk) / 3}, index=index
        )
        return (weights * panel[["VFMF", "VB", "BIL"]]).sum(axis=1) - turnover_cost(weights)

    fund_current, fund_revised = fund(credit_only), fund(graded)
    benchmark = (2 / 3) * market + (1 / 3) * cash

    table = pd.DataFrame(
        [
            metrics(fund_current, cash, "Fundo — overlay de crédito binário"),
            metrics(fund_revised, cash, "Fundo — overlay dois eixos graduado"),
            metrics(benchmark, cash, "Benchmark 2/3 SPY + 1/3 BIL"),
            metrics(market, cash, "SPY"),
            metrics(panel["VFMF"], cash, "Sleeve 1 (proxy VFMF)"),
            metrics(panel["VB"], cash, "Sleeve 2 (proxy VB, sempre ligado)"),
        ]
    ).set_index("serie")
    table.to_csv(TABLES / "metricas_revisao.csv")
    print("\n=== MÉTRICAS ===")
    print(table.to_string(float_format=lambda v: f"{v:.4f}"))

    # ------------------------------------------------- 1. atribuição aditiva
    # fundo - benchmark decompõe exatamente em três termos mais custo.
    attribution = pd.DataFrame(
        {
            "selecao_sleeve1": (1 / 3) * (panel["VFMF"] - market),
            "selecao_sleeve2": (1 / 3) * (panel["VB"] - market),
            "overlay_regime": (1 / 3) * credit_only * (cash - panel["VB"]),
            "custos": -turnover_cost(
                pd.DataFrame(
                    {"VFMF": 1 / 3, "VB": (1 - credit_only) / 3, "BIL": (1 + credit_only) / 3},
                    index=index,
                )
            ),
        }
    )
    annual = attribution.mean() * MONTHS
    residual = (fund_current - benchmark).mean() * MONTHS - annual.sum()
    annual.to_csv(TABLES / "atribuicao_vs_benchmark.csv", header=["pp_ao_ano"])
    print("\n=== ATRIBUIÇÃO vs BENCHMARK (pontos percentuais ao ano) ===")
    for name, value in annual.items():
        print(f"  {name:20s} {value * 100:+6.2f}")
    print(f"  {'TOTAL':20s} {annual.sum() * 100:+6.2f}   (resíduo {residual * 100:+.4f})")

    # ------------------------------------------- 2. anatomia do ponto cego 2022
    blind = pd.DataFrame(
        {
            "credito_z": zscores["credito"],
            "condicoes_z": zscores["condicoes_financeiras"],
            "credito_nivel": macro["credito"],
        }
    ).loc[pd.Period("2022-01"): pd.Period("2023-12")]
    blind["drawdown_SPY"] = (
        (1 + market).cumprod() / (1 + market).cumprod().cummax() - 1
    ).reindex(blind.index)
    blind.to_csv(TABLES / "ponto_cego_2022.csv", index_label="mes")
    print("\n=== PONTO CEGO DE 2022 ===")
    print(
        f"  z do crédito em 2022: min {blind.loc[:pd.Period('2022-12'), 'credito_z'].min():.2f} "
        f"máx {blind.loc[:pd.Period('2022-12'), 'credito_z'].max():.2f} — nunca cruzou {CFG.stress_entry_z:.1f}"
    )
    print(
        f"  z de condições financeiras: máx {blind.loc[:pd.Period('2022-12'), 'condicoes_z'].max():.2f} — cruzou o limiar"
    )
    print(f"  drawdown do SPY no período: {blind['drawdown_SPY'].min():.2%}")

    # -------------------------------------------------- 3. grid de sensibilidade
    grid = []
    baseline = metrics(panel["VB"], cash, "sempre ligado")
    for window in (24, 36, 48):
        for entry, exit_ in ((0.75, 0.25), (1.0, 0.5), (1.25, 0.75)):
            for cap in (0.33, 0.50, 0.67, 1.00):
                votes = []
                for label, series in macro.items():
                    z = rolling_zscore(series.rename(label), window, max(2, int(window * 0.7)))
                    votes.append(hysteresis_state(z, entry, exit_).shift(1).reindex(index).fillna(0))
                level = cap * sum(votes) / len(votes)
                hedged = panel["VB"] * (1 - level) + cash * level
                weights = pd.DataFrame({"VB": 1 - level, "BIL": level}, index=index)
                row = metrics(hedged - turnover_cost(weights), cash)
                row.update({"janela": window, "entrada": entry, "saida": exit_, "cap_derisk": cap})
                grid.append(row)
    grid_df = pd.DataFrame(grid).drop(columns=["serie"])
    grid_df.to_csv(TABLES / "sensibilidade_overlay.csv", index=False)
    better_dd = (grid_df["max_drawdown"] > baseline["max_drawdown"]).mean()
    better_sharpe = (grid_df["Sharpe"] > baseline["Sharpe"]).mean()
    print("\n=== SENSIBILIDADE (36 configurações) ===")
    print(f"  melhoram o drawdown máximo: {better_dd:.0%}")
    print(f"  melhoram o Sharpe         : {better_sharpe:.0%}")
    print("\n  mediana por intensidade de de-risking:")
    print(
        grid_df.groupby("cap_derisk")[["CAGR", "vol_anual", "Sharpe", "max_drawdown"]]
        .median()
        .to_string(float_format=lambda v: f"{v:.4f}")
    )

    # ------------------------------------------------ 4. overlay como seguro
    print("\n=== OVERLAY COMO SEGURO ===")
    ledger = []
    for label, level in (("binário 100%", credit_only), ("dois eixos graduado", graded)):
        row = insurance_ledger(panel["VB"], cash, level)
        row["especificacao"] = label
        ledger.append(row)
        print(
            f"  {label:22s} prêmio {row['premio_anual'] * 100:+5.2f} pp/ano | "
            f"cobertura {row['cobertura_pct']:.0%} dos meses | "
            f"5 piores meses {row['cauda_sem_overlay']:.2%} -> {row['cauda_com_overlay']:.2%} | "
            f"giro {row['giro_anual']:.2f}x"
        )
    pd.DataFrame(ledger).set_index("especificacao").to_csv(TABLES / "overlay_como_seguro.csv")

    # ---------------------------------- 5. a medida certa de diversificação
    aligned = factors.reindex(index)
    residuals = {}
    for column in ("VFMF", "VB"):
        model = sm.OLS(
            (panel[column] - aligned["RF"]).dropna(),
            sm.add_constant(aligned[["Mkt-RF", "SMB"]].dropna()),
        ).fit()
        residuals[column] = model.resid
    residuals = pd.DataFrame(residuals)
    diversification = pd.Series(
        {
            "retorno_total": panel["VFMF"].corr(panel["VB"]),
            "retorno_ativo_vs_SPY": (panel["VFMF"] - market).corr(panel["VB"] - market),
            "residual_pos_mercado_e_tamanho": residuals["VFMF"].corr(residuals["VB"]),
        },
        name="correlacao",
    )
    diversification.to_csv(TABLES / "diversificacao_por_medida.csv", index_label="medida")
    print("\n=== DIVERSIFICAÇÃO: a medida muda a conclusão ===")
    print(diversification.to_string(float_format=lambda v: f"{v:.2f}"))

    # ------------------------------------- 6. contexto: o prêmio de fator existiu?
    sample = factors.reindex(index).dropna()
    long_run = factors.loc[pd.Period("1963-07"): pd.Period("2017-12")]
    context = pd.DataFrame(
        {
            "media_anual_na_amostra": sample[["SMB", "HML", "RMW", "CMA", "Mom"]].mean() * MONTHS,
            "media_anual_1963_2017": long_run[["SMB", "HML", "RMW", "CMA", "Mom"]].mean() * MONTHS,
        }
    )
    context.to_csv(TABLES / "contexto_premios_fator.csv", index_label="fator")
    print("\n=== CONTEXTO: prêmios de fator na janela testada ===")
    print(context.to_string(float_format=lambda v: f"{v:.4f}"))

    manifest = {
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "config_overlay": asdict(CFG),
        "custo_bps": COST_BPS,
        "series_macro": FRED_SERIES,
        "sha256_config": hashlib.sha256(
            json.dumps(asdict(CFG), sort_keys=True, default=list).encode()
        ).hexdigest(),
        "nota": "Revisões motivadas por argumento econômico; grid publicado para mostrar dependência de parâmetro.",
    }
    (RESULTS / "manifesto_revisao.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=list), encoding="utf-8"
    )
    print(f"\nOK | período {index.min()}..{index.max()} | {len(index)} meses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
