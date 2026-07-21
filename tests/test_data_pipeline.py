from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from iitauquant_data.core import canonical_ticker, normalize_month_end, yahoo_ticker
from iitauquant_data.factors import parse_monthly_french
from iitauquant_data.fundamentals import _extract_companyfacts
from iitauquant_data.macro import ingest_macro_file
from iitauquant_data.quality import audit_fundamentals, audit_prices, infer_frequency
from iitauquant_data.universe import ingest_holdings


class TickerTests(unittest.TestCase):
    def test_normalizes_class_ticker_for_yahoo(self) -> None:
        self.assertEqual(canonical_ticker(" brk.b "), "BRK.B")
        self.assertEqual(yahoo_ticker("BRK.B"), "BRK-B")

    def test_rejects_empty_ticker(self) -> None:
        with self.assertRaises(ValueError):
            canonical_ticker("--")


class DateTests(unittest.TestCase):
    def test_normalizes_to_calendar_month_end(self) -> None:
        result = normalize_month_end(["2026-01-05", "2026-02-27"])
        self.assertEqual(list(result.strftime("%Y-%m-%d")), ["2026-01-31", "2026-02-28"])

    def test_frequency_detection(self) -> None:
        dates = pd.date_range("2024-01-31", periods=12, freq="ME")
        self.assertEqual(infer_frequency(dates), "monthly")


class FrenchParserTests(unittest.TestCase):
    def test_parses_monthly_block_and_decimal_units(self) -> None:
        text = "description\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n202401,1.00,-2.00,3.00,4.00,5.00,0.40\n202402,-99.99,1,2,3,4,0.4\n\n Annual Factors\n"
        result = parse_monthly_french(text)
        self.assertAlmostEqual(float(result.loc[0, "Mkt-RF"]), 0.01)
        self.assertTrue(pd.isna(result.loc[1, "Mkt-RF"]))
        self.assertEqual(result.loc[0, "date"], pd.Timestamp("2024-01-31"))


class FundamentalsTests(unittest.TestCase):
    def test_sec_extractor_keeps_annual_duration_not_quarter(self) -> None:
        payload = {
            "cik": 1,
            "entityName": "Example",
            "facts": {"us-gaap": {"GrossProfit": {"units": {"USD": [
                {"val": 25, "start": "2024-10-01", "end": "2024-12-31", "filed": "2025-02-10", "form": "10-K", "fy": 2024, "fp": "FY", "accn": "a"},
                {"val": 100, "start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-10", "form": "10-K", "fy": 2024, "fp": "FY", "accn": "a"},
            ]}}}},
        }
        result = _extract_companyfacts(payload, "ABC", {"10-K"})
        self.assertEqual(result["value"].tolist(), [100])
        self.assertEqual(result["duration_days"].tolist(), [365])


class MacroImportTests(unittest.TestCase):
    def test_ingests_tradingview_unix_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tv.csv"
            source.write_text("time,close\n1577836800,4.0\n1580428800,5.0\n", encoding="utf-8")
            with patch("iitauquant_data.macro.write_dataset"):
                result = ingest_macro_file(source, series_id="TEST")
            self.assertEqual(result["date"].dt.strftime("%Y-%m-%d").tolist(), ["2020-01-31"])
            self.assertEqual(result["value"].tolist(), [5.0])


class QualityTests(unittest.TestCase):
    def test_price_audit_detects_duplicate_and_extreme_return(self) -> None:
        frame = pd.DataFrame(
            {
                "month_end": ["2024-01-31", "2024-02-29", "2024-02-29"],
                "ticker": ["ABC", "ABC", "ABC"],
                "adjusted_close": [10.0, 20.0, 20.0],
                "return": [None, 1.0, 1.0],
            }
        )
        codes = {issue.code for issue in audit_prices(frame)}
        self.assertIn("duplicate_key", codes)
        self.assertIn("extreme_return", codes)

    def test_fundamental_audit_detects_lookahead_date_error(self) -> None:
        frame = pd.DataFrame(
            {
                "ticker": ["ABC"], "metric": ["assets"], "fiscal_year": [2024],
                "fiscal_period_end": ["2024-12-31"], "availability_date": ["2024-12-01"], "value": [1.0],
            }
        )
        codes = {issue.code for issue in audit_fundamentals(frame)}
        self.assertIn("invalid_availability_date", codes)
        self.assertIn("incomplete_fundamentals", codes)


class HoldingsTests(unittest.TestCase):
    def test_ingest_marks_snapshot_not_point_in_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "holdings.csv"
            source.write_text("Ticker,Name\nABC,Alpha\nBRK.B,Berkshire\n--,Cash\n", encoding="utf-8")
            # A escrita final usa a raiz do projeto, mas o arquivo temporario de entrada
            # prova a deteccao/normalizacao da coluna.
            with patch("iitauquant_data.universe.write_dataset"):
                result = ingest_holdings(source, fund="TEST", as_of="2026-07-20")
            self.assertEqual(set(result["provider_ticker"]), {"ABC", "BRK-B"})
            self.assertFalse(bool(result["point_in_time"].any()))


if __name__ == "__main__":
    unittest.main()
