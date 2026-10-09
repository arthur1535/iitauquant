# Pesquisa de ações e ETFs dos EUA para dias a semanas

O pipeline `investment_research` organiza uma triagem quantitativa de 24 ações e ETFs negociados nos EUA, em USD. O horizonte de leitura é de 5–10 pregões. Cada execução registra a configuração, os dados utilizados, as exclusões e uma comparação histórica da regra de negociação.

## Executar e reproduzir

Na raiz do repositório, com Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/run_investment_research.py --refresh --as-of 2026-10-09
```

O comando instalado `iitauquant-research` aceita os mesmos argumentos. A execução por script usa a configuração padrão [`config/swing_us.json`](../config/swing_us.json) e grava em `results/investment_research/<as-of>/`.

A pesquisa usa CSV e as dependências centrais do pacote. PyArrow continua necessário para testes e estudos legados que usam Parquet, mas não é requisito da nova coleta.

| Argumento | Uso |
|---|---|
| `--as-of YYYY-MM-DD` | Data de corte da pesquisa; sempre confira a última sessão efetivamente disponível. |
| `--config caminho.json` | Universo, filtros, custos e demais regras explícitas. |
| `--output-dir caminho` | Diretório alternativo para preservar uma execução separada. |
| `--data-dir caminho` | Cache alternativo; o padrão é `data/swing_us/`. |
| `--refresh` | Solicita nova coleta e registra sua proveniência. |
| `--offline` | Usa o cache local sem coletar dados de mercado. |

Exemplo de reprodução após a coleta:

```powershell
.\.venv\Scripts\python.exe scripts/run_investment_research.py --offline --as-of 2026-10-09 --output-dir results/investment_research/repro_2026-10-09
```

Compare os hashes dos dados e a configuração dos manifestos para saber se duas execuções utilizam as mesmas entradas. Mudar o corte, universo ou parâmetros define outra experiência. Para repetir a interpretação e os números, preserve também a versão do código e das dependências.

## Artefatos

| Arquivo | Conteúdo |
|---|---|
| `relatorio.html` | Visão de leitura do ranking, dados, risco, cenários e resultados históricos. |
| `ranking.csv` | Métricas por ativo, pontuação e elegibilidade pelas regras. |
| `exclusions.csv` | Ativos excluídos e seus motivos, inclusive falhas de coleta e dados antigos. |
| `manifest.json` | Corte, fonte, horário de coleta, parâmetros, hashes e limitações da execução. |
| `support_note.md` | Versão textual da análise e contexto metodológico. |

Os resultados pertencem ao corte indicado no manifesto. Um relatório antigo não se torna atual quando é aberto novamente. Ausência de candidatos elegíveis é um resultado possível da triagem.

## Fontes, ajustes e integridade

A coleta usa Yahoo Finance via `yfinance`, uma fonte exploratória. O cache desta pesquisa fica isolado em `data/swing_us/`; os históricos de `data/market/` e os dados mensais de `dados/` não são promovidos silenciosamente a dados atuais.

São preservados OHLC ajustados, fechamento bruto e informações de proveniência. Os ajustes corporativos precisam ser coerentes entre abertura, máxima, mínima e fechamento: combinar uma abertura bruta com um fechamento ajustado produz retornos e stops inconsistentes. A liquidez em dólares deve conservar sua interpretação econômica ao combinar preço e volume. Os valores de execução sobre preços historicamente ajustados são valores de simulação, não cotações executáveis de uma ordem atual.

A coleta remove a sessão corrente até 17h de Nova York, com margem após o fechamento regular, e respeita o corte solicitado. Dados com mais de três dias úteis de atraso ficam fora da seleção atual. Essa contagem usa dias úteis e não representa um calendário oficial de feriados das bolsas; eventos e feriados podem exigir conferência. Falhas não são substituídas por preços inventados nem por séries sintéticas.

Hashes documentam que uma entrada mudou ou permaneceu igual. Eles não certificam a exatidão econômica do provedor. Eventos corporativos, alterações posteriores dos ajustes e divergências entre fontes continuam sendo limitações.

## Sinal fixo e ranking

Todos os indicadores usam somente informações disponíveis no fechamento da barra de decisão. Na configuração padrão, um ativo precisa satisfazer simultaneamente:

1. `close > MA20 > MA50`, com médias simples de 20 e 50 pregões.
2. Retorno de 20 pregões positivo.
3. Força relativa de 20 pregões positiva frente ao SPY; o próprio SPY dispensa essa condição.
4. `close - MA20 <= 3 × ATR14`.
5. Média de 20 pregões de `raw_close × volume` de pelo menos US$ 20 milhões.
6. SPY acima da própria média de 50 pregões.
7. Pelo menos 252 barras de histórico, preços válidos e dados recentes.

O score soma percentis transversais dos componentes abaixo, com pesos fixos em `src/investment_research/engine.py`. A volatilidade anualizada é estimada pelos retornos diários dos últimos 20 pregões; os denominadores de risco são reescalados para o horizonte correspondente.

| Componente | Peso |
|---|---:|
| Retorno de 20 pregões / risco de 20 pregões | 35% |
| Retorno de 60 pregões / risco de 60 pregões | 25% |
| (Retorno de 20 pregões − retorno SPY de 20 pregões) / risco de 20 pregões | 25% |
| Distância do fechamento à máxima dos últimos 60 pregões | 15% |

Não há busca de parâmetros que maximize o histórico. A pontuação serve para ordenar o universo escolhido. Ela não é probabilidade de ganho, retorno esperado, margem de segurança de valuation ou recomendação personalizada. Resultados OOS não entram na pontuação.

Um ativo pode ter score alto e falhar no filtro de entrada. Leia pontuação e elegibilidade separadamente: `candidato` passa nos filtros técnicos; `observar` tem motivos de espera listados. Candidatos aparecem primeiro, ordenados pelo score dentro de sua categoria. Também confira volatilidade, drawdown, liquidez e concentração: várias ações e ETFs podem representar a mesma exposição econômica.

A referência de peso usa `min(10%, 0,5% / distância percentual do stop)`. Ela depende do fechamento disponível e não é uma carteira pronta. O stop deve ser recalculado no preço efetivo de entrada; gaps, custos, correlação e posições simultâneas podem exceder o orçamento de risco indicado.

## Backtest causal e comparação

A simulação segue a sequência temporal:

```text
fechamento t: indicadores e decisão
    -> abertura t+1: entrada, se houver sinal elegível
    -> stop móvel de 2 ATR e saída por prazo de até 10 pregões
    -> custos na entrada e na saída
