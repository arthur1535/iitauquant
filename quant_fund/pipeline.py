"""Orquestração e exportação dos três sleeves."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import FundConfig, Sleeve1Config, Sleeve2Config
from .portfolio import (
    build_fund_allocations,
    build_fund_returns,
    combine_security_weights,
    validate_fully_invested,
)
from .risk_overlay import RiskOverlayConfig, graded_allocations
from .sleeve1 import Sleeve1Result, build_sleeve1
from .sleeve2 import Sleeve2Result, build_sleeve2
from .sleeve3 import Sleeve3Result, build_sleeve3
from .utils import weights_to_long


@dataclass
class PipelineResult:
    """Entrega completa: sinais, carteiras, pesos e retornos mensais."""

    sleeve1: Sleeve1Result
    sleeve2: Sleeve2Result
    sleeve3: Sleeve3Result
    fund_allocations: pd.DataFrame
    fund_security_weights: pd.DataFrame
    fund_returns: pd.Series


def run_pipeline(
    factor_prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    small_cap_prices: pd.DataFrame,
    credit_spread: pd.Series,
    bil_prices: pd.Series,
    factor_market_prices: pd.DataFrame | None = None,
    universe_membership: pd.DataFrame | None = None,
    sleeve1_config: Sleeve1Config | None = None,
    sleeve2_config: Sleeve2Config | None = None,
    fund_config: FundConfig | None = None,
    financial_conditions: pd.Series | None = None,
    risk_overlay_config: RiskOverlayConfig | None = None,
) -> PipelineResult:
    """Executa os sleeves e consolida somente o histórico plenamente investido.

    O argumento opcional ``financial_conditions`` ativa o overlay graduado de
    dois eixos. Sua ausência mantém o caminho credit-only anterior.
    """

    sleeve1_config = sleeve1_config or Sleeve1Config()
    sleeve2_config = sleeve2_config or Sleeve2Config()
    fund_config = fund_config or FundConfig()
    sleeve1 = build_sleeve1(
        factor_prices,
        fundamentals,
        sleeve1_config,
        market_prices=factor_market_prices,
    )
    sleeve3 = build_sleeve3(bil_prices, sleeve2_config.bil_ticker)
    sleeve2 = build_sleeve2(
        small_cap_prices,
        credit_spread,
        bil_prices=sleeve3.prices,
        universe_membership=universe_membership,
        config=sleeve2_config,
        financial_conditions=financial_conditions,
        risk_overlay_config=risk_overlay_config,
    )

    common_index = (
        sleeve1.weights.index.intersection(sleeve2.risky_weights.index)
        .intersection(sleeve3.weights.index)
        .intersection(sleeve2.regime.index)
    )
    sleeve1_active = sleeve1.weights.reindex(common_index).sum(axis=1).sub(1.0).abs().le(1e-10)
    sleeve2_active = (
        sleeve2.risky_weights.reindex(common_index).sum(axis=1).sub(1.0).abs().le(1e-10)
    )
    valid_index = common_index[sleeve1_active & sleeve2_active]
    if financial_conditions is None:
        regime_effective = sleeve2.regime.loc[valid_index, "regime_effective"]
        allocations = build_fund_allocations(regime_effective, fund_config)
    else:
        allocations = graded_allocations(
            sleeve2.regime.loc[valid_index, "derisk_aplicado"],
            normal_weights=(
                fund_config.normal_factor,
                fund_config.normal_small_caps,
                fund_config.normal_fixed_income,
            ),
        )
    security_weights = combine_security_weights(
        sleeve1.weights,
        sleeve2.risky_weights,
        allocations,
        sleeve2_config.bil_ticker,
    )
    if not validate_fully_invested(security_weights).all():
        raise RuntimeError("Falha interna: pesos consolidados não somam 1.")
    fund_returns = build_fund_returns(
        sleeve1.returns,
        sleeve2.risky_returns,
        sleeve3.returns,
        allocations,
    )
    return PipelineResult(
        sleeve1=sleeve1,
        sleeve2=sleeve2,
        sleeve3=sleeve3,
        fund_allocations=allocations,
        fund_security_weights=security_weights,
        fund_returns=fund_returns,
    )


def export_pipeline_result(result: PipelineResult, output_dir: str | Path) -> None:
    """Grava a entrega em CSVs auditáveis, com datas em ISO-8601."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.sleeve1.signals.to_csv(output / "sleeve1_signals.csv", index=False)
    result.sleeve1.weights.to_csv(output / "sleeve1_weights_monthly.csv", index_label="date")
    result.sleeve1.returns.to_csv(output / "sleeve1_returns_monthly.csv", index_label="date")
    result.sleeve2.signals.to_csv(output / "sleeve2_signals.csv", index=False)
    result.sleeve2.regime.to_csv(output / "sleeve2_regime_monthly.csv", index_label="date")
    result.sleeve2.risky_weights.to_csv(
        output / "sleeve2_risky_weights_monthly.csv", index_label="date"
    )
    result.sleeve2.weights_with_regime.to_csv(
        output / "sleeve2_weights_with_regime_monthly.csv", index_label="date"
    )
    result.sleeve2.risky_returns.to_csv(
        output / "sleeve2_risky_returns_monthly.csv", index_label="date"
    )
    if result.sleeve2.returns_with_regime is not None:
        result.sleeve2.returns_with_regime.to_csv(
            output / "sleeve2_regime_returns_monthly.csv", index_label="date"
        )
    result.sleeve3.weights.to_csv(output / "sleeve3_weights_monthly.csv", index_label="date")
    result.sleeve3.returns.to_csv(output / "sleeve3_returns_monthly.csv", index_label="date")
    result.fund_allocations.to_csv(output / "fund_sleeve_allocations_monthly.csv")
    result.fund_security_weights.to_csv(output / "fund_security_weights_monthly.csv")
    weights_to_long(result.fund_security_weights).to_csv(
        output / "fund_portfolio_monthly.csv", index=False
    )
    result.fund_returns.to_csv(output / "fund_returns_monthly.csv", index_label="date")
