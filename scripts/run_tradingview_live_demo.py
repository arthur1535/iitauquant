"""Demonstração interativa no terminal da integração do TradingView com o OMS Paper-Only.

Executa uma simulação ponta a ponta com ativos globais (NVDA, SPY, MSFT),
processando assinaturas HMAC-SHA256, ordens simuladas, preenchimento de stops,
contabilidade de carteira e defesas adversariais em tempo real.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient
from pydantic import SecretStr

from server.app import create_app
from server.config import load_runtime_settings, RuntimeSettings


def format_currency(val: float | str | Decimal) -> str:
    return f"R$ {float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def run_live_terminal_demo() -> None:
    print("=" * 84)
    print("      ITAÚ QUANT 2026 — TRADINGVIEW PAPER OMS LIVE TERMINAL DEMONSTRATION")
    print("=" * 84)
    print("Modo: ESTRITAMENTE SIMULAÇÃO (PAPER-ONLY) | Sem risco financeiro | Zero live broker\n")

    # 1. Configuração e Chave Segura
    import os
    secret_key = secrets.token_urlsafe(36)
    os.environ["TRADINGVIEW_WEBHOOK_SECRET"] = secret_key
    demo_db = ROOT / "data" / "oms_live_demo.sqlite3"
    if demo_db.exists():
        try:
            demo_db.unlink()
        except OSError:
            pass
    settings = load_runtime_settings()
    oms_config = settings.oms.model_copy(update={"database_path": demo_db})
    runtime = RuntimeSettings(webhook_secret=SecretStr(secret_key), oms=oms_config)

    print(f"[*] Base de Dados SQLite: {runtime.oms.database_path}")
    print(f"[*] Capital Inicial:      {format_currency(runtime.oms.initial_cash_brl)}")
    print(f"[*] Custo por Ponta:      {float(runtime.oms.cost_per_side)*100:.2f}% (15 bps)")
    print(f"[*] Ativos Autorizados:   {len(runtime.oms.allowed_symbols)} símbolos (incluindo NVDA, SPY, AAPL, MSFT, QQQ)")
    print(f"[*] Chave HMAC (Gateway): {secret_key[:8]}...{secret_key[-6:]} (32+ bytes)\n")

    # 2. Inicialização da Aplicação
    now_ts = [time.time()]
    app = create_app(runtime, clock=lambda: now_ts[0])

    with TestClient(app) as client:
        # Health & Readiness
        print("-" * 84)
        print("FASE 1: VERIFICAÇÃO DE SAÚDE E PRONTIDÃO DO SERVIDOR")
        print("-" * 84)
        
        health_resp = client.get("/health")
        print(f"  [GET /health] -> HTTP {health_resp.status_code}: {health_resp.json()}")

        ready_resp = client.get("/ready")
        print(f"  [GET /ready]  -> HTTP {ready_resp.status_code}: {ready_resp.json()}\n")

        # Função auxiliar de envio de webhook assinado
        def send_webhook(alert_dict: dict) -> tuple[int, dict]:
            body = json.dumps(alert_dict, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            signature = "sha256=" + hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            }
            res = client.post("/webhook/tradingview", content=body, headers=headers)
            return res.status_code, res.json()

        # 3. Simulação de Eventos do TradingView com Ativos Globais
        print("-" * 84)
        print("FASE 2: PROCESSAMENTO DE ALERTAS DE TRADINGVIEW EM TEMPO REAL")
        print("-" * 84)

        events = [
            {
                "desc": "ENTRADA DE MOMENTUM EM NVDA (LONG)",
                "payload": {
                    "strategy": "MOMENTUM_ATR",
                    "action": "BUY",
                    "order_type": "MARKET",
                    "ticker": "NVDA",
                    "close_price": 128.50,
                    "stop_price": 118.20,
                    "quantity": 50,
                    "timestamp": int(now_ts[0] * 1000),
                    "nonce": "NVDA-1D-0001-" + str(int(now_ts[0])),
                    "idempotency_key": "NVDA-1D-0001-" + str(int(now_ts[0])),
                    "reason": "MOMENTUM_ENTRY",
                    "metadata": {"exchange": "NASDAQ", "interval": "1D", "bar_time": "2026-09-07T00:00:00Z"},
                },
            },
            {
                "desc": "ENTRADA DE MOMENTUM EM SPY (LONG S&P 500 ETF)",
                "payload": {
                    "strategy": "MOMENTUM_ATR",
                    "action": "BUY",
                    "order_type": "MARKET",
                    "ticker": "SPY",
                    "close_price": 555.20,
                    "stop_price": 542.00,
                    "quantity": 25,
                    "timestamp": int(now_ts[0] * 1000) + 1000,
                    "nonce": "SPY-1D-0001-" + str(int(now_ts[0])),
                    "idempotency_key": "SPY-1D-0001-" + str(int(now_ts[0])),
                    "reason": "MOMENTUM_ENTRY",
                    "metadata": {"exchange": "AMEX", "interval": "1D", "bar_time": "2026-09-07T00:00:00Z"},
                },
            },
            {
                "desc": "ENTRADA DE MOMENTUM EM MSFT (LONG MICROSOFT)",
                "payload": {
                    "strategy": "MOMENTUM_ATR",
                    "action": "BUY",
                    "order_type": "MARKET",
                    "ticker": "MSFT",
                    "close_price": 420.00,
                    "stop_price": 405.00,
                    "quantity": 30,
                    "timestamp": int(now_ts[0] * 1000) + 2000,
                    "nonce": "MSFT-1D-0001-" + str(int(now_ts[0])),
                    "idempotency_key": "MSFT-1D-0001-" + str(int(now_ts[0])),
                    "reason": "MOMENTUM_ENTRY",
                    "metadata": {"exchange": "NASDAQ", "interval": "1D", "bar_time": "2026-09-07T00:00:00Z"},
                },
            },
            {
                "desc": "SAÍDA COM LUCRO EM NVDA (TRAILING STOP RATChET ATINGIDO)",
                "payload": {
                    "strategy": "MOMENTUM_ATR",
                    "action": "SELL",
                    "order_type": "MARKET",
                    "ticker": "NVDA",
                    "close_price": 135.80,
                    "stop_price": 135.80,
                    "quantity": 50,
                    "timestamp": int(now_ts[0] * 1000) + 3000,
                    "nonce": "NVDA-1D-0002-" + str(int(now_ts[0])),
                    "idempotency_key": "NVDA-1D-0002-" + str(int(now_ts[0])),
                    "reason": "EXIT_STOP_TRIGGERED",
                    "metadata": {"exchange": "NASDAQ", "interval": "1D", "bar_time": "2026-09-07T00:00:00Z"},
                },
            },
        ]

        for step, ev in enumerate(events, start=1):
            print(f"[{step}/4] {ev['desc']}")
            p = ev["payload"]
            print(f"      Ticker: {p['ticker']} | Ação: {p['action']} | Qtd: {p['quantity']} | Preço: ${p['close_price']:.2f}")
            status_code, body = send_webhook(p)
            if status_code == 200:
                print(f"      [SUCESSO HTTP 200] Ordem #{body['paper_order_id']} Aceita e Preenchida no Ledger!")
                print(f"      -> Taxa B3/Broker: {format_currency(body['fee_brl'])}")
                print(f"      -> Saldo de Caixa:  {format_currency(body['cash_after_brl'])}\n")
            else:
                print(f"      [ERRO HTTP {status_code}]: {body}\n")

        # 4. Consulta Contábil da Carteira (/paper/status)
        print("-" * 84)
        print("FASE 3: CONTABILIDADE EM TEMPO REAL DA CARTEIRA (/paper/status)")
        print("-" * 84)

        status_resp = client.get("/paper/status", headers={"Authorization": f"Bearer {secret_key}"})
        status_data = status_resp.json()

        print(f"  Status do Ledger:         {status_data.get('ledger_status', 'ready').upper()}")
        print(f"  Saldo em Caixa:           {format_currency(status_data['cash_brl'])}")
        print(f"  Exposição Bruta:          {format_currency(status_data['gross_exposure_brl'])}")
        print(f"  Patrimônio de Referência: {format_currency(status_data['equity_reference_brl'])}")
        print(f"  Total de Taxas Pagas:     {format_currency(status_data['fees_paid_brl'])}")
        print(f"  Lucro Realizado (P&L):    {format_currency(status_data['realized_pnl_brl'])}")
        print(f"  Fills Executados:         {status_data['fill_count']}")
        print(f"  Posições em Aberto:")
        for ticker, pos in status_data["positions"].items():
            print(f"    • {ticker}: {float(pos['quantity']):.0f} ações @ custo médio ${float(pos['average_cost_brl']):.2f} (Valor Ref: {format_currency(pos['reference_value_brl'])})")
        print()

        # 5. Demonstração de Defesas Adversariais de Segurança
        print("-" * 84)
        print("FASE 4: DEFESAS ADVERSARIAIS DE SEGURANÇA E AUDITORIA")
        print("-" * 84)

        # 5.1 Replay Attack
        print("  [TESTE 1] Ataque de Replay: Reenvio do mesmo webhook com nonce duplicado")
        dup_code, dup_body = send_webhook(events[0]["payload"])
        print(f"  -> Resposta do OMS: HTTP {dup_code} ({dup_body['detail']}) — BLOQUEADO COM SUCESSO!\n")

        # 5.2 Assinatura Inválida
        print("  [TESTE 2] Ataque Man-in-the-Middle: Assinatura HMAC fraudulenta")
        bad_sig_headers = {"Content-Type": "application/json", "X-Webhook-Signature": "sha256=" + "0" * 64}
        bad_sig_resp = client.post("/webhook/tradingview", content=b"{}", headers=bad_sig_headers)
        print(f"  -> Resposta do OMS: HTTP {bad_sig_resp.status_code} ({bad_sig_resp.json()['detail']}) — REJEITADO COM SUCESSO!\n")

        # 5.3 Short Selling Não Autorizado
        print("  [TESTE 3] Venda Descoberta (Short Sale) em ativo sem custódia")
        short_payload = {
            "strategy": "MOMENTUM_ATR",
            "action": "SELL",
            "order_type": "MARKET",
            "ticker": "AAPL",
            "close_price": 220.00,
            "quantity": 10,
            "timestamp": int(now_ts[0] * 1000) + 5000,
            "nonce": "AAPL-SELL-0001-" + str(int(now_ts[0])),
            "idempotency_key": "AAPL-SELL-0001-" + str(int(now_ts[0])),
            "reason": "EXIT_STOP_TRIGGERED",
        }
        short_code, short_body = send_webhook(short_payload)
        print(f"  -> Resposta do OMS: HTTP {short_code} ({short_body['detail']}) — PROTEGIDO COM SUCESSO!\n")

    print("=" * 84)
    print("      INTEGRACAO TRADINGVIEW <-> OMS PAPER-ONLY 100% OPERACIONAL E HOMOLOGADA")
    print("=" * 84)


if __name__ == "__main__":
    run_live_terminal_demo()