```

O preço de decisão não é o preço de execução. O stop inicia a 2 ATR da abertura de entrada e só sobe com fechamentos conhecidos; pode disparar intradiariamente. Uma abertura abaixo do stop é preenchida na abertura. A perda da média de 20 pregões e o prazo máximo geram saída na abertura seguinte. A posição remanescente é liquidada no fechamento final com custo.

No cenário base, cada ponta custa 15 pontos-base (0,15%); no estresse, 30 pontos-base (0,30%). Os custos representam uma hipótese agregada, e não uma tabela garantida de comissão ou spread. Impostos e condições específicas de uma conta não estão modelados. A simulação por ativo usa 100% do capital enquanto comprado, sem alavancagem; caixa rende zero, e o Sharpe adota taxa livre de risco zero.

O histórico é dividido cronologicamente em 70%/30%. Indicadores da segunda parte recebem barras anteriores para aquecimento, mas a posição começa zerada: uma operação da primeira parte não é transferida ao teste. Parâmetros fixos são mantidos em ambas as partes. A avaliação inclui a estratégia, comprar e manter o ativo e o benchmark SPY sobre períodos compatíveis.

Para interpretar resultados, observe conjuntamente retorno, volatilidade, drawdown, número de operações, exposição e comportamento no cenário de custos maior. Poucas operações geram estimativas instáveis; um bom retorno agregado pode depender de um único ativo ou episódio. A curva de uma estratégia por ativo não demonstra o desempenho de uma carteira implementável com todas as posições simultâneas.

## Limitações da evidência

O universo é escolhido no presente e testado retrospectivamente. Empresas que desapareceram, mudaram de ticker ou não foram selecionadas podem estar ausentes. Há viés de sobrevivência e seleção; a divisão cronológica não remove esses vieses. Estudos anteriores do projeto já observaram parte dos mesmos anos: a segunda janela é uma avaliação histórica reservada pela regra, não um holdout cego independente.

Desempenho superior ao SPY no histórico não basta para inferir alpha. Fatores de risco, concentração temática, diferenças de exposição, custos e múltiplas experiências podem explicar a diferença. O ranking técnico também não incorpora demonstrações financeiras ou valuation. Fundamentos SEC de outras frentes não devem ser apresentados como insumos coletados desta análise.

Os números são em USD. O retorno de um investidor com patrimônio em BRL também depende do câmbio, custos de remessa e tributação, que não são calculados aqui. O horizonte de 5–10 pregões é uma convenção de pesquisa, sem garantia de liquidez ou de preenchimento nos preços simulados.

## Relação com o restante do projeto

- [`quant_fund/`](../quant_fund/README.md) implementa o fundo mensal LASTRO e possui contratos de dados próprios.
- [`src/backtest/`](ARCHITECTURE_MOMENTUM.md) e os estudos Momentum ATR preservam suas regras, caches e manifestos originais.
- O OMS e o Worker continuam dedicados a ordens simuladas. A pesquisa gera relatórios; a publicação de um ranking não envia ordens.
- Consulte o [índice de documentação](README.md), a [governança dos dados](DATA_GOVERNANCE.md) e o [histórico de verificações](../AGENT_SYNC.md).
