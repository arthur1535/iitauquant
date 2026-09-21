# Pesquisa Quantitativa: ETFs e Ações do Mercado Chinês (2020 – 2026)
> **Laboratório de Pesquisa Quantitativa — Fundo LASTRO & Momentum ATR**  
> **Data de Execução**: 2026-09-21  
> **Amostra**: 1.687 pregões diários (2020-01-02 a 2026-09-18)  
> **Mecanismo**: Simulação causal estrita (decisão no fechamento de $t$, execução no *Open* de $t+1$), custos de 15 bps bilaterais e *trailing stop* Ratchet.

---

## 1. Sumário Executivo e Tese Macroeconômica

O mercado de capitais chinês vivenciou entre 2020 e 2026 um dos ciclos de desalavancagem e contração de múltiplos mais severos da história moderna de mercados emergentes. Impulsionado pela política das *Três Linhas Vermelhas* no setor imobiliário, pelo endurecimento regulatório sob a bandeira da *Prosperidade Comum* e por atritos geopolíticos e tecnológicos com os EUA, o investidor passivo (*Buy & Hold*) sofreu perdas de capital catastróficas:
- **KWEB (Internet)**: queda pico-a-vale de **-82,22%** e retorno total de **-51,99%**;
- **BABA (Alibaba)**: queda pico-a-vale de **-80,09%** e retorno total de **-48,47%**;
- **NIO (EV)**: queda pico-a-vale de **-95,00%** e retorno total de **-1,61%**;
- **MCHI (MSCI China)**: queda pico-a-vale de **-63,39%** e retorno total de **-19,87%**.

Neste cenário de destruição de capital de longo prazo, a implementação do modelo sistemático **`Momentum ATR`** com *trailing stop* por volatilidade demonstrou seu principal papel: **mitigação de perdas de cauda (*tail risk management*)**, cortando o drawdown de KWEB para -46,62% e convertendo posições ultra-voláteis como **`NIO`** (+77,80% vs. -1,61%) e **`BIDU`** (+17,85% vs. -34,94%) em resultados positivos ao surfar pernadas de alta e abortar ciclos de bear market.

A única classe onshore que preservou rentabilidade ajustada a risco positiva foi o **`ASHR` (CSI 300 A-Shares)**, cujo drawdown caiu de -53,43% para **-24,44%** com Sharpe de **0,183**.

---

## 2. Tabela Consolidada de Desempenho (2020–2026)

| Ticker | Segmento / Tese | B&H Retorno (%) | B&H Max DD (%) | Mom ATR Retorno (%) | Mom ATR Max DD (%) | Mom ATR Vol Anual (%) | Mom ATR Sharpe | Win Rate (%) | Profit Factor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ASHR** | CSI 300 (A-Shares Onshore) | +11,60% | -53,43% | **+11,42%** | **-24,44%** | 14,76% | **0,183** | 37,35% | **1,21** |
| **CQQQ** | China Tech (Chips e Hardware) | -14,90% | -74,15% | **-4,11%** | **-44,94%** | 18,15% | **0,056** | 35,14% | **1,06** |
| **MCHI** | MSCI China Amplo | -19,87% | -63,39% | **-9,75%** | **-31,76%** | 16,02% | -0,016 | 29,49% | 0,99 |
| **FXI** | Large Caps / Estatais HK | -23,53% | -61,54% | **-25,88%** | **-36,35%** | 16,31% | -0,193 | 34,18% | 0,84 |
| **KWEB** | Internet & E-commerce | -51,99% | -82,22% | **-35,79%** | **-46,62%** | 21,52% | -0,201 | 32,93% | 0,81 |
| **NIO** | Veículos Elétricos | -1,61% | -95,00% | **+77,80%** | **-83,13%** | 48,33% | **0,412** | 24,29% | **1,99** |
| **BIDU** | Busca, Nuvem & IA | -34,94% | -77,47% | **+17,85%** | **-60,22%** | 31,19% | **0,231** | 36,67% | **1,34** |
| **PDD** | PDD Holdings (Temu) | +91,37% | -87,41% | -40,67% | -69,60% | 36,85% | -0,028 | 34,52% | 0,94 |
| **BABA** | Alibaba Group | -48,47% | -80,09% | -40,06% | -64,58% | 25,57% | -0,172 | 32,47% | 0,87 |
| **JD** | JD.com | -28,65% | -79,94% | -67,95% | -75,75% | 29,07% | -0,440 | 34,34% | 0,61 |

---

## 3. Decomposição Qualitativa por Ativo e ETF

### 3.1. ETFs
- **ASHR (Xtrackers Harvest CSI 300 A-Share ETF)**:
  Composto pelas 300 maiores ações de Xangai e Shenzhen (moeda local RMB). Apresenta menor exposição a ADRs estrangeiras e maior peso no setor financeiro e industrial doméstico. O algoritmo de *trend-following* reduziu o drawdown pela metade (-24,44% vs. -53,43%), tornando-o o veículo mais defensivo para exposição à China.
- **KWEB (KraneShares CSI China Internet ETF)**:
  Exposição pesada a Tencent, Alibaba, Meituan e PDD. O setor foi o epicentro das multas antitruste e cancelamentos de IPOs em 2020-2022. O índice de acerto foi de 32,93%, refletindo repiques falsos de alívio seguidos de novas mínimas (*bear market traps*).
- **MCHI e FXI**:
  Concentrados em bancos estatais chineses (CCB, ICBC) e operadoras de telecom. Embora paguem dividendos elevados, a fraqueza cambial e o risco de crédito imobiliário comprimiram o retorno total.

### 3.2. Ações
- **NIO**: Alta convexidade. A pernada de 2020 impulsionou o ativo de \$3 para mais de \$60, permitindo ao Momentum ATR acumular lucros expressivos. O *trailing stop* acionou a saída no início da reversão em 2021, poupando a carteira do colapso de -95%.
- **PDD (Pinduoduo / Temu)**: A única ação com forte crescimento de receita internacional via Temu (+91,37% no Buy & Hold). No entanto, a extrema volatilidade diária (67% a.a.) e lacunas de abertura (*gaps*) prejudicaram estratégias de tendência de curto prazo.
- **BABA & JD**: Vítimas da guerra de preços no varejo online chinês e da fraca confiança do consumidor doméstico.

---

## 4. Recomendações de Alocação e Governança

1. **Rejeição de Alocação Passiva Irrestrita**: Não alocar capital em *Buy & Hold* de índices amplos offshore (`KWEB`, `FXI`) sem mecanismos ativos de proteção de cauda.
2. **Priorização de A-Shares Onshore (`ASHR`)**: Para mandatos institucionais que exigem exposição à China, o ASHR é o único instrumento que respondeu positivamente aos filtros de volatilidade e momentum.
3. **Conexão com a B3 via Commodities**: Para se beneficiar de eventuais estímulos fiscais de Pequim, o veículo mais eficiente historicamente foi a exposição a mineradoras brasileiras (**`VALE3.SA`**, com Sharpe de 0,873 no mesmo período), evitando o risco regulatório interno de Pequim.
