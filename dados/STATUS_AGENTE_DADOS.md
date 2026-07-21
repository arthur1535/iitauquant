# Status do Agente de Dados — 20/07/2026

## Resumo executivo

A camada de dados está implementada e os endpoints principais foram testados. A coleta de referência produziu 990 observações mensais de preços (cinco ETFs), 755 meses completos de FF5+Momentum e 503 membros atuais do S&P 500. A auditoria está em **FAIL controlado** porque o histórico oficial hoje disponível no FRED para `BAMLH0A0HYM2` começa em julho de 2023, enquanto a metodologia exige ao menos 2012 para cobrir 2015-16, 2020 e 2022-23.

O repositório também contém `dados/spread_hy_mensal.csv` desde 2005, montado por outro pipeline com um espelho público de terceiros mais o trecho atual do FRED. Ele é útil para resultado preliminar, mas não deve ser tratado como fonte final sem confirmação/licença; o próprio relatório de backtest já declara essa limitação.

## Estado por ativo

| Bloco | Estado | Evidência / pendência |
|---|---|---|
| Preços ajustados IWM/VB/IJR/SPY/BIL | Pronto | 2010-01 a 2026-06; nenhum ticker falhou; mês corrente incompleto removido |
| Preço não ajustado | Pronto | `close` preservado para valor de mercado; retornos usam `adjusted_close` |
| FF5 + Momentum | Pronto | 1963-07 a 2026-05; interseção completa, retornos decimais |
| S&P 500 atual | Pronto com ressalva | 503 símbolos; `BRK.B` → `BRK-B`; `point_in_time=false` |
| Spread HY oficial | Bloqueado para histórico longo | FRED atual: 2023-07 a 2026-06; importar exportação licenciada/TradingView |
| Fundamentos SEC | Código pronto, coleta pendente | Requer nome + e-mail real da equipe no `SEC_USER_AGENT` |
| Holdings VB | Importador pronto, arquivo pendente | Baixar “Portfolio composition file” no site oficial da Vanguard e registrar `as_of` |
| Viés de sobrevivência | Identificado | S&P 500 e holdings atuais não reconstroem membros removidos |

## Próximas entradas necessárias

1. Exportar no TradingView Premium o histórico diário completo de `FRED:BAMLH0A0HYM2` e salvar o CSV neste workspace. O importador reconhece `date`/`time` e `close`/`value`.
2. Informar no ambiente o identificador real para SEC: `$env:SEC_USER_AGENT = "Nome email@dominio.com"`.
3. Baixar o arquivo oficial de composição do VB, preservando o nome original e a data do snapshot.

Depois dessas três entradas:

```powershell
python -m iitauquant_data fred --file "CAMINHO_DO_CSV" --source-label "TradingView Premium exportado manualmente"
python -m iitauquant_data fundamentals
python -m iitauquant_data holdings --file "CAMINHO_HOLDINGS" --fund VB --as-of AAAA-MM-DD
python -m iitauquant_data audit
```

## Regras que não podem ser relaxadas

- Não imputar fundamento ausente; excluir ticker-período.
- Usar `availability_date <= data_de_decisao` nos fatos SEC.
- Usar `close` não ajustado para `shares_outstanding × preço`; usar `adjusted_close` para retornos.
- Não chamar composição atual de universo histórico.
- Não misturar observação parcial do mês corrente com meses fechados.
- Não substituir o dado por TradingView sem registrar fonte, data de exportação e permissão de uso.
