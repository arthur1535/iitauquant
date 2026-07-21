# Backtest preliminar e auditoria metodológica

Gerado em 2026-07-21 20:59 UTC · configuração `a870cbd4d3f3`.

## Escopo e veredito

Este resultado valida o **overlay de regime e a mecânica de consolidação** usando ETFs líquidos e preços ajustados. Ele ainda não valida o stock-picking point-in-time: `VFMF` representa provisoriamente o Sleeve 1 e `VB` representa provisoriamente o Sleeve 2. Logo, os números são evidência preliminar, não o backtest final das duas seleções de ações.

Auditoria automatizada: **12/12 testes aprovados**. Falhas: nenhuma.

**Resultado principal:** no período comum, o overlay de regime **não agregou valor: reduziu o Sharpe e/ou não melhorou o drawdown**. A versão sempre ligada teve CAGR de 10.81%, Sharpe de 0.48 e Max Drawdown de -30.06%; com regime e custo, os valores foram 6.69%, 0.32 e -31.79%. Isso é evidência contra a regra atual nesta implementação proxy — não uma falha do motor de backtest.

## Decisão do proxy small-cap

O proxy escolhido foi **VB**, pela correlação mais negativa entre variação mensal do spread HY e retorno relativo ao SPY nas crises pré-definidas. A decisão usa uma referência externa ao payoff do backtest.

| ticker   |   correlacao_todos_meses |   correlacao_crises |   n_meses_crise | selecionado   |
|:---------|-------------------------:|--------------------:|----------------:|:--------------|
| IWM      |                   -0.366 |              -0.496 |              65 | False         |
| VB       |                   -0.465 |              -0.635 |              65 | True          |
| IJR      |                   -0.311 |              -0.432 |              65 | False         |

## Métricas

Sharpe calculado sobre o excesso em relação ao BIL. Séries “líquidas” descontam 10 bps por unidade de giro do overlay; não incluem o giro do stock-picking ainda inexistente.

|                                | inicio   | fim     |   meses | CAGR   | volatilidade_anual   | Sharpe_excesso_BIL   | max_drawdown   | retorno_acumulado   |
|:-------------------------------|:---------|:--------|--------:|:-------|:---------------------|:---------------------|:---------------|:--------------------|
| factor_proxy_VFMF              | 2018-03  | 2026-06 |     100 | 12.54% | 18.74%               | 0.59                 | -30.35%        | 167.70%             |
| smallcap_VB_sempre_ligada      | 2018-03  | 2026-06 |     100 | 10.81% | 20.74%               | 0.48                 | -30.06%        | 135.23%             |
| smallcap_VB_com_regime_bruto   | 2018-03  | 2026-06 |     100 | 6.74%  | 17.22%               | 0.32                 | -31.65%        | 72.26%              |
| smallcap_VB_com_regime_liquido | 2018-03  | 2026-06 |     100 | 6.69%  | 17.21%               | 0.32                 | -31.79%        | 71.58%              |
| renda_fixa_BIL                 | 2018-03  | 2026-06 |     100 | 2.54%  | 0.57%                | n/a                  | -0.16%         | 23.24%              |
| fundo_proxy_bruto              | 2018-03  | 2026-06 |     100 | 7.67%  | 11.41%               | 0.49                 | -16.33%        | 85.05%              |
| fundo_proxy_liquido            | 2018-03  | 2026-06 |     100 | 7.65%  | 11.41%               | 0.48                 | -16.38%        | 84.81%              |
| benchmark_2_3_SPY_1_3_BIL      | 2018-03  | 2026-06 |     100 | 10.83% | 11.01%               | 0.76                 | -16.13%        | 135.51%             |
| SPY                            | 2018-03  | 2026-06 |     100 | 14.68% | 16.52%               | 0.76                 | -23.93%        | 213.13%             |

## Diversificação

Correlação mensal Factor proxy × Small Cap: **0.96**. A matriz completa está em `resultados/tabelas/correlacao_sleeves.csv`.

## Regressões FF5 + Momentum

OLS mensal com erros HAC/Newey-West (3 defasagens). Coeficientes e p-valores completos estão em `resultados/tabelas/regressoes_ff5_mom.csv`. A interpretação deve considerar que proxies de ETF não reproduzem os rankings de ações prometidos.

## Auditoria de riscos metodológicos

| Risco | Veredito | Evidência / ação |
|---|---|---|
| Look-ahead do regime | Mitigado | O estado observado no fechamento de t só é aplicado ao retorno de t+1; teste automatizado `sinal_defasado_1_mes`. |
| Viés de sobrevivência | Não resolvido no modelo final | ETFs evitam reconstrução de constituintes neste teste do overlay, mas a futura seleção com holdings atuais terá viés; exige constituintes históricos point-in-time. |
| Alinhamento de datas | Testado | Todas as séries viram `PeriodIndex` mensal, usam interseção de datas e excluem o mês corrente incompleto. |
| Preço não ajustado | Mitigado | Retornos usam `Adj Close`; divergência contra `Close` foi salva como evidência. |
| Parâmetros pós-backtest | Mitigado no pipeline | Limiar 1,0/0,5, janela 36 e crises estão congelados em configuração imutável e hash; não há busca de hiperparâmetro. |
| Dados ausentes | Mitigado | Nenhuma imputação de retornos; consolidação usa apenas a interseção completa. No stock-picking final, empresa incompleta deve ser excluída. |
| Retornos × pesos | Testado | Pesos não negativos, soma unitária e igualdade exata BIL/Small Cap em cada estado. |
| Custos | Parcial | Overlay desconta 10 bps por giro; custos e turnover do ranking mensal precisam ser incluídos no backtest final. |
| Fonte do spread | Limitação material | Histórico longo vem de espelho público e trecho recente do FRED; arquivar checksum e, antes da entrega final, substituir/confirmar com exportação oficial autenticada. |
| Proxy vs. estratégia | Limitação material | Este pipeline não testa momentum+reversão por ação nem os quatro fatores fundamentalistas point-in-time. |

## Proveniência

- Preços: Yahoo Finance, campo `Adj Close`, baixados no momento da execução.
- Spread histórico: https://huggingface.co/datasets/Sashank-810/crisisnet-dataset/resolve/main/Module_1/credit_spreads/BAMLH0A0HYM2.csv
- Spread atual: https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2
- Fatores: Kenneth R. French Data Library, FF5 e Momentum mensais.

## Arquivos visuais

- `01_curvas_capital.png`: fundo, benchmark e Small Cap com/sem regime.
- `02_regime_credito.png`: z-score, histerese e meses efetivamente defensivos.
- `03_matriz_correlacao.png`: teste visual da tese de diversificação.
- `04_drawdown.png`: profundidade e duração das perdas.
