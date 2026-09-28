# Blueprint de backtest: apostas e ações brasileiras

`scripts/backtest_bets.py` implementa um experimento exploratório, sem corretora,
com pandas/numpy e replay facultativo real em `vectorbt.Portfolio.from_orders`.
O código não baixa séries de apostas nem atribui causalidade a retornos.
`--demo` usa apenas tickers SYNTH e dados artificiais: seus resultados verificam
software e não devem aparecer como evidência da tese econômica.

## Executar

```powershell
.venv/Scripts/python.exe scripts/backtest_bets.py --demo --ablations --output-dir tmp/bets_demo
.venv/Scripts/python.exe -m pytest tests/test_bets_blueprint.py -q

# Dados próprios, sem fabricar eventos ou buscas:
.venv/Scripts/python.exe scripts/backtest_bets.py --prices precos.csv --benchmark benchmark.csv --features features.csv --exploratory --ablations --output-dir results/bets_research/meu_experimento
```

`--exploratory` é obrigatório para dados CSV. Preservar vintages é condição
necessária, mas este programa não certifica a autenticidade do universo ou das
publicações. Ele não promove retrospectivamente o experimento a teste cego.

## Contratos de dados

**Preços longos**, uma linha por sessão/ticker:

```text
date,ticker,sector,open,high,low,close,raw_close,volume,eligible
```

- `date` sem timezone, data da sessão B3; OHLC na mesma base ajustada, coerente
  entre todas as colunas e ao longo da série. Não misturar Close bruto com Open
  ajustado. O input deve tratar dividendos, JCP, splits, grupamentos, cisões e
  tickers históricos antes da execução.
- `raw_close` é o preço bruto e `volume` a quantidade bruta negociada: produto
  em reais para liquidez. Esses campos não entram no retorno total.
- `eligible` é 0/1 observado naquela sessão, incluindo históricos de retiradas
  e deslistagens. Uma cesta selecionada hoje tem viés de sobrevivência.
- `sector` representa a classificação disponível naquela data. Nenhum setor é
  inferido automaticamente pelo código.
- Não preencher suspensões. Ausência de preço em posição carregada interrompe
  o programa; liquidação/deslistagem exige resolução externa e documentada.
- Quantidades fracionárias na base ajustada são unidades contábeis sintéticas,
  não números de ações enviáveis à bolsa; lotes e dividendos em caixa não são
  simulados separadamente.

**Benchmark**, uma linha por sessão, calendário principal:

```text
date,ibov,cdi_return
```

`ibov` é nível do índice; `cdi_return` é retorno decimal CDI do intervalo desde
a sessão anterior, já incorporando calendário/feriados (não taxa anual).

**Features**, snapshots completos publicados, sem timezone implícito:

```text
available_at,search_relief_z,regulation_score,vintage_id
2025-01-06T09:00:00-03:00,...,...,identificador_real_da_fotografia
```

`available_at` deve ser a data/hora em que TODOS os campos do snapshot estavam
disponíveis. `regulation_score` em [-1,1], definido por regra congelada antes de
medir retornos; positivo significa endurecimento na hipótese. Não é variação
de alíquota nem intensidade estimada causalmente. `search_relief_z>0` representa
alívio no interesse por apostas segundo transformação definida no gerador de
features. `vintage_id` é obrigatório e não pode estar vazio. O gerador separado
`scripts/build_bets_features.py` pode preparar os snapshots.

O merge usa `available_at <= 18:00 America/Sao_Paulo` de cada sessão; sinal
conhecido até esse horário só executa na abertura da próxima sessão. O cutoff
é um horário operacional fixo após o fechamento, não o horário histórico exato
do leilão B3. Snapshots com mais de 14 dias corridos deixam de habilitar o gate.
Mudança regulatória persistente deve ser carregada em novos snapshots semanais
com origem/vintage de cada componente preservados pelo gerador.

## Regras efetivamente implementadas

1. **Gate combinado:** regulation_score > 0 e search_relief_z > 0, com snapshot
   fresco. Ausência de sinal mantém caixa. Perda do gate causa saída imediata
   na próxima abertura, sem esperar duas semanas.
2. **Elegibilidade diária:** eligible=1; ADV60 >= R$20 milhões; beta de retornos
   simples diários contra IBOV em janela252 (mínimo126) entre0,7 e1,8;
   M20>0; Close>SMA200; M12–1>0. M20=Close/Close.shift(20)−1;
   M12–1=Close.shift(21)/Close.shift(252)−1. Este filtro é persistente,
   diferente do cruzamento de momentum do motor original do repositório.
3. **Seleção semanal:** primeira sessão de cada semana usa o fechamento anterior;
   top6 por M12–1/vol60 anualizada. Todos os cálculos usam apenas o passado.
