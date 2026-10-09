# IITAU Quant — pesquisa quantitativa de investimentos

Pesquisa reproduzível de ações e ETFs negociados nos EUA, em USD, para operações de dias a semanas. O pipeline compara tendência, força relativa, liquidez e risco; entrega um ranking com regras explícitas, cenários de custos e evidências de backtest. O fundo LASTRO, os estudos anteriores e o OMS simulado continuam documentados neste repositório.

## Começar

Python 3.11+; recomendado 3.12. No PowerShell, na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/run_investment_research.py --refresh --as-of 2026-10-09
```

Abra `results/investment_research/2026-10-09/relatorio.html`. A mesma pasta contém `ranking.csv`, `exclusions.csv`, `manifest.json` e `support_note.md`. Depois da instalação, `iitauquant-research` também executa a CLI.

Para repetir a análise usando o cache local:

```powershell
.\.venv\Scripts\python.exe scripts/run_investment_research.py --offline --as-of 2026-10-09
```

A data é explícita: troque `--as-of` para a data desejada e atualize a coleta. Sessões ainda abertas são removidas; séries antigas ou sem evidência suficiente são excluídas. O ranking é um filtro quantitativo de pesquisa, não uma probabilidade de lucro. Confira a data dos preços, as exclusões e o manifesto antes de interpretar os resultados.

## Navegação

| Procurando | Caminho |
|---|---|
| Regras, dados, custos e leitura do ranking | [Guia da pesquisa de curto prazo](docs/INVESTMENT_RESEARCH.md) |
| Universo e parâmetros da pesquisa | [config/swing_us.json](config/swing_us.json) |
| Documentação técnica completa | [Índice de documentação](docs/README.md) |
| Fundo e estudos anteriores | [Pesquisa e entregas anteriores](#pesquisa-e-entregas-anteriores) |
| Proveniência mensal e macro | [Camada de dados LASTRO](dados/README.md) |
| Operação do servidor simulado | [Runbook](docs/OPERATIONS_RUNBOOK.md) |
| Histórico de colaboração e verificações | [AGENT_SYNC.md](AGENT_SYNC.md) |

## Organização

```text
config/swing_us.json             Universo dos EUA e parâmetros fixos
src/investment_research/         Coleta, filtros, métricas, backtest e relatório
scripts/run_investment_research.py  Entrada da pesquisa de curto prazo
data/swing_us/                  Cache isolado e proveniência da nova pesquisa
results/investment_research/     Relatórios e tabelas separados por data

