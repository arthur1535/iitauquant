# Pesquisa Avançada de Métodos Quantitativos para o Fundo LASTRO e OMS
> **Documento de Engenharia Financeira & Research Buy-Side**  
> **Repositório**: `iitauquant` (Desafio Quant AI 2026)  
> **Data**: 2026-09-21  

---

## 1. Visão Geral Executiva

Este documento reúne a pesquisa aprofundada de métodos quantitativos de ponta praticados por hedge funds institucionais (como AQR, Two Sigma, Renaissance Technologies, Bridgewater e Man Group) com foco em **aplicabilidade direta e viável** sobre a arquitetura do fundo **LASTRO** e do **Laboratório Momentum ATR**.

Os métodos pesquisados atacam diretamente as limitações identificadas no projeto:
1. Instabilidade e concentração na alocação de ativos;
2. Ponto cego macro em choques de taxa de juros (como ocorrido em 2022);
3. Filtros de tendência com menor defasagem temporal;
4. Validação causal fora da amostra (anti-overfitting);
5. Modelagem de microestrutura e impacto de mercado.

---

## 2. Métodos de Alocação de Portfólio & Otimização de Risco

### 2.1. Hierarchical Risk Parity (HRP) — Marcos López de Prado (2016)
* **O Problema de Markowitz**: A Otimização de Média-Variância (MVO) clássica exige a inversão da matriz de covariância ($\Sigma^{-1}$). Quando os ativos são correlacionados ou a amostra de tempo é limitada, a matriz torna-se mal-condicionada, gerando pesos extremos, instáveis e péssimos fora da amostra.
* **Como o HRP Funciona**:
  1. **Tree Clustering**: Agrupa os ativos hierarquicamente com base na distância de correlação $d_{i,j} = \sqrt{0.5 \times (1 - \rho_{i,j})}$.
  2. **Quasi-Diagonalization**: Reorganiza a matriz de covariância para colocar ativos com dinâmicas semelhantes lado a lado na diagonal.
  3. **Recursive Bisection**: Distribui o capital de cima para baixo na árvore de clusters, ponderando cada ramo inversamente à sua variância agregada.
* **Aplicação no LASTRO**:
  - Em vez de atribuir pesos fixos ou iguais ($1/N$) dentro do Top 50 do Sleeve 1 ou na cesta de Global Leaders (`NVDA`, `MSFT`, `VALE3`, `SPY`), o HRP aloca capital conforme a estrutura natural de correlação, evitando que ações de semicondutores e big techs monopolizem o risco do portfólio.

### 2.2. Encolhimento da Matriz de Covariância (Ledoit-Wolf Shrinkage)
* **Conceito**: Quando o número de ativos $N$ é relativamente grande em relação ao histórico temporal $T$, a matriz de covariância amostral superestima as maiores correlações e subestima as menores.
* **Mecanismo**: A matriz encolhida combina a matriz amostral empírica $S$ com uma matriz estruturada constante $F$ (alvo com correlações iguais):
  $$\Sigma_{\text{shrunk}} = \alpha F + (1 - \alpha) S$$
  onde $\alpha \in [0, 1]$ é o parâmetro ótimo de intensidade de encolhimento deduzido analiticamente por Ledoit & Wolf (2004).
* **Aplicação no Projeto**:
  - Elimina o ruído na estimação de covariâncias entre os sleeves e os líderes globais, tornando qualquer cálculo de volatilidade da carteira muito mais estável.

### 2.3. Equal Risk Contribution (ERC / Risk Budgeting)
* **Conceito**: No fundo LASTRO, a alocação base é 33% Factor / 33% Small Caps / 33% BIL. Contudo, em termos de risco, as Small Caps e as ações do S&P 500 carregam quase 98% da volatilidade total, enquanto o BIL carrega ~0%.
* **Mecanismo**: Ajusta os pesos $w_i$ para que a contribuição marginal de risco de cada manga para a volatilidade do fundo seja idêntica:
  $$RC_i = w_i \times \frac{(\Sigma w)_i}{\sigma_p} = \frac{\sigma_p}{K}$$
* **Aplicação no Projeto**:
  - Transforma o "33/33/33 de capital" em uma paridade de risco real, amortecendo drawdowns em períodos de volatilidade extrema.

---

## 3. Modelagem de Regimes Macroeconômicos (Resolvendo o Ponto Cego de 2022)

### 3.1. Modelo Multi-Eixo de Estresse com Estrutura a Termo (Yield Curve Slope)
* **Diagnóstico do Ponto Cego**: Em 2022, o spread de crédito corporativo `BAA10Y` falhou porque os spreads de dívida corporativa demoram meses para refletir um choque quando as empresas possuem liquidez em caixa. O choque real foi o aumento agressivo da taxa livre de risco pelo Federal Reserve (Fed Funds e Treasuries de 10 anos).
* **Solução Quantitativa**: Adicionar o **Slope da Curva de Juros** e a **Aceleração da Taxa de 10 Anos**:
  1. **Inclinação da Curva ($T_{10Y} - T_{2Y}$)**: Inversões e desinversões abruptas antecipam recessões e quebras de liquidez.
  2. **Z-score da Taxa de 10 Anos**: Desvio móvel da taxa de 10 anos em relação à sua média móvel de 12 meses. Se $z > 1.5$, identifica-se choque inflacionário / de taxa de desconto, acionando o desinvestimento preventivo para `BIL`.

