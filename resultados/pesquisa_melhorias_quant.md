# Pesquisa de melhorias quantitativas - LASTRO

Data da revisão: 2026-08-16.

## Decisão

Não acrescentar mais um fator ou modelo de machine learning antes da entrega. Com
101 observações mensais, isso aumentaria os graus de liberdade sem resolver as duas
fragilidades centrais: dados macro revisados e avaliação de muitas especificações na
mesma amostra.

A revisão prioriza quatro controles:

1. reconstrução point-in-time de BAA10Y e NFCI com as vintages do ALFRED;
2. uma única implementação do overlay no pipeline, no TradingView e no relatório;
3. teste de falsificação por deslocamentos circulares do sinal, que preserva sua
   frequência e persistência e pergunta se o timing verdadeiro protegeu mais que os
   timings placebo;
4. Probabilistic/Deflated Sharpe Ratio e bootstrap em blocos para separar evidência de
   alpha de uma escolha favorecida por múltiplos testes e por dependência temporal.

O critério de promoção passa a ser explícito: o overlay só pode ser descrito como
fonte de alpha se superar um gate estatístico de 95%. Caso contrário, permanece como
controle de risco, e seu valor é julgado por custo da proteção e desempenho na cauda.

## Por que isso muda o projeto

O TradingView e o FRED exibem hoje a melhor estimativa disponível de todo o passado.
Isso não é o mesmo que a informação conhecida em cada fechamento histórico. O Chicago
Fed informa que o histórico do NFCI pode mudar com novos dados, revisões e reestimação
dos pesos. O ALFRED registra quando cada valor era conhecido. Usar a diagonal dessas
vintages remove um look-ahead residual que uma simples defasagem de um mês não elimina.

O grid de 36 configurações continua útil como sensibilidade, mas passa a ser chamado de
exploratório. Um hash identifica a configuração; ele não prova, sozinho, que houve
pré-registro antes de observar os resultados. O DSR penaliza explicitamente o número de
tentativas, a assimetria e a curtose dos retornos.

## Fontes primárias

- Federal Reserve Bank of St. Louis, **Real-Time Periods**:
  https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- Federal Reserve Bank of Chicago, **National Financial Conditions Index - Current
  Data and Revisions**:
  https://www.chicagofed.org/research/data/nfci/current-data
- Bailey e Lopez de Prado, **The Deflated Sharpe Ratio: Correcting for Selection Bias,
  Backtest Overfitting and Non-Normality**:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey et al., **The Probability of Backtest Overfitting**:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Politis e Romano, **The Stationary Bootstrap**:
  https://statistics.stanford.edu/technical-reports/stationary-bootstrap
- Frazzini, Israel e Moskowitz, **Trading Costs of Asset Pricing Anomalies**:
  https://pages.stern.nyu.edu/~afrazzin/pdf/Trading%20Cost%20of%20Asset%20Pricing%20Anomalies%20-%20Frazzini%2C%20Israel%20and%20Moskowitz.pdf

## Limite que permanece

VFMF e VB ainda são proxies. A validação definitiva dos rankings por ação exige
fundamentos com data real de disponibilidade, membros históricos do universo,
delistings, custos por ativo e capacidade. A revisão acima melhora a validade do
overlay, mas não transforma o backtest proxy em teste do stock-picking prometido.
