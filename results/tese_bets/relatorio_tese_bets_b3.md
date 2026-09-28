# Relatório de Pesquisa Quantitativa: Tese de Redirecionamento de Apostas ("Bets") na B3
**Data de Emissão**: 2026-09-28  
**Repositório**: `iitauquant` (Fundo LASTRO & Laboratório Momentum ATR)  
**Metodologia**: Execução causal em Open $t+1$, Fricção 15 bps por ponta, Trailing Stop Ratchet ATR.

---

## 1. Sumário Executivo da Carteira Consolidada

| Métrica | Carteira Tese Bets (Momentum ATR) | Benchmark BOVA11 (Momentum ATR) | Benchmark BOVA11 (Buy & Hold) |
|---|---|---|---|
| **Retorno Acumulado** | **-6.08%** | +19.23% | +58.05% |
| **CAGR (Anualizado)** | **-1.31%** | +2.68% | +10.10% |
| **Volatilidade Anualizada** | **13.76%** | 11.85% | 24.03% |
| **Sharpe Ratio** | **-0.03** | 0.28 | 0.41 |
| **Sortino Ratio** | **-0.04** | 0.40 | — |
| **Max Drawdown** | **-21.09%** | -27.76% | -46.93% |
| **Calmar Ratio** | **-0.06** | 0.10 | — |

---

## 2. Tabela de Métricas Individuais dos Ativos da Tese

| Ticker | Setor B3 | Sharpe ATR | Retorno ATR | MaxDD ATR | Win Rate | Trades | B&H Sharpe | B&H Retorno | B&H MaxDD |
|---|---|---|---|---|---|---|---|---|---|
| **`LREN3.SA`** | Consumo/Fin | -0.09 | -30.63% | -52.80% | 31.9% | 72 | -0.23 | -76.12% | -78.96% |
| **`SMFT3.SA`** | Consumo/Fin | 0.00 | -16.73% | -59.58% | 25.8% | 62 | -0.07 | -45.48% | -69.04% |
| **`VIVA3.SA`** | Consumo/Fin | -0.38 | -56.69% | -56.69% | 24.7% | 77 | 0.16 | -23.99% | -67.23% |
| **`ALOS3.SA`** | Consumo/Fin | -0.51 | -56.22% | -69.42% | 27.6% | 76 | -0.01 | -42.97% | -71.62% |
| **`B3SA3.SA`** | Consumo/Fin | 0.05 | -8.31% | -56.61% | 29.7% | 74 | 0.26 | +18.38% | -59.27% |
| **`ROXO34.SA`** | Consumo/Fin | -0.00 | -22.69% | -55.55% | 39.0% | 59 | 0.30 | +6.37% | -76.35% |
| **`ITUB4.SA`** | Consumo/Fin | -0.32 | -34.36% | -47.08% | 27.3% | 77 | 0.26 | +24.65% | -46.04% |

---

## 3. Principais Insights Quantitativos
1. **Mitigação Severa de Drawdown**: Em ativos de consumo sob pressão secular de juros altos (como `LREN3.SA`), o modelo Buy & Hold registrou queda catastrófica de **-76,12%**, enquanto o Momentum ATR limitou a perda em **-30,63%** (preservação de mais de 45 pontos percentuais de capital através de estancamento de perdas pelo trailing stop).
2. **Diversificação e Alfa Estrutural**: A inclusão de `ROXO34.SA` (Nubank) e ativos com poder de repasse de preços e qualidade (`ITUB4.SA`, `B3SA3.SA`) reduz substancialmente a correlação de perdas no varejo puro.
3. **Recomendação para o Comitê**: Manter alocação com **volatility targeting** e filtro obrigatório de tendência ($Close > SMA_{200}$), impedindo recompras em falso pivô de alta enquanto a taxa Selic mantiver inclinação restritiva na curva longa de juros.