quant_fund/                     Fundo LASTRO: fatores, small caps, caixa e overlay
dados/                          Dados mensais, SEC, FRED, fatores e vintages
resultados/                     Tabelas e figuras do fundo
src/backtest/ + src/strategies/  Laboratório Momentum ATR
src/iitauquant_data/             CLI de dados mensais auditáveis
src/automation/ + src/server/   Automação local e OMS simulado
tradingview/ + infra/cloudflare/ Pine Script, webhook e Worker
relatorios/                     Relatórios institucionais e estudos anteriores
tests/                          Verificações Python
```

A nova pesquisa usa um cache próprio. Os arquivos de `data/market/` e os resultados antigos mantêm seus cortes e limitações originais; executar um script antigo não atualiza automaticamente o mercado nem valida sua proveniência.

## Método de curto prazo

O universo reúne 24 ações e ETFs dos EUA. A triagem exige fechamento acima da média de 20 pregões e esta acima da média de 50, retorno positivo em 20 pregões, força relativa positiva frente ao SPY (dispensada para o próprio SPY), extensão máxima de 3 ATR e liquidez média de 20 pregões de pelo menos US$ 20 milhões. O SPY também precisa estar acima da média de 50 pregões. O score combina momentum de 20/60 pregões ajustado ao risco, força relativa e drawdown com pesos fixos documentados no código.

O backtest compra na abertura seguinte ao sinal, usa stop móvel de 2 ATR e prazo máximo de 10 pregões. Há divisão cronológica 70/30, custos de 15 pontos-base por ponta, estresse de 30 pontos-base e comparação com comprar e manter e SPY. Os indicadores do teste podem usar o histórico anterior para aquecimento; posições e sinais anteriores não são herdados.

A seleção do universo é atual e retrospectiva, sujeita a viés de sobrevivência e seleção. A avaliação reservada é uma comparação histórica; não é um holdout cego nem prova de alpha. Veja [definições e limitações](docs/INVESTMENT_RESEARCH.md).

## Testes e empacotamento

A suíte inclui backtests causais, divisão temporal, adaptadores SEC, regras do fundo, HMAC/replay e o servidor paper. Para instalar suas dependências adicionais e executar:

```powershell
.\.venv\Scripts\python.exe -m pip install "fastapi>=0.115" "httpx>=0.27" "pyarrow>=17.0" "statsmodels>=0.14" "matplotlib>=3.9"
.\.venv\Scripts\python.exe -m pytest tests -q
node --test infra/cloudflare/test/worker.test.mjs
.\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation -w tmp/wheels .
```

O workflow [Tests and packaging](.github/workflows/tests.yml) executa Python 3.11/3.12 e Node no Windows, verifica o conteúdo do wheel e importa os pacotes fora do checkout. `vectorbt` é opcional; a CI usa o motor causal do projeto. O pacote inclui tanto `src/` quanto `quant_fund/`.

## Pesquisa e entregas anteriores

O projeto nasceu no **Desafio II Itaú Quant** e preserva duas frentes históricas:

- **Fundo LASTRO:** fatores/qualidade, small caps com momentum 12–1 e caixa em BIL; overlay de crédito BAA10Y e condições financeiras NFCI. Regras e contratos CSV em [quant_fund/README.md](quant_fund/README.md), [relatório técnico](docs/fundo/relatorio_tecnico_fundo.md) e [tutorial](docs/fundo/tutorial_desenvolvimento_fundo.md).
- **Laboratório Momentum ATR e OMS:** sinal no fechamento e execução na abertura seguinte, trailing stop ATR, estudos de parâmetros, walk-forward e ordens simuladas. Consulte [arquitetura](docs/ARCHITECTURE_MOMENTUM.md), [auditoria temporal](docs/AUDITORIA_OOS_TAREFA1.md), [métodos](docs/PESQUISA_METODOS_QUANTITATIVOS.md) e [histórico de resultados](results/README.md).

O relatório institucional está em [relatorios/AAKR.pdf](relatorios/AAKR.pdf); a versão alternativa está em [relatorios/AAKR_retrato.pdf](relatorios/AAKR_retrato.pdf). Para reconstruir a entrega, com os dados exigidos disponíveis e as dependências completas de `requirements.txt` instaladas:

```powershell
python scripts/backtest_auditoria.py
python scripts/auditar_vintages_macro.py
python scripts/diagnostico_overlay.py
python scripts/graficos_relatorio.py
python scripts/build_relatorio.py
```

Outras entradas históricas:

```powershell
python scripts/run_quant_pipeline.py --input-dir dados --output-dir resultados/quant
python scripts/run_global_momentum_research.py
python scripts/analisar_mercado_chines.py
python scripts/run_out_of_sample_audit.py --symbols SPY --dry-run
```

O último comando gera um contrato de planejamento; métricas não são calculadas em `--dry-run`. Estudos globais antigos leem os caches locais. A coleta SEC exige identificação verdadeira em `SEC_USER_AGENT` e o fundo por ações depende de fundamentos e universo adequados; veja [status dos dados](dados/STATUS_AGENTE_DADOS.md).

Para o servidor simulado, instale `.[tradingview]`, configure `.env` a partir de `.env.example` e execute:

```powershell
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

O OMS permanece em `mode="paper"`, com assinatura HMAC e registro em SQLite. Detalhes em [segurança](docs/SECURITY_MODEL.md), [operações](docs/OPERATIONS_RUNBOOK.md) e [TradingView](tradingview/README.md).

## Governança

Os critérios do projeto estão em [ACCEPTANCE_CHECKLIST.md](docs/ACCEPTANCE_CHECKLIST.md). O [log de uso de IA](log_uso_genai.csv) e o [barramento de colaboração](AGENT_SYNC.md) preservam a trilha das intervenções. Dados ausentes não devem ser inventados; resultados sintéticos precisam estar identificados. Relatórios históricos representam as informações e a metodologia da data de geração.
