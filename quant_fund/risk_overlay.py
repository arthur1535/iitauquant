"""Overlay de risco: condições financeiras em dois eixos e de-risking graduado.

Motivação empírica (ver `scripts/diagnostico_overlay.py`):

1. Um spread de crédito é o prêmio exigido para carregar risco de crédito. Ele
   não enxerga um choque de taxa de desconto. Entre 2022-01 e 2022-12 o BAA10Y
   oscilou entre z = -0,77 e +0,19 enquanto o Treasury de 10 anos saía de 1,79%
   para 4,10% e o mercado acionário caía 24%. O gatilho de crédito nunca acendeu
   no maior drawdown da amostra — não por calibração ruim, mas por construção.
   O segundo eixo (índice amplo de condições financeiras) cobre esse ângulo.

2. Migrar 100% do sleeve de risco em um único passo pode concentrar o resultado
   em poucos acertos de timing. A intensidade parcial torna o custo da proteção
   explícito e evita tratar um único episódio como evidência de generalização.

Os parâmetros abaixo descrevem a especificação exploratória do relatório. O
hash do manifesto identifica exatamente o que foi executado, mas não equivale a
pré-registro. A significância é avaliada separadamente com placebos temporais,
bootstrap em blocos e Deflated Sharpe Ratio.

O overlay resultante não é mais complexo que o anterior: mesma arquitetura de
z-score com histerese, um insumo a mais, e uma saída graduada em vez de binária.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .utils import monthly_last


@dataclass(frozen=True)
class RiskOverlayConfig:
    """Parâmetros identificados do overlay; não selecionar pelo melhor backtest."""

    zscore_window_months: int = 36
    zscore_min_periods: int = 24
    stress_entry_z: float = 1.0
    stress_exit_z: float = 0.5
    # Fração máxima do sleeve de risco que migra para caixa com os dois eixos acesos.
    max_derisk: float = 0.50
    # Rótulos dos eixos, apenas para relatórios e auditoria.
    axis_labels: tuple[str, ...] = ("credito", "condicoes_financeiras")

    def __post_init__(self) -> None:
        if self.zscore_window_months < 2:
            raise ValueError("zscore_window_months deve ser pelo menos 2.")
        if not 1 <= self.zscore_min_periods <= self.zscore_window_months:
            raise ValueError("zscore_min_periods deve caber na janela do z-score.")
        if self.stress_exit_z >= self.stress_entry_z:
            raise ValueError("O limiar de saída deve ser menor que o de entrada.")
        if not 0 < self.max_derisk <= 1:
            raise ValueError("max_derisk deve estar em (0, 1].")
        if not self.axis_labels:
            raise ValueError("Defina ao menos um eixo no overlay.")


def _to_monthly(series: pd.Series) -> pd.Series:
    """Normaliza para uma observação por mês, aceitando índice de data ou de período.

    As séries macro chegam com `PeriodIndex` (arquivos em `dados/`) ou com datas
    diárias vindas da fonte; ambas precisam virar a mesma grade mensal.
    """

    if isinstance(series.index, pd.PeriodIndex):
        ordered = series.sort_index()
        return ordered[~ordered.index.duplicated(keep="last")]
    return monthly_last(series).sort_index()


def rolling_zscore(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Z-score móvel padrão. Usa apenas observações até a data corrente."""

    values = pd.to_numeric(series, errors="coerce")
    rolling = values.rolling(window, min_periods=min_periods)
    deviation = rolling.std(ddof=1).replace(0.0, np.nan)
    return ((values - rolling.mean()) / deviation).rename(f"{series.name}_z")


def hysteresis_state(zscore: pd.Series, entry_z: float, exit_z: float) -> pd.Series:
    """Estado persistente 0/1. Entra acima de entry_z, só sai abaixo de exit_z.

    A histerese existe para que uma oscilação em torno do limiar não gere um
    par de operações por mês. O custo é uma saída deliberadamente tardia.
    """

    if exit_z >= entry_z:
        raise ValueError("exit_z deve ser menor que entry_z.")
    stressed = False
    states: list[int] = []
    for value in zscore:
        if pd.notna(value):
            if not stressed and value > entry_z:
                stressed = True
            elif stressed and value < exit_z:
                stressed = False
        states.append(int(stressed))
    return pd.Series(states, index=zscore.index, name="estado", dtype=int)


