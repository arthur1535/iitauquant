# Agente Quantitativo — fundo multi-sleeve

Este pacote implementa a lógica financeira descrita em `relatorio_tecnico_fundo.md` e
`tutorial_desenvolvimento_fundo.md`. A entrega é point-in-time: um sinal calculado no
fechamento de um mês só vira posição no mês seguinte.

## Regras implementadas

- **Sleeve 1:** tamanho, valor, rentabilidade e investimento; winsorização 1%/99%;
  z-score transversal; média dos quatro fatores; top 50; peso igual na formação;
  compra e manutenção com pesos derivados pelos preços até o rebalanceamento anual
  em junho; balanço disponível na data informada ou, na ausência dela, três meses
  depois do fechamento fiscal.
- **Sleeve 2:** momentum 12–1 (`P(t-1) / P(t-12) - 1`); reversão do último mês;
  z-scores transversais; composto 50/50; top 5%; peso igual; rebalanceamento mensal.
  O overlay combina o spread Baa–Treasury (`BAA10Y`) e o índice amplo de condições
  financeiras (`NFCI`), ambos com z-score móvel e histerese 1,0/0,5. Cada eixo aceso
  migra 25% do Sleeve 2 para BIL, até o limite de 50%.
- **Sleeve 3:** retorno mensal do preço ajustado do BIL e peso integral no instrumento.
- **Fundo:** a decisão observada no fechamento de `t` só altera a posição de `t+1`.
  Com 0/1/2 eixos acesos, os pesos fator/small caps/BIL são, respectivamente,
  33,33/33,33/33,33%, 33,33/25,00/41,67% e 33,33/16,67/50,00%.

O argumento `financial_conditions` ativa o overlay de dois eixos na API. Se ele não
for informado, `run_pipeline` e `build_sleeve2` preservam o comportamento credit-only
anterior: BAA10Y binário e migração integral do Sleeve 2 para BIL.

Esse acionamento gera o **cenário de pesquisa**, não uma autorização de capital. O
manifesto vigente registra `governanca.aprovado=false`; no TradingView, a flag de
capital inicia desligada e mantém 1/3 por sleeve enquanto o overlay permanece shadow.

Os parâmetros são centralizados em `quant_fund/config.py`. Junho é uma convenção
operacional parametrizável; a documentação original fixa a frequência anual, mas não
o mês. O filtro de idade máxima do balanço é 18 meses para impedir o uso indefinido de
contas antigas e também pode ser desativado.

## Contrato dos dados

Crie a pasta `dados/` com os arquivos abaixo. Datas ficam na primeira coluna e preços
devem ser **ajustados por dividendos e desdobramentos**.

| Arquivo | Formato |
|---|---|
| `factor_prices.csv` | wide ajustado, ou long da camada de dados com `close` e `adjusted_close` |
| `factor_fundamentals.csv` | long: colunas descritas abaixo |
| `small_cap_prices.csv` | wide: `date, ticker1, ticker2, ...` |
| `credit_spread.csv` | `date, spread` — FRED `BAA10Y` |
| `financial_conditions.csv` | opcional, `date, NFCI` — Chicago Fed `NFCI` |
| `bil_prices.csv` | `date, BIL` |
| `small_cap_membership.csv` | opcional, wide de booleanos point-in-time |

Colunas obrigatórias de `factor_fundamentals.csv`:

```text
ticker,fiscal_date,available_date,market_cap,book_equity,total_assets,gross_profit
```

`available_date` é opcional. Quando vazia ou ausente, o código aplica a defasagem de
três meses. Cada ticker precisa de ao menos dois balanços para calcular crescimento do
ativo. Linhas incompletas não são imputadas: a empresa sai do ranking daquela data.

O tamanho e o valor podem receber `market_cap` diretamente. Quando os fundamentos
vierem como fatos SEC longos, o adaptador usa `shares_outstanding` e o **Close não
ajustado** na data do ranking; preço ajustado não é usado para valor de mercado porque
carrega ajustes de dividendos e desdobramentos. Os retornos continuam usando somente
`adjusted_close`.

## Execução

```powershell
python -m unittest discover -s tests -v
python run_quant_pipeline.py --input-dir dados --output-dir resultados/quant
```

Parâmetros principais podem ser alterados na linha de comando:

```powershell
python run_quant_pipeline.py --sleeve1-top-n 50 --sleeve1-rebalance-month 6 `
  --sleeve2-top-fraction 0.05 --stress-entry-z 1.0 --stress-exit-z 0.5 `
  --financial-conditions-file financial_conditions.csv --max-derisk 0.50
```

## Entregas geradas

A pasta de saída contém:

- sinais completos e seleção de cada sleeve;
- pesos mensais wide de cada sleeve;
- z-scores, votos por eixo, `derisk_sinal` e `derisk_aplicado` defasado no modo dual;
- carteira do Sleeve 2 sempre ligada e carteira com migração graduada para BIL;
- alocações mensais entre sleeves;
- pesos consolidados por instrumento, em formatos wide e long;
- retornos mensais dos sleeves e do fundo.

`fund_portfolio_monthly.csv` é a entrega longa mais direta: uma linha por mês e ativo
com peso positivo. Os CSVs de sinais preservam fatores brutos, z-scores, nota, rank e
data do balanço usado para auditoria de look-ahead.
