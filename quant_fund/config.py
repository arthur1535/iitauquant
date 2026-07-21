"""Parâmetros auditáveis das regras financeiras."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sleeve1Config:
    """Configuração do ranking fundamentalista anual."""

    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    top_n: int | None = 50
    selection_fraction: float | None = None
    rebalance_month: int = 6
    reporting_lag_months: int = 3
    max_statement_age_months: int | None = 18

    def __post_init__(self) -> None:
        _validate_winsor(self.winsor_lower, self.winsor_upper)
        if self.top_n is None and self.selection_fraction is None:
            raise ValueError("Defina top_n ou selection_fraction para o Sleeve 1.")
        if self.top_n is not None and self.top_n < 1:
            raise ValueError("top_n deve ser positivo.")
        if self.selection_fraction is not None and not 0 < self.selection_fraction <= 1:
            raise ValueError("selection_fraction deve estar em (0, 1].")
        if not 1 <= self.rebalance_month <= 12:
            raise ValueError("rebalance_month deve estar entre 1 e 12.")
        if self.reporting_lag_months < 0:
            raise ValueError("reporting_lag_months não pode ser negativo.")
        if self.max_statement_age_months is not None and self.max_statement_age_months < 1:
            raise ValueError("max_statement_age_months deve ser positivo ou None.")


@dataclass(frozen=True)
class Sleeve2Config:
    """Configuração dos sinais técnico e de regime."""

    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    selection_fraction: float = 0.05
    momentum_weight: float = 0.50
    reversal_weight: float = 0.50
    spread_window_months: int = 36
    stress_entry_z: float = 1.0
    stress_exit_z: float = 0.5
    bil_ticker: str = "BIL"

    def __post_init__(self) -> None:
        _validate_winsor(self.winsor_lower, self.winsor_upper)
        if not 0 < self.selection_fraction <= 1:
            raise ValueError("selection_fraction deve estar em (0, 1].")
        if self.momentum_weight < 0 or self.reversal_weight < 0:
            raise ValueError("Pesos dos sinais não podem ser negativos.")
        if abs(self.momentum_weight + self.reversal_weight - 1.0) > 1e-12:
            raise ValueError("Pesos de momentum e reversão devem somar 1.")
        if self.spread_window_months < 2:
            raise ValueError("spread_window_months deve ser pelo menos 2.")
        if self.stress_exit_z >= self.stress_entry_z:
            raise ValueError("O limiar de saída deve ser menor que o de entrada.")
        if not self.bil_ticker.strip():
            raise ValueError("bil_ticker não pode ser vazio.")


@dataclass(frozen=True)
class FundConfig:
    """Alocações estratégicas e defensivas do fundo consolidado."""

    normal_factor: float = 1 / 3
    normal_small_caps: float = 1 / 3
    normal_fixed_income: float = 1 / 3
    stress_factor: float = 1 / 3
    stress_small_caps: float = 0.0
    stress_fixed_income: float = 2 / 3

    def __post_init__(self) -> None:
        normal = self.normal_factor + self.normal_small_caps + self.normal_fixed_income
        stress = self.stress_factor + self.stress_small_caps + self.stress_fixed_income
        if min(
            self.normal_factor,
            self.normal_small_caps,
            self.normal_fixed_income,
            self.stress_factor,
            self.stress_small_caps,
            self.stress_fixed_income,
        ) < 0:
            raise ValueError("Alocações do fundo não podem ser negativas.")
        if abs(normal - 1.0) > 1e-12 or abs(stress - 1.0) > 1e-12:
            raise ValueError("As alocações de cada regime devem somar 1.")


def _validate_winsor(lower: float, upper: float) -> None:
    if not 0 <= lower < upper <= 1:
        raise ValueError("Quantis de winsorização inválidos.")