def build_risk_overlay(
    axes: dict[str, pd.Series],
    monthly_index: pd.Index,
    config: RiskOverlayConfig | None = None,
) -> pd.DataFrame:
    """Converte N séries macro no fator de de-risking aplicado a cada mês.

    Cada eixo é padronizado, passa pela mesma histerese e vale um voto. O nível
    de de-risking é ``max_derisk × (votos acesos / total de eixos)``. O estado
    observado no fechamento de t só governa o retorno de t+1: a coluna
    ``derisk_aplicado`` já contém a defasagem.
    """

    config = config or RiskOverlayConfig()
    if not axes:
        raise ValueError("Informe ao menos uma série macro no overlay.")

    frame = pd.DataFrame(index=pd.Index(monthly_index, name="mes"))
    votes = pd.DataFrame(index=frame.index)
    for name, raw in axes.items():
        series = _to_monthly(pd.to_numeric(raw, errors="coerce").dropna())
        zscore = rolling_zscore(series.rename(name), config.zscore_window_months, config.zscore_min_periods)
        state = hysteresis_state(zscore, config.stress_entry_z, config.stress_exit_z)
        frame[f"{name}_nivel"] = series.reindex(frame.index)
        frame[f"{name}_z"] = zscore.reindex(frame.index)
        frame[f"{name}_estado"] = state.reindex(frame.index).fillna(0).astype(int)
        votes[name] = frame[f"{name}_estado"]

    frame["eixos_acesos"] = votes.sum(axis=1).astype(int)
    frame["derisk_sinal"] = config.max_derisk * frame["eixos_acesos"] / votes.shape[1]
    # Informação observada no fechamento de t só pode alterar a posição de t+1.
    frame["derisk_aplicado"] = frame["derisk_sinal"].shift(1).fillna(0.0)
    frame["regime_efetivo"] = np.where(frame["derisk_aplicado"] > 0, "defensivo", "normal")
    return frame


def graded_allocations(
    derisk_applied: pd.Series,
    normal_weights: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
) -> pd.DataFrame:
    """Pesos mensais dos três sleeves com migração proporcional ao de-risking.

    O sleeve fundamentalista nunca é tocado pelo gatilho — ele carrega uma tese
    estrutural, não uma view de curto prazo. Só a perna tática migra para caixa.
    """

    factor_w, small_w, cash_w = normal_weights
    if abs(factor_w + small_w + cash_w - 1.0) > 1e-12:
        raise ValueError("Os pesos normais devem somar 1.")
    level = pd.to_numeric(derisk_applied, errors="coerce").fillna(0.0).clip(0.0, 1.0)
    migrated = small_w * level
    allocations = pd.DataFrame(
        {
            "factor": factor_w,
            "small_caps": small_w - migrated,
            "fixed_income": cash_w + migrated,
        },
        index=level.index,
    )
    allocations.index.name = "date"
    return allocations


def insurance_ledger(
    risky_returns: pd.Series,
    cash_returns: pd.Series,
    derisk_applied: pd.Series,
    tail_months: int = 5,
) -> dict[str, float]:
    """Mede o overlay como seguro: prêmio pago por ano contra alívio na cauda.

    Um overlay defensivo não deve ser julgado pelo Sharpe do período inteiro.
    A pergunta certa é a de uma apólice: quanto custa carregar e quanto devolve
    quando o sinistro acontece.
    """

    aligned = pd.concat(
        {"risky": risky_returns, "cash": cash_returns, "derisk": derisk_applied}, axis=1
    ).dropna()
    hedged = aligned["risky"] * (1 - aligned["derisk"]) + aligned["cash"] * aligned["derisk"]
    months_per_year = 12
    return {
        "premio_anual": float((hedged - aligned["risky"]).mean() * months_per_year),
        "meses_ativos": int((aligned["derisk"] > 0).sum()),
        "cobertura_pct": float((aligned["derisk"] > 0).mean()),
        "cauda_sem_overlay": float(aligned["risky"].nsmallest(tail_months).mean()),
        "cauda_com_overlay": float(hedged.nsmallest(tail_months).mean()),
        "giro_anual": float(aligned["derisk"].diff().abs().sum() / (len(aligned) / months_per_year)),
    }
