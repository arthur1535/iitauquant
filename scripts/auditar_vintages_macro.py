"""Reconstrói BAA10Y e NFCI como eram conhecidos em cada fechamento mensal.

O FRED/TradingView mostra hoje a melhor estimativa disponível do passado. Para
um backtest point-in-time, este script consulta o ALFRED com ``vintage_date``
igual ao fim de cada mês, recalcula o z-score dentro daquela fotografia e salva
a diagonal das vintages. O endpoint ``alfredgraph.csv`` não exige API key.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant_fund.risk_overlay import (  # noqa: E402
    RiskOverlayConfig,
    hysteresis_state,
    rolling_zscore,
)

DATA = ROOT / "dados"
RESULTS = ROOT / "resultados"
OUTPUT = DATA / "macro_point_in_time_mensal.csv"
AUDIT_JSON = RESULTS / "auditoria_vintages_macro.json"
AUDIT_MD = RESULTS / "auditoria_vintages_macro.md"
ALFRED_CSV = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
SERIES = ("BAA10Y", "NFCI")
WINDOWS = (24, 36, 48)
CFG = RiskOverlayConfig()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2011-05", help="primeira vintage YYYY-MM")
    parser.add_argument("--end", default="2026-07", help="última vintage YYYY-MM")
    parser.add_argument("--audit-start", default="2018-02")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def _unrevised_fallback(series_id: str, month: pd.Period, vintage: str) -> dict[str, object]:
    """Fallback pré-arquivo para BAA10Y, uma série de preços de mercado.

    O ALFRED só começa a servir algumas vintages de BAA10Y depois do início da
    série. Esses meses são anteriores ao backtest; usamos a série final truncada
    no corte, sem qualquer observação futura, apenas para inicializar a histerese.
    """

    if series_id != "BAA10Y":
        raise ValueError("Fallback permitido somente para BAA10Y")
    monthly = _final_series(series_id).loc[:month]
    if monthly.empty:
        raise ValueError(f"Sem fallback local para {series_id} {month}")
    row: dict[str, object] = {
        "mes": str(month),
        f"{series_id}_vintage_date": vintage,
        f"{series_id}_observation_date": month.end_time.date().isoformat(),
        f"{series_id}_point_in_time": float(monthly.iloc[-1]),
        f"{series_id}_snapshot_source": "FRED truncado; ALFRED sem arquivo",
    }
    for window in WINDOWS:
        min_periods = CFG.zscore_min_periods if window == 36 else window
        zscore = rolling_zscore(monthly.rename(series_id), window, min_periods)
        value = zscore.iloc[-1]
        row[f"{series_id}_z_{window}_point_in_time"] = (
            float(value) if pd.notna(value) else math.nan
        )
    return row


def _snapshot(series_id: str, month: pd.Period) -> dict[str, object]:
    vintage = month.end_time.date().isoformat()
    start = (month - 72).start_time.date().isoformat()
    url = (
        f"{ALFRED_CSV}?id={series_id}&cosd={start}&coed={vintage}"
        f"&vintage_date={vintage}"
    )
    error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(
                url,
                timeout=40,
                headers={"User-Agent": "iitauquant-point-in-time-audit/1.0"},
            )
            if response.status_code == 404 and series_id == "BAA10Y":
                return _unrevised_fallback(series_id, month, vintage)
            response.raise_for_status()
            frame = pd.read_csv(io.StringIO(response.text))
            if frame.shape[1] != 2:
                raise ValueError(f"Resposta ALFRED inesperada: {frame.columns.tolist()}")
            dates = pd.to_datetime(frame.iloc[:, 0], errors="coerce")
            values = pd.to_numeric(frame.iloc[:, 1], errors="coerce")
            raw = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
            if raw.empty:
                raise ValueError("Vintage sem observações")
            monthly = raw.resample("ME").last()
            monthly.index = monthly.index.to_period("M")
            available = monthly.index[monthly.index <= month]
            if available.empty:
                raise ValueError("Vintage sem mês elegível")
            last_month = available[-1]
            row: dict[str, object] = {
                "mes": str(month),
                f"{series_id}_vintage_date": vintage,
                f"{series_id}_observation_date": raw.index.max().date().isoformat(),
                f"{series_id}_point_in_time": float(monthly.loc[last_month]),
                f"{series_id}_snapshot_source": "ALFRED",
            }
            for window in WINDOWS:
                min_periods = CFG.zscore_min_periods if window == 36 else window
                zscore = rolling_zscore(monthly.rename(series_id), window, min_periods)
                value = zscore.loc[last_month]
                row[f"{series_id}_z_{window}_point_in_time"] = (
                    float(value) if pd.notna(value) else math.nan
                )
            return row
        except Exception as exc:  # pragma: no cover - depende da rede
            error = exc
            if attempt < 3:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Falha em {series_id} {month}: {error}")


def _load_existing() -> pd.DataFrame:
    if not OUTPUT.exists():
        return pd.DataFrame()
    frame = pd.read_csv(OUTPUT, index_col="mes")
    frame.index = pd.PeriodIndex(frame.index, freq="M")
    return frame


def _final_series(series_id: str) -> pd.Series:
    path = DATA / f"macro_{series_id}_mensal.csv"
    series = pd.read_csv(path, index_col=0)[series_id]
    series.index = pd.PeriodIndex(series.index, freq="M")
    return pd.to_numeric(series, errors="coerce").sort_index()


def _complete(frame: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    frame = frame.reindex(months)
    frame.index.name = "mes"
    for series_id in SERIES:
        z_col = f"{series_id}_z_36_point_in_time"
        state_col = f"{series_id}_state_point_in_time"
        frame[state_col] = hysteresis_state(
            pd.to_numeric(frame[z_col], errors="coerce"),
            CFG.stress_entry_z,
            CFG.stress_exit_z,
        ).astype(int)

        final = _final_series(series_id)
        frame[f"{series_id}_final"] = final.reindex(months)
        for window in WINDOWS:
            min_periods = CFG.zscore_min_periods if window == 36 else window
            final_z = rolling_zscore(final.rename(series_id), window, min_periods)
            frame[f"{series_id}_z_{window}_final"] = final_z.reindex(months)
        final_state = hysteresis_state(
            rolling_zscore(
                final.rename(series_id), CFG.zscore_window_months, CFG.zscore_min_periods
            ),
            CFG.stress_entry_z,
            CFG.stress_exit_z,
        )
        frame[f"{series_id}_state_final"] = final_state.reindex(months).fillna(0).astype(int)
        frame[f"{series_id}_state_changed"] = (
            frame[state_col] != frame[f"{series_id}_state_final"]
        ).astype(int)

    frame["votes_point_in_time"] = sum(
        frame[f"{series_id}_state_point_in_time"] for series_id in SERIES
    )
    frame["votes_final"] = sum(frame[f"{series_id}_state_final"] for series_id in SERIES)
    frame["derisk_signal_point_in_time"] = CFG.max_derisk * frame["votes_point_in_time"] / 2
    frame["derisk_signal_final"] = CFG.max_derisk * frame["votes_final"] / 2
    frame["derisk_applied_point_in_time"] = (
        frame["derisk_signal_point_in_time"].shift(1).fillna(0.0)
    )
    frame["derisk_applied_final"] = frame["derisk_signal_final"].shift(1).fillna(0.0)
    return frame


def _audit(frame: pd.DataFrame, audit_start: pd.Period) -> dict[str, object]:
    sample = frame.loc[audit_start:]
    by_series: dict[str, object] = {}
    for series_id in SERIES:
        by_series[series_id] = {
            "meses": int(len(sample)),
            "mudancas_de_estado": int(sample[f"{series_id}_state_changed"].sum()),
            "mae_nivel": float(
                (
                    sample[f"{series_id}_point_in_time"]
                    - sample[f"{series_id}_final"]
                ).abs().mean()
            ),
            "mae_z_36": float(
                (
                    sample[f"{series_id}_z_36_point_in_time"]
                    - sample[f"{series_id}_z_36_final"]
                ).abs().mean()
            ),
        }
    changed_votes = sample["votes_point_in_time"] != sample["votes_final"]
    changed_applied = (
        sample["derisk_applied_point_in_time"] != sample["derisk_applied_final"]
    )
    latest = frame.iloc[-1]
    return {
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "fonte": "ALFRED alfredgraph.csv; vintage_date = fim de cada mês",
        "config": asdict(CFG),
        "periodo": {"inicio": str(frame.index.min()), "fim": str(frame.index.max())},
        "amostra_backtest": {
            "inicio": str(sample.index.min()),
            "fim": str(sample.index.max()),
            "meses": int(len(sample)),
        },
        "por_serie": by_series,
        "meses_com_votos_diferentes": int(changed_votes.sum()),
        "meses_com_derisk_aplicado_diferente": int(changed_applied.sum()),
        "cutoff_mais_recente": {
            series_id: {
                "vintage": latest[f"{series_id}_vintage_date"],
                "observacao": latest[f"{series_id}_observation_date"],
                "nivel": float(latest[f"{series_id}_point_in_time"]),
                "z_36": float(latest[f"{series_id}_z_36_point_in_time"]),
                "estado": int(latest[f"{series_id}_state_point_in_time"]),
            }
            for series_id in SERIES
        },
    }


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 16:
        raise ValueError("--workers deve ficar entre 1 e 16")
    months = pd.period_range(args.start, args.end, freq="M")
    existing = pd.DataFrame() if args.refresh else _load_existing()
    rows: list[dict[str, object]] = []
    tasks: list[tuple[str, pd.Period]] = []
    for month in months:
        for series_id in SERIES:
            required = f"{series_id}_z_36_point_in_time"
            if month not in existing.index or required not in existing or pd.isna(existing.loc[month, required]):
                tasks.append((series_id, month))

    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(_snapshot, sid, month): (sid, month) for sid, month in tasks}
            for count, future in enumerate(as_completed(futures), start=1):
                rows.append(future.result())
                if count % 40 == 0 or count == len(futures):
                    print(f"ALFRED: {count}/{len(futures)} snapshots", flush=True)

    fresh = pd.DataFrame(rows)
    if not fresh.empty:
        fresh["mes"] = pd.PeriodIndex(fresh["mes"], freq="M")
        fresh = fresh.set_index("mes")
        # Cada tarefa preenche apenas um eixo; consolida por mês sem perder o outro.
        fresh = fresh.groupby(level=0).first()
        base = existing.combine_first(fresh) if not existing.empty else fresh
        base.update(fresh)
    else:
        base = existing

    completed = _complete(base, months)
    if completed[[f"{sid}_point_in_time" for sid in SERIES]].isna().any().any():
        raise RuntimeError("Há vintages ausentes no resultado final")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    completed.to_csv(OUTPUT, index_label="mes")

    audit = _audit(completed, pd.Period(args.audit_start, freq="M"))
    AUDIT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Auditoria point-in-time das séries macro",
        "",
        f"Período: {audit['periodo']['inicio']} a {audit['periodo']['fim']}.",
        f"Amostra do backtest: {audit['amostra_backtest']['meses']} meses.",
        "",
        "| Série | Mudanças de estado | MAE nível | MAE z(36) |",
        "|---|---:|---:|---:|",
    ]
    for sid in SERIES:
        item = audit["por_serie"][sid]
        lines.append(
            f"| {sid} | {item['mudancas_de_estado']} | {item['mae_nivel']:.4f} | {item['mae_z_36']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Meses com voto agregado diferente: {audit['meses_com_votos_diferentes']}.",
            f"Meses com de-risking aplicado diferente: {audit['meses_com_derisk_aplicado_diferente']}.",
            "",
            "A vintage final do FRED/TradingView é adequada para monitoramento corrente, mas não",
            "substitui esta diagonal de vintages em um backtest histórico.",
        ]
    )
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "OK | "
        f"{months.min()}..{months.max()} | "
        f"votos diferentes={audit['meses_com_votos_diferentes']} | "
        f"derisk diferente={audit['meses_com_derisk_aplicado_diferente']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
