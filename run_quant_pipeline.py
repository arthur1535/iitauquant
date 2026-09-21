"""Executa o pipeline quantitativo a partir de arquivos CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant_fund import (
    RiskOverlayConfig,
    Sleeve1Config,
    Sleeve2Config,
    export_pipeline_result,
    long_prices_to_wide,
    run_pipeline,
    sec_facts_to_fundamentals,
)


def _wide_csv(path: Path, value_column: str = "adjusted_close") -> pd.DataFrame:
    frame = pd.read_csv(path)
    if {"month_end", "ticker", value_column}.issubset(frame.columns):
        return long_prices_to_wide(frame, value_column=value_column)
    if value_column != "adjusted_close":
        raise ValueError(
            f"{path} está em formato wide; forneça market_cap nos fundamentos ou "
            "um CSV longo que também contenha a coluna close."
        )
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _fundamentals_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if {"metric", "value", "fiscal_period_end", "availability_date"}.issubset(frame.columns):
        return sec_facts_to_fundamentals(frame)
    return frame


def _series_csv(path: Path, value_column: str | None = None) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    if value_column is not None:
        if value_column not in frame:
            raise ValueError(f"Coluna {value_column!r} ausente em {path}.")
        return frame[value_column]
    if frame.shape[1] != 1:
        raise ValueError(f"{path} deve ter exatamente uma coluna de valores.")
    return frame.iloc[:, 0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("dados"))
    parser.add_argument("--output-dir", type=Path, default=Path("resultados") / "quant")
    parser.add_argument("--sleeve1-top-n", type=int, default=50)
    parser.add_argument("--sleeve1-rebalance-month", type=int, default=6)
    parser.add_argument("--sleeve2-top-fraction", type=float, default=0.05)
    parser.add_argument("--stress-entry-z", type=float, default=1.0)
    parser.add_argument("--stress-exit-z", type=float, default=0.5)
    parser.add_argument(
        "--financial-conditions-file",
        type=Path,
        help=(
            "CSV de condições financeiras, relativo a --input-dir. "
            "Se omitido, usa financial_conditions.csv quando existente."
        ),
    )
    parser.add_argument("--overlay-window-months", type=int, default=36)
    parser.add_argument("--overlay-min-periods", type=int, default=24)
    parser.add_argument("--max-derisk", type=float, default=0.50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input_dir
    membership_path = source / "small_cap_membership.csv"
    membership = _wide_csv(membership_path) if membership_path.exists() else None
    factor_path = source / "factor_prices.csv"
    fundamentals = _fundamentals_csv(source / "factor_fundamentals.csv")
    needs_close = "market_cap" not in fundamentals or fundamentals["market_cap"].isna().any()
    if args.financial_conditions_file is None:
        default_financial_path = source / "financial_conditions.csv"
        financial_path = default_financial_path if default_financial_path.exists() else None
    else:
        financial_path = args.financial_conditions_file
        if not financial_path.is_absolute():
            financial_path = source / financial_path
        if not financial_path.exists():
            raise FileNotFoundError(f"Arquivo de condições financeiras ausente: {financial_path}")
    financial_conditions = (
        _series_csv(financial_path, "NFCI") if financial_path is not None else None
    )
    result = run_pipeline(
        factor_prices=_wide_csv(factor_path),
        factor_market_prices=_wide_csv(factor_path, "close") if needs_close else None,
        fundamentals=fundamentals,
        small_cap_prices=_wide_csv(source / "small_cap_prices.csv"),
        credit_spread=_series_csv(source / "credit_spread.csv", "spread"),
        bil_prices=_series_csv(source / "bil_prices.csv", "BIL"),
        universe_membership=membership,
        sleeve1_config=Sleeve1Config(
            top_n=args.sleeve1_top_n,
            rebalance_month=args.sleeve1_rebalance_month,
        ),
        sleeve2_config=Sleeve2Config(
            selection_fraction=args.sleeve2_top_fraction,
            stress_entry_z=args.stress_entry_z,
            stress_exit_z=args.stress_exit_z,
        ),
        financial_conditions=financial_conditions,
        risk_overlay_config=(
            RiskOverlayConfig(
                zscore_window_months=args.overlay_window_months,
                zscore_min_periods=args.overlay_min_periods,
                stress_entry_z=args.stress_entry_z,
                stress_exit_z=args.stress_exit_z,
                max_derisk=args.max_derisk,
            )
            if financial_conditions is not None
            else None
        ),
    )
    export_pipeline_result(result, args.output_dir)
    print(f"Resultados exportados para {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
