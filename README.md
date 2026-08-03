# Fundo Multi-Sleeve — backtest e visualização

Este diretório agora contém um backtest **preliminar por proxies**, uma suíte de auditoria, gráficos reprodutíveis e o indicador de regime para TradingView.

## Relatório final

O relatório acadêmico consolidado da VCapital está disponível em:

- `relatorios/Relatorio_Final_VCapital.pdf`;
- `relatorios/Relatorio_Final_VCapital.docx`.

## Executar

```powershell
python -m pip install -r requirements.txt
python scripts/backtest_auditoria.py
```

Os dados baixados ficam em `dados/`; métricas, regressões, pesos, testes e imagens ficam em `resultados/`. Os parâmetros ficam congelados e identificados por hash em `resultados/manifesto_execucao.json`.

Para uso imediato no texto, consulte `resultados/material_pre_relatorio.md`. O registro de IA está em `log_uso_genai.csv`; cada nova intervenção deve ser acrescentada no momento em que ocorrer.

## O que este teste valida

- z-score de 36 meses e histerese 1,0/0,5 do spread de crédito Baa (`BAA10Y`);
- aplicação do sinal apenas no mês seguinte;
- comparação Small Cap com e sem regime;
- pesos 33/33/33 e 33/0/67;
- métricas, drawdown, correlações e regressões FF5 + Momentum;
- verificações de datas, preços ajustados, dados ausentes e consistência retorno-peso.

## Limite do resultado

`VFMF` e o ETF small-cap escolhido são proxies. O backtest final ainda precisa substituir esses proxies pelas seleções de ações point-in-time dos Sleeves 1 e 2, incluindo custos e turnover próprios.

## Pipeline das seleções por ação

A lógica final dos rankings e pesos por ação está implementada separadamente em
`quant_fund/`; consulte `README_QUANT.md`. Ela cobre os quatro fatores do Sleeve 1,
momentum/reversão e regime do Sleeve 2, BIL, alocações entre sleeves e exportação das
carteiras mensais. Para gerar números finais, ainda é necessário completar os preços,
holdings e fundamentos point-in-time dos universos — os resultados existentes em
`resultados/` continuam corretamente identificados como preliminares por proxies.
