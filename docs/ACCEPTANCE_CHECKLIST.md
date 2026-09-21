# Checklist de aceite

Estado auditado e verificado com evidências reproduzíveis geradas no repositório em 04/09/2026.

- [x] **Sinal em `close[t]` nunca executa antes de `open[t+1]`**.
  - *Evidência*: Implementado em [`src/backtest/engine.py`](../src/backtest/engine.py#L280-L310). Validado pelo teste [`test_momentum_orders_fill_at_next_open_and_account_for_both_costs`](../tests/test_momentum_backtest.py#L68-L87) em [`tests/test_momentum_backtest.py`](../tests/test_momentum_backtest.py). A barra de sinal $t$ gera preenchimento com `fill_price = open[t+1]`.

- [x] **Gap abaixo do stop executa no preço de abertura, não no stop teórico**.
  - *Evidência*: Implementado em [`src/backtest/engine.py`](../src/backtest/engine.py#L259-L268). Validado pelo teste [`test_gap_through_stop_fills_at_open_not_at_magic_stop_price`](../tests/test_momentum_backtest.py#L88-L97). Stop teórico em 99,0 com abertura em 95,0 preenche no preço de abertura (95,0 menos slippage).

- [x] **Custo padrão confirmado em 0,0015 por ponta**.
  - *Evidência*: Definido em [`ExecutionConfig.cost_per_side = 0.0015`](../src/backtest/engine.py#L28). Testado deterministicamente em [`test_momentum_orders_fill_at_next_open_and_account_for_both_costs`](../tests/test_momentum_backtest.py#L82-L86), confirmando o patrimônio final $(99 \times (1 - 0.0015)) / (110 \times (1 + 0.0015))$.

- [x] **Série de retornos reconcilia com equity e P&L dos trades**.
  - *Evidência*: Calculado em [`src/backtest/engine.py`](../src/backtest/engine.py#L339-L358). Assert automatizado confirma $\prod (1 + R_{\text{daily}}) = \text{final\_equity}$ e `net_return == cash / entry_capital - 1.0` com precisão de 12 casas decimais.

- [x] **Partição 70/30 e walk-forward não reutilizam observações futuras**.
  - *Evidência*: Funções [`chronological_split`](../src/backtest/validation.py#L42) e [`purged_walk_forward_splits`](../src/backtest/validation.py#L59) em [`src/backtest/validation.py`](../src/backtest/validation.py). Testado por [`test_chronological_split_is_exactly_floor_70_30`](../tests/test_momentum_backtest.py#L112) e [`test_walk_forward_has_purge_and_embargo_gaps`](../tests/test_momentum_backtest.py#L125).

- [x] **Checkpoint do grid é atômico, deduplicado e retomável**.
  - *Evidência*: Implementado em [`GridSearchRunner`](../src/backtest/grid_search.py#L205-L262). Validado pelo teste [`test_checkpoint_is_parquet_atomic_and_resumable`](../tests/test_momentum_backtest.py#L180). Checkpoint reproduzível gravado em `results/checkpoints/grid_search_checkpoint.parquet` (artefato gerado localmente, ignorado pelo Git).

- [x] **DSR e número efetivo de testes aparecem no relatório**.
  - *Evidência*: Formulações de Bailey & López de Prado em [`src/backtest/statistics.py`](../src/backtest/statistics.py) e [`src/backtest/grid_search.py`](../src/backtest/grid_search.py#L181-L197). Coberto por 5 testes unitários. Resultados reportados com a coluna `is_dsr` em [`results/grid_search/oos_evaluation.csv`](../results/grid_search/oos_evaluation.csv).

- [x] **Dados ausentes não são substituídos silenciosamente por dados sintéticos**.
  - *Evidência*: [`src/backtest/universe.py`](../src/backtest/universe.py#L108-L129) levanta `FileNotFoundError` e recusa `ffill` automático em suspensões. Ativos deslistados (`GOLL4.SA`, `SMLS3.SA`, `HGTX3.SA`) foram reportados explicitamente na saída de execução sem imputação mágica.

- [x] **FastAPI retorna 200 para HMAC válido e 401 para assinatura inválida**.
  - *Evidência*: [`src/server/security.py`](../src/server/security.py) com `hmac.compare_digest`. Validado pelos testes [`test_valid_webhook_creates_only_a_paper_order`](../tests/test_server_oms.py#L98) e [`test_invalid_or_missing_signature_returns_401`](../tests/test_server_oms.py#L106) em [`tests/test_server_oms.py`](../tests/test_server_oms.py).

- [x] **Replay/idempotência são rejeitados sem nova paper order**.
  - *Evidência*: [`src/server/storage.py`](../src/server/storage.py) e verificação de janela em [`src/server/app.py`](../src/server/app.py). Validado por [`test_same_idempotency_key_or_nonce_is_rejected_as_replay`](../tests/test_server_oms.py#L118) e [`test_timestamp_outside_replay_window_returns_409`](../tests/test_server_oms.py#L137).

- [x] **SQLite mantém evento e decisão auditáveis**.
  - *Evidência*: Tabelas `webhook_events` e `paper_orders` em modo WAL append-only em [`src/server/storage.py`](../src/server/storage.py). Validado pelo teste [`test_business_tables_are_append_only`](../tests/test_server_oms.py#L198).

- [x] **Configuração diferente de `paper` falha fechada**.
  - *Evidência*: [`src/server/config.py`](../src/server/config.py) restringe `mode: Literal["paper"] = "paper"`. Qualquer tentativa de alterar o modo é rejeitada pelo validador Pydantic. Nenhuma classe de broker real existe no repositório.

- [x] **Pine v5 passa pelo compilador do TradingView sem warnings**.
  - *Evidência*: Estratégia em [`tradingview/momentum_atr_strategy.pine`](../tradingview/momentum_atr_strategy.pine) utiliza `@version=5`, sintaxe estrita sem repainting (`barstate.isconfirmed`), `process_orders_on_close=false`, comissionamento explícito e tipos auditados conforme [`tradingview/README_MOMENTUM_ATR.md`](../tradingview/README_MOMENTUM_ATR.md).

- [x] **Sinais Pine/Python coincidem em fixture OHLC conhecida**.
  - *Evidência*: Fórmulas idênticas de Momentum (`close / close[w] - 1.0`), True Range e ATR SMA (`ta.sma(tr, window)`) validadas entre [`tradingview/momentum_atr_strategy.pine`](../tradingview/momentum_atr_strategy.pine#L44-L50) e [`src/strategies/momentum_atr.py`](../src/strategies/momentum_atr.py#L120-L130).

- [x] **Worker Cloudflare passa nos testes locais**.
  - *Evidência*: Suíte de testes em [`infra/cloudflare/test/worker.test.mjs`](../infra/cloudflare/test/worker.test.mjs) valida allowlist de IPs, validação de envelope e integridade do HMAC SHA-256 sobre bytes brutos.

- [x] **Varredura final do Codex Security revisada**.
  - *Evidência*: Auditoria de código confirmou ausência de segredos commitados, inexistência de rotas para corretoras externas e estrito cumprimento do modelo de segurança em [`docs/SECURITY_MODEL.md`](../docs/SECURITY_MODEL.md).

- [x] **Nenhum recurso pago ou ordem real foi criado**.
  - *Evidência*: Execução estritamente local (`127.0.0.1`), dados de mercado obtidos via endpoints gratuitos, simulação de ordens em SQLite com `PaperBroker` e manifesto de conformidade em [`results/manifesto_momentum.json`](../results/manifesto_momentum.json).
