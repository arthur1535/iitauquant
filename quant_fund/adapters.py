"""Adaptadores para os datasets longos produzidos por ``iitauquant_data``."""

from __future__ import annotations

import pandas as pd


def long_prices_to_wide(
    prices: pd.DataFrame,
    *,
    date_column: str = "month_end",
    ticker_column: str = "ticker",
    value_column: str = "adjusted_close",
) -> pd.DataFrame:
    """Converte preços normalizados longos para a matriz usada pelos sleeves."""

    required = {date_column, ticker_column, value_column}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"Preços longos sem colunas: {sorted(missing)}")
    data = prices.loc[:, [date_column, ticker_column, value_column]].copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="raise")
    data[ticker_column] = data[ticker_column].astype(str)
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce")
    if data.duplicated([date_column, ticker_column]).any():
        raise ValueError("Preços longos contêm mais de uma observação por ticker-mês.")
    return data.pivot(index=date_column, columns=ticker_column, values=value_column).sort_index()


def sec_facts_to_fundamentals(facts: pd.DataFrame) -> pd.DataFrame:
    """Transforma fatos SEC longos em balanços anuais sem usar revisões futuras.

    Para cada métrica e exercício, preserva o primeiro filing disponível. A data de
    disponibilidade do balanço consolidado é a mais tardia entre os quatro campos.
    O valor de mercado será calculado no rebalanceamento com ações em circulação e
    preço de fechamento não ajustado daquela data.
    """

    required = {
        "ticker",
        "metric",
        "value",
        "fiscal_period_end",
        "availability_date",
    }
    missing = required.difference(facts.columns)
    if missing:
        raise ValueError(f"Fatos SEC sem colunas: {sorted(missing)}")
    metric_map = {
        "assets": "total_assets",
        "equity": "book_equity",
        "gross_profit": "gross_profit",
        "shares_outstanding": "shares_outstanding",
    }
    data = facts.loc[facts["metric"].isin(metric_map)].copy()
    if "fiscal_period" in data:
        data = data.loc[data["fiscal_period"].isna() | data["fiscal_period"].eq("FY")]
    data["fiscal_period_end"] = pd.to_datetime(data["fiscal_period_end"], errors="coerce")
    data["availability_date"] = pd.to_datetime(data["availability_date"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["tag_priority"] = pd.to_numeric(data.get("tag_priority", 0), errors="coerce").fillna(0)
    data = data.dropna(subset=["fiscal_period_end", "availability_date", "value"])
    data = data.sort_values(
        [
            "ticker",
            "fiscal_period_end",
            "metric",
            "availability_date",
            "tag_priority",
        ],
        kind="stable",
    )
    first_filing = data.drop_duplicates(
        ["ticker", "fiscal_period_end", "metric"], keep="first"
    )
    values = first_filing.pivot(
        index=["ticker", "fiscal_period_end"], columns="metric", values="value"
    ).rename(columns=metric_map)
    availability = first_filing.groupby(["ticker", "fiscal_period_end"])[
        "availability_date"
    ].max()
    result = values.join(availability).reset_index().rename(
        columns={"fiscal_period_end": "fiscal_date", "availability_date": "available_date"}
    )
    ordered = [
        "ticker",
        "fiscal_date",
        "available_date",
        "book_equity",
        "total_assets",
        "gross_profit",
        "shares_outstanding",
    ]
    for column in ordered:
        if column not in result:
            result[column] = pd.NA
    return result.loc[:, ordered].sort_values(["ticker", "fiscal_date"]).reset_index(drop=True)
