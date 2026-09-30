# Tese Infraestrutura de IA — chips, memória, data center e energia
**Data**: 2026-09-30 · **Snapshot**: 2026-09-29 (`snapshot_ohlcv_2026-09-29.parquet`, SHA-256 `976698b984b98e11…`)  
**Janela simulada**: 2020-02-03 a 2026-09-29 · **Motor**: Momentum ATR oficial, open t+1, 15 bps por ponta  
**Classificação**: pesquisa retrospectiva (`retrospective_pseudo_oos`), paper-only, sem aprovação para capital real.

## 1. Resultado das variantes pré-declaradas

| Variante | Retorno | CAGR | Vol. | Sharpe | Sortino | Max DD | Calmar |
|---|---|---|---|---|---|---|---|
| Buy & Hold, pesos iguais | +2510,9% | +63,5% | 42,9% | 1,36 | 2,00 | -49,7% | 1,28 |
| Buy & Hold, pesos por camada | +2824,0% | +66,3% | 42,1% | 1,42 | 2,09 | -49,4% | 1,34 |
| Momentum ATR, pesos iguais | +181,8% | +16,9% | 20,0% | 0,88 | 1,31 | -24,7% | 0,68 |
| Momentum ATR, pesos por camada | +236,2% | +20,0% | 20,1% | 1,01 | 1,52 | -25,9% | 0,77 |
| Momentum ATR + camadas + vol target 25% (principal) | +238,5% | +20,2% | 19,9% | 1,02 | 1,55 | -23,8% | 0,85 |
| SMH Buy & Hold (benchmark) | +770,4% | +38,5% | 37,5% | 1,06 | 1,54 | -45,3% | 0,85 |
| QQQ Buy & Hold (benchmark) | +231,8% | +19,8% | 24,9% | 0,85 | 1,22 | -35,6% | 0,56 |
| SPY Buy & Hold (benchmark) | +135,8% | +13,8% | 20,2% | 0,74 | 1,05 | -34,1% | 0,40 |

Sharpe da principal: **1,02**; Sharpe máximo esperado ao acaso com 5 tentativas: 0,28; DSR: **0,970**; PSR contra o Sharpe do QQQ (0,85): 0,671. Exposição média a mercado: 43,4%. Correlação média entre pares de ativos: 0,33.

## 2. Subperíodos (corte em 31/12/2022)

| Variante | Período | CAGR | Sharpe | Max DD |
|---|---|---|---|---|
| ATR_CAMADAS_VT | 2020-2022 | +11,3% | 0,66 | -19,0% |
| ATR_CAMADAS_VT | 2023-2026 | +27,6% | 1,29 | -23,8% |
| BH_CAMADAS | 2020-2022 | +28,8% | 0,81 | -49,4% |
| BH_CAMADAS | 2023-2026 | +103,2% | 1,91 | -41,9% |
| SMH_BH | 2020-2022 | +13,7% | 0,52 | -45,3% |
| SMH_BH | 2023-2026 | +61,7% | 1,53 | -36,0% |
| QQQ_BH | 2020-2022 | +6,4% | 0,36 | -35,6% |
| QQQ_BH | 2023-2026 | +31,5% | 1,46 | -22,9% |

## 3. Retornos por ano

| Ano | Momentum ATR + camadas + vol target 25% (principal) | Buy & Hold, pesos por camada | SMH Buy & Hold | QQQ Buy & Hold | Exposição média (principal) |
|---|---|---|---|---|---|
| 2020 | +21,3% | +80,9% | +56,6% | +41,1% | 43% |
| 2021 | +15,2% | +41,0% | +41,4% | +26,8% | 46% |
| 2022 | -2,2% | -18,0% | -34,3% | -33,1% | 36% |
| 2023 | +49,9% | +116,2% | +72,3% | +53,8% | 56% |
| 2024 | +39,7% | +118,3% | +38,5% | +24,8% | 44% |
| 2025 | -1,1% | +58,8% | +48,7% | +20,2% | 35% |
| 2026 | +19,6% | +86,7% | +68,5% | +20,1% | 43% |

## 4. Exclusão de um ativo por vez (estratégia principal)

| Ativo excluído | CAGR | Sharpe | Max DD |
|---|---|---|---|
| NVDA | +12,9% | 0,75 | -24,9% |
| MU | +22,4% | 1,08 | -23,1% |
| SMCI | +20,7% | 1,04 | -24,5% |
| STM | +20,6% | 1,02 | -24,5% |
| VRT | +18,8% | 1,02 | -24,4% |
| PWR | +19,9% | 0,98 | -22,8% |
| GEV | +20,0% | 1,00 | -22,5% |
| VST | +20,4% | 0,94 | -25,8% |
| BE | +18,9% | 1,01 | -24,6% |
| DGXX | +19,9% | 1,01 | -23,8% |
| VIVO | +20,4% | 1,04 | -23,8% |
| RDW | +19,6% | 1,00 | -23,6% |

## 5. Estresse de custos e slippage

