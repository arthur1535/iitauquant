# Dicionário de dados

## `processed/precos_mensais.csv`

- `date`: último pregão efetivamente observado no mês.
- `month_end`: chave mensal padronizada no último dia de calendário.
- `ticker`: símbolo canônico do projeto.
- `provider_ticker`: símbolo enviado ao Yahoo.
- `close`: fechamento não ajustado.
- `adjusted_close`: fechamento ajustado por eventos corporativos e distribuições conforme o provedor.
- `volume`: volume no último pregão observado.
- `return`: variação mensal de `adjusted_close`.

Para calcular valor de mercado histórico a partir de `shares_outstanding`, use `close` **não ajustado**. `adjusted_close` é correto para retorno total, mas não deve ser multiplicado por ações reportadas sem um ajuste correspondente nas ações.

## `processed/fundamentos_sec_anuais.csv`

- `metric`: campo lógico (`assets`, `equity`, `gross_profit`, `revenue`, `shares_outstanding`).
- `taxonomy` / `tag`: origem XBRL exata do valor.
- `tag_priority`: prioridade entre tags equivalentes; zero é preferencial.
- `value` / `unit`: valor reportado e unidade original.
- `period_start` / `fiscal_period_end`: período econômico do fato.
- `duration_days`: duração do fato; receitas/lucro bruto são limitados a 270–430 dias para não misturar trimestres contidos no 10-K.
- `availability_date`: dia em que o filing foi submetido à SEC; chave contra *look-ahead*.
- `fiscal_year` / `fiscal_period`: ano e período declarados pelo emissor.
- `form`, `accession`, `frame`: rastreabilidade ao filing.

## `processed/fred_BAA10Y_mensal.csv`

- `date`: último dia de calendário do mês.
- `series_id`: identificador FRED `BAA10Y`.
- `value`: último valor não ausente observado no mês.
- `frequency`: regra de agregação aplicada.

A série mede o spread entre o rendimento de títulos corporativos Baa da Moody's
e o Treasury de 10 anos. O histórico oficial do FRED começa em 1986.

## `processed/fama_french_5_mais_momentum_mensal.csv`

- `date`: fim do mês.
- `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, `RF`, `MOM`: retornos em unidade decimal, não percentual.
