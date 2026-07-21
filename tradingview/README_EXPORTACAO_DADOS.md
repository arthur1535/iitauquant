# Exportação manual do spread HY no TradingView Premium

1. Abra um gráfico novo e procure o símbolo `FRED:BAMLH0A0HYM2`.
2. Selecione intervalo diário e carregue o máximo de histórico disponível.
3. Use **Export chart data** no menu do gráfico e preserve o CSV original sem editar.
4. Salve o arquivo no workspace e rode:

```powershell
python -m iitauquant_data fred --file "C:\caminho\arquivo.csv" --source-label "TradingView Premium exportado manualmente"
python -m iitauquant_data audit
```

O importador aceita datas ISO ou timestamps Unix em segundos/milissegundos e procura automaticamente as colunas `date`/`time` e `close`/`value`. Se os nomes forem diferentes:

```powershell
python -m iitauquant_data fred --file "C:\caminho\arquivo.csv" --date-column "time" --value-column "close" --source-label "TradingView Premium exportado manualmente"
```

O TradingView serve aqui para suprir o histórico que o FRED deixou de distribuir integralmente em abril de 2026. O arquivo, a data da exportação e os termos de uso aplicáveis devem ser guardados com a entrega.
