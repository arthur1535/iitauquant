# Aplicação do LASTRO no TradingView

O arquivo `regime_credito_baa.pine` é o painel operacional do overlay de risco
implementado em `quant_fund/risk_overlay.py`. Ele lê mensalmente:

- `FRED:BAA10Y`: spread de crédito corporativo Baa contra Treasury de 10 anos;
- `FRED:NFCI`: índice amplo de condições financeiras do Chicago Fed.

Cada eixo recebe z-score móvel e histerese. Na especificação identificada do
projeto, zero, um ou dois votos produzem de-risking de 0%, 25% ou 50% do sleeve
tático. O estado do mês fechado em `t-1` produz o sinal candidato do mês `t`.
Por padrão, esse sinal roda em modo shadow e não altera capital.

## Instalação

1. No TradingView, abra qualquer gráfico e depois o **Pine Editor**.
2. Crie um indicador vazio e substitua todo o conteúdo pelo arquivo
   `tradingview/regime_credito_baa.pine`.
3. Salve como `LASTRO — Overlay de Risco` e clique em **Add to chart**.
4. Mantenha os parâmetros padrão: janela 36, entrada 1,0, saída 0,5 e de-risking
   máximo de 50%. O input **Aprovar overlay para capital** deve permanecer
   desligado até a aprovação formal da estratégia.
5. Para automação, crie um alerta sobre o indicador e selecione
   **Any alert() function call**. A mensagem identifica o sinal candidato, o
   estado do gate e os pesos executáveis.

O indicador pode ficar em gráficos diários ou mensais. As duas requisições
ignoram o mês corrente ainda aberto. Isso evita um erro simples de calendário,
mas não torna o gráfico histórico point-in-time: BAA10Y e, sobretudo, NFCI podem
receber observações atrasadas ou revisões. O backtest oficial reconstrói o que era
conhecido em cada fechamento com vintages do ALFRED; o TradingView é monitor e
checagem da publicação corrente.

## Sinal candidato versus capital

O indicador separa duas decisões que não devem ser confundidas:

- **candidato:** z-scores, votos, regime e de-risking continuam calculados,
  coloridos e alertados para observação fora da amostra;
- **capital:** somente os pesos marcados como **PESOS EXECUTÁVEIS** podem orientar
  uma alocação. Com o gate desligado, o painel mostra **SHADOW / NÃO APROVADO**,
  de-risking executável de 0% e 33,33% em cada sleeve, qualquer que seja o sinal;
- depois da aprovação formal, ligar **Aprovar overlay para capital** muda o painel
  para **LIVE / APROVADO** e permite que o candidato governe os pesos.

O input é apenas um bloqueio operacional explícito. Ligá-lo não constitui, por si
só, aprovação de risco, evidência de backtest ou autorização para enviar ordens.

## Tabela de alocação candidata

| Eixos acesos | De-risking do sleeve tático | Factor | Small Caps | BIL / renda fixa |
|---:|---:|---:|---:|---:|
| 0 | 0% | 33,33% | 33,33% | 33,33% |
| 1 | 25% | 33,33% | 25,00% | 41,67% |
| 2 | 50% | 33,33% | 16,67% | 50,00% |

Enquanto o gate estiver desligado, as três linhas acima são apenas candidatas;
os pesos executáveis permanecem 33,33% / 33,33% / 33,33%.

## Conferência e exportação

Para conferir as fontes, abra separadamente `FRED:BAA10Y` e `FRED:NFCI`, use o
intervalo mensal e carregue o máximo de histórico. Se desejar arquivar uma
exportação de BAA10Y, preserve o CSV original e rode:

```powershell
python -m iitauquant_data fred --series BAA10Y --file "C:\caminho\arquivo.csv" --source-label "TradingView exportado manualmente"
python -m iitauquant_data audit
```

Para a checagem específica do LASTRO, exporte os dois gráficos mensais com a
janela **Todos** e rode o sanitizador. Ele descarta automaticamente qualquer
coluna de indicador alheia ao projeto, reconcilia os fechamentos com as bases do
repositório e registra hashes dos arquivos brutos:

```powershell
python scripts/auditar_tradingview.py --baa10y "C:\caminho\BAA10Y.csv" --nfci "C:\caminho\NFCI.csv"
```

Os arquivos gerados são `dados/tradingview/lastro_tradingview_mensal.csv`,
`resultados/auditoria_tradingview.json` e `resultados/auditoria_tradingview.md`.

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

Uma exportação atual do TradingView reconciliada sem divergências prova que as
duas fontes exibem hoje a mesma vintage final. Ela não prova que esses valores já
eram conhecidos em cada mês passado. Essa segunda verificação é feita por
`scripts/auditar_vintages_macro.py`.
