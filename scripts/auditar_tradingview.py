"""Sanitiza exportações do TradingView e reconcilia o painel LASTRO.

Os CSVs baixados pelo TradingView incluem todos os indicadores presentes no
layout. Este script preserva apenas as séries do LASTRO, compara os fechamentos
com as bases do repositório e gera um registro auditável sem carregar colunas de
estratégias privadas ou não relacionadas ao projeto.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dados"
OUTPUT_DATA = DATA / "tradingview" / "lastro_tradingview_mensal.csv"
OUTPUT_JSON = ROOT / "resultados" / "auditoria_tradingview.json"
OUTPUT_MD = ROOT / "resultados" / "auditoria_tradingview.md"

Z_BAA = "z-score BAA10Y (fechado)"
Z_NFCI = "z-score NFCI (fechado)"
REGIME_CHANGE = "Mudança de regime"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baa10y", type=Path, required=True)
    parser.add_argument("--nfci", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def maybe_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def read_export(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"time", "close", Z_BAA, Z_NFCI, REGIME_CHANGE}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: colunas ausentes: {sorted(missing)}")
        rows: list[dict[str, object]] = []
        for row in reader:
            month = datetime.fromtimestamp(int(row["time"]), timezone.utc).strftime("%Y-%m")
            rows.append(
                {
                    "mes": month,
                    "close": maybe_float(row["close"]),
                    "z_baa10y_fechado": maybe_float(row[Z_BAA]),
                    "z_nfci_fechado": maybe_float(row[Z_NFCI]),
                    "mudanca_regime": int(float(row[REGIME_CHANGE] or 0)),
                }
            )
    return rows


def read_repo_series(path: Path, month_col: str, value_col: str) -> dict[str, float]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            row[month_col]: float(row[value_col])
            for row in csv.DictReader(stream)
            if row.get(month_col) and row.get(value_col)
        }


def compare_series(observed: dict[str, float], expected: dict[str, float]) -> dict[str, object]:
    months = sorted(set(observed).intersection(expected))
    diffs = {month: abs(observed[month] - expected[month]) for month in months}
    divergent = {month: value for month, value in diffs.items() if value > 1e-9}
    return {
        "meses_comparados": len(months),
        "primeiro_mes": months[0],
        "ultimo_mes": months[-1],
        "divergencias": len(divergent),
        "maior_diferenca_absoluta": max(diffs.values(), default=0.0),
        "meses_divergentes": divergent,
    }


def hysteresis(z_values: list[float | None], entry: float = 1.0, exit_: float = 0.5) -> bool:
    stressed = False
    for value in z_values:
        if value is None:
            continue
        if not stressed and value > entry:
            stressed = True
        elif stressed and value < exit_:
            stressed = False
    return stressed


def main() -> int:
    args = parse_args()
    baa_rows = read_export(args.baa10y)
    nfci_rows = read_export(args.nfci)
    baa_by_month = {str(row["mes"]): row for row in baa_rows}
    nfci_by_month = {str(row["mes"]): row for row in nfci_rows}
    common_months = sorted(set(baa_by_month).intersection(nfci_by_month))
    if not common_months:
        raise ValueError("As exportações não têm meses em comum")

    indicator_mismatches = 0
    clean_rows: list[dict[str, object]] = []
    for month in common_months:
        baa = baa_by_month[month]
        nfci = nfci_by_month[month]
        for column in ("z_baa10y_fechado", "z_nfci_fechado", "mudanca_regime"):
            if baa[column] != nfci[column]:
                indicator_mismatches += 1
        clean_rows.append(
            {
                "mes": month,
                "BAA10Y": baa["close"],
                "NFCI": nfci["close"],
                "z_baa10y_fechado": baa["z_baa10y_fechado"],
                "z_nfci_fechado": baa["z_nfci_fechado"],
                "mudanca_regime": baa["mudanca_regime"],
            }
        )

    OUTPUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_DATA.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(clean_rows[0]))
        writer.writeheader()
        writer.writerows(clean_rows)

    repo_baa = read_repo_series(DATA / "macro_BAA10Y_mensal.csv", "mes", "BAA10Y")
    repo_nfci = read_repo_series(DATA / "macro_NFCI_mensal.csv", "mes", "NFCI")
    observed_baa = {str(row["mes"]): float(row["BAA10Y"]) for row in clean_rows}
    observed_nfci = {str(row["mes"]): float(row["NFCI"]) for row in clean_rows}

    latest = clean_rows[-1]
    latest_confirmed = clean_rows[-2]
    credit_stressed = hysteresis([row["z_baa10y_fechado"] for row in clean_rows])
    conditions_stressed = hysteresis([row["z_nfci_fechado"] for row in clean_rows])
    active_axes = int(credit_stressed) + int(conditions_stressed)
    derisk = 0.5 * active_axes / 2
    weights = {
        "factor": 1 / 3,
        "small_caps": (1 / 3) * (1 - derisk),
        "bil_renda_fixa": (1 / 3) * (1 + derisk),
    }

    audit = {
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "origem": "TradingView Premium Desktop; intervalo 1M; janela Todos",
        "arquivos_brutos": {
            "BAA10Y": {"nome": args.baa10y.name, "sha256": sha256(args.baa10y)},
            "NFCI": {"nome": args.nfci.name, "sha256": sha256(args.nfci)},
        },
        "arquivo_sanitizado": str(OUTPUT_DATA.relative_to(ROOT)).replace("\\", "/"),
        "linhas_sanitizadas": len(clean_rows),
        "periodo_exportado": [common_months[0], common_months[-1]],
        "colunas_privadas_descartadas": True,
        "divergencias_entre_exports_nos_plots_lastro": indicator_mismatches,
        "reconciliacao_repositorio": {
            "BAA10Y": compare_series(observed_baa, repo_baa),
            "NFCI": compare_series(observed_nfci, repo_nfci),
        },
        "estado_operacional": {
            "mes_corrente_parcial": latest["mes"],
            "ultimo_mes_fechado": latest_confirmed["mes"],
            "BAA10Y_fechado": latest_confirmed["BAA10Y"],
            "NFCI_fechado": latest_confirmed["NFCI"],
            "z_BAA10Y_aplicado": latest["z_baa10y_fechado"],
            "z_NFCI_aplicado": latest["z_nfci_fechado"],
            "eixos_acesos": active_axes,
            "regime": "NORMAL" if active_axes == 0 else f"DEFENSIVO {active_axes}/2",
            "derisk_do_sleeve_tatico": derisk,
            "pesos": weights,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state = audit["estado_operacional"]
    reconciliation = audit["reconciliacao_repositorio"]
    markdown = f"""# Auditoria TradingView Premium - LASTRO

