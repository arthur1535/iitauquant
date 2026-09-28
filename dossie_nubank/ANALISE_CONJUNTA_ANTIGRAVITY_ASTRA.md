# Dossiê de Inteligência & Análise Conjunta: Nu Holdings (`NU` / `ROXO34`)
**Autoria Conjunta**: Google Antigravity (Motor Quantitativo & Backtest B3) & ChatGPT Astra (Macro, M&A & Equity Research)  
**Data**: Setembro de 2026  
**Repositório Base**: `iitauquant` (Fundo LASTRO & Laboratório Momentum ATR)

---

## 1. O Ponto de Inflexão: M&A do Monzo vs O Fim da Farra das Bets

O investidor está diante de um clássico episódio de **deslocamento de preço por fluxo de M&A** somado a um **vetor positivo não precificado na qualidade do crédito doméstico**:

1. **A Queda (-12,5% em `NU` e -10,5% em `ROXO34`)**: Foi precipitada pelo temor de diluição acionária de 12% a 18% para pagar entre £ 8 e £ 10 bilhões no neobank britânico Monzo (múltiplo > 100x lucro pré-impostos). O mercado puniu o papel como se a transação destruísse valor imediato, ignorando que o Nubank absorve **£ 25,7 bilhões (US$ 34,2 bilhões) em depósitos de funding barato em moeda forte** e 16M de correntistas no Reino Unido.
2. **A Descompressão das Apostas ("Bets")**: O endurecimento regulatório no Brasil (bloqueio de >2.000 sites, proibição de cartões e PIX de benefícios sociais) estanca o dreno de R$ 20 bi a R$ 30 bi mensais que sangrava o crédito rotativo do Nubank. Cada alívio de 50 a 100 bps no custo do crédito libera entre **US$ 150 milhões e US$ 300 milhões líquidos por ano em despesas de PDD**, impulsionando o lucro líquido para além de US$ 4,5 bilhões.

---

## 2. Métricas Financeiras e Sensibilidade Modelada

| Indicador | Nubank (Pós-Queda Set/2026) | Itaú Unibanco (`ITUB4`) | Médio Bancos LatAm |
|---|---|---|---|
| **Cotação Atual** | **US$ 12,34 (NYSE) / R$ 10,68 (B3)** | R$ 35,50 | — |
| **Market Cap** | **US$ 59,2 bilhões** | ~US$ 62,0 bilhões | — |
| **P/L Projetado 2026e** | **14,0x** (com lucro Q2 anualizado) | 7,5x | 8,5x |
| **P/L Projetado 2027e** | **11,2x** (crescimento moderado) | 7,0x | 7,8x |
| **ROE Anualizado** | **33,0%** (Recorde) | 22,0% | 18,5% |
| **Índice de Eficiência** | **19,5%** (Líder Global) | 38,5% | 42,0% |
| **Depósitos Totais** | **US$ 45,3 bi (+US$ 34,2 bi com Monzo)** | ~US$ 180 bi | — |

### Sensibilidade de Alívio em PDD com a Regulação das Bets (Carteira de US$ 39,4B)
* **Alívio de 25 bps no Custo de Crédito**: Economia anual de PDD de **US$ 98M** $\to$ Lucro Líquido: **+US$ 74M (+1,74%)**
* **Alívio de 50 bps no Custo de Crédito**: Economia anual de PDD de **US$ 197M** $\to$ Lucro Líquido: **+US$ 148M (+3,48%)**
* **Alívio de 100 bps no Custo de Crédito**: Economia anual de PDD de **US$ 394M** $\to$ Lucro Líquido: **+US$ 296M (+6,96%)** $\to$ Lucro total atinge **US$ 4,54 bilhões/ano**.

---

## 3. Matriz de Recomendação & Execução Tática

```
                            ┌──────────────────────────────────────────────┐
                            │      DECISÃO DE ALOCAÇÃO NUBANK (NU)         │
                            │      Preço Atual: US$ 12,34 / R$ 10,68       │
                            └──────────────────────┬───────────────────────┘
                                                   │
                       ┌───────────────────────────┴───────────────────────────┐
                       ▼                                                       ▼
      ┌───────────────────────────────────┐                   ┌───────────────────────────────────┐
      │   INVESTIDOR DE LONGO PRAZO       │                   │       MESA TÁTICA / SWING         │
      │                                   │                   │                                   │
      │ • Tese: COMPRA GRADUAL (Dollar    │                   │ • Suporte Chave: US$ 11,80–12,00  │
      │   Cost Averaging em 3 tranches)   │                   │ • Gatilho: Cruzamento Mom20 > 0   │
      │ • Carregamento em ROE de 33% e    │                   │ • Trailing Stop ATR: 2,5x ATR     │
      │   P/L de 14x para neobank global  │                   │ • Alvo Técnico: Reteste US$ 14,50 │
      │ • Preço-Alvo 2026/27: US$ 18,00   │                   │ • Risco/Retorno: 3,2 : 1          │
      └───────────────────────────────────┘                   └───────────────────────────────────┘
```

---

## 4. Divisão de Trabalho: Antigravity ↔ ChatGPT Astra

* **Google Antigravity (Engine Quant)**:
  * Curadoria de cotações em [`data/market/NU.parquet`](file:///C:/Users/amand/OneDrive%20-%20Universidade%20Federal%20de%20Uberlândia/2026/iitauquant/data/market/NU.parquet) e [`data/market/ROXO34.SA.parquet`](file:///C:/Users/amand/OneDrive%20-%20Universidade%20Federal%20de%20Uberlândia/2026/iitauquant/data/market/ROXO34.SA.parquet).
  * Execução da modelagem e backtest em [`scripts/analisar_nubank_monzo_bets.py`](file:///C:/Users/amand/OneDrive%20-%20Universidade%20Federal%20de%20Uberlândia/2026/iitauquant/scripts/analisar_nubank_monzo_bets.py).
  * Renderização do dashboard visual em [`relatorios/nubank_monzo_bets_analise_conjunta.html`](file:///C:/Users/amand/OneDrive%20-%20Universidade%20Federal%20de%20Uberlândia/2026/iitauquant/relatorios/nubank_monzo_bets_analise_conjunta.html).
* **ChatGPT Astra (Fundamental & M&A Specialist)**:
  * Avaliação qualitativa da aprovação regulatória junto à PRA e FCA no Reino Unido.
  * Estratégia de precificação competitiva contra Revolut e bancos incumbentes britânicos.
  * Projeção do fluxo de caixa descontado (DCF) detalhado considerando a taxa de juros do Bank of England.