| Cenário | Custo/ponta | Slippage stop | CAGR | Sharpe | Max DD |
|---|---|---|---|---|---|
| base_15bps | 0,15% | 0,00% | +20,2% | 1,02 | -23,8% |
| liquidez_reduzida | 0,35% | 0,15% | +13,7% | 0,75 | -25,8% |
| severo_50bps | 0,50% | 0,30% | +9,0% | 0,53 | -27,2% |

## 6. Ativos individuais

| Ticker | Camada | Peso-alvo | Início | ATR CAGR | ATR Max DD | B&H CAGR | B&H Max DD | Beta QQQ |
|---|---|---|---|---|---|---|---|---|
| `NVDA` | Chips e computação | 20% | 2020-01-02 | +26,6% | -46,7% | +71,7% | -66,4% | 1,66 |
| `MU` | Chips e computação | 10% | 2020-01-02 | -0,6% | -75,2% | +55,2% | -57,8% | 1,46 |
| `SMCI` | Chips e computação | 5% | 2020-01-02 | +0,2% | -80,2% | +52,9% | -84,8% | 1,42 |
| `STM` | Chips e computação | 5% | 2020-01-02 | +5,0% | -49,8% | +10,1% | -67,2% | 1,37 |
| `VRT` | Infraestrutura do data center | 12% | 2020-01-02 | +20,3% | -45,7% | +58,5% | -71,2% | 1,34 |
| `PWR` | Infraestrutura do data center | 10% | 2020-01-02 | +21,0% | -34,8% | +50,9% | -42,4% | 0,82 |
| `GEV` | Geração de energia | 10% | 2024-03-27 | +25,5% | -40,8% | +122,2% | -38,3% | 1,43 |
| `VST` | Geração de energia | 10% | 2020-01-02 | +5,6% | -60,5% | +31,1% | -48,9% | 0,80 |
| `BE` | Geração de energia | 8% | 2020-01-02 | +8,1% | -61,5% | +71,1% | -79,9% | 1,69 |
| `DGXX` | Satélites especulativos | 4% | 2021-01-08 | -9,6% | -88,1% | +11,5% | -97,4% | 1,93 |
| `VIVO` | Satélites especulativos | 3% | 2020-01-02 | +7,1% | -92,7% | -14,4% | -99,6% | 0,88 |
| `RDW` | Satélites especulativos | 3% | 2021-01-14 | +1,0% | -69,0% | +0,5% | -87,3% | 1,54 |

## 7. Postura do sinal em 2026-09-29 (paper, não é ordem)

| Ticker | Sinal | Entrada | Stop atual | Distância ao stop | Peso-alvo vigente | Peso indicativo próximo mês |
|---|---|---|---|---|---|---|
| `NVDA` | comprado | 2026-09-29 | 218,04 | 4,2% | 20,0% | 20,0% |
| `MU` | comprado | 2026-09-18 | 981,64 | 8,5% | 10,0% | 10,0% |
| `SMCI` | comprado | 2026-09-18 | 37,45 | 9,5% | 5,0% | 5,0% |
| `STM` | comprado | 2026-09-21 | 49,39 | 7,8% | 5,0% | 5,0% |
| `VRT` | fora (caixa) | — | — | — | 12,0% | 12,0% |
| `PWR` | comprado | 2026-09-22 | 598,90 | 8,8% | 10,0% | 10,0% |
| `GEV` | comprado | 2026-09-23 | 876,33 | 9,8% | 10,0% | 10,0% |
| `VST` | comprado | 2026-09-29 | 130,45 | 8,0% | 10,0% | 10,0% |
| `BE` | comprado | 2026-09-04 | 241,26 | 20,7% | 8,0% | 8,0% |
| `DGXX` | comprado | 2026-09-17 | 3,91 | 8,8% | 5,7% | 5,7% |
| `VIVO` | fora (caixa) | — | — | — | 0,0% | 0,0% |
| `RDW` | comprado | 2026-09-25 | 9,93 | 8,0% | 4,3% | 4,3% |

Multiplicador de volatilidade vigente: 1,00; exposição a mercado atual: 89,3%.

## 8. Limitações

- **Viés de seleção ex-post**: o universo foi escolhido em setembro de 2026, depois da alta dos nomes ligados à IA. O backtest mede o que teria acontecido com esta cesta, não a capacidade de escolhê-la em 2020.
- Um único fator domina a carteira (capex de IA dos hiperescaladores); a diversificação entre camadas é menor do que o número de ativos sugere.
- Microcaps (VIVO, DGXX) tiveram liquidez mínima em parte da amostra; o filtro de US$ 5 mi evita alocação nesses períodos, mas fills a 15 bps continuam otimistas para elas.
- Preços sem dividendos, caixa sem remuneração, Sharpe com taxa livre de risco zero, sem impostos nem câmbio para investidor brasileiro.
- Nenhum parâmetro foi otimizado, mas cinco variantes foram comparadas; o DSR considera apenas essas cinco tentativas.
- Quando só um satélite especulativo é elegível, ele recebe os 10% da camada inteira (VIVO em 2021, RDW em 2025).
- A banda de 10 p.p. do vol target pode deixar o multiplicador parado um pouco abaixo de 1 depois de um episódio volátil; o efeito médio é pequeno (multiplicador médio 0,98).
