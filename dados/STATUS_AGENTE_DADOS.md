# Status do Agente de Dados - 02/08/2026

## Resumo executivo

A camada de dados está implementada e os endpoints principais foram testados. A
coleta de referência contém 990 observações mensais de preços (cinco ETFs), 755
meses completos de FF5+Momentum, 503 membros atuais do S&P 500 e 487 meses do
spread `BAA10Y`, de janeiro/1986 a julho/2026.

A limitação histórica do `BAMLH0A0HYM2` foi resolvida pela substituição por
`BAA10Y`, obtida diretamente do FRED. A auditoria não acusa mais histórico de
crédito insuficiente. O status agregado continua em **FAIL controlado** apenas
porque os fundamentos SEC point-in-time ainda não foram coletados. Permanecem
dois avisos: universo atual sujeito a viés de sobrevivência e ausência do
snapshot de holdings do VB.

## Estado por ativo

| Bloco | Estado | Evidência / pendência |
|---|---|---|
| Preços ajustados IWM/VB/IJR/SPY/BIL | Pronto | 990 linhas; `close` preservado e retornos por `adjusted_close` |
| FF5 + Momentum | Pronto | 755 meses completos; retornos em decimais |
| S&P 500 atual | Pronto com ressalva | 503 símbolos; `point_in_time=false` |
| Spread de crédito Baa | Pronto | FRED `BAA10Y`; 1986-01 a 2026-07; 487 meses |
| Fundamentos SEC | Código pronto, coleta pendente | Requer identificador real da equipe no `SEC_USER_AGENT` |
| Holdings VB | Importador pronto, arquivo pendente | Preservar arquivo oficial e data `as_of` |
| Backtest por proxies | Atualizado | BAA10Y; período 2018-03 a 2026-07; auditoria 12/12 |
| Backtest por ações | Bloqueado por dados | Faltam `factor_fundamentals.csv`, preços/universo point-in-time e holdings históricos |

## Próximas entradas necessárias

1. Definir o identificador real exigido pela SEC:
   `$env:SEC_USER_AGENT = "Nome email@dominio.com"`.
2. Coletar fundamentos anuais da amostra e preservar `availability_date`.
3. Obter universo/holdings históricos point-in-time ou declarar formalmente o
   viés de sobrevivência no experimento por amostra.
4. Montar os cinco arquivos de entrada do `run_quant_pipeline.py`:
   `factor_prices.csv`, `factor_fundamentals.csv`, `small_cap_prices.csv`,
   `credit_spread.csv` e `bil_prices.csv`.

## Regras que não podem ser relaxadas

- Não imputar fundamento ausente; excluir ticker-período.
- Usar `availability_date <= data_de_decisao` nos fatos SEC.
- Usar `close` não ajustado para `shares_outstanding × preço`; usar
  `adjusted_close` para retornos.
- Não chamar composição atual de universo histórico.
- Não misturar observação parcial do mês corrente com meses fechados.
- Manter o TradingView como conferência/alerta, não como fonte automatizada do
  backtest.
