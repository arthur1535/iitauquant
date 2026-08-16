# Aplicação do LASTRO no TradingView

O arquivo `regime_credito_baa.pine` é o painel operacional do overlay de risco
implementado em `quant_fund/risk_overlay.py`. Ele lê mensalmente:

- `FRED:BAA10Y`: spread de crédito corporativo Baa contra Treasury de 10 anos;
- `FRED:NFCI`: índice amplo de condições financeiras do Chicago Fed.

Cada eixo recebe z-score móvel e histerese. Com os parâmetros congelados do
projeto, zero, um ou dois votos produzem de-risking de 0%, 25% ou 50% do sleeve
tático. O estado do mês fechado em `t-1` é aplicado aos pesos do mês `t`.

## Instalação

1. No TradingView, abra qualquer gráfico e depois o **Pine Editor**.
2. Crie um indicador vazio e substitua todo o conteúdo pelo arquivo
   `tradingview/regime_credito_baa.pine`.
3. Salve como `LASTRO — Overlay de Risco` e clique em **Add to chart**.
4. Mantenha os parâmetros padrão: janela 36, entrada 1,0, saída 0,5 e de-risking
   máximo de 50%.
5. Para automação, crie um alerta sobre o indicador e selecione
   **Any alert() function call**. A mensagem informa os pesos vigentes.

O indicador pode ficar em gráficos diários ou mensais. As duas requisições usam
apenas o fechamento mensal confirmado anterior; portanto, o painel não altera o
regime no meio do mês e não usa informação futura.

## Tabela de alocação padrão

| Eixos acesos | De-risking do sleeve tático | Factor | Small Caps | BIL / renda fixa |
|---:|---:|---:|---:|---:|
| 0 | 0% | 33,33% | 33,33% | 33,33% |
| 1 | 25% | 33,33% | 25,00% | 41,67% |
| 2 | 50% | 33,33% | 16,67% | 50,00% |

## Conferência e exportação

Para conferir as fontes, abra separadamente `FRED:BAA10Y` e `FRED:NFCI`, use o
intervalo mensal e carregue o máximo de histórico. Se desejar arquivar uma
exportação de BAA10Y, preserve o CSV original e rode:

```powershell
python -m iitauquant_data fred --series BAA10Y --file "C:\caminho\arquivo.csv" --source-label "TradingView exportado manualmente"
python -m iitauquant_data audit
```

O importador aceita datas ISO ou timestamps Unix em segundos/milissegundos e
procura automaticamente as colunas `date`/`time` e `close`/`value`. Se os nomes
forem diferentes:

```powershell
python -m iitauquant_data fred --series BAA10Y --file "C:\caminho\arquivo.csv" --date-column "time" --value-column "close" --source-label "TradingView exportado manualmente"
```

## Limites operacionais

O Pine é uma camada de visualização, decisão mensal e alertas. O TradingView não
executa o pipeline Python de fundamentos point-in-time e seu Strategy Tester não
representa de forma fiel uma carteira simultânea de vários ativos. O backtest,
os rankings e o histórico auditável continuam no repositório; ordens reais devem
passar por paper trading, conferência humana e controles de risco próprios.
