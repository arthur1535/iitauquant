"""Entrypoint único: coleta, auditoria, análise e relatório swing em USD."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .engine import analyze
from .market_data import snapshot_data


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or config.get("currency") != "USD":
        raise ValueError("config requer schema_version=1 e currency=USD")
    tickers = [item["ticker"] for item in config["assets"]]
    if not tickers or len(tickers) != len(set(tickers)) or any(not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker) for ticker in tickers):
        raise ValueError("universo vazio, duplicado ou ticker inválido")
    if config["benchmark"] not in tickers:
        raise ValueError("benchmark precisa constar no universo")
    for key in ("holding_days", "stop_atr", "min_dollar_volume", "min_history", "max_stale_business_days", "min_oos_trades"):
        if not np.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"{key} deve ser positivo e finito")
    for key in ("holding_days", "min_history", "max_stale_business_days", "min_oos_trades"):
        if int(config[key]) != config[key]:
            raise ValueError(f"{key} deve ser inteiro")
    if config["min_history"] < 120:
        raise ValueError("min_history deve ser >= 120 para aquecimento e teste cronológico")
    for key in ("cost_per_side", "stress_cost_per_side", "risk_budget", "max_position_weight"):
        if not np.isfinite(config[key]) or not 0 < config[key] < 1:
            raise ValueError(f"{key} deve estar entre 0 e 1")
    if config["stress_cost_per_side"] < config["cost_per_side"]:
        raise ValueError("custo de estresse deve ser >= custo base")
    pd.Timestamp(config["start"])
    return config


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pesquisa swing de ações e ETFs USD; somente simulação")
    parser.add_argument("--config", type=Path, default=Path("config/swing_us.json"))
    parser.add_argument("--as-of", default=datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/swing_us"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    try:
        as_of = pd.Timestamp(args.as_of).date().isoformat()
        if pd.Timestamp(as_of) > pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize():
            raise ValueError("--as-of não pode ser uma data futura")
        config = load_config(args.config)
        output = args.output_dir or Path("results/investment_research") / as_of
        frames, sources, failures = snapshot_data(config, args.data_dir, as_of, refresh=args.refresh, offline=args.offline)
        ranking, exclusions, correlation = analyze(frames, config, as_of)
        config["methodology"] = [
            "USD; ações e ETFs sem alavancagem; universo atual selecionado manualmente, sujeito a viés de sobrevivência e seleção.",
            "Filtro: close > média20 > média50, retorno20 positivo, desempenho20 superior ao SPY (SPY dispensa essa condição), SPY > média50, distância da média20 ≤ 3 ATR14 e liquidez mínima declarada.",
            "Score: percentis de momentum20/vol20 (35%), momentum60/vol20 (25%), retorno20 menos SPY/vol20 (25%) e distância da máxima60 (15%). OOS não entra no score; score não é probabilidade nem retorno esperado.",
            "Backtest por ativo: 100% do capital quando sinal, caixa rende zero, sem alavancagem. Decisão no fechamento; compra e saída de tendência/tempo na abertura seguinte. Stop móvel de 2 ATR; gap preenche na abertura; limite de 10 pregões; encerramento final com custo.",
            "Divisão cronológica 70/30 em calendário comum; indicadores aquecem no trecho anterior; teste começa sem posição e sem sinal herdado. Regras pré-fixadas nesta revisão, sem otimização. OOS retrospectivo não equivale a histórico prospectivo.",
            "Custos por ponta e estresse declarados; SPY e buy & hold usam a mesma janela de teste e fricção bilateral. Sharpe com taxa livre de risco zero; não ajustado por múltiplas comparações entre ativos.",
            "Referência de tamanho = mínimo(teto de peso, orçamento de risco / distância percentual do stop). Não é carteira pronta: gaps, correlação e custos podem exceder o risco; stop precisa ser recalculado no preço real de execução.",
            "Preços OHLC ajustados por Adj Close/Close; último fechamento e referência de stop reconvertidos à escala bruta atual. Sessão corrente excluída até 17h de Nova York. Feriados não integram a contagem aproximada de dias úteis.",
        ]
        warnings = [
            "Triagem técnica para pesquisa em 5–10 pregões. Não demonstra preço justo, vantagem futura ou aprovação para operar.",
            "Datas de resultados, notícias, spreads, composição e sobreposição de ETFs precisam de checagem antes de qualquer operação; não foram validadas por este modelo.",
            "Retornos em USD, antes de impostos, câmbio BRL/USD, corretagem fixa e eventual diferença entre liquidez do ETF e dos componentes.",
            "Dados Yahoo são uma fonte pública secundária; ajustes históricos podem ser revisados. Manifestos e SHA256 identificam o snapshot analisado.",
        ]
        if not any(row["status"] == "candidato" for row in ranking):
            warnings.insert(0, "Nenhum ativo passou por todos os filtros. Aguardar também é uma conclusão válida.")
        payload = json_safe({"as_of": as_of, "generated_at": datetime.now(timezone.utc).isoformat(),
                             "config": config, "ranking": ranking, "exclusions": failures + exclusions,
                             "sources": sources, "correlation": correlation, "warnings": warnings,
                             "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
                             "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in Path(__file__).parent.glob("*.py")}})
        output.mkdir(parents=True, exist_ok=True)
        # Escrever JSON estrito também comprova ausência de NaN/Infinity no relatório.
        (output / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        pd.DataFrame(payload["ranking"]).to_csv(output / "ranking.csv", index=False)
        pd.DataFrame(payload["exclusions"], columns=["ticker", "reason"]).to_csv(output / "exclusions.csv", index=False)
        from .report import write_reports
        report = write_reports(payload, output)
        print(f"Relatório: {report.resolve()}")
        print(f"Data solicitada: {as_of}; último pregão: {ranking[0]['as_of']}; ativos: {len(ranking)}; exclusões: {len(failures + exclusions)}")
        for row in ranking[:5]:
            print(f"{row['ticker']:6} {row['status']:10} score={row['score']:.1f} retorno20={row['return_20d']:.2%} OOS={row['oos_return']:.2%} trades={row['oos_trades']}")
        return 0
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, f"Pesquisa indisponível: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
