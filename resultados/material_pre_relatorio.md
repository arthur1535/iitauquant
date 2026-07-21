# Material pronto para o pré-relatório

## Texto curto — backtest e risco

No teste preliminar com ETFs, o VB foi o proxy small-cap mais sensível ao crédito: nas crises pré-definidas, sua correlação entre retorno relativo ao SPY e variação do spread HY foi -0.64, contra -0.50 no IWM e -0.43 no IJR. O sinal usa z-score de 36 meses, entra em estresse acima de 1,0 e sai abaixo de 0,5; o estado observado no fim do mês só altera os pesos do mês seguinte.

O resultado foi adverso e informativo. De março de 2018 a junho de 2026, o VB sempre ligado apresentou CAGR de 10.8%, Sharpe de 0.48 e drawdown máximo de -30.1%. Com o filtro de regime e 10 bps por giro, apresentou 6.7%, 0.32 e -31.8%. Portanto, o filtro binário, com sinal mensal defasado, não protegeu a proxy nesta amostra e não deve ser vendido como fonte comprovada de valor.

O fundo proxy obteve CAGR de 7.6%, volatilidade de 11.4%, Sharpe de 0.48 e drawdown de -16.4%, contra 10.8%, 11.0%, 0.76 e -16.1% do benchmark 2/3 SPY + 1/3 BIL. A correlação de 0.96 entre VFMF e VB também não sustenta, por proxies, a hipótese de dois motores pouco correlacionados. A próxima validação decisiva é substituir os ETFs pelas seleções point-in-time dos Sleeves 1 e 2.

## Tabela enxuta sugerida

| Série | CAGR | Vol. | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| VB sempre ligado | 10.8% | 20.7% | 0.48 | -30.1% |
| VB com regime, líquido | 6.7% | 17.2% | 0.32 | -31.8% |
| Fundo proxy, líquido | 7.6% | 11.4% | 0.48 | -16.4% |
| Benchmark | 10.8% | 11.0% | 0.76 | -16.1% |

## Layout visual sugerido

- Página do Sleeve 2: use `02_regime_credito.png` acima e `01_curvas_capital.png` abaixo; destaque em uma caixa: “o filtro não agregou valor no teste proxy”.
- Página do fundo: use `04_drawdown.png` à esquerda, a tabela enxuta à direita e `03_matriz_correlacao.png` menor no rodapé.
- Rodapé metodológico: “Preços ajustados; sinal defasado em um mês; custos de 10 bps por giro do overlay; resultados por proxies, não stock-picking final.”

## TradingView Premium

1. Abra um layout com dois painéis: benchmark/ativos no painel superior e o indicador `regime_credito_hy.pine` no inferior.
2. Cole o script no Pine Editor, salve e adicione ao gráfico. Use gráfico mensal para auditoria visual.
3. Crie dois alertas separados, “ENTRADA EM ESTRESSE” e “VOLTA AO NORMAL”, ambos **Once Per Bar Close**. O alerta confirmado no fechamento do mês define os pesos do mês seguinte.
4. Mantenha os inputs de produção em 36 meses, entrada 1,0 e saída 0,5. Qualquer alteração deve gerar uma nova versão do manifesto antes de olhar o resultado.