### 3.2. Hidden Markov Models (HMM) para Transição de Regimes
* **Conceito**: Em vez de limiares rígidos de histerese (ex.: z > 1,0 e z < 0,5 fixados manualmente, que geraram suspeita de overfitting no edital), o HMM presume que o mercado transita probabilisticamente entre $K=2$ ou $K=3$ estados não observáveis (*latentes*):
  - Estado 0: *Bull Market / Baixa Volatilidade / Expansão de Crédito*;
  - Estado 1: *Stress / Alta Volatilidade / Aperto de Liquidez*.
* **Vantagem**: A probabilidade de pertencer ao regime de estresse $P(S_t = 1)$ varia suavemente de 0% a 100%, permitindo um de-risking graduado endógeno sem limiares arbitrários.
* **Aplicação**: No laboratório Momentum ATR (que possui 1.678 observações diárias), o HMM possui dados suficientes para ser treinado de forma robusta e livre de overfitting.

---

## 4. Engenharia de Sinais & Filtragem de Tendência

### 4.1. L1 Trend Filtering (Boyd et al.)
* **Limitação das Médias Móveis**: Uma SMA ou EMA gera atraso (*lag*) proporcional à sua janela. Quando o mercado quebra bruscamente, o sinal demora semanas para estopar a posição.
* **O Método**: O filtro de tendência L1 resolve um problema de otimização convexa que minimiza o erro quadrático em relação à série de preços, com uma penalidade L1 na segunda diferença:
  $$\min_x \frac{1}{2} \|y - x\|_2^2 + \lambda \|D x\|_1$$
* **Resultado**: Produz uma linha de tendência linear por partes (*piecewise linear*), que acompanha o preço instantaneamente quando ocorre uma quebra de regime, mas filtra o ruído branco diário.

### 4.2. Dynamic Volatility Targeting (Vol-Targeting Causal)
* **Conceito**: Escalar a exposição total da carteira para manter uma volatilidade realizada anualizada constante (ex.: $\sigma_{\text{target}} = 10\%$).
* **Fórmula de Exposição**:
  $$w_t = \min\left(1.0, \frac{\sigma_{\text{target}}}{\hat{\sigma}_t}\right)$$
  onde $\hat{\sigma}_t$ é a volatilidade estimada por EWMA (Exponentially Weighted Moving Average) com decay $\lambda = 0.94$.
* **Efeito Comprovado**: Em momentos de calmaria, o fundo aproveita o *rally*; quando o VIX explode, o tamanho da posição é cortado automaticamente antes do stop ser atingido.

---

## 5. Validação Estatística Avançada (Anti-Overfitting)

### 5.1. Combinatorial Purged Cross-Validation (CPCV) — López de Prado (2018)
* **Por que K-Fold comum falha em finanças**:
  - Dados financeiros possuem dependência temporal e vazamento de informação (*leakage*) se os retornos de períodos adjacentes forem misturados.
* **A Estrutura do CPCV**:
  1. **Purging**: Remove das partições de treino as observações cujos rótulos de retorno se sobrepõem ao conjunto de teste.
  2. **Embargo**: Insere um intervalo cego (ex.: 5 a 21 dias) imediatamente após o conjunto de teste para eliminar a autocorrelação serial residual.
  3. **Combinações**: Gera $N$ caminhos históricos independentes out-of-sample combinando $k$ subgrupos.
* **Cálculo da Probability of Backtest Overfitting (PBO)**:
  - O CPCV permite traçar a distribuição de probabilidade de que a estratégia vencedora in-sample performe abaixo da mediana fora da amostra. Se $PBO > 0.5$, o modelo é descartado imediatamente.

---

## 6. Microestrutura e Modelagem de Custos de Transação

### 6.1. Modelo de Custo de Impacto Almgren-Chriss
* Em vez de assumir um custo fixo irreal de 10 bps para qualquer volume, hedge funds modelam o custo total de transação como:
  $$\text{Custo Total} = \text{Taxa Fixa} + \frac{\text{Bid-Ask Spread}}{2} + \gamma \sigma \left(\frac{Q}{\text{ADV}}\right)^{\alpha}$$
  onde $Q$ é o volume financeiro da ordem, $\text{ADV}$ é o Volume Médio Diário e $\alpha \approx 0.5$ (lei da raiz quadrada do impacto de mercado).
* **Aplicação**: No OMS paper, esse modelo impede que a estratégia execute ordens grandes demais em Small Caps ilíquidas, simulando a derrapagem (*slippage*) institucional real.

---

## 7. Roteiro Prático de Implementação no `iitauquant`

| Prioridade | Método Quantitativo | Módulo Alvo | Ganho Direto para o Projeto |
|---|---|---|---|
| **Fase 1 (Imediata)** | **Purged Walk-Forward & DSR/PBO** | `scripts/run_out_of_sample_audit.py` | Gera os relatórios OOS solicitados na sincronização com o ChatGPT |
| **Fase 2 (Curto Prazo)** | **Hierarchical Risk Parity (HRP)** | `quant_fund/portfolio_hrp.py` | Alocação ótima entre Global Leaders e mangas do fundo |
| **Fase 3 (Médio Prazo)** | **Macro Yield Curve Slope** | `quant_fund/risk_overlay.py` | Resolve definitivamente o ponto cego do choque de juros de 2022 |
| **Fase 4 (Operacional)** | **Slippage por Raiz Quadrada no OMS** | `src/server/storage.py` & `src/backtest/engine.py` | Fricção realista de mercado para auditoria institucional |
