# Central de Documentação Técnica e Governança — `iitauquant`

Este diretório centraliza os documentos de governança, arquitetura, pesquisa quantitativa, runbooks operacionais, relatórios técnicos e barramentos de colaboração com Inteligência Artificial do repositório **`iitauquant`** (Fundo LASTRO & Laboratório Momentum ATR).

---

## 1. Governança, Aceite e Auditoria

| Documento | Escopo e Finalidade |
|---|---|
| [`ACCEPTANCE_CHECKLIST.md`](ACCEPTANCE_CHECKLIST.md) | **17 critérios de aceite** formais e auditados com evidências reproduzíveis geradas no repositório (sem look-ahead, custos explícitos, gap stops, HMAC, modo paper-only). |
| [`DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md) | Governança da camada de dados point-in-time: proveniência, integridade OHLCV, tratamento de deslistadas e prevenção de vieses de sobrevivência. |
| [`SECURITY_MODEL.md`](SECURITY_MODEL.md) | Modelo de segurança em camadas: fail-closed, assinatura HMAC SHA-256 sobre bytes brutos, deduplicação de replay, allowlist de IPs e kill switch. |
| [`OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md) | Runbook operacional: procedimentos de deploy, monitoramento de webhooks, reconciliação diária de P&L e protocolo de emergência em incidentes. |

---

## 2. Pesquisa Econométrica e Validação Estatística

| Documento | Escopo e Finalidade |
|---|---|
| [`PESQUISA_METODOS_QUANTITATIVOS.md`](PESQUISA_METODOS_QUANTITATIVOS.md) | Frameworks matemáticos: DSR/PSR (Bailey & López de Prado), testes de múltiplos testes, blocos móveis bootstrap, placebos de shift circular e decomposição Fama-French 5 fatores + Momentum. |
| [`PESQUISA_CONTEXTO_MERCADO_ACOES.md`](PESQUISA_CONTEXTO_MERCADO_ACOES.md) | Enquadramento quantitativo de ativos (Big Tech, Blue Chips B3, Small Caps e Distressed) sob a ótica macro e fatorial recente (setembro/2026). |
| [`AUDITORIA_OOS_TAREFA1.md`](AUDITORIA_OOS_TAREFA1.md) | Auditoria Out-Of-Sample (OOS) com contrato temporal estrito: split cronológico 70/30 (treino até 2022-12-31 e teste a partir de 2023-01-01), manifestos com integridade por SHA-256. *(Sob revisão concorrente)* |
| [`../results/china_research/relatorio_pesquisa_china.md`](../results/china_research/relatorio_pesquisa_china.md) | Pesquisa quantitativa do mercado chinês: análise de ETFs (`MCHI`, `KWEB`, `FXI`, `ASHR`, `CQQQ`) e ADRs (`BABA`, `PDD`, `JD`, `BIDU`, `NIO`), mitigação de cauda com trailing stop e comparação causal. |
| [`../results/outliers_research/relatorio_pesquisa_outliers.md`](../results/outliers_research/relatorio_pesquisa_outliers.md) | Pesquisa quantitativa em outliers de hiper-crescimento e assimetria (`VRT`, `PLTR`, `CELH`, `SMCI`, `MSTR`, `FUTU`, `ASTS`, `APP`, `HIMS`), matemática de multi-baggers contra drawdowns de -85% e regras de sizing. |


---

## 3. Fundo Sistemático Multi-Sleeve (LASTRO)

Localizados em [`docs/fundo/`](fundo/):

| Documento | Escopo e Finalidade |
|---|---|
| [`fundo/relatorio_tecnico_fundo.md`](fundo/relatorio_tecnico_fundo.md) | Relatório técnico completo (20 páginas) detalhando a engenharia do fundo: Sleeve 1 (Fatores/Qualidade), Sleeve 2 (Small Cap Momentum), Sleeve 3 (Caixa/BIL), overlay macro BAA10Y + NFCI e atribuição Brinson-Fachler. |
| [`fundo/tutorial_desenvolvimento_fundo.md`](fundo/tutorial_desenvolvimento_fundo.md) | Tutorial prático passo a passo para replicação do fundo, download de demonstrações financeiras da SEC via XBRL e reconciliação dos rankings. |
| [`fundo/checklist_pre_relatorio_31_07.md`](fundo/checklist_pre_relatorio_31_07.md) | Checklist de consistência de dados, integridade de séries temporais e validação prévia à geração dos PDFs oficiais `AAKR.pdf`. |

---

## 4. Estratégias Algorítmicas, Plataformas e Dados

| Documento | Escopo e Finalidade |
|---|---|
| [`ARCHITECTURE_MOMENTUM.md`](ARCHITECTURE_MOMENTUM.md) | Arquitetura do motor Momentum ATR: pipeline orientado a eventos, trailing stops dinâmicos, walk-forward analysis com purging e embargo, e integração com o OMS paper. |
| [`TRADINGVIEW_CREATOR.md`](TRADINGVIEW_CREATOR.md) | Guia do criador Pine Script v5/v6: boas práticas sem repainting (`barstate.isconfirmed`), cálculo de ATR, dimensionamento de posição e disparos de alertas JSON. |
| [`quant_fund/README.md`](../quant_fund/README.md) | Pacote Python do fundo multi-sleeve: especificação das classes, regras de rebalanceamento, drift de preços e execução com `scripts/run_quant_pipeline.py`. |
| [`tradingview/README.md`](../tradingview/README.md) | Painel integrado no TradingView: indicadores de regime, estratégias de volatilidade alvo e modelos de alerta. |
| [`dados/README.md`](../dados/README.md) | Arquitetura da camada de dados mensais: cache bruto, datasets normalizados, sidecars `.meta.json` e manifestos de qualidade. |
| [`data/README.md`](../data/README.md) | Repositório local de cotações diárias em Parquet (`data/market/*.parquet`) e banco SQLite de simulação paper trading. |

---

## 5. Barramento de Inteligência Artificial e Protocolos de Colaboração

Localizados em [`docs/prompts/`](prompts/) e na raiz do repositório:

| Documento | Escopo e Finalidade |
|---|---|
| [`prompts/MEGAPROMPT_ANALISTA_INVESTIMENTOS.md`](prompts/MEGAPROMPT_ANALISTA_INVESTIMENTOS.md) | Prompt de sistema institucional padronizado para atuar como Analista de Investimentos Quantitativo Sênior & Buy-Side Portfolio Manager nos padrões do fundo LASTRO. |
| [`prompts/PROMPT_INTEGRACAO_CHATGPT.md`](prompts/PROMPT_INTEGRACAO_CHATGPT.md) | Protocolo de handoff e alinhamento de contexto para manter cooperação contínua e sem atritos entre agentes de IA. |
| [`AGENT_SYNC.md`](../AGENT_SYNC.md) | Barramento vivo de sincronização e concorrência (Antigravity ↔ ChatGPT/Codex) com locks de trabalho ativo e inbox bilateral. |
| [`log_uso_genai.csv`](../log_uso_genai.csv) | Trilha de auditoria cronológica de intervenções com ferramentas de GenAI (requisito formal de 15% da avaliação do edital). |