- Exportação: intervalo mensal, janela **Todos**, {len(clean_rows)} observações entre {common_months[0]} e {common_months[-1]}.
- Privacidade: apenas BAA10Y, NFCI e os três plots do LASTRO foram preservados; colunas de outros indicadores foram descartadas.
- Reconciliação: BAA10Y com {reconciliation['BAA10Y']['divergencias']} divergências em {reconciliation['BAA10Y']['meses_comparados']} meses; NFCI com {reconciliation['NFCI']['divergencias']} divergências em {reconciliation['NFCI']['meses_comparados']} meses.
- Último mês fechado ({state['ultimo_mes_fechado']}): BAA10Y {state['BAA10Y_fechado']:.3f}; NFCI {state['NFCI_fechado']:.3f}.
- Sinal aplicado em {state['mes_corrente_parcial']}: z BAA10Y {state['z_BAA10Y_aplicado']:.2f}; z NFCI {state['z_NFCI_aplicado']:.2f}; regime **{state['regime']}** ({state['eixos_acesos']}/2 eixos).
- Pesos vigentes: Factor {weights['factor']:.2%}; Small Caps {weights['small_caps']:.2%}; BIL/renda fixa {weights['bil_renda_fixa']:.2%}.

Hashes dos CSVs brutos e todos os valores numéricos estão em `resultados/auditoria_tradingview.json`.
"""
    OUTPUT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
