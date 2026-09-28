"""Prepara sinais de bets somente a partir de informações já disponíveis.

Entradas CSV:
  trends: week_end,available_at,interest,vintage_id
  regulation: available_at,regulation_score,source

week_end é a data do último dia COMPLETO da semana, no fuso --timezone.
available_at exige ISO8601 com offset. Uma extração feita hoje deve carregar a
disponibilidade real de hoje, nunca a data retrospectiva da semana observada.
Esta versão não resolve revisões: rejeita semanas duplicadas e disponibilidades
fora de ordem. Semanas de uma mesma extração podem compartilhar available_at;
nesse caso, apenas a semana mais recente fica visível naquele instante.

O sinal é -Z da diferença semanal de log(1 + interest), contra até 52 diferenças
ANTERIORES, com mínimo de 26 e desvio amostral. Dados incompletos/desvio zero
produzem NaN, não autorização para negociar. Trends mede atenção, não gasto.
Regulação é uma anotação documentada do pesquisador, não inferida de notícias.
Os templates não contêm observações. Não se baixa nem se inventa série aqui.

Exemplo:
  python scripts/build_bets_features.py --trends trends.csv \
      --regulation regulatory_snapshots.csv --output bets_features.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


TREND_COLUMNS = ["week_end", "available_at", "interest", "vintage_id"]
REGULATION_COLUMNS = ["available_at", "regulation_score", "source"]
OUTPUT_COLUMNS = ["available_at", "search_relief_z", "regulation_score", "vintage_id"]


def _require_columns(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{name}: colunas ausentes: {sorted(missing)}")


def _timestamps(values: pd.Series, name: str) -> pd.Series:
    """Normaliza instantes para UTC, recusando inferir fuso de datas ingênuas."""
    parsed = []
    for value in values:
        try:
            stamp = pd.Timestamp(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: timestamp inválido {value!r}") from exc
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise ValueError(f"{name}: use timestamp ISO8601 com offset explícito")
        parsed.append(stamp.tz_convert("UTC"))
    return pd.Series(parsed, index=values.index, dtype="datetime64[ns, UTC]")


def _nonempty(values: pd.Series, name: str) -> None:
    if values.isna().any() or values.astype(str).str.strip().eq("").any():
        raise ValueError(f"{name}: valores vazios não são permitidos")


def build_features(
    trends: pd.DataFrame,
    regulatory_snapshots: pd.DataFrame,
    timezone: str = "America/Sao_Paulo",
) -> pd.DataFrame:
    """Une sinais nos instantes de publicação, usando apenas asof para trás.

    Retorna available_at consciente de fuso (UTC). A saída inclui mudanças de
    qualquer fonte; valores de uma fonte ainda não publicada ficam ausentes.
    Não aplica backfill, não interpola e não atribui score a um evento jurídico.
    """
    _require_columns(trends, TREND_COLUMNS, "trends")
    _require_columns(regulatory_snapshots, REGULATION_COLUMNS, "regulation")
    if trends.empty:
        raise ValueError("trends: template vazio; forneça observações reais documentadas")
    trend = trends[TREND_COLUMNS].copy()
    regulation = regulatory_snapshots[REGULATION_COLUMNS].copy()
    _nonempty(trend["vintage_id"], "vintage_id")
    if not trend["week_end"].astype(str).map(
        lambda value: bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    ).all():
        raise ValueError("week_end: use somente a data YYYY-MM-DD")
    trend["week_end"] = pd.to_datetime(trend["week_end"], errors="raise")
    if trend["week_end"].duplicated().any():
        raise ValueError("week_end duplicado: revisões/vintages repetidos não são suportados")
    trend["available_at"] = _timestamps(trend["available_at"], "trends.available_at")
    trend = trend.sort_values("week_end").reset_index(drop=True)
    if not trend["week_end"].diff().dropna().eq(pd.Timedelta(days=7)).all():
        raise ValueError("week_end: a série deve ser semanal, sem lacunas")
    if not trend["available_at"].is_monotonic_increasing:
        raise ValueError("available_at deve ser não decrescente na ordem das semanas")
    earliest = (trend["week_end"] + pd.Timedelta(days=1)).dt.tz_localize(
        timezone, nonexistent="raise", ambiguous="raise"
    ).dt.tz_convert("UTC")
    if (trend["available_at"] < earliest).any():
        raise ValueError("available_at antecede o fim completo da semana observada")
    trend["interest"] = pd.to_numeric(trend["interest"], errors="raise")
    if not np.isfinite(trend["interest"]).all() or not trend["interest"].between(0, 100).all():
        raise ValueError("interest deve ser finito e estar entre 0 e 100")

    delta = np.log1p(trend["interest"]).diff()
    previous = delta.shift(1).rolling(52, min_periods=26)
    denominator = previous.std(ddof=1).replace(0.0, np.nan)
    trend["search_relief_z"] = -(delta - previous.mean()) / denominator
    # Uma extração em lote não fabrica 52 datas passadas de conhecimento.
    trend = trend.drop_duplicates("available_at", keep="last")

    regulation["available_at"] = _timestamps(regulation["available_at"], "regulation.available_at")
    if regulation["available_at"].duplicated().any():
        raise ValueError("regulation.available_at duplicado: resolva o snapshot explicitamente")
    _nonempty(regulation["source"], "source")
    regulation["regulation_score"] = pd.to_numeric(regulation["regulation_score"], errors="raise")
    if not np.isfinite(regulation["regulation_score"]).all() or not regulation["regulation_score"].between(-1, 1).all():
        raise ValueError("regulation_score deve ser finito e estar entre -1 e 1")
    regulation = regulation.sort_values("available_at")
    timeline = pd.DataFrame({"available_at": pd.concat(
        [trend["available_at"], regulation["available_at"]]
    ).drop_duplicates().sort_values().reset_index(drop=True)})
    output = pd.merge_asof(
        timeline,
        trend[["available_at", "search_relief_z", "vintage_id"]].sort_values("available_at"),
        on="available_at", direction="backward", allow_exact_matches=True,
    )
    if regulation.empty:
        output["regulation_score"] = np.nan
    else:
        output = pd.merge_asof(
            output, regulation[["available_at", "regulation_score"]],
            on="available_at", direction="backward", allow_exact_matches=True,
        )
    return output[OUTPUT_COLUMNS]


def main() -> None:
    """Lê CSVs auditáveis e salva o painel sem remover o fuso dos timestamps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trends", required=True, type=Path)
    parser.add_argument("--regulation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timezone", default="America/Sao_Paulo")
    args = parser.parse_args()
    result = build_features(pd.read_csv(args.trends), pd.read_csv(args.regulation), args.timezone)
    result["available_at"] = result["available_at"].map(lambda stamp: stamp.isoformat())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"{len(result)} snapshots salvos em {args.output}")


if __name__ == "__main__":
    main()
