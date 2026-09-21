# LASTRO — Fundo Sistemático Multi-Sleeve & Laboratório Momentum ATR

[![Testes Python](https://img.shields.io/badge/testes%20python-139%20aprovados-brightgreen.svg)](#testes-e-validação)
[![Testes Cloudflare](https://img.shields.io/badge/testes%20worker-37%20aprovados-brightgreen.svg)](#testes-e-validação)
[![Modo Operacional](https://img.shields.io/badge/modo-paper--only-blue.svg)](#segurança-e-governança)
[![Edital Itaú Quant](https://img.shields.io/badge/entrega%20oficial-AAKR%20(16%3A9)-orange.svg)](#relatórios-oficiais)

Repositório unificado de pesquisa, modelagem econométrica, backtest orientado a eventos e execução simulada desenvolvido para o **Desafio II Itaú Quant**. O projeto combina uma estratégia fundamentalista/momentum multi-sleeve com overlay macro e um laboratório sistemático de alta capacidade baseado em Momentum ATR e Order Management System (OMS) estritamente paper-only.

---

## 1. Estrutura do Repositório

O projeto adota uma arquitetura modular com separação estrita de responsabilidades entre dados macro/mensais e cotações diárias, relatórios oficiais e evidências de pesquisa:

```text
iitauquant/
├── README.md                      # [Este arquivo] Guia mestre, arquitetura e documentação
├── AGENT_SYNC.md                  # Barramento de colaboração multi-agente (Antigravity ↔ ChatGPT)
├── log_uso_genai.csv              # Trilha de auditoria GenAI (requisito formal do edital - 15% da nota)
├── pyproject.toml                 # Configuração de build, pacotes e ferramentas de teste
├── requirements.txt               # Dependências completas Python
├── requirements-tradingview.txt   # Dependências específicas para TradingView/OMS
├── run_quant_pipeline.py          # Shim CLI para execução rápida do pipeline multi-sleeve
│
├── config/                        # Configurações declarativas JSON (universos, OMS e automação)
│   ├── automation.json            # Agendamentos de automação
│   ├── dados.json                 # Parâmetros de ingestão e normalização
│   ├── momentum_universe.json     # Universos (B3 local, Global Leaders, ETFs)
│   └── oms_simulation.json        # Limites de risco, capital inicial e símbolos autorizados
│
├── docs/                          # Central de Documentação Técnica e Governança
│   ├── README.md                  # Catálogo mestre de toda a documentação
│   ├── ACCEPTANCE_CHECKLIST.md    # 17 critérios de aceite formais auditados
│   ├── ARCHITECTURE_MOMENTUM.md   # Arquitetura do motor Momentum ATR e paper OMS
│   ├── AUDITORIA_OOS_TAREFA1.md   # Auditoria Out-Of-Sample com contrato temporal
│   ├── DATA_GOVERNANCE.md         # Governança de dados e integridade point-in-time
│   ├── OPERATIONS_RUNBOOK.md      # Runbook de operações, monitoramento e contingência
│   ├── PESQUISA_METODOS_QUANTITATIVOS.md # Métodos econométricos (DSR, Bootstrap, FF5)
│   ├── SECURITY_MODEL.md          # Modelo de segurança fail-closed e assinatura HMAC
│   ├── TRADINGVIEW_CREATOR.md     # Guia de desenvolvimento Pine v5/v6 sem repainting
│   ├── fundo/                     # Relatórios técnicos e tutoriais do Fundo LASTRO
│   │   ├── relatorio_tecnico_fundo.md
│   │   ├── tutorial_desenvolvimento_fundo.md
│   │   └── checklist_pre_relatorio_31_07.md
│   └── prompts/                   # Prompts institucionais e barramentos de colaboração
│       ├── MEGAPROMPT_ANALISTA_INVESTIMENTOS.md
│       └── PROMPT_INTEGRACAO_CHATGPT.md
│
├── quant_fund/                    # Pacote Python do Fundo Multi-Sleeve LASTRO
│   ├── README.md                  # Documentação do pacote, regras de pesos e rebalanceamento
│   ├── adapters.py                # Adaptadores de dados SEC e preços
│   ├── config.py                  # Parâmetros de sleeves e overlay
│   ├── pipeline.py                # Pipeline ponta a ponta
│   ├── portfolio.py               # Consolidação e ponderação de carteira
│   ├── risk_overlay.py            # Overlay macro BAA10Y + NFCI com histerese
│   ├── sleeve1.py                 # Sleeve 1: Fatores / Qualidade (top 50 anual)
│   ├── sleeve2.py                 # Sleeve 2: Small Cap Momentum 12-1 (mensal)
│   ├── sleeve3.py                 # Sleeve 3: Gestão de Caixa (BIL / T-Bills)
│   ├── utils.py                   # Z-score transversal e drift de pesos
│   └── validation.py              # DSR, PSR e bootstrap em blocos
│
├── src/                           # Pacote Python do Laboratório Momentum ATR e OMS
│   ├── antigravity/               # Prompts e manifestos de pesquisa autônoma
│   ├── automation/                # Agendador e orquestrador de tarefas
│   ├── backtest/                  # Motor de backtest causal, DSR, WFA e grid
│   ├── iitauquant_data/           # Pipeline de ingestão, normalização e cache
│   ├── server/                    # Servidor FastAPI do Paper OMS e webhook HMAC
│   └── strategies/                # Estratégia Momentum ATR e validação OHLCV
│
├── scripts/                       # Todos os scripts executáveis da esteira unificada
│   ├── run_quant_pipeline.py      # Execução do pipeline completo do fundo
│   ├── backtest_auditoria.py      # Backtest preliminar por proxies e vieses
│   ├── auditar_vintages_macro.py  # Fotografias ALFRED disponíveis point-in-time
│   ├── diagnostico_overlay.py     # Atribuição, sensibilidade e gate estatístico
│   ├── graficos_relatorio.py      # Geração das figuras oficiais R1..R7
│   ├── build_relatorio.py         # Compilação dos PDFs oficiais AAKR
│   ├── auditar_tradingview.py     # Reconciliação de sinais do TradingView
│   ├── analisar_trades_tv.py      # Análise de exportações de trades
│   ├── run_momentum_research.py   # Pipeline de pesquisa Momentum B3
│   ├── run_global_momentum_research.py # Pesquisa da cesta Global Leaders
│   ├── run_out_of_sample_audit.py # Split cronológico OOS e contrato temporal
│   ├── run_tradingview_live_demo.py   # Emulação de webhook TradingView -> OMS
│   └── analisar_mercado_chines.py # Estudo quantitativo de ETFs/ações da China
│
├── dados/                         # Camada de dados mensais e macro do Fundo LASTRO
│   ├── README.md                  # Documentação da camada de dados
│   ├── DICIONARIO_DADOS.md        # Dicionário de variáveis e fontes XBRL/FRED
│   ├── STATUS_AGENTE_DADOS.md     # Status de ingestão
│   └── ...                        # Datasets (preços, fatores FF, BAA10Y, NFCI)
│
├── data/                          # Camada de mercado diária em Parquet e Paper OMS
│   ├── README.md                  # Documentação dos caches de mercado
│   ├── market/*.parquet           # Cotações diárias validadas (B3, Globais, ETFs)
│   └── oms_live_demo.sqlite3      # Banco SQLite em WAL append-only para ordens paper
│
├── relatorios/                    # Entregáveis Oficiais do Edital (Anonimizados)
│   ├── AAKR.pdf                   # Relatório oficial em 5 páginas 16:9 horizontal
│   ├── AAKR_retrato.pdf           # Versão alternativa em A4 retrato
│   ├── AAKR.html                  # Versão autocontida para visualização em tela
│   └── AAKR_retrato.html          # Versão autocontida retrato
│
├── resultados/                    # Artefatos, gráficos e tabelas do Fundo LASTRO
│   ├── graficos/                  # Figuras renderizadas (R1 a R7)
│   ├── tabelas/                   # Métricas e saídas numéricas
│   └── *.json / *.csv             # Manifestos de revisão, validação e pesos
│
├── results/                       # Evidências do Laboratório Momentum ATR e OMS
│   ├── README.md                  # Histórico das evidências arquivadas
│   ├── baseline/                  # Métricas de referência
│   ├── global_research/           # Resultados dos Global Leaders (NVDA, SPY, etc.)
│   ├── china_research/            # Resultados do mercado chinês
│   ├── grid_search/               # Avaliação e checkpoints de grid search
│   ├── oos_audit/                 # Manifestos e métricas da auditoria OOS
│   └── test_reports/              # Relatórios XML de testes
│
├── tradingview/                   # Scripts Pine v5/v6 e integrações TradingView
│   ├── README.md                  # Guia geral do módulo TradingView
│   ├── README_MOMENTUM_ATR.md     # Especificação técnica do Momentum ATR
│   ├── README_EXPORTACAO_DADOS.md # Protocolo de exportação e sanitização
│   ├── alert_templates.json       # Templates de alerta JSON para webhook
│   └── *.pine                     # Indicadores de regime, dashboard e estratégias
│
├── infra/                         # Infraestrutura e borda
│   └── cloudflare/                # Worker Cloudflare de terminação de webhook com HMAC
│
└── tests/                         # Suíte de testes automatizados (139 testes verdes)
    ├── test_automation_runner.py
    ├── test_data_pipeline.py
    ├── test_momentum_backtest.py
    ├── test_oos_validation.py
    ├── test_paper_ledger.py
    ├── test_paper_replay.py
    ├── test_quant_fund.py
    ├── test_research_automation.py
    ├── test_risk_overlay.py
    ├── test_server_oms.py
    └── test_validation.py
```

---

## 2. As Duas Frentes do Projeto

### A. Fundo Sistemático Multi-Sleeve (LASTRO)
- **Sleeve 1 (Fatores / Qualidade)**: Seleção anual em junho das 50 maiores pontuações combinadas de valor, tamanho, rentabilidade e investimento, baseada em demonstrações financeiras SEC XBRL point-in-time.
- **Sleeve 2 (Small Cap Momentum)**: Rebalanceamento mensal no top 5% do ranking composto por Momentum 12-1 defasado e reversão de curto prazo.
- **Sleeve 3 (Caixa Defensivo)**: Alocação em títulos do Tesouro Americano de curtíssimo prazo (`BIL`).
- **Overlay de Risco Dual-Axis**: Monitoramento do spread de crédito corporativo (`BAA10Y`) e índice de condições financeiras (`NFCI`) via z-score móvel de 36 meses com histerese (entrada 1,0 / saída 0,5) e de-risking graduado (até 50% de migração para BIL).
- **Entregável**: Relatório institucional anônimo **`relatorios/AAKR.pdf`** (5 páginas, formato 16:9 exigido pelo edital).

### B. Laboratório Momentum ATR & Paper OMS
- **Estratégia Momentum ATR**: Trend-following sistemático em barras diárias com gatilho de Momentum relativo, filtro de volatilidade e trailing stop adaptativo calculado via ATR (`stop = close - multiplier * ATR`).
- **Garantias Anti-Look-Ahead**: Sinal computado em `close[t]` executado estritamente em `open[t+1]`. Tratamento realista de gaps abaixo do stop com preenchimento no preço de abertura e comissão de 15 bps por ponta.
- **Auditoria Out-Of-Sample (OOS)**: Split cronológico 70/30 (In-Sample até 2022-12-31 e Out-Of-Sample a partir de 2023-01-01), Walk-Forward com purga e embargo, cálculo de Deflated Sharpe Ratio (DSR) e testes de estresse em múltiplos ativos.
- **Paper OMS & Borda**: Servidor FastAPI local com autenticação HMAC SHA-256 sobre bytes brutos, prevenção de replay por timestamp/nonce, base SQLite append-only em WAL mode e Worker Cloudflare na borda. Modo estritamente restrito a simulação (`mode = "paper"`).

---

## 3. Como Executar

### Pré-requisitos
Ambiente Python 3.11+ (recomendado 3.12). Recomenda-se utilizar ambiente virtual `.venv`:

```bash
# Criar e ativar ambiente virtual (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

### Reproduzir o Relatório Oficial (LASTRO AAKR)
Para reconstruir os dados, auditar vintages, computar o diagnóstico, gerar os gráficos e compilar o PDF oficial:

```bash
# 1. Backtest preliminar por proxies e auditoria de vieses
python scripts/backtest_auditoria.py

# 2. Auditoria de vintages point-in-time no ALFRED (FRED vintage)
python scripts/auditar_vintages_macro.py

# 3. Diagnóstico do overlay, testes de sensibilidade e gate estatístico
python scripts/diagnostico_overlay.py

# 4. Renderização das figuras oficiais R1 a R7
python scripts/graficos_relatorio.py

# 5. Compilação dos relatórios finais AAKR.pdf e AAKR_retrato.pdf
python scripts/build_relatorio.py
```

Os relatórios prontos são gerados em [`relatorios/AAKR.pdf`](relatorios/AAKR.pdf).

### Executar o Pipeline Multi-Sleeve em CSV
Para rodar a esteira quantitativa com datasets locais:

```bash
python scripts/run_quant_pipeline.py --input-dir dados --output-dir resultados/quant
```

### Executar a Pesquisa Momentum ATR e Auditoria OOS
Para rodar a esteira de pesquisa do motor Momentum:

```bash
# Pesquisa em ativos globais de alta liquidez (NVDA, SPY, AAPL, etc.)
python scripts/run_global_momentum_research.py

# Estudo quantitativo de ETFs e ações chinesas
python scripts/analisar_mercado_chines.py

# Auditoria formal Out-Of-Sample com contrato temporal (dry-run SPY)
python scripts/run_out_of_sample_audit.py --symbol SPY --dry-run
```

### Iniciar o Servidor Paper OMS
Para iniciar o serviço de ordens simuladas:

```bash
# Copiar configuração de ambiente (paper-only)
cp .env.example .env

# Iniciar servidor local com Uvicorn
python -m uvicorn src.server.app:app --host 127.0.0.1 --port 8000
```

---

## 4. Testes e Validação

A integridade de todo o ecossistema é garantida por testes automatizados executados de forma independente:

### Suíte Python (139 testes)
```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```
*Cobertura: backtest sem look-ahead, fill em gaps, cálculos DSR/PSR, adapters SEC, carteira multi-sleeve, overlay de risco, HMAC do servidor OMS, janelas de replay e validação cronológica OOS.*

### Suíte Cloudflare Worker (37 testes)
```bash
node --test infra/cloudflare/test/worker.test.mjs
```
*Cobertura: allowlist de IPs do TradingView, integridade do HMAC SHA-256 e validação do envelope de requisição.*

---

## 5. Governança e Transparência

- **Uso de IA Generativa**: Todas as sessões, prompts, revisões e commits de agentes de IA são registrados no arquivo [`log_uso_genai.csv`](log_uso_genai.csv), cumprindo integralmente a exigência do edital (15% da avaliação).
- **Coordenação Concorrente**: Convivência ordenada entre agentes de IA registrada em [`AGENT_SYNC.md`](AGENT_SYNC.md).
- **Checklist de Aceite**: 17 critérios de aceite formalmente comprovados em [`docs/ACCEPTANCE_CHECKLIST.md`](docs/ACCEPTANCE_CHECKLIST.md).
- **Modo Paper-Only**: Impossibilidade técnica de envio de ordens reais a corretoras; qualquer tentativa de alterar a configuração do servidor para outro modo resulta em falha imediata (*fail-closed*).