4. **Pesos:** inversa vol60; exposição bruta máxima planejada80%; máximo15% por
   nome e35% por setor; risco de stop por posição <=0,5% NAV; redução adicional
   se volatilidade ex ante pela matriz de covariância60 ultrapassar12% a.a.
   Caps apenas reduzem pesos, sem redistribuição; caixa absorve a sobra.
5. **Execução:** vendas de rebalanceamento antes das compras, caixa compartilhado,
   custo15 bps por ponta. Ordens de rebalanceamento limitadas a1% ADV60; ordens
   de saída por risco/stop são integrais e **não** respeitam esse limite. Custos
   de mercado para essas saídas devem ser estressados antes de uso econômico.
6. **Stops:** ATR14 SMA do True Range; entrada na abertura menos2,5 ATR anterior.
   Stop carregado é verificado primeiro contra abertura (gap) e depois Low.
   Gap preenche na abertura; intraday preenche no stop; ambos descontam10 bps
   extras de slippage, além da comissão. Após sobreviver à barra:
   stop=max(stop anterior,Close−2,5ATR); só vale para a próxima sessão.
   Não reentrar no mesmo dia após saída por risco/stop. Aumentos de posição
   podem apertar o stop na abertura usando apenas ATR anterior e preço aberto.
7. **Outras saídas:** M20<=0, Close<SMA100 ou elegibilidade perdida, avaliados
   no snapshot anterior; retirada do ranking é tratada no próximo rebalance.
8. **Caixa:** saldo do fechamento anterior recebe CDI no início da sessão;
   primeira sessão começa no capital informado sem rendimento prévio. Posições
   finais permanecem marcadas a mercado, sem liquidação artificial.

Limites de peso são metas no rebalanceamento, não barreiras contínuas: gaps,
drift e custos podem causar pequenos excessos entre ajustes. Stops não garantem
a perda planejada de0,5% NAV. A estrutura não calcula Kelly nem contribuição
marginal igual de risco: inversa volatilidade é uma aproximação de alocação.
Parâmetros são hipóteses explícitas no dataclass `Config`, não ótimos estimados.

## Resultados e validação

O programa grava curvas, ordens, snapshots alinhados e manifesto JSON. As
ablações são: combinado, preço apenas, buscas apenas e regulação apenas; todas
mantêm o mesmo universo, sizing, custos e demais filtros. O teste não inclui
automaticamente controles setoriais, choques de juros, eventos macro, bootstrap,
DSR, placebo ou regressão causal — esses são próximos experimentos necessários.

Sharpe e Sortino usam excesso diário sobre CDI, anualização252; downside é RMS
dos excessos negativos incluindo zeros nos demais dias. Drawdown deriva da
curva NAV; retorno/CAGR inclui CDI do caixa e custos. A primeira sessão tem
retorno0. As métricas cobrem **todo calendário recebido, inclusive aquecimento
em caixa antes dos primeiros sinais**; comparar amostras de mesmo calendário
ou recalcular métricas no intervalo de avaliação congelado antes da pesquisa.

Testes cobrem disponibilidade de features após cutoff, rejeição de timezone
ausente, invariância do passado a mutações futuras, entrada no pregão seguinte,
caixa/custos, metas de risco, gaps e preço ausente em posição aberta. Validação
de software não demonstra rentabilidade, capacidade de execução ou causalidade.

## Replay real com vectorbt

`--vectorbt-replay` reproduz o livro de ordens com uma linha por evento e uma
marcação diária. Como `from_orders` não remunera caixa, preços e fills são
divididos pelo índice CDI acumulado; o valor final é reconvertido para reais.
Essa mudança de unidade reproduz precisamente o caixa remunerado, preserva
quantidades, taxas e sequência compartilhada das ordens. O script exige que a
curva diária reconciliada coincida com o motor em rtol1e−8 e atolR$0,01.
O replay verifica contabilidade; sinais e decisões de stop vêm do motor original.
Não usar estatísticas anualizadas das linhas de evento em vectorbt: há várias
linhas por sessão e o calendário econômico é a curva diária exportada.

No ambiente verificado, vectorbt1.1.0 e Plotly7 têm incompatibilidade de template
`scattermapbox`. Não foi alterada a `.venv`. A compatibilidade opcional pode ser
isolada em `tmp` e aplicada apenas ao processo:

```powershell
.venv/Scripts/python.exe -m pip install --target tmp/bets_plotly_compat 'plotly<6'
$env:PYTHONPATH = (Resolve-Path tmp/bets_plotly_compat).Path
.venv/Scripts/python.exe scripts/backtest_bets.py --demo --vectorbt-replay --output-dir tmp/bets_vectorbt
Remove-Item Env:PYTHONPATH
```

Se já houver PYTHONPATH personalizado, preserve/restaure seu valor em vez de
removê-lo. O teste de replay executa subprocesso com PYTHONPATH próprio quando
esse target existe e vectorbt está instalado; caso contrário marca skip.
