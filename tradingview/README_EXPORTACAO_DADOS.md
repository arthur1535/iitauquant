# Conferência do spread Baa no TradingView

1. Abra um gráfico novo e procure o símbolo `FRED:BAA10Y`.
2. Selecione intervalo diário e carregue o máximo de histórico disponível.
3. Para auditoria visual, adicione `regime_credito_baa.pine` em um painel mensal.
4. Se desejar arquivar uma exportação, preserve o CSV original e rode:

```powershell
python -m iitauquant_data fred --series BAA10Y --file "C:\caminho\arquivo.csv" --source-label "TradingView exportado manualmente"
python -m iitauquant_data audit
```

O importador aceita datas ISO ou timestamps Unix em segundos/milissegundos e procura automaticamente as colunas `date`/`time` e `close`/`value`. Se os nomes forem diferentes:

```powershell
python -m iitauquant_data fred --series BAA10Y --file "C:\caminho\arquivo.csv" --date-column "time" --value-column "close" --source-label "TradingView exportado manualmente"
```

O TradingView é uma camada de conferência e alertas; a fonte automatizada do
backtest continua sendo o FRED. O arquivo, a data da exportação e os termos de uso
aplicáveis devem ser guardados com a entrega.
