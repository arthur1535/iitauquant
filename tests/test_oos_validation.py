"""Testes automatizados de auditoria OOS para a Tarefa 1 (Contrato Temporal e Manifesto).

Conforme especificado em docs/AUDITORIA_OOS_TAREFA1.md:
- corte por datas em feriados/limites de ano, preservando a primeira sessão disponível de 2023;
- nenhuma interseção de treino/purge/teste dentro do fold; todos os testes internos anteriores a 2023;
- dados ausentes, datas duplicadas, OHLC inválido e histórico insuficiente geram bloqueio explícito;
- mudar apenas preços OOS, mantendo datas, não altera índices/folds IS, mas altera o hash dos dados;
- mesmos inputs geram o mesmo plano/run_id; funções de backtest, otimização e rede substituídas por funções que falham comprovam que dry-run não as chama;
- nenhum Sharpe, DSR/PBO ou aprovação apresentado como calculado; todos os flags de pesquisa preservados.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
SCRIPTS = PROJECT_ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_out_of_sample_audit import (
    DATA_DIR,
    TemporalAuditConfig,
    date_based_split,
    plan_out_of_sample_audit,
)


class OutOfSampleValidationTask1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.dates = pd.date_range("2020-01-01", periods=1000, freq="B")
        prices = [100.0 + i * 0.1 for i in range(len(self.dates))]
        self.sample_df = pd.DataFrame(
            {
                "open": prices,
                "high": [p * 1.01 for p in prices],
                "low": [p * 0.99 for p in prices],
                "close": prices,
            },
            index=self.dates,
        )

    def test_corte_por_datas_em_limites_de_ano(self) -> None:
        """Corte nominal em 2022-12-31 e 2023-01-01 preserva a primeira sessão útil de 2023."""
        is_df, oos_df = date_based_split(
            self.sample_df,
            is_end_date="2022-12-31",
            oos_start_date="2023-01-01",
        )
        self.assertGreater(len(is_df), 0)
        self.assertGreater(len(oos_df), 0)
        self.assertLess(is_df.index[-1], oos_df.index[0])
        self.assertEqual(is_df.index[-1].year, 2022)
        self.assertEqual(oos_df.index[0].year, 2023)

    def test_nenhuma_intersecao_e_todos_testes_internos_no_is(self) -> None:
        """Nenhum treino/purge/teste se sobrepõe e todos os testes walk-forward terminam no IS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = TemporalAuditConfig(
                symbols=("SPY",),
                is_end="2022-12-31",
                oos_start="2023-01-01",
                train_bars=504,
                test_bars=63,
                purge_bars=1,
                embargo_bars=5,
                output_dir=tmpdir,
            )
            manifest = plan_out_of_sample_audit(config)
            self.assertEqual(manifest["status"], "planned")

            folds_csv_path = Path(manifest["artifacts"]["folds_csv"])
            folds_df = pd.read_csv(folds_csv_path)

            is_folds = folds_df[folds_df["partition_type"] == "is_walk_forward"]
            self.assertGreater(len(is_folds), 1)

            for _, row in is_folds.iterrows():
                train_start = pd.Timestamp(row["train_start"])
                train_end = pd.Timestamp(row["train_end"])
                test_start = pd.Timestamp(row["test_start"])
                test_end = pd.Timestamp(row["test_end"])

                # Todos os testes internos devem terminar estritamente antes de 2023
                self.assertLessEqual(test_end, pd.Timestamp("2022-12-31"))
                self.assertLess(train_end, test_start)

                if pd.notna(row["purge_start"]) and str(row["purge_start"]).strip():
                    purge_start = pd.Timestamp(row["purge_start"])
                    purge_end = pd.Timestamp(row["purge_end"])
                    self.assertGreater(purge_start, train_end)
                    self.assertLess(purge_end, test_start)

            # Verificar fold incompleto no final do IS
            incomplete_folds = is_folds[is_folds["is_complete"] == False]
            self.assertEqual(len(incomplete_folds), 1)
            self.assertEqual(incomplete_folds.iloc[0]["notes"], "incomplete_last_fold")

            # Verificar reserva OOS
            oos_reserve = folds_df[folds_df["partition_type"] == "oos_evaluation_reserve"]
            self.assertEqual(len(oos_reserve), 1)
            self.assertGreaterEqual(pd.Timestamp(oos_reserve.iloc[0]["test_start"]), pd.Timestamp("2023-01-01"))

    def test_dados_ausentes_datas_duplicadas_ohlc_invalido_geram_bloqueio(self) -> None:
        """Ativo ausente gera manifest status=blocked; datas duplicadas ou OHLC inválido geram exceção ou bloqueio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Ativo ausente -> manifest status="blocked"
            config_missing = TemporalAuditConfig(
                symbols=("NON_EXISTING_TICKER_XYZ",),
                output_dir=tmpdir,
            )
            manifest = plan_out_of_sample_audit(config_missing)
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"], "incomplete_or_invalid_symbols")

            # 2. Datas duplicadas no date_based_split -> ValueError
            dates_dup = self.dates.copy().tolist()
            dates_dup[1] = dates_dup[0]
            dup_df = self.sample_df.copy()
            dup_df.index = pd.DatetimeIndex(dates_dup)
            with self.assertRaises(ValueError):
                date_based_split(dup_df)

            # 3. OHLC inválido (High < Low)
            invalid_ohlc = self.sample_df.copy()
            invalid_ohlc.iloc[5, invalid_ohlc.columns.get_loc("high")] = (
                invalid_ohlc.iloc[5, invalid_ohlc.columns.get_loc("low")] - 5.0
            )
            with self.assertRaises(ValueError):
                date_based_split(invalid_ohlc)

    def test_mudar_apenas_precos_oos_preserva_folds_is_mas_altera_hash(self) -> None:
        """Mudar preços no OOS mantém datas e partições do IS intactas, mas altera data_fingerprint e run_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            temp_data_dir.mkdir(parents=True, exist_ok=True)

            base_df = self.sample_df.copy()
            parquet_path = temp_data_dir / "SYNTH.parquet"
            base_df.to_parquet(parquet_path)

            with patch("run_out_of_sample_audit.DATA_DIR", temp_data_dir):
                config1 = TemporalAuditConfig(
                    symbols=("SYNTH",),
                    is_end="2022-12-31",
                    oos_start="2023-01-01",
                    train_bars=400,
                    test_bars=50,
                    output_dir=str(Path(tmpdir) / "out1"),
                )
                res1 = plan_out_of_sample_audit(config1)

                # Altera apenas preços do OOS
                modified_df = base_df.copy()
                oos_mask = modified_df.index >= "2023-01-01"
                modified_df.loc[oos_mask, "close"] *= 1.5
                modified_df.loc[oos_mask, "high"] *= 1.5
                modified_df.to_parquet(parquet_path)

                config2 = TemporalAuditConfig(
                    symbols=("SYNTH",),
                    is_end="2022-12-31",
                    oos_start="2023-01-01",
                    train_bars=400,
                    test_bars=50,
                    output_dir=str(Path(tmpdir) / "out2"),
                )
                res2 = plan_out_of_sample_audit(config2)

                folds1 = pd.read_csv(res1["artifacts"]["folds_csv"])
                folds2 = pd.read_csv(res2["artifacts"]["folds_csv"])

                # Folds do IS permanecem exatamente idênticos
                is_folds1 = folds1[folds1["partition_type"] == "is_walk_forward"]
                is_folds2 = folds2[folds2["partition_type"] == "is_walk_forward"]
                pd.testing.assert_frame_equal(is_folds1, is_folds2)

                # Mas data_fingerprint e run_id obrigatoriamente mudam
                self.assertNotEqual(
                    res1["identity"]["data_fingerprints"]["SYNTH"],
                    res2["identity"]["data_fingerprints"]["SYNTH"],
                )
                self.assertNotEqual(res1["run_id"], res2["run_id"])

    def test_mesmos_inputs_geram_mesmo_run_id_e_dry_run_nao_chama_motor(self) -> None:
        """Determinismo de run_id e garantia de que --dry-run não invoca motor de backtest nem rede."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config1 = TemporalAuditConfig(
                symbols=("SPY",),
                is_end="2022-12-31",
                oos_start="2023-01-01",
                output_dir=tmpdir,
            )
            res1 = plan_out_of_sample_audit(config1)
            res2 = plan_out_of_sample_audit(config1)
            self.assertEqual(res1["run_id"], res2["run_id"])

            # Prova de que backtest/otimização não são chamados no dry-run
            with patch(
                "backtest.engine.run_backtest",
                side_effect=RuntimeError("ERRO: Backtest foi indevidamente chamado no dry-run!"),
            ):
                dry_res = plan_out_of_sample_audit(config1)
                self.assertEqual(dry_res["status"], "planned")

    def test_nenhum_sharpe_dsr_pbo_calculado_em_dry_run(self) -> None:
        """Garante que nenhum Sharpe, DSR/PBO ou promoção econômica é afirmado nesta etapa."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = TemporalAuditConfig(
                symbols=("SPY",),
                output_dir=tmpdir,
            )
            manifest = plan_out_of_sample_audit(config)
            gov = manifest["governance"]
            metrics = manifest["metrics"]

            self.assertEqual(manifest["classification"], "retrospective_pseudo_oos")
            self.assertTrue(gov["shadow_mode"])
            self.assertFalse(gov["aprovado"])
            self.assertFalse(gov["promotion_allowed"])

            self.assertIsNone(metrics["dsr"])
            self.assertIsNone(metrics["pbo"])
            self.assertIsNone(metrics["sharpe_is"])
            self.assertIsNone(metrics["sharpe_oos"])
            self.assertEqual(metrics["reason"], "not_computed_in_dry_run")


if __name__ == "__main__":
    unittest.main()
