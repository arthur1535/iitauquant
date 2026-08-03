# Material pronto para o pré-relatório

## Texto curto — backtest e risco

No teste preliminar com ETFs, o VB foi o proxy small-cap mais sensível ao crédito: nas crises pré-definidas, sua correlação entre retorno relativo ao SPY e variação do spread Baa foi -0.52, contra -0.41 no IWM e -0.34 no IJR. O sinal usa z-score de 36 meses, entra em estresse acima de 1,0 e sai abaixo de 0,5; o estado observado no fim do mês só altera os pesos do mês seguinte.

O resultado foi adverso e informativo. No período de 2018-03 a 2026-07, o VB sempre ligado apresentou CAGR de 10.3%, Sharpe de 0.46 e drawdown máximo de -30.1%. Com o filtro de regime e 10 bps por giro, apresentou 7.6%, 0.36 e -24.4%. Portanto, o filtro binário, com sinal mensal defasado, não protegeu a proxy nesta amostra e não deve ser vendido como fonte comprovada de valor.

O fundo proxy obteve CAGR de 8.0%, volatilidade de 11.5%, Sharpe de 0.51 e drawdown de -13.7%, contra 10.7%, 11.0%, 0.76 e -16.1% do benchmark 2/3 SPY + 1/3 BIL. A correlação de 0.96 entre VFMF e VB também não sustenta, por proxies, a hipótese de dois motores pouco correlacionados. A próxima validação decisiva é substituir os ETFs pelas seleções point-in-time dos Sleeves 1 e 2.

## Tabela enxuta sugerida

| Série | CAGR | Vol. | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| VB sempre ligado | 10.3% | 20.7% | 0.46 | -30.1% |
| VB com regime, líquido | 7.6% | 17.5% | 0.36 | -24.4% |
| Fundo proxy, líquido | 8.0% | 11.5% | 0.51 | -13.7% |
| Benchmark | 10.7% | 11.0% | 0.76 | -16.1% |

## Layout visual sugerido

- Página do Sleeve 2: use `02_regime_credito.png` acima e `01_curvas_capital.png` abaixo; destaque em uma caixa: “o filtro não agregou valor no teste proxy”.
- Página do fundo: use `04_drawdown.png` à esquerda, a tabela enxuta à direita e `03_matriz_correlacao.png` menor no rodapé.
- Rodapé metodológico: “Preços ajustados; sinal defasado em um mês; custos de 10 bps por giro do overlay; resultados por proxies, não stock-picking final.”

## TradingView Premium

1. Abra um layout com dois painéis: benchmark/ativos no painel superior e o indicador `regime_credito_baa.pine` no inferior.
2. Cole o script no Pine Editor, salve e adicione ao gráfico. Use gráfico mensal para auditoria visual.
3. Crie dois alertas separados, “ENTRADA EM ESTRESSE” e “VOLTA AO NORMAL”, ambos **Once Per Bar Close**. O alerta confirmado no fechamento do mês define os pesos do mês seguinte.
4. Mantenha os inputs de produção em 36 meses, entrada 1,0 e saída 0,5. Qualquer alteração deve gerar uma nova versão do manifesto antes de olhar o resultado.
