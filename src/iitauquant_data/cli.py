from __future__ import annotations

import argparse
import json
import sys
from .core import load_config
from .factors import collect_fama_french
from .fundamentals import collect_sec_fundamentals
from .macro import collect_fred_series, ingest_macro_file
from .prices import collect_adjusted_prices
from .quality import run_full_audit
from .universe import collect_sp500, ingest_holdings


def _tickers(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coleta e auditoria dos dados do fundo multi-sleeve")
    parser.add_argument("--config", default=None, help="Caminho do JSON de configuracao")
    sub = parser.add_subparsers(dest="command", required=True)
    prices = sub.add_parser("prices", help="Coletar precos ajustados mensais")
    prices.add_argument("--tickers", required=True, help="Lista separada por virgula")
    prices.add_argument("--start", default=None)
    prices.add_argument("--end", default=None)
    prices.add_argument("--refresh", action="store_true")
    prices.add_argument("--output", default="precos_mensais.csv")
    fred = sub.add_parser("fred", help="Coletar serie do FRED")
    fred.add_argument("--series", default="BAMLH0A0HYM2")
    fred.add_argument("--file", default=None, help="CSV alternativo/licenciado com historico completo")
    fred.add_argument("--date-column", default=None)
    fred.add_argument("--value-column", default=None)
    fred.add_argument("--source-label", default="arquivo fornecido pela equipe")
    fred.add_argument("--refresh", action="store_true")
    factors = sub.add_parser("factors", help="Coletar FF5 + Momentum")
    factors.add_argument("--refresh", action="store_true")
    sp500 = sub.add_parser("sp500", help="Coletar composicao atual do S&P 500")
    sp500.add_argument("--refresh", action="store_true")
    fundamentals = sub.add_parser("fundamentals", help="Coletar fundamentos anuais SEC")
    fundamentals.add_argument("--tickers", default=None, help="Lista; sem ela usa amostra do config")
    fundamentals.add_argument("--sec-user-agent", default=None, help="Nome e email exigidos pela SEC")
    fundamentals.add_argument("--refresh", action="store_true")
    holdings = sub.add_parser("holdings", help="Normalizar arquivo de holdings do gestor")
    holdings.add_argument("--file", required=True)
    holdings.add_argument("--fund", required=True)
    holdings.add_argument("--as-of", required=True)
    holdings.add_argument("--ticker-column", default=None)
    sub.add_parser("audit", help="Auditar todos os datasets disponiveis")
    reference = sub.add_parser("reference", help="Coletar universo, referencias, FRED e fatores")
    reference.add_argument("--refresh", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "prices":
        frame, failed = collect_adjusted_prices(_tickers(args.tickers), args.start or config["prices"]["start"], args.end, refresh=args.refresh, output_name=args.output)
        print(json.dumps({"rows": len(frame), "failed_tickers": failed}, ensure_ascii=False))
    elif args.command == "fred":
        if args.file:
            frame = ingest_macro_file(args.file, series_id=args.series, date_column=args.date_column, value_column=args.value_column, source_label=args.source_label)
        else:
            frame = collect_fred_series(args.series, refresh=args.refresh)
        print(json.dumps({"rows": len(frame), "series": args.series}))
    elif args.command == "factors":
        frame = collect_fama_french(refresh=args.refresh)
        print(json.dumps({"rows": len(frame)}))
    elif args.command == "sp500":
        frame = collect_sp500(refresh=args.refresh)
        print(json.dumps({"rows": len(frame), "point_in_time": False}))
    elif args.command == "fundamentals":
        selected = _tickers(args.tickers) if args.tickers else config["fundamentals"]["sample_tickers"]
        frame, failed = collect_sec_fundamentals(selected, forms=config["fundamentals"]["forms"], refresh=args.refresh, user_agent=args.sec_user_agent)
        print(json.dumps({"rows": len(frame), "failed_tickers": failed}, ensure_ascii=False))
    elif args.command == "holdings":
        frame = ingest_holdings(args.file, fund=args.fund, as_of=args.as_of, ticker_column=args.ticker_column)
        print(json.dumps({"rows": len(frame), "fund": args.fund.upper(), "point_in_time": False}))
    elif args.command == "reference":
        collect_sp500(refresh=args.refresh)
        collect_adjusted_prices(config["prices"]["reference_tickers"], config["prices"]["start"], refresh=args.refresh)
        for series in config["fred"]["series"]:
            collect_fred_series(series, refresh=args.refresh)
        collect_fama_french(refresh=args.refresh)
        _, summary = run_full_audit(config)
        print(json.dumps(summary, ensure_ascii=False))
    elif args.command == "audit":
        _, summary = run_full_audit(config)
        print(json.dumps(summary, ensure_ascii=False))
        return 1 if summary["status"] == "FAIL" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
